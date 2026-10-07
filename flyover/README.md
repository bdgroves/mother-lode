# Columbia flyover

A forge3d fly-through of the diggings at Columbia: the bare-earth lidar of the limestone pits and pinnacles the hydraulic miners left, at true scale, with the USDA NAIP aerial photo draped on it and shaded by the relief so the pits read. It flies in from the south-west, low over the rock gardens and the old quarry, and back over the diggings to the town.

## How it's split

- **The data is built on GitHub Actions** (`.github/workflows/flyover-data.yml`). It needs PDAL for the lidar, which Brooks's laptop can't run (Smart App Control blocks it). The workflow builds the place the same way as the map, adds the NAIP photo with `flyover/prep.py`, and publishes `dtm.tif`, `photo.png`, `relief.png` and `place.json` to the `flyover-data` branch under `columbia/`. It runs on every push to `flyover/prep.py`, or by hand from the Actions tab for another place.
- **The render runs locally on the GPU** with `f3d`, the PowerShell function that borrows the trusted humphreys-orbit environment (forge3d 1.39). It needs no PDAL, no yaml and no pixi.

## Render it (PowerShell)

```powershell
cd C:\Users\brook\Projects\mother-lode
git pull
git fetch origin flyover-data
git archive -o fly.tar origin/flyover-data
mkdir flyover\data -Force; tar -xf fly.tar -C flyover\data; Remove-Item fly.tar

f3d flyover\render.py --stills "3,15,30,45" --size 960x540 --lite   # check the look
f3d flyover\render.py --preview                                     # quick 640x360 version
f3d flyover\render.py                                               # the full flight, 1920x1080
```

Quote the `--stills` list: through `f3d`, PowerShell would otherwise split `3,15,30,45` into separate values. The film lands in `flyover\out\columbia\columbia_flyover.mp4`.

- `f3d flyover\flight.py` draws the flight on a map (`flyover\out\columbia\flight_map.png`) and prints the camera's height above the ground along the way.
- Set `$env:FLY_TEXTURE = "photo"` to drape the plain aerial photo instead of the shaded one.
- To change the flight, edit `KEYS` in `flyover/flight.py`. To change the names on screen, edit `flyover/route.py`.

## Another place

Run **Flyover data** from the Actions tab with a place id from `places.yaml` (for example `harvard-pit`), unpack the branch as above, and render with `$env:FLY_PLACE = "harvard-pit"`. That place still needs its own `KEYS` and labels.
