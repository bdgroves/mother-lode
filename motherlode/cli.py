"""
mother-lode command line.

    pixi run ml sites            # list places.yaml
    pixi run ml build columbia   # lidar -> bare-earth DTM -> relief -> web layers
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import click
import numpy as np
import rasterio
import yaml

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "data" / "sites"
WEB = ROOT / "docs" / "sites"


def catalog():
    return yaml.safe_load((ROOT / "places.yaml").read_text(encoding="utf-8"))["places"]


def get_site(sid):
    cat = catalog()
    if sid not in cat:
        raise click.BadParameter(f"unknown place {sid!r}; try: {', '.join(cat)}")
    return dict(cat[sid], id=sid)


def tif_write(path, arr, prof):
    p = {k: v for k, v in prof.items() if k not in ("blockxsize", "blockysize", "tiled", "interleave")}
    p.update(count=1, dtype="float32", nodata=np.nan, compress="deflate", predictor=3,
             tiled=True, blockxsize=256, blockysize=256, driver="GTiff")
    with rasterio.open(path, "w", **p) as d:
        d.write(arr.astype("float32"), 1)


@click.group()
def main():
    """mother-lode: gold country in lidar."""


@main.command()
def sites():
    for sid, s in catalog().items():
        built = (WEB / sid / "site.json").exists()
        click.echo(f"{'*' if built else ' '} {sid:14s} {s['name']:24s} {s['project']}  {s['res']} m")


@main.command()
@click.argument("sid")
@click.option("--refetch", is_flag=True)
def build(sid, refetch):
    """Points -> bare-earth DTM -> relief products -> web layers."""
    from motherlode import fetch, relief, web
    site = get_site(sid)
    work, out = WORK / sid, WEB / sid
    work.mkdir(parents=True, exist_ok=True)
    raw, prov_path = work / "dtm_raw.tif", work / "provenance.json"
    t0 = time.time()
    if refetch or not raw.exists():
        prov_path.write_text(json.dumps(fetch.fetch_ept(site, raw, log=click.echo)))
    prov = json.loads(prov_path.read_text())
    dtm, prof = fetch.read_dtm(raw)
    cover = float(np.isfinite(dtm).mean())
    click.echo(f"  DTM {dtm.shape[1]} x {dtm.shape[0]} at {site['res']} m, {cover:.1%} with ground returns")
    # mining landscapes are bigger than kiva walls: look a little wider
    prods = relief.all_products(dtm, site["res"], lrm_radius_m=site.get("lrm_m", 25.0),
                                horizon_m=site.get("horizon_m", 15.0))
    (work / "products").mkdir(exist_ok=True)
    tif_write(work / "dtm.tif", dtm, prof)
    for k, v in prods.items():
        tif_write(work / "products" / f"{k}.tif", v, prof)
    meta = web.export(prods, prof, out)
    zf = dtm[np.isfinite(dtm)]
    area = dtm.size * site["res"] ** 2
    info = {"id": sid, "name": site["name"], "blurb": " ".join(site.get("blurb", "").split()),
            "center": site["center"], "res_m": site["res"], "crs": site["crs"], "size_m": site["size_m"],
            "source": prov["source"], "project": prov["project"], "ground_points": prov["ground_points"],
            "ground_density": round(prov["ground_points"] / area, 2), "coverage": round(cover, 4),
            "elev_m": [round(float(zf.min()), 1), round(float(zf.max()), 1)], **meta}
    web.write_json(info, out / "site.json")
    click.echo(f"  done in {time.time() - t0:.0f} s -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
