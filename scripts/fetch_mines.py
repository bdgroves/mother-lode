"""Mines of Tuolumne County from USGS mrdata, saved as GeoJSON.

    usmin  every mine and prospect symbol from the old USGS topo maps
           (shafts, adits, prospect pits, tailings, open pits, placer
           diggings...), via the USMIN web feature service; the state KMZ
           is the fallback.
    mrds   the Mineral Resources Data System: named mines and prospects
           with commodities, development status and a little history.

Both are clipped to the county outline (data/tuolumne.geojson). Writes
data/mines/{usmin,mrds}.geojson and a summary to data/mines/summary.json.
"""
from __future__ import annotations

import collections, io, json, re, sys, zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from shapely.geometry import shape, Point, mapping

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "mines"
COUNTY = shape(json.loads((ROOT / "data" / "tuolumne.geojson").read_text())["geometry"])
W, S, E, N = COUNTY.bounds
UA = {"User-Agent": "mother-lode (github.com/bdgroves/mother-lode)"}
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LOG.append(s)


def feature_types(svc):
    r = requests.get(f"https://mrdata.usgs.gov/services/wfs/{svc}",
                     params={"service": "WFS", "request": "GetCapabilities", "version": "1.1.0"}, headers=UA, timeout=120)
    names = re.findall(r"<(?:wfs:)?Name>([^<]+)</(?:wfs:)?Name>", r.text)
    fmts = sorted(set(re.findall(r"<ows:Value>([^<]*(?:json|JSON|gml|GML)[^<]*)</ows:Value>", r.text)))
    log(f"{svc}: feature types {names}; formats {fmts[:12]}")
    return names, fmts


def wfs_geojson(svc, typename):
    """GetFeature in the county box. Try the GeoJSON output formats MapServer offers."""
    base = f"https://mrdata.usgs.gov/services/wfs/{svc}"
    for fmt in ("geojson", "application/json", "json"):
        p = {"service": "WFS", "version": "1.1.0", "request": "GetFeature", "typeName": typename,
             "srsName": "EPSG:4326", "bbox": f"{S},{W},{N},{E},EPSG:4326", "outputFormat": fmt}
        try:
            r = requests.get(base, params=p, headers=UA, timeout=300)
            js = r.json()
            if js.get("features") is not None:
                log(f"  {svc}/{typename} as {fmt}: {len(js['features'])} features in the box")
                return js["features"]
        except Exception as e:  # noqa: BLE001
            log(f"  {svc}/{typename} as {fmt}: {r.status_code if 'r' in dir() else '?'} {e.__class__.__name__}")
    # last resort: GML, parsed by hand (points only)
    p = {"service": "WFS", "version": "1.1.0", "request": "GetFeature", "typeName": typename,
         "srsName": "EPSG:4326", "bbox": f"{S},{W},{N},{E},EPSG:4326"}
    r = requests.get(base, params=p, headers=UA, timeout=300)
    (OUT / f"_{svc}_{typename}_raw.gml").write_text(r.text[:1_000_000])
    feats = []
    root = ET.fromstring(r.content)

    def lonlat(a, b):  # GML 3 with EPSG:4326 gives lat lon; be tolerant
        return (b, a) if abs(a) < 90 and abs(b) > 90 else (a, b)

    def ring(text):
        v = [float(x) for x in text.replace(",", " ").split()]
        return [lonlat(v[i], v[i + 1]) for i in range(0, len(v) - 1, 2)]

    for m in root.iter():
        if not m.tag.split("}")[-1] in ("featureMember", "member"):
            continue
        for f in m:
            props, xy, rings = {}, None, []
            for el in f.iter():
                tag = el.tag.split("}")[-1]
                if tag == "pos" and el.text:
                    a, b = map(float, el.text.split()[:2])
                    xy = lonlat(a, b)
                elif tag in ("posList", "coordinates") and el.text:
                    rings.append(ring(el.text))
                elif len(el) == 0 and el.text and el.text.strip() and tag not in ("lowerCorner", "upperCorner"):
                    props[tag] = el.text.strip()
            if rings and len(rings[0]) >= 4:
                geom = {"type": "Polygon", "coordinates": [[list(p) for p in rings[0]]] + [[list(p) for p in r_] for r_ in rings[1:] if len(r_) >= 4]}
            elif xy:
                geom = {"type": "Point", "coordinates": list(xy)}
            else:
                continue
            feats.append({"type": "Feature", "geometry": geom, "properties": props})
    kinds = collections.Counter(f["geometry"]["type"] for f in feats)
    log(f"  {svc}/{typename} as GML: {dict(kinds)} ({len(r.content):,} bytes)")
    return feats


def kmz_usmin():
    r = requests.get("https://mrdata.usgs.gov/usmin/kml/usmin-CA.kmz", headers=UA, timeout=600)
    z = zipfile.ZipFile(io.BytesIO(r.content))
    kml = z.read([n for n in z.namelist() if n.endswith(".kml")][0])
    ns = {"k": "http://www.opengis.net/kml/2.2"}
    feats = []
    for pm in ET.fromstring(kml).iter("{http://www.opengis.net/kml/2.2}Placemark"):
        c = pm.find(".//k:Point/k:coordinates", ns)
        if c is None:
            continue
        lon, lat = map(float, c.text.strip().split(",")[:2])
        if not (W <= lon <= E and S <= lat <= N):
            continue
        props = {"name": (pm.findtext("k:name", "", ns) or "").strip()}
        for d in pm.iter("{http://www.opengis.net/kml/2.2}Data"):
            props[d.get("name")] = (d.findtext("k:value", "", ns) or "").strip()
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": props})
    log(f"  usmin KMZ (CA): {len(feats)} point features in the box")
    return feats


def clip(feats):
    out = []
    for f in feats:
        g = shape(f["geometry"])
        if g.intersects(COUNTY):
            out.append(f)
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {}
    for svc in ("usmin", "mrds"):
        try:
            names, _ = feature_types(svc)
        except Exception as e:  # noqa: BLE001
            log(f"{svc}: capabilities failed {e}")
            names = []
        feats = []
        for tn in names:
            try:
                got = wfs_geojson(svc, tn)
            except Exception as e:  # noqa: BLE001
                log(f"  {svc}/{tn}: failed {e.__class__.__name__}: {e}")
                continue
            for f in got:
                f.setdefault("properties", {})["_layer"] = tn
            feats += got
        if svc == "usmin" and not feats:
            feats = kmz_usmin()
        feats = clip(feats)
        (OUT / f"{svc}.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
        keys = sorted({k for f in feats for k in f["properties"]})
        summary[svc] = {"features": len(feats), "fields": keys,
                        "sample": [f["properties"] for f in feats[:3]]}
        log(f"{svc}: {len(feats)} features inside Tuolumne County")
    summary["log"] = LOG
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))


if __name__ == "__main__":
    sys.exit(main())
