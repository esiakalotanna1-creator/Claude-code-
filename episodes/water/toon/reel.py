"""5 SECONDS WITHOUT WATER: a 'what if' explainer reel. Toon characters on a 3D pier plus 2D motion-graphic scenes.

    python reel.py --frame T [scale] | --stills | --preview [--full] | --master-par N
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
for d in (HERE, os.path.join(ROOT, "tools", "toon")):
    sys.path.insert(0, d)
import rig  # noqa: E402
import looks  # noqa: E402,F401  (theo, maya, frank)
import toon as TN  # noqa: E402
from anim import blink  # noqa: E402
from toon import Camera, Frame, W, H, argb, lin, paint, rad, shade  # noqa: E402

FPS = 30
OUT, VID = os.path.join(HERE, "review"), os.path.join(HERE, "video")
TL = json.load(open(os.path.join(HERE, "timeline.json"), encoding="utf-8"))
TOTAL = TL["total"]
B = TL["beats"]
b0 = lambda k: B[k]["t0"]      # noqa: E731
b1 = lambda k: B[k]["t1"]      # noqa: E731
TF, TFB = TN.typeface(False), TN.typeface(True)


def cl(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def sm(u):
    u = cl(u)
    return u * u * (3 - 2 * u)


def text(c, s, x, y, size, colr="#ffffff", stroke=0.0, bold=True, a=1.0, center=True):
    f = skia.Font(TFB if bold else TF, size)
    w = f.measureText(s)
    x0 = x - w / 2 if center else x
    if stroke:
        c.drawString(s, x0, y, f, paint("#000000", a=a, stroke=stroke))
    c.drawString(s, x0, y, f, paint(colr, a=a))
    return w


def ellipse(c, x, y, rx, ry, colr, a=1.0, blur=0.0):
    c.drawOval(skia.Rect(x - rx, y - ry, x + rx, y + ry), paint(colr, a=a, blur=blur))


def grad_bg(c, cols, pos=None):
    c.drawRect(skia.Rect(-10, -10, W + 10, H + 10), paint(shader=lin((0, 0), (0, H), [argb(x) for x in cols], pos)))


# ================================================================================================ the pier (3D, Theo)
SEA = "#2f86c2"


def pier_world(fr, cam, T, water=1.0, sky="day", dust=0.0, hoodie=0.0, cast=(), flicker=1.0):
    c = fr.c
    if sky == "day":
        grad_bg(c, ["#5aa7e8", "#9fd0f2", "#f6e3c4"], [0, 0.55, 1])
    else:
        grad_bg(c, ["#5d6b80", "#8a95a5", "#b9b5aa"], [0, 0.6, 1])
    sx, sy, sd, ss = cam.proj((-40, 30, 300))
    if sd > 0.3 and sky == "day":
        fr.glow(sx, sy, 160, "#fff4d0", a=0.5)
        c.drawCircle(sx, sy, 46, paint("#fff8e6"))
    w = water * flicker
    # the sea floor, far below (seen when the water is gone)
    fr.poly(cam, [(-400, -30, -5), (400, -30, -5), (400, -30, 600), (-400, -30, 600)],
            shader=lambda p: lin((0, p.getBounds().top()), (0, p.getBounds().bottom()), [argb("#3a2a22"), argb("#6e5038")]))
    r = np.random.default_rng(3)
    for i in range(60):                                           # rocks and stranded things on the sea floor
        x, z = r.uniform(-60, 60), r.uniform(4, 120)
        fr.ground_ellipse(cam, x, z, r.uniform(0.6, 2.5), r.uniform(0.5, 1.6), "#2a1d17", 0.6, blur_m=0.3) if False else None
        q = cam.proj((x, -30, z))
        if q[2] > 1 and w < 0.99:
            c.drawOval(skia.Rect(q[0] - 1.2 * q[3], q[1] - 0.4 * q[3], q[0] + 1.2 * q[3], q[1] + 0.4 * q[3]), paint("#2a1d17", a=0.7 * (1 - w)))
    # pier posts reach all the way down
    for z in np.arange(0.6, 12.0, 1.6):
        for x in (-1.15, 1.15):
            fr.box(cam, (x - 0.08, x + 0.08), (-30, 0.95), (z - 0.08, z + 0.08), "#5a4232", line=1.0)
    # the sea
    if w > 0.01:
        fr.poly(cam, [(-400, 0, -5), (400, 0, -5), (400, 0, 600), (-400, 0, 600)], a=w,
                shader=lambda p: lin((0, p.getBounds().top()), (0, p.getBounds().bottom()), [argb("#7fc6e6"), argb(SEA), argb("#1f5f96")], [0, 0.3, 1]))
        for i in range(40):                                       # glints on the waves
            x, z = r.uniform(-30, 30), r.uniform(3, 80)
            q = cam.proj((x + 0.6 * math.sin(T * 0.7 + i), 0.0, z))
            if q[2] > 1:
                c.drawRect(skia.Rect(q[0] - 0.6 * q[3], q[1], q[0] + 0.6 * q[3], q[1] + max(1.0, 0.04 * q[3])), paint("#e6f6ff", a=0.55 * w))
    # the deck
    fr.box(cam, (-1.3, 1.3), (0.85, 1.0), (-2.0, 12.0), "#b0875e", line=1.2)
    for z in np.arange(-2.0, 12.0, 0.35):
        fr.poly(cam, [(-1.3, 1.001, z), (1.3, 1.001, z), (1.3, 1.001, z + 0.012), (-1.3, 1.001, z + 0.012)], colr="#8a6644")
    for z in np.arange(-2.0, 12.0, 1.6):                         # rail posts
        for x in (-1.25, 1.25):
            fr.box(cam, (x - 0.04, x + 0.04), (1.0, 1.95), (z - 0.04, z + 0.04), "#8a6644", line=1.0)
    for x in (-1.25, 1.25):
        fr.box(cam, (x - 0.03, x + 0.03), (1.9, 1.96), (-2.0, 12.0), "#9a7650", line=1.0)
    # what is left of Theo: his hoodie, joggers, shoes, headphones and a little pile of dust
    if hoodie > 0:
        x, z = 0.0, 2.0
        fr.ground_ellipse(cam, x, z, 0.5, 0.45, "#000000", 0.3, blur_m=0.05)
        fr.poly(cam, [(x - 0.35, 1.02, z - 0.2), (x + 0.4, 1.02, z - 0.25), (x + 0.45, 1.06, z + 0.25), (x - 0.3, 1.07, z + 0.3)], colr="#4f8a8b", outline="#2b4b4c", line=2.0)
        fr.poly(cam, [(x - 0.25, 1.03, z - 0.25), (x + 0.2, 1.03, z - 0.25), (x + 0.15, 1.03, z - 0.75), (x - 0.2, 1.03, z - 0.7)], colr="#8b8f99", outline="#4b4f59", line=2.0)
        for sxx in (-0.12, 0.1):
            fr.box(cam, (x + sxx - 0.06, x + sxx + 0.06), (1.0, 1.06), (z - 0.86, z - 0.7), "#e9e9ef", line=1.0)
        q = cam.proj((x + 0.05, 1.08, z + 0.05))
        if q[2] > 0.3:
            ellipse(c, q[0], q[1], 0.28 * q[3], 0.11 * q[3], "#cdb79a", a=dust)
            for k in range(40):
                a = k * 2.4
                rr = (k % 7) / 7 * 0.25 * q[3]
                c.drawCircle(q[0] + math.cos(a) * rr, q[1] + math.sin(a) * rr * 0.4, max(1.0, 0.012 * q[3]), paint("#b39b7d", a=dust))
            hp = cam.proj((x + 0.32, 1.1, z + 0.32))
            c.drawOval(skia.Rect(hp[0] - 0.12 * hp[3], hp[1] - 0.06 * hp[3], hp[0] + 0.12 * hp[3], hp[1] + 0.06 * hp[3]), paint("#24262e", stroke=0.035 * hp[3]))
            for s in (-1, 1):
                ellipse(c, hp[0] + s * 0.12 * hp[3], hp[1], 0.045 * hp[3], 0.035 * hp[3], "#d9583a")
    outs = {}
    for pid, look, pose, held in cast:
        outs[pid] = rig.draw(fr, cam, look, pose, light=(2.0, 6.0, -2.0), held=held)
    return outs


def theo_pose(T, drink=0.0, scared=0.0):
    p = dict(rig.REST, x=0.0, z=2.0, yaw=-15.0, floor=1.0, t=T, breath=0.5 + 0.5 * math.sin(T * 2))
    p.update(lid=0.9 * blink(T, [1.2, 4.1, 7.0, 10.4, 13.3]), smile=0.25 * (1 - scared), brow=0.5 * scared - 0.1, mouth=0.2 * scared,
             gx=0.0, gy=0.0, head_pitch=-10 * drink, aL=(10.0, 8.0, 30.0))
    J = rig.solve("theo", dict(p))
    hx, hy, hz = J["head"]
    mouth = (hx - 0.02, hy - 0.12, hz - 0.17)
    chest = rig.Basis.yaw(-15).w((0, 1.0, 2.0), -0.08, 1.05, 0.32)
    u = sm(drink)
    p["ik_R"] = tuple(a + (b - a) * u for a, b in zip(chest, mouth))
    p["pole_R"] = (-1.0, -0.6, -0.3)
    return p


def cam(pos, tgt, f, hz=0.46):
    return Camera(pos, math.degrees(math.atan2(tgt[0] - pos[0], tgt[2] - pos[2])), f, hz)


def lerp(a, b, u):
    return tuple(x + (y - x) * u for x, y in zip(a, b)) if isinstance(a, tuple) else a + (b - a) * u


# ================================================================================================ 2D scenes
def scene_globe(fr, T, t0, t1, drain):
    c = fr.c
    grad_bg(c, ["#03050f", "#0a1230", "#03050f"])
    r = np.random.default_rng(1)
    for i in range(160):
        c.drawCircle(r.uniform(0, W), r.uniform(0, H), r.uniform(0.6, 2.2), paint("#ffffff", a=r.uniform(0.2, 0.9)))
    cx, cy, R = W / 2, H * 0.47, 400 + 25 * (T - t0)
    fr.glow(cx, cy, R * 1.25, "#5aa0ff", a=0.25 * (1 - drain) + 0.05)
    globe = skia.Path()
    globe.addCircle(cx, cy, R)
    c.save()
    c.clipPath(globe, skia.ClipOp.kIntersect, True)
    ocean = [shade("#2a7fd4", 0.0), "#174e8c"]
    dry = ["#6b4a33", "#3a261a"]
    col0 = TN.mix(ocean[0], dry[0], drain)
    col1 = TN.mix(ocean[1], dry[1], drain)
    c.drawCircle(cx, cy, R, paint(shader=rad((cx - R * 0.3, cy - R * 0.35), R * 1.5, [argb(col0), argb(col1)], [0, 1])))
    if drain > 0:                                                 # trenches and ridges where the sea was
        for i in range(14):
            y = cy - R + (i + 0.5) * 2 * R / 14
            p = skia.Path()
            p.moveTo(cx - R, y)
            for k in range(1, 9):
                p.lineTo(cx - R + k * R / 4, y + 18 * math.sin(k * 1.7 + i))
            c.drawPath(p, paint("#22150e", a=0.5 * drain, stroke=5))
    rot = (T - t0) * 22
    for i in range(7):                                            # continents
        ang = i * 0.9 + 0.4
        x = cx + ((math.cos(ang) * R * 0.75 + rot + i * 210) % (2.4 * R)) - 1.2 * R
        y = cy + math.sin(i * 1.3) * R * 0.55
        pts = [(x + math.cos(a) * R * (0.18 + 0.08 * math.sin(a * 3 + i)), y + math.sin(a) * R * (0.22 + 0.07 * math.cos(a * 2 + i))) for a in np.linspace(0, 2 * math.pi, 14, endpoint=False)]
        path = rig.smooth(pts)
        c.drawPath(path, paint(TN.mix("#4f9a4a", "#8a7a52", drain)))
        c.drawPath(path, paint("#1d3a1a", a=0.5, stroke=3))
    for i in range(10):                                           # clouds blink out
        x = cx + ((i * 173 + rot * 1.6) % (2.2 * R)) - 1.1 * R
        y = cy + math.sin(i * 2.1) * R * 0.75
        ellipse(c, x, y, 90, 26, "#ffffff", a=0.75 * (1 - cl(drain * 3)))
    c.drawCircle(cx, cy, R, paint(shader=rad((cx + R * 0.45, cy + R * 0.3), R * 1.3, [argb("#000000", 0.0), argb("#000000", 0.55)], [0.4, 1])))
    c.restore()
    c.drawCircle(cx, cy, R, paint("#9cc8ff", a=0.5 * (1 - drain), stroke=6))
    text(c, "WATER: %d%%" % round(100 * (1 - drain)), W / 2, H * 0.80, 64, "#ffffff" if drain < 0.5 else "#ff5a4a", stroke=10)


def scene_body(fr, T, t0, t1):
    """Theo on the pier, an x-ray water meter in him, then he dries to dust inside his clothes."""
    c = fr.c
    u = (T - t0) / (t1 - t0)
    level = 1.0 - sm((T - (b0("sixty") + 1.8)) / 1.2)
    gone = sm((T - (b0("sixty") + 2.6)) / 0.8)
    cm = cam((1.1, 1.6, -0.3), (0.0, 1.45, 2.0), 1150 + 150 * u, 0.52)
    pose = theo_pose(T, scared=1.0)
    pier_world(fr, cm, T, water=0.0, sky="day", hoodie=gone, dust=gone)
    c.drawRect(skia.Rect(-10, -10, W + 10, H + 10), paint("#06101e", a=0.45))
    c.saveLayer(None, None)
    o = rig.draw(fr, cm, "theo", pose, light=(2.0, 6.0, -2.0), held={"R": rig.bottle()} if False else None) if gone < 1 else {}
    if gone < 1 and o:                                            # the water inside him, as a blue fill clipped to his body
        top, bot = o["head"][1] - o["head_r"] * 1.1, H * 1.05
        y = bot - (bot - top) * 0.62 * level
        q = skia.Paint(Color=argb("#3aa0ff", 0.42), BlendMode=skia.BlendMode.kSrcATop)
        c.drawRect(skia.Rect(0, y, W, H), q)
        c.drawRect(skia.Rect(0, y - 5, W, y + 5), skia.Paint(Color=argb("#b9e2ff", 0.8), BlendMode=skia.BlendMode.kSrcATop))
        if gone > 0:                                              # drying out
            d = skia.Paint(Color=argb("#d8c2a0", gone), BlendMode=skia.BlendMode.kSrcATop)
            c.drawRect(skia.Rect(0, 0, W, H), d)
    c.restore()
    if gone > 0:                                                  # dust falling out of the clothes
        r = np.random.default_rng(int(T * 3))
        for i in range(int(260 * gone)):
            x = W * 0.5 + r.normal(0, 120)
            y = H * 0.35 + r.uniform(0, H * 0.55) * gone
            c.drawCircle(x, y, r.uniform(1.5, 4.5), paint("#c9b08a", a=0.7 * (1 - 0.5 * gone)))
    pct = round(60 * level)
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect(60, 260, 400, 380), 30, 30), paint("#000000", a=0.55))
    text(c, "BODY WATER", 230, 305, 34, "#9fd6ff")
    text(c, "%d%%" % pct, 230, 365, 60, "#ffffff" if pct > 20 else "#ff5a4a")


def scene_scale(fr, T, t0, t1):
    """'Great for your diet': a bathroom scale with a pile of dust and a hoodie on it, the numbers dropping."""
    c = fr.c
    grad_bg(c, ["#f0e6d8", "#e3d3bf"])
    c.drawRect(skia.Rect(0, H * 0.62, W, H), paint("#cfd8dc"))
    for i in range(12):
        c.drawLine(i * 100, H * 0.62, i * 100, H, paint("#b0bcc2", stroke=3))
    u = sm((T - t0) / 1.4)
    kg = 70 - (70 - 28) * u
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect(W / 2 - 300, H * 0.58, W / 2 + 300, H * 0.80), 50, 50), paint("#f7f7f9"))
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect(W / 2 - 300, H * 0.58, W / 2 + 300, H * 0.80), 50, 50), paint("#9aa3ab", stroke=5))
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect(W / 2 - 150, H * 0.6, W / 2 + 150, H * 0.66), 16, 16), paint("#1d2a33"))
    text(c, "%.1f kg" % kg, W / 2, H * 0.648, 64, "#7dffa0")
    ellipse(c, W / 2 - 40, H * 0.715, 200, 50, "#4f8a8b")                 # the hoodie, collapsed
    ellipse(c, W / 2 + 60, H * 0.705, 110, 40, "#c9b08a")                 # the dust
    for i in range(80):
        a = i * 2.3
        c.drawCircle(W / 2 + 60 + math.cos(a) * (i % 9) * 11, H * 0.705 + math.sin(a) * (i % 9) * 4, 3, paint("#a8906c"))
    text(c, "-60%", W / 2, H * 0.40, 150, "#ff5a4a", stroke=14)
    text(c, "GREAT FOR YOUR DIET", W / 2, H * 0.47, 54, "#222222")


def scene_trees(fr, T, t0, t1):
    c = fr.c
    grad_bg(c, ["#79b8ec", "#cde6f6"])
    c.drawRect(skia.Rect(0, H * 0.66, W, H), paint("#6fae4c"))
    u = sm((T - (t0 + 0.6)) / 1.4)
    c.drawRect(skia.Rect(0, H * 0.66, W, H), paint("#b49a6a", a=u))
    r = np.random.default_rng(2)
    for i in range(6):
        x = 120 + i * 170 + r.uniform(-30, 30)
        base = H * 0.66 + r.uniform(0, 60)
        s = r.uniform(0.8, 1.25)
        k = cl(u * 1.4 - i * 0.07)
        trunk_h = 260 * s * (1 - 0.7 * k)
        c.drawRect(skia.Rect(x - 18 * s, base - trunk_h, x + 18 * s, base), paint(TN.mix("#6b4630", "#8a7558", k)))
        for j in range(3):                                         # canopy, falling apart into dust
            cy = base - trunk_h - 60 * s + j * 50 * s + k * 220 * (j + 1) * 0.5
            rr = (110 - j * 15) * s * (1 - 0.6 * k)
            col = TN.mix("#3f8f3a", "#b9a27a", k)
            ellipse(c, x + (j - 1) * 30 * s, cy, rr, rr * 0.8, col, a=1 - 0.6 * k)
        if k > 0:
            for p in range(60):
                c.drawCircle(x + r.normal(0, 90), base - r.uniform(0, 300) * (1 - k), r.uniform(2, 5), paint("#b9a27a", a=0.6 * k))
    # a houseplant on a table, front and centre (dark humor beat)
    hp = sm((T - (b0("plants") + 3.6)) / 0.8)
    if T > b0("plants") + 2.8:
        a = sm((T - (b0("plants") + 2.8)) / 0.3)
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect(W / 2 - 160, H * 0.78, W / 2 + 160, H * 0.98), 20, 20), paint("#e9e0d2", a=a))
        c.drawRect(skia.Rect(W / 2 - 70, H * 0.70, W / 2 + 70, H * 0.79), paint("#c2643e", a=a))
        for j in range(5):
            ang = -2.4 + j * 0.45
            L = 170 * (1 - 0.8 * hp)
            ex, ey = W / 2 + math.cos(ang) * L, H * 0.70 + math.sin(ang) * L + hp * 100
            c.drawLine(W / 2, H * 0.70, ex, ey, paint(TN.mix("#3f8f3a", "#8a7558", hp), a=a, stroke=16))
            ellipse(c, ex, ey, 40 * (1 - 0.5 * hp), 22, TN.mix("#4fae4a", "#b9a27a", hp), a=a)


def scene_city(fr, T, t0, t1):
    c = fr.c
    grad_bg(c, ["#8fb7dd", "#d9e2ea"])
    u = sm((T - (t0 + 1.2)) / 2.5)
    r = np.random.default_rng(4)
    xs = 0
    blds = []
    while xs < W + 100:
        w = r.uniform(110, 190)
        h = r.uniform(500, 1150)
        blds.append((xs, w, h, r.uniform(0, 0.4)))
        xs += w + r.uniform(4, 20)
    ground = H * 0.88
    for x, w, h, d in blds:
        k = cl((u - d) / 0.6)
        hh = h * (1 - 0.65 * k)
        tilt = 8 * k * (1 if (x // 100) % 2 else -1)
        c.save()
        c.rotate(tilt, x + w / 2, ground)
        c.drawRect(skia.Rect(x, ground - hh, x + w, ground), paint(TN.mix("#6b7c8f", "#a89f92", k)))
        c.drawRect(skia.Rect(x, ground - hh, x + w, ground), paint("#2f3a46", stroke=3))
        for wy in np.arange(ground - hh + 30, ground - 40, 60):
            for wx in np.arange(x + 18, x + w - 30, 38):
                c.drawRect(skia.Rect(wx, wy, wx + 20, wy + 30), paint("#d6ecff" if (wx + wy) % 3 else "#ffe9a8", a=1 - k))
        c.restore()
        if k > 0:
            for p in range(25):
                ellipse(c, x + r.uniform(0, w), ground - hh * r.uniform(0, 1.1), r.uniform(20, 60) * k, r.uniform(14, 40) * k, "#c9bba6", a=0.45 * k)
    c.drawRect(skia.Rect(0, ground, W, H), paint("#4a4a50"))
    c.drawRect(skia.Rect(0, 0, W, H), paint("#c9bba6", a=0.35 * u))


def scene_ship(fr, T, t0, t1, drop_t, back_t=None):
    """Side view: the sea, a ship; the sea vanishes, the ship falls; optionally the walls of water come back."""
    c = fr.c
    grad_bg(c, ["#86c1ec", "#d3ecf8"])
    sea_y = H * 0.40
    floor_y = H * 1.6
    # seabed cross-section (a deep trench)
    tr = skia.Path()
    tr.moveTo(0, sea_y + 40)
    tr.lineTo(200, sea_y + 120)
    tr.lineTo(380, floor_y)
    tr.lineTo(700, floor_y)
    tr.lineTo(880, sea_y + 160)
    tr.lineTo(W, sea_y + 60)
    tr.lineTo(W, H + 400)
    tr.lineTo(0, H + 400)
    tr.close()
    gone = sm((T - drop_t) / 0.35)
    back = sm((T - back_t) / 0.7) if back_t else 0.0
    wl = 1 - gone + back
    if wl > 0.01:                                                  # the water (or its walls rushing back in)
        if back_t and T >= back_t:
            for side in (0, 1):
                wpath = skia.Path()
                x0 = 0 if side == 0 else W
                x1 = W / 2 * back if side == 0 else W - W / 2 * back
                wpath.moveTo(x0, sea_y)
                wpath.lineTo(x1, sea_y - 120 * (1 - back) * math.sin(math.pi * back))
                wpath.lineTo(x1, H + 400)
                wpath.lineTo(x0, H + 400)
                wpath.close()
                c.drawPath(wpath, paint("#1f6fb0", a=0.95))
            if 0.85 < back < 1.0 or back >= 1.0 and T < back_t + 1.2:   # the splash where they meet
                s = cl((T - back_t - 0.6) / 0.6)
                for i in range(40):
                    a = -math.pi * (0.1 + 0.8 * i / 40)
                    rr = 500 * s
                    ellipse(c, W / 2 + math.cos(a) * rr * 0.6, sea_y + math.sin(a) * rr, 40 * (1 - s) + 10, 28 * (1 - s) + 8, "#e8f6ff", a=1 - s)
        else:
            c.drawRect(skia.Rect(0, sea_y, W, H + 400), paint(shader=lin((0, sea_y), (0, H), [argb("#4aa3dc"), argb("#0d3a6b")]), a=1 - gone))
    c.drawPath(tr, paint("#5b4130"))
    c.drawPath(tr, paint("#2c1d14", stroke=6))
    # the ship
    fall = max(0.0, T - drop_t) if not back_t or T < back_t else max(0.0, back_t - drop_t)
    y = sea_y - 70 + 0.5 * 9.81 * min(fall, 5.0) ** 2 * 3.0
    sx = W / 2
    c.save()
    c.rotate(min(12.0, fall * 6), sx, y)
    hull = skia.Path()
    hull.moveTo(sx - 230, y)
    hull.lineTo(sx + 230, y)
    hull.lineTo(sx + 170, y + 90)
    hull.lineTo(sx - 190, y + 90)
    hull.close()
    c.drawPath(hull, paint("#c0392b"))
    c.drawPath(hull, paint("#1b1b1b", stroke=5))
    for i, col in enumerate(("#2e86de", "#f39c12", "#27ae60", "#8e44ad", "#16a085")):
        c.drawRect(skia.Rect(sx - 200 + i * 75, y - 60, sx - 130 + i * 75, y), paint(col))
        c.drawRect(skia.Rect(sx - 200 + i * 75, y - 60, sx - 130 + i * 75, y), paint("#1b1b1b", stroke=3))
    c.drawRect(skia.Rect(sx + 170, y - 110, sx + 220, y), paint("#ecf0f1"))
    c.restore()
    if fall > 0 and (not back_t or T < back_t + 0.2):
        m = 0.5 * 9.81 * min(fall, 5.0) ** 2
        c.drawLine(120, sea_y - 20, 120, y + 20, paint("#ffffff", stroke=6))
        text(c, "%d m" % m, 220, (sea_y + y) / 2, 60, "#ffffff", stroke=10)


def scene_sky(fr, T, t0, t1):
    c = fr.c
    u = sm((T - (t0 + 0.6)) / 1.0)
    grad_bg(c, [TN.mix("#6f9fd0", "#1f63c9", u), TN.mix("#b9d4ea", "#5aa7f0", u)])
    r = np.random.default_rng(6)
    for i in range(12):
        x, y = r.uniform(-100, W + 100), r.uniform(100, H * 0.75)
        s = r.uniform(0.7, 1.5)
        pop = cl(u * 1.6 - r.uniform(0, 0.6))
        a = 1 - pop
        if a <= 0:
            continue
        for k in range(4):
            ellipse(c, x + (k - 1.5) * 70 * s, y + (k % 2) * 20 * s, 90 * s * (1 + 0.2 * pop), 55 * s, "#ffffff", a=0.9 * a)
    fr.glow(W * 0.75, H * 0.2, 220, "#fff6d8", a=0.5)
    c.drawCircle(W * 0.75, H * 0.2, 70, paint("#fffbe9"))
    if u < 0.4:                                                     # rain streaks freeze and vanish
        for i in range(120):
            x, y = r.uniform(0, W), r.uniform(0, H)
            c.drawLine(x, y, x - 6, y + 40, paint("#e0ecff", a=0.5 * (1 - u / 0.4), stroke=2))


def tardigrade(c, x, y, s, T, wake, shake):
    """A cute water bear: a plump segmented body, eight stubby legs, a round little mouth, big eyes."""
    jig = 8 * shake * math.sin(T * 40)
    c.save()
    c.translate(x + jig, y)
    c.scale(s, s)
    for i, lx in enumerate((-110, -40, 40, 110)):
        for sgn in (-1, 1):
            kick = 10 * math.sin(T * 6 + i) * wake
            c.drawRoundRect(skia.Rect(lx - 20, 40 + kick * (sgn > 0), lx + 20, 100 + kick * (sgn > 0)), 18, 18, paint("#c9a9a0" if sgn > 0 else "#b29188"))
            for cl_ in range(3):
                c.drawLine(lx - 12 + cl_ * 12, 98, lx - 14 + cl_ * 12, 112, paint("#5a4038", stroke=4))
    body = skia.RRect.MakeRectXY(skia.Rect(-170, -70, 170, 70), 70, 70)
    c.drawRRect(body, paint(shader=lin((0, -70), (0, 70), [argb("#f1d6cc"), argb("#c9a9a0")])))
    for i in range(1, 5):
        c.drawLine(-170 + i * 68, -66, -170 + i * 68, 66, paint("#b29188", stroke=4, a=0.6))
    c.drawRRect(body, paint("#5a4038", stroke=6))
    hx = -150
    lid = 0.15 + 0.85 * wake
    for ex in (-28, 18):
        c.drawOval(skia.Rect(hx + ex - 16, -36, hx + ex + 16, -36 + 34 * lid), paint("#1a1214"))
        if lid > 0.3:
            c.drawCircle(hx + ex - 5, -26, 5, paint("#ffffff"))
    c.drawCircle(hx - 20, 18, 14, paint("#7a4a44"))
    c.drawCircle(hx - 20, 18, 8, paint("#3a1a18"))
    c.drawOval(skia.Rect(hx + 10, -6, hx + 40, 10), paint("#ff9aa0", a=0.5))
    c.restore()


def scene_tardi(fr, T, t0, t1):
    c = fr.c
    grad_bg(c, ["#8a95a5", "#c9c2b5"])
    c.drawRect(skia.Rect(0, H * 0.62, W, H), paint("#9a7650"))
    for i in range(10):
        c.drawLine(0, H * 0.62 + i * 80, W, H * 0.62 + i * 80, paint("#7a5a3a", stroke=5))
    ellipse(c, W * 0.42, H * 0.70, 380, 90, "#cdb79a")                         # the dust pile
    r = np.random.default_rng(9)
    for i in range(300):
        ellipse(c, W * 0.42 + r.normal(0, 160), H * 0.70 + r.normal(0, 36), 4, 3, "#b39b7d")
    wake = sm((T - (b0("tardi") + 2.0)) / 0.8)
    shake = 1.0 if b0("tardi") + 2.8 < T < b0("tardi") + 3.6 else 0.0
    rise = sm((T - (b0("tardi") + 1.0)) / 1.0)
    tardigrade(c, W * 0.46, H * 0.70 - 60 * rise, 1.2, T, wake, shake)
    if shake:
        for i in range(60):
            a = r.uniform(0, 2 * math.pi)
            rr = r.uniform(150, 320)
            c.drawCircle(W * 0.46 + math.cos(a) * rr, H * 0.66 + math.sin(a) * rr * 0.5, 5, paint("#cdb79a", a=0.8))
    # Theo's headphones beside it; the water bear crawls into them at the end
    hp = sm((T - b0("planet")) / 1.2)
    hx, hy = W * 0.78 - 200 * hp, H * 0.74 - 140 * hp
    c.drawOval(skia.Rect(hx - 140, hy - 70, hx + 140, hy + 70), paint("#24262e", stroke=26))
    for s in (-1, 1):
        ellipse(c, hx + s * 140, hy + 10, 48, 60, "#24262e")
        ellipse(c, hx + s * 140, hy + 10, 26, 34, "#d9583a")


# ================================================================================================ shots
def pier_shot(camf, **kw):
    def fn(fr, T, t0, t1):
        u = (T - t0) / max(1e-6, t1 - t0)
        cm = camf(u)
        cast = kw.get("cast", lambda T: [])(T)
        pier_world(fr, cm, T, water=kw.get("water", lambda T: 1.0)(T), sky=kw.get("sky", "day"), dust=kw.get("dust", 0.0),
                   hoodie=kw.get("hoodie", 0.0), cast=cast, flicker=kw.get("flicker", lambda T: 1.0)(T))
    return fn


def hook_flicker(T):
    """The ocean blinks out for a few frames on 'disappeared', a glitch that previews the whole video."""
    d = b0("hook") + 2.9
    return 0.0 if (d < T < d + 0.12 or d + 0.25 < T < d + 0.33) else 1.0


def theo_cast(drink_t0=None, scared=0.0):
    def f(T):
        dr = sm((T - drink_t0) / 0.8) if drink_t0 else 0.0
        return [("theo", "theo", theo_pose(T, drink=dr, scared=scared), {"R": rig.bottle()})]
    return f


def wide_pier(u):
    return cam(lerp((1.2, 1.7, -0.6), (0.9, 1.72, -0.1), sm(u)), (0.0, 1.5, 3.0), 1450, 0.50)


def high_pier(u):
    return cam(lerp((2.2, 4.2, -1.0), (2.0, 4.6, -0.6), sm(u)), (0.0, -6.0, 9.0), 1100, 0.12)


SHOTS = [
    ("HOOK", 0.0, b0("s1"), pier_shot(wide_pier, cast=theo_cast(0.8), flicker=hook_flicker), {}),
    ("GLOBE", b0("s1"), b0("you"), lambda fr, T, t0, t1: scene_globe(fr, T, t0, t1, sm((T - (b0("gone") - 0.1)) / 1.2)), {}),
    ("BODY", b0("you"), b0("diet") - 0.1, scene_body, {}),
    ("SCALE", b0("diet") - 0.1, b0("s2"), scene_scale, dict(cap=(1780, 66))),
    ("TREES", b0("s2"), b0("s3"), scene_trees, {}),
    ("CITY", b0("s3"), b0("ships"), scene_city, {}),
    ("SHIP", b0("ships"), b0("s4"), lambda fr, T, t0, t1: scene_ship(fr, T, t0, t1, b0("ships") + 1.2), {}),
    ("SKY", b0("s4"), b0("s5"), scene_sky, {}),
    ("BACK", b0("s5"), b0("after"), lambda fr, T, t0, t1: scene_ship(fr, T, t0, t1, t0 - 6.0, back_t=b0("back") + 0.3), {}),
    ("EMPTY", b0("after"), b0("but"), pier_shot(lambda u: cam(lerp((0.9, 2.1, 0.5), (0.7, 2.0, 0.8), sm(u)), (0.0, 1.0, 2.0), 1500, 0.22), sky="grey",
                                               dust=1.0, hoodie=1.0), {}),
    ("DRY", b0("but"), b0("tardi"), pier_shot(high_pier, sky="grey", hoodie=1.0, dust=1.0), {}),
    ("TARDI", b0("tardi"), TOTAL, scene_tardi, {}),
]


# ---- overlays: the countdown and captions -----------------------------------------------------------------------
SECS = ["s1", "s2", "s3", "s4", "s5"]


def overlay(fr, T, name):
    c = fr.c
    if T < b0("s1"):                                                # the title card on the hook
        a = sm(T / 0.4)
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect(W / 2 - 150, 150, W / 2 + 150, 215), 32, 32), paint("#ff3b30", a=a))
        text(c, "WHAT IF", W / 2, 198, 46, "#ffffff", a=a)
        text(c, "WATER DISAPPEARED", W / 2, 320, 84, "#ffffff", stroke=14, a=a)
        text(c, "FOR 5 SECONDS?", W / 2, 420, 84, "#3fb6ff", stroke=14, a=a)
    k = sum(1 for s in SECS if T >= b0(s))
    if 1 <= k and T < b0("after"):                                  # the timer pill, counting up through the 5 seconds
        sec = min(5.0, k - 1 + cl((T - b0(SECS[k - 1])) / ((b0(SECS[k]) if k < 5 else b0("after")) - b0(SECS[k - 1]))))
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect(W / 2 - 190, 120, W / 2 + 190, 230), 55, 55), paint("#000000", a=0.65))
        text(c, "00:0%d.%d" % (int(sec), int((sec % 1) * 10)), W / 2, 200, 74, "#ff5a4a" if k == 5 else "#ffffff")
        for i in range(5):
            c.drawCircle(W / 2 - 120 + i * 60, 260, 14, paint("#ff5a4a" if i < k else "#ffffff", a=0.9 if i < k else 0.35))
        st = b0(SECS[k - 1])
        if st <= T < st + 0.9:                                      # "SECOND N" punch-in
            p = (T - st) / 0.9
            s = 1.4 - 0.4 * sm(p * 3)
            a = min(1.0, (0.9 - (T - st)) / 0.3)
            c.save()
            c.scale(s, s)
            text(c, "SECOND %d" % k, W / 2 / s, H * 0.45 / s, 130, "#ffffff", stroke=18, a=a)
            c.restore()
    if T >= b1("planet") + 0.1:
        a = sm((T - b1("planet") - 0.1) / 0.4)
        text(c, "5 SECONDS.", W / 2, H * 0.30, 120, "#ffffff", stroke=16, a=a)
        text(c, "THAT'S ALL IT TAKES.", W / 2, H * 0.36, 60, "#3fb6ff", stroke=10, a=a)


CHUNKS = sorted([c for L in TL["lines"] for c in L["chunks"]], key=lambda c: c["t0"])


def caption(T):
    cur = None
    for c in CHUNKS:
        if c["t0"] <= T + 1e-6:
            cur = c
    return cur["text"] if cur and T < cur["t1"] + 0.3 else None


def draw_caption(fr, s, y=1640, size=76):
    f = skia.Font(TFB, size)
    parts = [(b.strip("[]"), b.startswith("[")) for b in s.replace("[", "|[").replace("]", "]|").split("|") if b]
    x = (W - sum(f.measureText(p) for p, _ in parts)) / 2
    for p, key in parts:
        blob = skia.TextBlob(p, f)
        fr.c.drawTextBlob(blob, x, y, paint("#000000", stroke=size * 0.2))
        fr.c.drawTextBlob(blob, x, y, paint("#FFD23F" if key else "#FFFFFF"))
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
    if T - t0 < 0.08 and t0 > 0:                                    # a white flash on every cut (TikTok punch)
        fr.c.drawRect(skia.Rect(-10, -10, W + 10, H + 10), paint("#ffffff", a=0.5 * (1 - (T - t0) / 0.08)))
    overlay(fr, T, name)
    s = caption(T)
    if s:
        draw_caption(fr, s, *opt.get("cap", (1640, 76)))
    a = fr.array()
    k = min(1.0, max(0.0, (TOTAL - T) / 0.35))
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
            for t in (t0 + 0.05, (t0 + t1) / 2, t1 - 0.05):
                im = Image.fromarray(render(t, 0.25)[1])
                ImageDraw.Draw(im).text((4, 4), f"{name} {t:.1f}", fill=(255, 255, 0))
                tiles.append(im)
        w, h = tiles[0].size
        sheet = Image.new("RGB", (w * 9, h * ((len(tiles) + 8) // 9)))
        for i, im in enumerate(tiles):
            sheet.paste(im, ((i % 9) * w, (i // 9) * h))
        sheet.save(os.path.join(OUT, "shots.png"))
        print(os.path.join(OUT, "shots.png"))
    elif "--preview" in a:
        full = "--full" in a
        encode((render(t, 1.0 if full else 0.5)[1] for t in frames_of(0, TOTAL)), os.path.join(OUT, "reel_preview.mp4"), "1080x1920" if full else "540x960", crf="20", preset="veryfast")
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
