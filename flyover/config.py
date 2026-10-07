"""Settings for a mother-lode flyover, read from the place's prepared data.

The data comes from the `flyover-data` branch (built on GitHub Actions by
flyover/prep.py): flyover/data/<place>/dtm.tif, relief.png, photo.png and
place.json. Set FLY_PLACE to pick a place (default columbia) and
FLY_TEXTURE=photo to drape the plain aerial photo instead of the shaded one.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLACE = os.environ.get("FLY_PLACE", "columbia")
DATA = ROOT / "data" / PLACE
OUT = ROOT / "out" / PLACE

_info_path = DATA / "place.json"
INFO = json.loads(_info_path.read_text()) if _info_path.exists() else {
    "name": "Columbia", "crs": "EPSG:26910", "res_m": 1.0, "elev_m": [620.0, 780.0],
    "bounds": [726584.0, 4211775.0, 729584.0, 4214175.0], "naip_year": None, "lidar": "USGS 3DEP"}

CRS = INFO["crs"]
DEM_RES = float(INFO["res_m"])
LEFT, BOTTOM, RIGHT, TOP = INFO["bounds"]
EXAGGERATION = 1.0                      # true scale: the pinnacles and pits are real height
DEM_X = DATA / "dtm.tif"
TEXTURE = DATA / ("photo.png" if os.environ.get("FLY_TEXTURE") == "photo" else "relief.png")
VIDEO = OUT / f"{PLACE}_flyover.mp4"

# Late afternoon on the anniversary of the strike: March 27, 2026, 5:30 pm PDT.
# A low sun from the west rakes across the pits and pinnacles.
SUN_UTC = (2026, 3, 28, 0, 30, 0)
SUN_LATLON = (38.036, -120.401)


def image_tiles():
    """One texture over the whole window: (path, left, top, right, bottom)."""
    return [(TEXTURE, LEFT, TOP, RIGHT, BOTTOM)]


def graded(path: Path) -> Path:
    return path
