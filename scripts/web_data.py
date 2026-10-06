"""Slim the mine layers for the web page and index the built places.

    data/mines/{usmin,mrds}.geojson  ->  docs/data/mines.geojson
    places.yaml + docs/sites/*/site.json  ->  docs/data/places.json
"""
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "data"
OUT.mkdir(parents=True, exist_ok=True)

COMMODITY = {"AU": "gold", "AG": "silver", "CU": "copper", "PB": "lead", "ZN": "zinc", "W": "tungsten",
             "CR": "chromium", "FE": "iron", "MN": "manganese", "MG": "magnesium", "BI": "bismuth",
             "ASB": "asbestos", "MBL": "marble", "LST_D": "limestone", "STN_C": "crushed stone",
             "SDG": "sand and gravel", "TLC": "talc", "SB": "antimony", "HG": "mercury", "MO": "molybdenum"}


def r5(c):
    return [round(c[0], 5), round(c[1], 5)]


feats = []
for f in json.loads((ROOT / "data/mines/usmin.geojson").read_text())["features"]:
    p, g = f["properties"], f["geometry"]
    geom = ({"type": "Point", "coordinates": r5(g["coordinates"])} if g["type"] == "Point" else
            {"type": "Polygon", "coordinates": [[r5(c) for c in ring] for ring in g["coordinates"]]})
    feats.append({"type": "Feature", "geometry": geom, "properties": {
        "src": "usmin", "kind": p.get("ftr_type", ""), "name": p.get("ftr_name", ""),
        "topo": f"{p.get('topo_name', '')} {p.get('topo_date', '')}".strip(), "url": p.get("url", "")}})
for f in json.loads((ROOT / "data/mines/mrds.geojson").read_text())["features"]:
    p = f["properties"]
    codes = (p.get("code_list") or "").split()
    feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": r5(f["geometry"]["coordinates"])},
                  "properties": {"src": "mrds", "name": p.get("site_name", ""), "status": p.get("dev_stat", ""),
                                 "commodities": ", ".join(COMMODITY.get(c, c) for c in codes),
                                 "gold": "AU" in codes, "url": p.get("url", "")}})
(OUT / "mines.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":")))

cat = yaml.safe_load((ROOT / "places.yaml").read_text(encoding="utf-8"))["places"]
places = []
for pid, p in cat.items():
    sj = ROOT / "docs" / "sites" / pid / "site.json"
    if not sj.exists():
        continue
    s = json.loads(sj.read_text())
    places.append({"id": pid, "name": p["name"], "center": p["center"], "bounds": s["bounds"],
                   "layers": s["layers"], "lrm_clip_m": s.get("lrm_clip_m"),
                   "story": p.get("story", []), "sources": p.get("sources", []),
                   "lidar": {"project": s["project"], "coverage": s["coverage"], "res_m": s["res_m"],
                             "ground_points": s["ground_points"], "elev_m": s["elev_m"],
                             "seam_shift_m": s.get("seam_shift_m", {})}})
(OUT / "places.json").write_text(json.dumps(places, indent=1, ensure_ascii=False))
print(f"{len(feats)} mine features, {len(places)} places")
