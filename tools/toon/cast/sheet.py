"""Model sheet for any kit look: six yaws standing, a seated/crouched pose, and a face close-up.
python -m cast.sheet <module> <look> [out.png]     (run from tools/toon; e.g. python -m cast.sheet mara mara)
<module> is a cast module that registers looks in rig.LOOK (mara, powerup), or the path of an episode's looks.py.
Default output: assets/kit/cast/<look>.png at the repo root."""
import importlib
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import rig  # noqa: E402
from toon import Camera, Frame  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))


def sheet(look, out, extra_pose=None):
    L = rig.LOOK[look]
    hgt = L["h"]
    ep = extra_pose or {}
    tiles = []
    cam = Camera((0, hgt * 0.55, 0.0), 0, f=2300 * 1.7 / max(hgt, 1.0), horizon=0.5)
    for yaw in (0, 35, 70, 110, 160, -60):
        fr = Frame(0.35, bg="#1b2236")
        rig.draw(fr, cam, look, dict(x=0, z=4.2, yaw=yaw, aR=(10, 8, 30), aL=(-6, 6, 12), t=1.0, **ep), light=(0.5, 2.6, 3.6))
        tiles.append(Image.fromarray(fr.array()))
    # crouched / kneeling (the robe and hands from above)
    fr = Frame(0.35, bg="#1b2236")
    rig.draw(fr, Camera((0, hgt * 0.6, 1.0), 0, f=1900, horizon=0.4), look,
             dict(x=0, z=4.2, yaw=25, crouch=0.5, lean=25, aR=(55, 10, 40), aL=(50, 10, 40), curl_R=0.8, t=2.0, breeze=1.0, **ep),
             light=(0.5, 2.6, 3.6))
    tiles.append(Image.fromarray(fr.array()))
    # face close-ups: front and three-quarter, hands up near the face
    for yaw in (0, 30):
        fr = Frame(0.35, bg="#1b2236")
        rig.draw(fr, Camera((0, hgt * 0.9, 2.9), 0, f=3400, horizon=0.5), look,
                 dict(x=0, z=4.2, yaw=yaw, aR=(45, 25, 70), aL=(10, 8, 20), curl_R=0.6, t=3.0, breeze=0.6, **ep),
                 light=(0.5, 2.6, 3.6))
        tiles.append(Image.fromarray(fr.array()))
    w, h = tiles[0].size
    cols = 9
    img = Image.new("RGB", (w * cols + 8 * (cols - 1), h), (255, 0, 255))
    for i, t in enumerate(tiles):
        img.paste(t, (i * (w + 8), 0))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    img.save(out)
    print(out, img.size)


if __name__ == "__main__":
    mod, look = sys.argv[1], sys.argv[2]
    if mod.endswith(".py"):                                   # an episode's own looks file (give its path)
        sys.path.insert(0, os.path.dirname(os.path.abspath(mod)))
        importlib.import_module(os.path.splitext(os.path.basename(mod))[0])
    else:
        importlib.import_module("cast." + mod)
    if look not in rig.LOOK:
        sys.exit(f"{look!r} is not in rig.LOOK after importing {mod}. Registered looks: {', '.join(sorted(rig.LOOK))}. "
                 "(cast.creature and cast.widemouth draw themselves: run `python -m cast.creature` / `python -m cast.widemouth`.)")
    sheet(look, sys.argv[3] if len(sys.argv) > 3 else os.path.join(ROOT, "assets", "kit", "cast", look + ".png"))
