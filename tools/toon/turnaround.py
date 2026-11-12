"""Model sheet: one character at six yaw angles + the cast with expressions (consistency check)."""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rig  # noqa: E402
from toon import Camera, Frame  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "turnaround.png"
tiles = []
cam = Camera((0, 1.0, 0.0), 0, f=2300, horizon=0.5)
for yaw in (0, 35, 70, 100, 150, -60):
    fr = Frame(0.35, bg="#1b2236")
    rig.draw(fr, cam, "jeff", dict(x=0, z=4.2, yaw=yaw, aR=(10, 8, 30), aL=(-6, 6, 12)), light=(0.5, 2.6, 3.6))
    tiles.append(Image.fromarray(fr.array()))
EXPR = {"liu": dict(lid=1.0, brow=0.8, brow_in=-0.6, mouth=0.35, gx=0.3),
        "randy": dict(lid=0.75, brow_in=0.9, smile=0.6, lid_lo=0.25),
        "bully": dict(brow_in=0.5, smile=0.4, lid=0.8),
        "bully2": dict(brow=-0.2, smile=0.8, mouth=0.4),
        "jeff": dict(lid=0.85, brow_in=1.0, smile=-0.5, gy=0.1)}
for look, ex in EXPR.items():
    fr = Frame(0.35, bg="#1b2236")
    rig.draw(fr, cam, look, dict(x=0, z=4.2, yaw=25, **ex), light=(0.5, 2.6, 3.6))
    tiles.append(Image.fromarray(fr.array()))
w, h = tiles[0].size
sheet = Image.new("RGB", (w * 6, h * 2), (255, 0, 255))
for i, t in enumerate(tiles):
    sheet.paste(t, ((i % 6) * w, (i // 6) * h))
sheet.save(OUT)
print(OUT, sheet.size)
