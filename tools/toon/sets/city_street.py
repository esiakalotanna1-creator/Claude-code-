"""CITY STREET: a reusable, modular night street for toon reels (built 2026-11-06 for The Smiling Man).

World units are metres, y up. The road runs along +z; x = 0 is the road centre line.

    road        x in [-ROAD, ROAD]            asphalt, y = 0 (wet), double yellow centre line, zebra crossing
    curbs       |x| in [ROAD, ROAD + CURB_W]  granite curb, top at y = CURB_H, gutter + storm drains on the road side
    sidewalks   |x| in [ROAD, FACADE]          concrete slabs at y = CURB_H, 2.7 m wide: walk, dance and run room
    buildings   |x| >= FACADE                  facades face the road; alleys are gaps between buildings

Every piece is a class with a pivot and a side (+1 = right side of the road looking +z, -1 = left):
    pivot = (x, floor, z): base centre on the surface it stands on; facades/alleys pivot on the facade line.
    kind  = road | marking | sidewalk | building | alley | fence | prop      (draw layer; props are depth sorted)
    bg(fr, cam, T)      static layer drawing      item(cam, T) -> (depth, fn, name) for props sorted with people
    solid() -> box      collision box for the reel checks          lights() -> [Light]
Build a street from a LAYOUT list (see make_layout) and hand it to CityStreet. Characters stand at
floor_at(x) (pose key "floor" in rig.py).

    py -m sets.city_street --sheet  review/city_street_sheet.png     asset sheet (wide, both sidewalks, alley, props)
    py -m sets.city_street --manifest review/city_street.json        piece list with names, kinds, pivots, sizes
"""
import json
import math

import numpy as np
import skia

from toon import Rain, W, H, argb, lin, mix, paint, shade

ROAD, CURB_W, CURB_H, FACADE = 3.0, 0.16, 0.14, 5.7
Z_MIN, Z_MAX = -30.0, 140.0
CROSS = (6.6, 9.6)                                   # zebra crossing (z range)
FOG = "#1b2134"                                      # distance haze colour
WARM, SODIUM, COOL, WINDOW = "#ffc27a", "#ffb062", "#dfe8ff", "#ffc98a"
SKY0, SKY1 = "#04060d", "#151b30"


def floor_at(x):
    """Ground height under a point: the raised sidewalk beyond the curb face, the road inside it."""
    return CURB_H if abs(x) >= ROAD else 0.0


def fogged(colr, depth, k0=10.0, k1=70.0, amax=0.62):
    return mix(colr, FOG, max(0.0, min(amax, (depth - k0) / (k1 - k0) * amax)))


class Light:
    """A point light: key light for the toon shading, a hole in the night grade, rain glints, wet reflections."""

    def __init__(self, name, pos, colr=WARM, grade_r=3.0, k=0.95, flick=False, mirror=True):
        self.name, self.pos, self.colr, self.grade_r, self.k, self.flick, self.mirror = name, pos, colr, grade_r, k, flick, mirror

    def level(self, T):
        return flick(T) if self.flick else 1.0


# a flickering lamp dips on this 12 s pattern: (start s, length s, level)
FLICKS = [(0.55, 0.08, 0.2), (0.70, 0.05, 0.5), (1.90, 0.10, 0.15), (2.95, 0.06, 0.3), (3.74, 0.12, 0.08),
          (5.20, 0.07, 0.25), (6.40, 0.15, 0.1), (8.10, 0.06, 0.3), (9.70, 0.10, 0.1), (10.9, 0.05, 0.4)]


def flick(T):
    t = T % 12.0
    for a, d, lv in FLICKS:
        if a <= t < a + d:
            return lv
    return 1.0


def _vis(cam, P, margin=260):
    x, y, z, _ = cam.proj(P)
    return z > 0.3 and -margin < x < W + margin


def _quad_x(fr, cam, x, y0, y1, z0, z1, colr, a=1.0, outline=None, line=1.2):
    """A rectangle in the plane x = const (facade decals)."""
    return fr.poly(cam, [(x, y0, z0), (x, y0, z1), (x, y1, z1), (x, y1, z0)], colr=colr, a=a, outline=outline, line=line)


def _line(fr, cam, a, b, colr, w=1.0, a_=1.0, wm=0.0):
    p, q = cam.proj(a), cam.proj(b)
    if p[2] > 0.3 and q[2] > 0.3:
        fr.c.drawLine(p[0], p[1], q[0], q[1], paint(colr, a=a_, stroke=max(w, wm * min(p[3], q[3]))))


# ======================================================================================================
# pieces
# ======================================================================================================
class Piece:
    kind = "prop"
    size = (0.0, 0.0, 0.0)                           # x (across), y, z (along) extents in metres

    def __init__(self, name, x, z, side=0):
        self.name, self.x, self.z, self.side = name, x, z, side

    @property
    def pivot(self):
        return (self.x, floor_at(self.x), self.z)

    def bg(self, fr, cam, T):
        pass

    def item(self, cam, T):
        return None

    def solid(self):
        return None

    def lights(self):
        return []

    def depth(self, cam):
        return cam.view((self.x, 1.0, self.z))[2]


class RoadSegment(Piece):
    """Wet asphalt between the curbs, z0..z1: a darker gutter at each curb, tyre-polished lane sheen,
    the double yellow centre line (broken by the zebra crossing)."""
    kind = "road"

    def __init__(self, name, z0, z1):
        super().__init__(name, 0.0, (z0 + z1) / 2)
        self.z0, self.z1 = z0, z1
        self.size = (2 * ROAD, 0.0, z1 - z0)

    def bg(self, fr, cam, T):
        hy = H * cam.horizon
        z0, z1 = self.z0, self.z1
        fr.poly(cam, [(-ROAD, 0, z0), (ROAD, 0, z0), (ROAD, 0, z1), (-ROAD, 0, z1)],
                shader=lambda p: lin((0, hy), (0, H), [argb("#181c2a"), argb("#232838")]))
        for sx in (-1, 1):                                # gutters: the wettest, darkest strip
            fr.poly(cam, [(sx * (ROAD - 0.4), 0.001, z0), (sx * ROAD, 0.001, z0), (sx * ROAD, 0.001, z1), (sx * (ROAD - 0.4), 0.001, z1)],
                    colr="#10131e", a=0.7)
            fr.poly(cam, [(sx * 1.1, 0.001, z0), (sx * 1.9, 0.001, z0), (sx * 1.9, 0.001, z1), (sx * 1.1, 0.001, z1)],
                    colr="#2a3044", a=0.35)           # tyre track sheen in each lane
        for zz in np.arange(z0, z1, 6.0):                # asphalt patch seams
            _line(fr, cam, (-ROAD, 0.002, zz + 2.3), (ROAD, 0.002, zz + 2.6), "#0e111a", 1.0, 0.5)
        for xo in (-0.09, 0.09):                         # double yellow
            for a, b in ((z0, CROSS[0] - 0.6), (CROSS[1] + 0.6, z1)):
                if b > a:
                    fr.poly(cam, [(xo - 0.05, 0.003, a), (xo + 0.05, 0.003, a), (xo + 0.05, 0.003, b), (xo - 0.05, 0.003, b)],
                            colr="#c9a23a", a=0.55)


class Crosswalk(Piece):
    """Zebra crossing across the whole road, z0..z1: worn white bars along z, plus a stop bar each side."""
    kind = "marking"

    def __init__(self, name, z0, z1):
        super().__init__(name, 0.0, (z0 + z1) / 2)
        self.z0, self.z1 = z0, z1
        self.size = (2 * ROAD, 0.0, z1 - z0)

    def bg(self, fr, cam, T):
        for xc in np.arange(-ROAD + 0.45, ROAD - 0.3, 0.9):
            fr.poly(cam, [(xc - 0.25, 0.004, self.z0), (xc + 0.25, 0.004, self.z0), (xc + 0.25, 0.004, self.z1), (xc - 0.25, 0.004, self.z1)],
                    colr="#c8ccd6", a=0.42)
        for zz, x0, x1 in ((self.z0 - 1.0, 0.0, ROAD), (self.z1 + 1.0, -ROAD, 0.0)):
            fr.poly(cam, [(x0, 0.004, zz - 0.2), (x1, 0.004, zz - 0.2), (x1, 0.004, zz + 0.2), (x0, 0.004, zz + 0.2)], colr="#c8ccd6", a=0.4)


class Manhole(Piece):
    kind = "marking"
    size = (0.7, 0.0, 0.7)

    def bg(self, fr, cam, T):
        fr.ground_ellipse(cam, self.x, self.z, 0.36, 0.36, "#0c0e16", 0.9, y=0.005)
        fr.ground_ellipse(cam, self.x, self.z, 0.31, 0.31, "#2c3040", 0.9, y=0.006)
        for k in range(-2, 3):
            _line(fr, cam, (self.x - 0.27, 0.007, self.z + 0.1 * k), (self.x + 0.27, 0.007, self.z + 0.1 * k), "#151824", 1.0, 0.8)


class StormDrain(Piece):
    """Curb inlet: a grate in the gutter and the dark slot in the curb face behind it (pivot = grate centre)."""
    kind = "marking"
    size = (0.4, 0.0, 0.9)

    def bg(self, fr, cam, T):
        s, z = self.side, self.z
        x0, x1 = sorted((s * (ROAD - 0.42), s * (ROAD - 0.04)))
        fr.poly(cam, [(x0, 0.005, z - 0.45), (x1, 0.005, z - 0.45), (x1, 0.005, z + 0.45), (x0, 0.005, z + 0.45)], colr="#2a2e3a", outline="#0a0c12", line=1.2)
        for k in np.arange(-0.38, 0.4, 0.09):
            _line(fr, cam, (x0 + 0.03, 0.006, z + k), (x1 - 0.03, 0.006, z + k), "#06070c", 1.0, 0.9, wm=0.012)
        if cam.pos[0] * s < ROAD:
            _quad_x(fr, cam, s * (ROAD - 0.002), 0.02, 0.1, z - 0.5, z + 0.5, "#05060a")


class Sidewalk(Piece):
    """One side's sidewalk, z0..z1: curb face, curb top, 1.5 m concrete slabs, wet sheen near the lamps."""
    kind = "sidewalk"

    def __init__(self, name, side, z0, z1, lamps=()):
        super().__init__(name, side * (ROAD + FACADE) / 2, (z0 + z1) / 2, side)
        self.z0, self.z1, self.lamps = z0, z1, lamps
        self.size = (FACADE - ROAD, CURB_H, z1 - z0)

    def bg(self, fr, cam, T):
        s, z0, z1, y = self.side, self.z0, self.z1, CURB_H
        hy = H * cam.horizon
        xr, xc, xf = s * ROAD, s * (ROAD + CURB_W), s * FACADE
        if cam.pos[0] * s < ROAD:                         # curb face, seen from the road side
            _quad_x(fr, cam, xr, 0.0, y, z0, z1, "#4a505e")
            _line(fr, cam, (xr, 0.003, z0), (xr, 0.003, z1), "#0a0c14", 1.2, 0.9)
        fr.poly(cam, [(xc, y, z0), (xf, y, z0), (xf, y, z1), (xc, y, z1)],
                shader=lambda p: lin((0, hy), (0, H), [argb("#2c3142"), argb("#3a4052")]))
        fr.poly(cam, [(xr, y + 0.001, z0), (xc, y + 0.001, z0), (xc, y + 0.001, z1), (xr, y + 0.001, z1)], colr="#5d6372")
        _line(fr, cam, (xc, y + 0.002, z0), (xc, y + 0.002, z1), "#202432", 1.0, 0.8)
        for zz in np.arange(z0, z1, 1.5):                 # slab joints
            if _vis(cam, (s * 4.3, y, zz), 600):
                _line(fr, cam, (xc, y + 0.002, zz), (xf, y + 0.002, zz), "#1c2030", 1.0, 0.7, wm=0.004)
        _line(fr, cam, (s * (ROAD + 1.4), y + 0.002, z0), (s * (ROAD + 1.4), y + 0.002, z1), "#1c2030", 1.0, 0.45)
        for L in self.lamps:                              # restrained wet sheen under the lamps
            lx, _, lz = L.pos
            k = L.level(T)
            fr.ground_ellipse(cam, s * (ROAD + 1.0), lz, 1.5, 2.4, L.colr, 0.07 * k, blur_m=0.7, y=y + 0.002, add=True)


# ---- buildings -----------------------------------------------------------------------------------------------
STYLES = {
    "brick": dict(wall="#4c3430", trim="#2a2024", sill="#6a5c58"),
    "brick_red": dict(wall="#5a3a33", trim="#2c2026", sill="#7a6a62"),
    "plaster": dict(wall="#545866", trim="#2c303e", sill="#70747e"),
    "concrete": dict(wall="#464c5a", trim="#262a36", sill="#646a78"),
    "stone": dict(wall="#5a5860", trim="#2e2c36", sill="#7a7880"),
    "green": dict(wall="#3c4848", trim="#222c2e", sill="#5c6a68"),
}


class Building(Piece):
    """A facade block on one side, z0..z1 along the street, `floors` storeys (ground floor 3.6 m, uppers 3.0 m).
    ground: list of (z centre, kind) with kind in door | shop | shutter | lobby | blank. roof: flat | tank |
    setback | cornice. lit: share of upper windows lit warm (deterministic per building)."""
    kind = "building"
    GF, FL = 3.6, 3.0

    def __init__(self, name, side, z0, z1, floors, style="brick", ground=(), roof="cornice", lit=0.22, depth=10.0,
                 seed=0, fire_escape=False):
        super().__init__(name, side * FACADE, (z0 + z1) / 2, side)
        self.z0, self.z1, self.floors, self.st = z0, z1, floors, STYLES[style]
        self.ground, self.roof, self.lit, self.d, self.seed, self.fe = list(ground), roof, lit, depth, seed, fire_escape
        self.top = self.GF + (floors - 1) * self.FL + 0.5
        self.size = (depth, self.top, z1 - z0)

    @property
    def pivot(self):
        return (self.x, 0.0, self.z)

    def depth(self, cam):
        zs = (self.z0, self.z1)
        return max(cam.view((self.side * (FACADE + self.d / 2), 4.0, max(min(cam.pos[2], zs[1]), zs[0])))[2], 0.5) + \
            0.001 * abs(self.z - cam.pos[2])

    def _cols(self):
        n = max(1, int((self.z1 - self.z0 - 0.6) / 2.2))
        w = (self.z1 - self.z0) / n
        return [self.z0 + w * (i + 0.5) for i in range(n)]

    def _is_lit(self, f, i):
        h = (f * 73 + i * 151 + self.seed * 97 + int(self.z0 * 7)) % 100
        return h < self.lit * 100

    def bg(self, fr, cam, T):
        s, z0, z1 = self.side, self.z0, self.z1
        dz = cam.view((s * FACADE, 3.0, (z0 + z1) / 2))[2]
        if dz < -self.d - 30 or max(cam.view((s * FACADE, 3.0, z0))[2], cam.view((s * FACADE, 3.0, z1))[2]) < 0.2:
            return
        wall = fogged(self.st["wall"], dz)
        trim = fogged(self.st["trim"], dz)
        xs = sorted((s * FACADE, s * (FACADE + self.d)))
        fr.box(cam, xs, (0, self.top), (z0, z1), wall, line=1.3, top_k=0.05, side_k=-0.3)
        if cam.pos[0] * s >= FACADE:
            return
        xf = s * (FACADE - 0.012)
        # plinth, belt course between ground and first floor, cornice
        _quad_x(fr, cam, xf, CURB_H, CURB_H + 0.45, z0, z1, shade(wall, -0.35))
        _quad_x(fr, cam, xf - s * 0.01, self.GF - 0.12, self.GF + 0.08, z0, z1, fogged(self.st["sill"], dz))
        if self.roof in ("cornice", "tank", "setback"):
            fr.box(cam, sorted((s * (FACADE - 0.28), s * (FACADE + 0.2))), (self.top - 0.42, self.top - 0.1), (z0 - 0.1, z1 + 0.1),
                   fogged(self.st["sill"], dz), line=1.1)
        # upper windows
        cols = self._cols()
        for f in range(1, self.floors):
            y = self.GF + (f - 1) * self.FL + 0.75
            for i, zc in enumerate(cols):
                if not _vis(cam, (xf, y, zc)):
                    continue
                self.window(fr, cam, xf, y, zc, f, i, dz, T)
        # ground floor
        for zc, kind in self.ground:
            if _vis(cam, (xf, 1.5, zc), 600):
                getattr(self, "g_" + kind)(fr, cam, xf, zc, dz, T)
        if self.fe and self.floors > 2:
            self.fire_escape(fr, cam, xf, dz)
        self.roof_bits(fr, cam, dz)

    def window(self, fr, cam, xf, y, zc, f, i, dz, T):
        s, st = self.side, self.st
        w, h = 0.55, 1.45
        lit = self._is_lit(f, i)
        _quad_x(fr, cam, xf, y - 0.12, y - 0.04, zc - w - 0.08, zc + w + 0.08, fogged(st["sill"], dz))      # sill
        _quad_x(fr, cam, xf, y, y + h, zc - w, zc + w, fogged(st["trim"], dz))                             # frame
        if lit:
            colr = fogged(WINDOW if (f + i) % 5 else "#ffdcae", dz, amax=0.35)
            _quad_x(fr, cam, xf, y + 0.06, y + h - 0.06, zc - w + 0.06, zc + w - 0.06, colr)
            # curtains drawn to the sides, a lampshade silhouette in one of them
            _quad_x(fr, cam, xf, y + 0.06, y + h - 0.06, zc - w + 0.06, zc - w + 0.26, shade(colr, -0.3))
            _quad_x(fr, cam, xf, y + 0.06, y + h - 0.06, zc + w - 0.26, zc + w - 0.06, shade(colr, -0.3))
            if (f * 3 + i) % 4 == 0:
                fr.poly(cam, [(xf, y + 0.35, zc - 0.12), (xf, y + 0.35, zc + 0.12), (xf, y + 0.55, zc + 0.08), (xf, y + 0.55, zc - 0.08)],
                        colr=shade(colr, -0.45))
            x, yy, z, sc = cam.proj((xf, y + h / 2, zc))
            if z > 0.5:
                fr.glow(x, yy, 1.1 * sc, "#ff9a48", a=0.12 * (1 - min(0.8, dz / 80)))
        else:
            glass = fogged("#111726", dz, amax=0.4)
            _quad_x(fr, cam, xf, y + 0.06, y + h - 0.06, zc - w + 0.06, zc + w - 0.06, glass)
            _line(fr, cam, (xf, y + h - 0.3, zc - w + 0.12), (xf, y + h - 0.12, zc - w + 0.4), "#3a4660", 1.0, 0.5)   # sky glint
        _line(fr, cam, (xf, y + h * 0.55, zc - w + 0.06), (xf, y + h * 0.55, zc + w - 0.06), fogged(st["trim"], dz), 1.0, 0.9, wm=0.02)

    # -- ground floor kinds --
    def g_door(self, fr, cam, xf, zc, dz, T):
        """Recessed entrance: steps, a dark door with a lit transom and a small lamp over it."""
        s = self.side
        _quad_x(fr, cam, xf, CURB_H, 2.75, zc - 0.75, zc + 0.75, shade(self.st["wall"], -0.55))
        _quad_x(fr, cam, xf, CURB_H, 2.3, zc - 0.55, zc + 0.55, "#1e1a1c", outline="#0c0a0c")
        _quad_x(fr, cam, xf, 2.36, 2.66, zc - 0.55, zc + 0.55, "#ffcf8e")
        _line(fr, cam, (xf, 2.36, zc), (xf, 2.66, zc), "#5a3a20", 1.0, 0.9)
        x, y, z, sc = cam.proj((xf, 1.3, zc + 0.38))
        if z > 0.3:
            fr.c.drawCircle(x, y, max(1.2, 0.025 * sc), paint("#c8a060"))                  # door knob
        x, y, z, sc = cam.proj((xf - s * 0.1, 2.9, zc))
        if z > 0.3:
            fr.c.drawOval(skia.Rect(x - 0.1 * sc, y - 0.06 * sc, x + 0.1 * sc, y + 0.06 * sc), paint("#fff0d0"))
            fr.glow(x, y, 1.2 * sc, WARM, a=0.3)
        fr.box(cam, sorted((s * (FACADE - 0.35), s * FACADE)), (CURB_H, CURB_H + 0.16), (zc - 0.7, zc + 0.7), "#5a5e6a", line=1.1)

    def g_shop(self, fr, cam, xf, zc, dz, T, w=1.9):
        """Lit corner-store front: warm interior, shelves of stock, a counter, an awning."""
        s = self.side
        _quad_x(fr, cam, xf, CURB_H + 0.45, 3.0, zc - w, zc + w, "#ffd8a0")
        for y in (0.95, 1.45, 1.95):                          # shelves with product silhouettes
            _quad_x(fr, cam, xf, y, y + 0.04, zc - w + 0.2, zc + w - 1.0, "#8a6a48")
            for k, zz in enumerate(np.arange(zc - w + 0.25, zc + w - 1.05, 0.16)):
                _quad_x(fr, cam, xf, y + 0.04, y + 0.2 + 0.06 * ((k * 7) % 3), zz, zz + 0.11,
                        ["#c04a3a", "#3a7ac0", "#e0b040", "#5aa05a", "#d0d0c8"][(k + int(y * 10)) % 5])
        _quad_x(fr, cam, xf, CURB_H + 0.45, 1.15, zc + w - 0.9, zc + w - 0.1, "#6a4a32")          # counter
        for zz in (zc - w, zc, zc + w):                        # mullions
            _quad_x(fr, cam, xf, CURB_H + 0.45, 3.0, zz - 0.05, zz + 0.05, "#1a1c24")
        _quad_x(fr, cam, xf, 3.0, 3.35, zc - w - 0.1, zc + w + 0.1, "#1e2a3a")                       # sign band
        _quad_x(fr, cam, xf, 3.07, 3.28, zc - w + 0.4, zc + w - 0.4, "#c84a3a")
        fr.poly(cam, [(xf, 3.38, zc - w - 0.15), (xf, 3.38, zc + w + 0.15), (s * (FACADE - 1.1), 2.85, zc + w + 0.15),
                      (s * (FACADE - 1.1), 2.85, zc - w - 0.15)], colr="#2f4a5a", outline="#121a22", line=1.2)       # awning
        x, y, z, sc = cam.proj((s * (FACADE - 0.9), 1.6, zc))
        if z > 0.3:
            fr.glow(x, y, 2.4 * sc, WARM, a=0.2)

    def g_shutter(self, fr, cam, xf, zc, dz, T, w=1.8):
        _quad_x(fr, cam, xf, CURB_H + 0.2, 2.9, zc - w, zc + w, fogged("#5a5e68", dz))
        for y in np.arange(CURB_H + 0.3, 2.85, 0.1):
            _line(fr, cam, (xf, y, zc - w + 0.05), (xf, y, zc + w - 0.05), "#3a3e48", 1.0, 0.8, wm=0.008)
        _quad_x(fr, cam, xf, 2.95, 3.3, zc - w, zc + w, "#2a2a30")
        _line(fr, cam, (xf, 2.0, zc - w + 0.4), (xf, 1.6, zc - 0.2), "#a04050", 1.4, 0.6, wm=0.02)        # graffiti tag
        _line(fr, cam, (xf, 1.6, zc - 0.2), (xf, 2.1, zc + 0.4), "#a04050", 1.4, 0.6, wm=0.02)

    def g_lobby(self, fr, cam, xf, zc, dz, T):
        """Apartment lobby: glass double doors, cool fluorescent light inside, mailboxes on the back wall."""
        s = self.side
        _quad_x(fr, cam, xf, CURB_H, 2.8, zc - 1.0, zc + 1.0, "#cfd8e6")
        for k in range(4):
            _quad_x(fr, cam, xf, 1.0, 1.6, zc - 0.85 + 0.42 * k, zc - 0.5 + 0.42 * k, "#8a909a")
        for zz in (zc - 1.0, zc, zc + 1.0):
            _quad_x(fr, cam, xf, CURB_H, 2.8, zz - 0.05, zz + 0.05, "#20242c")
        _quad_x(fr, cam, xf, 2.4, 2.46, zc - 1.0, zc + 1.0, "#20242c")
        x, y, z, sc = cam.proj((s * (FACADE - 0.6), 1.5, zc))
        if z > 0.3:
            fr.glow(x, y, 2.0 * sc, COOL, a=0.16)

    def g_blank(self, fr, cam, xf, zc, dz, T):
        pass

    def fire_escape(self, fr, cam, xf, dz):
        s = self.side
        za, zb = self.z0 + 0.8, self.z0 + 4.2
        col = fogged("#15171e", dz, amax=0.45)
        for f in range(1, self.floors):
            y = self.GF + (f - 1) * self.FL + 0.05
            xo = s * (FACADE - 1.0)
            fr.poly(cam, [(xf, y, za), (xf, y, zb), (xo, y, zb), (xo, y, za)], colr=col, a=0.55)
            for zz in np.arange(za, zb + 0.01, 0.3):
                _line(fr, cam, (xo, y, zz), (xo, y + 0.9, zz), col, 1.0, 0.9)
            _line(fr, cam, (xo, y + 0.9, za), (xo, y + 0.9, zb), col, 1.2, 0.9)
            if f < self.floors - 1:
                _line(fr, cam, (xo, y, za + 0.3 if f % 2 else zb - 0.3), (xo, y + self.FL, zb - 0.3 if f % 2 else za + 0.3), col, 1.4, 0.9)

    def roof_bits(self, fr, cam, dz):
        s = self.side
        if self.roof == "tank":
            xc, zc = s * (FACADE + self.d * 0.55), self.z0 + (self.z1 - self.z0) * 0.6
            for dx, dzz in ((-0.6, -0.6), (0.6, -0.6), (-0.6, 0.6), (0.6, 0.6)):
                fr.box(cam, (xc + dx - 0.05, xc + dx + 0.05), (self.top, self.top + 1.4), (zc + dzz - 0.05, zc + dzz + 0.05), fogged("#2a2a30", dz), line=1.0)
            fr.box(cam, (xc - 0.9, xc + 0.9), (self.top + 1.4, self.top + 3.2), (zc - 0.9, zc + 0.9), fogged("#4a3c32", dz), line=1.2)
            fr.poly(cam, [(xc - 0.95, self.top + 3.2, zc - 0.95), (xc, self.top + 4.0, zc), (xc + 0.95, self.top + 3.2, zc - 0.95)],
                    colr=fogged("#34302e", dz), outline="#14141a")
        elif self.roof == "setback":
            xs = sorted((s * (FACADE + 2.5), s * (FACADE + self.d)))
            fr.box(cam, xs, (self.top, self.top + 3.0), (self.z0 + 1.5, self.z1 - 1.5), fogged(shade(self.st["wall"], -0.1), dz), line=1.2)
        elif self.roof == "flat":
            xs = sorted((s * (FACADE + 3.0), s * (FACADE + 4.4)))
            fr.box(cam, xs, (self.top, self.top + 0.9), (self.z0 + 2.0, self.z0 + 3.6), fogged("#3a3e48", dz), line=1.0)   # AC unit

    def solid(self):
        return (tuple(sorted((self.side * FACADE, self.side * (FACADE + self.d)))), (0.0, self.top), (self.z0, self.z1))

    def lights(self):
        out = []
        for zc, kind in self.ground:
            if kind == "shop":
                out.append(Light(f"{self.name}_shop", (self.side * (FACADE - 0.9), 1.6, zc), WARM, 2.8, 0.75, mirror=False))
            elif kind == "lobby":
                out.append(Light(f"{self.name}_lobby", (self.side * (FACADE - 0.6), 1.5, zc), COOL, 2.2, 0.6, mirror=False))
            elif kind == "door":
                out.append(Light(f"{self.name}_door", (self.side * (FACADE - 0.1), 2.9, zc), WARM, 1.6, 0.6, mirror=False))
        return out


class Alley(Piece):
    """A narrow gap between two buildings, z0..z1, running back from the facade line: wet floor, a dim bulb
    halfway down, bags and a dumpster, a dead end wall. The flanking buildings' side walls are its walls."""
    kind = "alley"

    def __init__(self, name, side, z0, z1, depth=9.0):
        super().__init__(name, side * FACADE, (z0 + z1) / 2, side)
        self.z0, self.z1, self.d = z0, z1, depth
        self.size = (depth, 6.0, z1 - z0)

    @property
    def pivot(self):
        return (self.x, CURB_H, self.z)

    def depth(self, cam):
        return cam.view((self.side * (FACADE + self.d), 2.0, self.z))[2] + 50

    def bg(self, fr, cam, T):
        s, z0, z1 = self.side, self.z0, self.z1
        if cam.pos[0] * s >= FACADE or not _vis(cam, (s * FACADE, 1.0, self.z), 500):
            return
        xa, xb = s * FACADE, s * (FACADE + self.d)
        fr.poly(cam, [(xa, CURB_H, z0), (xb, CURB_H, z0), (xb, CURB_H, z1), (xa, CURB_H, z1)], colr="#11141e")
        _quad_x(fr, cam, xb, CURB_H, 7.0, z0, z1, "#0c0e16")                                    # dead end
        bx, bz = s * (FACADE + self.d * 0.55), (z0 + z1) / 2
        fr.box(cam, sorted((bx - s * 0.6, bx + s * 0.6)), (CURB_H, 1.3), (z0 + 0.1, z0 + 0.95), "#24382e", line=1.2)   # dumpster
        for k, (dx, dzz) in enumerate(((0.3, 0.75), (0.75, 0.9), (-0.4, 0.8))):                 # trash bags
            x, y, z, sc = cam.proj((s * (FACADE + 1.4 + dx), CURB_H + 0.22, z1 - dzz * (z1 - z0) * 0.5))
            if z > 0.3:
                fr.c.drawOval(skia.Rect(x - 0.3 * sc, y - 0.24 * sc, x + 0.3 * sc, y + 0.24 * sc), paint("#0a0b10"))
        x, y, z, sc = cam.proj((bx, 3.2, bz))                                                    # the dim bulb
        if z > 0.3:
            fr.c.drawCircle(x, y, max(1.5, 0.05 * sc), paint("#ffe0a8"))
            fr.glow(x, y, 2.2 * sc, "#ffb060", a=0.16)
        fr.ground_ellipse(cam, bx, bz, 1.2, 0.6, "#ffb060", 0.06, blur_m=0.5, y=CURB_H + 0.002, add=True)


class Fence(Piece):
    """Chain-link (alley mouths, mesh you can see through) or a low iron railing, along z at x = side * xpos."""
    kind = "fence"

    def __init__(self, name, side, z0, z1, xpos=FACADE, h=2.1, style="chain", gate_open=0.0):
        super().__init__(name, side * xpos, (z0 + z1) / 2, side)
        self.z0, self.z1, self.h, self.style, self.open = z0, z1, h, style, gate_open
        self.size = (0.05, h, z1 - z0)

    def depth(self, cam):
        return cam.view((self.x, 1.0, self.z))[2] + 0.2

    def bg(self, fr, cam, T):
        if not _vis(cam, (self.x, 1.0, self.z), 500):
            return
        x, y0, z0, z1, h = self.x, CURB_H, self.z0, self.z1 - self.open, self.h
        if self.style == "chain":
            for zz in np.arange(z0, z1 + 0.01, (z1 - z0) / max(1, round((z1 - z0) / 2.0))):
                fr.box(cam, (x - 0.03, x + 0.03), (y0, y0 + h + 0.05), (zz - 0.03, zz + 0.03), "#6a707c", line=1.0)
            _line(fr, cam, (x, y0 + h, z0), (x, y0 + h, z1), "#6a707c", 1.4, 0.9, wm=0.02)
            for zz in np.arange(z0, z1, 0.1):                     # diamond mesh as two diagonal hatches
                _line(fr, cam, (x, y0, zz), (x, y0 + h, min(z1, zz + h * 0.5)), "#8a909c", 1.0, 0.22)
                _line(fr, cam, (x, y0, min(z1, zz + h * 0.5)), (x, y0 + h, zz), "#8a909c", 1.0, 0.22)
        else:
            _line(fr, cam, (x, y0 + h, z0), (x, y0 + h, z1), "#15161c", 1.4, 1.0, wm=0.025)
            _line(fr, cam, (x, y0 + 0.12, z0), (x, y0 + 0.12, z1), "#15161c", 1.2, 1.0, wm=0.02)
            for zz in np.arange(z0, z1 + 0.01, 0.13):
                _line(fr, cam, (x, y0, zz), (x, y0 + h + 0.06, zz), "#15161c", 1.0, 1.0, wm=0.012)

    def solid(self):
        return ((self.x - 0.04, self.x + 0.04), (CURB_H, CURB_H + self.h), (self.z0, self.z1 - self.open))


# ---- props (depth sorted with the cast) ---------------------------------------------------------------------
class StreetLight(Piece):
    """Steel pole on the curb edge of the sidewalk, an arm out over the road, a sodium head. Pivot = pole base."""
    kind = "prop"
    size = (1.3, 5.6, 0.2)

    def __init__(self, name, side, z, flicker=False):
        super().__init__(name, side * (ROAD + 0.35), z, side)
        self.flicker = flicker
        self.head = (side * (ROAD - 0.75), 5.35, z)
        self.light = Light(name, self.head, SODIUM, 3.4, 0.95, flick=flicker)

    def item(self, cam, T):
        s, x, z = self.side, self.x, self.z
        hx, hy, hz = self.head
        on = self.light.level(T)

        def fn(fr):
            if not _vis(cam, (x, 3.0, z), 400):
                return
            L = self.head
            fr.box(cam, (x - 0.07, x + 0.07), (CURB_H, 5.5), (z - 0.07, z + 0.07), "#3a4048", light=L, line=1.3)
            fr.box(cam, (x - 0.13, x + 0.13), (CURB_H, CURB_H + 0.5), (z - 0.13, z + 0.13), "#30363e", line=1.2)
            fr.box(cam, sorted((x, hx - s * 0.1)), (5.42, 5.5), (z - 0.04, z + 0.04), "#3a4048", line=1.1)
            fr.box(cam, sorted((hx - s * 0.35, hx + s * 0.25)), (5.32, 5.46), (hz - 0.16, hz + 0.16), "#2c3038", line=1.1)
            a, b, d, sc = cam.proj((hx, hy - 0.005, hz))
            if d < 0.3:
                return
            fr.c.drawOval(skia.Rect(a - 0.22 * sc, b - 0.03 * sc, a + 0.22 * sc, b + 0.05 * sc), paint("#fff1d0" if on > 0.6 else "#5a5448"))
            fr.glow(a, b + 0.25 * sc, 2.8 * sc, SODIUM, a=0.24 * on)
            fr.glow(a, b + 0.05 * sc, 0.8 * sc, "#ffe0b0", a=0.5 * on)
            # the cone of light down to the ground: a faint wedge
            g0, g1 = cam.proj((hx - 1.4, 0.0, hz)), cam.proj((hx + 1.4, 0.0, hz))
            if g0[2] > 0.3 and g1[2] > 0.3:
                path = skia.Path()
                path.moveTo(a - 0.18 * sc, b)
                path.lineTo(a + 0.18 * sc, b)
                path.lineTo(g1[0], g1[1])
                path.lineTo(g0[0], g0[1])
                path.close()
                fr.c.drawPath(path, paint(SODIUM, a=0.035 * on, blur=0.3 * sc, blend="add"))
        return (cam.view((x, 2.5, z))[2], fn, self.name)

    def solid(self):
        return ((self.x - 0.13, self.x + 0.13), (CURB_H, 5.5), (self.z - 0.13, self.z + 0.13))

    def lights(self):
        return [self.light]


class UtilityPole(Piece):
    """Creosote wood pole with a crossarm, insulators and a transformer drum. Wires: CityStreet.wires()."""
    kind = "prop"
    size = (1.8, 8.4, 0.24)

    def __init__(self, name, side, z, drum=False):
        super().__init__(name, side * (ROAD + 0.3), z, side)
        self.drum = drum

    def item(self, cam, T):
        x, z, s = self.x, self.z, self.side

        def fn(fr):
            if not _vis(cam, (x, 3.0, z), 400):
                return
            fr.box(cam, (x - 0.12, x + 0.12), (CURB_H, 8.3), (z - 0.12, z + 0.12), "#4a3e34", line=1.3)
            fr.box(cam, (x - 0.95, x + 0.95), (7.6, 7.72), (z - 0.05, z + 0.05), "#3a3028", line=1.1)
            for dx in (-0.8, -0.3, 0.3, 0.8):
                fr.box(cam, (x + dx - 0.025, x + dx + 0.025), (7.72, 7.84), (z - 0.025, z + 0.025), "#b8bcc0", line=0.8)
            if self.drum:
                fr.box(cam, sorted((x + s * 0.15, x + s * 0.55)), (6.2, 6.9), (z - 0.2, z + 0.2), "#535a66", line=1.1)
            for y in np.arange(2.2, 5.0, 0.45):
                fr.box(cam, (x - 0.17, x + 0.17), (y, y + 0.025), (z - 0.012, z + 0.012), "#2a2622", line=0.6)
            for k in range(3):                                   # stapled flyers
                _quad_x(fr, cam, x - s * 0.125, 1.2 + 0.25 * k, 1.42 + 0.25 * k, z - 0.09, z + 0.09, ["#c8c0a8", "#d8b860", "#a8c0c8"][k])
        return (cam.view((x, 2.5, z))[2], fn, self.name)

    def solid(self):
        return ((self.x - 0.12, self.x + 0.12), (CURB_H, 8.3), (self.z - 0.12, self.z + 0.12))


CAN_COLS = ["#d8343a", "#2f6fd0", "#f0b32a", "#3aa35a", "#e8e8e8", "#8a3ad0", "#e07020", "#20a0b0"]


class VendingMachine(Piece):
    """Drinks machine against a facade, its lit front toward the road. Pivot = front-face base centre."""
    kind = "prop"
    size = (0.75, 1.83, 0.95)

    def __init__(self, name, side, z, body="#d9dde4", band="#d8343a"):
        super().__init__(name, side * (FACADE - 0.78), z, side)
        self.body, self.band = body, band
        xs = sorted((side * (FACADE - 0.78), side * (FACADE - 0.02)))
        self.box = (tuple(xs), (CURB_H, CURB_H + 1.83), (z - 0.475, z + 0.475))
        self.light = Light(name, (side * (FACADE - 1.6), CURB_H + 1.2, z), COOL, 1.8, 0.75, mirror=False)

    def item(self, cam, T):
        (x0, x1), (y0, y1), (z0, z1) = self.box
        s = self.side
        xf = self.x - s * 0.004

        def fn(fr):
            if not _vis(cam, (xf, 1.0, self.z), 400):
                return
            fr.box(cam, (x0, x1), (y0, y1), (z0, z1), self.body, light=self.light.pos, line=1.5)
            if cam.pos[0] * s >= self.x * s:
                return
            q = lambda ya, yb, za, zb, c, **kw: _quad_x(fr, cam, xf, y0 + ya, y0 + yb, za, zb, c, **kw)   # noqa: E731
            q(1.62, 1.78, z0 + 0.06, z1 - 0.06, "#ffffff")
            q(1.62, 1.72, z0 + 0.15, z1 - 0.15, self.band)
            q(0.95, 1.58, z0 + 0.06, z1 - 0.06, "#fff8e8")
            for r, y in enumerate((1.38, 1.17, 0.98)):
                for i, z in enumerate(np.arange(z0 + 0.1, z1 - 0.12, 0.105)):
                    colr = CAN_COLS[(i * 3 + r * 5) % len(CAN_COLS)]
                    _quad_x(fr, cam, xf - s * 0.002, y0 + y, y0 + y + 0.15, z, z + 0.07, colr, outline=shade(colr, -0.5), line=0.8)
            q(0.12, 0.34, z0 + 0.12, z1 - 0.12, "#1a1c22")
            q(0.55, 0.85, z1 - 0.32, z1 - 0.12, "#3a3e48")
            x, y, z, sc = cam.proj((xf - s * 0.3, y0 + 1.3, self.z))
            if z > 0.3:
                fr.glow(x, y, 1.5 * sc, COOL, a=0.26 * (1 + 0.03 * math.sin(T * 50)))
        return (cam.view((self.x, 1.0, self.z))[2], fn, self.name)

    def solid(self):
        return self.box

    def lights(self):
        return [self.light]


# ======================================================================================================
# the set
# ======================================================================================================
LAYER = {"road": 0, "marking": 1, "sidewalk": 2, "alley": 3, "building": 4, "fence": 5}


class CityStreet:
    """bg + depth-sorted items + rain + night grade for a LAYOUT of pieces. Characters are added by the scene."""
    NIGHT = 0.5

    def __init__(self, layout, wires=(), fog_banks=(), seed=11):
        self.pieces = layout
        self.by_name = {p.name: p for p in layout}
        self.LIGHTS = [L for p in layout for L in p.lights()]
        self.LAMPS = [L for L in self.LIGHTS if L.mirror]
        self.wire_runs = list(wires)
        self.fog_banks = list(fog_banks)
        self.RAIN = Rain(n=4200, box=((-6.5, 6.5), (0, 8.0), (-12, 75)), speed=8.0, seed=seed)

    # -- lookups --
    def floor_at(self, x):
        return floor_at(x)

    def nearest_light(self, p):
        return min(self.LIGHTS, key=lambda L: math.dist(L.pos, p) / L.k).pos

    def solids(self):
        return {p.name: p.solid() for p in self.pieces if p.solid()}

    # -- drawing --
    def sky(self, fr, cam):
        hy = H * cam.horizon
        fr.c.drawRect(skia.Rect(0, 0, W, H), paint(shader=lin((0, 0), (0, hy + 60), [argb(SKY0), argb("#0b1022"), argb(SKY1)], [0, 0.55, 1])))
        r = np.random.default_rng(4)
        for z, base, col in ((260, 40, "#0f1426"), (190, 26, "#131a30")):      # far skyline
            xs = np.arange(-200, 200, 9.0)
            for x in xs:
                hgt = base * r.uniform(0.35, 1.0) * (1.5 if r.random() < 0.12 else 1.0)
                fr.poly(cam, [(x, -2, z), (x + 8.2, -2, z), (x + 8.2, hgt, z), (x, hgt, z)], colr=col)
                for _ in range(int(r.integers(0, 4))):
                    wx, wy = x + r.uniform(1, 7), r.uniform(3, hgt - 2)
                    p = cam.proj((wx, wy, z))
                    if p[2] > 1:
                        fr.c.drawRect(skia.Rect(p[0], p[1], p[0] + max(1.0, 0.6 * p[3]), p[1] + max(1.0, 0.9 * p[3])), paint("#c8a470", a=0.35))
        fr.c.drawRect(skia.Rect(0, hy - 320, W, hy + 120), paint(shader=lin((0, hy - 320), (0, hy + 120),
                      [argb("#2a2848", 0), argb("#2c2a4a", 0.32), argb(FOG, 0)], [0, 0.65, 1])))   # city glow on low cloud

    def ground_layer(self, fr, cam, T):
        for p in sorted([p for p in self.pieces if LAYER.get(p.kind, 9) <= 1], key=lambda p: LAYER[p.kind]):
            p.bg(fr, cam, T)
        for L in self.LAMPS:                                   # restrained wet reflections on the road
            lx, ly, lz = L.pos
            k = L.level(T)
            fr.ground_ellipse(cam, lx, lz, 1.9, 2.6, L.colr, 0.07 * k, blur_m=0.8, add=True)
            x, y, z, s = cam.proj((lx, -ly, lz))
            if z > 0.6:
                fr.glow(x, y, 0.4 * s, L.colr, a=0.16 * k, sx=0.55, sy=3.0)
        for px, pz, rx, rz in PUDDLES:
            fr.ground_ellipse(cam, px, pz, rx, rz, "#10141f", 0.7, blur_m=0.03, y=0.003)
            fr.ground_ellipse(cam, px, pz, rx * 0.8, rz * 0.7, "#343a5c", 0.18, blur_m=0.05, y=0.004)
            for k in range(2):
                u = (T * 1.3 + k * 0.5 + px) % 1.0
                cx = px + rx * 0.5 * math.sin(k * 2.1 + int(T * 1.3 + k * 0.5 + px) * 1.7)
                cz = pz + rz * 0.4 * math.cos(k * 1.3 + int(T * 1.3) * 0.7)
                ring(fr, cam, cx, cz, 0.04 + 0.14 * u, (1 - u) * 0.35)

    def bg(self, fr, cam, T):
        self.sky(fr, cam)
        self.ground_layer(fr, cam, T)
        for p in self.pieces:
            if p.kind == "sidewalk":
                p.bg(fr, cam, T)
        rest = [p for p in self.pieces if p.kind in ("alley", "building", "fence")]
        for p in sorted(rest, key=lambda p: -p.depth(cam)):
            p.bg(fr, cam, T)
        self.wires(fr, cam)
        self.ground_fog(fr, cam, T)

    def items(self, cam, T):
        return [it for it in (p.item(cam, T) for p in self.pieces if p.kind == "prop") if it]

    def wires(self, fr, cam):
        for a, b, sag in self.wire_runs:
            cat(fr, cam, a, b, sag)

    def ground_fog(self, fr, cam, T):
        """Low drifting fog: wide soft pools hugging the ground, thicker with distance (never over the cast)."""
        for x, z, r in self.fog_banks:
            xx = x + 0.6 * math.sin(T * 0.15 + z)
            d = cam.view((xx, 0.2, z))[2]
            if d < 1.5:
                continue
            a = min(0.12, 0.02 + d / 300)
            fr.ground_ellipse(cam, xx, z, r, r * 0.6, "#8a96ba", a, blur_m=0.9, y=0.25)

    def rain(self, fr, cam, T, light=None):
        # thin, sparse near drops: no heavy streaks across faces
        self.RAIN.draw(fr, cam, T, light=light, colr=(0.7, 0.78, 0.95), amax=0.26, zmin=2.2, wmax=1.5)

    def night(self, fr, cam, T, extra=()):
        """Night grade: darken toward night with soft holes round every light and round the cast (extra =
        [(point, radius, strength)]), so faces stay readable."""
        lights = [(L.pos[:1] + (min(L.pos[1], 1.2),) + L.pos[2:], L.grade_r, L.k * L.level(T)) for L in self.LIGHTS]
        lights += list(extra)
        c = fr.c
        c.saveLayer()
        c.drawRect(skia.Rect(0, 0, W, H), paint("#03050c", a=self.NIGHT))
        for P, rm, s in lights:
            x, y, z = cam.view(P)
            if z < 0.35:
                continue
            sc = cam.f / z
            sx, sy, R = W / 2 + x * sc, H * cam.horizon - y * sc, min(rm * sc, 3.0 * H)
            if not (-R < sx < W + R and -R < sy < H + R):
                continue
            pt = paint(shader=skia.GradientShader.MakeRadial(skia.Point(sx, sy), max(R, 1.0),
                       [argb("#000000", s), argb("#000000", s * 0.55), argb("#000000", 0)], [0.0, 0.45, 1.0]))
            pt.setBlendMode(skia.BlendMode.kDstOut)
            c.drawRect(skia.Rect(0, 0, W, H), pt)
        c.restore()

    def manifest(self):
        rows = []
        for p in self.pieces:
            rows.append(dict(name=p.name, piece=type(p).__name__, kind=p.kind, side=p.side,
                             pivot=[round(v, 3) for v in p.pivot], size_m=[round(v, 3) for v in p.size],
                             solid=p.solid()))
        return dict(units="metres, y up, road along +z, x = 0 road centre line",
                    road_half=ROAD, curb=dict(width=CURB_W, height=CURB_H), facade_x=FACADE, crosswalk_z=CROSS,
                    sidewalk_width=FACADE - ROAD, pieces=rows,
                    lights=[dict(name=L.name, pos=L.pos, flicker=L.flick) for L in self.LIGHTS])


PUDDLES = [(1.6, 3.0, 0.9, 0.35), (-1.8, 12.4, 1.1, 0.4), (2.2, 18.0, 0.8, 0.3), (-0.9, 26.0, 1.3, 0.45),
           (-4.6, 2.6, 0.5, 0.25), (4.4, 15.2, 0.55, 0.22), (1.0, 36.0, 1.2, 0.4)]


def ring(fr, cam, cx, cz, r, a, y=0.005):
    pts = [cam.proj((cx + r * math.cos(t), y, cz + r * 0.55 * math.sin(t))) for t in np.linspace(0, 2 * math.pi, 14)]
    if min(p[2] for p in pts) < 0.5:
        return
    path = skia.Path()
    path.moveTo(*pts[0][:2])
    for p in pts[1:]:
        path.lineTo(*p[:2])
    fr.c.drawPath(path, paint("#b8c8f0", a=a, stroke=max(0.8, 0.008 * pts[0][3])))


def cat(fr, cam, a, b, sag):
    pts = []
    for t in np.linspace(0, 1, 20):
        p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t - sag * 4 * t * (1 - t), a[2] + (b[2] - a[2]) * t)
        pp = cam.proj(p)
        if pp[2] < 0.3:
            pts = []
            continue
        pts.append(pp)
    if len(pts) > 1:
        path = skia.Path()
        path.moveTo(*pts[0][:2])
        for p in pts[1:]:
            path.lineTo(*p[:2])
        fr.c.drawPath(path, paint("#07080e", a=0.85, stroke=max(1.0, 0.012 * pts[len(pts) // 2][3])))


# ======================================================================================================
# the default layout (The Smiling Man): z grows away from the camera end
# ======================================================================================================
def make_layout(flicker_z=21.0):
    R, L = 1, -1
    P = [RoadSegment("road_main", Z_MIN, Z_MAX), Crosswalk("crosswalk_a", *CROSS),
         Manhole("manhole_a", 1.3, 2.0), Manhole("manhole_b", -1.4, 17.5), Manhole("manhole_c", 1.2, 33.0),
         StormDrain("drain_R1", ROAD - 0.23, 4.0, R), StormDrain("drain_L1", -ROAD + 0.23, 11.0, L), StormDrain("drain_R2", ROAD - 0.23, 24.5, R),
         StormDrain("drain_L2", -ROAD + 0.23, 36.0, L)]
    lamps_R = [StreetLight("lamp_R0", R, 1.5), StreetLight("lamp_R1", R, flicker_z, flicker=True), StreetLight("lamp_R2", R, 41.0),
               StreetLight("lamp_R3", R, 61.0)]
    lamps_L = [StreetLight("lamp_L0", L, 2.0), StreetLight("lamp_L1", L, 15.5), StreetLight("lamp_L2", L, 31.0), StreetLight("lamp_L3", L, 51.0),
               StreetLight("lamp_L4", L, 71.0)]
    P += [Sidewalk("sidewalk_R", R, Z_MIN, Z_MAX, [l.light for l in lamps_R]), Sidewalk("sidewalk_L", L, Z_MIN, Z_MAX, [l.light for l in lamps_L])]
    P += lamps_R + lamps_L
    P += [UtilityPole("upole_R1", R, 12.5, drum=True), UtilityPole("upole_R2", R, 31.0), UtilityPole("upole_R3", R, 50.0, drum=True),
          UtilityPole("upole_L1", L, 23.0), UtilityPole("upole_L2", L, 42.0, drum=True), UtilityPole("upole_L3", L, -6.0)]
    P += [VendingMachine("vend_R", R, 9.9), VendingMachine("vend_L", L, 18.6, body="#2c5a8a", band="#f0f0f0")]
    # right side buildings (camera end first)
    P += [Building("bld_R1", R, -30, -6, 4, "brick", [(-12, "door"), (-20, "shutter")], "cornice", 0.2, seed=1),
          # the opening's sidewalk: warm lit shopfronts so the hook has cosy pools
          Building("bld_R2", R, -6, 7.0, 3, "plaster", [(-2.0, "door"), (3.5, "shop")], "flat", 0.45, seed=2),
          Building("bld_R3", R, 7.0, 16.0, 2, "green", [(13.4, "shop")], "cornice", 0.5, seed=3),
          Alley("alley_R1", R, 16.0, 18.0),
          Building("bld_R4", R, 18.0, 33.0, 5, "concrete", [(21.5, "lobby"), (28.5, "blank")], "tank", 0.18, seed=4, fire_escape=True),
          Building("bld_R5", R, 33.0, 45.0, 3, "brick_red", [(36.5, "door"), (41.5, "shop")], "cornice", 0.22, seed=5),
          Alley("alley_R2", R, 45.0, 47.0),
          Building("bld_R6", R, 47.0, 68.0, 4, "stone", [(52.0, "door"), (60.0, "shutter")], "setback", 0.2, seed=6),
          Building("bld_R7", R, 68.0, Z_MAX, 6, "concrete", [], "flat", 0.15, seed=7)]
    # left side
    P += [Building("bld_L1", L, -30, -2.0, 3, "stone", [(-8, "door"), (-18, "shutter")], "cornice", 0.2, seed=11),
          Building("bld_L2", L, -2.0, 10.5, 2, "brick_red", [(1.2, "shop"), (7.4, "door")], "flat", 0.35, seed=12),
          Building("bld_L3", L, 10.5, 14.5, 3, "plaster", [(12.5, "door")], "cornice", 0.25, seed=13),
          Alley("alley_L1", L, 14.5, 16.5),
          Building("bld_L4", L, 16.5, 29.0, 4, "brick", [(20.8, "blank"), (25.0, "door")], "tank", 0.2, seed=14, fire_escape=True),
          Alley("alley_L2", L, 29.0, 30.8),
          Building("bld_L5", L, 30.8, 49.0, 5, "concrete", [(35.0, "lobby"), (43.0, "shutter")], "setback", 0.17, seed=15),
          Building("bld_L6", L, 49.0, Z_MAX, 3, "brick_red", [(55.0, "door"), (63.0, "shop")], "cornice", 0.2, seed=16)]
    P += [Fence("fence_alley_R1", R, 16.0, 18.0, gate_open=0.7), Fence("fence_alley_L1", L, 14.5, 16.5),
          Fence("fence_alley_L2", L, 29.0, 30.8, gate_open=0.6),
          Fence("railing_L3", L, 10.7, 11.9, xpos=FACADE - 0.6, h=0.9, style="iron"),
          Fence("railing_L3b", L, 13.1, 14.3, xpos=FACADE - 0.6, h=0.9, style="iron")]
    return P


def default_wires():
    """Sagging wires pole to pole on each side, and two spans across the street."""
    poles = {1: [12.5, 31.0, 50.0], -1: [-6.0, 23.0, 42.0]}
    runs = []
    for s, zs in poles.items():
        for za, zb in zip(zs, zs[1:]):
            for dx, y in ((-0.6, 7.78), (0.4, 7.78), (0.0, 7.0)):
                runs.append(((s * (ROAD + 0.3) + dx, y, za), (s * (ROAD + 0.3) + dx, y, zb), 0.6))
    runs.append(((ROAD + 0.3, 7.0, 12.5), (-ROAD - 0.3, 7.0, 23.0), 0.4))
    runs.append(((ROAD + 0.3, 7.6, 31.0), (-ROAD - 0.3, 7.6, 42.0), 0.45))
    runs.append(((ROAD + 0.3, 7.2, 12.5), (FACADE + 0.5, 6.0, 9.0), 0.2))          # service drop to a building
    return runs


def default_fog():
    return [(x, z, r) for z in np.arange(-6, 80, 5.0) for x, r in ((-2.6, 3.4), (2.4, 3.0))] + [(0.0, z, 4.5) for z in np.arange(20, 90, 9.0)]


def default_street(flicker_z=21.0):
    return CityStreet(make_layout(flicker_z), default_wires(), default_fog())


# ======================================================================================================
# asset sheet + manifest
# ======================================================================================================
if __name__ == "__main__":
    import sys

    from PIL import Image, ImageDraw

    from toon import Camera, Frame

    args = sys.argv[1:]
    st = default_street()
    if "--manifest" in args:
        out = args[args.index("--manifest") + 1]
        json.dump(st.manifest(), open(out, "w"), indent=1)
        print("wrote", out, len(st.pieces), "pieces")
    if "--sheet" in args:
        out = args[args.index("--sheet") + 1]

        def aimc(pos, tgt, f, hz=0.46):
            return Camera(pos, math.degrees(math.atan2(tgt[0] - pos[0], tgt[2] - pos[2])), f, hz)
        views = [("wide down the street (both sidewalks)", aimc((0.0, 3.2, -6.0), (0.0, 2.0, 20.0), 900)),
                 ("right sidewalk, eye level", aimc((2.0, 1.3, 2.0), (4.3, 1.1, 14.0), 1000)),
                 ("left sidewalk + corner store", aimc((-1.0, 1.2, -1.0), (-4.4, 1.2, 8.0), 900)),
                 ("crosswalk from the curb", aimc((3.9, 1.0, 4.0), (-2.0, 0.2, 8.5), 850)),
                 ("alley + fence (left)", aimc((-1.0, 1.4, 13.0), (-9.0, 1.6, 15.6), 900)),
                 ("vending + lamps (right)", aimc((1.2, 1.3, 6.5), (5.0, 1.1, 10.0), 1100)),
                 ("high wide, escape depth", aimc((-1.5, 6.5, -10.0), (0.0, 1.0, 40.0), 1100)),
                 ("reverse, toward the camera end", aimc((0.5, 1.6, 30.0), (0.0, 1.4, 0.0), 900))]
        tiles = []
        for lab, cam in views:
            fr = Frame(0.4)
            st.bg(fr, cam, 1.0)
            for _, fn, _ in sorted(st.items(cam, 1.0), key=lambda q: -q[0]):
                fn(fr)
            st.rain(fr, cam, 1.0)
            st.night(fr, cam, 1.0)
            im = Image.fromarray(fr.array())
            d = ImageDraw.Draw(im)
            d.rectangle((0, im.height - 24, im.width, im.height), fill=(0, 0, 0))
            d.text((6, im.height - 19), lab, fill=(255, 255, 0))
            tiles.append(im)
        w, h = tiles[0].size
        sheet = Image.new("RGB", (4 * w + 3 * 12, 2 * h + 12), (40, 40, 40))
        for i, t in enumerate(tiles):
            sheet.paste(t, ((i % 4) * (w + 12), (i // 4) * (h + 12)))
        sheet.save(out)
        print("wrote", out)
