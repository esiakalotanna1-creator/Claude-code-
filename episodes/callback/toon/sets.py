"""The two homes of LEAVE A MESSAGE, both on the same rainy night city. World units are metres, y up.

FLAT (Maya): a small high-floor apartment. Cameras mostly look toward +z.
    x -2.2 .. 2.2, z -3 .. 3, ceiling 2.6. Back wall (z = 3): a wide window over the city with a cushioned window
    seat under it. Left wall: bookshelf, the floor lamp, a sofa along it (facing +x). Right: kitchen counter with
    the kettle and mugs. Dad's photo stands on the window seat's end. A wall clock left of the window.
    Light: the city's blue through the glass (cool environment), the floor lamp (warm practical), the small
    under-cabinet strip in the kitchen (warm), and her phone screen (a cool key on her face when lit).

ROOM (Theo): a teenager's bedroom in a terraced house.
    x -2 .. 2, z -3 .. 3, ceiling 2.5. Back wall: a window onto the wet street (houses opposite, a street lamp),
    fairy lights along the top of the wall. Right wall: desk with a bendy lamp, laptop, mugs, books; a desk chair.
    Left wall: bed with a rumpled duvet, posters above it. A door at the front left.
    Light: the night blue from the window, the desk lamp (warm key), the laptop (cool), the fairy lights.

Each world: draw(fr, cam, T, cast) -> {pid: rig.draw result}; cast is [(pid, look, pose, held)] supplied by the
acting. Everything is a function of T.
"""
import math
import os
import sys

import numpy as np
import skia

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
for _d in (HERE, os.path.join(ROOT, "tools", "toon")):
    if _d not in sys.path:
        sys.path.insert(0, _d)
import rig  # noqa: E402
import looks  # noqa: E402,F401
from toon import H, W, Rain, argb, lin, paint, rad, shade  # noqa: E402

WARM, COOL, CITY = "#ffcf8f", "#9fb6e8", "#7f97d8"


# ---- small helpers ---------------------------------------------------------------------------------------------
def win(T, a, b):
    u = min(1.0, max(0.0, (T - a) / max(1e-6, b - a)))
    return u * u * (3 - 2 * u)


def glow3(fr, cam, P, r_m, colr, a):
    """A small additive glow at a world point (skipped when the point is behind or at the lens)."""
    x, y, d, s = cam.proj(P)
    if d > 0.3 and a > 0.003:
        fr.glow(x, y, max(2.0, r_m * s), colr, a=a)


def quad(fr, cam, pts, colr, **kw):
    fr.poly(cam, pts, colr=colr, **kw)


def wall_rect(fr, cam, axis, at, a0, a1, y0, y1, colr, eps=0.0, **kw):
    """A rectangle flat on a wall. axis 'z': on the plane z = at, spanning x a0..a1. axis 'x': plane x = at, z a0..a1."""
    if axis == "z":
        pts = [(a0, y0, at - eps), (a1, y0, at - eps), (a1, y1, at - eps), (a0, y1, at - eps)]
    else:
        pts = [(at - eps, y0, a0), (at - eps, y0, a1), (at - eps, y1, a1), (at - eps, y1, a0)]
    fr.poly(cam, pts, colr=colr, **kw)
    return pts


def clip_to(fr, cam, pts):
    path = skia.Path()
    q = [cam.proj(p) for p in pts]
    if min(v[2] for v in q) < 0.05:
        return False
    for i, v in enumerate(q):
        (path.moveTo if i == 0 else path.lineTo)(v[0], v[1])
    path.close()
    fr.c.save()
    fr.c.clipPath(path, skia.ClipOp.kIntersect, True)
    return True


def seated(look, x, z, yaw, seat_y, feet_fwd, feet_y=None, **kw):
    """A sitting pose: pelvis at the seat height, ankles in front on the floor (or on feet_y)."""
    h = rig.LOOK[look]["h"]
    p = dict(rig.REST, x=x, z=z, yaw=yaw, crouch=0.47 - (seat_y + 0.06) / h)
    p.update(kw)
    Bb = rig.Basis.yaw(yaw)
    fy = 0.035 * h if feet_y is None else feet_y
    p["ankle_R"] = Bb.w((x, 0, z), 0.065 * h, fy, feet_fwd)
    p["ankle_L"] = Bb.w((x, 0, z), -0.065 * h, fy, feet_fwd)
    p["plant"] = "both" if feet_y is None else "none"
    return p


def grade(fr, o, tint, keys):
    """Light on a person, drawn inside their own layer: a cool night tint everywhere but the face, then soft keys
    on the face. keys = [(colour, strength, dx, dy)] with the offset in head radii (where the light comes from)."""
    if o.get("culled") or not o.get("head"):
        return
    hx, hy = o["head"][:2]
    r = max(8.0, o["head_r"])
    p = skia.Paint()
    p.setBlendMode(skia.BlendMode.kModulate)
    p.setShader(rad((hx, hy), r * 6.0, [argb("#ffffff"), argb("#ffffff"), argb(tint)], [0, 0.22, 1]))
    fr.c.drawPaint(p)
    for col, k, dx, dy in keys:
        if k <= 0.004:
            continue
        q = skia.Paint()
        q.setBlendMode(skia.BlendMode.kSrcATop)
        q.setShader(rad((hx + dx * r, hy + dy * r), r * 2.2, [argb(col, k), argb(col, k * 0.55), argb(col, 0)], [0, 0.5, 1]))
        fr.c.drawPaint(q)


def draw_people(fr, cam, T, cast, items, light, grade_fn):
    outs = {}
    for pid, look, pose, held in cast:
        def person(_fr, pid=pid, look=look, pose=pose, held=held):
            fr.c.saveLayer(None, None)
            outs[pid] = rig.draw(fr, cam, look, pose, light=light, held=held)
            grade_fn(fr, T, pid, outs[pid])
            fr.c.restore()
        items.append((cam.view(rig.solve(look, pose)["pelvis"])[2], person))
    for _, fn in sorted(items, key=lambda q: -q[0]):
        fn(fr)
    return outs


# ---- the city seen through a window -----------------------------------------------------------------------------
class City:
    """Towers across the river: boxes with lit window grids, far below and away; a wet haze; rain in front."""

    def __init__(self, seed, base_y, z0, z1, x0, x1, n, hmin, hmax, rain_box):
        r = np.random.default_rng(seed)
        self.blocks = []
        for i in range(n):
            z = r.uniform(z0, z1)
            w = r.uniform(2.5, 6.0)
            x = r.uniform(x0, x1)
            h = r.uniform(hmin, hmax) * (0.6 + 0.4 * (z - z0) / (z1 - z0))
            lit = r.random((12, 40)) < 0.28
            warm = r.random((12, 40)) < 0.7
            self.blocks.append((x, z, w, h, lit, warm, r.uniform(-0.06, 0.06)))
        self.blocks.sort(key=lambda b: -b[1])
        self.base = base_y
        self.rain = Rain(n=420, box=rain_box, speed=6.5, seed=seed + 1)

    def draw(self, fr, cam, T, sky=("#0d1430", "#2a3463", "#4a4a78")):
        # sky: a dark top, a low orange-purple city glow at the horizon
        fr.c.drawRect(skia.Rect(-10, -10, W + 10, H + 10), paint(shader=lin((0, 0), (0, H), [argb(sky[0]), argb(sky[1]), argb(sky[2])], [0, 0.55, 1])))
        for x, z, w, h, lit, warm, tone in self.blocks:
            far = min(1.0, (z - 8) / 40)
            col = shade("#1b2246", -0.1 + 0.25 * far + tone)
            y0, y1 = self.base, self.base + h
            fr.box(cam, (x - w / 2, x + w / 2), (y0, y1), (z, z + w * 0.8), col, line=0.0)
            cols, rows = max(2, int(w / 0.9)), max(2, int(h / 1.1))
            for i in range(min(cols, 40)):
                for j in range(min(rows, 12)):
                    if not lit[j % 12, i % 40]:
                        continue
                    wx = x - w / 2 + (i + 0.5) * w / cols
                    wy = y0 + (j + 0.5) * h / rows
                    q = cam.proj((wx, wy, z - 0.01))
                    if q[2] < 1:
                        continue
                    s = q[3] * 0.32
                    c = "#ffd79a" if warm[j % 12, i % 40] else "#bfd4ff"
                    fr.c.drawRect(skia.Rect(q[0] - s * 0.5, q[1] - s * 0.6, q[0] + s * 0.5, q[1] + s * 0.6), paint(c, a=0.55 - 0.3 * far))
        fr.c.drawRect(skia.Rect(-10, -10, W + 10, H + 10), paint(shader=lin((0, H * 0.3), (0, H), [argb("#2b2d55", 0.0), argb("#463e6a", 0.35)], [0, 1])))
        self.rain.draw(fr, cam, T, colr=(0.75, 0.82, 0.98), amax=0.35, wmax=2.0)


def glass_drops(fr, cam, T, plane, seed=4, n=60):
    """Raindrops on a window: a few run down slowly, the rest sit. plane = (axis, at, a0, a1, y0, y1)."""
    axis, at, a0, a1, y0, y1 = plane
    r = np.random.default_rng(seed)
    for i in range(n):
        a = r.uniform(a0, a1)
        y = r.uniform(y0, y1)
        sp = r.uniform(0.0, 0.06) if r.random() < 0.3 else 0.0
        yy = y0 + (y - y0 - sp * T) % (y1 - y0)
        P = (a, yy, at - 0.005) if axis == "z" else (at - 0.005, yy, a)
        q = cam.proj(P)
        if q[2] < 0.3:
            continue
        rr = max(0.8, q[3] * r.uniform(0.004, 0.009))
        fr.c.drawCircle(q[0], q[1], rr, paint("#cfdcff", a=0.35))
        fr.c.drawCircle(q[0] - rr * 0.3, q[1] - rr * 0.3, rr * 0.35, paint("#ffffff", a=0.5))
        if sp > 0:
            t = cam.proj((P[0], P[1] + 0.06, P[2]) if axis == "z" else (P[0], P[1] + 0.06, P[2]))
            fr.c.drawLine(q[0], q[1], t[0], t[1], paint("#cfdcff", a=0.18, stroke=rr * 0.8))


# =================================================================================================================
# Maya's flat
# =================================================================================================================
class Flat:
    X0, X1, Z0, Z1, HT = -2.2, 2.2, -3.0, 3.0, 2.6
    WIN = ((-1.15, 1.15), (0.62, 2.30))            # back-wall window: x span, y span
    SEAT = ((-1.25, 1.25), (0.0, 0.40), (2.38, 3.0))
    LAMP = (-1.75, 1.55, 2.45)                     # floor-lamp shade centre
    KITCH = ((1.45, 2.2), (0.0, 0.92), (-1.2, 1.4))
    SOFA = ((-2.2, -1.35), (0.0, 0.45), (-0.4, 1.7))
    WALL, FLOOR = "#3a3f5e", "#4a3a36"

    def __init__(self, day=False):
        self.day = day
        self.city = City(11, -26.0, 14, 70, -40, 40, 70, 10, 46, rain_box=((-3, 3), (-2, 4.5), (3.4, 9)))
        self.near_rain = Rain(n=260, box=((-1.6, 1.6), (0.3, 2.8), (3.04, 3.9)), speed=6.5, seed=31)
        self.props = []                     # [(kind, (x, y, z), lit)] loose phones etc., set per frame by the shot

    def lamp_level(self, T):
        return 1.0

    def shell(self, fr, cam, T):
        X0, X1, Z0, Z1, HT = self.X0, self.X1, self.Z0, self.Z1, self.HT
        (wx0, wx1), (wy0, wy1) = self.WIN
        # outside first (clipped to the window), then the room around it
        outside = cam.pos[2] > Z1
        if outside:                                                              # looking in from the rain
            fr.c.drawRect(skia.Rect(-10, -10, W + 10, H + 10), paint("#0b1026"))
        elif clip_to(fr, cam, [(wx0, wy0, Z1), (wx1, wy0, Z1), (wx1, wy1, Z1), (wx0, wy1, Z1)]):
            if self.day:
                fr.c.drawRect(skia.Rect(-10, -10, W + 10, H + 10), paint(shader=lin((0, 0), (0, H), [argb("#f2b37a"), argb("#f6d3a0"), argb("#c98a6a")], [0, 0.5, 1])))
                glow3(fr, cam, (-6.0, 4.0, 30.0), 9.0, "#fff1c9", 0.5)
            else:
                self.city.draw(fr, cam, T)
            fr.c.restore()
        wall = self.WALL
        back = lambda path: lin((0, path.getBounds().top()), (0, path.getBounds().bottom()), [argb(shade(wall, -0.3)), argb(wall), argb(shade(wall, -0.15))], [0, 0.6, 1])  # noqa: E731
        for pts in ([(X0, 0, Z1), (wx0, 0, Z1), (wx0, HT, Z1), (X0, HT, Z1)], [(wx1, 0, Z1), (X1, 0, Z1), (X1, HT, Z1), (wx1, HT, Z1)],
                    [(wx0, 0, Z1), (wx1, 0, Z1), (wx1, wy0, Z1), (wx0, wy0, Z1)], [(wx0, wy1, Z1), (wx1, wy1, Z1), (wx1, HT, Z1), (wx0, HT, Z1)]):
            fr.poly(cam, pts, shader=back)
        fr.poly(cam, [(X0, 0, Z0), (X1, 0, Z0), (X1, 0, Z1), (X0, 0, Z1)], colr=self.FLOOR)
        for i in range(-14, 16):                                                # floorboards along z
            x = i * 0.16
            fr.poly(cam, [(x, 0, Z0), (x + 0.008, 0, Z0), (x + 0.008, 0, Z1), (x, 0, Z1)], colr=shade(self.FLOOR, -0.25))
        fr.poly(cam, [(X0, HT, Z0), (X1, HT, Z0), (X1, HT, Z1), (X0, HT, Z1)], colr=shade(wall, -0.55))
        fr.poly(cam, [(X0, 0, Z0), (X0, 0, Z1), (X0, HT, Z1), (X0, HT, Z0)], colr=shade(wall, -0.12))
        fr.poly(cam, [(X1, 0, Z0), (X1, 0, Z1), (X1, HT, Z1), (X1, HT, Z0)], colr=shade(wall, -0.25))
        fr.poly(cam, [(-1.5, 0.001, 0.2), (1.1, 0.001, 0.2), (1.1, 0.001, 2.3), (-1.5, 0.001, 2.3)], colr="#5c4b6b")       # rug
        fr.poly(cam, [(-1.38, 0.002, 0.32), (0.98, 0.002, 0.32), (0.98, 0.002, 2.18), (-1.38, 0.002, 2.18)], colr="#6e5a7c",
                outline=shade("#5c4b6b", -0.4), line=2.0)
        # window frame, sill, mullions, drops on the glass
        fr.box(cam, (wx0 - 0.08, wx1 + 0.08), (wy0 - 0.06, wy0), (Z1 - 0.12, Z1 + 0.02), "#d9d2c4", line=1.5)
        for a, b in (((wx0 - 0.06, wy0), (wx0, wy1)), ((wx1, wy0), (wx1 + 0.06, wy1)), ((wx0 - 0.06, wy1), (wx1 + 0.06, wy1 + 0.06)),
                     ((-0.02, wy0), (0.02, wy1)), ((wx0, 1.62), (wx1, 1.66))):
            quad(fr, cam, [(a[0], a[1], Z1 - 0.01), (b[0], a[1], Z1 - 0.01), (b[0], b[1], Z1 - 0.01), (a[0], b[1], Z1 - 0.01)], "#e3ddd0")
        if not self.day:
            glass_drops(fr, cam, T, ("z", Z1 - 0.012, wx0, wx1, wy0, wy1), seed=5, n=70)
        # wall clock, left of the window: 11:00
        cx, cy, cd, cs = cam.proj((-1.62, 2.02, Z1 - 0.01))
        if cd > 0.3:
            fr.c.drawCircle(cx, cy, 0.15 * cs, paint("#efe8da"))
            fr.c.drawCircle(cx, cy, 0.15 * cs, paint("#2a2422", stroke=0.018 * cs))
            fr.c.drawLine(cx, cy, cx, cy - 0.11 * cs, paint("#2a2422", stroke=0.012 * cs))
            fr.c.drawLine(cx, cy, cx - 0.04 * cs, cy - 0.06 * cs, paint("#2a2422", stroke=0.016 * cs))
        # framed print on the right of the back wall
        wall_rect(fr, cam, "z", Z1, 1.45, 2.05, 1.35, 2.05, "#1f2438", eps=0.01, outline="#c9b48a", line=3.0)
        wall_rect(fr, cam, "z", Z1, 1.52, 1.98, 1.42, 1.98, "#c76d4a", eps=0.012)
        wall_rect(fr, cam, "z", Z1, 1.52, 1.98, 1.42, 1.66, "#2e5a6b", eps=0.013)

    def furniture(self, cam, T):
        """[(depth, draw_fn)] for everything that people can stand in front of or behind."""
        it = []
        S = self.SEAT

        def seat(fr):
            fr.box(cam, S[0], S[1], S[2], "#d8d0c0", line=1.5)
            fr.box(cam, (S[0][0] + 0.03, S[0][1] - 0.03), (S[1][1], S[1][1] + 0.09), (S[2][0] + 0.02, S[2][1] - 0.04), "#6f7fa8", line=1.5)
            for x, c in ((-0.95, "#d9a25a"), (-0.62, "#c4556a"), (0.95, "#8fb39a")):       # cushions against the glass
                fr.box(cam, (x - 0.16, x + 0.16), (0.49, 0.79), (2.82, 2.95), c, line=1.5)
            # Dad's photo on the end of the seat
            fr.box(cam, (0.62, 0.84), (0.49, 0.77), (2.86, 2.9), "#3b2a22", line=1.2)
            quad(fr, cam, [(0.645, 0.52, 2.855), (0.815, 0.52, 2.855), (0.815, 0.74, 2.855), (0.645, 0.74, 2.855)], "#e9b880")
            fr.ground_ellipse(cam, 0.0, 2.6, 1.4, 0.5, "#000000", 0.32, blur_m=0.12)
        it.append((cam.view((0, 0.3, 2.7))[2], seat))

        def lamp(fr):
            x, y, z = self.LAMP
            fr.ground_ellipse(cam, x, z, 0.25, 0.25, "#000000", 0.35, blur_m=0.06)
            fr.box(cam, (x - 0.14, x + 0.14), (0, 0.04), (z - 0.14, z + 0.14), "#2a2a30")
            fr.box(cam, (x - 0.015, x + 0.015), (0.04, y - 0.12), (z - 0.015, z + 0.015), "#2a2a30")
            shade_pts = [(x - 0.22, y - 0.14, z), (x + 0.22, y - 0.14, z), (x + 0.15, y + 0.14, z), (x - 0.15, y + 0.14, z)]
            fr.poly(cam, shade_pts, colr="#f3dcae", outline="#a58a5c", line=2.0)
            glow3(fr, cam, (x, y - 0.05, z - 0.05), 0.6, WARM, 0.35)
            fr.ground_ellipse(cam, x + 0.3, z - 0.3, 1.5, 1.3, WARM, 0.16, blur_m=0.4, add=True)
        it.append((cam.view((self.LAMP[0], 0.8, self.LAMP[2]))[2], lamp))

        def shelf(fr):
            x0 = self.X0
            fr.box(cam, (x0, x0 + 0.32), (0, 2.0), (1.85, 2.75), "#5a4334", line=1.5)
            for j, yy in enumerate((0.45, 0.9, 1.35, 1.8)):
                fr.box(cam, (x0 + 0.3, x0 + 0.33), (yy - 0.02, yy), (1.85, 2.75), "#4a372a")
                r = np.random.default_rng(j)
                zz = 1.9
                while zz < 2.66:
                    w = r.uniform(0.03, 0.06)
                    hh = r.uniform(0.22, 0.34)
                    fr.box(cam, (x0 + 0.06, x0 + 0.28), (yy, yy + hh), (zz, zz + w), ["#9a4a3a", "#3e5a7a", "#c9a45a", "#5b7a52", "#d7cfc0"][int(r.integers(5))], line=1.0)
                    zz += w + 0.005
        it.append((cam.view((self.X0 + 0.16, 1.0, 2.3))[2], shelf))

        def sofa(fr):
            (x0, x1), (y0, y1), (z0, z1) = self.SOFA
            fr.ground_ellipse(cam, (x0 + x1) / 2, (z0 + z1) / 2, 0.55, 1.2, "#000000", 0.35, blur_m=0.1)
            fr.box(cam, (x0, x1), (0.08, 0.42), (z0, z1), "#5e6f93", line=1.5)
            fr.box(cam, (x0, x0 + 0.22), (0.42, 0.85), (z0, z1), "#56678a", line=1.5)                 # back
            for zz in (z0, z1 - 0.18):
                fr.box(cam, (x0, x1), (0.42, 0.62), (zz, zz + 0.18), "#56678a", line=1.5)         # arms
            fr.box(cam, (x0 + 0.24, x1 - 0.02), (0.42, 0.52), (z0 + 0.2, z1 - 0.2), "#6c7da2", line=1.5)   # seat cushion
            fr.box(cam, (x0 + 0.22, x0 + 0.42), (0.52, 0.8), (z0 + 0.3, z0 + 0.62), "#e3c27a", line=1.2)   # throw pillow
        it.append((cam.view((-1.8, 0.4, 0.6))[2], sofa))

        def kitchen(fr):
            (x0, x1), (y0, y1), (z0, z1) = self.KITCH
            fr.ground_ellipse(cam, (x0 + x1) / 2, (z0 + z1) / 2, 0.5, 1.4, "#000000", 0.3, blur_m=0.1)
            fr.box(cam, (x0, x1), (0.0, y1 - 0.04), (z0, z1), "#6e7f86", line=1.5)
            fr.box(cam, (x0 - 0.03, x1), (y1 - 0.04, y1), (z0 - 0.03, z1 + 0.03), "#d8d2c6", line=1.5)
            for zz in (-0.9, -0.1, 0.7):
                fr.box(cam, (x0 - 0.005, x0), (0.12, 0.8), (zz, zz + 0.62), "#7d8e95", line=1.2)
            fr.box(cam, (x0 + 0.3, x0 + 0.55), (y1, y1 + 0.24), (-0.95, -0.75), "#c9483a", line=1.5)       # kettle
            fr.box(cam, (x0 + 0.2, x0 + 0.29), (y1, y1 + 0.1), (-0.45, -0.36), "#efe8da", line=1.2)       # mug
            fr.box(cam, (1.8, 2.2), (1.45, 2.05), (z0, z1), "#7d8e95", line=1.5)                       # wall cabinets
            fr.poly(cam, [(1.8, 1.44, z0), (1.8, 1.44, z1), (2.2, 1.44, z1), (2.2, 1.44, z0)], colr=WARM, a=0.9)   # under-cabinet strip
            fr.ground_ellipse(cam, 1.7, 0.1, 0.6, 1.4, WARM, 0.08, blur_m=0.3, add=True)
        it.append((cam.view((1.8, 0.5, 0.1))[2], kitchen))
        return it

    def grade(self, fr, T, pid, o, phone=0.0):
        if self.day:
            grade(fr, o, "#d9b9a0", [("#ffe2b8", 0.22, 0.6, -0.4)])
        else:
            grade(fr, o, "#8a97c4", [(WARM, 0.16, -0.7, -0.2), ("#d9e6ff", 0.14 * phone, 0.2, 0.6)])

    def prop_items(self, cam, T):
        return prop_items(self.props, cam)


def prop_items(props, cam):
    """Loose phones lying on things: [(kind, (x, y, z), lit)] -> depth-sorted draw items."""
    if True:
        it = []
        for kind, (x, y, z), lit in props:
            def ph(fr, x=x, y=y, z=z, lit=lit):
                fr.ground_ellipse(cam, x, z, 0.06, 0.09, "#000000", 0.4, blur_m=0.02)
                fr.box(cam, (x - 0.036, x + 0.036), (y, y + 0.009), (z - 0.075, z + 0.075), "#14161d", line=1.0)
                if lit > 0.01:
                    fr.poly(cam, [(x - 0.03, y + 0.0095, z - 0.068), (x + 0.03, y + 0.0095, z - 0.068), (x + 0.03, y + 0.0095, z + 0.068),
                                  (x - 0.03, y + 0.0095, z + 0.068)], colr="#9fc4ff", a=lit)
                    glow3(fr, cam, (x, y + 0.02, z), 0.25, "#9fc4ff", 0.35 * lit)
            it.append((cam.view((x, y, z))[2] - 0.05, ph))
        return it


class _FlatDraw:
    pass


def _flat_draw(self, fr, cam, T, cast, phone=0.0):
        self.shell(fr, cam, T)
        items = self.furniture(cam, T) + self.prop_items(cam, T)
        outs = draw_people(fr, cam, T, cast, items, self.LAMP, lambda fr, T, pid, o: self.grade(fr, T, pid, o, phone))
        if cam.pos[2] > self.Z1:                                              # outside: the glass and the rain are in front
            (wx0, wx1), (wy0, wy1) = self.WIN
            glass_drops(fr, cam, T, ("z", self.Z1 + 0.02, wx0, wx1, wy0, wy1), seed=5, n=90)
            self.near_rain.draw(fr, cam, T, colr=(0.8, 0.86, 1.0), amax=0.3, zmin=0.15, wmax=1.6)
            fr.c.drawRect(skia.Rect(-10, -10, W + 10, H + 10), paint("#0d1430", a=0.18))
        if self.day:
            fr.c.drawRect(skia.Rect(-10, -10, W + 10, H + 10), paint(shader=rad((W / 2, H * 0.45), H * 0.7, [argb("#000000", 0), argb("#2a1408", 0.45)], [0.55, 1])))
        return outs


Flat.draw = _flat_draw


# =================================================================================================================
# Theo's room
# =================================================================================================================
class Room:
    X0, X1, Z0, Z1, HT = -2.0, 2.0, -3.0, 3.0, 2.5
    WIN = ((-0.75, 0.55), (1.0, 2.1))
    DESK = ((1.38, 2.0), (0.0, 0.74), (0.9, 2.6))
    DLAMP = (1.62, 1.18, 2.35)
    BED = ((-2.0, -0.95), (0.0, 0.52), (0.4, 2.95))
    CHAIR = (0.92, 1.75)
    WALL, FLOOR = "#4b5a6e", "#5a4a3c"

    def __init__(self):
        self.props = []
        self.street = City(23, -3.6, 9, 30, -18, 18, 26, 4, 9, rain_box=((-2, 2), (-1, 4), (3.3, 7)))

    def shell(self, fr, cam, T):
        X0, X1, Z0, Z1, HT = self.X0, self.X1, self.Z0, self.Z1, self.HT
        (wx0, wx1), (wy0, wy1) = self.WIN
        if clip_to(fr, cam, [(wx0, wy0, Z1), (wx1, wy0, Z1), (wx1, wy1, Z1), (wx0, wy1, Z1)]):
            self.street.draw(fr, cam, T, sky=("#111833", "#27304f", "#3f3f62"))
            glow3(fr, cam, (2.2, 0.8, 7.0), 1.6, "#ffb86b", 0.5)                  # the street lamp outside
            fr.c.restore()
        wall = self.WALL
        back = lambda path: lin((0, path.getBounds().top()), (0, path.getBounds().bottom()), [argb(shade(wall, -0.3)), argb(wall), argb(shade(wall, -0.15))], [0, 0.6, 1])  # noqa: E731
        for pts in ([(X0, 0, Z1), (wx0, 0, Z1), (wx0, HT, Z1), (X0, HT, Z1)], [(wx1, 0, Z1), (X1, 0, Z1), (X1, HT, Z1), (wx1, HT, Z1)],
                    [(wx0, 0, Z1), (wx1, 0, Z1), (wx1, wy0, Z1), (wx0, wy0, Z1)], [(wx0, wy1, Z1), (wx1, wy1, Z1), (wx1, HT, Z1), (wx0, HT, Z1)]):
            fr.poly(cam, pts, shader=back)
        fr.poly(cam, [(X0, 0, Z0), (X1, 0, Z0), (X1, 0, Z1), (X0, 0, Z1)], colr=self.FLOOR)
        for i in range(-12, 14):
            x = i * 0.18
            fr.poly(cam, [(x, 0, Z0), (x + 0.008, 0, Z0), (x + 0.008, 0, Z1), (x, 0, Z1)], colr=shade(self.FLOOR, -0.25))
        fr.poly(cam, [(X0, HT, Z0), (X1, HT, Z0), (X1, HT, Z1), (X0, HT, Z1)], colr=shade(wall, -0.55))
        fr.poly(cam, [(X0, 0, Z0), (X0, 0, Z1), (X0, HT, Z1), (X0, HT, Z0)], colr=shade(wall, -0.1))
        fr.poly(cam, [(X1, 0, Z0), (X1, 0, Z1), (X1, HT, Z1), (X1, HT, Z0)], colr=shade(wall, -0.22))
        fr.poly(cam, [(-0.9, 0.001, 0.4), (1.2, 0.001, 0.4), (1.2, 0.001, 2.2), (-0.9, 0.001, 2.2)], colr="#2f4f5a")         # rug
        # window frame and sill; drops
        fr.box(cam, (wx0 - 0.08, wx1 + 0.08), (wy0 - 0.05, wy0), (Z1 - 0.14, Z1 + 0.02), "#ece6da", line=1.5)
        for a, b in (((wx0 - 0.05, wy0), (wx0, wy1)), ((wx1, wy0), (wx1 + 0.05, wy1)), ((wx0 - 0.05, wy1), (wx1 + 0.05, wy1 + 0.05)),
                     (((wx0 + wx1) / 2 - 0.02, wy0), ((wx0 + wx1) / 2 + 0.02, wy1))):
            quad(fr, cam, [(a[0], a[1], Z1 - 0.01), (b[0], a[1], Z1 - 0.01), (b[0], b[1], Z1 - 0.01), (a[0], b[1], Z1 - 0.01)], "#efe9de")
        glass_drops(fr, cam, T, ("z", Z1 - 0.012, wx0, wx1, wy0, wy1), seed=9, n=45)
        # posters over the bed (left wall) and one on the back wall
        for (z0, z1, y0, y1, c1, c2) in ((0.7, 1.4, 1.2, 2.1, "#d0473b", "#f2c14e"), (1.6, 2.2, 1.35, 2.0, "#20304f", "#6fc2b6")):
            wall_rect(fr, cam, "x", X0, z0, z1, y0, y1, c1, eps=-0.01, outline=shade(c1, -0.5), line=2.0)
            wall_rect(fr, cam, "x", X0, z0 + 0.08, z1 - 0.08, y0 + 0.1, (y0 + y1) / 2, c2, eps=-0.012)
        wall_rect(fr, cam, "z", Z1, 0.9, 1.3, 1.2, 1.8, "#e8e1d0", eps=0.01, outline="#9a8f7a", line=2.0)
        # fairy lights along the top of the back wall
        for i in range(26):
            x = X0 + 0.1 + i * 0.152
            y = HT - 0.12 - 0.07 * math.sin(i * 0.9) ** 2
            glow3(fr, cam, (x, y, Z1 - 0.02), 0.07, "#ffd58a", 0.5 + 0.15 * math.sin(T * 1.3 + i))
        # the door, front-left
        wall_rect(fr, cam, "x", X0, -1.6, -0.75, 0.0, 2.05, "#c9bda8", eps=-0.01, outline="#7a6e5c", line=2.0)

    def furniture(self, cam, T, laptop=1.0):
        it = []

        def desk(fr):
            (x0, x1), (y0, y1), (z0, z1) = self.DESK
            fr.ground_ellipse(cam, (x0 + x1) / 2, (z0 + z1) / 2, 0.45, 1.0, "#000000", 0.3, blur_m=0.1)
            fr.box(cam, (x0, x1), (y1 - 0.04, y1), (z0, z1), "#c8b293", line=1.5)
            for zz in (z0 + 0.02, z1 - 0.06):
                fr.box(cam, (x0 + 0.04, x0 + 0.08), (0, y1 - 0.04), (zz, zz + 0.04), "#2a2c33")
            fr.box(cam, (x0 + 0.05, x1), (0.3, y1 - 0.04), (z1 - 0.5, z1 - 0.02), "#b49d7e", line=1.2)    # drawers
            # laptop: base and lid, the screen glowing toward the chair
            fr.box(cam, (1.48, 1.78), (y1, y1 + 0.02), (1.6, 2.0), "#9aa0aa", line=1.2)
            lid = [(1.78, y1 + 0.02, 1.6), (1.78, y1 + 0.02, 2.0), (1.86, y1 + 0.27, 2.0), (1.86, y1 + 0.27, 1.6)]
            fr.poly(cam, lid, colr="#2a2f3a", outline="#15171c", line=1.5)
            scr = [(1.775, y1 + 0.04, 1.63), (1.775, y1 + 0.04, 1.97), (1.85, y1 + 0.25, 1.97), (1.85, y1 + 0.25, 1.63)]
            fr.poly(cam, scr, colr=shade("#8fb3e8", -0.5 * (1 - laptop)))
            glow3(fr, cam, (1.78, y1 + 0.16, 1.8), 0.35, "#9cc0ff", 0.18 * laptop)
            # mugs, books
            fr.box(cam, (1.5, 1.58), (y1, y1 + 0.1), (1.15, 1.23), "#e7e2d5", line=1.2)
            fr.box(cam, (1.62, 1.92), (y1, y1 + 0.05), (1.0, 1.3), "#3b6b8f", line=1.2)
            fr.box(cam, (1.64, 1.9), (y1 + 0.05, y1 + 0.09), (1.02, 1.28), "#c9573e", line=1.2)
            # bendy lamp
            lx, ly, lz = self.DLAMP
            fr.box(cam, (lx - 0.07, lx + 0.07), (y1, y1 + 0.03), (lz - 0.07, lz + 0.07), "#2e3440")
            a, b = cam.proj((lx, y1 + 0.03, lz)), cam.proj((lx + 0.05, ly + 0.14, lz - 0.05))
            fr.c.drawLine(a[0], a[1], b[0], b[1], paint("#2e3440", stroke=max(1.5, 0.018 * a[3])))
            c = cam.proj((lx - 0.08, ly, lz - 0.12))
            fr.c.drawLine(b[0], b[1], c[0], c[1], paint("#2e3440", stroke=max(1.5, 0.018 * a[3])))
            fr.box(cam, (lx - 0.14, lx - 0.02), (ly - 0.04, ly + 0.05), (lz - 0.2, lz - 0.06), "#2e3440", line=1.2)
            glow3(fr, cam, (lx - 0.08, ly - 0.06, lz - 0.13), 0.35, WARM, 0.55)
            fr.ground_ellipse(cam, 1.55, 2.0, 0.5, 0.6, WARM, 0.18, blur_m=0.2, add=True)
        it.append((cam.view((1.7, 0.4, 1.75))[2], desk))

        def chair(fr):
            cx, cz = self.CHAIR
            fr.ground_ellipse(cam, cx, cz, 0.3, 0.3, "#000000", 0.35, blur_m=0.06)
            for a in range(5):                                                   # star base
                t = a * 2 * math.pi / 5
                p0, p1 = cam.proj((cx, 0.06, cz)), cam.proj((cx + 0.26 * math.cos(t), 0.04, cz + 0.26 * math.sin(t)))
                fr.c.drawLine(p0[0], p0[1], p1[0], p1[1], paint("#1d1f26", stroke=max(1.5, 0.03 * p0[3])))
            fr.box(cam, (cx - 0.025, cx + 0.025), (0.06, 0.42), (cz - 0.025, cz + 0.025), "#1d1f26")
            fr.box(cam, (cx - 0.24, cx + 0.22), (0.42, 0.5), (cz - 0.23, cz + 0.23), "#323848", line=1.5)
            fr.box(cam, (cx - 0.30, cx - 0.24), (0.5, 1.05), (cz - 0.22, cz + 0.22), "#323848", line=1.5)
        it.append((cam.view((self.CHAIR[0] - 0.2, 0.5, self.CHAIR[1]))[2], chair))

        def bed(fr):
            (x0, x1), (y0, y1), (z0, z1) = self.BED
            fr.ground_ellipse(cam, (x0 + x1) / 2, (z0 + z1) / 2, 0.6, 1.4, "#000000", 0.35, blur_m=0.1)
            fr.box(cam, (x0, x1), (0.0, 0.3), (z0, z1), "#6b4c3a", line=1.5)
            fr.box(cam, (x0 + 0.02, x1 - 0.02), (0.3, 0.46), (z0 + 0.02, z1 - 0.02), "#e9e4da", line=1.2)
            fr.box(cam, (x0 + 0.05, x1 + 0.03), (0.42, 0.56), (z0 - 0.02, z1 - 0.55), "#e0884f", line=1.5)   # duvet
            fr.box(cam, (x0 + 0.12, x1 - 0.12), (0.46, 0.62), (z1 - 0.5, z1 - 0.1), "#f2efe8", line=1.2)       # pillow
            fr.box(cam, (x0, x1), (0.0, 0.9), (z1 - 0.06, z1), "#6b4c3a", line=1.5)                            # headboard
        it.append((cam.view((-1.5, 0.3, 1.7))[2], bed))
        return it

    def grade(self, fr, T, pid, o, phone=0.0, laptop=1.0):
        grade(fr, o, "#8c9ac0", [(WARM, 0.22, 0.8, -0.3), ("#a9c6ff", 0.08 * laptop, 0.9, 0.2), ("#d9e6ff", 0.14 * phone, 0.0, 0.6)])

    def draw(self, fr, cam, T, cast, phone=0.0, laptop=1.0):
        self.shell(fr, cam, T)
        items = self.furniture(cam, T, laptop) + prop_items(self.props, cam)
        return draw_people(fr, cam, T, cast, items, self.DLAMP, lambda fr, T, pid, o: self.grade(fr, T, pid, o, phone, laptop))
