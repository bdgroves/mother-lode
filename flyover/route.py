"""What gets named on screen in the Columbia flyover (the renderer calls these TOWNS).

  name: (lat, lon, label)

Sources: Columbia State Historic Park's coordinates are the place centre in
places.yaml (Wikipedia). The diggings label sits on the rough ground south and
east of the old town that the place's story describes. The old quarry is the
biggest water-filled hole in the lidar (no returns from water), found by
prep.py. Columbia Airport is placed on its runway.
"""
from __future__ import annotations

import config

TOWNS = {
    "park": (38.0358, -120.4011, "Columbia State Historic Park"),
    "diggings": (38.0335, -120.3937, "The diggings"),
    "airport": (38.0304, -120.4147, "Columbia Airport"),
}
if config.INFO.get("water"):
    _w = config.INFO["water"][0]
    TOWNS["quarry"] = (_w["lat"], _w["lon"], "Old quarry")

LEGS = []
ROUTE_RGB = (242, 179, 94)
LOOP_RGB = (253, 250, 244)
HALO_RGB = (28, 26, 22)
