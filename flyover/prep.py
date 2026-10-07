"""Prepare a place for the forge3d flyover (runs on GitHub Actions).

Needs the place built first (`pixi run ml build columbia`), which leaves the
bare-earth DTM and relief products in data/sites/<id>/. This adds the NAIP
aerial photo and writes, into flyover/data/<id>/:

  dtm.tif       the DTM with its holes filled: water (no lidar returns) as a
                flat surface at the shoreline, anything else from its neighbours
  photo.png     NAIP true colour on the DTM grid
  relief.png    the photo shaded by the relief composite, so the diggings read
                (what the flyover drapes by default)
  place.json    name, CRS, bounds, elevations, NAIP year: everything the
                renderer needs, so the render needs no yaml and no PDAL

    pixi run python flyover/prep.py columbia
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from motherlode.cli import get_site, WORK          # noqa: E402
from motherlode.fetch import lonlat_bounds           # noqa: E402

OUT = ROOT / "flyover" / "data"


def fill_holes(z: np.ndarray) -> np.ndarray:
    """Holes inside the window are water: fill each flat at its shoreline (the low
    10th percentile of the ring around it). Holes touching the edge borrow neighbours."""
    bad = ~np.isfinite(z)
    lab, n = ndimage.label(bad)
    out = z.copy()
    edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])))
    for i, sl in enumerate(ndimage.find_objects(lab), start=1):
        if i in edge or sl is None:
            continue
        rs = slice(max(sl[0].start - 3, 0), sl[0].stop + 3)
        cs = slice(max(sl[1].start - 3, 0), sl[1].stop + 3)
        hole = lab[rs, cs] == i
        ring = ndimage.binary_dilation(hole, iterations=3) & ~hole & np.isfinite(z[rs, cs])
        if ring.any():
            sub = out[rs, cs]
            sub[hole] = np.percentile(z[rs, cs][ring], 10)
    rest = ~np.isfinite(out)
    if rest.any():
        idx = ndimage.distance_transform_edt(rest, return_distances=False, return_indices=True)
        out = out[tuple(idx)]
    return out.astype(np.float32)


def naip(site, transform, shape):
    """NAIP RGB on the DTM grid from Microsoft's Planetary Computer, newest year first."""
    import planetary_computer
    import pystac_client
    from rasterio.warp import Resampling, reproject
    cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1",
                                    modifier=planetary_computer.sign_inplace)
    items = sorted(cat.search(collections=["naip"], bbox=lonlat_bounds(site)).items(),
                   key=lambda it: it.datetime, reverse=True)
    out = np.zeros((3,) + shape, np.uint8)
    have = np.zeros(shape, bool)
    years = []
    for it in items:
        with rasterio.open(it.assets["image"].href) as src:
            band = np.zeros((3,) + shape, np.uint8)
            for b in range(3):
                reproject(rasterio.band(src, b + 1), band[b], dst_transform=transform,
                          dst_crs=site["crs"], resampling=Resampling.bilinear, dst_nodata=0)
        new = (band.max(axis=0) > 0) & ~have
        if new.any():
            out[:, new] = band[:, new]
            have |= new
            years.append(it.datetime.year)
        if have.mean() > 0.999:
            break
    print(f"  NAIP {sorted(set(years), reverse=True)}: {have.mean():.1%} covered")
    return np.moveaxis(out, 0, -1), (max(years) if years else None)


def main(sid: str) -> int:
    site = get_site(sid)
    work = WORK / sid
    with rasterio.open(work / "dtm.tif") as s:
        z, prof, T = s.read(1).astype(np.float32), s.profile, s.transform
    with rasterio.open(work / "products" / "composite.tif") as s:
        comp = s.read(1).astype(np.float32)
    out = OUT / sid
    out.mkdir(parents=True, exist_ok=True)
    filled = fill_holes(z)
    p = {k: v for k, v in prof.items() if k not in ("blockxsize", "blockysize", "tiled", "interleave")}
    p.update(count=1, dtype="float32", nodata=None, compress="deflate", predictor=3)
    with rasterio.open(out / "dtm.tif", "w", **p) as d:
        d.write(filled, 1)

    rgb, year = naip(site, T, z.shape)
    Image.fromarray(rgb).save(out / "photo.png")
    c = np.nan_to_num(comp, nan=0.5)
    c = (c - np.percentile(c, 1)) / (np.percentile(c, 99) - np.percentile(c, 1) + 1e-6)
    shade = 0.55 + 0.65 * np.clip(c, 0, 1)               # the composite is light on open ground, dark in pits
    rel = np.clip(rgb.astype(np.float32) / 255.0 * shade[..., None], 0, 1)
    Image.fromarray((rel * 255 + 0.5).astype(np.uint8)).save(out / "relief.png")

    l, b, r, t = rasterio.transform.array_bounds(z.shape[0], z.shape[1], T)
    # open water (holes with no lidar returns, away from the edge), biggest first, for labels
    from rasterio.warp import transform as warp
    bad = ~np.isfinite(z)
    lab, n = ndimage.label(bad)
    edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])))
    water = []
    for i in range(1, n + 1):
        if i in edge:
            continue
        rows, cols = np.nonzero(lab == i)
        area = rows.size * site["res"] ** 2
        if area < 2000:
            continue
        x, y = rasterio.transform.xy(T, rows.mean(), cols.mean())
        lon, lat = warp(site["crs"], "EPSG:4326", [x], [y])
        water.append({"lat": round(lat[0], 5), "lon": round(lon[0], 5), "area_m2": round(area)})
    water.sort(key=lambda w: -w["area_m2"])
    info = {"id": sid, "name": site["name"], "crs": site["crs"], "res_m": site["res"],
            "bounds": [l, b, r, t], "elev_m": [float(np.nanmin(z)), float(np.nanmax(z))],
            "naip_year": year, "lidar": " + ".join(site["project"]), "water": water}
    (out / "place.json").write_text(json.dumps(info, indent=1))
    print(f"  wrote {out.relative_to(ROOT)}: {z.shape[1]} x {z.shape[0]}, NAIP {year}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "columbia"))
