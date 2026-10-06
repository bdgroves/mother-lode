"""Look at each data source once, from a GitHub runner, and save what came back.

The sandbox these scripts are written in can't reach USGS, ScienceBase or
Macrostrat, so the first step is to ask them what they hold and commit the
answers to data/_probe/ before writing the real fetchers against them.
"""
import json, pathlib, requests

OUT = pathlib.Path("data/_probe"); OUT.mkdir(parents=True, exist_ok=True)
# Tuolumne County, CA (lon/lat): from the county outline
BBOX = (-120.653, 37.634, -119.200, 38.434)
UA = {"User-Agent": "mother-lode (github.com/bdgroves/mother-lode)"}

def get(name, url, params=None, n=4000):
    try:
        r = requests.get(url, params=params, headers=UA, timeout=60)
        txt = r.text
        (OUT / f"{name}.txt").write_text(f"{r.status_code} {r.url}\n{r.headers.get('content-type')}\n\n{txt[:n]}")
        print(f"{name}: {r.status_code} {len(txt)} bytes")
        return r
    except Exception as e:
        (OUT / f"{name}.txt").write_text(f"ERR {e}")
        print(f"{name}: ERR {e}")

env = ",".join(map(str, BBOX))
# USMIN: the western-US MapServer from ScienceBase, and the consolidated national item
get("usmin_mapserver", "https://my.usgs.gov/arcgis/rest/services/Catalog/57962314e4b007df0739fede/MapServer", {"f": "json"})
for lyr in (0, 1, 2):
    get(f"usmin_layer{lyr}", f"https://my.usgs.gov/arcgis/rest/services/Catalog/57962314e4b007df0739fede/MapServer/{lyr}", {"f": "json"})
    get(f"usmin_count{lyr}", f"https://my.usgs.gov/arcgis/rest/services/Catalog/57962314e4b007df0739fede/MapServer/{lyr}/query",
        {"f": "json", "where": "1=1", "geometry": env, "geometryType": "esriGeometryEnvelope", "inSR": 4326,
         "spatialRel": "esriSpatialRelIntersects", "returnCountOnly": "true"})
get("sb_usmin_us", "https://www.sciencebase.gov/catalog/item/64dfc0efd34e5f6cd553c265", {"format": "json"}, n=20000)
get("sb_usmin_west", "https://www.sciencebase.gov/catalog/item/57962314e4b007df0739fede", {"format": "json"}, n=20000)
get("mrdata_usmin", "https://mrdata.usgs.gov/usmin/", n=6000)
get("mrds_wfs", "https://mrdata.usgs.gov/services/wfs/mrds", {"service": "WFS", "request": "GetCapabilities"}, n=3000)
# Geology at Columbia and Jamestown
for nm, lat, lon in (("columbia", 38.036, -120.401), ("jamestown", 37.953, -120.422)):
    get(f"macrostrat_{nm}", "https://macrostrat.org/api/v2/geologic_units/map", {"lat": lat, "lng": lon}, n=6000)
# Lidar: the two surveys over the gold belt
for p in ("CA_SierraNevada_12_B22", "CA_CalaverasTuolumne_2011"):
    get(f"ept_{p}", f"https://s3-us-west-2.amazonaws.com/usgs-lidar-public/{p}/ept.json", n=3000)
