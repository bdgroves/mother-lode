"""
Lidar points -> bare-earth DTM for one site window.

Adapted from Project Kiva (github.com/bdgroves/project-kiva). Source:

  ept      The USGS 3DEP point-cloud archive on AWS (Entwine Point Tiles).
           PDAL walks the octree and pulls only the nodes inside the window,
           so a 60-billion-point project costs a few hundred MB of transfer.
           EPT bounds must be given in EPSG:3857, the octree's own CRS: pass
           survey-CRS bounds and you get zero points back, with no error.


Ground returns only (ASPRS class 2), gridded with inverse-distance weighting.
Cells with no ground return nearby stay nodata: that is where buildings,
water and dense brush stood, and the gaps are part of the evidence.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import rasterio
import requests
from pyproj import Transformer

EPT = "https://s3-us-west-2.amazonaws.com/usgs-lidar-public/{project}/ept.json"


def utm_bounds(site):
    """Site window in its projected CRS, snapped to the cell size."""
    t = Transformer.from_crs("EPSG:4326", site["crs"], always_xy=True)
    cx, cy = t.transform(site["center"][1], site["center"][0])
    w, h = site["size_m"]
    r = site["res"]
    x0 = np.floor((cx - w / 2) / r) * r
    y0 = np.floor((cy - h / 2) / r) * r
    return float(x0), float(y0), float(x0 + w), float(y0 + h)


def lonlat_bounds(site, pad_m=30.0):
    x0, y0, x1, y1 = utm_bounds(site)
    t = Transformer.from_crs(site["crs"], "EPSG:4326", always_xy=True)
    xs, ys = t.transform([x0 - pad_m, x1 + pad_m, x0 - pad_m, x1 + pad_m],
                         [y0 - pad_m, y0 - pad_m, y1 + pad_m, y1 + pad_m])
    return min(xs), min(ys), max(xs), max(ys)


def _grid_stage(path, bounds, res):
    x0, y0, x1, y1 = bounds
    return {"type": "writers.gdal", "filename": str(path), "resolution": res,
            "output_type": "idw,count", "radius": res * 2.5, "window_size": 3,
            "nodata": -9999, "data_type": "float32",
            "bounds": f"([{x0},{x1 - res / 2}],[{y0},{y1 - res / 2}])"}


def _ground_stages(crs, bounds, pad=20.0):
    x0, y0, x1, y1 = bounds
    return [
        {"type": "filters.range", "limits": "Classification[2:2]"},
        {"type": "filters.reprojection", "out_srs": crs},
        {"type": "filters.crop",
         "bounds": f"([{x0 - pad},{x1 + pad}],[{y0 - pad},{y1 + pad}])"},
    ]


def run(pipeline) -> int:
    import pdal
    p = pdal.Pipeline(json.dumps({"pipeline": pipeline}))
    return p.execute()


def _ept_grid(project, site, out_tif: Path, log=print) -> int:
    bounds = utm_bounds(site)
    w, s, e, n = lonlat_bounds(site)
    t = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    mx0, my0 = t.transform(w, s)
    mx1, my1 = t.transform(e, n)
    meta = requests.get(EPT.format(project=project), timeout=60).json()
    log(f"  EPT {project}: {meta['points']:,} points in the project")
    pipe = [{"type": "readers.ept", "filename": EPT.format(project=project),
             "bounds": f"([{mx0},{mx1}],[{my0},{my1}])", "threads": 8}]
    pipe += _ground_stages(site["crs"], bounds)
    pipe += [_grid_stage(out_tif, bounds, site["res"])]
    n_ground = run(pipe)
    log(f"  {project}: {n_ground:,} ground returns in the window")
    return int(n_ground)


def fetch_ept(site, out_tif: Path, log=print) -> dict:
    """Grid each project in `project` (a name or a list, best first) and fill
    the first one's gaps from the next. Survey edges run through some windows:
    Columbia sits on the edge of the newer Sierra Nevada flight, and the 2011
    Calaveras-Tuolumne survey covers the rest.

    Where two surveys overlap, the later one is shifted by the median height
    difference in the overlap so the seam doesn't show; the shift is logged
    and kept in the provenance (it should be centimetres if both are NAVD88)."""
    projects = site["project"] if isinstance(site["project"], list) else [site["project"]]
    z = cnt = prof = None
    used, total, shifts = [], 0, {}
    for k, proj in enumerate(projects):
        part = out_tif.with_name(f"{out_tif.stem}_{k}.tif")
        n = _ept_grid(proj, site, part, log)
        if n == 0:
            continue
        with rasterio.open(part) as src:
            zi, ci, prof = src.read(1), src.read(2), src.profile
        zi = np.where((zi == -9999) | (ci <= 0), np.nan, zi)
        if z is None:
            z, cnt = zi, np.where(np.isfinite(zi), ci, 0)
        else:
            both = np.isfinite(z) & np.isfinite(zi)
            dz = float(np.median(z[both] - zi[both])) if both.sum() > 1000 else 0.0
            shifts[proj] = round(dz, 3)
            log(f"  {proj}: median offset to {used[0]} over {int(both.sum()):,} shared cells: {dz:+.3f} m")
            hole = ~np.isfinite(z) & np.isfinite(zi)
            z[hole] = zi[hole] + dz
            cnt[hole] = ci[hole]
            log(f"  {proj}: filled {hole.mean():.1%} of the window")
        used.append(proj)
        total += n
        if np.isfinite(z).mean() > 0.995:
            break
    if z is None:
        raise SystemExit("no ground returns from any project")
    prof.update(count=2)
    with rasterio.open(out_tif, "w", **prof) as d:
        d.write(np.where(np.isfinite(z), z, -9999).astype("float32"), 1)
        d.write(cnt.astype("float32"), 2)
    return {"source": "USGS 3DEP point cloud (EPT on AWS)", "project": ", ".join(used),
            "ground_points": total, "seam_shift_m": shifts}


def read_dtm(tif: Path, max_gap_m: float = 3.0):
    """IDW band with NaN where no ground return fell within max_gap_m."""
    from scipy.ndimage import distance_transform_edt
    with rasterio.open(tif) as src:
        z = src.read(1).astype(np.float32)
        cnt = src.read(2) if src.count > 1 else (z != -9999).astype(np.float32)
        prof, res = src.profile, src.res[0]
    z[z == -9999] = np.nan
    has = (cnt > 0) & np.isfinite(z)
    far = distance_transform_edt(~has) * res > max_gap_m
    z[far] = np.nan
    if not has.all():
        from motherlode.relief import fill_nodata
        filled, _ = fill_nodata(z)
        z = np.where(far, np.nan, filled)
    prof.update(count=1, nodata=np.nan, dtype="float32")
    return z, prof
