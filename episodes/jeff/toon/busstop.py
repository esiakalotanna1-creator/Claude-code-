"""JEFF (toon rework): the bus-stop confrontation sample, 11.32-17.70 s of the episode.

One 3D world (set + five characters on one timeline); each shot only chooses a camera, so positions,
screen direction and lighting carry across the cuts.

  S1  0.00-1.88  establishing: Jeff and Liu under the shelter light; the camera trucks right and reveals
                 the three bullies walking in.
  S2  1.88-3.67  medium on Jeff: eyes shift -> head turns -> shoulders tense -> arm rises to shield Liu.
  S3  3.67-5.48  over Jeff's shoulder onto Randy: last step, stop, settle, chin up; reaches back and
                 pulls a knife (16.13 s).
  S4  5.48-6.38  close-up: Jeff's fear turns to anger on "Jeff" (17.27 s).

    py busstop.py --poses      key-pose sheets per shot (blocking)
    py busstop.py --preview    540x960 30 fps per shot (+ quarter-speed copy); --shot S2 for one shot
    py busstop.py --check      motion/contact/caption checks over every frame + stills and cut frames
    py busstop.py              final 1080x1920 30 fps with captions and the mix's audio
"""
import json
import math
import os
import subprocess
import sys

import numpy as np
import skia
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "toon"))
import toon as TN  # noqa: E402
import rig  # noqa: E402
from anim import HOLD, Track, blink, move  # noqa: E402
from toon import Camera, Frame, Rain, W, H, argb, lin, paint, shade  # noqa: E402

EP = os.path.dirname(HERE)
T0 = 11.32                                    # episode time of sample t = 0
FPS = 30
OUT = os.path.join(HERE, "review")
SHOTS = [("S1", 0.00, 1.88), ("S2", 1.88, 3.67), ("S3", 3.67, 5.48), ("S4", 5.48, 6.38)]
LIGHT = (-0.55, 2.36, 6.30)                   # the shelter's fluorescent tube
SHELTER = (-2.4, 1.3, 5.35, 7.3)              # x0, x1, z0, z1
RAIN = Rain(n=2400, box=((-6, 9), (0, 4.0), (1.0, 14)), speed=7.0, seed=5,
            shelter=(SHELTER[0] - 0.1, SHELTER[1] + 0.1, SHELTER[2] - 0.1, SHELTER[3], 2.6))


# ---- set -------------------------------------------------------------------------------------------------
BUILDINGS = [(-14, -7, 16, 44), (-7, -2, 22, 46), (-2, 4, 12, 40), (4, 9, 19, 45), (9, 15, 14, 42), (15, 22, 24, 48)]


def draw_sky(fr, cam):
    c = fr.c
    hy = H * cam.horizon
    c.drawRect(skia.Rect(0, 0, W, H), paint(shader=lin((0, 0), (0, hy), [argb("#070a16"), argb("#18213d")])))


def draw_far(fr, cam):
    for x0, x1, top, z in BUILDINGS:
        fr.poly(cam, [(x0, 0, z), (x1, 0, z), (x1, top, z), (x0, top, z)], colr="#101628")
        fr.poly(cam, [(x0, top - 0.6, z - 0.01), (x1, top - 0.6, z - 0.01), (x1, top, z - 0.01), (x0, top, z - 0.01)], colr="#161e36")
        k = 0
        for wy in np.arange(2.0, top - 1.5, 2.6):
            for wx in np.arange(x0 + 0.8, x1 - 0.8, 1.6):
                k += 1
                if (k * 7 + int(wx * 3) + int(wy)) % 5:
                    continue
                q = [(wx, wy, z - 0.02), (wx + 0.8, wy, z - 0.02), (wx + 0.8, wy + 1.1, z - 0.02), (wx, wy + 1.1, z - 0.02)]
                fr.poly(cam, q, colr="#ffbb66" if k % 3 else "#ffd49a")
                x, y, _, s = cam.proj((wx + 0.4, wy + 0.55, z))
                fr.glow(x, y, 1.6 * s, "#ff9a40", a=0.18)
    # far pavement, road, kerbs
    fr.poly(cam, [(-30, 0, 15), (30, 0, 15), (30, 0, 18), (-30, 0, 18)], colr="#1d2336")
    fr.poly(cam, [(-30, 0, 7.75), (30, 0, 7.75), (30, 0, 15), (-30, 0, 15)],
            shader=lambda p: lin((0, p.getBounds().top()), (0, p.getBounds().bottom()), [argb("#0e1220"), argb("#161b2c")]))
    for x in np.arange(-20, 24, 3.2):
        fr.poly(cam, [(x, 0, 11.3), (x + 1.6, 0, 11.3), (x + 1.6, 0, 11.45), (x, 0, 11.45)], colr="#3a4258")
    fr.box(cam, (-30, 30), (0, 0.13), (7.6, 7.75), "#4a5268")
    # a street lamp across the road and its reflection on the wet asphalt
    for lx in (-8.0, 7.5):
        fr.box(cam, (lx - 0.06, lx + 0.06), (0, 4.6), (14.6, 14.72), "#252b3c")
        x, y, _, s = cam.proj((lx, 4.55, 14.0))
        fr.glow(x, y, 1.1 * s, "#cfe0ff", a=0.55)
        rx, ry, _, rs = cam.proj((lx, -2.6, 13.0))
        fr.glow(rx, ry, 0.5 * rs, "#9fb8ff", a=0.25, sx=0.6, sy=3.0)


def draw_ground(fr, cam):
    fr.poly(cam, [(-30, 0, -3), (30, 0, -3), (30, 0, 7.6), (-30, 0, 7.6)],
            shader=lambda p: lin((0, H * cam.horizon), (0, H), [argb("#20273c"), argb("#2c3550")]))
    for z in np.arange(-1.0, 7.6, 1.2):                                   # paving joints, subtle
        fr.poly(cam, [(-30, 0, z), (30, 0, z), (30, 0, z + 0.025), (-30, 0, z + 0.025)], colr="#1a2032", a=0.7)
    # cool pool under the shelter light, a wet reflection of the tube, puddles
    fr.ground_ellipse(cam, LIGHT[0], LIGHT[2] - 0.2, 2.5, 1.5, "#6f8fd0", 0.30, blur_m=0.5, add=True)
    fr.ground_ellipse(cam, LIGHT[0], LIGHT[2] - 0.2, 1.3, 0.8, "#8fb0ff", 0.22, blur_m=0.3, add=True)
    for px, pz, rx, rz in ((2.2, 4.9, 0.7, 0.28), (-2.9, 4.4, 0.9, 0.3), (0.6, 3.6, 0.5, 0.18)):
        fr.ground_ellipse(cam, px, pz, rx, rz, "#141a2a", 0.8, blur_m=0.02)
    x, y, _, s = cam.proj((LIGHT[0], -LIGHT[1], LIGHT[2] - 0.4))
    fr.glow(x, y, 0.55 * s, "#cfe0ff", a=0.22, sx=1.6, sy=0.5)


def solids():
    """Solid set pieces as world boxes (x, y, z ranges), matching what shelter_items() draws."""
    x0, x1, z0, z1 = SHELTER
    s = {"back": ((x0, x1), (0.1, 2.42), (z1 - 0.03, z1 + 0.03)),
         "bench": ((x0 + 0.3, -0.2), (0.0, 0.47), (6.75, 7.1)),
         "sign": ((0.87, 0.93), (0.0, 2.25), (4.47, 4.53)),
         "bin": ((2.35, 2.8), (0.0, 0.92), (4.0, 4.45))}
    for px, pz in ((x0, z0 + 0.1), (x1, z0 + 0.1), (x0, z1 - 0.05), (x1, z1 - 0.05)):
        s[f"post{px:+.1f},{pz:.2f}"] = ((px - 0.04, px + 0.04), (0.0, 2.45), (pz - 0.04, pz + 0.04))
    return s


def shelter_items(cam):
    """Shelter pieces as depth-sorted drawables (they interleave with the characters)."""
    x0, x1, z0, z1 = SHELTER
    items = []

    def add(pt, fn, name="set"):
        items.append((cam.view(pt)[2], fn, name))

    def back(fr):
        # back glass with a frame, a backlit poster on the right half, a highlight streak
        fr.poly(cam, [(x0, 0.1, z1), (x1, 0.1, z1), (x1, 2.42, z1), (x0, 2.42, z1)], colr="#5a78a8", a=0.22)
        fr.poly(cam, [(0.05, 0.35, z1 - 0.01), (1.15, 0.35, z1 - 0.01), (1.15, 2.1, z1 - 0.01), (0.05, 2.1, z1 - 0.01)],
                shader=lambda p: lin((0, p.getBounds().top()), (0, p.getBounds().bottom()), [argb("#93a5cc"), argb("#5f739e")]))
        fr.poly(cam, [(0.25, 1.25, z1 - 0.02), (0.95, 1.25, z1 - 0.02), (0.95, 1.95, z1 - 0.02), (0.25, 1.95, z1 - 0.02)], colr="#b9474a")
        fr.poly(cam, [(0.25, 0.6, z1 - 0.02), (0.95, 0.6, z1 - 0.02), (0.95, 0.75, z1 - 0.02), (0.25, 0.75, z1 - 0.02)], colr="#2a3552")
        fr.poly(cam, [(0.25, 0.85, z1 - 0.02), (0.75, 0.85, z1 - 0.02), (0.75, 0.95, z1 - 0.02), (0.25, 0.95, z1 - 0.02)], colr="#2a3552")
        fr.poly(cam, [(x0 + 0.4, 0.3, z1 - 0.005), (x0 + 0.7, 0.3, z1 - 0.005), (x0 + 1.4, 2.3, z1 - 0.005), (x0 + 1.1, 2.3, z1 - 0.005)], colr="#ffffff", a=0.06)
        for xx in (x0, x1, -0.0):
            fr.box(cam, (xx - 0.03, xx + 0.03), (0.1, 2.42), (z1 - 0.03, z1 + 0.03), "#7c8aa6", light=LIGHT)
        fr.box(cam, (x0, x1), (0.08, 0.12), (z1 - 0.03, z1 + 0.03), "#7c8aa6", light=LIGHT)
        x, y, _, s = cam.proj((0.6, 1.2, z1 - 0.05))
        fr.glow(x, y, 1.0 * s, "#b9ccff", a=0.18)
    add((0.0, 1.2, z1 + 0.4), back, "back")      # anchor behind its own posts: no order flips

    def bench(fr):
        fr.box(cam, (x0 + 0.3, -0.2), (0.42, 0.47), (6.75, 7.1), "#8a6a4e", light=LIGHT)
        for bx in (x0 + 0.45, -0.35):
            fr.box(cam, (bx - 0.03, bx + 0.03), (0.0, 0.42), (6.85, 6.95), "#5d6680", light=LIGHT)
    add((x0 + 1.0, 0.45, 6.9), bench, "bench")

    for px, pz in ((x0, z0 + 0.1), (x1, z0 + 0.1), (x0, z1 - 0.05), (x1, z1 - 0.05)):
        add((px, 1.2, pz), lambda fr, px=px, pz=pz: fr.box(cam, (px - 0.04, px + 0.04), (0, 2.45), (pz - 0.04, pz + 0.04), "#7c8aa6", light=LIGHT),
            f"post{px:+.1f},{pz:.2f}")

    def roof(fr):
        fr.box(cam, (x0 - 0.15, x1 + 0.15), (2.45, 2.6), (z0, z1 + 0.05), "#3a4660", light=LIGHT)
        fr.box(cam, (LIGHT[0] - 1.0, LIGHT[0] + 1.0), (2.40, 2.45), (LIGHT[2] - 0.05, LIGHT[2] + 0.05), "#f2f8ff")
        x, y, _, s = cam.proj(LIGHT)
        fr.glow(x, y, 1.4 * s, "#cfe0ff", a=0.45, sx=1.6, sy=0.8)
        fr.glow(x, y, 0.35 * s, "#ffffff", a=0.6, sx=2.8, sy=0.4)
    add((LIGHT[0], 2.5, z1 + 0.5), roof, "roof")                      # always behind the people

    def sign(fr):                                             # bus-stop sign pole in the foreground
        fr.box(cam, (0.87, 0.93), (0, 2.25), (4.47, 4.53), "#7c8aa6", light=LIGHT)
        fr.box(cam, (0.62, 1.18), (2.2, 2.62), (4.44, 4.47), "#2f63c9", light=None)
        fr.box(cam, (0.7, 1.1), (2.3, 2.52), (4.435, 4.44), "#e8eef8")
    add((0.9, 1.2, 4.5), sign, "sign")

    def bin_(fr):
        fr.box(cam, (2.35, 2.8), (0, 0.85), (4.0, 4.45), "#2c4a3c", light=LIGHT)
        fr.box(cam, (2.32, 2.83), (0.85, 0.92), (3.97, 4.48), "#3c5e4c", light=LIGHT)
    add((2.6, 0.5, 4.2), bin_, "bin")
    return items


# ---- choreography (sample time t, seconds) ---------------------------------------------------------------
def hold(*names):
    return {n: HOLD for n in names}


JEFF = Track([
    (0.00, dict(x=-0.35, z=6.15, yaw=25, head_yaw=-4, head_pitch=18, lean=3, shrug=0.0, gx=0.15, gy=1.0,
                lid=0.62, brow=0.35, brow_in=-0.5, mouth=0.0, smile=0.0, lid_lo=0.0, side=0,
                aL=(24.0, -4.0, 92.0), aR=(4.0, 8.0, 14.0), fist=0.0, twist=0)),
    # notice: eyes -> head -> shoulders -> body -> hands, each starting a little after the last
    (2.05, hold("gx", "gy", "lid")), (2.15, dict(gx=0.75, gy=0.0, lid=1.0), "out"),
    (2.18, hold("head_yaw", "head_pitch", "brow", "brow_in")),
    (2.50, dict(head_yaw=34, head_pitch=-2, brow=0.45, brow_in=-0.25), "io"),
    (2.38, hold("shrug", "lean")), (2.62, dict(shrug=0.75, lean=-3), "out"),
    (2.45, hold("yaw")), (2.95, dict(yaw=62, head_yaw=8, gx=0.25), "io"),
    (2.70, hold("aL")), (3.05, dict(aL=(10.0, 4.0, 30.0)), "io"),              # phone comes down
    (2.80, hold("aR", "fist")), (3.30, dict(aR=(-38.0, 34.0, 24.0), fist=0.6), "back"),   # shields Liu
    (3.58, hold("aR")), (4.20, dict(aR=(-14.0, 24.0, 22.0)), "io"),             # arm eases down as Randy stops
    # Randy arrives: Jeff squares up to him; the knife makes him flinch (seen from behind in S3)
    (3.90, hold("yaw", "head_yaw")), (4.50, dict(yaw=80, head_yaw=2), "io"),
    (5.06, hold("brow", "brow_in", "mouth", "gx", "gy", "shrug", "head_pitch")),
    (5.26, dict(brow=0.85, brow_in=-0.7, mouth=0.3, gx=0.3, gy=0.1, shrug=0.65, head_pitch=-5), "out"),
    # anger on "Jeff" (17.27 s): quick, then a small settle
    (5.92, hold("brow", "brow_in", "lid", "lid_lo", "mouth", "smile", "head_pitch", "shrug", "lean", "fist", "gx")),
    (6.06, dict(brow=-0.25, brow_in=1.0, lid=0.70, lid_lo=0.25, mouth=0.0, smile=-0.55, head_pitch=7,
                shrug=0.2, lean=2, fist=1.0, gx=0.45), "out"),
    (6.38, dict(head_pitch=5, lean=1), "back"),
])
JEFF_BLINKS = [0.95, 3.45]
PHONE = Track([(0.0, dict(u=0.0)), (2.70, dict(u=0.0)), (3.10, dict(u=1.0), "io")])

LIU = Track([
    (0.00, dict(x=-1.19, z=6.28, yaw=32, head_yaw=18, head_pitch=4, lid=0.78, gx=0.3, gy=0.1, brow=0.0,
                brow_in=0.0, mouth=0.0, crouch=0.0, lean=0, aR=(6.0, 6.0, 16.0), aL=(6.0, 6.0, 16.0), shrug=0)),
    (2.55, hold("gx", "lid")), (2.63, dict(gx=0.8, lid=1.0), "out"),            # notices after Jeff
    (2.68, hold("head_yaw", "head_pitch", "brow", "brow_in", "mouth")),
    (2.95, dict(head_yaw=40, head_pitch=-2, brow=0.7, brow_in=-0.7, mouth=0.18), "io"),
    (2.90, hold("crouch", "lean", "shrug", "aR", "aL")),
    (3.45, dict(crouch=0.025, lean=-5, shrug=0.8, aR=(48.0, 6.0, 122.0), aL=(44.0, 4.0, 118.0)), "out"),
])
LIU_BLINKS = [1.40, 4.6]

WALKERS = {   # start pelvis point, yaw, step length, steps/s, steps, start time
    "randy": dict(start=(3.46, 0, 6.05), yaw=-90, step=0.542, rate=1.235, n=5),
    "bully": dict(start=(4.16, 0, 6.07), yaw=-90, step=0.5025, rate=1.37, n=4),
    "bully2": dict(start=(4.36, 0, 5.33), yaw=-90, step=0.526, rate=1.27, n=5),
}
RANDY_UP = Track([       # upper body after the stop (t >= stop time); blended in over 0.35 s
    (4.05, dict(lean=5, head_pitch=4, aR=(4.0, 8.0, 16.0), aL=(4.0, 8.0, 16.0), smile=0.2, brow_in=0.5, lid=0.85,
                gx=-0.2, head_yaw=-6, mouth=0.0, shrug=0.0, lid_lo=0.1)),
    (4.42, dict(lean=-1), "back"),                                          # settle with overshoot
    (4.30, hold("head_pitch", "smile", "lid", "lid_lo")),
    (4.62, dict(head_pitch=-8, smile=0.5, lid=0.78, lid_lo=0.3), "io"),     # chin up, sneer
    (4.80, hold("aL", "lean", "shrug")),
    (5.00, dict(aL=(-42.0, 14.0, 38.0), lean=1, shrug=0.25), "io"),         # preparation: hand to back pocket
    (5.05, hold("aL", "lean", "shrug")),                                    # grip in the pocket
    (5.14, dict(aL=(45.0, 30.0, 75.0), lean=6, shrug=0.0), "snap"),         # the draw: quick
    (5.48, dict(aL=(40.0, 26.0, 82.0), lean=4, smile=0.65), "back"),        # settle, knife held out
])
KNIFE = Track([(5.04, dict(k=0.0)), (5.13, dict(k=1.0), "snap")])
BULLY_UP = {"bully": dict(aR=(34.0, -14.0, 118.0), aL=(30.0, -18.0, 112.0), smile=0.5, brow_in=0.5, lid=0.85),
            "bully2": dict(aR=(-4.0, 6.0, 26.0), aL=(-4.0, 6.0, 26.0), smile=0.7, brow=-0.1, lid=0.8, head_yaw=-10)}


def walker_pose(name, t):
    w = WALKERS[name]
    g = rig.gait(t, w["start"], w["yaw"], w["step"], w["rate"], n=w["n"], h=rig.LOOK[name]["h"])
    t_stop = w["n"] / w["rate"]
    sw = g["swing"]
    walk_arms = dict(aR=(-sw * 22 + 2, 7.0, 18.0), aL=(sw * 22 + 2, 7.0, 18.0))
    p = dict(x=g["x"], z=g["z"], yaw=w["yaw"], bob=g.get("bob", 0.0), lean=4,
             ankle_R=g["ankle_R"], ankle_L=g["ankle_L"], brow_in=0.4, lid=0.85, smile=0.15, **walk_arms)
    if not g["moving"]:
        # blend out of the walk over 0.6 s (lean and arms start from their last walk values: no snap)
        u = min(1.0, (t - t_stop) / 0.6)
        u = 0.5 - 0.5 * math.cos(math.pi * u)
        up = {"lean": 0, **(RANDY_UP(t) if name == "randy" else BULLY_UP[name])}
        for k, v in up.items():
            a = p.get(k, rig.REST[k])
            p[k] = tuple(x + (y - x) * u for x, y in zip(a, v)) if isinstance(v, tuple) else a + (v - a) * u
    p["plant"] = g["plant"]
    return p


POCKET = Track([(4.82, dict(w=0.0)), (5.00, dict(w=1.0), "io"), (5.05, dict(w=1.0)), (5.14, dict(w=0.0), "snap")])


def randy_pocket(p, t):
    """Randy's left hand reaches his back pocket (4.82-5.00), grips (5.00-5.05), then the draw takes it out.
    IK target = blend of the keyed (FK) wrist and the pocket; the FK elbow is the pole, so w=0 matches FK exactly."""
    w = POCKET(t)["w"]
    if w <= 0:
        return
    J = rig.solve("randy", p)
    h = rig.LOOK["randy"]["h"]
    pocket = J["Bb"].w(J["pelvis"], -0.075 * h, -0.05 * h, -0.075 * h)
    wr = J["wr_L"]
    p["ik_L"] = tuple(a + (b - a) * w for a, b in zip(wr, pocket))
    p["pole_L"] = rig.norm(rig.sub(J["el_L"], J["sh_L"]))


_FEET = {}


def jeff_feet(t):
    """Jeff's ankles stay planted in world space while his body turns; when he squares up (3.90-4.50) he
    re-plants: right foot first, then left, each lifted on a short arc."""
    if not _FEET:
        for k, tt in (("A", 0.0), ("B", 6.0)):
            J = rig.solve("jeff", JEFF(tt))
            _FEET[k] = (J["ank_R"], J["ank_L"])
    (aR, aL), (bR, bL) = _FEET["A"], _FEET["B"]
    h = rig.LOOK["jeff"]["h"]
    out, plant = {}, "both"
    for s, a, b, t0 in (("R", aR, bR, 3.90), ("L", aL, bL, 4.20)):
        u = min(1.0, max(0.0, (t - t0) / 0.30))
        if 0 < u < 1:
            plant = "L" if s == "R" else "R"
        e = 0.5 - 0.5 * math.cos(math.pi * u)
        lift = 0.03 * h * math.sin(math.pi * u)
        out["ankle_" + s] = (a[0] + (b[0] - a[0]) * e, a[1] + (b[1] - a[1]) * e + lift, a[2] + (b[2] - a[2]) * e)
    out["plant"] = plant
    return out


def cast(t):
    """[(name, pose, held, glow)] for every character at sample time t."""
    out = []
    jp = JEFF(t)
    jp.update(jeff_feet(t))
    jp["lid"] *= blink(t, JEFF_BLINKS)
    phone_on = t < 3.4
    # the phone hand is placed by IK: in front of the sternum, then lowered beside the hip (PHONE: 0 -> 1)
    J0 = rig.solve("jeff", jp)
    h = rig.LOOK["jeff"]["h"]
    up_pt = J0["Bc"].w(J0["pelvis"], -0.08 * h, 0.15 * h, 0.17 * h)   # phone held up in front of the chest
    down_pt = J0["Bb"].w(J0["pelvis"], -0.12 * h, 0.02 * h, 0.06 * h)   # within reach: arm hangs relaxed, slight elbow bend
    u = PHONE(t)["u"]
    jp["ik_L"] = tuple(a + (b - a) * u for a, b in zip(up_pt, down_pt))
    J = rig.solve("jeff", jp)
    glow = (rig.add(J["hand_L"], (0, 0.06, 0)), 0.30, "#3a78ff", 0.45 * max(0.0, 1 - max(0.0, t - 2.4) / 0.8)) if phone_on else None
    out.append(("jeff", jp, {"L": rig.phone(on=phone_on)}, glow))
    lp = LIU(t)
    lp["lid"] *= blink(t, LIU_BLINKS)
    out.append(("liu", lp, None, None))
    for name in WALKERS:
        p = walker_pose(name, t)
        if name == "randy":
            randy_pocket(p, t)
        held = {"L": rig.knife(KNIFE(t)["k"])} if name == "randy" and t >= 5.04 else None
        out.append((name, p, held, None))
    return out


# ---- cameras (continuous moves; nothing restarts at caption changes) -------------------------------------
def camera(t):
    if t < 1.88:
        a = dict(x=-0.75, y=1.30, z=2.60, yaw=0.0, f=1300.0)
        b = dict(x=1.35, y=1.30, z=2.30, yaw=8.0, f=1300.0)
        k = {n: move(t, 0.25, 1.88, a[n], b[n], ramp=0.35) for n in a}
        return "S1", Camera((k["x"], k["y"], k["z"]), k["yaw"], k["f"])
    if t < 3.67:
        a = dict(x=0.50, y=1.30, z=3.90, yaw=-14.0)
        b = dict(x=0.42, y=1.30, z=4.18, yaw=-15.0)
        k = {n: move(t, 1.88, 3.67, a[n], b[n], ramp=0.25) for n in a}
        return "S2", Camera((k["x"], k["y"], k["z"]), k["yaw"], 1750)
    if t < 5.48:
        a = dict(x=-2.00, y=1.45, z=5.20)
        b = dict(x=-1.80, y=1.45, z=5.27)
        k = {n: move(t, 3.67, 5.48, a[n], b[n], ramp=0.25) for n in a}
        return "S3", Camera((k["x"], k["y"], k["z"]), 70.0, 1500)
    # reverse angle from Randy's side, ~35 deg off Jeff's eyeline (both eyes read), clear of the knife arm
    a = dict(x=0.64, z=5.33, yaw=-49.0, f=1950.0)
    b = dict(x=0.58, z=5.28, yaw=-47.0, f=2050.0)
    k = {n: move(t, 5.48, 6.38, a[n], b[n], ramp=0.25) for n in a}
    return "S4", Camera((k["x"], 1.55, k["z"]), k["yaw"], k["f"])


# ---- captions (screen-fixed, one band) -------------------------------------------------------------------
TL = json.load(open(os.path.join(EP, "timeline.json"), encoding="utf-8"))
CHUNKS = sorted([c for L in TL["lines"] for c in L["chunks"]], key=lambda c: c["t0"])
CAP_Y = 1500
FONT = skia.Font(TN.typeface(), 66)   # by name it fell back to a thin face


def caption(T):
    cur = None
    for c in CHUNKS:
        if c["t0"] <= T + 1e-6:
            cur = c
    return cur["text"] if cur and T < cur["t1"] + 0.45 else None


def caption_box(text):
    w = FONT.measureText(text.replace("[", "").replace("]", "")) + 16
    return ((W - w) / 2, CAP_Y - 48, (W + w) / 2, CAP_Y + 22)


def draw_caption(fr, text):
    parts = [(b.strip("[]"), b.startswith("[")) for b in text.replace("[", "|[").replace("]", "]|").split("|") if b]
    x = (W - sum(FONT.measureText(p) for p, _ in parts)) / 2
    for p, key in parts:
        blob = skia.TextBlob(p, FONT)
        fr.c.drawTextBlob(blob, x, CAP_Y, paint("#000000", stroke=12))
        fr.c.drawTextBlob(blob, x, CAP_Y, paint("#FF4D4D" if key else "#F4F1EA"))
        x += FONT.measureText(p)


# ---- one frame ---------------------------------------------------------------------------------------------
def render(t, scale=1.0, captions=True, log=None):
    shot, cam = camera(t)
    fr = Frame(scale)
    draw_sky(fr, cam)
    draw_far(fr, cam)
    draw_ground(fr, cam)
    items = shelter_items(cam)
    people = cast(t)
    for name, p, held, glow in people:
        J = rig.solve(name, p)
        items.append((cam.view(J["pelvis"])[2], lambda fr, name=name, p=p, held=held, glow=glow:
                      _person(fr, cam, name, p, held, glow, log, shot, t), name))
    order = sorted(items, key=lambda q: -q[0])
    for _, fn, _ in order:
        fn(fr)
    if log is not None:
        log.append(dict(kind="order", t=t, shot=shot, order=[n for _, _, n in order], cam=cam))
    RAIN.draw(fr, cam, t + T0, light=LIGHT)
    # vignette: darkens the frame edges, keeps the centre readable
    fr.c.drawRect(skia.Rect(0, 0, W, H), paint(shader=skia.GradientShader.MakeRadial(
        skia.Point(W / 2, H * 0.45), H * 0.75, [argb("#000000", 0), argb("#000000", 0), argb("#000008", 0.55)], [0, 0.55, 1])))
    if captions:
        c = caption(T0 + t)
        if c:
            draw_caption(fr, c)
    return shot, fr.array()


def _person(fr, cam, name, p, held, glow, log, shot, t):
    j = rig.draw(fr, cam, name, p, light=LIGHT, glow=glow, held=held)
    if log is not None and not j.get("culled"):
        J = j["J"]
        log.append(dict(kind="person", J=J, held=sorted(held or {}), t=t, shot=shot, name=name, plant=p.get("plant", "both"),
                        ank_R=J["ank_R"], ank_L=J["ank_L"], head=j["head"], head_r=j["head_r"],
                        hand_R=j.get("hand_R"), hand_L=j.get("hand_L"), err=J["err"],
                        lens=[math.dist(J["sh_R"], J["el_R"]), math.dist(J["el_R"], J["wr_R"]),
                              math.dist(J["hip_L"], J["kn_L"]), math.dist(J["kn_L"], J["ank_L"])],
                        joints={k: cam.proj(J[k])[:2] for k in ("head", "wr_R", "wr_L", "el_R", "el_L", "kn_R", "kn_L")}))


# ---- modes -------------------------------------------------------------------------------------------------
KEYS = {"S1": [(0.0, "Jeff + Liu under the light"), (0.95, "truck right begins the reveal"), (1.87, "bullies in view")],
        "S2": [(1.88, "on phone"), (2.15, "eyes shift"), (2.5, "head turns"), (2.62, "shoulders tense"), (3.3, "arm shields Liu")],
        "S3": [(3.7, "last step"), (4.1, "stop"), (4.62, "chin up"), (5.0, "hand to pocket"), (5.14, "knife out"), (5.47, "settle")],
        "S4": [(5.5, "fear"), (5.93, "anger starts"), (6.06, "anger"), (6.37, "settled")]}


def sheet(tiles, path, cols=6):
    w, h = tiles[0].size
    rows = (len(tiles) + cols - 1) // cols
    im = Image.new("RGB", (cols * (w + 4), rows * (h + 4)), (255, 0, 255))
    for i, t in enumerate(tiles):
        im.paste(t, ((i % cols) * (w + 4), (i // cols) * (h + 4)))
    im.save(path)


def label(im, text):
    d = ImageDraw.Draw(im)
    d.rectangle((0, im.height - 22, im.width, im.height), fill=(0, 0, 0))
    d.text((6, im.height - 18), text, fill=(255, 255, 0))
    return im


def poses():
    os.makedirs(OUT, exist_ok=True)
    tiles = []
    for shot, a, b in SHOTS:
        for tk, lab in KEYS[shot]:
            _, arr = render(tk, 0.3)
            tiles.append(label(Image.fromarray(arr), f"{shot} {T0 + tk:.2f}s {lab}"))
    sheet(tiles, os.path.join(OUT, "poses.png"))
    print("poses.png", len(tiles), "keys")


def encode(frames, path, size, fps=FPS):
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", size,
                          "-r", str(fps), "-i", "-", "-c:v", "libx264", "-crf", "15", "-preset", "medium",
                          "-pix_fmt", "yuv420p", path], stdin=subprocess.PIPE)
    for a in frames:
        p.stdin.write(np.ascontiguousarray(a).tobytes())
    p.stdin.close()
    p.wait()


def frames_of(a, b):
    return [i / FPS for i in range(int(round(a * FPS)), int(round(b * FPS)))]


def preview(only=None):
    os.makedirs(OUT, exist_ok=True)
    for shot, a, b in SHOTS:
        if only and shot != only:
            continue
        path = os.path.join(OUT, f"preview_{shot}.mp4")
        encode((render(t, 0.5)[1] for t in frames_of(a, b)), path, "540x960")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-vf", "setpts=4*PTS", "-r", "30",
                        os.path.join(OUT, f"preview_{shot}_quarter.mp4")], check=True)
        print("preview", shot)


def _spheres(J):
    """Body volumes (name, centre, radius) for collision tests."""
    h, f = J["h"], J["Bb"].f
    mid = lambda a, b: tuple((x + y) / 2 for x, y in zip(a, b))       # noqa: E731
    out = [("pelvis", J["pelvis"], 0.085 * h), ("chest", mid(J["neck"], J["pelvis"]), 0.08 * h), ("head", J["head"], J["R"])]
    for s in ("R", "L"):
        out += [("hand_" + s, J["hand_" + s], 0.035 * h), ("elbow_" + s, J["el_" + s], 0.03 * h),
                ("knee_" + s, J["kn_" + s], 0.035 * h), ("ankle_" + s, J["ank_" + s], 0.03 * h),
                ("toe_" + s, rig.add(J["ank_" + s], rig.mul(J.get("fdir_footf_" + s, f), 0.06 * h)), 0.03 * h)]
    return out


def _box_pen(c, r, box):
    q = [min(max(v, lo), hi) for v, (lo, hi) in zip(c, box)]
    return r - math.dist(c, q)


def _angle(a, b):
    return math.degrees(math.acos(max(-1.0, min(1.0, rig.dot(rig.norm(a), rig.norm(b))))))


GAZE = {  # who should be looking at whom: (name, from t, target name, target joint)
    "jeff": [(0.0, "jeff", "hand_L"), (2.55, "randy", "head")],
    "liu": [(3.0, "randy", "head")],
    "randy": [(4.45, "jeff", "head")],
}


def constraints(log):
    """Physical checks on every logged frame. Returns report lines (each anomaly with its time)."""
    rep = []
    people = [r for r in log if r["kind"] == "person"]
    frames = {}
    for r in people:
        frames.setdefault((r["shot"], r["t"]), {})[r["name"]] = r
    S = solids()
    hits = {}

    def hit(key, t, msg):
        a = hits.setdefault(key, [t, t, msg])
        a[0], a[1] = min(a[0], t), max(a[1], t)
        if len(msg) > len(a[2]):
            a[2] = msg
    by = {}
    for r in people:
        by.setdefault((r["shot"], r["name"]), []).append(r)
    for (shot, name), rs in by.items():
        prev = None
        for r in rs:
            J, t, h = r["J"], r["t"], r["J"]["h"]
            for s in ("R", "L"):
                up, fo = rig.sub(J["el_" + s], J["sh_" + s]), rig.sub(J["wr_" + s], J["el_" + s])
                bend = _angle(up, fo)
                if bend > 155:
                    hit((shot, name, "elbow over-bent", s), t, f"elbow_{s} {bend:.0f} deg")
                thigh, shin = rig.sub(J["kn_" + s], J["hip_" + s]), rig.sub(J["ank_" + s], J["kn_" + s])
                knee_fwd = rig.dot(rig.sub(J["kn_" + s], rig.mul(rig.add(J["hip_" + s], J["ank_" + s]), 0.5)), J["Bb"].f)
                if knee_fwd < -0.005:
                    hit((shot, name, "knee reversed", s), t, f"knee_{s} {knee_fwd * 1000:.0f} mm behind the leg line")
                if prev:
                    for lab, a1, b1, a0, b0 in (("elbow", up, fo, rig.sub(prev["el_" + s], prev["sh_" + s]), rig.sub(prev["wr_" + s], prev["el_" + s])),
                                                ("knee", thigh, shin, rig.sub(prev["kn_" + s], prev["hip_" + s]), rig.sub(prev["ank_" + s], prev["kn_" + s]))):
                        n1, n0 = rig.cross(a1, b1), rig.cross(a0, b0)
                        if _angle(a1, b1) > 12 and _angle(a0, b0) > 12 and rig.dot(n1, n0) < 0:
                            hit((shot, name, f"{lab} flip", s), t, f"{lab}_{s} bend plane flipped between frames")
                ay = J["ank_" + s][1] - 0.035 * h
                if ay < -0.003:
                    hit((shot, name, "foot sinks", s), t, f"ankle_{s} {ay * 1000:.0f} mm into the ground")
                if r["plant"] in (s, "both") and abs(ay) > 0.003:
                    hit((shot, name, "planted foot floats", s), t, f"ankle_{s} {ay * 1000:.0f} mm off the ground")
            for part, c, rad in _spheres(J):
                for sn, box in S.items():
                    pen = _box_pen(c, rad, box)
                    if pen > 0.005:
                        hit((shot, name, "passes through", sn, part), t, f"{part} {pen * 1000:.0f} mm inside {sn}")
            prev = J
    for (shot, t), who in frames.items():
        names = sorted(who)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                for pa, ca, ra in _spheres(who[a]["J"]):
                    for pb, cb, rb in _spheres(who[b]["J"]):
                        pen = ra + rb - math.dist(ca, cb)
                        if pen > 0.01:
                            hit((shot, a, "touches", b, pa, pb), t, f"{a} {pa} {pen * 1000:.0f} mm into {b} {pb}")
    # occlusion: two things that overlap on screen must not swap front/back between consecutive frames
    orders = [r for r in log if r["kind"] == "order"]

    def bbox(shot, t, n, cam):
        if n in frames.get((shot, t), {}):
            J = frames[(shot, t)][n]["J"]
            pts = [cam.proj(c)[:2] for _, c, _ in _spheres(J)]
        elif n in S:
            xs, ys, zs = S[n]
            pts = [cam.proj((x, y, z))[:2] for x in xs for y in ys for z in zs if cam.view((x, y, z))[2] > 0.05]
        else:
            return None
        if not pts:
            return None
        return min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)
    for o0, o1 in zip(orders, orders[1:]):
        if o0["shot"] != o1["shot"]:
            continue
        r0 = {n: i for i, n in enumerate(o0["order"])}
        r1 = {n: i for i, n in enumerate(o1["order"])}
        common = [n for n in r0 if n in r1]
        for i, a in enumerate(common):
            for b in common[i + 1:]:
                if (r0[a] < r0[b]) != (r1[a] < r1[b]):
                    ba, bb = bbox(o1["shot"], o1["t"], a, o1["cam"]), bbox(o1["shot"], o1["t"], b, o1["cam"])
                    if ba and bb and ba[0] < bb[2] and bb[0] < ba[2] and ba[1] < bb[3] and bb[1] < ba[3]:
                        hit((o1["shot"], a, "order flip", b), o1["t"], f"{a} and {b} swap front/back while overlapping")
    # reach before grab: Randy's hand is at his hip when the knife appears
    for r in people:
        if r["name"] == "randy" and abs(r["t"] - 5.04) < 0.017:
            d = math.dist(r["J"]["hand_L"], r["J"]["hip_L"])
            rep.append(f"grab: Randy's left hand is {d * 100:.0f} cm from his hip when the knife appears at {T0 + 5.04:.2f}s"
                       + (" OK" if d < 0.2 else " TOO FAR"))
    # gaze: head direction vs the thing the character should be looking at (reported at each shot's last frame)
    for (shot, t), who in sorted(frames.items(), key=lambda kv: kv[0][1]):
        last = max(tt for (s2, tt) in frames if s2 == shot)
        if t != last:
            continue
        for n, rules in GAZE.items():
            if n not in who:
                continue
            rule = [g for g in rules if g[0] <= t]
            if not rule:
                continue
            _, tn, joint = rule[-1]
            src = who[n]["J"]
            tgt = (who.get(tn) or {}).get("J") or rig.solve(tn, dict(cast(t)[[c[0] for c in cast(t)].index(tn)][1]))
            pp = src["pose"]                                 # eyes add up to ~20 deg of look on top of the head
            look = rig.add(src["Bh"].f, rig.mul(src["Bh"].u, -0.36 * pp["gy"]))
            ang = _angle(look, rig.sub(tgt[joint], src["head"]))
            rep.append(f"gaze {shot} {T0 + t:.2f}s {n} looks {ang:.0f} deg off {tn} {joint}" + (" OK" if ang < 30 else " CHECK"))
    for (shot, *what), (ta, tb, msg) in sorted(hits.items(), key=lambda kv: kv[1][0]):
        rep.append(f"ANOMALY {shot} {T0 + ta:.2f}-{T0 + tb:.2f}s {what[0]}: {msg}")
    if not hits:
        rep.append("constraints: no joint, contact, collision or occlusion anomaly in any logged frame")
    return rep


def check():
    os.makedirs(OUT, exist_ok=True)
    log, rep = [], []
    stills = []
    for shot, a, b in SHOTS:
        ts = frames_of(a, b)
        for i, t in enumerate(ts):
            _, arr = render(t, 0.25, captions=False, log=log)
        for lab, t in (("first", ts[0]), ("mid", ts[len(ts) // 2]), ("last", ts[-1])):
            _, arr = render(t, 0.3)
            stills.append(label(Image.fromarray(arr), f"{shot} {lab} {T0 + t:.2f}s"))
    sheet(stills, os.path.join(OUT, "stills.png"), cols=6)
    by = {}
    for r in log:
        if r["kind"] == "person":
            by.setdefault((r["shot"], r["name"]), []).append(r)
    for (shot, name), rs in by.items():
        # feet: a planted ankle may not move while the same foot stays planted
        drift = 0.0
        for p, q in zip(rs, rs[1:]):
            for s in ("R", "L"):
                if p["plant"] in (s, "both") and q["plant"] in (s, "both"):
                    drift = max(drift, math.dist(p["ank_" + s], q["ank_" + s]))
        reach = max(max(r["err"].values()) for r in rs)
        lens = [r["lens"] for r in rs]
        lvar = max(max(l[i] for l in lens) - min(l[i] for l in lens) for i in range(4))
        # snaps: screen acceleration of joints between consecutive frames (px at 1080 wide)
        acc = (0.0, "")
        for p, q, r in zip(rs, rs[1:], rs[2:]):
            for k in p["joints"]:
                a2 = math.dist((r["joints"][k][0] - 2 * q["joints"][k][0] + p["joints"][k][0],
                                r["joints"][k][1] - 2 * q["joints"][k][1] + p["joints"][k][1]), (0, 0))
                if a2 > acc[0]:
                    acc = (a2, f"{k} {T0 + q['t']:.2f}s")
        hr = [r["head_r"] for r in rs]
        scale_jump = max(abs(b2 - a2) / a2 for a2, b2 in zip(hr, hr[1:])) if len(hr) > 1 else 0
        rep.append(f"{shot} {name:7s} planted-foot drift {drift * 1000:5.2f} mm | leg reach short {reach * 1000:5.1f} mm | "
                   f"limb length spread {lvar * 1000:4.2f} mm | max joint accel {acc[0]:6.1f} px/f^2 at {acc[1]} | "
                   f"head size jump/frame {scale_jump * 100:4.1f}%")
    hits = set()
    for r in log:
        if r["kind"] != "person":
            continue
        c = caption(T0 + r["t"])
        if not c:
            continue
        x0, y0, x1, y1 = caption_box(c)
        for what, pt, rr in (("face", r["head"], r["head_r"]), ("hand_R", r["hand_R"], 30), ("hand_L", r["hand_L"], 30)):
            if pt and x0 - rr < pt[0] < x1 + rr and y0 - rr < pt[1] < y1 + rr and -50 < pt[0] < W + 50:
                hits.add(f"caption {r['shot']} {T0 + r['t']:.2f}s {r['name']} {what} under '{c}'")
    rep += sorted(hits) or ["caption: no face or hand under the caption in any frame"]
    rep += constraints(log)
    open(os.path.join(OUT, "checks.txt"), "w").write("\n".join(rep) + "\n")
    print("\n".join(rep))
    # both sides of every cut at full res
    tiles = []
    for (s1, _, b1), (s2, a2, _) in zip(SHOTS, SHOTS[1:]):
        for t in (b1 - 2 / FPS, b1 - 1 / FPS, a2, a2 + 1 / FPS):
            _, arr = render(t, 0.3)
            tiles.append(label(Image.fromarray(arr), f"{T0 + t:.3f}s"))
    sheet(tiles, os.path.join(OUT, "cuts.png"), cols=4)


def final():
    os.makedirs(OUT, exist_ok=True)
    ts = frames_of(0.0, SHOTS[-1][2])
    silent = os.path.join(OUT, "busstop_silent.mp4")
    encode((render(t)[1] for t in ts), silent, f"{W}x{H}")
    src = os.path.join(EP, "video", "renders", "jeff_instagram.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-ss", str(T0), "-t", str(SHOTS[-1][2]),
                    "-i", src, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", "-movflags", "+faststart", os.path.join(OUT, "busstop.mp4")], check=True)
    print("busstop.mp4", len(ts), "frames")


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--poses" in a:
        poses()
    elif "--preview" in a:
        preview(a[a.index("--shot") + 1] if "--shot" in a else None)
    elif "--check" in a:
        check()
    else:
        final()
