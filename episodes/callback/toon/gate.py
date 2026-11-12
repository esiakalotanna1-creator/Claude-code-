"""Set frames for the gate: each home with its person in place.  python gate.py -> review/sets.png"""
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sets as S  # noqa: E402
import rig  # noqa: E402
from toon import Camera, Frame  # noqa: E402


def track_cam(pos, tgt, f, hz=0.46):
    import math
    return Camera(pos, math.degrees(math.atan2(tgt[0] - pos[0], tgt[2] - pos[2])), f, hz)


def maya_pose(T=0.0):
    p = S.seated("maya", 0.12, 2.70, 0.0, 0.48, 0.36, lid=0.35, brow=-0.35, head_yaw=-8.0, head_pitch=6.0, head_roll=6.0,
                 lean=4.0, aR=(20.0, 10.0, 70.0), t=T)
    J = rig.solve("maya", p)
    hx, hy, hz = J["head"]
    p["ik_L"] = (hx + 0.165, hy - 0.03, hz + 0.02)   # the phone in her left hand: the side the cameras see
    p["pole_L"] = (0.6, -0.15, -1.0)              # elbow forward and out at chest height: the forearm runs up beside the cheek
    return p


def theo_pose(T=0.0):
    p = S.seated("theo", 0.92, 1.75, 75.0, 0.5, 0.36, head_pitch=22.0, gy=-0.6, lid=0.85, brow=-0.15, lean=10.0, t=T)
    B = rig.Basis.yaw(75.0)
    p["ik_R"] = B.w((0.92, 0, 1.75), 0.06, 0.98, 0.34)
    p["ik_L"] = B.w((0.92, 0, 1.75), -0.06, 0.98, 0.34)
    p["pole_R"], p["pole_L"] = (0.3, -1.0, -1.0), (0.3, -1.0, 1.0)
    return p


def frames():
    flat, room = S.Flat(), S.Room()
    shots = [
        (flat, track_cam((1.25, 1.15, 0.0), (-0.15, 0.95, 2.7), 1250, 0.48), [("maya", "maya", maya_pose(), {"L": rig.phone(on=False)})], 0.0),
        (flat, track_cam((0.85, 1.32, 1.55), rig.solve("maya", maya_pose())["head"], 2300, 0.42), [("maya", "maya", maya_pose(), {"L": rig.phone(on=False)})], 0.0),
        (room, track_cam((-1.3, 1.25, -0.6), (1.1, 0.85, 2.1), 1250, 0.5), [("theo", "theo", theo_pose(), {"R": rig.phone()})], 1.0),
        (room, track_cam((1.9, 1.3, 0.55), rig.solve("theo", theo_pose())["head"], 2000, 0.42), [("theo", "theo", theo_pose(), {"R": rig.phone()})], 1.0),
    ]
    import ui
    tiles = []
    fr = Frame(0.4)
    world, cam, cast, ph = shots[1]
    world.draw(fr, cam, 2.0, cast, phone=0.0)
    ui.call_screen(fr, "Dad", "calling...", 1.0, initial="F")
    ui_tile = Image.fromarray(fr.array())
    for world, cam, cast, ph in shots:
        fr = Frame(0.4)
        world.draw(fr, cam, 2.0, cast, phone=ph)
        tiles.append(Image.fromarray(fr.array()))
    tiles.insert(2, ui_tile)
    w, h = tiles[0].size
    im = Image.new("RGB", (w * len(tiles) + 8 * (len(tiles) - 1), h), (16, 18, 26))
    for i, t in enumerate(tiles):
        im.paste(t, (i * (w + 8), 0))
    out = os.path.join(HERE, "review", "sets.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    im.save(out)
    print(out)


if __name__ == "__main__":
    frames()
