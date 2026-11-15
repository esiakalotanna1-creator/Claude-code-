import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "tools", "toon"))
sys.path.insert(0, HERE)
import rig, looks  # noqa
from toon import Camera, Frame
from PIL import Image
tiles = []
for nm in ("kai", "remi", "mom", "gma"):
    for yaw in (0, 35, 180, 150):
        cam = Camera((0, 0.95, 0.0), 0, f=2300 * 1.0, horizon=0.5)
        fr = Frame(0.3, bg="#2a3046")
        rig.draw(fr, cam, nm, dict(rig.REST, x=0, z=4.6, yaw=yaw, aR=(10, 8, 30), aL=(-6, 6, 12), t=1.0), light=(0.5, 2.6, 3.6))
        tiles.append(Image.fromarray(fr.array()))
w, h = tiles[0].size
s = Image.new("RGB", (w * 8, h * 2))
for i, im in enumerate(tiles):
    s.paste(im, ((i % 8) * w, (i // 8) * h))
s.save(os.path.join(HERE, "review_cast.png")); print(s.size)
