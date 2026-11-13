"""ONE LOOK: the reel. Toon characters in a woods clearing, a city street and a bunker, plus 2D motion-graphic inserts.

    python reel.py --frame T [scale] | --stills | --preview [--full] | --master-par N
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
from toon import Camera, Frame, W, H, argb, lin, mix, paint, rad, shade  # noqa: E402
from sets.city_street import default_street, floor_at  # noqa: E402

FPS = 30
OUT, VID = os.path.join(HERE, "review"), os.path.join(HERE, "video")
TL = json.load(open(os.path.join(HERE, "timeline.json"), encoding="utf-8"))
TOTAL, B = TL["total"], TL["beats"]
b0 = lambda k: B[k]["t0"]      # noqa: E731
b1 = lambda k: B[k]["t1"]      # noqa: E731
TF, TFB = TN.typeface(False), TN.typeface(True)
PURPLE = "#b45cff"
STREET = default_street()

# ---- the cast: infected copies of the kit people get glowing purple eyes; the woman at the gate gets a blindfold --
for nm in ("jeff", "liu", "randy", "mother", "father", "doctor", "bully"):
    rig.LOOK[nm + "_x"] = dict(rig.LOOK[nm], glow=PURPLE)


def blindfold(colr="#c0392b"):
    def extra(parts, fr, cam, J, p, ld, lw, out):
        R, Bh, hc = J["R"], J["Bh"], J["head"]
        rings = [(0.06 * R, 1.09 * R, 1.06 * R, 0, 0.02 * R), (-0.24 * R, 1.10 * R, 1.07 * R, 0, 0.02 * R)]
        path, z = rig.lathe(cam, Bh.w(hc, 0, 0, 0), Bh, rings)
        k = cam.proj(hc)[3]
        knot = cam.proj(Bh.w(hc, 0, -0.05 * R, -1.12 * R))

        def draw():
            fr.part(path, colr, ld, width=2.2 * R * k, line=lw, lit=0.15, dark=0.45)
            if dot_back(cam, J) and knot[2] > 0.2:
                for s in (-1, 1):
                    fr.c.drawOval(skia.Rect(knot[0] - 0.2 * R * k + s * 0.18 * R * k, knot[1] - 0.12 * R * k, knot[0] + 0.2 * R * k + s * 0.18 * R * k, knot[1] + 0.12 * R * k), paint(colr))
        parts.append(("face", 0.0, draw))
    return extra


def dot_back(cam, J):
    return rig.dot(J["Bh"].f, rig.norm(rig.sub(cam.pos, J["head"]))) < 0


rig.LOOK["gate_woman"] = dict(rig.LOOK["maya"], extras=tuple(rig.LOOK["maya"]["extras"]) + (blindfold(),))
rig.LOOK["randy_bf"] = dict(rig.LOOK["randy"], extras=(blindfold("#2c3e50"),))


def helmet():
    """The blackout helmet: a white shell with a solid black visor (pose key "helmet" 0..1 = on)."""
    def extra(parts, fr, cam, J, p, ld, lw, out):
        if p.get("helmet", 0.0) < 0.5:
            return
        R, Bh, hc = J["R"], J["Bh"], J["head"]
        k = cam.proj(hc)[3]
        shell = [(u * R, math.sqrt(max(0.0, 1 - (u / 1.28) ** 2)) * 1.28 * R, math.sqrt(max(0.0, 1 - (u / 1.28) ** 2)) * 1.25 * R, 0, -0.02 * R)
                 for u in (-1.15, -0.8, -0.3, 0.2, 0.7, 1.1, 1.26)]
        path, _ = rig.lathe(cam, hc, Bh, shell)
        vis = [cam.proj(Bh.w(hc, x * R, y * R, 1.16 * R)) for x, y in ((-0.85, 0.45), (0.85, 0.45), (0.9, -0.35), (0.5, -0.62), (-0.5, -0.62), (-0.9, -0.35))]

        def draw():
            fr.part(path, "#e9ecf1", ld, width=2.6 * R * k, line=lw, lit=0.2, dark=0.4)
            if not dot_back(cam, J):
                v = rig.smooth([q[:2] for q in vis], k=0.6)
                fr.c.drawPath(v, paint("#07080c"))
                b = v.getBounds()
                fr.c.drawOval(skia.Rect(b.left() + b.width() * 0.12, b.top() + b.height() * 0.12, b.left() + b.width() * 0.4, b.top() + b.height() * 0.3), paint("#ffffff", a=0.25))
        parts.append(("top", 0.0, draw))
    return extra


rig.LOOK["theo"]["extras"] = tuple(rig.LOOK["theo"]["extras"]) + (helmet(),)


# ---- helpers -----------------------------------------------------------------------------------------------------
def cl(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def sm(u):
    u = cl(u)
    return u * u * (3 - 2 * u)


def lerp(a, b, u):
    return tuple(x + (y - x) * u for x, y in zip(a, b)) if isinstance(a, tuple) else a + (b - a) * u


def cam(pos, tgt, f, hz=0.46):
    return Camera(pos, math.degrees(math.atan2(tgt[0] - pos[0], tgt[2] - pos[2])), f, hz)


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


def grad_bg(c, cols, pos=None):
    c.drawRect(skia.Rect(-10, -10, W + 10, H + 10), paint(shader=lin((0, 0), (0, H), [argb(x) for x in cols], pos)))


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
            return 0.32 * float(np.mean(e[max(0, i - 2):i + 3])) if i < len(e) else 0.0
    return 0.0


# ================================================================================================ the woods clearing
class Woods:
    """A clearing in a pine forest. The cabin stands at z = 8; the gate and fence cross at z = 2 (gate at x = 0)."""

    def __init__(self):
        r = np.random.default_rng(7)
        self.trees = []
        for i in range(140):
            a = r.uniform(0, 2 * math.pi)
            d = r.uniform(11, 45)
            x, z = math.cos(a) * d, 6 + math.sin(a) * d
            self.trees.append((x, z, r.uniform(5.5, 10.0), r.uniform(1.4, 2.4), r.uniform(-0.08, 0.08)))

    def draw(self, fr, cm, T, night=False, built=(), cast=(), dog=None):
        c = fr.c
        if night:
            grad_bg(c, ["#03040c", "#0b1430", "#1b2547"], [0, 0.6, 1])
            mx, my, md, ms = cm.proj((30, 40, -120))
            if md > 0.3:
                fr.glow(mx, my, 120, "#c9d7ff", a=0.4)
                c.drawCircle(mx, my, 34, paint("#e9eeff"))
        else:
            grad_bg(c, ["#79b2e4", "#bfe0f2", "#f2e4c4"], [0, 0.6, 1])
        g0, g1 = ("#18241c", "#0d140f") if night else ("#6fa152", "#4f7f3c")
        fr.poly(cm, [(-80, 0, -80), (80, 0, -80), (80, 0, 120), (-80, 0, 120)], colr=g0)
        fr.ground_ellipse(cm, 0, 6, 9, 9, "#8a7350" if not night else "#2a2a24", 0.55, blur_m=1.5)          # the dirt clearing
        items = []
        for x, z, h, w, tone in self.trees:
            items.append((cm.view((x, h / 2, z))[2], lambda fr, x=x, z=z, h=h, w=w, tone=tone: self.tree(fr, cm, x, z, h, w, tone, night)))
        if "house" in built:
            items.append((cm.view((0, 2, 8))[2], lambda fr: self.cabin(fr, cm, T, built, night)))
        if "bunker" in built:
            items.append((cm.view((3.6, 0.5, 5.2))[2], lambda fr: self.hatch(fr, cm, night)))
        if "cameras" in built:
            for px, pz in ((-5.5, 3.0), (5.5, 3.0)):
                items.append((cm.view((px, 2, pz))[2], lambda fr, px=px, pz=pz: self.campole(fr, cm, px, pz, T)))
        if "food" in built:
            items.append((cm.view((-3.2, 0.5, 6.4))[2], lambda fr: self.crates(fr, cm, night)))
        if "gate" in built:
            items.append((cm.view((0, 1, 2))[2], lambda fr: self.fence(fr, cm, night)))
        if dog:
            items.append((cm.view(dog[:3])[2], lambda fr: self.dog(fr, cm, dog, T)))
        for pid, look, pose, held in cast:
            items.append((cm.view(rig.solve(look, pose)["pelvis"])[2], lambda fr, look=look, pose=pose, held=held:
                          self.person(fr, cm, look, pose, held, night)))
        outs = {}
        for _, fn in sorted(items, key=lambda q: -q[0]):
            r = fn(fr)
            if isinstance(r, dict):
                outs.update(r)
        if night:
            c.drawRect(skia.Rect(-10, -10, W + 10, H + 10), paint(shader=rad((W / 2, H * 0.5), H * 0.7, [argb("#000000", 0), argb("#000008", 0.6)], [0.45, 1])))
        return outs

    def person(self, fr, cm, look, pose, held, night):
        fr.c.saveLayer(None, None)
        o = rig.draw(fr, cm, look, pose, light=(4, 8, -4), held=held)
        if night and o.get("head"):
            hx, hy = o["head"][:2]
            r = max(8.0, o["head_r"])
            p = skia.Paint(BlendMode=skia.BlendMode.kModulate)
            p.setShader(rad((hx, hy), r * 7, [argb("#ffffff"), argb("#c5cbe0"), argb("#5d6788")], [0, 0.3, 1]))
            fr.c.drawPaint(p)
        fr.c.restore()
        return {look: o}

    def tree(self, fr, cm, x, z, h, w, tone, night):
        trunk = "#3b2a1e" if not night else "#15100c"
        fr.box(cm, (x - 0.18, x + 0.18), (0, h * 0.35), (z - 0.18, z + 0.18), trunk, line=0.8)
        base = "#2f6b3a" if not night else "#0d1c14"
        for k in range(4):
            y0 = h * (0.25 + k * 0.18)
            rw = w * (1.0 - k * 0.2)
            a, b = cm.proj((x - rw, y0, z)), cm.proj((x + rw, y0, z))
            t = cm.proj((x, y0 + h * 0.32, z))
            if min(a[2], b[2], t[2]) < 0.3:
                continue
            p = skia.Path()
            p.moveTo(a[0], a[1])
            p.lineTo(t[0], t[1])
            p.lineTo(b[0], b[1])
            p.close()
            fr.c.drawPath(p, paint(shade(base, tone + 0.05 * k)))
            fr.c.drawPath(p, paint(shade(base, -0.5), stroke=1.2))

    def cabin(self, fr, cm, T, built, night):
        pop = sm((T - b0("house") - 0.3) / 0.5) if T < b0("house") + 1 else 1.0
        y1 = 2.6 * pop
        wall = "#9a6a42" if not night else "#3a2a20"
        fr.ground_ellipse(cm, 0, 8, 3.4, 2.6, "#000000", 0.35, blur_m=0.3)
        fr.box(cm, (-3.0, 3.0), (0, y1), (6.5, 9.5), wall, light=(4, 8, -4), line=1.5)
        for i in range(8):                                         # log lines
            yy = y1 * (i + 0.5) / 8
            fr.poly(cm, [(-3.0, yy, 6.49), (3.0, yy, 6.49), (3.0, yy + 0.03, 6.49), (-3.0, yy + 0.03, 6.49)], colr=shade(wall, -0.35))
        if pop > 0.9:
            roof = "#3b3f48"
            fr.poly(cm, [(-3.3, 2.6, 6.2), (3.3, 2.6, 6.2), (3.3, 4.0, 8.0), (-3.3, 4.0, 8.0)], colr=roof, outline="#15171c", line=1.5)
            sh = sm((T - b0("shutters") - 0.2) / 0.5) if "shutters" in built else 0.0
            for wx in (-1.8, 1.8):                                 # windows, then the steel shutters roll down
                lit = "#ffd27a" if night else "#bfe3ff"
                fr.poly(cm, [(wx - 0.6, 0.9, 6.48), (wx + 0.6, 0.9, 6.48), (wx + 0.6, 1.9, 6.48), (wx - 0.6, 1.9, 6.48)], colr=lit, outline="#2a1d14", line=2.0)
                if sh > 0:
                    yb = 1.9 - 1.0 * sh
                    fr.poly(cm, [(wx - 0.65, yb, 6.46), (wx + 0.65, yb, 6.46), (wx + 0.65, 1.95, 6.46), (wx - 0.65, 1.95, 6.46)], colr="#8e959f", outline="#3b4048", line=1.5)
                    for k in range(5):
                        yy = 1.95 - (1.95 - yb) * (k + 1) / 6
                        fr.poly(cm, [(wx - 0.65, yy, 6.455), (wx + 0.65, yy, 6.455), (wx + 0.65, yy + 0.02, 6.455), (wx - 0.65, yy + 0.02, 6.455)], colr="#5e646d")
            fr.poly(cm, [(-0.45, 0, 6.48), (0.45, 0, 6.48), (0.45, 1.9, 6.48), (-0.45, 1.9, 6.48)], colr="#4a3424", outline="#1f150e", line=2.0)

    def hatch(self, fr, cm, night):
        fr.box(cm, (3.0, 4.2), (0, 0.35), (4.6, 5.8), "#5d6670" if not night else "#2a2f36", line=1.5)
        fr.poly(cm, [(3.15, 0.351, 4.75), (4.05, 0.351, 4.75), (4.05, 0.351, 5.65), (3.15, 0.351, 5.65)], colr="#3b4048", outline="#ffcc00", line=4.0)
        p = cm.proj((3.6, 0.36, 5.2))
        if p[2] > 0.3:
            fr.c.drawCircle(p[0], p[1], 0.22 * p[3], paint("#8e959f", stroke=0.05 * p[3]))

    def campole(self, fr, cm, x, z, T):
        fr.box(cm, (x - 0.06, x + 0.06), (0, 3.2), (z - 0.06, z + 0.06), "#2b2e34", line=1.0)
        fr.box(cm, (x - 0.25, x + 0.25), (3.1, 3.4), (z - 0.35, z + 0.1), "#e9ecf1", line=1.2)
        p = cm.proj((x, 3.25, z - 0.36))
        if p[2] > 0.3:
            fr.c.drawCircle(p[0], p[1], 0.08 * p[3], paint("#14161d"))
            if int(T * 2) % 2 == 0:
                fr.c.drawCircle(p[0] + 0.15 * p[3], p[1] - 0.1 * p[3], 0.03 * p[3], paint("#ff2d2d"))

    def crates(self, fr, cm, night):
        for i, (x, z, c) in enumerate(((-3.6, 6.2, "#a07a4a"), (-2.9, 6.3, "#8a6a3e"), (-3.3, 6.9, "#2e7d32"))):
            fr.box(cm, (x - 0.32, x + 0.32), (0, 0.55 if i < 2 else 0.4), (z - 0.3, z + 0.3), c if not night else shade(c, -0.6), line=1.2)
        fr.box(cm, (-3.6, -2.7), (0.55, 0.95), (6.0, 6.5), "#2b2e34", line=1.2)
        for k in range(4):
            fr.poly(cm, [(-3.5 + k * 0.22, 0.6, 5.99), (-3.36 + k * 0.22, 0.6, 5.99), (-3.36 + k * 0.22, 0.9, 5.99), (-3.5 + k * 0.22, 0.9, 5.99)], colr="#3ddc84")

    def fence(self, fr, cm, night):
        col = "#5d6670" if not night else "#3a4250"
        for x in np.arange(-7.0, 7.01, 0.35):
            if abs(x) < 0.05:
                continue
            fr.box(cm, (x - 0.03, x + 0.03), (0, 2.2), (1.98, 2.02), col, line=0.6)
        for y in (0.3, 2.1):
            fr.box(cm, (-7.0, 7.0), (y - 0.04, y + 0.04), (1.97, 2.03), shade(col, -0.2), line=0.8)
        fr.box(cm, (-0.9, 0.9), (2.2, 2.5), (1.95, 2.05), shade(col, -0.3), line=1.0)
        p = cm.proj((0.95, 1.4, 1.9))
        if p[2] > 0.3:                                             # the intercom box
            fr.c.drawRect(skia.Rect(p[0] - 0.12 * p[3], p[1] - 0.18 * p[3], p[0] + 0.12 * p[3], p[1] + 0.18 * p[3]), paint("#1d1f24"))
            fr.c.drawCircle(p[0], p[1] + 0.08 * p[3], 0.03 * p[3], paint("#3ddc84"))

    def dog(self, fr, cm, d, T):
        x, y, z, yaw = d
        f = (math.sin(math.radians(yaw)), 0, -math.cos(math.radians(yaw)))
        c = fr.c
        body = cm.proj((x, 0.45, z))
        head = cm.proj((x + f[0] * 0.45, 0.68, z + f[2] * 0.45))
        tail = cm.proj((x - f[0] * 0.42, 0.62 + 0.05 * math.sin(T * 14), z - f[2] * 0.42))
        if min(body[2], head[2]) < 0.3:
            return None
        k = body[3]
        fr.ground_ellipse(cm, x, z, 0.4, 0.25, "#000000", 0.35, blur_m=0.05)
        for dx in (-0.25, 0.25):
            for dz in (-0.1, 0.1):
                lp = cm.proj((x + f[0] * dx + dz * f[2], 0.0, z + f[2] * dx - dz * f[0]))
                c.drawRoundRect(skia.Rect(lp[0] - 0.05 * k, lp[1] - 0.4 * k, lp[0] + 0.05 * k, lp[1]), 0.03 * k, 0.03 * k, paint("#b5793e"))
        c.drawLine(body[0], body[1], tail[0], tail[1] - 0.15 * k, paint("#b5793e", stroke=0.06 * k))
        bp = skia.Path()
        bp.addOval(skia.Rect(body[0] - 0.42 * k, body[1] - 0.2 * k, body[0] + 0.42 * k, body[1] + 0.18 * k))
        fr.part(bp, "#c98a4b", (0.3, 1.0), width=0.8 * k, line=1.5)
        hp = skia.Path()
        hp.addOval(skia.Rect(head[0] - 0.18 * k, head[1] - 0.17 * k, head[0] + 0.18 * k, head[1] + 0.15 * k))
        fr.part(hp, "#c98a4b", (0.3, 1.0), width=0.36 * k, line=1.5)
        for s in (-1, 1):
            c.drawOval(skia.Rect(head[0] + s * 0.17 * k - 0.06 * k, head[1] - 0.12 * k, head[0] + s * 0.17 * k + 0.06 * k, head[1] + 0.1 * k), paint("#7a4a22"))
            c.drawCircle(head[0] + s * 0.07 * k, head[1] - 0.03 * k, 0.025 * k, paint("#111111"))
        c.drawCircle(head[0], head[1] + 0.07 * k, 0.04 * k, paint("#222222"))
        return None


WOODS = Woods()


def theo(T, x=-1.4, z=4.2, yaw=-20.0, helm=0.0, look_up=0.0, scared=0.0):
    p = dict(rig.REST, x=x, z=z, yaw=yaw, t=T, helmet=helm, breath=0.5 + 0.5 * math.sin(T * 2.1))
    p.update(lid=0.95 * blink(T, [x * 3.1 + 1.5 for x in range(40)]), smile=0.3 * (1 - scared), brow=-0.5 * scared, mouth=0.1 * scared,
             head_pitch=-12 * look_up, aR=(10.0, 8.0, 30.0), aL=(10.0, 8.0, 30.0))
    return p


# ================================================================================================ 2D inserts
def scene_eye(fr, T, t0, t1):
    c = fr.c
    grad_bg(c, ["#0a0618", "#1d0c3a", "#0a0618"])
    u = (T - t0) / (t1 - t0)
    open_ = sm((T - t0 - 0.3) / 0.6)
    cx, cy = W / 2, H * 0.5
    R = 420 + 140 * u
    eye = skia.Path()
    eye.moveTo(cx - R * 1.25, cy)
    eye.quadTo(cx, cy - R * 0.95 * open_, cx + R * 1.25, cy)
    eye.quadTo(cx, cy + R * 0.95 * open_, cx - R * 1.25, cy)
    c.drawPath(eye, paint("#f4eefc"))
    c.save()
    c.clipPath(eye, skia.ClipOp.kIntersect, True)
    fr.glow(cx, cy, R * 1.1, PURPLE, a=0.6)
    c.drawCircle(cx, cy, R * 0.62, paint(shader=rad((cx, cy), R * 0.62, [argb("#f0d9ff"), argb(PURPLE), argb("#3b0f6e")], [0, 0.5, 1])))
    for i in range(36):                                            # iris fibres, slowly turning
        a = i * math.pi / 18 + T * 0.4
        c.drawLine(cx + math.cos(a) * R * 0.22, cy + math.sin(a) * R * 0.22, cx + math.cos(a) * R * 0.6, cy + math.sin(a) * R * 0.6, paint("#e3b6ff", a=0.35, stroke=4))
    c.drawCircle(cx, cy, R * (0.16 + 0.04 * math.sin(T * 3)), paint("#07020f"))
    c.drawCircle(cx - R * 0.18, cy - R * 0.2, R * 0.08, paint("#ffffff", a=0.9))
    c.restore()
    c.drawPath(eye, paint("#1a0b2e", stroke=14))
    for i in range(14):                                            # lashes
        a = math.pi * (0.1 + 0.8 * i / 13)
        x0, y0 = cx - math.cos(a) * R * 1.1, cy - math.sin(a) * R * 0.78 * open_
        c.drawLine(x0, y0, x0 - math.cos(a) * 60, y0 - math.sin(a) * 90, paint("#1a0b2e", stroke=10))


def scene_alaska(fr, T, t0, t1):
    c = fr.c
    grad_bg(c, ["#a9c8e6", "#e8f1f8"])
    for i, (x, h) in enumerate(((-100, 700), (250, 900), (600, 760), (950, 880))):           # mountains
        p = skia.Path()
        p.moveTo(x - 380, H * 0.55)
        p.lineTo(x, H * 0.55 - h * 0.6)
        p.lineTo(x + 380, H * 0.55)
        p.close()
        c.drawPath(p, paint("#7f97b0" if i % 2 else "#91a8c0"))
        sp = skia.Path()
        sp.moveTo(x - 110, H * 0.55 - h * 0.6 + 170)
        sp.lineTo(x, H * 0.55 - h * 0.6)
        sp.lineTo(x + 110, H * 0.55 - h * 0.6 + 170)
        sp.close()
        c.drawPath(sp, paint("#ffffff"))
    c.drawRect(skia.Rect(0, H * 0.55, W, H), paint("#eef3f7"))
    u = sm((T - t0) / 0.5)
    y0 = H * 0.30 + (1 - u) * 300
    c.drawRoundRect(skia.Rect(90, y0, W - 90, y0 + 1000), 30, 30, paint("#f7f1e3"))
    c.drawRoundRect(skia.Rect(90, y0, W - 90, y0 + 1000), 30, 30, paint("#5b4a33", stroke=6))
    text(c, "FIELD REPORT", 150, y0 + 110, 76, "#2b2218", center=False)
    text(c, "ALASKA · FISHING TOWN", 150, y0 + 170, 38, "#6b5a43", center=False, bold=False)
    for i, (who, age) in enumerate((("DOCK WORKER", 41), ("SCHOOL TEACHER", 29), ("RETIRED NURSE", 67))):
        y = y0 + 240 + i * 230
        a = sm((T - t0 - 0.4 - i * 0.35) / 0.3)
        c.drawRoundRect(skia.Rect(140, y, W - 140, y + 200), 18, 18, paint("#ffffff", a=a))
        c.drawCircle(240, y + 100, 64, paint("#d9c6a8", a=a))
        c.drawCircle(225, y + 90, 9, paint(PURPLE, a=a))
        c.drawCircle(258, y + 90, 9, paint(PURPLE, a=a))
        text(c, "CASE 00%d" % (i + 1), 340, y + 80, 44, "#222222", center=False, a=a)
        text(c, "%s, %d" % (who, age), 340, y + 130, 34, "#555555", center=False, bold=False, a=a)
        text(c, "NO FEVER", 340, y + 175, 30, "#2e7d32", center=False, a=a)
    st = sm((T - (b0("alaska") + 3.6)) / 0.25)
    if st > 0:
        c.save()
        c.rotate(-12, W / 2, y0 + 880)
        sc = 1.6 - 0.6 * st
        c.scale(sc, sc)
        text(c, "LOW RISK", W / 2 / sc, (y0 + 900) / sc, 120, "#2ecc71", stroke=10, a=st)
        c.restore()


def scene_map(fr, T, t0, t1):
    c = fr.c
    grad_bg(c, ["#0b0f24", "#151a3a"])
    u = sm((T - t0 - 0.4) / (t1 - t0 - 1.6))
    r = np.random.default_rng(12)
    blobs = [(r.uniform(120, W - 120), r.uniform(H * 0.25, H * 0.62), r.uniform(70, 170)) for _ in range(26)]
    for i, (x, y, s) in enumerate(blobs):                         # a stylised world map of land blobs
        inf = cl(u * 1.6 - (abs(x - 200) + abs(y - H * 0.3)) / 1600)
        pts = [(x + math.cos(a) * s * (0.7 + 0.3 * math.sin(a * 3 + i)), y + math.sin(a) * s * 0.6 * (0.8 + 0.2 * math.cos(a * 2 + i)))
               for a in np.linspace(0, 2 * math.pi, 12, endpoint=False)]
        c.drawPath(rig.smooth(pts), paint(mix("#2f5d50", PURPLE, inf)))
        if inf > 0.5:
            fr.glow(x, y, s * 0.8, PURPLE, a=0.25 * inf)
    pill(c, 140, H * 0.70, W - 140, H * 0.70 + 110, "#000000", 0.6)
    text(c, "COUNTRIES INFECTED: %d / 195" % round(195 * u), W / 2, H * 0.70 + 75, 52, "#ffffff" if u < 0.99 else "#ff5a5a")
    if T > b0("numbers") + 3.6:                                   # the calendar slams in
        a = sm((T - b0("numbers") - 3.6) / 0.25)
        s = 1.5 - 0.5 * a
        c.save()
        c.translate(W / 2, H * 0.47)
        c.scale(s, s)
        c.drawRoundRect(skia.Rect(-260, -280, 260, 280), 30, 30, paint("#ffffff", a=a))
        c.drawRoundRect(skia.Rect(-260, -280, 260, -150), 30, 30, paint("#e53935", a=a))
        text(c, "DAYS LEFT", 0, -195, 60, "#ffffff", a=a)
        text(c, "100", 0, 150, 260, "#111111", a=a)
        c.restore()


def scene_city_card(fr, T, t0, t1, label):
    c = fr.c
    grad_bg(c, ["#120a26", "#2a1650"])
    a = sm((T - t0) / 0.3)
    s = 1.3 - 0.3 * a
    c.save()
    c.translate(W / 2, H * 0.47)
    c.scale(s, s)
    c.drawRoundRect(skia.Rect(-280, -300, 280, 300), 30, 30, paint("#ffffff", a=a))
    c.drawRoundRect(skia.Rect(-280, -300, 280, -170), 30, 30, paint("#e53935", a=a))
    text(c, "DAY", 0, -210, 70, "#ffffff", a=a)
    text(c, label, 0, 150, 240, "#111111", a=a)
    c.restore()


def scene_nosignal(fr, T, t0, t1):
    c = fr.c
    grad_bg(c, ["#05060a", "#0f1116"])
    c.drawRoundRect(skia.Rect(80, H * 0.28, W - 80, H * 0.62), 24, 24, paint("#20232b"))
    on = T < b0("dark") + 1.6
    if on:
        r = np.random.default_rng(int(T * 30))
        for i in range(300):                                       # static
            x, y = r.uniform(110, W - 110), r.uniform(H * 0.29, H * 0.61)
            c.drawRect(skia.Rect(x, y, x + r.uniform(4, 30), y + 3), paint("#ffffff", a=r.uniform(0.1, 0.6)))
    else:
        c.drawRect(skia.Rect(110, H * 0.29, W - 110, H * 0.61), paint("#1d3fbf"))
        text(c, "NO SIGNAL", W / 2, H * 0.46, 110, "#ffffff")
        text(c, "CHANNEL LOST", W / 2, H * 0.51, 40, "#c9d4ff", bold=False)
    text(c, "DAY 103", W / 2, H * 0.2, 90, "#ff5a5a", stroke=12)


# ================================================================================================ post looks
def cctv(arr, T, label):
    a = arr.astype(np.float32)
    g = a.mean(axis=2, keepdims=True)
    a = 0.35 * a + 0.65 * g * np.array([0.75, 1.0, 0.8])
    a[::3] *= 0.8
    out = np.clip(a, 0, 255).astype(np.uint8)
    im = Image.fromarray(out)
    d = ImageDraw.Draw(im)
    s = im.width / 1080
    d.rectangle((30 * s, 30 * s, im.width - 30 * s, im.height - 30 * s), outline=(220, 255, 220), width=max(1, int(3 * s)))
    d.text((60 * s, 60 * s), label, fill=(220, 255, 220))
    d.text((60 * s, 90 * s), "DAY 103   23:%02d:%02d" % (14 + int(T) // 60 % 10, int(T) % 60), fill=(220, 255, 220))
    if int(T * 2) % 2 == 0:
        d.ellipse((im.width - 120 * s, 60 * s, im.width - 90 * s, 90 * s), fill=(255, 40, 40))
    return np.asarray(im)


def thermal(arr, mask):
    """Heat view: the person (mask) runs white-yellow-red, everything else cold blue-purple."""
    g = arr.astype(np.float32).mean(axis=2) / 255.0
    cold = np.stack([30 + 40 * g, 20 + 30 * g, 90 + 90 * g], axis=2)
    hot_t = np.clip(0.55 + 0.45 * g, 0, 1)[..., None]
    hot = np.concatenate([255 * np.ones_like(hot_t), 120 + 135 * hot_t ** 2, 40 * hot_t ** 4], axis=2)
    m = mask[..., None]
    return np.clip(cold * (1 - m) + hot * m, 0, 255).astype(np.uint8)


# ================================================================================================ shots
def items_built(T):
    seq = [("house", "house"), ("shutters", "shutters"), ("bunker", "bunker"), ("cameras", "cameras"), ("food", "food")]
    return tuple(k for k, beat in seq if T >= b0(beat))


def woods_shot(camf, castf=None, night=False, dog=False, post=None):
    def fn(fr, T, t0, t1):
        u = (T - t0) / max(1e-6, t1 - t0)
        cm = camf(u)
        built = items_built(T) if not night else ("house", "shutters", "bunker", "cameras", "food", "gate")
        d = (-0.4, 0, 4.6, -60.0) if (dog and (night or T >= b0("food"))) else None
        WOODS.draw(fr, cm, T, night=night, built=built, cast=castf(T) if castf else (), dog=d)
        return post
    return fn


def street_shot(camf, castf):
    def fn(fr, T, t0, t1):
        u = (T - t0) / max(1e-6, t1 - t0)
        cm = camf(u)
        STREET.bg(fr, cm, T)
        items = [(d, f) for d, f, _ in STREET.items(cm, T)]
        for pid, look, pose, held in castf(T):
            items.append((cm.view(rig.solve(look, pose)["pelvis"])[2], lambda fr, look=look, pose=pose: rig.draw(fr, cm, look, pose, light=(0, 5, 10))))
        for _, f in sorted(items, key=lambda q: -q[0]):
            f(fr)
        STREET.rain(fr, cm, T)
        STREET.night(fr, cm, T)
    return fn


def walker(look, x, z0, T, t_start, rate=1.6, smile=0.9, yaw=0.0, head_yaw=0.0):
    g = rig.gait(T, (x, floor_at(x), z0), yaw, 0.55, rate, t0=t_start)
    p = dict(rig.REST, x=g["x"], z=g["z"], yaw=yaw, floor=floor_at(x), t=T, ankle_R=g["ankle_R"], ankle_L=g["ankle_L"], plant=g["plant"],
             bob=g.get("bob", 0.0), smile=smile, mouth=0.12, lid=1.0, head_yaw=head_yaw)
    sw = g["swing"]
    p["aR"], p["aL"] = (-18 * sw, 6.0, 20.0), (18 * sw, 6.0, 20.0)
    return (look, look, p, None)


def crowd(T):
    t = b0("city")
    out = []
    for i, (lk, x, z) in enumerate((("jeff_x", -1.2, 12), ("liu_x", 1.0, 13.5), ("randy_x", 3.8, 11), ("mother_x", -3.9, 14), ("father_x", 0.2, 17),
                                    ("doctor_x", -2.4, 19), ("bully_x", 2.6, 20), ("jeff_x", 4.4, 23), ("liu_x", -4.2, 24))):
        out.append(walker(lk, x, z, T, t + 0.13 * i, rate=1.3 + 0.05 * (i % 3)))
    return out


def infect_pair(T):
    """A smiling carrier looks at a woman; one second later her eyes turn."""
    turned = T >= b0("second") + 1.2
    a = dict(rig.REST, x=-0.45, z=6.0, yaw=90.0, floor=floor_at(-0.45), smile=0.95, mouth=0.15, lid=1.0, t=T, head_yaw=-5)
    v = dict(rig.REST, x=0.45, z=6.0, yaw=-90.0, floor=floor_at(0.45), smile=0.95 if turned else 0.0, mouth=0.15 if turned else 0.2,
             lid=1.0 if turned else 1.15, brow=0.0 if turned else 0.5, t=T, head_yaw=8 * math.sin(T) if turned else 0)
    return [("jeff_x", "jeff_x", a, None), ("liu_x" if turned else "liu", "liu_x" if turned else "liu", v, None)]


def blind_pair(T):
    t = b0("blind")
    a = walker("randy_bf", 0.6, 9.5, T, t, rate=0.9, smile=0.0, yaw=0)
    a[2].update(aR=(70.0, 10.0, 10.0), aL=(70.0, -6.0, 10.0), lid=1.0, brow=-0.6)
    lean = sm((T - t - 2.0) / 1.0)
    b = dict(rig.REST, x=0.25, z=6.2 + 0.25 * lean, yaw=180.0, floor=floor_at(0.35), smile=0.95, mouth=0.12, lid=1.0, lean=12 * lean, t=T, head_yaw=-10)
    return [a, ("bully_x", "bully_x", b, None)]


def gate_woman(T, side=False):
    p = dict(rig.REST, x=0.0, z=1.45, yaw=180.0, t=T, aR=(60.0, 14.0, 70.0), aL=(60.0, 14.0, 70.0), brow=-0.7, smile=-0.3, head_pitch=4,
             breath=0.5 + 0.5 * math.sin(T * 4), lid=1.0)
    p["mouth"] = mouth(T, "MAYA")
    J = rig.solve("gate_woman", dict(p))
    p["ik_R"], p["ik_L"] = (-0.3, 1.35, 1.92), (0.3, 1.4, 1.92)          # hands on the gate bars
    p["pole_R"], p["pole_L"] = (-1, -1, 0.3), (1, -1, 0.3)
    return [("gate_woman", "gate_woman", p, None)]


def bunker_shot(fr, T, t0, t1):
    """Inside the bunker: red alarm light, monitors, Theo jumps up; the dog barks."""
    c = fr.c
    grad_bg(c, ["#1a1416", "#2b2024"])
    u = (T - t0) / (t1 - t0)
    cm = cam(lerp((1.1, 1.5, -0.3), (0.95, 1.5, 0.1), u), (-0.3, 1.3, 2.2), 1300, 0.46)
    fr.poly(cm, [(-3, 0, -2), (3, 0, -2), (3, 0, 6), (-3, 0, 6)], colr="#3a3438")
    fr.poly(cm, [(-3, 0, 4), (3, 0, 4), (3, 2.6, 4), (-3, 2.6, 4)], colr="#4a4a52")
    for i in range(3):                                             # monitors on the back wall
        x0 = -2.2 + i * 1.5
        fr.poly(cm, [(x0, 1.2, 3.98), (x0 + 1.3, 1.2, 3.98), (x0 + 1.3, 2.1, 3.98), (x0, 2.1, 3.98)], colr="#0a2a14" if i != 1 else "#3a0a0a", outline="#14161d", line=3)
    pr = cm.proj((-0.15, 1.65, 3.97))
    if pr[2] > 0.3:
        text(c, "MOTION", pr[0], pr[1], 0.18 * pr[3], "#ff4d4d")
    fr.box(cm, (-2.6, 2.6), (0, 0.8), (3.2, 3.9), "#2b2e34", line=1.5)
    lp = cm.proj((1.8, 2.4, 3.6))
    pulse = 0.5 + 0.5 * math.sin(T * 9)
    if lp[2] > 0.3:
        fr.glow(lp[0], lp[1], 0.6 * lp[3], "#ff2020", a=0.8 * pulse)
        c.drawCircle(lp[0], lp[1], 0.08 * lp[3], paint("#ff6060"))
    p = theo(T, x=-0.5, z=2.2, yaw=-15, scared=1.0)
    p["head_yaw"] = 25
    rig.draw(fr, cm, "theo", p, light=(1.8, 2.4, 3.6))
    WOODS.dog(fr, cm, (0.9, 0, 1.6, -40.0), T)
    c.drawRect(skia.Rect(-10, -10, W + 10, H + 10), paint("#ff1010", a=0.18 * pulse))


def thermal_shot(fr, T, t0, t1):
    cm = cam((0.0, 1.55, 3.4), (0.0, 1.45, 1.2), 2300, 0.42)
    WOODS.draw(fr, cm, T, night=True, built=("gate",), cast=gate_woman(T))
    base = fr.array()
    m = Frame(fr_scale(fr))
    rig.draw(m, cm, "gate_woman", gate_woman(T)[0][2], light=(0, 5, 0))
    mask = (m.array().astype(np.float32).sum(axis=2) > 30).astype(np.float32)
    out = thermal(base, mask)
    im = Image.fromarray(out)
    d = ImageDraw.Draw(im)
    s = im.width / 1080
    d.text((60 * s, 60 * s), "CAM 5 · THERMAL      36.8°C", fill=(255, 230, 200))
    d.text((60 * s, im.height - 400 * s), "IRIS:  NO DATA", fill=(255, 120, 120))
    d.text((60 * s, im.height - 370 * s), "PUPIL: NO DATA", fill=(255, 120, 120))
    return np.asarray(im)


def fr_scale(fr):
    return fr.array().shape[1] / W


def trees_shot(fr, T, t0, t1):
    u = (T - t0) / (t1 - t0)
    cm = cam(lerp((0.3, 1.6, 4.2), (0.2, 1.6, 3.6), u), (0.0, 1.5, -8.0), 1500, 0.46)
    WOODS.draw(fr, cm, T, night=True, built=("gate",), cast=gate_woman(T))
    c = fr.c
    r = np.random.default_rng(5)
    for i in range(7):                                             # smiles in the dark between the trees
        x, z = r.uniform(-5, 5), r.uniform(-9, -3)
        a = sm((T - t0 - 0.3 - i * 0.25) / 0.4)
        p = cm.proj((x, 1.6, z))
        if p[2] < 0.3 or a <= 0:
            continue
        s = p[3]
        for e in (-0.07, 0.07):
            fr.glow(p[0] + e * s, p[1], 0.14 * s, PURPLE, a=0.8 * a)
            c.drawCircle(p[0] + e * s, p[1], 0.025 * s, paint("#f2dcff", a=a))
        sp = skia.Path()
        sp.moveTo(p[0] - 0.1 * s, p[1] + 0.12 * s)
        sp.quadTo(p[0], p[1] + 0.22 * s, p[0] + 0.1 * s, p[1] + 0.12 * s)
        c.drawPath(sp, paint("#e8e0ff", a=0.8 * a, stroke=0.02 * s))


def choice_shot(fr, T, t0, t1):
    top = Frame(fr_scale(fr))
    WOODS.draw(top, cam((0.0, 1.6, 3.6), (0.0, 1.45, 1.2), 1700, 0.40), T, night=True, built=("gate",), cast=gate_woman(T))
    bot = Frame(fr_scale(fr))
    WOODS.draw(bot, cam((0.0, 2.2, 5.2), (0.0, 1.0, 0.0), 1100, 0.40), T, night=True, built=("gate",), cast=gate_woman(T))
    A1, B1 = top.array(), bot.array()
    h = A1.shape[0]
    out = np.concatenate([A1[h // 4: h // 4 + h // 2], B1[h // 4: h // 4 + h // 2]], axis=0)
    im = Image.fromarray(out)
    d = ImageDraw.Draw(im)
    s = im.width / 1080
    d.line((0, im.height // 2, im.width, im.height // 2), fill=(255, 255, 255), width=max(1, int(6 * s)))
    return np.asarray(im)


def items_cam(u):
    return cam(lerp((4.6, 2.1, -0.6), (3.9, 2.0, 0.2), sm(u)), (-0.5, 1.4, 6.5), 1000, 0.48)


SHOTS = [
    ("EYE", 0.0, b0("second"), scene_eye, {}),
    ("CONTACT", b0("second"), b0("smile"), street_shot(lambda u: cam(lerp((0.0, 1.62, 3.4), (0.0, 1.62, 3.7), u), (0.0, 1.55, 6.0), 1700, 0.42), infect_pair), {}),
    ("SMILE", b0("smile"), b0("alaska"), street_shot(lambda u: cam(lerp((-0.5, 1.62, 5.0), (-0.45, 1.62, 5.15), u), (0.45, 1.58, 6.0), 2300, 0.42), infect_pair), {}),
    ("ALASKA", b0("alaska"), b0("numbers"), scene_alaska, dict(cap=(1820, 66))),
    ("MAP", b0("numbers"), b0("deal"), scene_map, dict(cap=(1820, 66))),
    ("DEAL", b0("deal"), b0("house"), woods_shot(lambda u: cam(lerp((0.6, 1.7, 0.4), (0.2, 1.65, 1.2), sm(u)), (-1.4, 1.5, 4.2), 1500, 0.46),
                                                 lambda T: [("theo", "theo", theo(T, look_up=0.5), None)]), {}),
    ("BUILD", b0("house"), b0("helmet"), woods_shot(items_cam, lambda T: [("theo", "theo", theo(T), None)], dog=True), {}),
    ("HELMET", b0("helmet"), b0("city"), woods_shot(lambda u: cam(lerp((0.1, 1.7, 1.6), (-0.1, 1.68, 2.0), u), (-1.4, 1.6, 4.2), 2000, 0.42),
                                                    lambda T: [("theo", "theo", theo(T, helm=1.0 if T > b0("helmet") + 1.6 else 0.0), None)], dog=True), {}),
    ("DAY100", b0("city"), b0("city") + 1.4, lambda fr, T, t0, t1: scene_city_card(fr, T, t0, t1, "100"), {}),
    ("CITY", b0("city") + 1.4, b0("streets") + 2.6, street_shot(lambda u: cam(lerp((0.0, 2.6, -2.0), (0.0, 2.4, -0.5), u), (0.0, 1.4, 20.0), 1100, 0.44), crowd), {}),
    ("FACES", b0("streets") + 2.6, b0("blind"), street_shot(lambda u: cam(lerp((0.2, 1.62, 3.5), (0.2, 1.62, 3.9), u), (-0.4, 1.6, 10.0), 2400, 0.42), crowd), {}),
    ("BLIND", b0("blind"), b0("dark"), street_shot(lambda u: cam(lerp((1.6, 1.6, 3.0), (1.4, 1.6, 3.3), u), (0.4, 1.5, 7.0), 1500, 0.43), blind_pair), {}),
    ("NOSIGNAL", b0("dark"), b0("gate"), scene_nosignal, {}),
    ("ALARM", b0("gate"), b0("woman"), bunker_shot, {}),
    ("CCTV", b0("woman"), b0("please") + 1.6, woods_shot(lambda u: cam(lerp((1.6, 3.2, 5.0), (1.5, 3.1, 4.7), u), (0.0, 1.0, 1.0), 1200, 0.30),
                                                        gate_woman, night=True, post="CAM 2 · FRONT GATE"), {}),
    ("INTERCOM", b0("please") + 1.6, b0("heat"), woods_shot(lambda u: cam(lerp((0.25, 1.62, 2.6), (0.22, 1.62, 2.45), u), (0.0, 1.55, 1.2), 2600, 0.42),
                                                           gate_woman, night=True, post="GATE INTERCOM · LIVE"), {}),
    ("THERMAL", b0("heat"), b0("trees"), thermal_shot, {}),
    ("TREES", b0("trees"), b0("thirty"), trees_shot, {}),
    ("THIRTY", b0("thirty"), b0("choice"), bunker_shot, {}),
    ("CHOICE", b0("choice"), TOTAL, choice_shot, dict(cap=(900, 58))),
]


# ---- overlays ------------------------------------------------------------------------------------------------------
def hud_state(T):
    day, money = None, None
    for bid, b in B.items():
        pass
    for k, spk, *_ in []:
        pass
    import script as S
    for bid, spk, text_, ch, gap, ex in S.BEATS:
        if b0(bid) <= T:
            if "day" in ex:
                day = ex["day"]
            if "budget" in ex:
                money = ex["budget"]
    return day, money


def overlay(fr, T, name):
    c = fr.c
    if T < b0("second"):                                           # the title card
        a = sm(T / 0.3)
        text(c, "ONE LOOK", W / 2, 300, 150, "#d9a6ff", stroke=18, a=a)
        text(c, "AND IT'S OVER", W / 2, 390, 70, "#ffffff", stroke=12, a=a)
        pill(c, W / 2 - 220, 420, W / 2 + 220, 480, "#ffcc00", a)
        text(c, "100 DAYS · PART 1", W / 2, 465, 40, "#111111", a=a)
    if name == "CONTACT":                                          # the one-second ring
        u = cl((T - b0("second") - 0.2) / 1.0)
        c.drawCircle(W / 2, 330, 70, paint("#000000", a=0.6))
        c.drawArc(skia.Rect(W / 2 - 70, 260, W / 2 + 70, 400), -90, 360 * u, False, paint(PURPLE, stroke=12))
        text(c, "1 SEC", W / 2, 345, 40, "#ffffff")
    day, money = hud_state(T)
    if day is not None and name not in ("EYE", "CHOICE"):
        pill(c, 40, 120, 420, 210, "#000000", 0.7)
        text(c, "%d DAYS LEFT" % day if day > 0 else "DAY %d" % (100 - day), 230, 182, 44, "#ffffff")
        pill(c, W - 400, 120, W - 40, 210, "#000000", 0.7)
        text(c, "$%s" % format(money, ","), W - 220, 182, 50, "#7dffa0" if money > 0 else "#ff5a5a")
    import script as S
    for bid, spk, text_, ch, gap, ex in S.BEATS:                   # the item price tag pops in
        if "item" in ex and b0(bid) <= T < b0(bid) + 2.4:
            a = min(sm((T - b0(bid)) / 0.2), sm((b0(bid) + 2.4 - T) / 0.3))
            nm, price = ex["item"].split("  ")
            pill(c, 100, 300, W - 100, 470, "#000000", 0.7 * a)
            text(c, nm, W / 2, 375, 54, "#ffffff", a=a)
            text(c, price, W / 2, 445, 60, "#ff5a5a", a=a)
    if name == "THIRTY" or name == "CHOICE":
        left = max(0.0, 30 - (T - b0("thirty")) * 6)
        pill(c, W / 2 - 160, 120, W / 2 + 160, 220, "#c0392b", 0.9)
        text(c, "00:%02d" % int(left), W / 2, 195, 70, "#ffffff")
    if name == "CHOICE":
        pill(c, 60, 260, 520, 350, "#2ecc71", 0.95)
        text(c, "A: OPEN THE GATE", 290, 320, 40, "#ffffff")
        pill(c, 60, H // 2 + 40, 600, H // 2 + 130, "#e53935", 0.95)
        text(c, "B: KEEP IT CLOSED", 330, H // 2 + 100, 40, "#ffffff")
        if T > b1("choice"):
            a = sm((T - b1("choice")) / 0.4)
            pill(c, W / 2 - 330, H - 330, W / 2 + 330, H - 230, "#ffcc00", a)
            text(c, "A OR B? FOLLOW FOR PART 2", W / 2, H - 263, 44, "#111111", a=a)


CHUNKS = sorted([c for L in TL["lines"] for c in L["chunks"]], key=lambda c: c["t0"])


def caption(T):
    cur = None
    for c in CHUNKS:
        if c["t0"] <= T + 1e-6:
            cur = c
    return cur["text"] if cur and T < cur["t1"] + 0.3 else None


def draw_caption(fr, s, y=1640, size=74):
    f = skia.Font(TFB, size)
    parts = [(b.strip("[]"), b.startswith("[")) for b in s.replace("[", "|[").replace("]", "]|").split("|") if b]
    x = (W - sum(f.measureText(p) for p, _ in parts)) / 2
    for p, key in parts:
        blob = skia.TextBlob(p, f)
        fr.c.drawTextBlob(blob, x, y, paint("#000000", stroke=size * 0.2))
        fr.c.drawTextBlob(blob, x, y, paint("#d9a6ff" if key else "#FFFFFF"))
        x += f.measureText(p)


def shot_at(T):
    for s in SHOTS:
        if s[1] <= T < s[2]:
            return s
    return SHOTS[-1]


def render(T, scale=1.0):
    name, t0, t1, fn, opt = shot_at(T)
    fr = Frame(scale)
    res = fn(fr, T, t0, t1)
    if isinstance(res, np.ndarray) or isinstance(res, str):
        arr = res if isinstance(res, np.ndarray) else cctv(fr.array(), T, res)
        fr = Frame(scale)
        img = skia.Image.fromarray(np.ascontiguousarray(np.dstack([arr, np.full(arr.shape[:2], 255, np.uint8)])), colorType=skia.kRGBA_8888_ColorType)
        fr.c.save()
        fr.c.resetMatrix()
        fr.c.drawImage(img, 0, 0)
        fr.c.restore()
    if T - t0 < 0.06 and t0 > 0:
        fr.c.drawRect(skia.Rect(-10, -10, W + 10, H + 10), paint("#ffffff", a=0.35))
    overlay(fr, T, name)
    s = caption(T)
    if s:
        draw_caption(fr, s, *opt.get("cap", (1640, 74)))
    a = fr.array()
    k = min(1.0, max(0.0, (TOTAL - T) / 0.4))
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


def downsample(a):
    h, w = a.shape[0] // 2, a.shape[1] // 2
    return a.astype(np.float32).reshape(h, 2, w, 2, 3).mean((1, 3)).astype(np.uint8)


if __name__ == "__main__":
    a = sys.argv[1:]
    pos = [x for x in a if not x.startswith("--")]
    os.makedirs(OUT, exist_ok=True)
    if "--frame" in a:
        t = float(pos[0])
        Image.fromarray(render(t, float(pos[1]) if len(pos) > 1 else 0.5)[1]).save(os.path.join(OUT, f"_f{t:.2f}.png"))
    elif "--stills" in a:
        tiles = []
        for name, t0, t1, _, _ in SHOTS:
            for t in (t0 + 0.08, (t0 + t1) / 2, t1 - 0.05):
                im = Image.fromarray(render(t, 0.25)[1])
                ImageDraw.Draw(im).text((4, 4), f"{name} {t:.1f}", fill=(255, 255, 0))
                tiles.append(im)
        w, h = tiles[0].size
        sheet = Image.new("RGB", (w * 9, h * ((len(tiles) + 8) // 9)))
        for i, im in enumerate(tiles):
            sheet.paste(im, ((i % 9) * w, (i // 9) * h))
        sheet.save(os.path.join(OUT, "shots.png"))
        print(os.path.join(OUT, "shots.png"))
    elif "--master-part" in a:
        k, n = int(pos[0]), int(pos[1])
        fr = frames_of(0, TOTAL)
        L = -(-len(fr) // n)
        TN.HQ["on"] = True
        encode((downsample(render(t, 2.0)[1]) for t in fr[k * L:(k + 1) * L]), os.path.join(VID, f"_part{k:02d}.mp4"), f"{W}x{H}", crf="12", preset="medium")
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
