"""Character reference sheets for this episode's cast (the gate before animating).
python turn_sheet.py -> review/turn_window.png: for each of the cast, front / three-quarter / side head-and-shoulders,
then the expressions the reel uses (stranger: smile with gaze left, right, up; father: calm, worried, lips parted,
eyes wide; wife: asleep)."""
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kit  # noqa: E402,F401
import rig  # noqa: E402
import looks  # noqa: E402,F401
from toon import Camera, Frame  # noqa: E402

TURNS = [(0, "front"), (35, "3/4"), (90, "side")]
EXPR = {
    "stranger": [("smile", {}), ("gaze L", dict(gx=-0.6)), ("gaze R", dict(gx=0.6)), ("gaze up", dict(gy=0.4)), ("press", dict(press=1.0))],
    "dad": [("calm", dict(brow=0.1)), ("worried", dict(brow=0.75, brow_in=-0.55, lid=1.0)), ("lips part", dict(brow=0.75, brow_in=-0.55, mouth=0.3, mouth_w=-0.2)),
            ("eyes wide", dict(brow=0.9, brow_in=-0.3, lid=1.0, lid_lo=0.0))],
    "wife": [("asleep", dict(lid=0.0, brow=0.1, mouth=0.02)), ("calm", dict(brow=0.1))],
}


def tile(look, yaw, extra, label):
    h = rig.LOOK[look]["h"]
    fr = Frame(0.5, bg="#1b2236")
    cam = Camera((0, h * 0.90, 1.6), 0, f=2600, horizon=0.50)
    p = dict(x=0, z=3.0, yaw=yaw)
    if look == "stranger":
        p["nomouth"] = True
    p.update(extra)
    rig.draw(fr, cam, look, p, light=(0.5, 2.8, 3.0))
    im = Image.fromarray(fr.array()).crop((70, 105, 470, 705))
    ImageDraw.Draw(im).text((8, 8), f"{look} {label}", fill="yellow")
    return im


rows = []
for look in ("stranger", "dad", "wife"):
    rows.append([tile(look, y, {}, l) for y, l in TURNS] + [tile(look, 0, e, l) for l, e in EXPR[look]])
w, hh = rows[0][0].size
n = max(len(r) for r in rows)
sheet = Image.new("RGB", (n * (w + 6), len(rows) * (hh + 6)), (255, 0, 255))
for j, r in enumerate(rows):
    for i, t in enumerate(r):
        sheet.paste(t, (i * (w + 6), j * (hh + 6)))
os.makedirs(os.path.join(HERE, "review"), exist_ok=True)
sheet.save(os.path.join(HERE, "review", "turn_window.png"))
print("review/turn_window.png", sheet.size)


def lineup():
    """Full bodies side by side (stranger, father, wife) for silhouette and height: review/lineup_window.png."""
    fr = Frame(1.0, bg="#1b2236")
    cam = Camera((0, 1.0, 1.6), 0, f=2300, horizon=0.50)
    for look, x, yaw in (("stranger", -0.66, 15), ("dad", 0.08, -10), ("wife", 0.72, -20)):
        rig.draw(fr, cam, look, dict(x=x, z=6.0, yaw=yaw), light=(0.5, 2.8, 3.0))
    Image.fromarray(fr.array()).save(os.path.join(HERE, "review", "lineup_window.png"))
    print("review/lineup_window.png")


lineup()
