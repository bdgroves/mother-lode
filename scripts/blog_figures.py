"""Annotated figures for the blog: the relief composite with the mines on top.

    python scripts/blog_figures.py OUT_DIR

For each place writes OUT_DIR/<id>-full.jpg (2400 px wide, for zooming in) and
OUT_DIR/<id>.jpg (1200 px, inline in the post). Markers:

    blue ring     mine shaft          (USGS topo maps, USMIN)
    red ring      adit / tunnel       (USMIN)
    gold ring     prospect pit        (USMIN)
    brown outline tailings or dump    (USMIN)
    green diamond named mine, labelled (USGS MRDS, producers and past producers)
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pyproj import Transformer

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "figures")
OUT.mkdir(parents=True, exist_ok=True)
PAPER = (245, 240, 232)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
COL = {"Mine Shaft": (29, 78, 216), "Adit": (194, 65, 12), "Prospect Pit": (202, 138, 4)}
OTHER, TAIL, NAMED = (100, 100, 110), (154, 52, 18), (4, 120, 87)

# extra landmarks per place (checked coordinates only)
EXTRA = {
    "big-oak-flat": [{"lonlat": (-120.26065, 37.82268), "label": "Big Oak Flat marker (CHL 406)", "star": True}],
}
POINTERS = {  # off-map places: an arrow on the edge pointing toward them
    "big-oak-flat": [{"lonlat": (-120.2324, 37.8385), "label": "Groveland, 2 mi"}],
}

T = Transformer.from_crs(4326, 3857, always_xy=True)
mines = json.loads((ROOT / "docs/data/mines.geojson").read_text())["features"]


def font(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT, size)


def render(pid):
    d = json.loads((ROOT / f"docs/sites/{pid}/site.json").read_text())
    (s, w), (n, e) = d["bounds"]
    im = Image.open(ROOT / f"docs/sites/{pid}/composite.webp").convert("RGBA")
    bg = Image.new("RGBA", im.size, PAPER + (255,))
    bg.alpha_composite(im)
    im = bg.convert("RGB")
    W, H = im.size
    # the reprojected image has slanted empty edges; find the box we'll keep
    a = np.asarray(im)
    m = (np.abs(a.astype(int) - np.array(PAPER)).sum(2) > 12)
    ys, xs = np.where(m)
    x0c, x1c, y0c, y1c = xs.min(), xs.max(), ys.min(), ys.max()
    dx, dy = int((x1c - x0c) * .035), int((y1c - y0c) * .035)
    CL, CT, CR, CB = x0c + dx, y0c + dy, x1c - dx, y1c - dy
    X0, Y0 = T.transform(w, s)
    X1, Y1 = T.transform(e, n)

    def px(lon, lat):
        X, Y = T.transform(lon, lat)
        return (X - X0) / (X1 - X0) * W, (Y1 - Y) / (Y1 - Y0) * H

    dr = ImageDraw.Draw(im, "RGBA")
    k = W / 2400                      # scale symbols with the image
    r = 11 * k
    inside = lambda x, y: CL <= x < CR and CT <= y < CB

    # tailings / dump outlines
    for f in mines:
        g, p = f["geometry"], f["properties"]
        if p["src"] == "usmin" and g["type"] == "Polygon":
            pts = [px(*c) for c in g["coordinates"][0]]
            if any(inside(*q) for q in pts):
                dr.polygon(pts, fill=TAIL + (60,), outline=TAIL + (255,))
                dr.line(pts + [pts[0]], fill=TAIL + (255,), width=max(2, int(4 * k)))
    # USMIN points
    for f in mines:
        g, p = f["geometry"], f["properties"]
        if p["src"] == "usmin" and g["type"] == "Point":
            x, y = px(*g["coordinates"])
            if inside(x, y):
                c = COL.get(p["kind"], OTHER)
                dr.ellipse([x - r, y - r, x + r, y + r], outline=(255, 255, 255, 220), width=max(2, int(7 * k)))
                dr.ellipse([x - r, y - r, x + r, y + r], outline=c + (255,), width=max(2, int(4 * k)))
    # named mines: one per name, producers first
    named = {}
    for f in mines:
        g, p = f["geometry"], f["properties"]
        if p["src"] != "mrds" or not p.get("gold"):
            continue
        x, y = px(*g["coordinates"])
        if not inside(x, y):
            continue
        nm = p["name"].strip()
        if "district" in nm.lower() or nm.lower() == "group":
            continue
        rank = {"Producer": 0, "Past Producer": 0}.get(p["status"], 1)
        key = "".join(ch for ch in nm.lower().replace(" mine", "") if ch.isalnum())
        if key not in named or rank < named[key][0]:
            named[key] = (rank, nm, x, y)
    taken = []
    fl = font(int(30 * k), bold=True)

    def place_label(x, y, text, color):
        tw, th = dr.textbbox((0, 0), text, font=fl)[2:]
        g = 20 * k
        for dx, dy in ((g, -th / 2), (-tw - g, -th / 2), (-tw / 2, -th - g), (-tw / 2, g), (g, g / 2), (g, -th - g / 2)):
            bx = (x + dx, y + dy)
            box = (bx[0] - 6, bx[1] - 4, bx[0] + tw + 6, bx[1] + th + 6)
            if box[0] < CL + 4 or box[1] < CT + 4 or box[2] > CR - 4 or box[3] > CB - 4:
                continue
            if any(not (box[2] < b[0] or box[0] > b[2] or box[3] < b[1] or box[1] > b[3]) for b in taken):
                continue
            taken.append(box)
            dr.rounded_rectangle(box, radius=6 * k, fill=(255, 255, 255, 215))
            dr.text(bx, text, font=fl, fill=color)
            return True
        return False

    for rank, nm, x, y in sorted(named.values()):
        q = 13 * k
        dr.polygon([(x, y - q), (x + q, y), (x, y + q), (x - q, y)], fill=NAMED + (255,), outline=(255, 255, 255))
    for rank, nm, x, y in sorted(named.values()):
        if rank == 0:
            place_label(x, y, nm, NAMED)
    for ex in EXTRA.get(pid, []):
        x, y = px(*ex["lonlat"])
        q = 26 * k
        star = [(x + q * (1 if i % 2 == 0 else .45) * math.sin(i * math.pi / 5), y - q * (1 if i % 2 == 0 else .45) * math.cos(i * math.pi / 5)) for i in range(10)]
        dr.polygon(star, fill=(220, 38, 38), outline=(255, 255, 255))
        place_label(x + 10 * k, y, ex["label"], (153, 27, 27))
    for po in POINTERS.get(pid, []):
        tx, ty = px(*po["lonlat"])
        cx, cy = (CL + CR) / 2, (CT + CB) / 2
        ang = math.atan2(ty - cy, tx - cx)
        # where the ray from the centre leaves the kept frame, pulled in a margin
        tmax = min(((CR - CL) / 2 - 50 * k) / abs(math.cos(ang) or 1e-9), ((CB - CT) / 2 - 50 * k) / abs(math.sin(ang) or 1e-9))
        ax, ay = cx + tmax * math.cos(ang), cy + tmax * math.sin(ang)
        L = 70 * k
        bx, by = ax - L * math.cos(ang), ay - L * math.sin(ang)
        dr.line([(bx, by), (ax, ay)], fill=(30, 30, 30), width=int(8 * k))
        hw = 20 * k
        dr.polygon([(ax + 10 * k * math.cos(ang), ay + 10 * k * math.sin(ang)),
                    (ax - hw * math.cos(ang - .5), ay - hw * math.sin(ang - .5)),
                    (ax - hw * math.cos(ang + .5), ay - hw * math.sin(ang + .5))], fill=(30, 30, 30))
        lab = po["label"] + " →"
        tw, th = dr.textbbox((0, 0), lab, font=fl)[2:]
        lx = min(max(bx - tw - 16 * k, CL + 10), CR - tw - 10)
        ly = min(max(by - th / 2 + 30 * k, CT + 10), CB - th - 10)
        dr.rounded_rectangle((lx - 6, ly - 4, lx + tw + 6, ly + th + 6), radius=6 * k, fill=(255, 255, 255, 225))
        dr.text((lx, ly), lab, font=fl, fill=(30, 30, 30))

    # legend, scale bar, north arrow
    fs = font(int(26 * k))
    items = [("ring", COL["Mine Shaft"], "Shaft"), ("ring", COL["Adit"], "Adit (tunnel)"),
             ("ring", COL["Prospect Pit"], "Prospect pit"), ("box", TAIL, "Tailings or dump"),
             ("dia", NAMED, "Named mine (USGS MRDS)")]
    lh = 40 * k
    lw = 430 * k
    m_per_px0 = (X1 - X0) / W * math.cos(math.radians((s + n) / 2))
    lw = max(lw, 500 / m_per_px0 + 170 * k)
    x0, y0 = CL + 24 * k, CB - (len(items) * lh + 110 * k)
    dr.rounded_rectangle((x0, y0, x0 + lw, CB - 24 * k), radius=10 * k, fill=(255, 255, 255, 225))
    yy = y0 + 18 * k
    for kind, c, lab in items:
        cx, cy = x0 + 30 * k, yy + lh / 2 - 6 * k
        if kind == "ring":
            dr.ellipse([cx - r, cy - r, cx + r, cy + r], outline=c, width=max(2, int(4 * k)))
        elif kind == "box":
            dr.rectangle([cx - r, cy - r, cx + r, cy + r], fill=c + (90,), outline=c, width=max(2, int(3 * k)))
        else:
            q = 13 * k
            dr.polygon([(cx, cy - q), (cx + q, cy), (cx, cy + q), (cx - q, cy)], fill=c)
        dr.text((cx + 30 * k, cy - 15 * k), lab, font=fs, fill=(35, 30, 25))
        yy += lh
    # scale bar: 500 m
    lat_c = (s + n) / 2
    m_per_px = (X1 - X0) / W * math.cos(math.radians(lat_c))
    bar = 500 / m_per_px
    bx0, by0 = x0 + 30 * k, CB - 56 * k
    dr.rectangle([bx0, by0, bx0 + bar, by0 + 10 * k], fill=(35, 30, 25))
    dr.rectangle([bx0 + bar / 2, by0, bx0 + bar, by0 + 10 * k], fill=(255, 255, 255), outline=(35, 30, 25))
    dr.text((bx0 + bar + 12 * k, by0 - 12 * k), "500 m", font=fs, fill=(35, 30, 25))
    # north arrow
    nx, ny = CR - 60 * k, CT + 70 * k
    dr.polygon([(nx, ny - 40 * k), (nx + 18 * k, ny + 14 * k), (nx, ny + 2 * k), (nx - 18 * k, ny + 14 * k)], fill=(35, 30, 25))
    dr.text((nx - 11 * k, ny + 18 * k), "N", font=font(int(30 * k), True), fill=(35, 30, 25))

    im = im.crop((CL, CT, CR, CB))
    full = im.resize((2400, int(im.height * 2400 / im.width)), Image.LANCZOS)
    full.save(OUT / f"{pid}-full.jpg", quality=84, optimize=True, progressive=True)
    small = im.resize((1200, int(im.height * 1200 / im.width)), Image.LANCZOS)
    small.save(OUT / f"{pid}.jpg", quality=80, optimize=True, progressive=True)
    print(pid, full.size, f"{len([v for v in named.values() if v[0] == 0])} producers labelled")


for pid in ("big-oak-flat", "columbia", "harvard-pit", "eagle-shawmut", "rawhide"):
    render(pid)
