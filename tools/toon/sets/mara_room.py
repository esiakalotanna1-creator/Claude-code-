"""MARA ROOM: Timmy's gamer bedroom at night for the Mara reel, built on sets/gamer_room.py, kept as a
kit set. Adds:
    Door          right wall: panelled door, a poster on it, warm hallway light leaking under it onto the floor
    Aircon        split unit high on the left wall above the bed: louvres, green standby LED, the draught shows on the curtain hem and a peeling poster corner
    ConsoleCabinet  low cabinet beside the desk with the console standing on it, cables to the wall (props/console.py);
                  .present = False once it is stolen (the scene draws it in the thief's arms)
    SleepBed      the bed made up for a sleeper: smooth duvet pulled up to the pillow, the weight dents of whatever
                  squats on it (.dents = [(x, z, r, depth)]) with the duvet creased tight between them; the duvet
                  is its own item ("bed_duvet") so the scene can lay the sleeper under it and the Mara on top
The monitors are asleep (dark glass, a faint standby glow); the PC keeps its purple glow; rain on the window.

    py -m sets.mara_room --sheet <png>       room views + the new pieces close up
"""
import math

import skia

from props import console, tv
import rig
from rig import Basis
from sets.gamer_room import (ROOM_X, ROOM_Z, Bed, BedsideTable, Bin, Corkboard, Desk, DeskClutter, Drawers,
                             FloorClutter, GamerRoom, GamingChair, Headset, HexPanels, Jersey, Keyboard, KeyLight,
                             LaundryBasket, Light, MicArm, Monitor, NeonSign, PC, Piece, Poster, Shell, Wardrobe,
                             WallShelves, Webcam, Window, Backpack, ControllerDock, blob, quad_x, wglow, wline, wpath,
                             aimc)
from toon import paint, shade

DOOR_Z0, DOOR_Z1, DOOR_H = 0.15, 0.97, 2.02


class Door(Piece):
    """Panelled door on the right wall, closed; the hallway light is on: a bright line under it and a warm fan of light
    across the floorboards."""
    kind = "wall"

    def __init__(self, name="door", z0=DOOR_Z0, z1=DOOR_Z1):
        super().__init__(name, ROOM_X, (z0 + z1) / 2)
        self.z0, self.z1 = z0, z1
        self.size = (0.06, DOOR_H, z1 - z0)

    def bg(self, fr, cam, T):
        X, z0, z1 = ROOM_X - 0.004, self.z0, self.z1
        trim, slab = "#d9d4c8", "#5d4a3a"
        fr.poly(cam, quad_x(z0 - 0.07, z1 + 0.07, 0.0, DOOR_H + 0.07, X, -1), colr=trim, outline=shade(trim, -0.6), line=1.2)
        fr.poly(cam, quad_x(z0, z1, 0.012, DOOR_H, X - 0.006, -1), colr=slab, outline=shade(slab, -0.65), line=1.3)
        for a, b, y0, y1 in ((0.08, 0.46, 1.12, 1.9), (0.54, 0.92, 1.12, 1.9), (0.08, 0.46, 0.12, 0.98), (0.54, 0.92, 0.12, 0.98)):
            za, zb = z0 + (z1 - z0) * a, z0 + (z1 - z0) * b
            fr.poly(cam, quad_x(za, zb, y0, y1, X - 0.009, -1), colr=shade(slab, -0.08), outline=shade(slab, -0.5), line=1.0)
            wline(fr, cam, (X - 0.01, y1, za), (X - 0.01, y1, zb), shade(slab, 0.25), 0.006, 0.6)
        # handle + lock plate on the far edge
        hz = z1 - 0.07
        fr.box(cam, (X - 0.02, X - 0.008), (0.98, 1.1), (hz - 0.02, hz + 0.02), "#b9b2a0", line=1.0)
        fr.box(cam, (X - 0.08, X - 0.02), (1.02, 1.04), (hz - 0.015, hz + 0.015), "#cfc8b4", line=1.0)
        # a poster stuck on the door, slightly crooked
        Poster("door_poster", "right", z0 + 0.2, z1 - 0.22, 1.24, 1.82, "anime_eyes", tilt=-0.01).bg(fr, cam, T)
        # the hallway light under the door: a hot line and a warm fan on the boards (flickers a touch)
        fl = 1.0 + 0.03 * math.sin(T * 13.0)
        wline(fr, cam, (X - 0.006, 0.006, z0 + 0.02), (X - 0.006, 0.006, z1 - 0.02), "#ffd9a0", 0.012, 0.95)
        fr.ground_ellipse(cam, X - 0.25, (z0 + z1) / 2, 0.42, (z1 - z0) * 0.55, "#ffb060", 0.30 * fl, blur_m=0.18, y=0.004, add=True)
        fr.ground_ellipse(cam, X - 0.06, (z0 + z1) / 2, 0.08, (z1 - z0) * 0.5, "#ffd9a0", 0.45 * fl, blur_m=0.04, y=0.005, add=True)

    def lights(self):
        return [Light(self.name, (ROOM_X - 0.3, 0.05, (self.z0 + self.z1) / 2), "#ffb060", 0.9, 0.5)]

    def solid(self):
        return ((ROOM_X - 0.06, ROOM_X), (0.0, DOOR_H), (self.z0, self.z1))


class Aircon(Piece):
    """Wall-mounted split aircon high on the left wall: white casing, louvre slot, green standby LED, a faint cold
    draught drifting down over the bed (the hum is in the ambience)."""
    kind = "wall"

    def __init__(self, name="aircon", z0=1.25, z1=2.1, y0=2.06, y1=2.34):
        super().__init__(name, -ROOM_X, (z0 + z1) / 2, y0)
        self.z0, self.z1, self.y0, self.y1 = z0, z1, y0, y1
        self.size = (0.24, y1 - y0, z1 - z0)

    def bg(self, fr, cam, T):
        X, z0, z1, y0, y1 = -ROOM_X, self.z0, self.z1, self.y0, self.y1
        fr.box(cam, (X, X + 0.22), (y0, y1), (z0, z1), "#d6dae2", line=1.3)
        fr.box(cam, (X + 0.17, X + 0.225), (y0, y0 + 0.05), (z0 + 0.04, z1 - 0.04), "#3a3e48", line=1.0)       # louvre slot
        for i in range(5):
            zz = z0 + 0.08 + (z1 - z0 - 0.16) * i / 4
            wline(fr, cam, (X + 0.226, y0 + 0.005, zz), (X + 0.226, y0 + 0.045, zz), "#8a8e98", 0.004, 0.8)
        wline(fr, cam, (X + 0.222, y1 - 0.06, z0 + 0.02), (X + 0.222, y1 - 0.06, z1 - 0.02), "#b0b4be", 0.004, 0.7)
        led = (X + 0.222, y0 + 0.08, z1 - 0.07)
        wglow(fr, cam, led, 0.05, "#5aff8a", 0.7)
        wglow(fr, cam, led, 0.012, "#d8ffe0", 0.9)
    def solid(self):
        return ((-ROOM_X, -ROOM_X + 0.22), (self.y0, self.y1), (self.z0, self.z1))


class TVBench(Piece):
    """Low media bench against the front wall at the foot of the bed, the TV on it facing the bed (the Mara carries it
    off at 9.6 s: `present` False leaves the bench bare with the cable lying loose)."""

    def __init__(self, name="tv", x=0.45, z=0.19, top=0.22):
        super().__init__(name, x, z)
        self.present, self.top = True, top

    def tv_origin(self):
        return (self.x, self.top, self.z - 0.02)

    def item(self, cam, T):
        x, z, top = self.x, self.z, self.top

        def fn(fr):
            wood = "#6a4e3a"
            fr.box(cam, (x - 0.4, x + 0.4), (0.04, top), (z - 0.17, z + 0.17), wood, line=1.3)
            for dx in (-0.36, 0.36):
                fr.box(cam, (x + dx - 0.03, x + dx + 0.03), (0.0, 0.04), (z - 0.14, z + 0.14), shade(wood, -0.4), line=1.0)
            fr.box(cam, (x - 0.36, x - 0.02), (0.07, top - 0.03), (z + 0.17, z + 0.171), shade(wood, -0.15), line=1.0)
            fr.box(cam, (x + 0.02, x + 0.36), (0.07, top - 0.03), (z + 0.17, z + 0.171), shade(wood, -0.15), line=1.0)
            if self.present:
                tv.draw(fr, cam, self.tv_origin(), Basis.yaw(180), t=T, light=(0.0, 1.6, 1.8))
            else:                                                # a clean rectangle in the dust, the cable dropped
                o = self.tv_origin()
                fr.poly(cam, [(o[0] - 0.24, top + 0.001, o[2] - 0.05), (o[0] + 0.24, top + 0.001, o[2] - 0.05),
                              (o[0] + 0.24, top + 0.001, o[2] + 0.05), (o[0] - 0.24, top + 0.001, o[2] + 0.05)], colr=shade(wood, 0.12))
                wpath(fr, cam, [(x + 0.1, top + 0.005, z - 0.1), (x + 0.2, top + 0.005, z + 0.05), (x + 0.32, 0.01, z + 0.25)], "#141418", 0.008)
        return self.it(cam, fn, (x, 0.2, z))

    def solid(self):
        return ((self.x - 0.4, self.x + 0.4), (0.0, self.top + (tv.FOOT + tv.PH if self.present else 0.0)), (self.z - 0.17, self.z + 0.17))


class DoorRug(Piece):
    """Small round rug in front of the door (the TV lands on it)."""
    kind = "floor"

    def __init__(self, name="door_rug", x=1.18, z=0.66, rx=0.5, rz=0.4):
        super().__init__(name, x, z)
        self.rx, self.rz = rx, rz

    def bg(self, fr, cam, T):
        for k, (s, col) in enumerate(((1.0, "#5a3a4a"), (0.8, "#6e4a5a"), (0.45, "#5a3a4a"))):
            pts = [(self.x + self.rx * s * math.cos(a * math.pi / 12), 0.003 + 0.0005 * k, self.z + self.rz * s * math.sin(a * math.pi / 12))
                   for a in range(24)]
            fr.poly(cam, pts, colr=col, outline=shade(col, -0.45), line=1.0)


class ConsoleCabinet(Piece):
    """Low white cabinet beside the desk; the console stands on it, cables down the back to a wall socket."""
    size = (0.4, 0.35 + console.H, 0.36)

    def __init__(self, name="console", x=1.13, z=3.32, top=0.35):
        super().__init__(name, x, z)
        self.present = True
        self.top = top                                           # > 0.4: stands on the desk, no cabinet

    def console_origin(self):
        return (self.x, self.top, self.z - 0.02)

    def item(self, cam, T):
        x, z, top = self.x, self.z, self.top

        def fn(fr):
            if top < 0.4:
                fr.box(cam, (x - 0.2, x + 0.2), (0.0, top), (z - 0.18, z + 0.18), "#e4e2dc", line=1.3)
                fr.box(cam, (x - 0.17, x + 0.17), (0.05, top - 0.05), (z - 0.181, z - 0.17), "#cfccc4", line=1.0)
            # wall socket + plug behind
            fr.box(cam, (x - 0.05, x + 0.05), (0.25, 0.33), (ROOM_Z - 0.012, ROOM_Z), "#e8e6e0", line=1.0)
            if self.present:
                console.draw(fr, cam, self.console_origin(), Basis.yaw(0), t=T, light=(0.0, 1.6, 2.4), cables=0.0)
                wpath(fr, cam, [(x - 0.01, top + 0.06, z + 0.11), (x - 0.02, top + 0.02, z + 0.2), (x - 0.03, 0.31, ROOM_Z - 0.02)], "#141418", 0.009)
                wpath(fr, cam, [(x + 0.015, top + 0.08, z + 0.11), (x - 0.1, top + 0.03, z + 0.15), (x - 0.3, top + 0.01, ROOM_Z - 0.03)], "#1d1e24", 0.008)  # HDMI to the monitor
            else:                                                # stolen: dust outline where it stood, cables pulled loose
                o = self.console_origin()
                fr.poly(cam, [(o[0] - 0.05, top + 0.001, o[2] - 0.12), (o[0] + 0.05, top + 0.001, o[2] - 0.12),
                              (o[0] + 0.05, top + 0.001, o[2] + 0.12), (o[0] - 0.05, top + 0.001, o[2] + 0.12)], colr="#f2f0ea")
                wpath(fr, cam, [(x - 0.03, 0.31, ROOM_Z - 0.02), (x + 0.02, 0.2, z + 0.1), (x + 0.1, 0.01, z - 0.15)], "#141418", 0.009)
        return self.it(cam, fn, (x, 0.3, z))

    def solid(self):
        return ((self.x - 0.2, self.x + 0.2), (0.0, self.top + (console.H if self.present else 0.0)), (self.z - 0.18, self.z + 0.18))

    def lights(self):
        return [Light(self.name, (self.x, self.top + 0.2, self.z - 0.2), "#4f8dff", 0.45, 0.3)] if self.present else []


def soft(fr, cam, c, r, colr, e=0.35, line=1.3, light=(0.4, 1.0), lit=0.25, dark=0.35):
    """A soft rounded 3D lump (pillow, rolled sheet, duvet slab): the projected hull of a superellipsoid at world
    centre c with radii r; e < 1 squares it off (0.3 = cushion, 1 = egg). Correct silhouette from any camera."""
    f = lambda v: math.copysign(abs(v) ** e, v)  # noqa: E731
    pts = []
    for i in range(9):
        th = -math.pi / 2 + math.pi * i / 8
        for j in range(16):
            ph = 2 * math.pi * j / 16
            pts.append(cam.proj((c[0] + r[0] * f(math.cos(th)) * f(math.cos(ph)), c[1] + r[1] * f(math.sin(th)),
                                 c[2] + r[2] * f(math.cos(th)) * f(math.sin(ph)))))
    pts = [q for q in pts if q[2] > 0.12]
    if len(pts) < 8:
        return None
    hull = rig.smooth(rig._hull([q[:2] for q in pts]), k=0.5)
    k0 = cam.proj(c)[3]
    fr.part(hull, colr, light, width=0.6 * min(r) * k0, line=line, lit=lit, dark=dark)
    return hull


class SleepBed(Bed):
    """The bed made for sleeping: smooth navy duvet up to the pillows, turned down at the top, and dents where weight
    presses into it (.dents, world x/z, radius, depth) with the cover pulled into tight creases between them."""

    def __init__(self, name="bed", **kw):
        super().__init__(name, **kw)
        self.dents = []
        self.lump = None                                         # (x, z0, z1): the sleeper's body under the duvet
        self.under, self.over = [], []                           # scene hooks: fn(fr) drawn under / over the duvet
        self.fold = 0.0                                          # 0 = up to his shoulders .. 1 = slid down to his lap
        self.pillows = False                                     # one soft pillow instead of the base's two flat blobs
        self.head = None                                         # (x, z) of a head pressed into the pillow
        self.mattress = "#3c4258"                                 # sheet seen at the uncovered foot end: dim, not a white slab

    def edge(self):
        """z of the duvet's turned-down top edge."""
        up = self.z1 - 0.5                                       # turned down below his shoulders
        return up - self.fold * (up - 1.75)

    def mound_top(self, z):
        """Height of the duvet over the sleeper at z (where a sitter's feet rest)."""
        top = 0.59
        if not self.lump or not (self.lump[1] <= z <= min(self.lump[2], self.edge())):
            return top
        u = (z - self.lump[1]) / (self.lump[2] - self.lump[1])
        return top + 0.05 + 0.1 * u ** 0.7

    def item(self, cam, T):
        x0, x1, z0, z1 = self.x0, self.x1, self.z0, self.z1
        top = 0.5
        base_fn = [it for it in super().item(cam, T) if it[2].endswith("_base")][0][1]

        def pillow(fr):
            """One plump pillow; with a head on it the middle is pressed down between two raised lobes."""
            px, pz = (self.head if self.head else ((x0 + x1) / 2, z1 - 0.22))
            pc = "#c3c8d6"
            if not self.head:
                soft(fr, cam, (px, top + 0.08, pz), (0.32, 0.075, 0.15), pc, e=0.3)
                return
            soft(fr, cam, (px, top + 0.05, pz + 0.01), (0.3, 0.05, 0.15), shade(pc, -0.12), e=0.3)    # the pressed middle
            for g in (-1, 1):                                    # the lobes bulging up either side of his head
                soft(fr, cam, (px + g * 0.2, top + 0.085, pz), (0.11, 0.065, 0.14), pc, e=0.45)
            q = cam.proj((px, top + 0.1, pz))
            if q[2] > 0.15:                                      # the hollow's soft shadow and a couple of pulled creases
                k = q[3]
                fr.c.drawOval(skia.Rect(q[0] - 0.13 * k, q[1] - 0.03 * k, q[0] + 0.13 * k, q[1] + 0.04 * k), paint("#262a38", a=0.35, blur=0.03 * k))
                for g in (-1, 1):
                    a0, a1 = cam.proj((px + g * 0.1, top + 0.09, pz + 0.05)), cam.proj((px + g * 0.2, top + 0.13, pz + 0.1))
                    if min(a0[2], a1[2]) > 0.15:
                        fr.c.drawLine(a0[0], a0[1], a1[0], a1[1], paint("#7c8296", stroke=0.005 * k, a=0.6, blur=0.002 * k))

        def duvet(fr):
            base_fn(fr)                                          # frame first, always under the duvet
            if min(cam.view((xx, top, zz))[2] for xx in (x0, x1) for zz in (z0, z1)) > 0.35:
                soft(fr, cam, ((x0 + x1) / 2, top - 0.065, (z0 + z1) / 2), ((x1 - x0) / 2 - 0.005, 0.075, (z1 - z0) / 2 - 0.03),
                     "#9ea4b2", e=0.16, line=1.2)                # sheeted mattress: rounded edges, not a slab
            pillow(fr)
            for fn in self.under:                                # the sleeper, under the cover
                fn(fr)
            dv = "#26304f"
            h = 0.09
            edge = self.edge()
            c = fr.c
            near = 0.0 if (x0 < cam.pos[0] < x1 + 0.1 and z0 < cam.pos[2] < z1) else 1.0   # lens over the bed = his own POV
            if near > 0.35:                                      # seen from outside the bed: a soft slab with thickness
                zc, zr = (z0 - 0.02 + edge) / 2, (edge - z0 + 0.02) / 2
                drape = [(x1 + 0.035, top + h - 0.005, z0 + 0.02 + (edge - z0 - 0.04) * i / 14) for i in range(15)]
                hem = [(x1 + 0.05, top - 0.13 + 0.02 * math.sin(i * 1.9) + 0.012 * math.sin(i * 4.3),
                        z0 + 0.02 + (edge - z0 - 0.04) * i / 14) for i in range(15)]
                fr.poly(cam, drape + hem[::-1], colr=shade(dv, -0.15), outline=shade(dv, -0.6), line=1.2)   # hanging over the side
                soft(fr, cam, ((x0 + x1) / 2 + 0.02, top + h / 2 - 0.02, zc), ((x1 - x0) / 2 + 0.03, h / 2 + 0.035, zr), dv, e=0.18, line=1.4)
                if self.fold < 0.3:
                    soft(fr, cam, ((x0 + x1) / 2 + 0.02, top + h + 0.012, edge - 0.05), ((x1 - x0) / 2 + 0.02, 0.028, 0.055), "#c9cdd8",
                         e=0.45, line=1.0)                       # turned-down sheet: a soft rolled edge
                else:                                            # thrown back: the cover heaped where it was pushed to
                    soft(fr, cam, ((x0 + x1) / 2 + 0.02, top + h + 0.05 * self.fold, edge + 0.1), ((x1 - x0) / 2 - 0.03, 0.05 + 0.08 * self.fold, 0.2),
                         shade(dv, 0.08), e=0.3, line=1.3)
            else:                                                # the sleeper's own POV: the plain boxes clip cleanly at the lens
                fr.box(cam, (x0 + 0.01, x1 + 0.03), (top - 0.1, top + h), (z0 - 0.02, edge), dv, line=1.4)
                fr.box(cam, (x0 + 0.01, x1 + 0.03), (top + h - 0.01, top + h + 0.015), (edge - 0.12, edge), "#c9cdd8", line=1.0)
            y = top + h + 0.002
            if self.lump:                                        # the sleeper under the cover: a body-shaped mound
                lx, la, lb = self.lump
                lb = min(lb, edge)
                pts = []
                for i in range(13):
                    u = i / 12
                    zz = la + (lb - la) * u
                    ry = 0.05 + 0.1 * u ** 0.7                   # shins low, chest high
                    rx = 0.11 + 0.08 * u
                    for j in range(9):
                        a = math.pi * j / 8
                        pts.append(cam.proj((lx + rx * math.cos(a), y + ry * math.sin(a), zz)))
                pts = [q for q in pts if q[2] > 0.12]           # the sleeper's own POV: the near end is under the lens
                if len(pts) > 8:
                    hull = rig.smooth(rig._hull([q[:2] for q in pts]), k=0.6)
                    k0 = pts[len(pts) // 2][3]
                    fr.part(hull, shade(dv, 0.1), (0.4, 1.0), width=0.25 * k0, line=1.3, lit=0.35, dark=0.45)
                    groove = [cam.proj((lx, y + 0.05 + 0.1 * (0.42 * i / 8) ** 0.7 - 0.012, la + (lb - la) * 0.42 * i / 8)) for i in range(9)]
                    if min(q[2] for q in groove) > 0.12:         # the gap between his two legs under the cover
                        c.drawPath(rig.smooth([q[:2] for q in groove], closed=False), paint(shade(dv, -0.55), stroke=0.012 * k0, a=0.5, blur=0.008 * k0))
                    ridge = [cam.proj((lx + 0.03, y + 0.05 + 0.1 * (i / 8) ** 0.7, la + (lb - la) * i / 8)) for i in range(9)]
                    c.drawPath(rig.smooth([q[:2] for q in ridge], closed=False),
                               paint(shade(dv, 0.45), stroke=0.015 * k0, a=0.3, blur=0.01 * k0))
            pts = []
            for dx, dz, r, d in self.dents:                      # weight: soft hollows with a lit lip
                p = cam.proj((dx, y + 0.002, dz))
                if p[2] < 0.15:
                    continue
                s = p[3]
                pts.append(p)
                c.drawOval(skia.Rect(p[0] - r * s, p[1] - r * s * 0.4, p[0] + r * s, p[1] + r * s * 0.4),
                           paint("#05060c", a=min(0.55, 3 * d), blur=0.35 * r * s))
                c.drawArc(skia.Rect(p[0] - r * s * 1.15, p[1] - r * s * 0.5, p[0] + r * s * 1.15, p[1] + r * s * 0.45), 200, 140,
                          False, paint(shade(dv, 0.3), stroke=0.01 * s, a=0.45, blur=0.006 * s))
            # (no pulled creases between the hollows: they fanned out under a sitter's feet like a glitch)
            for fn in self.over:                                 # whatever sits on the bed
                fn(fr)
        mid = ((x0 + x1) / 2, 0.3, (z0 + z1) / 2 - 0.2)
        return [(cam.view(mid)[2], duvet, self.name + "_duvet")]


class FrontWall(Piece):
    """The fourth wall (z = Z0, facing the desk), only drawn when the camera is inside the room looking toward it
    (Timmy's POV from the pillow): a light switch, a calendar, the skirting."""
    kind = "wall"
    Z0 = -0.45

    def __init__(self, name="front_wall"):
        super().__init__(name, 0.0, self.Z0)

    def bg(self, fr, cam, T):
        if cam.pos[2] < self.Z0 + 0.05:
            return
        from sets.gamer_room import ROOM_H, WALL, quad_z
        Z = self.Z0
        fr.poly(cam, [(ROOM_X, 0, Z), (-ROOM_X, 0, Z), (-ROOM_X, ROOM_H, Z), (ROOM_X, ROOM_H, Z)], colr=shade(WALL, -0.08))
        fr.poly(cam, [(ROOM_X, 0, Z + 0.004), (-ROOM_X, 0, Z + 0.004), (-ROOM_X, 0.1, Z + 0.004), (ROOM_X, 0.1, Z + 0.004)], colr="#1b1c2c")
        fr.poly(cam, quad_z(-1.2, -1.12, 1.15, 1.27, Z + 0.006), colr="#d8d6ce", outline="#6a6a70", line=1.0)     # switch
        fr.poly(cam, quad_z(-0.6, -0.1, 1.2, 1.75, Z + 0.006), colr="#e8e4da", outline="#5a5a62", line=1.0)      # calendar
        fr.poly(cam, quad_z(-0.6, -0.1, 1.6, 1.75, Z + 0.007), colr="#c0413a")


class PosterCorner(Piece):
    """The bottom corner of a side-wall poster come unstuck, lifting and falling in the aircon draught."""
    kind = "wall"

    def __init__(self, name, poster, size=0.09):
        super().__init__(name, poster.x, poster.z, poster.y0)
        self.p, self.size_m = poster, size

    def bg(self, fr, cam, T):
        P, d = self.p, self.size_m
        X = -ROOM_X + 0.007 if P.wall == "left" else ROOM_X - 0.007
        sg = 1 if P.wall == "left" else -1
        a, b, cnr = (X, P.y0 + d, P.a1), (X, P.y0, P.a1 - d), (X, P.y0, P.a1)
        lift = 0.5 + 0.35 * math.sin(T * 2.3) + 0.15 * math.sin(T * 5.1)
        m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)
        tip = (X + sg * 0.06 * lift, m[1] + (cnr[1] - m[1]) * (1 - lift), m[2] + (cnr[2] - m[2]) * (1 - lift))
        fr.poly(cam, [a, b, cnr], colr=shade("#272942", 0.05))                # bare wall where it peeled
        fr.poly(cam, [a, b, tip], colr="#e6e2d8", outline="#7a7a80", line=1.0)  # the white back of the paper


def make_layout():
    main = Monitor("monitor_main", -0.08, 3.38, "h", None, glow="#2a3a7a")
    side = Monitor("monitor_vertical", 0.5, 3.36, "v", None, glow="#2a3a7a")
    band = Poster("poster_band", "left", 0.15, 0.6, 1.35, 1.95, "band", tilt=0.012)
    win = Window("window", -1.98, -1.08, gap_x=-1.53, gap=0.24)       # wide enough to fly two demons through
    win.sway = 1.0
    return [Shell(), FrontWall(),
            win,
            Door(), Aircon(),
            Poster("poster_level_up", "back", -0.96, -0.6, 1.42, 2.0, "level_up"),
            band, PosterCorner("poster_band_corner", band),
            Poster("poster_lofi", "back", 0.98, 1.36, 1.82, 2.3, "lofi"),
            Corkboard("corkboard", 0.98, 1.36, 1.12, 1.68),
            NeonSign("neon_gg", 0.47, 1.98, 0.42),
            HexPanels("hex_panels", -0.42, 1.7, 0.1),
            Jersey("jersey", "left", 0.4, 1.0),
            Desk(), main, side, Webcam("webcam", main), PC("pc", -0.64, 3.3), Keyboard("keyboard", -0.06, 3.1),
            Headset("headset", 0.98, 3.0), MicArm("mic_arm"), KeyLight("key_light"), ControllerDock("controller_dock", 0.36, 3.12),
            DeskClutter(),
            GamingChair("chair", -0.2, 1.25),
            SleepBed("bed"), BedsideTable("bedside"),
            Wardrobe("wardrobe"), Drawers("drawers"), WallShelves("shelves"),
            ConsoleCabinet("console", 0.84, 3.4, top=0.74),
            TVBench("tv"), DoorRug(),
            # basket + bin in the front-left corner by the bed's foot: the floor from the TV to the door stays clear
            LaundryBasket("laundry", -1.45, 0.3), Bin("bin", -1.85, 0.35), Backpack("backpack", -1.05, 2.95, colr="#b8322e"),
            FloorClutter(trainers=None, socks=((0.3, 0.95, 20.0), (-0.25, 2.0, 140.0), (0.75, 1.5, 290.0)))]


def room():
    return GamerRoom(make_layout())


if __name__ == "__main__":
    import sys

    from PIL import Image, ImageDraw

    from toon import Frame
    args = sys.argv[1:]
    R = room()
    R.by_name["bed"].dents = [(-1.5, 1.85, 0.07, 0.06), (-1.62, 1.95, 0.07, 0.06), (-1.42, 2.05, 0.06, 0.05)]
    R.by_name["bed"].lump = (-1.52, 1.25, 2.3)

    def shot(cam, T=1.6, lab=None):
        fr = Frame(0.4)
        R.draw_all(fr, cam, T)
        im = Image.fromarray(fr.array())
        if lab:
            d = ImageDraw.Draw(im)
            d.rectangle((0, im.height - 24, im.width, im.height), fill=(0, 0, 0))
            d.text((6, im.height - 19), lab, fill=(255, 255, 0))
        return im
    views = [("wide from the front", aimc((0.35, 1.45, -0.6), (0.0, 1.0, 3.6), 620)),
             ("bed side", aimc((0.9, 1.4, 0.0), (-1.6, 0.8, 2.2), 700)),
             ("door side", aimc((-0.9, 1.4, 0.4), (2.0, 0.9, 0.6), 650)),
             ("bed close (dents)", aimc((-0.6, 1.5, 0.9), (-1.55, 0.5, 1.9), 1100)),
             ("aircon", aimc((-0.6, 1.6, 0.6), (-2.0, 2.2, 1.7), 1100)),
             ("pov from the pillow", aimc((-1.52, 0.72, 2.4), (-1.52, 1.2, 0.0), 700)),
             ("console cabinet", aimc((0.3, 1.25, 2.2), (0.84, 0.9, 3.4), 1300))]
    tiles = [shot(cam, lab=lab) for lab, cam in views]
    w, h = tiles[0].size
    sheet = Image.new("RGB", (len(tiles) * w + (len(tiles) - 1) * 12, h), (40, 40, 40))
    for i, t in enumerate(tiles):
        sheet.paste(t, (i * (w + 12), 0))
    out = args[args.index("--sheet") + 1] if "--sheet" in args else "mara_room.png"
    sheet.save(out)
    print("wrote", out)
