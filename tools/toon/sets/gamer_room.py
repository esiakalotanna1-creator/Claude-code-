"""GAMER ROOM: a reusable teenage gamer's bedroom for toon reels (built 2026-11-08 for the Timmy milestone clips).

World units are metres, y up. The room is x in [-ROOM_X, ROOM_X], z in [0, ROOM_Z], floor y = 0, ceiling ROOM_H. The desk
wall is the BACK wall (z = ROOM_Z); cameras stand near or behind the open front (z <= ~1.2) looking +z. The bed is on
the LEFT wall (x = -ROOM_X), the wardrobe and drawers on the RIGHT wall (x = +ROOM_X).

Every asset is a class with a name, a pivot (base centre on the floor/desk it stands on) and a size, and:
    bg(fr, cam, T)        flat wall / floor decoration (always behind everything that stands in the room)
    item(cam, T)          -> (depth, fn, name) or a list of them: drawables depth-sorted with the cast
    solid()               -> box ((x0, x1), (y0, y1), (z0, z1)) for the reel checks
    lights()              -> [Light]: holes in the night grade, glows
Build a room from a LAYOUT list (make_layout) and hand it to GamerRoom.

    py -m sets.gamer_room --sheet review/gamer_room_sheet.png      room views + every asset in close-up
    py -m sets.gamer_room --manifest review/gamer_room.json        piece list: names, kinds, pivots, sizes
    py -m sets.gamer_room --assets <dir>                           one PNG per asset
"""
import colorsys
import json
import math

import numpy as np
import skia

from toon import typeface, Rain, W, H, argb, lin, paint, shade, mix

ROOM_X, ROOM_Z, ROOM_H = 2.0, 3.6, 2.5
DESK_Z0, DESK_Z1, DESK_Y = 2.95, 3.58, 0.74            # desk front edge, back edge, top height
WALL, WALL_SIDE, CEIL = "#2b2d48", "#272942", "#17182a"
FLOOR, FLOOR_SEAM, RUG = "#4a3a34", "#362a26", "#3b3352"
TYPE = typeface()
TYPE_R = typeface(bold=True)


def hue(T, off=0.0, speed=0.12, s=0.85, v=1.0):
    """RGB-cycling colour (fans, strips, panels): the whole set drifts round the colour wheel together."""
    return colorsys.hsv_to_rgb((T * speed + off) % 1.0, s, v)


class Light:
    """A point light: a soft hole in the night grade (radius r) and the key for nearby shading."""

    def __init__(self, name, pos, colr, r=1.6, k=0.8, colr_fn=None):
        self.name, self.pos, self.colr, self.r, self.k, self.colr_fn = name, pos, colr, r, k, colr_fn

    def col(self, T):
        return self.colr_fn(T) if self.colr_fn else self.colr


# ======================================================================================================
# drawing helpers
# ======================================================================================================
def vis(cam, P, margin=300):
    x, y, z, _ = cam.proj(P)
    return z > 0.2 and -margin < x < W + margin and -margin < y < H + margin


def wglow(fr, cam, P, r, colr, a, sx=1.0, sy=1.0):
    """Additive glow round a world point, r in metres."""
    x, y, z, s = cam.proj(P)
    if z > 0.15:
        fr.glow(x, y, r * s, colr, a=a, sx=sx, sy=sy)


def wline(fr, cam, a, b, colr, w_m, alpha=1.0, wmin=1.0):
    p, q = cam.proj(a), cam.proj(b)
    if p[2] > 0.15 and q[2] > 0.15:
        fr.c.drawLine(p[0], p[1], q[0], q[1], paint(colr, a=alpha, stroke=max(wmin, w_m * min(p[3], q[3]))))


def wpath(fr, cam, pts, colr, w_m, alpha=1.0):
    """Polyline through world points (cables, arms)."""
    P = [cam.proj(p) for p in pts]
    if min(p[2] for p in P) < 0.15:
        return
    path = skia.Path()
    path.moveTo(P[0][0], P[0][1])
    for p in P[1:]:
        path.lineTo(p[0], p[1])
    fr.c.drawPath(path, paint(colr, a=alpha, stroke=max(1.0, w_m * P[len(P) // 2][3])))


def decal(fr, cam, corners, w, h, draw):
    """Draw 2D artwork (w x h units, y down) onto a world quad tl, tr, br, bl with a perspective map."""
    P = [cam.proj(c) for c in corners]
    if min(p[2] for p in P) < 0.15:
        return
    m = skia.Matrix()
    ok = m.setPolyToPoly([skia.Point(0, 0), skia.Point(w, 0), skia.Point(w, h), skia.Point(0, h)],
                         [skia.Point(p[0], p[1]) for p in P])
    if not ok:
        return
    fr.c.save()
    fr.c.concat(m)
    fr.c.clipRect(skia.Rect(0, 0, w, h), True)        # artwork never spills off its quad
    draw(fr.c, w, h)
    fr.c.restore()


def quad_z(x0, x1, y0, y1, z):
    """tl, tr, br, bl of a quad in the plane z = const, facing -z (the camera side)."""
    return [(x0, y1, z), (x1, y1, z), (x1, y0, z), (x0, y0, z)]


def quad_x(z0, z1, y0, y1, x, facing=1):
    """tl, tr, br, bl of a quad in the plane x = const; facing +1 = seen from +x (left wall), -1 = from -x."""
    a, b = (z0, z1) if facing > 0 else (z1, z0)
    return [(x, y1, a), (x, y1, b), (x, y0, b), (x, y0, a)]


def quad_y(x0, x1, z0, z1, y):
    """tl, tr, br, bl of a horizontal quad (far edge = top): mats, sheets, books lying flat."""
    return [(x0, y, z1), (x1, y, z1), (x1, y, z0), (x0, y, z0)]


def cyl(fr, cam, c, r, h, colr, a=1.0, cap=None, line=1.2, light=(0.35, 1.0)):
    """Upright cylinder (bottles, bins, gas lifts, cups): verticals stay vertical in this camera, so it is a band
    plus elliptic caps whose height follows the view angle."""
    b, t = cam.proj(c), cam.proj((c[0], c[1] + h, c[2]))
    if b[2] < 0.15 or t[2] < 0.15:
        return None
    def ry(P, y):
        dy = cam.pos[1] - y
        return r * P[3] * abs(dy) / math.hypot(P[2], dy)
    w, eb, et = r * b[3], ry(b, c[1]), ry(t, c[1] + h)
    path = skia.Path()
    path.addRect(skia.Rect(t[0] - w, t[1], b[0] + w, b[1]))
    path.addOval(skia.Rect(b[0] - w, b[1] - eb, b[0] + w, b[1] + eb))
    path.addOval(skia.Rect(t[0] - w, t[1] - et, t[0] + w, t[1] + et))
    path.setFillType(skia.PathFillType.kWinding)
    path = skia.Op(path, skia.Path(), skia.PathOp.kUnion_PathOp) or path
    if a >= 0.99:
        fr.part(path, colr, light=light, line=line)
    else:
        fr.c.drawPath(path, paint(colr, a=a))
        fr.c.drawPath(path, paint(shade(colr, -0.6), a=min(1.0, a + 0.3), stroke=line))
    if cam.pos[1] > c[1] + h:
        fr.c.drawOval(skia.Rect(t[0] - w, t[1] - et, t[0] + w, t[1] + et), paint(cap or shade(colr, 0.18), a=a))
        fr.c.drawOval(skia.Rect(t[0] - w, t[1] - et, t[0] + w, t[1] + et), paint(shade(colr, -0.6), a=min(1.0, a + 0.3), stroke=line))
    return path


def blob(fr, cam, c, rx, ry, colr, light=(0.35, 1.0), line=1.2, squash=1.0):
    """A soft rounded lump (pillows, clothes, beanbag) as a shaded ellipse at a world point."""
    x, y, z, s = cam.proj(c)
    if z < 0.15:
        return None
    path = skia.Path()
    path.addOval(skia.Rect(x - rx * s, y - ry * s * squash, x + rx * s, y + ry * s * squash))
    fr.part(path, colr, light=light, line=line)
    return path


def font(sz, bold=True):
    return skia.Font(TYPE if bold else TYPE_R, sz)


def text(c, s, x, y, sz, colr, a=1.0, center=False, bold=True, stroke=0.0, stroke_c="#000000"):
    f = font(sz, bold)
    if center:
        x -= f.measureText(s) / 2
    blob_ = skia.TextBlob(s, f)
    if stroke:
        c.drawTextBlob(blob_, x, y, paint(stroke_c, a=a, stroke=stroke))
    c.drawTextBlob(blob_, x, y, paint(colr, a=a))


def rrect(c, x0, y0, x1, y1, r, colr, a=1.0, stroke=0.0):
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x0, y0, x1, y1), r, r), paint(colr, a=a, stroke=stroke))


# ======================================================================================================
# pieces
# ======================================================================================================
class Piece:
    kind = "prop"                                    # wall (bg decal) | floor (bg) | prop (depth sorted)
    size = (0.0, 0.0, 0.0)

    def __init__(self, name, x, z, y=0.0):
        self.name, self.x, self.z, self.y = name, x, z, y

    @property
    def pivot(self):
        return (self.x, self.y, self.z)

    def bg(self, fr, cam, T):
        pass

    def item(self, cam, T):
        return None

    def solid(self):
        return None

    def lights(self):
        return []

    def it(self, cam, fn, anchor=None, suffix=""):
        a = anchor or (self.x, self.y + 0.3, self.z)
        return (cam.view(a)[2], fn, self.name + suffix)


# ---- shell -----------------------------------------------------------------------------------------------------
class Shell(Piece):
    """Floor (worn oak boards), rug, walls with skirting, ceiling, the LED glow strips (behind the desk, under the bed)."""
    kind = "floor"

    def __init__(self, name="shell"):
        super().__init__(name, 0.0, ROOM_Z / 2)
        self.size = (2 * ROOM_X, ROOM_H, ROOM_Z)

    def bg(self, fr, cam, T):
        X, Z, Hh = ROOM_X, ROOM_Z, ROOM_H
        fr.poly(cam, [(-X, Hh, -1.5), (X, Hh, -1.5), (X, Hh, Z), (-X, Hh, Z)], colr=CEIL)
        fr.poly(cam, [(-X, 0, -1.5), (X, 0, -1.5), (X, 0, Z), (-X, 0, Z)], colr=FLOOR)
        for x in np.arange(-X, X, 0.19):                       # boards along z, staggered end joints
            wline(fr, cam, (x, 0.001, -1.5), (x, 0.001, Z), FLOOR_SEAM, 0.006, 0.8)
            k = int((x + X) / 0.19)
            for zz in np.arange(-1.5 + (k * 0.71) % 1.4, Z, 1.4):
                wline(fr, cam, (x, 0.001, zz), (x + 0.19, 0.001, zz), FLOOR_SEAM, 0.004, 0.6)
        # rug (worn edge) under the chair
        fr.poly(cam, [(-1.15, 0.003, 1.05), (1.25, 0.003, 1.05), (1.25, 0.003, 2.85), (-1.15, 0.003, 2.85)], colr=RUG,
                outline=shade(RUG, -0.5), line=1.2)
        fr.poly(cam, [(-1.05, 0.004, 1.15), (1.15, 0.004, 1.15), (1.15, 0.004, 2.75), (-1.05, 0.004, 2.75)], colr=shade(RUG, 0.08),
                outline=shade(RUG, 0.25), line=1.0)
        gr = lambda p, a, b: lin((0, p.getBounds().top()), (0, p.getBounds().bottom()), [argb(shade(a, -0.3)), argb(a), argb(shade(a, -0.2))], [0, 0.6, 1])  # noqa: E731
        fr.poly(cam, [(-X, 0, Z), (X, 0, Z), (X, Hh, Z), (-X, Hh, Z)], shader=lambda p: gr(p, WALL, None))
        if cam.pos[0] > -X:
            fr.poly(cam, [(-X, 0, -1.5), (-X, 0, Z), (-X, Hh, Z), (-X, Hh, -1.5)], shader=lambda p: gr(p, WALL_SIDE, None))
        if cam.pos[0] < X:
            fr.poly(cam, [(X, 0, -1.5), (X, 0, Z), (X, Hh, Z), (X, Hh, -1.5)], shader=lambda p: gr(p, WALL_SIDE, None))
        for q in ([(-X, 0, Z - 0.004), (X, 0, Z - 0.004), (X, 0.1, Z - 0.004), (-X, 0.1, Z - 0.004)],
                  [(-X + 0.004, 0, -1.5), (-X + 0.004, 0, Z), (-X + 0.004, 0.1, Z), (-X + 0.004, 0.1, -1.5)],
                  [(X - 0.004, 0, -1.5), (X - 0.004, 0, Z), (X - 0.004, 0.1, Z), (X - 0.004, 0.1, -1.5)]):
            fr.poly(cam, q, colr="#1b1c2c")                   # skirting
        # LED strips: behind the desk (wall wash) and under the bed (floor pool), cycling
        col = hue(T, 0.0)
        for x in np.linspace(-0.85, 0.85, 9):
            wglow(fr, cam, (x, DESK_Y + 0.25, Z - 0.02), 0.55, col, 0.16, sx=1.4, sy=1.0)
        wline(fr, cam, (-0.88, DESK_Y + 0.02, Z - 0.01), (0.88, DESK_Y + 0.02, Z - 0.01), col, 0.012, 0.9)
        colb = hue(T, 0.5)
        fr.ground_ellipse(cam, -1.55, 1.7, 0.75, 1.25, colb, 0.13, blur_m=0.35, y=0.004, add=True)


# ---- wall decorations (flat on the wall, drawn in bg) ---------------------------------------------------------------
class Window(Piece):
    """Back-wall window: night rain on the glass, distant lit windows, blackout curtains drawn almost shut (a gap
    of `gap` m at `gap_x`). Always raining (standing look rule)."""
    kind = "wall"

    def __init__(self, name, x0, x1, y0=1.05, y1=2.05, gap_x=None, gap=0.2):
        super().__init__(name, (x0 + x1) / 2, ROOM_Z, y0)
        self.x0, self.x1, self.y0, self.y1 = x0, x1, y0, y1
        self.gap_x, self.gap = gap_x if gap_x is not None else (x0 + x1) / 2 + 0.05, gap
        self.size = (x1 - x0 + 0.4, y1 - y0 + 0.4, 0.12)
        self.rain = Rain(n=520, box=((x0 - 1.0, x1 + 1.0), (-1.0, 4.0), (ROOM_Z + 0.5, ROOM_Z + 5.0)), speed=7.0, seed=8)

    def bg(self, fr, cam, T):
        x0, x1, y0, y1, Z = self.x0, self.x1, self.y0, self.y1, ROOM_Z - 0.003
        glass = fr.poly(cam, quad_z(x0, x1, y0, y1, Z), shader=lambda p: lin((0, p.getBounds().top()), (0, p.getBounds().bottom()),
                                                                           [argb("#0a1028"), argb("#18224a")]))
        if glass is not None:
            fr.c.save()
            fr.c.clipPath(glass, skia.ClipOp.kIntersect, True)
            r = np.random.default_rng(3)
            for i in range(14):                                # the block across the street: a few warm windows
                wx, wy = r.uniform(x0 - 0.6, x1 + 0.6), r.uniform(y0 - 0.2, y1)
                p = cam.proj((wx, wy, ROOM_Z + 6.0))
                if p[2] > 0.3:
                    fr.c.drawRect(skia.Rect(p[0], p[1], p[0] + 0.25 * p[3], p[1] + 0.32 * p[3]), paint("#ffc27a", a=0.35))
            wglow(fr, cam, ((x0 + x1) / 2, y1 + 0.6, ROOM_Z + 4.0), 2.2, "#4a64b8", 0.25)
            self.rain.draw(fr, cam, T, colr=(0.75, 0.82, 0.98), amax=0.45)
            for k in range(9):                                 # drops running down the glass
                u = (T * 0.22 + k * 0.137) % 1.0
                dx = x0 + (x1 - x0) * ((k * 0.383) % 1.0)
                wline(fr, cam, (dx, y1 - (y1 - y0) * u, Z - 0.001), (dx + 0.004, y1 - (y1 - y0) * u - 0.05, Z - 0.001), "#cfe0ff", 0.006, 0.5)
            fr.c.restore()
        fc = "#3c3e58"
        for (a0, a1, b0, b1) in ((x0 - 0.05, x1 + 0.05, y0 - 0.06, y0), (x0 - 0.05, x1 + 0.05, y1, y1 + 0.05), (x0 - 0.05, x0, y0, y1),
                                 (x1, x1 + 0.05, y0, y1), ((x0 + x1) / 2 - 0.02, (x0 + x1) / 2 + 0.02, y0, y1)):
            fr.poly(cam, quad_z(a0, a1, b0, b1, Z - 0.006), colr=fc, outline=shade(fc, -0.6), line=1.0)
        fr.box(cam, (x0 - 0.1, x1 + 0.1), (y0 - 0.1, y0 - 0.06), (ROOM_Z - 0.09, ROOM_Z), shade(fc, 0.1), line=1.0)   # sill
        # curtain rail + blackout curtains, folds as vertical bands
        wline(fr, cam, (x0 - 0.25, y1 + 0.16, ROOM_Z - 0.06), (x1 + 0.25, y1 + 0.16, ROOM_Z - 0.06), "#9a9aa8", 0.012, 1.0)
        g0, g1 = self.gap_x - self.gap / 2, self.gap_x + self.gap / 2
        for a, b in ((x0 - 0.25, g0), (g1, x1 + 0.25)):
            n = max(2, int((b - a) / 0.07))
            for i in range(n):
                xa, xb = a + (b - a) * i / n, a + (b - a) * (i + 1) / n
                cc = "#1c2038" if i % 2 else "#252a48"
                q = quad_z(xa, xb, y0 - 0.32, y1 + 0.15, ROOM_Z - 0.07 - 0.01 * (i % 2))
                sw = getattr(self, "sway", 0.0)                # a draught lifting the hem (mara_room's aircon)
                if sw:
                    dz = sw * 0.06 * (0.6 + 0.4 * math.sin(T * 1.7 + i * 0.8))
                    q = [(p[0], p[1], p[2] - dz) if p[1] < y0 else p for p in q]
                fr.poly(cam, q, colr=cc)
            fr.poly(cam, quad_z(a, b, y0 - 0.32, y1 + 0.15, ROOM_Z - 0.085), colr="#000000", a=0.0, outline="#0c0e1c", line=1.2)

    def lights(self):
        return [Light(self.name, (self.gap_x, (self.y0 + self.y1) / 2, ROOM_Z - 0.1), "#6a86d8", 0.7, 0.35)]


class Poster(Piece):
    """A poster on a wall: wall = back | left | right, a0..a1 along the wall (x for back, z for the sides).
    art = level_up (game) | anime_eyes | band | lofi."""
    kind = "wall"

    def __init__(self, name, wall, a0, a1, y0, y1, art, tilt=0.0):
        super().__init__(name, *self._xz(wall, (a0 + a1) / 2), y0)
        self.wall, self.a0, self.a1, self.y0, self.y1, self.art, self.tilt = wall, a0, a1, y0, y1, art, tilt
        self.size = (a1 - a0, y1 - y0, 0.005)

    @staticmethod
    def _xz(wall, a):
        return {"back": (a, ROOM_Z), "left": (-ROOM_X, a), "right": (ROOM_X, a)}[wall]

    def corners(self, off=0.006):
        a0, a1, y0, y1, t = self.a0, self.a1, self.y0, self.y1, self.tilt
        if self.wall == "back":
            q = quad_z(a0, a1, y0, y1, ROOM_Z - off)
        elif self.wall == "left":
            q = quad_x(a0, a1, y0, y1, -ROOM_X + off, 1)
        else:
            q = quad_x(a0, a1, y0, y1, ROOM_X - off, -1)
        if t:                                         # a slightly crooked poster: shear the top edge
            q = [(p[0], p[1] + (t if i in (1, 2) else 0.0) * (1 if i == 1 else 0), p[2]) for i, p in enumerate(q)]
        return q

    def bg(self, fr, cam, T):
        if (self.wall == "left" and cam.pos[0] < -ROOM_X) or (self.wall == "right" and cam.pos[0] > ROOM_X):
            return
        decal(fr, cam, self.corners(), 300, 300 * (self.y1 - self.y0) / (self.a1 - self.a0), getattr(self, "art_" + self.art))

    @staticmethod
    def art_level_up(c, w, h):
        c.drawRect(skia.Rect(0, 0, w, h), paint(shader=lin((0, 0), (0, h), [argb("#1a0a3a"), argb("#7a1a8a"), argb("#ff6a3a")], [0, 0.6, 1])))
        for i in range(12):                            # synthwave grid floor
            y = h * 0.62 + (h * 0.38) * (i / 11) ** 1.7
            c.drawLine(0, y, w, y, paint("#ff4ad8", a=0.6, stroke=2))
        for i in range(-6, 7):
            c.drawLine(w / 2 + i * 18, h * 0.62, w / 2 + i * 70, h, paint("#ff4ad8", a=0.6, stroke=2))
        c.drawCircle(w / 2, h * 0.5, w * 0.24, paint(shader=lin((0, h * 0.26), (0, h * 0.74), [argb("#ffe14a"), argb("#ff3a7a")])))
        for i in range(5):
            c.drawRect(skia.Rect(w * 0.2, h * 0.52 + i * 12, w * 0.8, h * 0.52 + i * 12 + 4), paint("#7a1a8a"))
        # a little controller silhouette and the title
        rrect(c, w * 0.33, h * 0.68, w * 0.67, h * 0.8, 24, "#120822")
        c.drawCircle(w * 0.41, h * 0.74, 9, paint("#3ae0ff"))
        c.drawCircle(w * 0.6, h * 0.72, 6, paint("#ff4a6a"))
        c.drawCircle(w * 0.62, h * 0.76, 6, paint("#ffe14a"))
        text(c, "LEVEL UP", w / 2, h * 0.17, 52, "#ffffff", center=True, stroke=8, stroke_c="#3a0a5a")
        text(c, "PRESS START", w / 2, h * 0.95, 22, "#ffe14a", center=True)
        c.drawRect(skia.Rect(0, 0, w, h), paint("#000000", a=1.0, stroke=6))

    @staticmethod
    def art_anime_eyes(c, w, h):
        c.drawRect(skia.Rect(0, 0, w, h), paint(shader=lin((0, 0), (w, h), [argb("#0e2a4a"), argb("#2a6ab0")])))
        for k, cy in enumerate((h * 0.42,)):           # one big anime eye pair + speed lines
            for sx in (-1, 1):
                ex = w / 2 + sx * w * 0.2
                c.drawOval(skia.Rect(ex - 52, cy - 40, ex + 52, cy + 40), paint("#f4f6ff"))
                c.drawOval(skia.Rect(ex - 30, cy - 38, ex + 30, cy + 38), paint(shader=lin((0, cy - 38), (0, cy + 38), [argb("#3ad0ff"), argb("#1a3a9a")])))
                c.drawCircle(ex, cy + 4, 14, paint("#0a0a1a"))
                c.drawCircle(ex - 10, cy - 12, 8, paint("#ffffff"))
                c.drawLine(ex - 60, cy - 46, ex + 50, cy - 56 + sx * 4, paint("#0a0a1a", stroke=9))
        for i in range(18):
            a = i / 18 * math.tau
            c.drawLine(w / 2 + math.cos(a) * w * 0.42, h * 0.42 + math.sin(a) * w * 0.42, w / 2 + math.cos(a) * w * 0.7,
                       h * 0.42 + math.sin(a) * w * 0.7, paint("#ffffff", a=0.35, stroke=3))
        c.drawRect(skia.Rect(0, h * 0.72, w, h), paint("#ff3a5a"))
        text(c, "NEO RONIN", w / 2, h * 0.84, 40, "#ffffff", center=True)
        text(c, "SEASON 2", w / 2, h * 0.94, 22, "#ffe4ea", center=True)

    @staticmethod
    def art_band(c, w, h):
        c.drawRect(skia.Rect(0, 0, w, h), paint("#111114"))
        c.drawCircle(w / 2, h * 0.45, w * 0.33, paint(shader=lin((0, 0), (0, h), [argb("#e8e2d0"), argb("#a8a090")])))
        for i in range(7):                             # a record's grooves
            c.drawCircle(w / 2, h * 0.45, w * (0.3 - i * 0.035), paint("#111114", a=0.7, stroke=3))
        c.drawCircle(w / 2, h * 0.45, w * 0.07, paint("#d83a3a"))
        text(c, "THE STATIC", w / 2, h * 0.88, 40, "#e8e2d0", center=True)
        text(c, "WORLD TOUR", w / 2, h * 0.96, 18, "#d83a3a", center=True)

    @staticmethod
    def art_lofi(c, w, h):
        c.drawRect(skia.Rect(0, 0, w, h), paint(shader=lin((0, 0), (0, h), [argb("#ff9a7a"), argb("#7a5ab8"), argb("#2a2a5a")], [0, 0.5, 1])))
        c.drawCircle(w * 0.7, h * 0.3, w * 0.12, paint("#ffe8c8"))
        for i, (cx, cw, ch) in enumerate(((0.1, 0.16, 0.35), (0.3, 0.12, 0.5), (0.48, 0.18, 0.28), (0.72, 0.14, 0.45))):
            c.drawRect(skia.Rect(w * cx, h * (1 - ch), w * (cx + cw), h), paint("#1a1a3a"))
            for k in range(6):
                if (i + k) % 2:
                    c.drawRect(skia.Rect(w * (cx + 0.03), h * (1 - ch) + 16 + k * 22, w * (cx + 0.06), h * (1 - ch) + 26 + k * 22), paint("#ffd27a"))
        text(c, "lo-fi beats", w / 2, h * 0.14, 34, "#ffffff", center=True)


class Corkboard(Piece):
    """Cork board on the back wall: polaroids with friends, a ticket stub, pins."""
    kind = "wall"

    def __init__(self, name, x0, x1, y0, y1):
        super().__init__(name, (x0 + x1) / 2, ROOM_Z, y0)
        self.x0, self.x1, self.y0, self.y1 = x0, x1, y0, y1
        self.size = (x1 - x0, y1 - y0, 0.02)

    def bg(self, fr, cam, T):
        x0, x1, y0, y1 = self.x0, self.x1, self.y0, self.y1
        fr.box(cam, (x0 - 0.02, x1 + 0.02), (y0 - 0.02, y1 + 0.02), (ROOM_Z - 0.02, ROOM_Z), "#6a4a30", line=1.0)

        def art(c, w, h):
            c.drawRect(skia.Rect(0, 0, w, h), paint("#b07a48"))
            r = np.random.default_rng(5)
            for _ in range(260):
                c.drawCircle(r.uniform(0, w), r.uniform(0, h), r.uniform(0.6, 1.8), paint("#7a4a28", a=0.6))
            shots = [(0.06, 0.08, -6, "#5ab0e8"), (0.38, 0.05, 4, "#e8a05a"), (0.68, 0.12, -3, "#7ad07a"), (0.12, 0.52, 5, "#d07ab8"),
                     (0.46, 0.5, -5, "#e8d05a")]
            for i, (px, py, rot, sky) in enumerate(shots):
                c.save()
                c.translate(px * w + 40, py * h + 48)
                c.rotate(rot)
                c.drawRect(skia.Rect(-40, -48, 40, 48), paint("#f4f0e8"))
                c.drawRect(skia.Rect(-34, -42, 34, 24), paint(sky))
                for k in range(2 + i % 2):                 # friends: little round heads and shoulders
                    hx = -18 + k * 18
                    c.drawCircle(hx, 0, 7, paint("#f0c8a0" if (i + k) % 3 else "#a8704a"))
                    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect(hx - 10, 7, hx + 10, 24), 6, 6), paint(["#d83a3a", "#3a5ad8", "#3ad87a"][(i + k) % 3]))
                c.drawCircle(0, -44, 4, paint("#e83a3a"))
                c.restore()
            c.save()
            c.translate(w * 0.78, h * 0.66)
            c.rotate(12)
            c.drawRect(skia.Rect(-30, -14, 30, 14), paint("#f0d870"))
            text(c, "ADMIT 1", 0, 6, 12, "#6a4a10", center=True)
            c.restore()
        decal(fr, cam, quad_z(x0, x1, y0, y1, ROOM_Z - 0.022), 320, 320 * (y1 - y0) / (x1 - x0), art)


class NeonSign(Piece):
    """Neon tube sign on the back wall ("GG" by default): pink tubes on a clear acrylic back, buzzing glow."""
    kind = "wall"

    def __init__(self, name, x, y, w=0.5, word="GG", colr="#ff3ad8"):
        super().__init__(name, x, ROOM_Z, y)
        self.w, self.word, self.colr = w, word, colr
        self.size = (w, w * 0.45, 0.03)

    def bg(self, fr, cam, T):
        x, y, w = self.x, self.y, self.w
        hh = w * 0.45
        on = 0.92 + 0.08 * math.sin(T * 47.0) * math.sin(T * 13.0)
        wglow(fr, cam, (x, y + hh / 2, ROOM_Z - 0.02), w * 1.1, self.colr, 0.32 * on, sx=1.3)

        def art(c, ww, hh_):
            text(c, self.word, ww / 2, hh_ * 0.82, hh_ * 0.95, self.colr, a=0.35, center=True, stroke=18, stroke_c=self.colr)
            text(c, self.word, ww / 2, hh_ * 0.82, hh_ * 0.95, "#ffe0fa", center=True, stroke=0)
        decal(fr, cam, quad_z(x - w / 2, x + w / 2, y, y + hh, ROOM_Z - 0.02), 400, 180, art)

    def lights(self):
        return [Light(self.name, (self.x, self.y + 0.1, ROOM_Z - 0.2), self.colr, 1.0, 0.45)]


class HexPanels(Piece):
    """Geometric LED hexagon panels on the back wall, each cycling a step behind its neighbour."""
    kind = "wall"
    LAYOUT = [(0, 0), (1, 0), (0.5, 0.866), (1.5, 0.866), (2, 0), (-0.5, 0.866)]

    def __init__(self, name, x, y, r=0.11):
        super().__init__(name, x, ROOM_Z, y)
        self.r = r
        self.size = (r * 5.2, r * 3.0, 0.02)

    def bg(self, fr, cam, T):
        r = self.r
        for i, (u, v) in enumerate(self.LAYOUT):
            cx, cy = self.x + u * r * 1.8, self.y + v * r * 1.8
            col = hue(T, i * 0.09)
            pts = [(cx + r * math.cos(math.radians(30 + 60 * k)), cy + r * math.sin(math.radians(30 + 60 * k)), ROOM_Z - 0.015) for k in range(6)]
            wglow(fr, cam, (cx, cy, ROOM_Z - 0.02), r * 2.2, col, 0.22)
            fr.poly(cam, pts, colr=mix(col, (1, 1, 1), 0.35), outline="#101018", line=1.4)

    def lights(self):
        return [Light(self.name, (self.x + self.r * 1.8, self.y + self.r, ROOM_Z - 0.2), "#ffffff", 0.9, 0.4,
                      colr_fn=lambda T: hue(T, 0.1))]


class Jersey(Piece):
    """Football shirt pinned flat on a side wall, number on the back, sleeves out."""
    kind = "wall"

    def __init__(self, name, wall, a, y, w=0.55, colr="#c8283a", trim="#f4f0e8", number="10"):
        super().__init__(name, *Poster._xz(wall, a), y)
        self.wall, self.a, self.w, self.colr, self.trim, self.number = wall, a, w, colr, trim, number
        self.size = (w, w * 0.95, 0.01)

    def bg(self, fr, cam, T):
        w, a, y = self.w, self.a, self.y
        q = quad_x(a - w / 2, a + w / 2, y, y + w * 0.95, -ROOM_X + 0.008, 1) if self.wall == "left" else \
            quad_x(a - w / 2, a + w / 2, y, y + w * 0.95, ROOM_X - 0.008, -1)

        def art(c, ww, hh):
            p = skia.Path()
            pts = [(0.3, 0.02), (0.42, 0.08), (0.58, 0.08), (0.7, 0.02), (1.0, 0.2), (0.88, 0.42), (0.77, 0.36), (0.77, 1.0),
                   (0.23, 1.0), (0.23, 0.36), (0.12, 0.42), (0.0, 0.2)]
            p.moveTo(pts[0][0] * ww, pts[0][1] * hh)
            for u, v in pts[1:]:
                p.lineTo(u * ww, v * hh)
            p.close()
            c.drawPath(p, paint(self.colr))
            c.save()
            c.clipPath(p, skia.ClipOp.kIntersect, True)
            c.drawRect(skia.Rect(0, 0, ww, hh), paint(shader=lin((0, 0), (ww, hh), [argb("#ffffff", 0.18), argb("#000000", 0.0), argb("#000000", 0.3)], [0, 0.5, 1])))
            c.drawRect(skia.Rect(0, hh * 0.2, ww * 0.15, hh * 0.25), paint(self.trim))
            c.drawRect(skia.Rect(ww * 0.85, hh * 0.2, ww, hh * 0.25), paint(self.trim))
            c.restore()
            c.drawPath(p, paint(shade(self.colr, -0.7), stroke=4))
            text(c, "TIMMY", ww / 2, hh * 0.33, hh * 0.1, self.trim, center=True)
            text(c, self.number, ww / 2, hh * 0.78, hh * 0.4, self.trim, center=True, stroke=6, stroke_c=shade(self.colr, -0.5))
        decal(fr, cam, q, 300, 285, art)


class Skateboard(Piece):
    """Skate deck mounted upright on a side wall: grip tape side to the wall, the printed bottom toward the room."""
    kind = "wall"

    def __init__(self, name, wall, a, y, L=0.8):
        super().__init__(name, *Poster._xz(wall, a), y)
        self.wall, self.a, self.L = wall, a, L
        self.size = (0.21, L, 0.04)

    def bg(self, fr, cam, T):
        a, y, L = self.a, self.y, self.L
        x = ROOM_X - 0.03 if self.wall == "right" else -ROOM_X + 0.03
        q = quad_x(a - 0.105, a + 0.105, y, y + L, x, -1 if self.wall == "right" else 1)

        def art(c, ww, hh):
            c.drawRRect(skia.RRect.MakeRectXY(skia.Rect(4, 4, ww - 4, hh - 4), ww / 2 - 4, ww / 2 - 4), paint(shader=lin((0, 0), (0, hh), [argb("#2adab0"), argb("#3a4ad8"), argb("#d83ab0")])))
            c.drawCircle(ww / 2, hh * 0.5, ww * 0.3, paint("#ffe14a"))
            c.drawCircle(ww / 2 - 10, hh * 0.48, 6, paint("#111"))
            c.drawCircle(ww / 2 + 10, hh * 0.48, 6, paint("#111"))
            c.drawArc(skia.Rect(ww / 2 - 18, hh * 0.5 - 8, ww / 2 + 18, hh * 0.5 + 16), 20, 140, False, paint("#111", stroke=4))
            for yy in (hh * 0.17, hh * 0.83):                  # trucks + wheels
                c.drawRect(skia.Rect(ww * 0.25, yy - 6, ww * 0.75, yy + 6), paint("#b8bcc8"))
                for xx in (ww * 0.16, ww * 0.84):
                    c.drawCircle(xx, yy, 12, paint("#f4f0e0"))
            c.drawRRect(skia.RRect.MakeRectXY(skia.Rect(4, 4, ww - 4, hh - 4), ww / 2 - 4, ww / 2 - 4), paint("#111", stroke=4))
        decal(fr, cam, q, 120, 120 * L / 0.21, art)


# ---- furniture + props (depth sorted) ----------------------------------------------------------------------------
class Desk(Piece):
    """Black gaming desk against the back wall: carbon top, side panels, a cable tray. Desk mat on top. Under it:
    tangled cables, a power strip, chargers."""
    size = (1.8, DESK_Y, DESK_Z1 - DESK_Z0)

    def __init__(self, name="desk", x0=-0.9, x1=0.9):
        super().__init__(name, (x0 + x1) / 2, (DESK_Z0 + DESK_Z1) / 2)
        self.x0, self.x1 = x0, x1
        self.size = (x1 - x0, DESK_Y, DESK_Z1 - DESK_Z0)

    def item(self, cam, T):
        x0, x1 = self.x0, self.x1

        def under(fr):
            # power strip on the floor, plugs, cables snaking up to the desk
            fr.box(cam, (-0.35, 0.05), (0.0, 0.04), (3.35, 3.43), "#e8e8ec", line=1.0)
            for k in range(5):
                fr.box(cam, (-0.31 + 0.07 * k, -0.27 + 0.07 * k), (0.04, 0.07), (3.36, 3.42), "#1a1a20", line=0.8)
                wpath(fr, cam, [(-0.29 + 0.07 * k, 0.07, 3.39), (-0.25 + 0.1 * k, 0.03, 3.25), (-0.4 + 0.18 * k, 0.12, 3.1 + 0.04 * k),
                                (-0.5 + 0.2 * k, 0.45, 3.45), (-0.55 + 0.22 * k, DESK_Y - 0.02, 3.5)], ["#101014", "#202028", "#e8e8ec"][k % 3], 0.008)
            wpath(fr, cam, [(0.05, 0.02, 3.39), (0.3, 0.005, 3.2), (0.45, 0.01, 3.05), (0.62, 0.005, 3.1)], "#ffffff", 0.006)   # phone charger
            fr.box(cam, (0.6, 0.66), (0.0, 0.02), (3.08, 3.12), "#f4f4f4", line=0.8)

        def desk(fr):
            for xa in (x0, x1 - 0.05):
                fr.box(cam, (xa, xa + 0.05), (0.0, DESK_Y - 0.03), (DESK_Z0 + 0.03, DESK_Z1), "#16171e", line=1.3)
            fr.box(cam, (x0 + 0.05, x1 - 0.05), (DESK_Y - 0.22, DESK_Y - 0.03), (DESK_Z1 - 0.06, DESK_Z1 - 0.02), "#121318", line=1.0)
            fr.box(cam, (x0, x1), (DESK_Y - 0.035, DESK_Y), (DESK_Z0, DESK_Z1), "#202230", line=1.5, top_k=0.08)
            # red edge trim along the front, carbon weave on the top
            wline(fr, cam, (x0 + 0.01, DESK_Y - 0.018, DESK_Z0 - 0.001), (x1 - 0.01, DESK_Y - 0.018, DESK_Z0 - 0.001), "#d8283a", 0.006, 0.9)
            for k in np.arange(x0 + 0.06, x1, 0.06):
                wline(fr, cam, (k, DESK_Y + 0.0005, DESK_Z0 + 0.01), (k + 0.03, DESK_Y + 0.0005, DESK_Z1 - 0.01), "#2a2c3c", 0.002, 0.5)
            # oversized desk mat: dark with a purple circuit print and stitched edge
            mat = quad_y(-0.62, 0.62, DESK_Z0 + 0.03, DESK_Z0 + 0.42, DESK_Y + 0.002)

            def art(c, w, h):
                c.drawRect(skia.Rect(0, 0, w, h), paint("#121220"))
                for i in range(16):
                    yy = 20 + i * (h - 40) / 15
                    c.drawLine(40 + (i * 53) % 300, yy, 40 + (i * 53) % 300 + 160, yy, paint("#6a3ad8", a=0.35, stroke=3))
                    c.drawCircle(40 + (i * 53) % 300 + 160, yy, 6, paint("#6a3ad8", a=0.5))
                text(c, "TOON", w * 0.82, h * 0.88, 44, "#8a5af8", a=0.7, center=True)
                c.drawRRect(skia.RRect.MakeRectXY(skia.Rect(6, 6, w - 6, h - 6), 16, 16), paint("#8a5af8", a=0.6, stroke=5))
            decal(fr, cam, mat, 1000, 320, art)
        return [self.it(cam, under, (self.x, 0.2, DESK_Z1 + 0.02), "_under"), self.it(cam, desk, (self.x, 0.4, DESK_Z1 - 0.02))]

    def solid(self):
        return ((self.x0, self.x1), (0.0, DESK_Y), (DESK_Z0, DESK_Z1))


class Monitor(Piece):
    """Flat monitor on a stand on the desk. orient = h (27" landscape) | v (24" portrait). screen(c, w, h, T) draws the
    picture; the screen also glows into the room."""

    def __init__(self, name, x, z, orient="h", screen=None, y=DESK_Y, glow="#7aa8ff"):
        super().__init__(name, x, z, y)
        self.orient, self.screen, self.glow = orient, screen, glow
        self.sw, self.sh = (0.62, 0.36) if orient == "h" else (0.33, 0.58)
        self.y_low = y + (0.17 if orient == "h" else 0.15)
        self.size = (self.sw + 0.03, self.y_low - y + self.sh + 0.03, 0.2)

    def corners(self, inset=0.012):
        x, z, w, y0 = self.x, self.z - 0.015, self.sw, self.y_low
        return quad_z(x - w / 2 + inset, x + w / 2 - inset, y0 + inset, y0 + self.sh - inset, z - 0.001)

    def item(self, cam, T):
        x, z, w, y0, y = self.x, self.z, self.sw, self.y_low, self.y

        def fn(fr):
            fr.box(cam, (x - 0.13, x + 0.13), (y, y + 0.012), (z - 0.05, z + 0.12), "#1a1b22", line=1.0)       # foot
            fr.box(cam, (x - 0.025, x + 0.025), (y, y0 + 0.12), (z + 0.03, z + 0.06), "#24252e", line=1.0)     # neck
            fr.box(cam, (x - w / 2, x + w / 2), (y0, y0 + self.sh), (z - 0.015, z + 0.012), "#111218", line=1.4)
            pts = self.corners()
            if self.screen:
                decal(fr, cam, pts, 540 if self.orient == "h" else 330, 310 if self.orient == "h" else 580,
                      lambda c, ww, hh: self.screen(c, ww, hh, T))
            wglow(fr, cam, (x, y0 + self.sh / 2, z - 0.05), 0.55 if self.orient == "h" else 0.45, self.glow, 0.13)
        return self.it(cam, fn, (x, y0, z))

    def solid(self):
        return ((self.x - self.sw / 2, self.x + self.sw / 2), (self.y, self.y_low + self.sh), (self.z - 0.05, self.z + 0.12))

    def lights(self):
        return [Light(self.name, (self.x, self.y_low + self.sh / 2, self.z - 0.25), self.glow, 1.3, 0.55)]


class Webcam(Piece):
    """Clip-on webcam on top of a monitor bezel; recording light on."""

    def __init__(self, name, monitor):
        m = monitor
        super().__init__(name, m.x, m.z - 0.02, m.y_low + m.sh)
        self.size = (0.1, 0.035, 0.04)

    def item(self, cam, T):
        x, y, z = self.x, self.y, self.z

        def fn(fr):
            fr.box(cam, (x - 0.05, x + 0.05), (y, y + 0.035), (z - 0.03, z + 0.01), "#15161c", line=1.0)
            p = cam.proj((x, y + 0.018, z - 0.031))
            if p[2] > 0.15:
                fr.c.drawCircle(p[0], p[1], 0.012 * p[3], paint("#2a3a5a"))
                fr.c.drawCircle(p[0] - 0.003 * p[3], p[1] - 0.003 * p[3], 0.004 * p[3], paint("#9ab8ff"))
                q = cam.proj((x + 0.035, y + 0.018, z - 0.031))
                fr.c.drawCircle(q[0], q[1], max(1.0, 0.003 * q[3]), paint("#ff2a2a", a=0.6 + 0.4 * (int(T * 2) % 2)))
        return self.it(cam, fn, (x, y, z - 0.04))


class PC(Piece):
    """Gaming tower standing on the desk, tempered-glass side panel toward the room (-z): three RGB intake fans down the
    front edge, a rear exhaust fan, an AIO pump ring, rainbow RAM, the graphics card across the middle with its fans and
    light bar, the PSU shroud, a few stickers on the steel."""
    size = (0.46, 0.5, 0.22)

    def __init__(self, name, x, z, y=DESK_Y):
        super().__init__(name, x, z, y)

    def item(self, cam, T):
        x, z, y = self.x, self.z, self.y
        x0, x1, y0, y1, z0, z1 = x - 0.23, x + 0.23, y + 0.02, y + 0.5, z - 0.11, z + 0.11

        def fn(fr):
            for fx in (x0 + 0.03, x1 - 0.03):                   # feet
                fr.box(cam, (fx - 0.02, fx + 0.02), (y, y0), (z0 + 0.01, z1 - 0.01), "#0c0c10", line=0.8)
            fr.box(cam, (x0, x1), (y0, y1), (z0, z1), "#15161d", line=1.6)
            # glass panel: interior seen through it
            gl = quad_z(x0 + 0.015, x1 - 0.015, y0 + 0.015, y1 - 0.015, z0 - 0.002)

            def inside(c, w, h):
                c.drawRect(skia.Rect(0, 0, w, h), paint("#07070c"))
                c.drawRect(skia.Rect(w * 0.04, h * 0.04, w * 0.78, h * 0.72), paint("#14151e"))         # motherboard
                for k in range(6):
                    c.drawLine(w * 0.08, h * (0.1 + 0.1 * k), w * 0.7, h * (0.1 + 0.1 * k), paint("#22243a", stroke=2))
                # front fans down the right edge, rear fan top-left: rings of colour
                fans = [(w * 0.89, h * (0.17 + 0.27 * k), w * 0.095, k * 0.1) for k in range(3)] + [(w * 0.13, h * 0.17, w * 0.085, 0.45)]
                for cx, cy, r, off in fans:
                    col = hue(T, off)
                    c.drawCircle(cx, cy, r * 1.25, paint(blend="add", shader=skia.GradientShader.MakeRadial(
                        skia.Point(cx, cy), r * 1.35, [argb(col, 0.55), argb(col, 0.0)], [0.6, 1.0])))
                    c.drawCircle(cx, cy, r, paint("#0c0c12"))
                    c.drawCircle(cx, cy, r * 0.92, paint(col, stroke=r * 0.14))
                    sp = T * 9.0 + off * 7
                    for b in range(7):                         # spinning blades (motion-blurred: soft and thin)
                        a = sp + b * math.tau / 7
                        c.drawLine(cx + math.cos(a) * r * 0.22, cy + math.sin(a) * r * 0.22, cx + math.cos(a + 0.5) * r * 0.78,
                                   cy + math.sin(a + 0.5) * r * 0.78, paint("#2a2c3a", a=0.8, stroke=r * 0.2))
                    c.drawCircle(cx, cy, r * 0.22, paint("#1a1a24"))
                # AIO pump with an RGB ring, tubes to the front radiator
                pc_ = hue(T, 0.25)
                c.drawCircle(w * 0.4, h * 0.26, w * 0.065, paint("#101018"))
                c.drawCircle(w * 0.4, h * 0.26, w * 0.06, paint(pc_, stroke=5))
                text(c, "TOON", w * 0.4, h * 0.27, 11, "#e8e8f0", center=True)
                for k in range(2):
                    p = skia.Path()
                    p.moveTo(w * 0.43, h * (0.23 + 0.05 * k))
                    p.cubicTo(w * 0.6, h * (0.12 + 0.05 * k), w * 0.7, h * (0.3 + 0.06 * k), w * 0.84, h * (0.2 + 0.1 * k))
                    c.drawPath(p, paint("#1c1c26", stroke=7))
                for k in range(4):                             # RAM sticks, a rainbow wave
                    c.drawRect(skia.Rect(w * (0.53 + 0.035 * k), h * 0.1, w * (0.555 + 0.035 * k), h * 0.4), paint("#20222e"))
                    c.drawRect(skia.Rect(w * (0.53 + 0.035 * k), h * 0.1, w * (0.555 + 0.035 * k), h * 0.15), paint(hue(T, 0.6 + 0.07 * k)))
                # graphics card: shroud, light bar, backplate edge
                c.drawRect(skia.Rect(w * 0.06, h * 0.47, w * 0.76, h * 0.6), paint("#2a2c38"))
                c.drawRect(skia.Rect(w * 0.06, h * 0.6, w * 0.76, h * 0.64), paint("#101016"))
                c.drawRect(skia.Rect(w * 0.1, h * 0.49, w * 0.55, h * 0.515), paint(hue(T, 0.33)))
                text(c, "VOLT GX", w * 0.58, h * 0.565, 13, "#c8c8d8", center=True)
                for k in range(3):
                    c.drawCircle(w * (0.2 + 0.2 * k), h * 0.62, w * 0.06, paint("#18181f", a=0.9))
                # PSU shroud + cable comb
                c.drawRect(skia.Rect(0, h * 0.75, w, h), paint("#111118"))
                text(c, "TOON", w * 0.3, h * 0.9, 16, "#4a4a5a", center=True)
                c.drawRect(skia.Rect(0, 0, w, h), paint(shader=lin((0, 0), (w, h), [argb("#ffffff", 0.1), argb("#ffffff", 0.0), argb("#ffffff", 0.05)], [0, 0.45, 1])))
            decal(fr, cam, gl, 460, 480, inside)
            wglow(fr, cam, (x, (y0 + y1) / 2, z0 - 0.02), 0.5, hue(T, 0.1), 0.2)
            # front panel mesh + power button + stickers on the steel (top and right side)
            if cam.pos[0] > x1:
                fr.poly(cam, quad_x(z0 + 0.02, z1 - 0.02, y0 + 0.03, y1 - 0.03, x1 + 0.001, -1), colr="#0f1016", outline="#22242e", line=1.0)
                for k in range(12):
                    wline(fr, cam, (x1 + 0.002, y0 + 0.05 + 0.035 * k, z0 + 0.03), (x1 + 0.002, y0 + 0.05 + 0.035 * k, z1 - 0.03), "#1c1d26", 0.004, 0.9)
            if cam.pos[1] > y1:
                for k, (sx, sz, colr) in enumerate(((x0 + 0.08, z, "#ffe14a"), (x0 + 0.2, z - 0.04, "#3ad0ff"), (x + 0.12, z + 0.03, "#ff4a8a"))):
                    fr.ground_ellipse(cam, sx, sz, 0.03, 0.025, colr, 0.95, y=y1 + 0.001)
            p = cam.proj((x1 - 0.03, y1 - 0.02, z0 - 0.003))
            if p[2] > 0.15:
                fr.c.drawCircle(p[0], p[1], 0.008 * p[3], paint("#ffffff", a=0.9))
        return self.it(cam, fn, (x, y + 0.25, z))

    def solid(self):
        return ((self.x - 0.23, self.x + 0.23), (self.y, self.y + 0.5), (self.z - 0.11, self.z + 0.11))

    def lights(self):
        return [Light(self.name, (self.x, self.y + 0.28, self.z - 0.35), "#ffffff", 1.1, 0.55, colr_fn=lambda T: hue(T, 0.1))]


class Keyboard(Piece):
    """Tenkeyless mechanical keyboard with a rainbow wave under the keycaps; a gaming mouse beside it."""
    size = (0.62, 0.035, 0.16)

    def __init__(self, name, x, z, y=DESK_Y + 0.002):
        super().__init__(name, x, z, y)

    def item(self, cam, T):
        x, z, y = self.x, self.z, self.y

        def fn(fr):
            fr.box(cam, (x - 0.22, x + 0.22), (y, y + 0.03), (z - 0.07, z + 0.07), "#18191f", line=1.2)

            def keys(c, w, h):
                c.drawRect(skia.Rect(0, 0, w, h), paint("#0e0e14"))
                for r in range(5):
                    for k in range(15 if r else 14):
                        kw = w / 15.5
                        cx = 6 + k * kw + (r % 2) * 4
                        col = hue(T, k * 0.05 - r * 0.03, speed=0.35)
                        c.drawRect(skia.Rect(cx - 1, 6 + r * h / 5.2 - 1, cx + kw - 2, 6 + (r + 1) * h / 5.2 - 3), paint(col, a=0.8))
                        c.drawRect(skia.Rect(cx + 2, 8 + r * h / 5.2, cx + kw - 5, 4 + (r + 1) * h / 5.2 - 5), paint("#1c1d26"))
                c.drawRect(skia.Rect(w * 0.3, h * 0.82, w * 0.7, h * 0.97), paint("#1c1d26"))
            decal(fr, cam, quad_y(x - 0.21, x + 0.21, z - 0.065, z + 0.065, y + 0.031), 620, 200, keys)
            # mouse on the mat to the right
            mx, mz = x + 0.33, z - 0.01
            p = cam.proj((mx, y + 0.02, mz))
            if p[2] > 0.15:
                s = p[3]
                path = skia.Path()
                path.addOval(skia.Rect(p[0] - 0.03 * s, p[1] - 0.025 * s, p[0] + 0.03 * s, p[1] + 0.03 * s))
                fr.part(path, "#1a1b22", line=1.2)
                fr.c.drawLine(p[0], p[1] - 0.024 * s, p[0], p[1] - 0.005 * s, paint(hue(T, 0.5), stroke=max(1.0, 0.004 * s)))
                fr.glow(p[0], p[1] + 0.02 * s, 0.05 * s, hue(T, 0.5), a=0.35)
            wpath(fr, cam, [(mx, y + 0.01, mz + 0.03), (mx + 0.03, y + 0.005, mz + 0.15), (mx - 0.05, y + 0.004, DESK_Z1 - 0.05)], "#101014", 0.004)
        return self.it(cam, fn, (x, y, z))


class Headset(Piece):
    """Over-ear headset hanging on a hook clamped under the desk's right edge (cups with RGB rings)."""
    size = (0.2, 0.22, 0.1)

    def __init__(self, name, x, z):
        super().__init__(name, x, z, DESK_Y - 0.05)

    def item(self, cam, T):
        x, z, y = self.x, self.z, self.y

        def fn(fr):
            fr.box(cam, (x - 0.01, x + 0.05), (y, y + 0.04), (z - 0.02, z + 0.02), "#2a2a34", line=1.0)        # hook
            c0, c1 = cam.proj((x + 0.05, y - 0.02, z)), cam.proj((x + 0.05, y - 0.2, z))
            if c0[2] < 0.15:
                return
            s = c0[3]
            band = skia.Path()
            band.addArc(skia.Rect(c0[0] - 0.08 * s, c0[1] - 0.01 * s, c0[0] + 0.08 * s, c0[1] + 0.2 * s), 180, 180)
            fr.c.drawPath(band, paint("#14141a", stroke=0.022 * s))
            for sx in (-1, 1):
                cx, cy = c0[0] + sx * 0.078 * s, c0[1] + 0.12 * s
                path = skia.Path()
                path.addOval(skia.Rect(cx - 0.032 * s, cy - 0.05 * s, cx + 0.032 * s, cy + 0.05 * s))
                fr.part(path, "#1c1c24", line=1.2)
                fr.c.drawOval(skia.Rect(cx - 0.024 * s, cy - 0.04 * s, cx + 0.024 * s, cy + 0.04 * s), paint(hue(T, 0.7), stroke=0.006 * s))
        return self.it(cam, fn, (x, y, z - 0.1))


class MicArm(Piece):
    """Boom-arm microphone clamped to the back of the desk: two struts with springs, the mic in a shock mount with a pop
    filter, swung in front of the main monitor's left side."""
    size = (0.4, 0.55, 0.5)

    def __init__(self, name, clamp=(-0.55, DESK_Y, 3.5), mic=(-0.42, 1.02, 3.08)):
        super().__init__(name, clamp[0], clamp[2], clamp[1])
        self.clamp, self.mic = clamp, mic

    def item(self, cam, T):
        cx, cy, cz = self.clamp
        mx, my, mz = self.mic
        elbow = (cx + 0.02, cy + 0.42, cz - 0.15)

        def fn(fr):
            fr.box(cam, (cx - 0.035, cx + 0.035), (cy - 0.05, cy + 0.04), (cz - 0.03, cz + 0.06), "#1c1c22", line=1.0)
            for a, b in (((cx, cy + 0.04, cz), elbow), (elbow, (mx, my + 0.1, mz + 0.03))):
                wline(fr, cam, a, b, "#18181e", 0.018)
                m = tuple((p + q) / 2 for p, q in zip(a, b))
                wline(fr, cam, tuple(p + 0.25 * (q - p) for p, q in zip(a, m)), tuple(p + 0.75 * (q - p) for p, q in zip(m, b)), "#3a3a48", 0.006)
            p = cam.proj(elbow)
            if p[2] > 0.15:
                fr.c.drawCircle(p[0], p[1], 0.018 * p[3], paint("#22222a"))
            cyl(fr, cam, (mx, my - 0.06, mz), 0.03, 0.16, "#202028")
            for k in range(5):
                wline(fr, cam, (mx - 0.03, my + 0.02 + 0.02 * k, mz - 0.031), (mx + 0.03, my + 0.02 + 0.02 * k, mz - 0.031), "#4a4a58", 0.003, 0.9)
            q = cam.proj((mx, my + 0.06, mz - 0.09))                    # pop filter
            if q[2] > 0.15:
                fr.c.drawCircle(q[0], q[1], 0.06 * q[3], paint("#0a0a10", a=0.45))
                fr.c.drawCircle(q[0], q[1], 0.06 * q[3], paint("#2a2a34", stroke=max(1.0, 0.006 * q[3])))
        return self.it(cam, fn, (mx, my, mz - 0.1))


class KeyLight(Piece):
    """Streamer key light: a soft LED panel on a pole clamped to the desk's front-left corner, angled at the chair. It is
    the face light: warm white, lights the subject not the room."""
    size = (0.3, 1.0, 0.1)

    def __init__(self, name, x=-0.86, z=3.0):
        super().__init__(name, x, z, DESK_Y)
        self.panel = (x + 0.05, DESK_Y + 0.82, z - 0.05)

    def item(self, cam, T):
        x, z, y = self.x, self.z, self.y
        px, py, pz = self.panel

        def fn(fr):
            fr.box(cam, (x - 0.03, x + 0.03), (y - 0.06, y + 0.03), (z - 0.03, z + 0.03), "#1a1a20", line=1.0)
            wline(fr, cam, (x, y, z), (px, py - 0.1, pz), "#202028", 0.014)
            fr.box(cam, (px - 0.15, px + 0.15), (py - 0.1, py + 0.1), (pz - 0.02, pz + 0.02), "#1a1a20", line=1.2)
            q = quad_z(px - 0.14, px + 0.14, py - 0.09, py + 0.09, pz - 0.021)
            fr.poly(cam, q, shader=lambda p: lin((0, p.getBounds().top()), (0, p.getBounds().bottom()), [argb("#f6dcb4"), argb("#c8a070")]))
            wglow(fr, cam, (px, py, pz - 0.05), 0.45, "#ffc88a", 0.28)
        return self.it(cam, fn, (px, py, pz))

    def lights(self):
        return [Light(self.name, (self.panel[0] + 0.3, self.panel[1], self.panel[2] - 0.9), "#ffe2c0", 1.6, 0.8)]


class ControllerDock(Piece):
    """Charging dock with a controller standing in it (blue charge light), on the desk's right."""
    size = (0.16, 0.14, 0.08)

    def __init__(self, name, x, z):
        super().__init__(name, x, z, DESK_Y)

    def item(self, cam, T):
        x, z, y = self.x, self.z, self.y

        def fn(fr):
            fr.box(cam, (x - 0.08, x + 0.08), (y, y + 0.03), (z - 0.04, z + 0.04), "#1c1d24", line=1.0)
            wline(fr, cam, (x - 0.06, y + 0.031, z - 0.041), (x + 0.06, y + 0.031, z - 0.041), "#3a8aff", 0.004)
            controller(fr, cam, (x, y + 0.08, z - 0.005), 0.12, "#e8e8ee", T)
        return self.it(cam, fn, (x, y, z - 0.05))


def controller(fr, cam, c, w, colr, T=0.0, flat=False, worn=False):
    """A gamepad seen from the front (standing) or lying face up (flat): body with grips, sticks, buttons."""
    if flat:
        P = [cam.proj((c[0] - w / 2, c[1], c[2] + w * 0.3)), cam.proj((c[0] + w / 2, c[1], c[2] + w * 0.3)),
             cam.proj((c[0] + w / 2, c[1], c[2] - w * 0.3)), cam.proj((c[0] - w / 2, c[1], c[2] - w * 0.3))]
        corners = [(c[0] - w / 2, c[1], c[2] + w * 0.32), (c[0] + w / 2, c[1], c[2] + w * 0.32), (c[0] + w / 2, c[1], c[2] - w * 0.32),
                   (c[0] - w / 2, c[1], c[2] - w * 0.32)]
        if min(p[2] for p in P) < 0.15:
            return
    else:
        corners = quad_z(c[0] - w / 2, c[0] + w / 2, c[1] - w * 0.34, c[1] + w * 0.34, c[2])

    def art(cv, ww, hh):
        p = skia.Path()
        p.moveTo(ww * 0.2, hh * 0.1)
        p.lineTo(ww * 0.8, hh * 0.1)
        p.cubicTo(ww * 1.02, hh * 0.1, ww * 1.05, hh * 0.95, ww * 0.88, hh * 0.98)
        p.cubicTo(ww * 0.76, hh * 1.0, ww * 0.7, hh * 0.7, ww * 0.6, hh * 0.68)
        p.lineTo(ww * 0.4, hh * 0.68)
        p.cubicTo(ww * 0.3, hh * 0.7, ww * 0.24, hh * 1.0, ww * 0.12, hh * 0.98)
        p.cubicTo(-ww * 0.05, hh * 0.95, -ww * 0.02, hh * 0.1, ww * 0.2, hh * 0.1)
        p.close()
        cv.drawPath(p, paint(colr))
        cv.save()
        cv.clipPath(p, skia.ClipOp.kIntersect, True)
        cv.drawRect(skia.Rect(0, 0, ww, hh), paint(shader=lin((0, 0), (0, hh), [argb("#ffffff", 0.2), argb("#000000", 0.0), argb("#000000", 0.3)], [0, 0.5, 1])))
        cv.restore()
        cv.drawPath(p, paint(shade(colr, -0.65), stroke=4))
        for sx in (0.33, 0.6):
            cv.drawCircle(ww * sx, hh * 0.52, hh * 0.11, paint("#1a1a20"))
            cv.drawCircle(ww * sx + (3 if worn and sx < 0.5 else 0), hh * 0.5, hh * 0.07, paint("#3a3a44" if not (worn and sx < 0.5) else "#5a5a5a"))
        for k, (bx, by, bc) in enumerate(((0.78, 0.25, "#3ad87a"), (0.85, 0.38, "#ff4a4a"), (0.71, 0.38, "#3a8aff"), (0.78, 0.5, "#ffe14a"))):
            cv.drawCircle(ww * bx, hh * by, hh * 0.05, paint(bc))
        cv.drawRect(skia.Rect(ww * 0.16, hh * 0.32, ww * 0.26, hh * 0.38), paint("#2a2a30"))
        cv.drawRect(skia.Rect(ww * 0.18, hh * 0.27, ww * 0.24, hh * 0.43), paint("#2a2a30"))
        cv.drawRect(skia.Rect(ww * 0.42, hh * 0.18, ww * 0.58, hh * 0.24), paint("#3a8aff", a=0.8))
    decal(fr, cam, corners, 300, 200, art)


class DeskClutter(Piece):
    """The lived-in desk: schoolbooks and notebooks stacked on the left with an unfinished worksheet, pens, a calculator,
    a pencil case, a half-empty water bottle, snack wrappers, a cereal bowl with the spoon left in, the phone charger."""
    size = (1.6, 0.25, 0.5)

    def __init__(self, name="desk_clutter"):
        super().__init__(name, 0.0, 3.15, DESK_Y)

    def item(self, cam, T):
        y = DESK_Y
        out = []

        def books(fr):
            for k, (cc, hh, dx) in enumerate((("#2a6ab8", 0.025, 0.0), ("#c83a3a", 0.02, 0.012), ("#3a9a5a", 0.03, -0.01), ("#e8c84a", 0.015, 0.008))):
                y0 = y + sum(h for _, h, _ in (("", 0.025, 0), ("", 0.02, 0), ("", 0.03, 0), ("", 0.015, 0))[:k])
                fr.box(cam, (-0.86 + dx, -0.64 + dx), (y0, y0 + hh), (3.02, 3.22), cc, line=1.0)
                wline(fr, cam, (-0.858 + dx, y0 + hh * 0.5, 3.019), (-0.642 + dx, y0 + hh * 0.5, 3.019), "#f4f0e0", 0.003, 0.7)
        out.append(self.it(cam, books, (-0.75, y, 3.12), "_books"))

        def sheet(fr):
            q = [(-0.78, y + 0.002, 3.04), (-0.52, y + 0.002, 3.0), (-0.5, y + 0.002, 3.22), (-0.76, y + 0.002, 3.26)]
            q = [q[3], q[2], q[1], q[0]]

            def art(c, w, h):
                c.drawRect(skia.Rect(0, 0, w, h), paint("#f4f2ea"))
                text(c, "MATHS - Worksheet 4", 14, 26, 15, "#2a2a3a", bold=False)
                for i in range(9):
                    yy = 48 + i * 24
                    c.drawLine(14, yy, w - 14, yy, paint("#9ab0d8", stroke=1.2))
                    text(c, f"{i + 1}.", 14, yy - 4, 12, "#2a2a3a", bold=False)
                    if i < 4:                                    # answered...
                        c.drawLine(40, yy - 7, 40 + 40 + (i * 23) % 70, yy - 5, paint("#2a3aa8", stroke=2))
                c.drawLine(40, 48 + 4 * 24 - 7, 70, 48 + 4 * 24 - 9, paint("#2a3aa8", stroke=2))   # ...abandoned mid-answer
                text(c, "?", 80, 48 + 4 * 24 - 3, 16, "#2a3aa8")
            decal(fr, cam, q, 260, 270, art)
            for k, cc in enumerate(("#2a3aa8", "#d83a3a", "#1a1a1a")):                     # pens
                wline(fr, cam, (-0.48 + 0.02 * k, y + 0.006, 3.05 + 0.03 * k), (-0.36 + 0.015 * k, y + 0.006, 3.1 + 0.02 * k), cc, 0.008)
            fr.box(cam, (-0.47, -0.39), (y, y + 0.012), (3.14, 3.26), "#3a3c48", line=1.0)          # calculator
            fr.poly(cam, quad_y(-0.46, -0.4, 3.22, 3.25, y + 0.013), colr="#9ab89a")
            for r in range(3):
                for k in range(3):
                    fr.poly(cam, quad_y(-0.46 + 0.02 * k, -0.448 + 0.02 * k, 3.15 + 0.022 * r, 3.165 + 0.022 * r, y + 0.013), colr="#d8d8e0")
            blob(fr, cam, (-0.82, y + 0.03, 3.36), 0.07, 0.03, "#5a3ab8")                    # pencil case
            wline(fr, cam, (-0.88, y + 0.045, 3.355), (-0.76, y + 0.045, 3.355), "#c8c8d0", 0.003)
        out.append(self.it(cam, sheet, (-0.62, y, 3.1), "_school"))

        def snacks(fr):
            cyl(fr, cam, (0.56, y, 3.22), 0.032, 0.21, "#7ab8ff", a=0.45)                    # water bottle, half full
            cyl(fr, cam, (0.56, y, 3.22), 0.03, 0.09, "#3a8ae8", a=0.55)
            cyl(fr, cam, (0.56, y + 0.21, 3.22), 0.022, 0.03, "#2a5ab8")
            for k, (wx, wz, cc) in enumerate(((0.7, 3.05, "#e8382a"), (0.79, 3.13, "#f0c02a"), (0.66, 3.18, "#3a6ae8"))):     # wrappers
                q = [(wx - 0.05, y + 0.004, wz + 0.02), (wx + 0.04, y + 0.008, wz + 0.03), (wx + 0.05, y + 0.004, wz - 0.02), (wx - 0.04, y + 0.01, wz - 0.03)]
                fr.poly(cam, q, colr=cc, outline=shade(cc, -0.6), line=1.0)
                wline(fr, cam, (wx - 0.02, y + 0.012, wz), (wx + 0.02, y + 0.012, wz + 0.005), "#ffffff", 0.004, 0.7)
            # bowl with the spoon left in
            bx, bz = 0.77, 3.38
            path = cyl(fr, cam, (bx, y, bz), 0.075, 0.05, "#e8e4dc")
            p = cam.proj((bx, y + 0.05, bz))
            if p[2] > 0.15:
                fr.c.drawOval(skia.Rect(p[0] - 0.068 * p[3], p[1] - 0.02 * p[3], p[0] + 0.068 * p[3], p[1] + 0.02 * p[3]), paint("#f2e8c8"))
            wline(fr, cam, (bx - 0.02, y + 0.045, bz), (bx + 0.11, y + 0.11, bz - 0.04), "#c8ccd8", 0.009)
        out.append(self.it(cam, snacks, (0.7, y, 3.2), "_snacks"))
        return out


class GamingChair(Piece):
    """Racing-style gaming chair: five-star base on casters, gas lift, seat, tall back with wings and a headrest pillow,
    armrests; a grey hoodie draped over the top of the back. yaw: 0 = facing the camera (-z), 180 = facing the desk.
    The back and the seat are separate drawables, so whoever sits in it is drawn between them."""
    SEAT_Y = 0.46
    size = (0.7, 1.3, 0.7)

    def __init__(self, name, x, z, colr="#1b1c24", accent="#d8283a"):
        super().__init__(name, x, z)
        self.colr, self.accent = colr, accent
        self.yaw = 0.0                                   # set by the scene each frame (swivel)

    def basis(self):
        a = math.radians(self.yaw)
        f = (math.sin(a), 0.0, -math.cos(a))
        r = (math.cos(a), 0.0, math.sin(a))
        return f, r

    def w(self, fx, y, rx):
        f, r = self.basis()
        return (self.x + f[0] * fx + r[0] * rx, y, self.z + f[2] * fx + r[2] * rx)

    def _slab(self, fr, cam, fx0, fx1, y0, y1, rx0, rx1, colr, line=1.3):
        """A box in the chair's own frame (forward fx, right rx)."""
        pts = [self.w(fx, yy, rx) for fx, rx in ((fx0, rx0), (fx1, rx0), (fx1, rx1), (fx0, rx1)) for yy in (y0,)]
        top = [self.w(fx, y1, rx) for fx, rx in ((fx0, rx0), (fx1, rx0), (fx1, rx1), (fx0, rx1))]
        faces = [[pts[0], pts[1], top[1], top[0]], [pts[1], pts[2], top[2], top[1]], [pts[2], pts[3], top[3], top[2]],
                 [pts[3], pts[0], top[0], top[3]], top]
        C = cam.pos
        for i, q in enumerate(faces):
            fc = [sum(p[k] for p in q) / 4 for k in range(3)]
            if i < 4:
                ctr = self.w((fx0 + fx1) / 2, (y0 + y1) / 2, (rx0 + rx1) / 2)
                n = (fc[0] - ctr[0], 0.0, fc[2] - ctr[2])
            else:
                n = (0.0, 1.0, 0.0)
            if n[0] * (C[0] - fc[0]) + n[1] * (C[1] - fc[1]) + n[2] * (C[2] - fc[2]) <= 0:
                continue
            fr.poly(cam, q, colr=shade(colr, 0.1 if i == 4 else -0.12 * (i % 2)), outline=shade(colr, -0.75), line=line)

    def back_item(self, cam, T):
        def fn(fr):
            c = self.colr
            self._slab(fr, cam, -0.26, -0.18, self.SEAT_Y + 0.08, self.SEAT_Y + 0.82, -0.22, 0.22, c)
            for sx in (-1, 1):                                 # wings + red side panels
                self._slab(fr, cam, -0.25, -0.16, self.SEAT_Y + 0.12, self.SEAT_Y + 0.62, sx * 0.22, sx * 0.25, self.accent, line=1.0)
            self._slab(fr, cam, -0.25, -0.17, self.SEAT_Y + 0.84, self.SEAT_Y + 0.92, -0.17, 0.17, c)
            # the front face of the back: stitched panel + logo (only when the chair faces the camera)
            f, _ = self.basis()
            if f[2] * (cam.pos[2] - self.z) + f[0] * (cam.pos[0] - self.x) > 0:
                q = [self.w(-0.179, self.SEAT_Y + 0.78, -0.13), self.w(-0.179, self.SEAT_Y + 0.78, 0.13), self.w(-0.179, self.SEAT_Y + 0.12, 0.13),
                     self.w(-0.179, self.SEAT_Y + 0.12, -0.13)]
                fr.poly(cam, q, colr=shade(c, 0.12), outline=shade(c, -0.6), line=1.0)
                pl = self.w(-0.17, self.SEAT_Y + 0.66, 0.0)                    # headrest pillow
                blob(fr, cam, pl, 0.1, 0.05, "#2a2b36", line=1.0)
            else:
                # from behind: the hoodie draped over the top, sleeves hanging down the back
                for sx in (-1, 1):
                    q = [self.w(-0.265, self.SEAT_Y + 0.86, sx * 0.05), self.w(-0.265, self.SEAT_Y + 0.86, sx * 0.17),
                         self.w(-0.27, self.SEAT_Y + 0.42, sx * 0.2), self.w(-0.27, self.SEAT_Y + 0.46, sx * 0.1)]
                    fr.poly(cam, q, colr="#7a8090", outline="#3a3e4a", line=1.2)
            # the hoodie slung over the top: a soft fold on the headrest, one sleeve hanging down the side
            wpath(fr, cam, [self.w(-0.22, self.SEAT_Y + 0.9, 0.15), self.w(-0.23, self.SEAT_Y + 0.75, 0.24),
                            self.w(-0.22, self.SEAT_Y + 0.52, 0.25)], "#4a5068", 0.07)
            blob(fr, cam, self.w(-0.22, self.SEAT_Y + 0.91, 0.03), 0.16, 0.05, "#4a5068", line=1.2)
        return (cam.view(self.w(-0.22, 0.8, 0.0))[2], fn, self.name + "_back")

    def seat_item(self, cam, T, behind=None):
        def fn(fr):
            c = self.colr
            for k in range(5):                                  # five-star base, casters
                a = math.radians(self.yaw + 36 + 72 * k)
                tip = (self.x + 0.3 * math.sin(a), 0.07, self.z + 0.3 * math.cos(a))
                wline(fr, cam, (self.x, 0.1, self.z), tip, "#101014", 0.035)
                cyl(fr, cam, (tip[0], 0.0, tip[2]), 0.028, 0.05, "#0c0c10", line=1.0)
            cyl(fr, cam, (self.x, 0.1, self.z), 0.03, self.SEAT_Y - 0.16, "#2a2a32")
            cyl(fr, cam, (self.x, 0.1, self.z), 0.045, 0.1, "#141418")
            self._slab(fr, cam, -0.24, 0.24, self.SEAT_Y - 0.06, self.SEAT_Y, -0.24, 0.24, c)
            for sx in (-1, 1):
                self._slab(fr, cam, -0.18, 0.2, self.SEAT_Y, self.SEAT_Y + 0.04, sx * 0.2, sx * 0.25, self.accent, line=1.0)   # bolsters
                self._slab(fr, cam, -0.04, 0.0, self.SEAT_Y - 0.06, self.SEAT_Y + 0.2, sx * 0.27, sx * 0.3, "#141418", line=1.0)
                self._slab(fr, cam, -0.12, 0.12, self.SEAT_Y + 0.2, self.SEAT_Y + 0.23, sx * 0.26, sx * 0.31, "#22232c", line=1.0)  # armrest
        d = cam.view((self.x, 0.4, self.z))[2]
        return (max(d, behind) if behind is not None else d, fn, self.name + "_seat")

    def item(self, cam, T):
        return [self.back_item(cam, T), self.seat_item(cam, T)]

    def solid(self):
        return ((self.x - 0.3, self.x + 0.3), (0.0, self.SEAT_Y), (self.z - 0.3, self.z + 0.3))


class Bed(Piece):
    """Single bed along the left wall, head at the back: dark wood frame, grey sheet, an unmade dark navy duvet thrown
    back in a heap, two pillows, the phone face down on the duvet. LED strip glow underneath (Shell)."""
    size = (0.95, 0.62, 2.05)

    def __init__(self, name, x0=-ROOM_X, x1=-1.05, z0=0.65, z1=2.7):
        super().__init__(name, (x0 + x1) / 2, (z0 + z1) / 2)
        self.x0, self.x1, self.z0, self.z1 = x0, x1, z0, z1

    def item(self, cam, T):
        x0, x1, z0, z1 = self.x0, self.x1, self.z0, self.z1
        top = 0.5

        def base(fr):
            fr.box(cam, (x0, x1), (0.08, top - 0.14), (z0, z1), "#2a2420", line=1.3)
            fr.box(cam, (x0 + 0.01, x1 - 0.01), (top - 0.14, top), (z0 + 0.01, z1 - 0.01), getattr(self, "mattress", "#9ea4b2"), line=1.2)
            fr.box(cam, (x0, x1), (0.08, top + 0.32), (z1 - 0.05, z1), "#2a2420", line=1.3)          # headboard
            for lz in (z0 + 0.03, z1 - 0.08):
                fr.box(cam, (x1 - 0.06, x1 - 0.02), (0.0, 0.08), (lz, lz + 0.05), "#1a1612", line=1.0)
            for k, px in enumerate((x0 + 0.24, x0 + 0.68) if getattr(self, "pillows", True) else ()):   # pillows
                blob(fr, cam, (px, top + 0.07, z1 - 0.22), 0.2, 0.08, "#c8ccd8" if k else "#b8bcca")

        def duvet(fr):
            q = [(x0 + 0.02, top + 0.02, z1 - 0.55), (x1 + 0.03, top + 0.04, z1 - 0.6), (x1 + 0.04, 0.2, z0 + 0.2), (x1 + 0.02, top + 0.05, z0 + 0.05),
                 (x0 + 0.02, top + 0.04, z0 + 0.05)]
            fr.poly(cam, q, colr="#232b48", outline="#0e1222", line=1.4)
            for k, (bx, bz, rx) in enumerate(((x0 + 0.5, z1 - 0.7, 0.32), (x0 + 0.62, z0 + 0.9, 0.28), (x0 + 0.38, z0 + 0.45, 0.24))):
                blob(fr, cam, (bx, top + 0.1, bz), rx, 0.1, "#2a3456" if k % 2 else "#252e4e", line=1.2)       # rucked-up folds
            # phone face down on the duvet
            fr.box(cam, (x0 + 0.42, x0 + 0.5), (top + 0.16, top + 0.17), (z0 + 1.12, z0 + 1.27), "#18181e", line=1.0)
            p = cam.proj((x0 + 0.48, top + 0.172, z0 + 1.25))
            if p[2] > 0.15:
                fr.c.drawCircle(p[0], p[1], 0.008 * p[3], paint("#3a3a44"))
        far = z1 + 0.3 if cam.pos[2] < z1 else z0 - 0.3
        return [self.it(cam, base, ((x0 + x1) / 2, 0.3, far), "_base"), self.it(cam, duvet, ((x0 + x1) / 2, 0.3, (z0 + z1) / 2 - 0.2), "_duvet")]

    def solid(self):
        return ((self.x0, self.x1), (0.0, 0.62), (self.z0, self.z1))


class BedsideTable(Piece):
    """Bedside table at the bed head: a drawer, a small warm lamp, an alarm clock with red digits, a charger cable."""
    size = (0.42, 0.5, 0.4)

    def __init__(self, name, x=-1.76, z=3.05):
        super().__init__(name, x, z)

    def item(self, cam, T):
        x, z = self.x, self.z
        y = 0.5

        def fn(fr):
            fr.box(cam, (x - 0.21, x + 0.21), (0.0, y), (z - 0.2, z + 0.2), "#3a2e28", line=1.3)
            fr.poly(cam, quad_z(x - 0.17, x + 0.17, 0.27, 0.43, z - 0.201), colr="#463830", outline="#1a1410", line=1.0)
            fr.box(cam, (x - 0.03, x + 0.03), (0.34, 0.36), (z - 0.215, z - 0.2), "#b8a070", line=0.8)
            # alarm clock
            fr.box(cam, (x + 0.02, x + 0.16), (y, y + 0.07), (z - 0.12, z - 0.05), "#121216", line=1.0)

            def digits(c, w, h):
                c.drawRect(skia.Rect(0, 0, w, h), paint("#0a0606"))
                text(c, "11:47", w / 2, h * 0.78, h * 0.72, "#ff2a2a", center=True)
            decal(fr, cam, quad_z(x + 0.03, x + 0.15, y + 0.012, y + 0.06, z - 0.121), 200, 80, digits)
            wglow(fr, cam, (x + 0.09, y + 0.035, z - 0.14), 0.12, "#ff2a2a", 0.25)
            # lamp: base, stem, glowing shade
            lx, lz = x - 0.08, z + 0.04
            cyl(fr, cam, (lx, y, lz), 0.05, 0.025, "#2a2420")
            # a tall stem so the shade clears the headboard: the warm pool reads from the room
            wglow(fr, cam, (lx, y + 0.6, ROOM_Z - 0.05), 1.1, "#ffb46a", 0.22)       # warm wash on the wall behind
            cyl(fr, cam, (lx, y + 0.025, lz), 0.008, 0.34, "#b8a070")
            cyl(fr, cam, (lx, y + 0.34, lz), 0.085, 0.13, "#f3d8a8")
            wglow(fr, cam, (lx, y + 0.4, lz), 0.75, "#ffb46a", 0.42)
            wglow(fr, cam, (lx, y + 0.4, lz), 0.16, "#fff0d0", 0.5)
            wpath(fr, cam, [(x + 0.1, y + 0.002, z), (x + 0.2, y + 0.002, z + 0.02), (x + 0.22, y - 0.1, z + 0.05), (x + 0.24, 0.08, z - 0.1)], "#f4f4f4", 0.004)
        return self.it(cam, fn, (x, 0.3, z))

    def solid(self):
        return ((self.x - 0.21, self.x + 0.21), (0.0, 0.5), (self.z - 0.2, self.z + 0.2))

    def lights(self):
        return [Light(self.name, (self.x - 0.08, 0.9, self.z - 0.1), "#ffb46a", 1.3, 0.85)]


class Wardrobe(Piece):
    """Tall wardrobe on the right wall: two doors facing the room (-x), the near one slightly open showing hanging
    clothes; stickers on the doors."""
    size = (0.58, 2.0, 1.1)

    def __init__(self, name, z0=2.38, z1=3.5, x0=1.42, open_deg=22.0):
        super().__init__(name, (x0 + ROOM_X) / 2, (z0 + z1) / 2)
        self.x0, self.z0, self.z1, self.open = x0, z0, z1, open_deg

    def item(self, cam, T):
        x0, x1, z0, z1 = self.x0, ROOM_X, self.z0, self.z1
        zm = (z0 + z1) / 2

        def fn(fr):
            fr.box(cam, (x0, x1), (0.0, 2.0), (z0, z1), "#8a7a6c", line=1.5)
            fr.box(cam, (x0 - 0.02, x1), (1.98, 2.04), (z0 - 0.02, z1 + 0.02), "#7a6a5e", line=1.2)
            # inside, behind the open door: dark, a rail, hanging shirts
            fr.poly(cam, quad_x(z0 + 0.03, zm - 0.01, 0.08, 1.92, x0 - 0.001, -1), colr="#100e12")
            for k, cc in enumerate(("#c83a3a", "#3a5ad8", "#e8e4dc", "#2a2a30", "#3a8a5a")):
                zz = z0 + 0.08 + k * 0.085
                if zz < zm - 0.05:
                    fr.poly(cam, quad_x(zz - 0.035, zz + 0.035, 1.15, 1.75, x0 - 0.003, -1), colr=cc, outline=shade(cc, -0.6), line=1.0)
            fr.poly(cam, quad_x(zm + 0.01, z1 - 0.03, 0.08, 1.92, x0 - 0.002, -1), colr="#958676", outline="#4a3e34", line=1.2)    # far door
            for k, (sz, sy, cc) in enumerate(((zm + 0.2, 1.3, "#ffe14a"), (zm + 0.33, 1.05, "#3ad0ff"), (zm + 0.15, 0.9, "#ff4a8a"))):
                q = cam.proj((x0 - 0.004, sy, sz))
                if q[2] > 0.15:
                    fr.c.drawCircle(q[0], q[1], 0.035 * q[3], paint(cc))
                    fr.c.drawCircle(q[0], q[1], 0.035 * q[3], paint(shade(cc, -0.6), stroke=1.2))
            fr.box(cam, (x0 - 0.03, x0 - 0.01), (0.95, 1.15), (zm + 0.03, zm + 0.05), "#c8b890", line=0.8)
            # the near door, swung open about its hinge at z0
            a = math.radians(self.open)
            L = zm - z0 - 0.01
            ex, ez = x0 - L * math.sin(a), z0 + 0.01 + L * math.cos(a)
            fr.poly(cam, [(x0, 1.92, z0 + 0.01), (ex, 1.92, ez), (ex, 0.08, ez), (x0, 0.08, z0 + 0.01)], colr="#958676", outline="#4a3e34", line=1.3)
        return self.it(cam, fn, (x0 - 0.1, 1.0, zm))

    def solid(self):
        return ((self.x0, ROOM_X), (0.0, 2.0), (self.z0, self.z1))


class Drawers(Piece):
    """Chest of drawers on the right wall: four drawers (one ajar with a sock hanging out), stickers; trophies, a medal and
    a brick-built spaceship on top."""
    size = (0.45, 0.88, 0.85)

    def __init__(self, name, z0=1.32, z1=2.17, x0=1.55):
        super().__init__(name, (x0 + ROOM_X) / 2, (z0 + z1) / 2)
        self.x0, self.z0, self.z1 = x0, z0, z1

    def item(self, cam, T):
        x0, x1, z0, z1 = self.x0, ROOM_X, self.z0, self.z1
        top = 0.88

        def fn(fr):
            fr.box(cam, (x0, x1), (0.04, top), (z0, z1), "#e2dcd2", line=1.4)
            for k in range(4):
                y0 = 0.1 + k * 0.19
                dx = 0.05 if k == 2 else 0.0
                fr.box(cam, (x0 - 0.012 - dx, x0 + 0.05), (y0, y0 + 0.16), (z0 + 0.03, z1 - 0.03), "#d4cdc0", line=1.1)
                cyl(fr, cam, (x0 - 0.02 - dx, y0 + 0.075, (z0 + z1) / 2), 0.012, 0.012, "#5a5a64", line=0.8)
            wpath(fr, cam, [(x0 - 0.06, 0.53, z0 + 0.25), (x0 - 0.08, 0.42, z0 + 0.28), (x0 - 0.07, 0.34, z0 + 0.3)], "#e8e8f0", 0.05)   # the sock
            for k, (sz, sy, cc) in enumerate(((z0 + 0.15, 0.7, "#3ad87a"), (z1 - 0.2, 0.32, "#ffe14a"), (z1 - 0.12, 0.75, "#ff4a4a"))):
                q = cam.proj((x0 - 0.013, sy, sz))
                if q[2] > 0.15:
                    fr.c.drawCircle(q[0], q[1], 0.03 * q[3], paint(cc))
            # trophies (gold cups on plinths), a medal, the brick ship
            for k, (tz, th) in enumerate(((z0 + 0.12, 0.2), (z0 + 0.28, 0.15))):
                fr.box(cam, (x0 + 0.13, x0 + 0.21), (top, top + 0.05), (tz - 0.04, tz + 0.04), "#3a2a20", line=1.0)
                cyl(fr, cam, (x0 + 0.17, top + 0.05, tz), 0.012, th * 0.45, "#d8a83a", line=1.0)
                cyl(fr, cam, (x0 + 0.17, top + 0.05 + th * 0.45, tz), 0.04, th * 0.4, "#e8b84a", line=1.0)
            lx, lz = x0 + 0.2, z1 - 0.25
            for k, (dx, dz, w, h, cc) in enumerate(((0, 0, 0.12, 0.04, "#8a8a94"), (0.0, -0.06, 0.06, 0.035, "#d83a3a"), (0.0, 0.07, 0.05, 0.03, "#3a5ad8"),
                                                    (0.0, 0.0, 0.05, 0.05, "#e8e8ee"))):
                fr.box(cam, (lx - w / 2 + dx, lx + w / 2 + dx), (top + (0.04 if k == 3 else 0.0), top + h + (0.04 if k == 3 else 0.0)),
                       (lz + dz - w / 2, lz + dz + w / 2), cc, line=1.0)
            p = cam.proj((x0 + 0.1, top + 0.01, z1 - 0.08))                    # medal on its ribbon, laid down
            if p[2] > 0.15:
                fr.c.drawLine(p[0], p[1], p[0] - 0.05 * p[3], p[1] - 0.004 * p[3], paint("#3a5ad8", stroke=0.012 * p[3]))
                fr.c.drawCircle(p[0], p[1], 0.022 * p[3], paint("#e8b84a"))
        return self.it(cam, fn, (x0 - 0.05, 0.5, (z0 + z1) / 2))

    def solid(self):
        return ((self.x0, ROOM_X), (0.0, 0.88), (self.z0, self.z1))


class WallShelves(Piece):
    """Two floating shelves on the right wall over the drawers: comics and books, anime figures, a brick model,
    a small plant, a game case."""
    size = (0.25, 0.5, 0.85)

    def __init__(self, name, z0=1.32, z1=2.17, ys=(1.3, 1.66)):
        super().__init__(name, ROOM_X - 0.12, (z0 + z1) / 2, ys[0])
        self.z0, self.z1, self.ys = z0, z1, ys

    def item(self, cam, T):
        z0, z1 = self.z0, self.z1
        x0, x1 = ROOM_X - 0.24, ROOM_X

        def fn(fr):
            for i, y in enumerate(self.ys):
                fr.box(cam, (x0, x1), (y - 0.03, y), (z0, z1), "#5a4436", line=1.2)
                zz = z0 + 0.03
                r = np.random.default_rng(10 + i)
                if i == 0:                                       # books, leaning at the end
                    for k in range(9):
                        w = r.uniform(0.025, 0.045)
                        hh = r.uniform(0.17, 0.24)
                        cc = ["#c83a3a", "#3a5ad8", "#e8c84a", "#3a9a5a", "#2a2a30", "#e87a3a", "#8a3ad8"][k % 7]
                        fr.box(cam, (x0 + 0.04, x1 - 0.02), (y, y + hh), (zz, zz + w), cc, line=0.9)
                        zz += w + 0.004
                    # figure: a little hero (round head, cape)
                    fx, fz = x0 + 0.12, z1 - 0.18
                    fr.box(cam, (fx - 0.04, fx + 0.04), (y, y + 0.015), (fz - 0.04, fz + 0.04), "#1a1a20", line=0.8)
                    blob(fr, cam, (fx, y + 0.07, fz), 0.03, 0.05, "#3a6ad8", line=1.0)
                    blob(fr, cam, (fx, y + 0.14, fz), 0.03, 0.03, "#f0c8a0", line=1.0)
                    blob(fr, cam, (fx, y + 0.165, fz), 0.032, 0.018, "#e8d84a", line=1.0)
                    fx2 = x0 + 0.12
                    fz2 = z1 - 0.07
                    blob(fr, cam, (fx2, y + 0.06, fz2), 0.028, 0.045, "#d83a5a", line=1.0)
                    blob(fr, cam, (fx2, y + 0.12, fz2), 0.027, 0.027, "#f0c8a0", line=1.0)
                    blob(fr, cam, (fx2, y + 0.14, fz2), 0.03, 0.02, "#2a2a30", line=1.0)
                else:                                            # brick model, a plant, a game case, a puzzle cube
                    lz = z0 + 0.2
                    for k, (w, h, cc, dy) in enumerate(((0.16, 0.05, "#8a8a94", 0.0), (0.08, 0.05, "#e8e8ee", 0.05), (0.05, 0.03, "#3ad0ff", 0.1))):
                        fr.box(cam, (x0 + 0.06, x0 + 0.06 + w * 0.6), (y + dy, y + dy + h), (lz - w / 2, lz + w / 2), cc, line=1.0)
                    for k in range(4):
                        p = cam.proj((x0 + 0.05, y + 0.052, lz - 0.06 + 0.04 * k))
                        if p[2] > 0.15:
                            fr.c.drawCircle(p[0], p[1], 0.006 * p[3], paint("#a8a8b4"))
                    cyl(fr, cam, (x0 + 0.12, y, z1 - 0.3), 0.04, 0.07, "#d8784a")
                    for k in range(5):
                        a = k * 1.25
                        wline(fr, cam, (x0 + 0.12, y + 0.07, z1 - 0.3), (x0 + 0.12 + 0.05 * math.cos(a), y + 0.15 + 0.02 * k % 0.05, z1 - 0.3 + 0.06 * math.sin(a)),
                              "#3a9a4a", 0.014)
                    fr.box(cam, (x0 + 0.05, x1 - 0.04), (y, y + 0.17), (z1 - 0.16, z1 - 0.145), "#1a4ab8", line=0.9)
                    fr.box(cam, (x0 + 0.08, x0 + 0.13), (y, y + 0.05), (z1 - 0.08, z1 - 0.03), "#e8382a", line=0.9)
                    fr.poly(cam, quad_x(z1 - 0.08, z1 - 0.055, y + 0.025, y + 0.05, x0 + 0.079, -1), colr="#ffe14a")
                    fr.poly(cam, quad_x(z1 - 0.055, z1 - 0.03, y, y + 0.025, x0 + 0.079, -1), colr="#3ad87a")
        return self.it(cam, fn, (x0 - 0.05, self.ys[0], (z0 + z1) / 2))


class Beanbag(Piece):
    """Big slouched beanbag on the floor, a spare controller with a worn left stick lying on it."""
    size = (0.75, 0.55, 0.75)

    def __init__(self, name, x, z, colr="#5a3ab8"):
        super().__init__(name, x, z)
        self.colr = colr

    def item(self, cam, T):
        x, z = self.x, self.z

        def fn(fr):
            fr.ground_ellipse(cam, x, z, 0.42, 0.38, "#000000", 0.35, blur_m=0.08, y=0.005)
            blob(fr, cam, (x, 0.2, z), 0.4, 0.22, self.colr, line=1.5)
            blob(fr, cam, (x + 0.05, 0.42, z + 0.12), 0.27, 0.14, shade(self.colr, 0.08), line=1.2)
            p = cam.proj((x - 0.02, 0.33, z - 0.08))
            if p[2] > 0.15:
                path = skia.Path()
                path.moveTo(p[0] - 0.25 * p[3], p[1] + 0.02 * p[3])
                path.quadTo(p[0], p[1] - 0.06 * p[3], p[0] + 0.22 * p[3], p[1] + 0.03 * p[3])
                fr.c.drawPath(path, paint(shade(self.colr, -0.45), a=0.7, stroke=max(1.0, 0.008 * p[3])))
            controller(fr, cam, (x - 0.06, 0.36, z - 0.1), 0.15, "#2a2a32", T, flat=True, worn=True)
        return self.it(cam, fn, (x, 0.3, z))

    def solid(self):
        return ((self.x - 0.38, self.x + 0.38), (0.0, 0.45), (self.z - 0.35, self.z + 0.35))


class LaundryBasket(Piece):
    """Woven laundry basket, clothes heaped over the rim and one shirt slid onto the floor."""
    size = (0.48, 0.58, 0.36)

    def __init__(self, name, x, z):
        super().__init__(name, x, z)

    def item(self, cam, T):
        x, z = self.x, self.z

        def fn(fr):
            fr.box(cam, (x - 0.24, x + 0.24), (0.0, 0.45), (z - 0.18, z + 0.18), "#b8a078", line=1.3)
            for k in range(7):
                wline(fr, cam, (x - 0.24, 0.05 + 0.06 * k, z - 0.181), (x + 0.24, 0.05 + 0.06 * k, z - 0.181), "#7a6a4a", 0.006, 0.8)
            for k, (dx, dy, rx, cc) in enumerate(((-0.1, 0.5, 0.14, "#3a5ad8"), (0.08, 0.53, 0.15, "#c83a3a"), (0.0, 0.58, 0.11, "#e8e4dc"),
                                                   (-0.15, 0.47, 0.09, "#2a2a30"), (0.17, 0.48, 0.08, "#e8c84a"))):
                blob(fr, cam, (x + dx, dy, z - 0.02), rx, 0.06, cc, line=1.1)
            q = [(x - 0.2, 0.44, z - 0.18), (x - 0.05, 0.4, z - 0.19), (x - 0.12, 0.0, z - 0.32), (x - 0.34, 0.0, z - 0.3)]
            fr.poly(cam, q, colr="#3a8a5a", outline="#1a3a2a", line=1.2)
        return self.it(cam, fn, (x, 0.3, z))

    def solid(self):
        return ((self.x - 0.24, self.x + 0.24), (0.0, 0.45), (self.z - 0.18, self.z + 0.18))


class Bin(Piece):
    """Small rubbish bin by the desk, crumpled paper and a can poking out."""
    size = (0.26, 0.32, 0.26)

    def __init__(self, name, x, z):
        super().__init__(name, x, z)

    def item(self, cam, T):
        x, z = self.x, self.z

        def fn(fr):
            cyl(fr, cam, (x, 0.0, z), 0.13, 0.3, "#3a3c48")
            for k, (dx, dz, cc) in enumerate(((-0.04, 0.0, "#f0ece4"), (0.05, 0.02, "#e8e4dc"))):
                blob(fr, cam, (x + dx, 0.32, z + dz), 0.05, 0.04, cc, line=1.0)
            cyl(fr, cam, (x + 0.02, 0.26, z - 0.03), 0.028, 0.1, "#d8283a", line=1.0)
            q = [(x - 0.32, 0.003, z - 0.12), (x - 0.22, 0.008, z - 0.14), (x - 0.2, 0.003, z - 0.05), (x - 0.31, 0.01, z - 0.04)]
            fr.poly(cam, q, colr="#f0c02a", outline="#6a5010", line=1.0)         # a wrapper that missed
        return self.it(cam, fn, (x, 0.2, z))

    def solid(self):
        return ((self.x - 0.13, self.x + 0.13), (0.0, 0.3), (self.z - 0.13, self.z + 0.13))


class Backpack(Piece):
    """School backpack dropped beside the desk, slumped against the desk leg, a strap trailing."""
    size = (0.32, 0.42, 0.2)

    def __init__(self, name, x, z, colr="#2a4a8a"):
        super().__init__(name, x, z)
        self.colr = colr

    def item(self, cam, T):
        x, z = self.x, self.z

        def fn(fr):
            fr.ground_ellipse(cam, x, z, 0.2, 0.13, "#000000", 0.35, blur_m=0.05, y=0.004)
            p = cam.proj((x, 0.0, z))
            if p[2] < 0.15:
                return
            s = p[3]
            body = skia.Path()
            body.addRRect(skia.RRect.MakeRectXY(skia.Rect(p[0] - 0.16 * s, p[1] - 0.4 * s, p[0] + 0.15 * s, p[1]), 0.07 * s, 0.07 * s))
            fr.part(body, self.colr, line=1.5)
            pocket = skia.Path()
            pocket.addRRect(skia.RRect.MakeRectXY(skia.Rect(p[0] - 0.11 * s, p[1] - 0.2 * s, p[0] + 0.1 * s, p[1] - 0.03 * s), 0.04 * s, 0.04 * s))
            fr.part(pocket, shade(self.colr, -0.12), line=1.2)
            fr.c.drawLine(p[0] - 0.1 * s, p[1] - 0.2 * s, p[0] + 0.09 * s, p[1] - 0.2 * s, paint("#c8c8d0", stroke=max(1.0, 0.006 * s)))
            fr.c.drawCircle(p[0] + 0.07 * s, p[1] - 0.19 * s, 0.01 * s, paint("#e8e8f0"))
            fr.c.drawCircle(p[0] - 0.06 * s, p[1] - 0.31 * s, 0.03 * s, paint("#ffe14a"))           # a keyring badge
            wpath(fr, cam, [(x + 0.12, 0.3, z - 0.05), (x + 0.22, 0.12, z - 0.1), (x + 0.3, 0.005, z - 0.2)], shade(self.colr, -0.35), 0.03)
        return self.it(cam, fn, (x, 0.2, z))

    def solid(self):
        return ((self.x - 0.16, self.x + 0.16), (0.0, 0.42), (self.z - 0.1, self.z + 0.1))


class FloorClutter(Piece):
    """Socks, trainers kicked off, a hoodie and jeans on the floor, a notebook, and an open delivery box from a new RGB
    accessory with packing paper spilling out."""
    size = (3.0, 0.3, 2.0)

    def __init__(self, name="floor_clutter", trainers=(0.55, 1.2), box=(1.15, 2.95), clothes=(-0.75, 1.15), socks=((0.3, 0.95), (-0.25, 2.0))):
        super().__init__(name, 0.0, 1.8)
        self.trainers, self.box_at, self.clothes, self.socks = trainers, box, clothes, socks

    def item(self, cam, T):
        out = []
        tx, tz = self.trainers or (0.0, 0.0)

        def trainers(fr):
            for k, (dx, dz, yaw) in enumerate(((0.0, 0.0, 20.0), (0.16, 0.1, -50.0))):
                a = math.radians(yaw)
                c = (tx + dx, tz + dz)
                f = (math.sin(a) * 0.14, math.cos(a) * 0.14)
                r = (math.cos(a) * 0.05, -math.sin(a) * 0.05)
                sole = [(c[0] - f[0] - r[0], 0.0, c[1] - f[1] - r[1]), (c[0] + f[0] - r[0], 0.0, c[1] + f[1] - r[1]),
                        (c[0] + f[0] + r[0], 0.0, c[1] + f[1] + r[1]), (c[0] - f[0] + r[0], 0.0, c[1] - f[1] + r[1])]
                fr.poly(cam, [(p[0], 0.025, p[2]) for p in sole], colr="#f4f4f4", outline="#5a5a64", line=1.0)
                up = [(p[0] * 0.85 + c[0] * 0.15, 0.08 if i in (0, 3) else 0.05, p[2] * 0.85 + c[1] * 0.15) for i, p in enumerate(sole)]
                fr.poly(cam, [(p[0], 0.03, p[2]) for p in sole[:2]] + up[1::-1], colr="#e8383a", outline="#5a1010", line=1.0)
                fr.poly(cam, up, colr="#d82a2a", outline="#5a1010", line=1.0)
        if self.trainers:
            out.append(self.it(cam, trainers, (tx, 0.05, tz), "_trainers"))
        cx, cz = self.clothes

        def clothes(fr):
            q = [(cx - 0.3, 0.004, cz - 0.1), (cx + 0.1, 0.01, cz - 0.22), (cx + 0.32, 0.006, cz + 0.05), (cx + 0.05, 0.012, cz + 0.22), (cx - 0.25, 0.005, cz + 0.15)]
            fr.poly(cam, q, colr="#4a5068", outline="#1e2232", line=1.2)                # hoodie
            blob(fr, cam, (cx - 0.02, 0.04, cz), 0.12, 0.03, "#565c78", line=1.0)
            q2 = [(cx + 0.25, 0.006, cz - 0.3), (cx + 0.55, 0.006, cz - 0.42), (cx + 0.6, 0.006, cz - 0.3), (cx + 0.32, 0.008, cz - 0.15)]
            fr.poly(cam, q2, colr="#2a3a6a", outline="#101830", line=1.2)               # jeans
            for k, sk in enumerate(self.socks):
                sock(fr, cam, sk[0], sk[1], sk[2] if len(sk) > 2 else 30.0 * k, striped=(k % 2 == 1))
            # notebook open on the floor
            nb = quad_y(cx + 0.35, cx + 0.6, cz + 0.25, cz + 0.42, 0.006)
            decal(fr, cam, nb, 300, 200, lambda c, w, h: (c.drawRect(skia.Rect(0, 0, w, h), paint("#f4f0e4")),
                                                           [c.drawLine(10, 20 + i * 16, w - 10, 20 + i * 16, paint("#9ab0d8", stroke=1.2)) for i in range(11)],
                                                           c.drawLine(w / 2, 0, w / 2, h, paint("#8a8070", stroke=3))))
        out.append(self.it(cam, clothes, (cx, 0.05, cz + 0.3), "_clothes"))
        bx, bz = self.box_at

        def dbox(fr):
            fr.box(cam, (bx - 0.2, bx + 0.2), (0.0, 0.22), (bz - 0.15, bz + 0.15), "#c8985a", line=1.3)
            fr.poly(cam, [(bx - 0.2, 0.22, bz - 0.15), (bx + 0.2, 0.22, bz - 0.15), (bx + 0.22, 0.3, bz - 0.32), (bx - 0.22, 0.3, bz - 0.32)],
                    colr="#b8884a", outline="#5a3a18", line=1.1)                        # front flap open
            fr.poly(cam, [(bx - 0.2, 0.22, bz + 0.15), (bx + 0.2, 0.22, bz + 0.15), (bx + 0.2, 0.42, bz + 0.2), (bx - 0.2, 0.42, bz + 0.2)],
                    colr="#d8a86a", outline="#5a3a18", line=1.1)                        # back flap up
            wline(fr, cam, (bx - 0.2, 0.221, bz), (bx + 0.2, 0.221, bz), "#c8b070", 0.03, 0.9)   # tape
            for k in range(3):
                blob(fr, cam, (bx - 0.1 + 0.1 * k, 0.24, bz - 0.02), 0.07, 0.03, "#e8e0d0", line=1.0)
            fr.box(cam, (bx - 0.12, bx + 0.08), (0.18, 0.3), (bz - 0.05, bz + 0.05), "#14141c", line=1.0)     # the product box
            fr.poly(cam, quad_z(bx - 0.11, bx + 0.07, 0.19, 0.29, bz - 0.051), shader=lambda p: lin(
                (p.getBounds().left(), 0), (p.getBounds().right(), 0), [argb("#ff3a8a"), argb("#3ad0ff"), argb("#7aff6a")]))
        out.append(self.it(cam, dbox, (bx, 0.2, bz), "_box"))
        return out


# ======================================================================================================
# screens
# ======================================================================================================
def game_screen(c, w, h, T):
    """The main monitor: a bright cartoon platformer paused mid-run (sky, hills, coins, HUD)."""
    c.drawRect(skia.Rect(0, 0, w, h), paint(shader=lin((0, 0), (0, h), [argb("#3a8aff"), argb("#9ad0ff")])))
    for k, (cx, r, cc) in enumerate(((0.2, 0.35, "#3ab85a"), (0.65, 0.45, "#2a9a4a"), (1.0, 0.3, "#3ab85a"))):
        c.drawCircle(w * cx, h * 0.95, w * r, paint(cc))
    c.drawRect(skia.Rect(0, h * 0.82, w, h), paint("#8a5a3a"))
    c.drawRect(skia.Rect(0, h * 0.8, w, h * 0.84), paint("#5ad86a"))
    for k in range(5):
        x = (w * (0.3 + 0.12 * k) - T * 60) % w
        c.drawCircle(x, h * 0.55 - 10 * math.sin(k), 9, paint("#ffd83a"))
        c.drawCircle(x, h * 0.55 - 10 * math.sin(k), 9, paint("#a8781a", stroke=2))
    c.drawRect(skia.Rect(w * 0.42, h * 0.62, w * 0.47, h * 0.8), paint("#e8383a"))
    c.drawCircle(w * 0.445, h * 0.58, 12, paint("#f4c8a0"))
    for k in range(3):
        c.drawCircle(30 + k * 26, 26, 10, paint("#ff3a5a"))
    text(c, f"x {37 + int(T * 2) % 3}", w - 110, 34, 24, "#ffffff", stroke=4)
    rrect(c, w * 0.3, h * 0.25, w * 0.7, h * 0.4, 12, "#101020", a=0.7)
    text(c, "PAUSED", w / 2, h * 0.355, 34, "#ffffff", center=True)


def follower_screen(milestone=10000, platform="instagram", t_hit=1.3, start=None):
    """The portrait monitor: the profile page counting up to the milestone at t_hit, then a burst of confetti and hearts.
    platform = instagram (pink-orange gradient) | tiktok (black with cyan / red)."""
    start = start if start is not None else milestone - 6

    def draw(c, w, h, T):
        u = max(0.0, min(1.0, (T - 0.2) / max(0.01, t_hit - 0.2)))
        n = int(start + (milestone - start) * u) if T < t_hit else milestone
        hit = T >= t_hit
        if platform == "tiktok":
            c.drawRect(skia.Rect(0, 0, w, h), paint("#0c0c10"))
            ring = [argb("#25f4ee"), argb("#fe2c55")]
            accent = "#fe2c55"
        else:
            c.drawRect(skia.Rect(0, 0, w, h), paint("#fafafa"))
            ring = [argb("#feda75"), argb("#d62976"), argb("#4f5bd5")]
            accent = "#d62976"
        fg = "#ffffff" if platform == "tiktok" else "#111111"
        c.drawRect(skia.Rect(0, 0, w, 56), paint("#16161c" if platform == "tiktok" else "#ffffff"))
        text(c, "my channel", w / 2, 38, 22, fg, center=True)
        c.drawCircle(w / 2, 150, 70, paint(shader=lin((w / 2 - 70, 80), (w / 2 + 70, 220), ring)))
        c.drawCircle(w / 2, 150, 62, paint("#0c081d"))
        text(c, "TOON", w / 2, 160, 26, "#B653FB", center=True)
        s = 1.0 + (0.25 * math.exp(-(T - t_hit) * 5.0) * math.sin((T - t_hit) * 20.0) if hit else 0.0)
        c.save()
        c.translate(w / 2, 320)
        c.scale(s, s)
        label = f"{milestone // 1000}K" if hit else f"{n:,}"
        text(c, label, 0, 0, 76 if hit else 58, accent if hit else fg, center=True)
        c.restore()
        text(c, "followers", w / 2, 364, 26, "#8a8a94", center=True)
        rrect(c, 40, 400, w - 40, 446, 10, accent)
        text(c, "Following", w / 2, 431, 22, "#ffffff", center=True)
        for k in range(6):                                  # the grid of posts
            gx, gy = 22 + (k % 3) * ((w - 44) / 3), 470 + (k // 3) * 56
            c.drawRect(skia.Rect(gx + 2, gy, gx + (w - 44) / 3 - 2, gy + 52), paint(["#3a2a5a", "#5a2a3a", "#2a3a5a"][k % 3]))
        if hit:                                             # confetti and hearts
            r = np.random.default_rng(int(milestone) % 97)
            dt = T - t_hit
            for i in range(60):
                x0, vx, vy = r.uniform(0, w), r.uniform(-80, 80), r.uniform(-420, -160)
                x, y = x0 + vx * dt, 320 + vy * dt + 300 * dt * dt
                if 0 < y < h:
                    c.save()
                    c.translate(x, y)
                    c.rotate(dt * 400 + i * 37)
                    c.drawRect(skia.Rect(-5, -3, 5, 3), paint(["#ffe14a", "#3ad0ff", "#ff4a8a", "#7aff6a", "#B653FB"][i % 5]))
                    c.restore()
            for i in range(6):
                y = h - 40 - dt * 220 - i * 30
                if y > 60:
                    x = w * (0.75 + 0.08 * math.sin(dt * 4 + i))
                    p = skia.Path()
                    p.moveTo(x, y + 12)
                    p.cubicTo(x - 22, y - 2, x - 10, y - 18, x, y - 6)
                    p.cubicTo(x + 10, y - 18, x + 22, y - 2, x, y + 12)
                    c.drawPath(p, paint("#ff3a5a", a=max(0.0, 1 - dt / 2.5)))
    return draw


# ======================================================================================================
# the room
# ======================================================================================================
class GamerRoom:
    """bg + depth-sorted items + the night grade for a LAYOUT of pieces. Characters are added by the scene."""
    NIGHT = 0.28

    def __init__(self, layout):
        self.pieces = layout
        self.by_name = {p.name: p for p in layout}

    def lights(self):
        return [L for p in self.pieces for L in p.lights()]

    def solids(self):
        return {p.name: p.solid() for p in self.pieces if p.solid()}

    def bg(self, fr, cam, T):
        for p in self.pieces:
            if p.kind == "floor":
                p.bg(fr, cam, T)
        for p in self.pieces:
            if p.kind == "wall":
                p.bg(fr, cam, T)

    def items(self, cam, T):
        out = []
        for p in self.pieces:
            if p.kind != "prop":
                continue
            it = p.item(cam, T)
            if it:
                out += it if isinstance(it, list) else [it]
        return out

    def night(self, fr, cam, T, extra=()):
        """Darken toward night with soft holes round every light and round the cast (extra = [(point, r, k)])."""
        holes = [(L.pos, L.r, L.k) for L in self.lights()] + list(extra)
        c = fr.c
        c.saveLayer()
        c.drawRect(skia.Rect(0, 0, W, H), paint("#05040c", a=self.NIGHT))
        for P, rm, s in holes:
            x, y, z = cam.view(P)
            if z < 0.25:
                continue
            sc = cam.f / z
            sx, sy, R = W / 2 + x * sc, H * cam.horizon - y * sc, min(rm * sc, 3.0 * H)
            if not (-R < sx < W + R and -R < sy < H + R):
                continue
            pt = paint(shader=skia.GradientShader.MakeRadial(skia.Point(sx, sy), max(R, 1.0),
                       [argb("#000000", s), argb("#000000", s * 0.5), argb("#000000", 0)], [0.0, 0.45, 1.0]))
            pt.setBlendMode(skia.BlendMode.kDstOut)
            c.drawRect(skia.Rect(0, 0, W, H), pt)
        c.restore()

    def draw_all(self, fr, cam, T, extra_items=()):
        """Room only (asset sheets): bg, the sorted items, the grade."""
        self.bg(fr, cam, T)
        for _, fn, _ in sorted(self.items(cam, T) + list(extra_items), key=lambda q: -q[0]):
            fn(fr)
        self.night(fr, cam, T)

    def manifest(self):
        rows = [dict(name=p.name, piece=type(p).__name__, kind=p.kind, pivot=[round(v, 3) for v in p.pivot],
                     size_m=[round(v, 3) for v in p.size], solid=p.solid(), doc=(type(p).__doc__ or "").split("\n")[0])
                for p in self.pieces]
        return dict(units="metres, y up; back (desk) wall z = %.2f, left wall x = %.2f, right wall x = %.2f" % (ROOM_Z, -ROOM_X, ROOM_X),
                    room=dict(x=[-ROOM_X, ROOM_X], z=[0, ROOM_Z], h=ROOM_H), desk=dict(z=[DESK_Z0, DESK_Z1], top=DESK_Y),
                    pieces=rows, lights=[dict(name=L.name, pos=L.pos) for L in self.lights()])


def make_layout(milestone=10000, platform="instagram", t_hit=1.3):
    main = Monitor("monitor_main", -0.08, 3.38, "h", game_screen)
    side = Monitor("monitor_vertical", 0.5, 3.36, "v", follower_screen(milestone, platform, t_hit), glow="#ff8ad8" if platform == "instagram" else "#5af0ff")
    P = [Shell(),
         Window("window", -1.85, -1.2, gap_x=-1.48, gap=0.16),
         Poster("poster_level_up", "back", -1.05, -0.62, 1.42, 2.04, "level_up"),
         Poster("poster_anime", "right", 0.35, 0.9, 1.25, 2.0, "anime_eyes"),
         Poster("poster_band", "left", 0.15, 0.6, 1.35, 1.95, "band", tilt=0.012),
         Poster("poster_lofi", "back", 0.98, 1.36, 1.82, 2.3, "lofi"),
         Corkboard("corkboard", 0.98, 1.36, 1.12, 1.68),
         NeonSign("neon_gg", 0.47, 1.98, 0.42),
         HexPanels("hex_panels", -0.42, 1.7, 0.1),
         Jersey("jersey", "left", 1.55, 1.25),
         Skateboard("skateboard", "right", 1.05, 0.95),
         Desk(), main, side, Webcam("webcam", main), PC("pc", -0.64, 3.3), Keyboard("keyboard", -0.06, 3.1),
         Headset("headset", 0.9, 3.0), MicArm("mic_arm"), KeyLight("key_light"), ControllerDock("controller_dock", 0.73, 3.28),
         DeskClutter(),
         GamingChair("chair", 0.0, 2.3),
         Bed("bed"), BedsideTable("bedside"),
         Wardrobe("wardrobe"), Drawers("drawers"), WallShelves("shelves"),
         Beanbag("beanbag", 1.3, 0.95), LaundryBasket("laundry", 1.2, 2.55), Bin("bin", 1.08, 3.3), Backpack("backpack", -1.05, 2.95),
         FloorClutter()]
    return P


def default_room(**kw):
    return GamerRoom(make_layout(**kw))


# ======================================================================================================
# asset sheet + manifest + per-asset PNGs
# ======================================================================================================
def aimc(pos, tgt, f, hz=0.46):
    from toon import Camera
    return Camera(pos, math.degrees(math.atan2(tgt[0] - pos[0], tgt[2] - pos[2])), f, hz)


ASSET_VIEWS = {           # name -> (camera pos, target, f) close-ups for the kit
    "pc": ((-0.4, 1.15, 2.2), (-0.64, 0.98, 3.3), 1900), "monitor_main": ((0.0, 1.15, 2.1), (-0.08, 1.08, 3.38), 1500),
    "monitor_vertical": ((0.45, 1.2, 2.2), (0.5, 1.18, 3.36), 1700), "keyboard": ((0.05, 1.15, 2.45), (0.05, 0.76, 3.1), 1700),
    "desk": ((0.0, 1.3, 1.0), (0.0, 0.8, 3.2), 900), "chair": ((0.6, 1.1, 0.9), (0.0, 0.75, 2.3), 1100),
    "bed": ((-0.4, 1.4, 0.2), (-1.5, 0.5, 1.7), 900), "bedside": ((-1.2, 1.0, 2.2), (-1.76, 0.6, 3.05), 1500),
    "wardrobe": ((0.1, 1.2, 1.6), (1.6, 1.1, 2.95), 900), "drawers": ((0.6, 1.1, 1.0), (1.75, 0.8, 1.75), 1100),
    "shelves": ((0.8, 1.55, 1.2), (1.85, 1.45, 1.75), 1300), "beanbag": ((0.6, 0.9, 0.0), (1.3, 0.3, 0.95), 1300),
    "laundry": ((0.6, 0.9, 1.7), (1.2, 0.35, 2.55), 1400), "bin": ((0.7, 0.7, 2.5), (1.08, 0.2, 3.3), 1700),
    "backpack": ((-0.6, 0.6, 2.2), (-1.05, 0.22, 2.95), 1700), "floor_clutter": ((0.2, 1.4, 0.0), (0.3, 0.0, 1.8), 800),
    "window": ((-1.2, 1.5, 2.2), (-1.5, 1.5, 3.6), 1200), "neon_gg": ((0.4, 1.9, 2.4), (0.47, 2.07, 3.6), 1600),
    "hex_panels": ((-0.3, 1.8, 2.4), (-0.25, 1.8, 3.6), 1500), "corkboard": ((1.0, 1.4, 2.6), (1.17, 1.4, 3.6), 1500),
    "jersey": ((-0.8, 1.5, 1.4), (-2.0, 1.5, 1.55), 1300), "skateboard": ((0.9, 1.35, 1.0), (2.0, 1.35, 1.05), 1400),
    "poster_anime": ((0.9, 1.6, 0.6), (2.0, 1.6, 0.62), 1300), "poster_band": ((-0.9, 1.65, 0.4), (-2.0, 1.65, 0.38), 1300),
    "mic_arm": ((-0.2, 1.1, 2.4), (-0.45, 1.0, 3.2), 1600), "key_light": ((-0.4, 1.3, 2.0), (-0.81, 1.4, 2.95), 1500),
    "controller_dock": ((0.6, 0.95, 2.7), (0.73, 0.82, 3.28), 2400), "headset": ((0.6, 0.85, 2.4), (0.92, 0.6, 3.0), 2000),
    "desk_clutter": ((0.1, 1.45, 2.7), (0.0, 0.74, 3.2), 1000),
}

def sock(fr, cam, x, z, yaw, striped=False, colr="#ece9e2"):
    """A sock dropped on the floor, drawn as a bent tube: the foot lying flat with a grey toe cap, the heel bump, the
    leg folded over at the ankle, a ribbed cuff."""
    a = math.radians(yaw)
    f = (math.sin(a), math.cos(a))                            # along the foot
    r = (math.cos(a), -math.sin(a))                           # across it

    def P(u, v, y):
        return (x + f[0] * u + r[0] * v, y, z + f[1] * u + r[1] * v)
    W = 0.045
    toe = "#8e9099" if not striped else "#4a6a9a"
    # the foot: a rounded slab, toe forward (+u)
    foot = [P(-0.1, -W, 0.004), P(0.06, -W * 1.05, 0.004), P(0.11, -W * 0.6, 0.006), P(0.12, 0.0, 0.007), P(0.11, W * 0.6, 0.006),
            P(0.06, W * 1.05, 0.004), P(-0.1, W, 0.004), P(-0.13, W * 0.7, 0.012), P(-0.14, 0.0, 0.016), P(-0.13, -W * 0.7, 0.012)]
    fr.poly(cam, foot, colr=colr, outline=shade(colr, -0.55), line=1.1)
    fr.poly(cam, [P(0.07, -W * 1.0, 0.0045), P(0.11, -W * 0.6, 0.0065), P(0.12, 0.0, 0.0075), P(0.11, W * 0.6, 0.0065), P(0.07, W * 1.0, 0.0045), P(0.075, 0.0, 0.009)],
            colr=toe, outline=shade(toe, -0.5), line=1.0)                                   # toe cap
    blob(fr, cam, P(-0.12, 0.0, 0.0), 0.035, 0.03, shade(colr, -0.08), line=1.0)           # the heel bump
    # the leg, folded back over the ankle and lying beside the foot
    leg = [P(-0.12, -W * 0.9, 0.03), P(-0.26, -W * 1.6, 0.02), P(-0.34, -W * 1.4, 0.012), P(-0.36, -W * 0.5, 0.01),
           P(-0.3, W * 0.2, 0.012), P(-0.16, W * 0.1, 0.02), P(-0.12, W * 0.9, 0.03)]
    fr.poly(cam, leg, colr=shade(colr, -0.04), outline=shade(colr, -0.55), line=1.1)
    if striped:
        for u in (-0.2, -0.27):
            fr.poly(cam, [P(u, -W * 1.5, 0.014), P(u + 0.03, -W * 1.5, 0.014), P(u + 0.03, W * 0.15, 0.014), P(u, W * 0.15, 0.014)],
                    colr="#4a6a9a", outline=shade("#4a6a9a", -0.4), line=0.8)
    # the ribbed cuff at the open end
    cuff = [P(-0.36, -W * 1.4, 0.013), P(-0.3, W * 0.2, 0.013), P(-0.33, W * 0.25, 0.016), P(-0.39, -W * 1.35, 0.016)]
    fr.poly(cam, cuff, colr=shade(colr, -0.15), outline=shade(colr, -0.55), line=1.0)
    for k in range(5):
        t = k / 4
        a_, b_ = P(-0.36 + 0.06 * t, -W * 1.4 + (W * 1.6) * t, 0.017), P(-0.39 + 0.06 * t, -W * 1.35 + (W * 1.6) * t, 0.017)
        qa, qb = cam.proj(a_), cam.proj(b_)
        if min(qa[2], qb[2]) > 0.15:
            fr.c.drawLine(qa[0], qa[1], qb[0], qb[1], paint(shade(colr, -0.4), stroke=max(0.8, 0.004 * qa[3]), a=0.8))
    q = cam.proj(P(-0.02, 0.0, 0.01))                         # a soft crease across the instep
    q2 = cam.proj(P(-0.02, W * 0.8, 0.008))
    if min(q[2], q2[2]) > 0.15:
        fr.c.drawLine(q[0], q[1], q2[0], q2[1], paint(shade(colr, -0.35), stroke=max(0.8, 0.003 * q[3]), a=0.7))

if __name__ == "__main__":
    import os
    import sys

    from PIL import Image, ImageDraw

    from toon import Frame

    args = sys.argv[1:]
    room = default_room()
    if "--manifest" in args:
        out = args[args.index("--manifest") + 1]
        json.dump(room.manifest(), open(out, "w"), indent=1)
        print("wrote", out, len(room.pieces), "pieces")

    def shot(cam, T=1.6, scale=0.4, lab=None):
        fr = Frame(scale)
        room.draw_all(fr, cam, T)
        im = Image.fromarray(fr.array())
        if lab:
            d = ImageDraw.Draw(im)
            d.rectangle((0, im.height - 24, im.width, im.height), fill=(0, 0, 0))
            d.text((6, im.height - 19), lab, fill=(255, 255, 0))
        return im
    if "--sheet" in args:
        out = args[args.index("--sheet") + 1]
        views = [("wide from the door", aimc((0.35, 1.45, -0.6), (0.0, 1.0, 3.6), 620)),
                 ("desk wall", aimc((0.0, 1.2, 0.9), (0.0, 1.1, 3.6), 820)),
                 ("bed side", aimc((0.9, 1.4, 0.0), (-1.6, 0.8, 2.2), 700)),
                 ("wardrobe side", aimc((-0.9, 1.4, 0.0), (1.6, 1.0, 2.2), 700))]
        views += [(n, aimc(*ASSET_VIEWS[n])) for n in ("pc", "monitor_vertical", "chair", "bed", "drawers", "shelves", "floor_clutter", "desk_clutter")]
        tiles = [shot(cam, lab=lab) for lab, cam in views]
        w, h = tiles[0].size
        cols = 6
        rows = (len(tiles) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * w + (cols - 1) * 12, rows * h + (rows - 1) * 12), (40, 40, 40))
        for i, t in enumerate(tiles):
            sheet.paste(t, ((i % cols) * (w + 12), (i // cols) * (h + 12)))
        sheet.save(out)
        print("wrote", out)
    if "--assets" in args:
        out = args[args.index("--assets") + 1]
        os.makedirs(out, exist_ok=True)
        for n, v in ASSET_VIEWS.items():
            shot(aimc(*v), scale=0.6).save(os.path.join(out, f"{n}.png"))
        shot(aimc((0.35, 1.45, -0.6), (0.0, 1.0, 3.6), 620), scale=1.0).save(os.path.join(out, "_room_wide.png"))
        json.dump(room.manifest(), open(os.path.join(out, "manifest.json"), "w"), indent=1)
        print("wrote", len(ASSET_VIEWS) + 1, "asset renders to", out)
