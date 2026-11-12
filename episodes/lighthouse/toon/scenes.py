"""THE LIGHT AT SEA: one lantern room, one keeper. World units are metres, y up; cameras may look any way.

    x -2 .. 2, z -3 .. 3, floor y = 0, ceiling 2.6.
    Right wall (x = 2): the big window onto the sea.   Back-right corner: the great lamp on its pedestal.
    Ned stands at (0.1, 1.5) facing right (yaw 80), a desk in front of him: the lever that fires the lamp, the
    logbook, an oil lamp.

Everything is a function of T. Light, three layers: the cool night room, a soft key on his face (the oil lamp,
warmer when the great lamp fires, cold when the light at sea flashes), and the warm practicals.
"""
import math
import os
import sys

import skia

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
for _d in (HERE, os.path.join(ROOT, "tools", "toon")):
    if _d not in sys.path:
        sys.path.insert(0, _d)
import rig  # noqa: E402
import looks  # noqa: E402,F401  (registers the cast)
from anim import HOLD, Track, blink  # noqa: E402
from toon import argb, lin, rad, shade  # noqa: E402

RX, RZ, RH = 2.0, 3.0, 2.6
XW = 1.995                                         # the window plane (right wall)
WIN = ((0.2, 1.8), (0.85, 2.15))                   # window: z span, y span
HORIZON = 1.30                                     # the sea's horizon on the window plane
DESK = ((0.50, 1.10), (0.0, 0.92), (1.10, 2.00))   # x, y, z spans
LAMPBOX = ((1.30, 1.80), (0.0, 1.70), (2.10, 2.60))  # pedestal + lens: x, y, z
LAMPC = (1.55, 1.30, 2.35)                         # the great lamp's centre
OIL = (0.92, 1.12, 1.18)                           # the oil lamp's flame
LEVER_BASE = (0.56, 0.98, 1.35)
NED = (0.14, 1.52, 80.0)                           # x, z, yaw (yaw 90 faces +x)
WALL, FLOOR, WARM, COLD = "#262e4a", "#3a3340", "#ffcf8a", "#cfe6ff"

# when the great lamp flashes (3 = the nightly ritual, then his answers, then the last three by themselves)
LAMP = [1.7, 2.3, 2.9, 11.9, 12.4, 14.6, 38.0, 38.6, 39.2]
PRESS = LAMP[:6]                                   # ...pulled by hand. The last three nobody pulls.
# when the light at sea flashes
SEA = [5.6, 6.2, 6.8, 8.6, 9.2, 9.8, 12.95, 13.45, 15.15, 16.6, 18.0, 19.4, 22.0, 24.2, 26.4, 28.9, 31.6,
       35.0, 35.6, 36.2]


def win(T, a, b):
    u = min(1.0, max(0.0, (T - a) / max(1e-6, b - a)))
    return u * u * (3 - 2 * u)


def pulse(T, starts, dur=0.28):
    """1 during a flash (short ramps), else 0."""
    return max([0.0] + [min(1.0, max(0.0, (T - s) / 0.03)) * min(1.0, max(0.0, (s + dur - T) / 0.06)) for s in starts])


class Room:
    def __init__(self, marks):
        self.M = marks
        T = self
        # ---- Ned's acting: eyes -> head -> shoulders -> body ------------------------------------------------
        self.track = Track([
            (0.0, dict(head_yaw=42.0, head_pitch=2.0, twist=0.0, lean=2.0, gx=0.4, gy=0.0, brow=0.0, lid=0.95, smile=0.10, mouth=0.0)),
            # the ritual over: he relaxes, glances to the window out of habit
            (3.0, dict(head_yaw=HOLD, gx=HOLD)),
            (3.5, dict(head_yaw=6.0, gx=0.0), "io"),
            # the first answer: eyes, head, shoulders; the smile goes
            (5.25, dict(smile=HOLD, brow=HOLD, lid=HOLD, mouth=HOLD, head_yaw=HOLD, twist=HOLD, lean=HOLD)),
            (5.45, dict(gx=0.35, smile=0.0, brow=-0.5, lid=1.12), "out"),
            (5.65, dict(head_yaw=-3.0, mouth=0.10), "out"),
            (5.85, dict(twist=8.0, lean=-1.0), "out"),
            # staring: very still
            (8.0, dict(head_yaw=HOLD, brow=HOLD, lid=HOLD, mouth=HOLD)),
            (8.4, dict(brow=-0.65, lid=1.18, mouth=0.16, head_yaw=-5.0), "out"),
            # he answers: back to the lever, watching the sea
            (11.3, dict(brow=HOLD, lid=HOLD, mouth=HOLD, head_yaw=HOLD, gx=HOLD, twist=HOLD)),
            (11.6, dict(brow=-0.3, lid=1.05, mouth=0.05, head_yaw=-1.0, gx=0.3, twist=6.0), "io"),
            # it comes closer: he leans away, chin up
            (15.3, dict(lean=HOLD, head_pitch=HOLD, brow=HOLD, lid=HOLD, mouth=HOLD)),
            (16.2, dict(lean=-5.0, head_pitch=-5.0, brow=-0.7, lid=1.2, mouth=0.2), "out"),
            # the logbook: eyes, head down, hand to the page
            (20.4, dict(head_yaw=HOLD, head_pitch=HOLD, gx=HOLD, gy=HOLD, lean=HOLD, mouth=HOLD, twist=HOLD)),
            (20.7, dict(gy=-0.5, gx=0.2), "io"),
            (20.95, dict(head_pitch=20.0, head_yaw=22.0, lean=3.0, mouth=0.0, twist=3.0, lid=0.95), "io"),
            # reading the same line over and over: a slow squint
            (25.0, dict(lid=HOLD, brow=HOLD)),
            (27.8, dict(lid=0.78, brow=-0.25), "io"),
            # it wasn't copying him: eyes up, head up
            (28.3, dict(gy=HOLD, gx=HOLD, head_pitch=HOLD, head_yaw=HOLD, lean=HOLD, mouth=HOLD, brow=HOLD, lid=HOLD)),
            (28.5, dict(gy=0.15, gx=0.35, lid=1.2, brow=-0.6), "out"),
            (28.7, dict(head_pitch=-1.0, head_yaw=-2.0, mouth=0.16), "out"),
            (28.95, dict(lean=-3.0), "out"),
            # he had always been copying: eyes drop to his own hand
            (31.0, dict(gy=HOLD, gx=HOLD, head_pitch=HOLD, head_yaw=HOLD, mouth=HOLD, brow=HOLD, lid=HOLD)),
            (31.25, dict(gy=-0.7, gx=0.1), "io"),
            (31.55, dict(head_pitch=14.0, head_yaw=18.0, mouth=0.06, brow=-0.7, lid=1.1), "io"),
            # tonight he keeps his hand still: eyes to the window, then the lamp
            (34.0, dict(gy=HOLD, gx=HOLD, head_pitch=HOLD, head_yaw=HOLD, mouth=HOLD, lean=HOLD)),
            (34.3, dict(gy=0.05, gx=0.45), "out"),
            (34.55, dict(head_pitch=0.0, head_yaw=-3.0, mouth=0.14, lean=-2.0), "out"),
            # the lamp fires by itself: eyes, head, shoulders, all toward it
            (37.7, dict(gx=HOLD, head_yaw=HOLD, twist=HOLD, lean=HOLD)),
            (37.95, dict(gx=0.85, gy=0.1), "snap"),
            (38.15, dict(head_yaw=44.0, mouth=0.2), "out"),
            (38.4, dict(twist=8.0, lean=-2.0), "out"),
            (44.0, dict(brow=HOLD, lid=HOLD)),
        ])
        self.blinks = [0.9, 3.7, 7.3, 10.7, 14.0, 17.2, 20.2, 23.0, 26.6, 30.3, 33.6, 36.9, 41.5]

    # ---- time-driven state -----------------------------------------------------------------------------------
    def lamp(self, T):
        return pulse(T, LAMP)

    def sea(self, T):
        return pulse(T, SEA)

    def press(self, T):
        return pulse(T, [s - 0.07 for s in PRESS], 0.36)

    def seaspot(self, T):
        """The light at sea: (z, y, radius in metres, steady glow 0..1) on the window plane."""
        p = win(T, 15.0, 20.4)
        z = 0.95 + 0.38 * p
        y = HORIZON + 0.02 + 0.19 * p
        r = 0.03 + 0.06 * win(T, 15.1, 15.3) + 0.50 * p * p
        steady = 0.55 * win(T, 18.8, 20.4) * (1.0 - win(T, 40.4, 41.8))
        return z, y, r, steady

    def lever_tip(self, T):
        p = self.press(T)
        return (0.64 - 0.14 * p, 1.14 - 0.08 * p, 1.35)

    def ned(self, T):
        x, z, yaw = NED
        p = dict(rig.REST, x=x, z=z, yaw=yaw, aR=(8.0, 6.0, 24.0), aL=(6.0, 6.0, 18.0), breath=0.5 + 0.5 * math.sin(T * 1.9))
        p.update(self.track(T))
        p["arms_k"] = 1.08
        p["lid"] *= blink(T, self.blinks)
        tx, ty, tz = self.lever_tip(T)
        lift = win(T, 33.6, 34.6)                                  # tonight he keeps his hand still: it hovers
        trem = 0.004 * math.sin(T * 17.0) * lift
        p["ik_R"] = (tx - 0.01 - 0.04 * lift, ty + 0.10 * lift + trem, tz)
        p["pole_R"] = (0.0, -1.0, -0.7)
        book = win(T, 20.8, 21.6)                                  # the other hand goes to the book
        p["ik_L"] = (0.62, 0.99, 1.78 + 0.06 * book)
        p["pole_L"] = (0.0, -1.0, 0.7)
        return p

    def cast(self, T):
        return [("ned", "ned", self.ned(T))]

    # ---- drawing ---------------------------------------------------------------------------------------------
    def shell(self, fr, cam, T):
        L, S = self.lamp(T), self.sea(T)
        fr.poly(cam, [(-RX, 0, -3.2), (RX, 0, -3.2), (RX, 0, RZ), (-RX, 0, RZ)], colr=FLOOR)
        for i in range(-8, 14):                                                    # floor boards
            zb = -3 + i * 0.5
            fr.poly(cam, [(-RX, 0, zb), (RX, 0, zb), (RX, 0, zb + 0.012), (-RX, 0, zb + 0.012)], colr=shade(FLOOR, -0.22))
        fr.poly(cam, [(-1.6, 0, 0.5), (0.4, 0, 0.5), (0.4, 0, 2.6), (-1.6, 0, 2.6)], colr="#4a2c3a")              # rug
        fr.poly(cam, [(-1.5, 0, 0.6), (0.3, 0, 0.6), (0.3, 0, 2.5), (-1.5, 0, 2.5)], colr="#5b3445", outline=shade("#4a2c3a", -0.4), line=2.0)
        fr.poly(cam, [(-RX, RH, -3.2), (RX, RH, -3.2), (RX, RH, RZ), (-RX, RH, RZ)], colr=shade(WALL, -0.55))
        for zb in (0.4, 1.9):                                                      # ceiling beams
            fr.box(cam, (-RX, RX), (RH - 0.16, RH), (zb, zb + 0.18), shade("#3a2c28", -0.3))
        fr.poly(cam, [(-RX, 0, -3.2), (-RX, 0, RZ), (-RX, RH, RZ), (-RX, RH, -3.2)], colr=shade(WALL, -0.12))     # left wall
        fr.poly(cam, [(RX, 0, -3.2), (RX, 0, RZ), (RX, RH, RZ), (RX, RH, -3.2)], colr=shade(WALL, -0.3))        # right wall
        fr.poly(cam, [(-RX, 0, RZ), (RX, 0, RZ), (RX, RH, RZ), (-RX, RH, RZ)],
                shader=lambda path: lin((0, path.getBounds().top()), (0, path.getBounds().bottom()),
                                        [argb(shade(WALL, -0.25)), argb(WALL), argb(shade(WALL, -0.10))], [0, 0.55, 1]))
        fr.poly(cam, [(-RX, 0, RZ - 0.01), (RX, 0, RZ - 0.01), (RX, 0.10, RZ - 0.01), (-RX, 0.10, RZ - 0.01)], colr=shade(WALL, 0.10))   # skirting
        z = RZ - 0.01
        # a chart on the back wall, a ship's clock
        fr.poly(cam, [(-0.9, 1.25, z), (0.1, 1.25, z), (0.1, 1.95, z), (-0.9, 1.95, z)], colr="#c9bb94", outline="#4a3a2a", line=4.0)
        for k in range(6):
            fr.poly(cam, [(-0.82, 1.32 + k * 0.1, z - 0.005), (0.02 - 0.06 * (k % 3), 1.32 + k * 0.1, z - 0.005),
                          (0.02 - 0.06 * (k % 3), 1.335 + k * 0.1, z - 0.005), (-0.82, 1.335 + k * 0.1, z - 0.005)], colr="#8a7a58")
        cx, cy, cd, cs = cam.proj((0.75, 1.95, z))
        if cd > 0.3:
            fr.c.drawCircle(cx, cy, 0.17 * cs, skia.Paint(Color=argb("#e8dfc4"), AntiAlias=True))
            fr.c.drawCircle(cx, cy, 0.17 * cs, skia.Paint(Color=argb("#3a2c24"), AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=0.016 * cs))
            fr.c.drawLine(cx, cy, cx + 0.07 * cs, cy - 0.05 * cs, skia.Paint(Color=argb("#3a2c24"), AntiAlias=True, StrokeWidth=0.012 * cs))
            fr.c.drawLine(cx, cy, cx - 0.02 * cs, cy - 0.11 * cs, skia.Paint(Color=argb("#3a2c24"), AntiAlias=True, StrokeWidth=0.010 * cs))
        # a shelf on the left wall with a few things on it
        fr.box(cam, (-RX, -1.75), (1.55, 1.60), (0.6, 2.4), "#3d2e25")
        for zz, hh, cc in ((0.9, 0.16, "#7d3b32"), (1.25, 0.12, "#3a5a6a"), (1.7, 0.2, "#a58a4a"), (2.1, 0.14, "#5a6a4a")):
            fr.box(cam, (-1.95, -1.82), (1.60, 1.60 + hh), (zz, zz + 0.1), cc)
        self.window(fr, cam, T)
        # light on the room from the window and from the lamp
        fr.ground_ellipse(cam, 1.15, 1.0, 1.0, 0.8, COLD, 0.26 * S, blur_m=0.35, add=True)
        fr.ground_ellipse(cam, 0.9, 2.0, 1.4, 1.1, WARM, 0.22 * L, blur_m=0.4, add=True)

    def window(self, fr, cam, T):
        (z0, z1), (y0, y1) = WIN
        pts = [(XW, y0, z0), (XW, y0, z1), (XW, y1, z1), (XW, y1, z0)]
        fr.poly(cam, pts, shader=lambda path: lin((0, path.getBounds().top()), (0, path.getBounds().bottom()),
                                                  [argb("#0b1230"), argb("#1c2a52"), argb("#27375f")], [0, 0.6, 1]))
        fr.c.save()
        clip = skia.Path()
        for i, pt in enumerate(pts):
            (clip.moveTo if i == 0 else clip.lineTo)(*cam.proj(pt)[:2])
        clip.close()
        fr.c.clipPath(clip, skia.ClipOp.kIntersect, True)
        # the sea, with slow bands of light on it
        fr.poly(cam, [(XW, y0, z0), (XW, y0, z1), (XW, HORIZON, z1), (XW, HORIZON, z0)], colr="#0c1c30")
        for i in range(9):
            yy = HORIZON - 0.035 - i * 0.045 + 0.008 * math.sin(T * 0.8 + i * 1.3)
            if yy > y0:
                zz0 = z0 + 0.1 + (i * 0.37 + 0.2 * math.sin(T * 0.4 + i)) % 1.3
                fr.poly(cam, [(XW, yy, zz0), (XW, yy, zz0 + 0.25), (XW, yy + 0.008, zz0 + 0.25), (XW, yy + 0.008, zz0)], colr="#2d4b70", a=0.55)
        for i in range(14):                                                        # stars
            sx, sy, sd, ss = cam.proj((XW, HORIZON + 0.12 + (i * 0.173) % 0.6, z0 + 0.05 + (i * 0.311) % 1.5))
            if sd > 0.3:
                fr.c.drawCircle(sx, sy, 0.006 * ss, skia.Paint(Color=argb("#dfe8ff", 0.8), AntiAlias=True))
        # the answering light
        zl, yl, rl, steady = self.seaspot(T)
        I = max(self.sea(T), steady)
        lx, ly, ld, ls = cam.proj((XW, yl, zl))
        if ld > 0.3 and I > 0.01:
            fr.glow(lx, ly, max(22.0, rl * ls * 2.6), COLD, a=0.55 * I)
            fr.glow(lx, ly, max(10.0, rl * ls * 1.0), "#ffffff", a=0.6 * I)
            fr.c.drawCircle(lx, ly, max(5.0, rl * ls * 0.16), skia.Paint(Color=argb("#f4faff", min(1.0, I * 1.2)), AntiAlias=True))
        fr.c.restore()
        # frame, mullions, sill
        for a, b in (((z0, y0), (z1, y0)), ((z1, y0), (z1, y1)), ((z1, y1), (z0, y1)), ((z0, y1), (z0, y0)),
                     (((z0 + z1) / 2, y0), ((z0 + z1) / 2, y1)), ((z0, 1.5), (z1, 1.5))):
            pa, pb = cam.proj((XW, a[1], a[0])), cam.proj((XW, b[1], b[0]))
            if pa[2] > 0.3 and pb[2] > 0.3:
                fr.c.drawLine(pa[0], pa[1], pb[0], pb[1], skia.Paint(Color=argb("#7a6a58"), AntiAlias=True, StrokeWidth=max(3.0, 0.045 * pa[3])))

    def greatlamp(self, fr, cam, T):
        L = self.lamp(T)
        (x0, x1), (y0, y1), (z0, z1) = LAMPBOX
        fr.ground_ellipse(cam, (x0 + x1) / 2, (z0 + z1) / 2, 0.45, 0.42, "#000000", 0.35, blur_m=0.10)
        fr.box(cam, (x0 + 0.05, x1 - 0.05), (0.0, 0.85), (z0 + 0.05, z1 - 0.05), "#3b4048", line=2.0)                # pedestal
        fr.box(cam, (x0, x1), (0.85, 0.95), (z0, z1), "#8a6a3a", line=2.0)                                        # brass ring
        fr.box(cam, (x0 + 0.04, x1 - 0.04), (0.95, y1), (z0 + 0.04, z1 - 0.04), shade("#b99650", -0.2 + 0.1 * L), light=OIL, line=2.0)   # the lens drum
        face = [(x1 - 0.04, 1.0, z0 + 0.05), (x1 - 0.04, 1.0, z1 - 0.05), (x1 - 0.04, 1.62, z1 - 0.05), (x1 - 0.04, 1.62, z0 + 0.05)]
        fr.poly(cam, face, colr=shade("#f1d9a0", -0.45 * (1 - L)), outline="#6a5430", line=2.0)
        for k in range(1, 6):                                                      # lens ribs
            yy = 1.0 + k * 0.1
            fr.poly(cam, [(x1 - 0.045, yy, z0 + 0.05), (x1 - 0.045, yy, z1 - 0.05), (x1 - 0.045, yy + 0.012, z1 - 0.05), (x1 - 0.045, yy + 0.012, z0 + 0.05)],
                    colr=shade("#b99650", -0.3))
        fr.box(cam, (x0 + 0.1, x1 - 0.1), (y1, y1 + 0.07), (z0 + 0.1, z1 - 0.1), "#6a5430")
        gx, gy, gd, gs = cam.proj((x1 - 0.04, 1.31, (z0 + z1) / 2))
        if gd > 0.3:
            fr.glow(gx, gy, 0.55 * gs, WARM, a=0.10 + 0.8 * L)

    def desk(self, fr, cam, T):
        (x0, x1), (y0, y1), (z0, z1) = DESK
        fr.ground_ellipse(cam, (x0 + x1) / 2, (z0 + z1) / 2, 0.55, 0.62, "#000000", 0.32, blur_m=0.10)
        fr.box(cam, (x0, x1), (y0, y1), (z0, z1), "#5a4030", light=OIL, line=2.0)
        fr.box(cam, (x0 - 0.02, x1 + 0.02), (y1 - 0.035, y1), (z0 - 0.02, z1 + 0.02), "#6b4d3a", light=OIL, line=1.5)
        # the lever: base, rod to its tip, a knob (it tilts toward him when pulled)
        bx, by, bz = LEVER_BASE
        tx, ty, _ = self.lever_tip(T)
        fr.box(cam, (bx - 0.04, bx + 0.04), (y1, by), (bz - 0.04, bz + 0.04), "#2a2c33", line=1.5)
        fr.poly(cam, [(bx - 0.012, by, bz - 0.02), (bx + 0.012, by, bz - 0.02), (tx + 0.012, ty, bz - 0.02), (tx - 0.012, ty, bz - 0.02)], colr="#55565e", outline="#1e1f24", line=1.5)
        fr.box(cam, (tx - 0.03, tx + 0.03), (ty - 0.02, ty + 0.03), (bz - 0.03, bz + 0.03), "#b02a2a", line=1.5)
        # the logbook: closed, then open with lines of handwriting
        o = win(T, 20.8, 21.6)
        if o < 0.5:
            fr.box(cam, (0.66, 0.96), (y1, y1 + 0.03), (1.58, 1.82), "#4a2a2a", line=1.5)
        else:
            for za, zb in ((1.46, 1.70), (1.70, 1.94)):
                fr.poly(cam, [(0.64, y1 + 0.004, za), (0.98, y1 + 0.004, za), (0.98, y1 + 0.004, zb), (0.64, y1 + 0.004, zb)], colr="#e6dcc2", outline="#6a5a3a", line=2.0)
            for k in range(9):
                xx = 0.69 + k * 0.032
                for za, zb in ((1.50, 1.66 - 0.02 * (k % 3)), (1.74, 1.90 - 0.03 * (k % 2))):
                    fr.poly(cam, [(xx, y1 + 0.006, za), (xx, y1 + 0.006, zb), (xx + 0.006, y1 + 0.006, zb), (xx + 0.006, y1 + 0.006, za)], colr="#5a4a3a")
        # the oil lamp
        ox, oy, oz = OIL
        fr.box(cam, (ox - 0.06, ox + 0.06), (y1, y1 + 0.07), (oz - 0.06, oz + 0.06), "#6a5430", line=1.5)
        fr.poly(cam, [(ox - 0.045, y1 + 0.07, oz), (ox + 0.045, y1 + 0.07, oz), (ox + 0.035, oy + 0.06, oz), (ox - 0.035, oy + 0.06, oz)], colr="#e9d8a8", a=0.30, outline="#a89868", line=1.2)
        px, py, pd, ps = cam.proj((ox, oy, oz))
        if pd > 0.3:
            fr.glow(px, py, 0.16 * ps, WARM, a=0.45)
        fr.ground_ellipse(cam, ox - 0.1, oz, 0.5, 0.5, WARM, 0.10, blur_m=0.25, add=True)

    def grade(self, fr, T, o):
        """The night tint everywhere but the face, and a soft key on it: the oil lamp, plus the great lamp's warm
        flash, plus the cold flash from the sea (from the right)."""
        if o.get("culled") or not o.get("head"):
            return
        L, S = self.lamp(T), self.sea(T)
        hx, hy = o["head"][:2]
        r = max(8.0, o["head_r"])
        p = skia.Paint()
        p.setBlendMode(skia.BlendMode.kModulate)
        p.setShader(rad((hx, hy), r * 5.5, [argb("#ffffff"), argb("#ffffff"), argb("#a9b4d0")], [0, 0.24, 1]))
        fr.c.drawPaint(p)
        for col, k, dx, dy in ((WARM, 0.14 + 0.16 * L, 0.35, -0.15), (COLD, 0.34 * S, 0.9, -0.1)):
            if k <= 0.005:
                continue
            q = skia.Paint()
            q.setBlendMode(skia.BlendMode.kSrcATop)
            q.setShader(rad((hx + dx * r, hy + dy * r), r * 2.1, [argb(col, k), argb(col, k * 0.6), argb(col, 0)], [0, 0.5, 1]))
            fr.c.drawPaint(q)

    def draw(self, fr, cam, T):
        self.shell(fr, cam, T)
        outs = {}
        items = [(cam.view(((DESK[0][0] + DESK[0][1]) / 2, 0.5, (DESK[2][0] + DESK[2][1]) / 2))[2], lambda: self.desk(fr, cam, T)),
                 (cam.view((1.55, 0.5, 2.35))[2], lambda: self.greatlamp(fr, cam, T))]
        for pid, look, pose in self.cast(T):
            def person(pid=pid, look=look, pose=pose):
                fr.c.saveLayer(None, None)
                outs[pid] = rig.draw(fr, cam, look, pose, light=OIL)
                self.grade(fr, T, outs[pid])
                fr.c.restore()
            items.append((cam.view(rig.solve(look, pose)["pelvis"])[2], person))
        for _, fn in sorted(items, key=lambda q: -q[0]):
            fn()
        wash = 0.07 * self.lamp(T)                                                  # the flash fills the room a little
        if wash > 0.004:
            q = skia.Paint()
            q.setBlendMode(skia.BlendMode.kPlus)
            q.setColor(argb(WARM, wash))
            fr.c.drawPaint(q)
        return outs
