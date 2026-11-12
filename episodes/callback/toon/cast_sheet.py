"""Model sheets for the cast: six turnaround views and an expression row per character.

    python cast_sheet.py [look ...] [--out DIR]     -> review/cast_<look>.png
"""
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "tools", "toon"))
import rig  # noqa: E402
import looks  # noqa: E402,F401
from toon import Camera, Frame  # noqa: E402

EXPR = [
    ("neutral", dict()),
    ("smile", dict(smile=0.6, lid=0.9)),
    ("laugh", dict(smile=0.9, mouth=0.45, lid=0.55, brow=0.25)),
    ("sad", dict(brow=-0.65, lid=0.72, smile=-0.35, gy=-0.4)),
    ("crying", dict(brow=-0.9, lid=0.5, mouth=0.18, smile=-0.5, gy=-0.2)),
    ("shocked", dict(brow=0.5, lid=1.0, mouth=0.35, iris_k=1)),
    ("talking", dict(mouth=0.22, smile=0.15)),
    ("eyes shut", dict(lid=0.0, smile=0.2)),
]


def label(im, text):
    d = ImageDraw.Draw(im)
    d.rectangle((0, im.height - 22, im.width, im.height), fill=(0, 0, 0))
    d.text((6, im.height - 18), text, fill=(255, 220, 120))
    return im


def sheet(look, out):
    L = rig.LOOK[look]
    hgt = L["h"]
    light = (0.6, 2.6, 3.4)
    tiles = []
    cam = Camera((0, hgt * 0.55, 0.0), 0, f=2300 * 1.7 / max(hgt, 1.0), horizon=0.5)
    for yaw in (0, 30, 65, 100, 150, 180, -40):
        fr = Frame(0.32, bg="#26304a")
        rig.draw(fr, cam, look, dict(rig.REST, x=0, z=4.2, yaw=yaw, aR=(10, 8, 30), aL=(-6, 6, 12), t=1.0), light=light)
        tiles.append(label(Image.fromarray(fr.array()), f"{look} yaw {yaw}"))
    w, h = tiles[0].size
    faces = []
    fcam = Camera((0, hgt * 0.90, 2.6), 0, f=2600, horizon=0.5)
    for name, ex in EXPR:
        ex = {k: v for k, v in ex.items() if k != "iris_k"}
        fr = Frame(0.32, bg="#26304a")
        rig.draw(fr, fcam, look, dict(rig.REST, x=0, z=4.2, yaw=18, t=1.0, **ex), light=light)
        im = Image.fromarray(fr.array())
        faces.append(label(im.crop((0, int(h * 0.22), w, int(h * 0.22) + int(w * 0.95))), name))
    fw, fh = faces[0].size
    W = max(len(tiles) * w, 4 * fw)
    rows_f = (len(faces) + 3) // 4
    im = Image.new("RGB", (W, h + rows_f * fh), (16, 18, 26))
    for i, t in enumerate(tiles):
        im.paste(t, (i * w, 0))
    for i, f in enumerate(faces):
        im.paste(f, ((i % 4) * fw, h + (i // 4) * fh))
    im.save(out)
    print(out)


if __name__ == "__main__":
    a = sys.argv[1:]
    outdir = a[a.index("--out") + 1] if "--out" in a else os.path.join(HERE, "review")
    os.makedirs(outdir, exist_ok=True)
    names = [x for x in a if not x.startswith("--") and x != outdir] or ["maya", "theo", "frank"]
    for n in names:
        sheet(n, os.path.join(outdir, f"cast_{n}.png"))
