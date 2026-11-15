"""THREE SECONDS LATE, part 1: "IT MOVED FIRST". Toon characters in a house (bathroom, kitchen, hallway, Grandma's
room), a news studio and a street, plus 2D inserts (globe, fridge photo, phone).

Mirrors are real reflections: the scene is drawn again from the camera reflected in the mirror plane, flipped and
clipped to the glass. The people in the mirror can be given their own poses (late, early, or someone else entirely).

    python reel.py --frame T [scale] | --stills | --master-par N
"""
import json
import math
import os
import subprocess
import sys

import numpy as np
import skia
import soundfile as sf
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
for d in (HERE, os.path.join(ROOT, "tools", "toon")):
    sys.path.insert(0, d)
import rig  # noqa: E402
import looks  # noqa: E402,F401
import toon as TN  # noqa: E402
from anim import blink  # noqa: E402
from toon import Camera, Frame, W, H, argb, lin, paint, rad, shade  # noqa: E402

FPS = 30
OUT, VID = os.path.join(HERE, "review"), os.path.join(HERE, "video")
TL = json.load(open(os.path.join(HERE, "timeline.json"), encoding="utf-8"))
TOTAL, B = TL["total"], TL["beats"]
b0 = lambda k: B[k]["t0"]      # noqa: E731
b1 = lambda k: B[k]["t1"]      # noqa: E731
TF, TFB = TN.typeface(False), TN.typeface(True)
RED, ACC = "#ff3b3b", "#9fd8ff"


# ---- helpers -----------------------------------------------------------------------------------------------------
def cl(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def sm(u):
    u = cl(u)
    return u * u * (3 - 2 * u)


def lerp(a, b, u):
    return tuple(x + (y - x) * u for x, y in zip(a, b)) if isinstance(a, tuple) else a + (b - a) * u


def cam(pos, tgt, f=1500, hz=0.46):
    return Camera(pos, math.degrees(math.atan2(tgt[0] - pos[0], tgt[2] - pos[2])), f, hz)


def camk(keys, T):
    """Camera from keys [(t, pos, tgt, f, hz)], eased between them."""
    if T <= keys[0][0]:
        k = keys[0]
        return cam(k[1], k[2], k[3], k[4])
    for a, b in zip(keys, keys[1:]):
        if T <= b[0]:
            u = sm((T - a[0]) / (b[0] - a[0]))
            return cam(lerp(a[1], b[1], u), lerp(a[2], b[2], u), lerp(a[3], b[3], u), lerp(a[4], b[4], u))
    k = keys[-1]
    return cam(k[1], k[2], k[3], k[4])


def text(c, s, x, y, size, colr="#ffffff", stroke=0.0, bold=True, a=1.0, center=True):
    f = skia.Font(TFB if bold else TF, size)
    w = f.measureText(s)
    x0 = x - w / 2 if center else x
    if stroke:
        c.drawString(s, x0, y, f, paint("#000000", a=a, stroke=stroke))
    c.drawString(s, x0, y, f, paint(colr, a=a))
    return w


def pill(c, x0, y0, x1, y1, colr, a=1.0):
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x0, y0, x1, y1), (y1 - y0) / 2, (y1 - y0) / 2), paint(colr, a=a))


def full(c, colr, a=1.0, blend=None):
    p = paint(colr, a=a)
    if blend:
        p.setBlendMode(blend)
    c.drawRect(skia.Rect(-10, -10, W + 10, H + 10), p)


def grad_bg(c, cols, pos=None):
    c.drawRect(skia.Rect(-10, -10, W + 10, H + 10), paint(shader=lin((0, 0), (0, H), [argb(x) for x in cols], pos)))


def vignette(c, a=0.55):
    c.drawRect(skia.Rect(-10, -10, W + 10, H + 10), paint(shader=rad((W / 2, H * 0.48), H * 0.72, [argb("#000000", 0), argb("#000000", a)], [0.5, 1])))


def night(c, tint="#3c4a78"):
    full(c, tint, blend=skia.BlendMode.kMultiply)


_ENV = {}


def mouth(T, speaker):
    for bid, b in B.items():
        if b["speaker"] == speaker and b["t0"] <= T < b["t1"]:
            if bid not in _ENV:
                a, sr = sf.read(os.path.join(HERE, "audio", "lines", bid + ".wav"), dtype="float32")
                hop = sr // 60
                n = len(a) // hop
                e = np.sqrt(np.mean(a[:n * hop].reshape(n, hop) ** 2, axis=1))
                _ENV[bid] = np.clip(e / max(1e-6, np.percentile(e, 95)), 0, 1)
            e = _ENV[bid]
            i = int((T - b["t0"]) * 60)
            return 0.34 * float(np.mean(e[max(0, i - 2):i + 3])) if i < len(e) else 0.0
    return 0.0


BLINKS = [0.7 + i * 2.9 + (i % 3) * 0.6 for i in range(40)]


def person(look, x, z, yaw, T, spk=None, **kw):
    p = dict(rig.REST, x=x, z=z, yaw=yaw, t=T, breath=0.5 + 0.5 * math.sin(T * 2.2 + x))
    p["lid"] = blink(T + (hash(look) % 7) * 0.37, BLINKS)
    p["aR"], p["aL"] = (6.0, 7.0, 16.0), (6.0, 7.0, 16.0)
    if spk:
        p["mouth"] = mouth(T, spk)
    p.update(kw)
    return p


def seated(look, x, z, yaw, seat_y, feet_fwd, T, spk=None, **kw):
    h = rig.LOOK[look]["h"]
    p = person(look, x, z, yaw, T, spk, crouch=0.47 - (seat_y + 0.06) / h)
    p.update(kw)
    Bb = rig.Basis.yaw(yaw)
    p["ankle_R"] = Bb.w((x, 0, z), 0.065 * h, 0.035 * h, feet_fwd)
    p["ankle_L"] = Bb.w((x, 0, z), -0.065 * h, 0.035 * h, feet_fwd)
    p["plant"] = "both"
    return p


def fwd(yaw):
    y = math.radians(yaw)
    return (math.sin(y), 0.0, -math.cos(y))


# ---- props in the hand -------------------------------------------------------------------------------------------
def stick(colr, length, width, tip=None):
    """A thin straight thing out of the fist along the forearm (a toothbrush, a pen)."""
    def fn(fr, cam_, J, s, hd, fd, k):
        h = J["h"]
        d = rig._screen_dir(cam_, J["wr_" + s], fd)
        a = (hd[0] - d[0] * 0.03 * h * k, hd[1] - d[1] * 0.03 * h * k)
        b = (hd[0] + d[0] * length * h * k, hd[1] + d[1] * length * h * k)
        fr.c.drawLine(a[0], a[1], b[0], b[1], paint("#101014", stroke=width * h * k + 2.4))
        fr.c.drawLine(a[0], a[1], b[0], b[1], paint(colr, stroke=width * h * k))
        if tip:
            n = (-d[1], d[0])
            q = (b[0] - d[0] * 0.02 * h * k, b[1] - d[1] * 0.02 * h * k)
            fr.c.drawLine(q[0], q[1], q[0] + n[0] * 0.018 * h * k, q[1] + n[1] * 0.018 * h * k, paint(tip, stroke=0.016 * h * k))
    return fn


BRUSH = stick("#39b6ff", 0.11, 0.012, tip="#f4f4f4")
PEN = stick("#2b5cff", 0.085, 0.008)


def brushing(p, T, on, look="kai", side="R"):
    """Toothbrush at the mouth, the forearm scrubbing; on 0..1 = scrubbing, 0 = arm lowered."""
    J = rig.solve(look, dict(p, ik_R=None) if False else p)
    hc, Bh = J["head"], J["Bh"]
    at = Bh.w(hc, 0.05 * math.sin(T * 22) * on, -0.55 * J["R"], 1.25 * J["R"])
    rest = rig.Basis.yaw(p["yaw"]).w((p["x"], 0, p["z"]), -0.16 * J["h"] * (1 if side == "R" else -1), 0.62 * J["h"], 0.18)
    p["ik_" + side] = lerp(rest, at, on)
    return p


# ---- sets --------------------------------------------------------------------------------------------------------
class Room:
    """A box room: x0..x1, z0..z1, height hgt (walls, floor, ceiling), plus furniture boxes and wall quads.
    skip: faces not to draw ("z1" = the wall at z = z1, ...), for the pass that looks out through a mirror."""

    def __init__(self, x0, x1, z0, z1, hgt, wall, floor, ceil="#d9d4c8", tiles=None, ftiles=None, base="#2a2420"):
        self.x0, self.x1, self.z0, self.z1, self.h = x0, x1, z0, z1, hgt
        self.wall, self.floor, self.ceil, self.tiles, self.ftiles, self.base = wall, floor, ceil, tiles, ftiles, base
        self.boxes, self.quads = [], []

    def draw(self, fr, cm, skip=(), light=None):
        x0, x1, z0, z1, h = self.x0, self.x1, self.z0, self.z1, self.h
        c = fr.c
        faces = {"floor": [(x0, 0, z0), (x1, 0, z0), (x1, 0, z1), (x0, 0, z1)],
                 "ceil": [(x0, h, z0), (x1, h, z0), (x1, h, z1), (x0, h, z1)],
                 "z1": [(x0, 0, z1), (x1, 0, z1), (x1, h, z1), (x0, h, z1)],
                 "z0": [(x0, 0, z0), (x1, 0, z0), (x1, h, z0), (x0, h, z0)],
                 "x0": [(x0, 0, z0), (x0, 0, z1), (x0, h, z1), (x0, h, z0)],
                 "x1": [(x1, 0, z0), (x1, 0, z1), (x1, h, z1), (x1, h, z0)]}
        shade_k = dict(floor=0.0, ceil=-0.1, z1=0.0, z0=-0.05, x0=-0.14, x1=-0.1)
        for nm in ("ceil", "floor", "z1", "z0", "x0", "x1"):
            if nm in skip:
                continue
            colr = self.floor if nm == "floor" else self.ceil if nm == "ceil" else self.wall
            fr.poly(cm, faces[nm], colr=shade(colr, shade_k[nm]))
            if nm == "floor" and self.ftiles:
                for i in np.arange(x0, x1 + 0.01, self.ftiles):
                    fr.poly(cm, [(i - 0.006, 0.001, z0), (i + 0.006, 0.001, z0), (i + 0.006, 0.001, z1), (i - 0.006, 0.001, z1)], colr=shade(self.floor, -0.25))
                for j in np.arange(z0, z1 + 0.01, self.ftiles):
                    fr.poly(cm, [(x0, 0.001, j - 0.006), (x1, 0.001, j - 0.006), (x1, 0.001, j + 0.006), (x0, 0.001, j + 0.006)], colr=shade(self.floor, -0.25))
            if nm not in ("floor", "ceil") and self.tiles:
                ty = self.tiles
                for y in np.arange(0, min(h, 1.3) + 0.01, ty):
                    q = [(x0, y, z1 - 0.001), (x1, y, z1 - 0.001), (x1, y + 0.01, z1 - 0.001), (x0, y + 0.01, z1 - 0.001)] if nm == "z1" else \
                        [(x0, y, z0 + 0.001), (x1, y, z0 + 0.001), (x1, y + 0.01, z0 + 0.001), (x0, y + 0.01, z0 + 0.001)] if nm == "z0" else \
                        [(x0 + 0.001, y, z0), (x0 + 0.001, y, z1), (x0 + 0.001, y + 0.01, z1), (x0 + 0.001, y + 0.01, z0)] if nm == "x0" else \
                        [(x1 - 0.001, y, z0), (x1 - 0.001, y, z1), (x1 - 0.001, y + 0.01, z1), (x1 - 0.001, y + 0.01, z0)]
                    fr.poly(cm, q, colr=shade(self.wall, -0.2))
            if nm in ("x0", "x1", "z0", "z1"):                    # skirting board
                q = [(p[0], min(p[1], 0.09), p[2]) for p in faces[nm]]
                fr.poly(cm, q, colr=self.base)
        for wall, q, colr, ol in self.quads:
            if wall in skip:
                continue
            fr.poly(cm, q, colr=colr, outline=ol, line=2.0)

    def items(self, cm, skip=(), light=None):
        out = []
        for nm, xs, ys, zs, colr in self.boxes:
            if nm in skip:
                continue
            ctr = ((xs[0] + xs[1]) / 2, (ys[0] + ys[1]) / 2, (zs[0] + zs[1]) / 2)
            out.append((cm.view(ctr)[2], lambda fr, xs=xs, ys=ys, zs=zs, colr=colr: fr.box(cm, xs, ys, zs, colr, light=light, line=1.6)))
        return out


def draw_scene(fr, cm, room, cast, extra=(), skip=(), light=(0, 2.4, 0), grade=None):
    """Room, then furniture, props and people back to front. cast: [(look, pose, held)]; extra: [(depth_point, fn)]."""
    room.draw(fr, cm, skip, light)
    items = room.items(cm, skip, light)
    for pt, fn in extra:
        items.append((cm.view(pt)[2], lambda fr, fn=fn: fn(fr, cm)))
    outs = {}
    for look, pose, held in cast:
        J = rig.solve(look, pose)
        dz = cm.view(J["pelvis"])[2]
        if dz < 0.2:
            continue

        def fn(fr, look=look, pose=pose, held=held):
            o = rig.draw(fr, cm, look, pose, light=light, held=held)
            outs[look] = o
        items.append((dz, fn))
    for _, fn in sorted(items, key=lambda q: -q[0]):
        fn(fr)
    return outs


def mirror(fr, cm, plane, quad, draw_fn, alpha=1.0, tint="#b9c8d6", frame=None, glare=0.12):
    """A reflective quad on the plane z = plane (or ("y", y0) for a puddle). draw_fn(fr, cam_r) draws the
    reflected world from the reflected camera; the result is flipped and clipped to the glass."""
    pts = [cm.proj(p) for p in quad]
    if min(p[2] for p in pts) < 0.05:
        return
    path = rig.smooth([p[:2] for p in pts], k=0.0) if False else None
    path = skia.Path()
    path.addPoly([skia.Point(p[0], p[1]) for p in pts], True)
    c = fr.c
    c.save()
    c.clipPath(path, skia.ClipOp.kIntersect, True)
    if alpha < 1:
        c.saveLayerAlpha(None, int(255 * alpha))
    if isinstance(plane, tuple):                                   # a puddle: the ground is the mirror
        cr = Camera((cm.pos[0], 2 * plane[1] - cm.pos[1], cm.pos[2]), math.degrees(cm.yaw), cm.f, cm.horizon)
        c.translate(0, 2 * H * cm.horizon)
        c.scale(1, -1)
    else:
        cr = Camera((cm.pos[0], cm.pos[1], 2 * plane - cm.pos[2]), 180.0 - math.degrees(cm.yaw), cm.f, cm.horizon)
        c.translate(W, 0)
        c.scale(-1, 1)
    full(c, "#20242c")
    draw_fn(fr, cr)
    c.restore() if alpha >= 1 else (c.restore(), c.restore())
    if alpha >= 1:
        pass
    c.save()
    c.clipPath(path, skia.ClipOp.kIntersect, True)
    b = path.getBounds()
    c.drawPath(path, paint(tint, a=0.10))
    if glare:
        g = skia.Path()
        g.moveTo(b.left() + b.width() * 0.15, b.bottom())
        g.lineTo(b.left() + b.width() * 0.45, b.bottom())
        g.lineTo(b.left() + b.width() * 0.85, b.top())
        g.lineTo(b.left() + b.width() * 0.6, b.top())
        g.close()
        c.drawPath(g, paint("#ffffff", a=glare, blur=8))
    c.restore()
    if frame:
        c.drawPath(path, paint(frame, stroke=10))
        c.drawPath(path, paint("#000000", a=0.6, stroke=2))
    if alpha < 1 and False:
        pass


def _mirror_restore_fix():
    pass


# the bathroom: mirror over the sink on the wall z = 1.2
BATH = Room(-1.3, 1.3, -1.8, 1.2, 2.5, "#cfe1e6", "#e9ecef", tiles=0.2, ftiles=0.3)
BATH.boxes += [("sink", (-0.45, 0.45), (0.0, 0.84), (0.75, 1.2), "#f4f5f7"), ("shelf", (-0.5, 0.5), (1.92, 1.96), (1.1, 1.2), "#b0b8c0")]
BATH.quads += [("z1", [(-0.55, 0.98, 1.19), (0.55, 0.98, 1.19), (0.55, 1.88, 1.19), (-0.55, 1.88, 1.19)], "#9aa7b0", "#5d6a73")]
BATH_GLASS = [(-0.5, 1.02, 1.185), (0.5, 1.02, 1.185), (0.5, 1.84, 1.185), (-0.5, 1.84, 1.185)]
BATH_LIGHT = (0.0, 2.3, 0.6)

# the kitchen: table in the middle, fridge at the back
KITCH = Room(-2.4, 2.4, -2.0, 2.4, 2.6, "#e9d8b8", "#b98a5a", ftiles=0.45)
KITCH.boxes += [("table", (-0.7, 0.7), (0.70, 0.76), (0.2, 1.1), "#8a5a36"), ("tleg", (-0.65, -0.58), (0, 0.7), (0.25, 0.32), "#6a4228"),
                ("tleg2", (0.58, 0.65), (0, 0.7), (0.25, 0.32), "#6a4228"), ("fridge", (1.4, 2.2), (0, 1.9), (1.75, 2.38), "#eef1f4"),
                ("counter", (-2.38, 0.6), (0, 0.9), (1.85, 2.38), "#d2c3a6"), ("ctop", (-2.38, 0.6), (0.9, 0.95), (1.8, 2.38), "#5a4a3c")]

# the hallway: long along z, Grandma's door at the end (z = 6), a window on the left wall, a wall mirror on the right
HALL = Room(-0.85, 0.85, -1.5, 6.0, 2.5, "#8e9a86", "#6b4c34", ftiles=None)
HALL.quads += [("z1", [(-0.45, 0, 5.99), (0.45, 0, 5.99), (0.45, 2.05, 5.99), (-0.45, 2.05, 5.99)], "#5a3e2a", "#2a1c12"),
               ("x1", [(0.849, 0.9, 1.6), (0.849, 0.9, 2.4), (0.849, 1.8, 2.4), (0.849, 1.8, 1.6)], "#a8b4bc", "#3a3026")]
HALL_WIN = [(-0.849, 0.95, 2.6), (-0.849, 0.95, 3.6), (-0.849, 2.0, 3.6), (-0.849, 2.0, 2.6)]

# Grandma's room: vanity mirror on the wall z = 2.6, her chair in front of it, the door at z = -2
GROOM = Room(-2.0, 2.0, -2.2, 2.6, 2.5, "#7a5a6e", "#5a3e30", ceil="#cbbfae")
GROOM.boxes += [("vanity", (-0.75, 0.75), (0.0, 0.76), (2.15, 2.6), "#6b3f2a"), ("vtop", (-0.8, 0.8), (0.76, 0.8), (2.1, 2.6), "#4a2a1c"),
                ("bed", (-1.95, -0.6), (0.0, 0.55), (-1.4, 0.8), "#c9b8d8"), ("lamp", (1.2, 1.4), (0.0, 1.3), (2.2, 2.4), "#3a2a20")]
GROOM.quads += [("z1", [(-0.72, 0.84, 2.59), (0.72, 0.84, 2.59), (0.72, 2.2, 2.59), (-0.72, 2.2, 2.59)], "#c9a24a", "#3a2a1a")]
GROOM_GLASS = [(-0.62, 0.92, 2.585), (0.62, 0.92, 2.585), (0.62, 2.12, 2.585), (-0.62, 2.12, 2.585)]
GROOM_LIGHT = (1.3, 1.6, 2.0)


def chair(x, z, yaw, colr="#8a3a4a"):
    def fn(fr, cm):
        f = fwd(yaw)
        bx = (x - f[0] * 0.24, z - f[2] * 0.24)
        fr.box(cm, (x - 0.25, x + 0.25), (0.42, 0.48), (z - 0.25, z + 0.25), colr, line=1.4)
        for sx in (-0.21, 0.21):
            for sz in (-0.21, 0.21):
                fr.box(cm, (x + sx - 0.025, x + sx + 0.025), (0, 0.42), (z + sz - 0.025, z + sz + 0.025), "#3a2a20", line=1.0)
        if abs(f[2]) > 0.5:
            fr.box(cm, (x - 0.25, x + 0.25), (0.48, 1.05), (bx[1] - 0.03, bx[1] + 0.03), colr, line=1.4)
        else:
            fr.box(cm, (bx[0] - 0.03, bx[0] + 0.03), (0.48, 1.05), (z - 0.25, z + 0.25), colr, line=1.4)
    return fn


# ================================================================================================== the shots
def bath_shot(fr, T, t0, t1):
    """HOOK: over Kai's shoulder into the bathroom mirror. He stops brushing; his reflection doesn't."""
    u = T - t0
    cm = camk([(0, (0.62, 1.5, -1.25), (-0.05, 1.38, 1.2), 1200, 0.46), (4.3, (0.5, 1.5, -0.8), (-0.08, 1.42, 1.2), 1400, 0.46)], u)
    kai = person("kai", -0.22, 0.42, 180.0, T, aL=(4.0, 8.0, 12.0))
    kai = brushing(kai, u, 1.0 - sm((u - 1.3) / 0.35))
    on_r = 1.0 - sm((u - 3.0) / 0.8)                               # the reflection keeps scrubbing, slower
    ref = person("kai", -0.22, 0.42, 180.0, T, aL=(4.0, 8.0, 12.0), lid=1.0, head_pitch=-4 * sm((u - 2.0) / 0.6), smile=0.12 * sm((u - 3.3) / 0.5))
    ref = brushing(ref, u * (1.0 - 0.45 * sm((u - 1.3) / 0.5)), on_r)
    kai["head_pitch"] = -6 * sm((u - 1.5) / 0.4)
    cast_r = [("kai", ref, {"R": BRUSH})]

    def refl(fr_, cr):
        draw_scene(fr_, cr, BATH, cast_r, skip=("z1", "shelf", "sink"), light=BATH_LIGHT)
    draw_scene(fr, cm, BATH, [], light=BATH_LIGHT)
    mirror(fr, cm, 1.185, BATH_GLASS, refl, frame="#c8ced3")
    rig.draw(fr, cm, "kai", kai, light=BATH_LIGHT, held={"R": BRUSH})
    fr.glow(W / 2, 200, 500, "#fff6e0", a=0.12)
    vignette(fr.c, 0.45)


def face_shot(fr, T, t0, t1):
    """'It isn't on your side anymore': close on the mirror. Kai is still; his reflection slowly smiles and tilts."""
    u = T - t0
    cm = camk([(0, (0.42, 1.55, 0.05), (-0.05, 1.48, 1.2), 1700, 0.42), (2.3, (0.36, 1.55, 0.22), (-0.05, 1.5, 1.2), 1950, 0.42)], u)
    kai = person("kai", 0.08, 0.5, 180.0, T, aL=(4.0, 8.0, 12.0), aR=(4.0, 8.0, 12.0))
    ref = dict(kai, smile=0.55 * sm((u - 0.6) / 0.9), head_roll=-9 * sm((u - 0.9) / 0.8), lid=0.82, brow=0.25 * sm((u - 0.6) / 0.5), mouth=0.0)

    def refl(fr_, cr):
        draw_scene(fr_, cr, BATH, [("kai", ref, None)], skip=("z1", "shelf", "sink"), light=BATH_LIGHT)
    draw_scene(fr, cm, BATH, [], light=BATH_LIGHT)
    mirror(fr, cm, 1.185, BATH_GLASS, refl, frame="#c8ced3")
    rig.draw(fr, cm, "kai", kai, light=BATH_LIGHT)
    vignette(fr.c, 0.6)


def globe_shot(fr, T, t0, t1):
    """'By Friday they'd stopped trying to catch up': red dots spread over a turning globe, the delay counter."""
    u = T - t0
    c = fr.c
    grad_bg(c, ["#03050d", "#0a1230", "#03050d"])
    rng = np.random.default_rng(3)
    for _ in range(140):
        c.drawCircle(float(rng.uniform(0, W)), float(rng.uniform(0, H)), float(rng.uniform(0.8, 2.4)), paint("#ffffff", a=float(rng.uniform(0.2, 0.7))))
    cx, cy, R = W / 2, H * 0.47, 420 * (1 + 0.06 * u)
    fr.glow(cx, cy, R * 1.25, "#3a78ff", a=0.35)
    c.drawCircle(cx, cy, R, paint(shader=rad((cx - R * 0.35, cy - R * 0.35), R * 1.5, [argb("#2f6fb3"), argb("#14345e"), argb("#060d1c")], [0, 0.6, 1])))
    c.save()
    gp = skia.Path()
    gp.addCircle(cx, cy, R)
    c.clipPath(gp, skia.ClipOp.kIntersect, True)
    rot = u * 0.35
    land = np.random.default_rng(11)
    blobs = [(land.uniform(-math.pi, math.pi), land.uniform(-1.0, 1.0), land.uniform(0.12, 0.32)) for _ in range(22)]
    for lon, lat, r in blobs:                                      # continents: blobs on the sphere
        l = lon + rot
        if math.cos(l) < -0.1:
            continue
        x, y = cx + R * math.sin(l) * math.cos(lat), cy - R * math.sin(lat)
        c.drawOval(skia.Rect(x - r * R * math.cos(l) * 0.9, y - r * R * 0.6, x + r * R * math.cos(l) * 0.9, y + r * R * 0.6), paint("#3f9a5a", a=0.9))
    for i in range(1, 6):                                          # latitude lines
        y = cy - R * math.cos(math.pi * i / 6)
        w = R * math.sin(math.pi * i / 6)
        c.drawOval(skia.Rect(cx - w, y - w * 0.08, cx + w, y + w * 0.08), paint("#9fd8ff", a=0.12, stroke=2))
    dots = np.random.default_rng(5)
    n = int(18 + 160 * sm(u / 1.5))
    for i in range(n):
        lon, lat = dots.uniform(-math.pi, math.pi), dots.uniform(-1.1, 1.1)
        l = lon + rot
        if math.cos(l) < 0:
            continue
        x, y = cx + R * math.sin(l) * math.cos(lat), cy - R * math.sin(lat)
        pr = 0.5 + 0.5 * math.sin(T * 6 + i)
        fr.glow(x, y, 26, RED, a=0.5 * pr)
        c.drawCircle(x, y, 7, paint(RED))
    c.restore()
    c.drawCircle(cx, cy, R, paint(shader=rad((cx + R * 0.3, cy + R * 0.3), R * 1.2, [argb("#000000", 0), argb("#000000", 0.55)], [0.5, 1])))
    pill(c, W / 2 - 300, 330, W / 2 + 300, 450, "#000000", 0.75)
    d = 3.0 + 0.1 * int(max(0.0, u - 0.8) * 10)
    text(c, "%.1f s DELAY" % d, W / 2, 415, 84, RED)
    text(c, "WORLDWIDE", W / 2, 520, 46, "#ffffff", stroke=8)


def taped_shot(fr, T, t0, t1):
    """'Mirrors': a hall mirror papered over with newspaper and tape, a hand slapping on the last strip."""
    u = T - t0
    cm = camk([(0, (-0.1, 1.4, 0.6), (0.85, 1.35, 2.0), 1500, 0.46), (0.6, (-0.05, 1.4, 0.8), (0.85, 1.35, 2.0), 1650, 0.46)], u)
    HALL.draw(fr, cm)
    c = fr.c
    for i, (z0, z1, y0, y1, rot) in enumerate(((1.58, 2.1, 1.25, 1.85, 0), (1.95, 2.45, 1.3, 1.82, 0), (1.55, 2.42, 0.86, 1.36, 0))):
        if i == 2 and u < 0.15:
            continue
        q = [(0.846, y0, z0), (0.846, y0, z1), (0.846, y1, z1), (0.846, y1, z0)]
        p = fr.poly(cm, q, colr="#e8e2d2", outline="#9a9384", line=1.5)
        if p is not None:
            b = p.getBounds()
            for k in range(7):
                yy = b.top() + b.height() * (0.12 + k * 0.12)
                c.drawLine(b.left() + b.width() * 0.1, yy, b.left() + b.width() * (0.5 if k % 3 == 0 else 0.88), yy, paint("#5a5650", stroke=6 if k == 0 else 3))
    for z0, z1, y in ((1.5, 2.5, 1.33), (1.5, 2.5, 1.84), (1.5, 2.5, 0.88)):
        fr.poly(cm, [(0.845, y - 0.03, z0), (0.845, y - 0.03, z1), (0.845, y + 0.03, z1), (0.845, y + 0.03, z0)], colr="#d8c48a", a=0.85)
    vignette(c, 0.5)


def window_shot(fr, T, t0, t1):
    """'Windows': a woman walks past a dark shop window; her reflection stands still, watching."""
    u = T - t0
    cm = cam((-0.4, 1.4, -1.9), (0.6, 1.2, 1.0), 1250, 0.46)
    c = fr.c
    grad_bg(c, ["#0b0f1c", "#141b2e"])
    fr.poly(cm, [(-6, 0, -6), (6, 0, -6), (6, 0, 2), (-6, 0, 2)], colr="#2c2f38")
    fr.poly(cm, [(-6, 0, 1.0), (6, 0, 1.0), (6, 3.2, 1.0), (-6, 3.2, 1.0)], colr="#2a2430")
    glass = [(-2.4, 0.4, 0.99), (2.6, 0.4, 0.99), (2.6, 2.7, 0.99), (-2.4, 2.7, 0.99)]
    fr.poly(cm, glass, colr="#0d1220")
    for x in (-1.2, 0.0, 1.2):                                     # mannequins in the dark shop
        fr.box(cm, (x - 0.1, x + 0.1), (0.4, 1.6), (1.6, 1.7), "#3a3f55", line=1.0)
    walker = person("mom", 1.5 - u * 1.4, -0.1, -90.0, T, aR=(-14.0 * math.sin(u * 9), 6.0, 10.0), aL=(14.0 * math.sin(u * 9), 6.0, 10.0))
    walker = dict(walker, bob=0.02 * abs(math.sin(u * 9)))
    frozen = person("mom", 1.5, -0.1, -90.0, T, head_yaw=-70.0, lid=1.0, smile=0.2)
    look = "anchor"

    def refl(fr_, cr):
        draw_scene(fr_, cr, Room(-6, 6, -6, 0.99, 3.2, "#2a2430", "#2c2f38"), [(look, frozen, None)], skip=("z1",), light=(0, 3, -1))
    mirror(fr, cm, 0.99, glass, refl, alpha=0.55, glare=0.06)
    fr.glow(W * 0.8, H * 0.18, 300, "#ffd27a", a=0.3)
    rig.draw(fr, cm, look, walker, light=(0, 3, -1))
    night(c, "#a8b4dc")
    vignette(c, 0.4)


def puddle_shot(fr, T, t0, t1):
    """'Puddles': a man looks ahead; his reflection in the puddle looks UP at him."""
    u = T - t0
    cm = cam((0.0, 1.05, 1.3), (0.0, 0.0, 4.0), 1150, 0.30)
    c = fr.c
    grad_bg(c, ["#1b2236", "#2c2f38"])
    fr.poly(cm, [(-6, 0, 0.2), (6, 0, 0.2), (6, 0, 20), (-6, 0, 20)], colr="#3a3d45")
    fr.poly(cm, [(-6, 0, 9), (6, 0, 9), (6, 4, 9), (-6, 4, 9)], colr="#262a36")
    man = person("dad", 0.0, 4.0, 0.0, T, head_pitch=6.0, aR=(4, 7, 10), aL=(4, 7, 10))
    ref = dict(man, head_pitch=-48.0 * sm((u - 0.1) / 0.25), smile=0.4, lid=1.0)
    pts = [(math.cos(a) * 1.0, 0.0, 3.0 + math.sin(a) * 0.95) for a in np.linspace(0, 2 * math.pi, 28, endpoint=False)]

    def refl(fr_, cr):
        grad_bg(fr_.c, ["#2c2f38", "#1b2236"])
        rig.draw(fr_, cr, "dad", ref, light=(1, 3, 2), shadow=False)
    mirror(fr, cm, ("y", 0.0), pts, refl, alpha=0.95, glare=0.0, tint="#6a7fa8")
    rig.draw(fr, cm, "dad", man, light=(1, 3, 2))
    for i in range(3):                                             # ripples
        r = ((u * 0.9 + i * 0.33) % 1.0)
        p = cm.proj((0.3, 0.0, 2.9))
        c.drawOval(skia.Rect(p[0] - 260 * r, p[1] - 40 * r, p[0] + 260 * r, p[1] + 40 * r), paint("#ffffff", a=0.25 * (1 - r), stroke=3))
    night(c, "#a0acd8")
    vignette(c, 0.45)


def phone_face(fr, T, delay, look="kai", lit=0.0, phone_t=None, smirk=0.0):
    """A phone filling the frame, its black glass holding a face reflection; the face looks round at T - delay."""
    c = fr.c
    grad_bg(c, ["#10131c", "#05060a"])
    x0, y0, x1, y1 = 170, 230, W - 170, H - 260
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x0 - 26, y0 - 26, x1 + 26, y1 + 26), 110, 110), paint("#23262e"))
    scr = skia.Path()
    scr.addRRect(skia.RRect.MakeRectXY(skia.Rect(x0, y0, x1, y1), 86, 86))
    c.drawPath(scr, paint("#020306"))
    if lit > 0:
        c.save()
        c.clipPath(scr, skia.ClipOp.kIntersect, True)
        c.drawRect(skia.Rect(x0, y0, x1, y1), paint(shader=lin((x0, y0), (x1, y1), [argb("#9fd0ff"), argb("#3f7fe0")]), a=lit))
        text(c, "3:07", W / 2, y0 + 360, 190, "#ffffff", a=lit)
        c.restore()
    c.save()
    c.clipPath(scr, skia.ClipOp.kIntersect, True)
    c.saveLayerAlpha(None, int(255 * 0.42 * (1 - lit)))
    c.translate(W, 0)
    c.scale(-1, 1)
    tt = T - delay
    cm = Camera((0, 1.42, 0), 0.0, 3100, 0.5)
    p = person(look, 0.0, 1.0, 0.0, tt, head_yaw=25 * sm(math.sin(tt * 1.3) * 0.5 + 0.5) - 12, lid=1.0, smile=smirk)
    rig.draw(fr, cm, look, p, light=(0, 2, -1), shadow=False)
    c.restore()
    c.drawRect(skia.Rect(x0, y0, x1, y1), paint(shader=lin((x0, y0), (x1, y1), [argb("#ffffff", 0.10), argb("#ffffff", 0.0), argb("#ffffff", 0.05)], [0, 0.5, 1])))
    c.restore()
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect(W / 2 - 90, y0 + 22, W / 2 + 90, y0 + 58), 18, 18), paint("#000000"))


def phone_shot(fr, T, t0, t1):
    u = T - t0
    phone_face(fr, T, 1.0, lit=1.0 - sm((u - 0.35) / 0.12), smirk=0.25 * sm((u - 0.8) / 0.4))
    vignette(fr.c, 0.4)


def fridge_shot(fr, T, t0, t1):
    """Dad's photo on the fridge; at 'shaved without a mirror' the band-aids pop on. Then the clippings."""
    u, c = T - t0, fr.c
    tb = b0("blender") - t0
    z = 1.0 + 0.25 * sm(u / tb) - 0.35 * sm((T - b0("blender") - 1.8) / 0.6)
    grad_bg(c, ["#e9edf0", "#d5dbe0"])
    c.save()
    c.translate(W / 2, H * 0.46)
    c.scale(z, z)
    c.translate(-W / 2, -H * 0.46)
    c.drawRect(skia.Rect(W / 2 - 3, -200, W / 2 + 3, H + 200), paint("#b9c0c7"))
    rng = np.random.default_rng(2)
    clip_a = sm((T - b0("blender") - 1.6) / 0.5)
    heads = ["MIRRORS LIE", "DO NOT LOOK", "3 SECONDS?", "COVER THEM", "IT'S REAL", "WATCH THE PUDDLES"]
    for i in range(12):                                            # the clippings (he believes everything now)
        if clip_a <= 0:
            break
        x, y, r = rng.uniform(40, W - 300), rng.uniform(60, H - 420), rng.uniform(-12, 12)
        if abs(x - W / 2 + 130) < 330 and abs(y - H * 0.42) < 420:
            continue
        c.save()
        c.translate(x + 130, y + 90)
        c.rotate(r)
        c.drawRect(skia.Rect(-130, -90, 130, 90), paint("#efe9da", a=clip_a))
        text(c, heads[i % len(heads)], 0, -40, 30, "#1a1a1a", a=clip_a)
        for k in range(4):
            c.drawLine(-105, -5 + k * 22, 105 - (k % 2) * 40, -5 + k * 22, paint("#6a6a6a", a=clip_a, stroke=4))
        c.drawCircle(0, -82, 12, paint(RED, a=clip_a))
        c.restore()
    px, py, pw, ph = W / 2 - 290, H * 0.42 - 380, 580, 700          # the polaroid
    c.save()
    c.translate(W / 2, H * 0.42)
    c.rotate(-4)
    c.translate(-W / 2, -H * 0.42)
    c.drawRect(skia.Rect(px - 6, py - 6, px + pw + 6, py + ph + 6), paint("#000000", a=0.25, blur=14))
    c.drawRect(skia.Rect(px, py, px + pw, py + ph), paint("#fbfaf6"))
    ph_ = skia.Rect(px + 36, py + 36, px + pw - 36, py + ph - 150)
    c.save()
    c.clipRect(ph_)
    c.drawRect(ph_, paint(shader=lin((0, ph_.top()), (0, ph_.bottom()), [argb("#8fb7d9"), argb("#d8e6c4")])))
    cm = Camera((0, 1.62, 0), 0.0, 2600, 0.5)
    c.translate(0, H * 0.42 - H * 0.5 - 60)
    pz = person("dad", 0.0, 1.25, 0.0, T, smile=0.55, lid=1.0, brow=0.2, mouth=0.18)
    o = rig.draw(fr, cm, "dad", pz, light=(0.5, 2.5, -1), shadow=False)
    shave = b0("dad") + 1.15
    hx, hy = o["head"][:2]
    hr = o["head_r"]
    for i, (dx, dy, rr) in enumerate(((-0.45, 0.25, 35), (0.5, 0.1, -25), (0.1, 0.7, 10), (-0.2, -0.25, -40), (0.55, 0.6, 50), (-0.6, 0.65, -15), (0.0, 0.35, 80))):
        a = sm((T - shave - i * 0.12) / 0.08)
        if a <= 0:
            continue
        c.save()
        c.translate(hx + dx * hr, hy + dy * hr)
        c.rotate(rr)
        c.scale(0.6 + 0.4 * a, 0.6 + 0.4 * a)
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect(-0.42 * hr, -0.12 * hr, 0.42 * hr, 0.12 * hr), 0.1 * hr, 0.1 * hr), paint("#e8b98f"))
        c.drawRect(skia.Rect(-0.12 * hr, -0.1 * hr, 0.12 * hr, 0.1 * hr), paint("#f4dcc2"))
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect(-0.42 * hr, -0.12 * hr, 0.42 * hr, 0.12 * hr), 0.1 * hr, 0.1 * hr), paint("#9a6a48", stroke=2))
        c.restore()
    c.restore()
    text(c, "DAD", W / 2, py + ph - 60, 64, "#2a2a2a", bold=False)
    c.restore()
    for mx, my in ((W / 2 - 210, py + 6), (W / 2 + 190, py + 30)):
        c.drawCircle(mx, my, 30, paint(RED))
        c.drawCircle(mx - 8, my - 8, 9, paint("#ffffff", a=0.5))
    c.restore()
    vignette(c, 0.35)


def news_shot(fr, T, t0, t1, close=False):
    """The news: the anchor at her desk; where the studio monitor should be there's a black bar."""
    u, c = T - t0, fr.c
    grad_bg(c, ["#0c1d3f", "#1d3b74", "#0c1d3f"])
    for i in range(12):
        x = 40 + i * 92
        c.drawRect(skia.Rect(x, 0, x + 40, H), paint("#ffffff", a=0.025))
    cm = cam((0.1, 1.45, -1.2 if not close else -0.6), (0.1, 1.32, 1.0), 1500 if not close else 1650, 0.40)
    mon = [(-1.5, 1.2, 1.6), (-0.3, 1.2, 1.6), (-0.3, 2.3, 1.6), (-1.5, 2.3, 1.6)]
    fr.poly(cm, [(p[0] - 0.04, p[1] - 0.04, 1.61) if i in (0, 3) else (p[0] + 0.04, p[1] + (0.04 if i == 2 else -0.04), 1.61) for i, p in enumerate(mon)], colr="#30343c")
    fr.poly(cm, mon, colr="#000000")                              # the black bar: nothing will show in it
    a = cm.proj((-0.9, 1.75, 1.6))
    text(c, "NO SIGNAL", a[0], a[1] + 14, 40, "#ffffff", a=0.25 + 0.2 * math.sin(T * 9))
    anchor = person("anchor", 0.25, 0.85, 0.0, T, spk="ANCHOR", aR=(24.0, 10.0, 70.0), aL=(24.0, 10.0, 70.0), smile=-0.05,
                    head_yaw=-6 * math.sin(T * 0.8), brow=0.25)
    rig.draw(fr, cm, "anchor", anchor, light=(0.5, 2.5, -1))
    fr.box(cm, (-1.2, 1.4), (0.0, 0.95), (0.35, 0.6), "#e9eef5", line=2.0)
    fr.box(cm, (-1.25, 1.45), (0.95, 1.0), (0.3, 0.65), "#2f4f86", line=2.0)
    c.drawRect(skia.Rect(0, H - 330, W, H - 200), paint("#c0161b"))
    c.drawRect(skia.Rect(0, H - 200, W, H - 130), paint("#0b0b10"))
    seq = [(b0("anchor1"), "3 SEC"), (b0("anchor1") + 1.2, "3 SEC"), (b0("anchor1") + 1.9, "5 SEC"), (b0("anchor1") + 2.4, "10 SEC")]
    cur = "3 SEC"
    for t_, s in seq:
        if T >= t_:
            cur = s
    if not close:
        text(c, "REFLECTION DELAY: " + cur, W / 2, H - 245, 58, "#ffffff")
    else:
        text(c, "IF IT MOVES FIRST: DON'T LOOK AWAY", W / 2, H - 245, 48, "#ffffff")
    off = (T * 220) % 2200
    text(c, "COVER MIRRORS · AVOID STILL WATER · KEEP PHONE SCREENS LIT · STAY CALM · COVER MIRRORS", W - off, H - 150, 38, "#ffcc00", center=False)
    pill(c, 50, 130, 230, 210, "#c0161b")
    text(c, "LIVE", 140, 188, 52, "#ffffff")
    for y in range(0, H, 6):                                       # it's on a TV: scanlines
        c.drawRect(skia.Rect(0, y, W, y + 2), paint("#000000", a=0.10))
    vignette(c, 0.5)


def kitchen_shot(fr, T, t0, t1):
    """Kai signs the school form with his RIGHT hand. 'Cool. Normal Tuesday.'"""
    u, c = T - t0, fr.c
    cm = camk([(0, (0.45, 1.2, -0.05), (-0.02, 1.0, 1.3), 1400, 0.42), (1.0, (0.38, 1.2, 0.15), (-0.02, 1.02, 1.3), 1500, 0.42)], u)
    kai = seated("kai", 0.0, 1.45, 0.0, 0.47, -0.32, T, spk="KAI", head_pitch=10 - 12 * sm((u - 0.25) / 0.2), lid=0.82, brow=-0.1)
    J0 = rig.solve("kai", kai)
    sx = J0["sh_R"][0]
    pen_at = (sx * 0.8 + 0.03 * math.sin(T * 17) * (1 - sm((u - 0.3) / 0.1)), 0.79, 0.88)
    kai["ik_R"], kai["ik_L"] = pen_at, (J0["sh_L"][0] * 0.9, 0.79, 0.98)
    draw_scene(fr, cm, KITCH, [("kai", kai, {"R": PEN})], extra=[((0, 0.45, 1.6), chair(0.0, 1.5, 0.0))], light=(0.5, 2.4, 0.4))
    px_ = sx * 0.8
    paper = [(px_ - 0.17, 0.765, 0.7), (px_ + 0.17, 0.765, 0.7), (px_ + 0.17, 0.765, 1.0), (px_ - 0.17, 0.765, 1.0)]
    p = fr.poly(cm, paper, colr="#fbfbf7", outline="#9a9a90", line=1.5)
    J = rig.solve("kai", kai)
    rig.draw(fr, cm, "kai", dict(kai), light=(0.5, 2.4, 0.4), held={"R": PEN}) if False else None
    q = cm.proj((px_, 0.77, 0.74))
    text(c, "PERMISSION SLIP", q[0], q[1] - 30, 26, "#333333")
    hand = cm.proj(J["hand_R"])
    fr.glow(hand[0], hand[1], 90, "#fff2a8", a=0.25)
    vignette(c, 0.45)


def kitchen_overlay(fr, T):
    J = rig.solve("kai", seated("kai", 0.0, 1.45, 0.0, 0.47, -0.32, T))
    return J


def cover_shot(fr, T, t0, t1):
    """'So we covered every mirror in the house': Mom throws a blanket over the hall mirror, Remi with the tape."""
    u, c = T - t0, fr.c
    cm = cam((-0.55, 1.35, 0.1), (0.85, 1.25, 2.2), 1250, 0.46)
    cov = sm((u - 0.2) / 0.7)
    mom = person("mom", 0.35, 2.0, 90.0 + 180.0 - 180.0 + 0.0, T)
    mom = person("mom", 0.4, 2.0, -90.0 + 180.0, T)
    mom["yaw"] = 90.0                                              # facing +x: the mirror
    hy = 1.85 - 0.95 * cov
    mom["ik_R"], mom["ik_L"] = (0.8, hy, 1.7), (0.8, hy, 2.3)
    remi = person("remi", -0.15, 1.3, 120.0, T, aR=(40.0, 10.0, 60.0), head_pitch=-12.0, smile=0.2)
    mir = [(0.849, 0.9, 1.6), (0.849, 0.9, 2.4), (0.849, 1.8, 2.4), (0.849, 1.8, 1.6)]

    def refl(fr_, cr):
        draw_scene(fr_, cr, HALL, [("mom", mom, None), ("remi", remi, None)], skip=("x1",), light=(0, 2.3, 2))
    HALL.draw(fr, cm)

    class _Plane:
        pass
    # the hall mirror is on the x = 0.849 wall: reflect in x by swapping axes via a rotated camera
    mirror_x(fr, cm, 0.849, mir, refl, frame="#5a4a3a")
    blank = [(0.845, 1.88, 1.55), (0.845, 1.88, 2.45), (0.845, 1.88 - 1.02 * cov, 2.45), (0.845, 1.88 - 1.02 * cov, 1.55)]
    if cov > 0.02:
        p = fr.poly(cm, blank, colr="#5d7fb0", outline="#2a3a55", line=2)
        if p is not None:
            b = p.getBounds()
            for k in range(5):
                c.drawLine(b.left() + b.width() * (0.15 + k * 0.17), b.top(), b.left() + b.width() * (0.12 + k * 0.18), b.bottom(), paint("#3e5f8e", stroke=3))
    draw_scene(fr, cm, Room(0, 0, 0, 0, 0, "#000", "#000"), [("mom", mom, None), ("remi", remi, None)], light=(0, 2.3, 2)) if False else None
    for look, pose in (("mom", mom), ("remi", remi)):
        pass
    order = sorted([("mom", mom), ("remi", remi)], key=lambda q: -cm.view((q[1]["x"], 1, q[1]["z"]))[2])
    for look, pose in order:
        rig.draw(fr, cm, look, pose, light=(0, 2.3, 1.0))
    vignette(c, 0.45)


def mirror_x(fr, cm, plane_x, quad, draw_fn, frame=None, alpha=1.0):
    """A mirror on the wall x = plane_x: the reflected camera is mirrored in x (yaw -> -yaw), image flipped."""
    pts = [cm.proj(p) for p in quad]
    if min(p[2] for p in pts) < 0.05:
        return
    path = skia.Path()
    path.addPoly([skia.Point(p[0], p[1]) for p in pts], True)
    c = fr.c
    c.save()
    c.clipPath(path, skia.ClipOp.kIntersect, True)
    if alpha < 1:
        c.saveLayerAlpha(None, int(255 * alpha))
    cr = Camera((2 * plane_x - cm.pos[0], cm.pos[1], cm.pos[2]), -math.degrees(cm.yaw), cm.f, cm.horizon)
    c.translate(W, 0)
    c.scale(-1, 1)
    full(c, "#20242c")
    draw_fn(fr, cr)
    if alpha < 1:
        c.restore()
    c.restore()
    c.save()
    c.clipPath(path, skia.ClipOp.kIntersect, True)
    c.drawPath(path, paint("#b9c8d6", a=0.1))
    c.restore()
    if frame:
        c.drawPath(path, paint(frame, stroke=10))


def door_shot(fr, T, t0, t1, close=None):
    """Grandma blocks her bedroom door, arms crossed; Kai and Remi in the foreground (backs to us)."""
    u, c = T - t0, fr.c
    hall = HALL
    if close is None:
        cm = camk([(0, (0.25, 1.05, 2.4), (0.0, 1.35, 6.0), 1250, 0.4), (4.9, (0.2, 1.1, 3.0), (0.0, 1.4, 6.0), 1350, 0.4)], u)
    elif close == "gma":
        cm = camk([(0, (0.05, 1.25, 4.5), (0.0, 1.42, 6.0), 1550, 0.36), (2.0, (0.05, 1.25, 4.62), (0.0, 1.42, 6.0), 1650, 0.36)], u)
    else:                                                          # remi close-up from Grandma's side
        cm = cam((-0.2, 1.0, 5.1), (-0.42, 0.95, 4.1), 1300, 0.40)
    hall.draw(fr, cm)
    fr.poly(cm, [(-0.45, 0, 5.985), (0.45, 0, 5.985), (0.45, 2.05, 5.985), (-0.45, 2.05, 5.985)], colr="#e8b86a")   # the open door: warm room behind
    gma = person("gma", 0.0, 5.75, 0.0, T, spk="GMA", brow=-0.25, smile=0.15)
    J = rig.solve("gma", gma)
    gma["ik_R"] = J["el_L"] if False else rig.Basis.yaw(0.0).w((0, 0, 5.75), -0.09, 0.98, -0.16)
    gma["ik_L"] = rig.Basis.yaw(0.0).w((0, 0, 5.75), 0.09, 0.95, -0.17)
    if close == "gma" and T >= b0("gma2"):
        gma.update(smile=0.45, lid=0.7, head_roll=6)
    kai = person("kai", 0.5, 3.75, 170.0, T, spk="KAI")
    remi = person("remi", -0.42, 4.1, 190.0, T, spk="REMI", head_pitch=-14.0, aR=(10, 8, 30))
    if close == "remi":
        remi.update(head_pitch=-22.0, smile=0.25, yaw=200.0, brow=0.3)
    cast_ = [("gma", gma, None), ("kai", kai, None), ("remi", remi, None)]
    order = sorted(cast_, key=lambda q: -cm.view((q[1]["x"], 1.0, q[1]["z"]))[2])
    for look, pose, held in order:
        if cm.view((pose["x"], 1.0, pose["z"]))[2] < 0.3:
            continue
        rig.draw(fr, cm, look, pose, light=(0.6, 2.2, 4.8), held=held)
    vignette(c, 0.45)


def vanity_shot(fr, T, t0, t1):
    """'She kept her big mirror uncovered': through her door, the vanity, a glint."""
    u, c = T - t0, fr.c
    cm = camk([(0, (0.5, 1.4, -1.6), (0.0, 1.35, 2.6), 1300, 0.46), (1.4, (0.35, 1.4, -0.6), (0.0, 1.45, 2.6), 1500, 0.46)], u)

    def refl(fr_, cr):
        draw_scene(fr_, cr, GROOM, [], extra=[((0, 0.5, 1.6), chair(0.0, 1.6, 180.0))], skip=("z1", "vanity", "vtop"), light=GROOM_LIGHT)
    draw_scene(fr, cm, GROOM, [], extra=[((0, 0.5, 1.6), chair(0.0, 1.6, 180.0))], light=GROOM_LIGHT)
    mirror(fr, cm, 2.585, GROOM_GLASS, refl, frame="#c9a24a", glare=0.18 + 0.2 * sm((u - 0.6) / 0.3) * (1 - sm((u - 1.0) / 0.3)))
    lp = cm.proj((1.3, 1.35, 2.3))
    fr.glow(lp[0], lp[1], 260, "#ffcf7a", a=0.45)
    vignette(c, 0.55)


def night_hall(fr, T, t0, t1):
    """2 a.m.: Kai in the dark hallway, lit by his phone; the screen goes black."""
    u, c = T - t0, fr.c
    cm = camk([(0, (0.3, 1.35, -0.8), (-0.1, 1.3, 3.0), 1250, 0.45), (1.8, (0.25, 1.4, -0.3), (-0.1, 1.35, 3.0), 1400, 0.45)], u)
    HALL.draw(fr, cm)
    off = sm((T - (b0("night") + 1.0)) / 0.1)
    wp = fr.poly(cm, HALL_WIN, colr="#0b1226")
    kai = person("kai", -0.15, 1.6, 15.0, T, head_pitch=22.0, lid=0.8)
    kai["ik_R"] = rig.Basis.yaw(15.0).w((-0.15, 0, 1.6), 0.02, 1.08, -0.32)
    rig.draw(fr, cm, "kai", kai, light=(0, 1.3, 1.0), held={"R": rig.phone(on=off < 0.5)})
    night(c, "#38446e")
    o = rig.solve("kai", kai)
    hp = cm.proj(o["hand_R"])
    if off < 0.5:
        fr.glow(hp[0], hp[1] - 40, 420, "#5a8cff", a=0.55)
        hd = cm.proj(o["head"])
        fr.glow(hd[0], hd[1], 140, "#9fc0ff", a=0.25)
    if wp is not None:
        rain_on(c, wp, T)
    vignette(c, 0.6)


def rain_on(c, path, T):
    c.save()
    c.clipPath(path, skia.ClipOp.kIntersect, True)
    b = path.getBounds()
    rng = np.random.default_rng(9)
    for i in range(60):
        x = b.left() + rng.uniform(0, b.width())
        y = b.top() + ((rng.uniform(0, 1) + T * rng.uniform(0.3, 0.9)) % 1.0) * b.height()
        c.drawLine(x, y, x - 2, y + 22, paint("#9fb8ff", a=0.35, stroke=2))
    c.restore()


def night_window(fr, T, t0, t1):
    """At the dark window: Kai lowers the phone; his reflection in the glass lowers it a whole second later."""
    u, c = T - t0, fr.c
    cm = camk([(0, (0.55, 1.4, 1.75), (-0.85, 1.35, 3.1), 1350, 0.45), (2.2, (0.45, 1.42, 1.95), (-0.85, 1.38, 3.1), 1500, 0.45)], u)
    HALL.draw(fr, cm)
    down = b0("night") + 2.25 - t0
    kai = person("kai", -0.4, 3.1, -90.0 + 180.0, T, lid=0.85)
    kai["yaw"] = 270.0                                             # facing -x: the window
    ref = dict(kai)
    for p, dn in ((kai, down), (ref, down + 1.0)):
        k = sm((u - dn) / 0.35)
        at = rig.Basis.yaw(270.0).w((-0.4, 0, 3.1), 0.03, 1.08 - 0.42 * k, -0.30 + 0.12 * k)
        p["ik_R"] = at
        p["head_pitch"] = 18.0 - 10 * k
    ref.update(lid=1.0, head_pitch=ref["head_pitch"], smile=0.1)

    def refl(fr_, cr):
        grad_bg(fr_.c, ["#0a1024", "#121a33"])
        rig.draw(fr_, cr, "kai", ref, light=(0, 1.3, 2.5), held={"R": rig.phone(on=False)})
    mirror_x(fr, cm, -0.849, HALL_WIN, refl, frame="#2a2f3a", alpha=0.75)
    wp = skia.Path()
    wp.addPoly([skia.Point(*cm.proj(p)[:2]) for p in HALL_WIN], True)
    rain_on(c, wp, T)
    rig.draw(fr, cm, "kai", kai, light=(0, 1.3, 2.5), held={"R": rig.phone(on=False)})
    night(c, "#4a5684")
    vignette(c, 0.55)


def laugh_shot(fr, T, t0, t1, door_open=0.0):
    """Behind Kai in the dark hallway; at the end, Grandma's door, warm light underneath. Laughing."""
    u, c = T - t0, fr.c
    cm = camk([(0, (0.2, 1.5, 0.2), (0.0, 1.2, 6.0), 1250, 0.46), (2.2, (0.15, 1.5, 1.6), (0.0, 1.25, 6.0), 1400, 0.46)], u)
    HALL.draw(fr, cm)
    fr.poly(cm, [(-0.45, 0, 5.98), (0.45, 0, 5.98), (0.45, 0.04, 5.98), (-0.45, 0.04, 5.98)], colr="#ffcf7a")
    a = cm.proj((0, 0.02, 5.98))
    fr.glow(a[0], a[1], 260, "#ffb34a", a=0.6, sy=0.25)
    kai = person("kai", 0.05, 3.2 + 0.6 * sm(u / 2.0), 180.0, T, aR=(10, 8, 20))
    rig.draw(fr, cm, "kai", kai, light=(0, 0.3, 5.5))
    night(c, "#3a4670")
    fr.glow(a[0], a[1], 200, "#ffb34a", a=0.35, sy=0.3)
    vignette(c, 0.6)


def push_shot(fr, T, t0, t1):
    """'Oh, you were always the pretty one': Kai's hand on the door; it swings open on warm light."""
    u, c = T - t0, fr.c
    cm = cam((-0.4, 1.5, 3.9), (0.1, 1.2, 6.0), 1300, 0.46)
    HALL.draw(fr, cm, skip=("z1",)) if False else HALL.draw(fr, cm)
    op = sm((u - 0.6) / 0.9) * 0.9
    fr.poly(cm, [(-0.45, 0, 5.985), (0.45, 0, 5.985), (0.45, 2.05, 5.985), (-0.45, 2.05, 5.985)], colr="#ffcf7a")
    ang = op * 1.3
    hx, hz = -0.45, 5.985
    ex, ez = hx + 0.9 * math.cos(ang), hz + 0.9 * math.sin(ang)
    fr.poly(cm, [(hx, 0, hz), (ex, 0, ez), (ex, 2.05, ez), (hx, 2.05, hz)], colr="#5a3e2a", outline="#2a1c12", line=2)
    a = cm.proj((0, 1.0, 6.0))
    fr.glow(a[0], a[1], 500 * (0.3 + op), "#ffb34a", a=0.35)
    kai = person("kai", 0.45, 5.4, 195.0, T)
    kai["ik_L"] = (lerp(0.1, ex * 0.6 + hx * 0.4, 1.0), 1.05, lerp(5.95, ez * 0.6 + hz * 0.4, 1.0))
    rig.draw(fr, cm, "kai", kai, light=(0, 1.2, 6.0))
    night(c, "#6874a0")
    fr.glow(a[0], a[1], 400 * (0.2 + op), "#ffb34a", a=0.3)
    vignette(c, 0.6)


def reveal_shot(fr, T, t0, t1):
    """Grandma in her chair, back to us, facing the vanity. In the mirror she is STANDING, looking at Kai, waving.
    At 'talking' both heads turn at the same time; only one of them blinks."""
    u, c = T - t0, fr.c
    cm = camk([(0, (0.35, 1.45, -0.55), (0.12, 1.42, 2.6), 1350, 0.44), (3.6, (0.3, 1.45, 0.0), (0.15, 1.48, 2.6), 1650, 0.44)], u)
    turn = sm((T - (b1("which") - 0.45)) / 0.35)
    gma = seated("gma", 0.0, 1.6, 180.0, 0.48, -0.3, T, spk="GMA", head_yaw=-150 * turn, lid=1.0 if T < b1("which") + 0.9 else blink(T, [b1("which") + 1.0]))
    gma["ik_R"] = rig.Basis.yaw(180.0).w((0, 0, 1.6), -0.14, 0.62, 0.22)
    gma["ik_L"] = rig.Basis.yaw(180.0).w((0, 0, 1.6), 0.14, 0.62, 0.22)
    wave = math.sin(T * 7.5) * (1 - turn)
    ghost = person("gma", 0.25, 1.85, 180.0, T, lid=1.0, smile=0.35 + 0.2 * turn, head_roll=-10 * turn, brow=0.2)
    ghost["ik_R"] = rig.Basis.yaw(180.0).w((0.25, 0, 1.85), 0.25 + 0.08 * wave, 1.62, 0.12)
    kai = person("kai", -0.5, 0.1, 165.0, T, spk="KAI", aL=(30.0, 10.0, 50.0))
    gr = sm(u / 0.3)

    def refl(fr_, cr):
        draw_scene(fr_, cr, GROOM, [("gma", ghost, None), ("kai", kai, None)], extra=[((0, 0.5, 1.6), chair(0.0, 1.6, 180.0))],
                   skip=("z1", "vanity", "vtop"), light=GROOM_LIGHT)
    draw_scene(fr, cm, GROOM, [], extra=[((0, 0.5, 1.6), chair(0.0, 1.6, 180.0))], light=GROOM_LIGHT)
    mirror(fr, cm, 2.585, GROOM_GLASS, refl, frame="#c9a24a")
    rig.draw(fr, cm, "gma", gma, light=GROOM_LIGHT)
    rig.draw(fr, cm, "kai", kai, light=GROOM_LIGHT)
    lp = cm.proj((1.3, 1.35, 2.3))
    fr.glow(lp[0], lp[1], 300, "#ffcf7a", a=0.4)
    vignette(c, 0.55 + 0.2 * gr)


# ---- edit ----------------------------------------------------------------------------------------------------------
SHOTS = [
    ("BATH", 0.0, b0("friday"), bath_shot, {}),
    ("GLOBE", b0("friday"), b0("mirrors"), globe_shot, {}),
    ("TAPED", b0("mirrors"), b0("windows"), taped_shot, {}),
    ("WINDOW", b0("windows"), b0("puddles"), window_shot, {}),
    ("PUDDLE", b0("puddles"), b0("phone"), puddle_shot, {}),
    ("PHONE", b0("phone"), b0("face"), phone_shot, {}),
    ("FACE", b0("face"), b0("dad"), face_shot, {}),
    ("FRIDGE", b0("dad"), b0("anchor1"), fridge_shot, {}),
    ("NEWS", b0("anchor1"), b0("anchor2"), news_shot, {}),
    ("NEWS2", b0("anchor2"), b0("normal"), lambda fr, T, a, b: news_shot(fr, T, a, b, close=True), {}),
    ("KITCHEN", b0("normal"), b0("cover"), kitchen_shot, {}),
    ("COVER", b0("cover"), b0("gma1"), cover_shot, {}),
    ("DOOR", b0("gma1"), b0("gma1") + 2.3, door_shot, {}),
    ("GMA_CU", b0("gma1") + 2.3, b0("remi"), lambda fr, T, a, b: door_shot(fr, T, a, b, close="gma"), {}),
    ("REMI_CU", b0("remi"), b0("gma2"), lambda fr, T, a, b: door_shot(fr, T, a, b, close="remi"), {}),
    ("GMA_CU2", b0("gma2"), b0("vanity"), lambda fr, T, a, b: door_shot(fr, T, a, b, close="gma"), {}),
    ("VANITY", b0("vanity"), b0("night"), vanity_shot, {}),
    ("NIGHT", b0("night"), b0("night") + 1.5, night_hall, {}),
    ("WINDOW2", b0("night") + 1.5, b0("laugh"), night_window, {}),
    ("LAUGH", b0("laugh"), b0("pretty"), laugh_shot, {}),
    ("PUSH", b0("pretty"), b0("which"), push_shot, {}),
    ("REVEAL", b0("which"), TOTAL, reveal_shot, {}),
]


# ---- overlays ------------------------------------------------------------------------------------------------------
def overlay(fr, T, name):
    c = fr.c
    if T < 2.6:                                                    # the series card
        a = min(sm(T / 0.15), sm((2.6 - T) / 0.3))
        text(c, "THREE SECONDS LATE", W / 2, 250, 74, "#ffffff", stroke=14, a=a)
        pill(c, W / 2 - 120, 285, W / 2 + 120, 345, RED, a)
        text(c, "PART 1", W / 2, 332, 40, "#ffffff", a=a)
    if name == "REVEAL" and T > b0("card"):
        a = sm((T - b0("card")) / 0.25)
        full(c, "#000000", a=0.45 * a)
        text(c, "WHICH ONE", W / 2, H * 0.40, 130, "#ffffff", stroke=16, a=a)
        text(c, "IS REAL?", W / 2, H * 0.40 + 140, 130, RED, stroke=16, a=a)
        pill(c, W / 2 - 340, H * 0.40 + 210, W / 2 + 340, H * 0.40 + 300, "#ffffff", a)
        text(c, "FOLLOW FOR PART 2", W / 2, H * 0.40 + 272, 50, "#111111", a=a)


CHUNKS = sorted([c for L in TL["lines"] for c in L["chunks"]], key=lambda c: c["t0"])


def caption(T):
    cur = None
    for c in CHUNKS:
        if c["t0"] <= T + 1e-6:
            cur = c
    return cur["text"] if cur and T < cur["t1"] + 0.15 else None


def draw_caption(fr, s, y=1500, size=86):
    f = skia.Font(TFB, size)
    parts = [(b.strip("[]"), b.startswith("[")) for b in s.upper().replace("[", "|[").replace("]", "]|").split("|") if b]
    x = (W - sum(f.measureText(p) for p, _ in parts)) / 2
    for p, key in parts:
        blob = skia.TextBlob(p, f)
        fr.c.drawTextBlob(blob, x, y, paint("#000000", stroke=size * 0.22))
        fr.c.drawTextBlob(blob, x, y, paint(RED if key else "#FFFFFF"))
        x += f.measureText(p)


def shot_at(T):
    for s in SHOTS:
        if s[1] <= T < s[2]:
            return s
    return SHOTS[-1]


def render(T, scale=1.0):
    name, t0, t1, fn, opt = shot_at(T)
    fr = Frame(scale)
    fn(fr, T, t0, t1)
    if T - t0 < 0.05 and t0 > 0:
        full(fr.c, "#ffffff", a=0.25)
    overlay(fr, T, name)
    s = caption(T)
    if s and not (name == "REVEAL" and T > b0("card")):
        draw_caption(fr, s, *opt.get("cap", (1500, 86)))
    a = fr.array()
    k = min(1.0, max(0.0, (TOTAL - T) / 0.3))
    if k < 1:
        a = (a.astype(np.float32) * k).astype(np.uint8)
    return name, a


def frames_of(a, b):
    return [i / FPS for i in range(int(round(a * FPS)), int(round(b * FPS)))]


def encode(frames, path, size, crf="16", preset="medium"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", size, "-r", str(FPS), "-i", "-",
                          "-vf", "format=yuv420p", "-c:v", "libx264", "-crf", crf, "-preset", preset, "-tune", "animation", path], stdin=subprocess.PIPE)
    for a in frames:
        p.stdin.write(np.ascontiguousarray(a).tobytes())
    p.stdin.close()
    if p.wait():
        sys.exit("ffmpeg failed")


if __name__ == "__main__":
    a = sys.argv[1:]
    pos = [x for x in a if not x.startswith("--")]
    os.makedirs(OUT, exist_ok=True)
    if "--frame" in a:
        t = float(pos[0])
        Image.fromarray(render(t, float(pos[1]) if len(pos) > 1 else 0.5)[1]).save(os.path.join(OUT, f"_f{t:.2f}.png"))
    elif "--stills" in a:
        only = set(pos)
        tiles = []
        for name, t0, t1, _, _ in SHOTS:
            if only and name not in only:
                continue
            for t in (t0 + 0.1, (t0 + t1) / 2, t1 - 0.06):
                im = Image.fromarray(render(t, 0.25)[1])
                ImageDraw.Draw(im).text((4, 4), f"{name} {t:.1f}", fill=(255, 255, 0))
                tiles.append(im)
        w, h = tiles[0].size
        cols = 9
        sheet = Image.new("RGB", (w * cols, h * ((len(tiles) + cols - 1) // cols)))
        for i, im in enumerate(tiles):
            sheet.paste(im, ((i % cols) * w, (i // cols) * h))
        sheet.save(os.path.join(OUT, "shots.png"))
        print(os.path.join(OUT, "shots.png"))
    elif "--master-part" in a:
        k, n = int(pos[0]), int(pos[1])
        fr = frames_of(0, TOTAL)
        L = -(-len(fr) // n)
        encode((render(t, 1.0)[1] for t in fr[k * L:(k + 1) * L]), os.path.join(VID, f"_part{k:02d}.mp4"), f"{W}x{H}", crf="16", preset="fast")
    elif "--master-par" in a:
        n = int(a[a.index("--master-par") + 1])
        os.makedirs(VID, exist_ok=True)
        procs = [subprocess.Popen([sys.executable, os.path.abspath(__file__), "--master-part", str(k), str(n)]) for k in range(n)]
        if any([p.wait() for p in procs]):
            sys.exit("a master part failed")
        lst = os.path.join(VID, "_parts.txt")
        open(lst, "w").write("".join(f"file '_part{k:02d}.mp4'\n" for k in range(n)))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", os.path.join(VID, "reel_silent.mp4")], check=True)
        for k in range(n):
            os.remove(os.path.join(VID, f"_part{k:02d}.mp4"))
        os.remove(lst)
        print(os.path.join(VID, "reel_silent.mp4"))
