"""THE LAMP: one room, one person. World units are metres, y up; the cameras look toward +z.

    x -2 .. 2 (walls), floor y = 0, back wall z = 3. On the back wall: a window (left) and a door (right).
    A side table with the lamp stands front right; Nora stands mid-left, turned toward it.

A world needs only two things for reel.py:
    world.draw(fr, cam, T) -> {pid: what rig.draw returned}     draws everything for time T through camera cam
    world.cast(T)          -> [(pid, look, pose)]               used by the checks
Everything here is a function of T: nothing is stored between frames, so frames render in any order.

Light, three layers: the cool night room (wall, floor, the window's moonlight), a soft key on her face, and the
warm practicals (the lamp with its pool, the strip of hall light under the door).
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

RX, RZ, RH = 2.0, 3.0, 2.6                         # half width, back wall, ceiling
WINDOW = ((-1.6, -0.8), (1.1, 2.0))                # on the back wall: x span, y span
DOOR = ((1.1, 1.9), 2.05)                          # on the back wall: x span, height
TABLE = ((0.65, 1.15), (0.0, 0.62), (0.95, 1.45))  # side table: x, y, z spans
BULB = (0.9, 1.0, 1.2)                             # the lamp's bulb (a light position for the rig, too)
NORA = (-0.4, 2.0, 60.0)                           # x, z, yaw (yaw 0 faces the cameras, +90 faces screen right)
WALL, FLOOR, WARM, MOON = "#2b3350", "#3b3542", "#ffcf8a", "#9db4e6"


def win(T, a, b):
    """0 before a, 1 after b, smooth in between."""
    u = min(1.0, max(0.0, (T - a) / max(1e-6, b - a)))
    return u * u * (3 - 2 * u)


class Room:
    def __init__(self, marks):
        self.M = marks
        self.flicks = [2.35, 5.25, 5.62]                           # once, then twice
        self.knocks = [7.9, 8.3, 11.0, 11.35]                      # the answer, and again on the last line
        self.t_feet = marks["feet"] + 0.1                          # two shadows step into the light under the door
        k1 = self.knocks[0]
        # acting: every action is a chain with offsets (eyes, then head, then shoulders, then body)
        self.track = Track([
            (0.0, dict(head_yaw=0.0, head_pitch=4.0, twist=0.0, lean=2.0, gx=0.0, gy=-0.1, brow=0.0, lid=0.95, smile=0.12, mouth=0.0)),
            # the one flicker she expects: a glance up, a small smile
            (self.flicks[0] + 0.05, dict(gy=HOLD, smile=HOLD)),
            (self.flicks[0] + 0.30, dict(gy=0.1, smile=0.22), "out"),
            # the second and third: the smile goes, the eyes open, the head lifts
            (self.flicks[2] + 0.05, dict(smile=HOLD, lid=HOLD, brow=HOLD, head_pitch=HOLD, mouth=HOLD)),
            (self.flicks[2] + 0.22, dict(smile=0.0, lid=1.12, brow=-0.45), "out"),
            (self.flicks[2] + 0.40, dict(head_pitch=-3.0, mouth=0.14), "out"),
            # the knock: eyes first, then the head, then the shoulders, then she leans away
            (k1 + 0.06, dict(gx=HOLD, head_yaw=HOLD, twist=HOLD, lean=HOLD)),
            (k1 + 0.16, dict(gx=0.7), "snap"),
            (k1 + 0.34, dict(head_yaw=38.0, gx=0.25), "out"),
            (k1 + 0.50, dict(twist=14.0), "out"),
            (k1 + 0.75, dict(lean=-4.0, head_yaw=42.0), "back"),
        ])
        self.blinks = [1.1, 3.9, 6.4, 9.2]

    # ---- time-driven state ---------------------------------------------------------------------------------
    def lamp(self, T):
        """Lamp level 0..1: steady, with short dips at the flickers."""
        return min([1.0] + [0.12 + 0.88 * abs(T - (t + 0.07)) / 0.07 for t in self.flicks if t <= T < t + 0.14])

    def door_dx(self, T):
        """The door shudders on each knock."""
        return sum(0.008 * math.exp(-(T - k) * 14) * math.sin((T - k) * 60) for k in self.knocks if T >= k)

    def nora(self, T):
        x, z, yaw = NORA
        p = dict(rig.REST, x=x, z=z, yaw=yaw, aR=(8.0, 6.0, 24.0), aL=(6.0, 6.0, 18.0), breath=0.5 + 0.5 * math.sin(T * 1.9))
        p.update(self.track(T))
        p["lid"] *= blink(T, self.blinks)
        return p

    def cast(self, T):
        return [("nora", "nora", self.nora(T))]

    # ---- drawing -------------------------------------------------------------------------------------------
    def shell(self, fr, cam, T):
        """Floor, walls, ceiling, the window and the door."""
        fr.poly(cam, [(-RX, 0, -3), (RX, 0, -3), (RX, 0, RZ), (-RX, 0, RZ)], colr=FLOOR)
        fr.poly(cam, [(-RX, RH, -3), (RX, RH, -3), (RX, RH, RZ), (-RX, RH, RZ)], colr=shade(WALL, -0.45))
        for sx in (-RX, RX):
            fr.poly(cam, [(sx, 0, -3), (sx, 0, RZ), (sx, RH, RZ), (sx, RH, -3)], colr=shade(WALL, -0.22))
        fr.poly(cam, [(-RX, 0, RZ), (RX, 0, RZ), (RX, RH, RZ), (-RX, RH, RZ)],
                shader=lambda path: lin((0, path.getBounds().top()), (0, path.getBounds().bottom()),
                                        [argb(shade(WALL, -0.25)), argb(WALL), argb(shade(WALL, -0.12))], [0, 0.55, 1]))
        fr.poly(cam, [(-RX, 0, RZ - 0.01), (RX, 0, RZ - 0.01), (RX, 0.09, RZ - 0.01), (-RX, 0.09, RZ - 0.01)], colr=shade(WALL, 0.10))   # skirting
        # the window: night sky, a moon, a frame; its light lies on the floor
        (wx0, wx1), (wy0, wy1) = WINDOW
        z = RZ - 0.01
        fr.poly(cam, [(wx0, wy0, z), (wx1, wy0, z), (wx1, wy1, z), (wx0, wy1, z)], colr="#141c3a", outline="#c9cfe0", line=7.0)
        mx, my, _, s = cam.proj((wx0 + 0.55, wy1 - 0.28, z))
        fr.c.save()
        clip = skia.Path()
        for i, pt in enumerate([(wx0, wy0, z), (wx1, wy0, z), (wx1, wy1, z), (wx0, wy1, z)]):
            (clip.moveTo if i == 0 else clip.lineTo)(*cam.proj(pt)[:2])
        clip.close()
        fr.c.clipPath(clip, skia.ClipOp.kIntersect, True)
        fr.glow(mx, my, 0.5 * s, MOON, a=0.55)
        fr.c.drawCircle(mx, my, 0.07 * s, skia.Paint(Color=argb("#eef3ff"), AntiAlias=True))
        fr.c.restore()
        fr.poly(cam, [((wx0 + wx1) / 2 - 0.015, wy0, z), ((wx0 + wx1) / 2 + 0.015, wy0, z), ((wx0 + wx1) / 2 + 0.015, wy1, z),
                      ((wx0 + wx1) / 2 - 0.015, wy1, z)], colr="#c9cfe0")
        fr.ground_ellipse(cam, -1.1, 2.2, 0.55, 0.42, MOON, 0.10, blur_m=0.22, add=True)
        # the door: frame, slab (it shudders on a knock), handle, and the hall light under it
        (dx0, dx1), dh = DOOR
        d = self.door_dx(T)
        fr.poly(cam, [(dx0 - 0.06, 0, z), (dx1 + 0.06, 0, z), (dx1 + 0.06, dh + 0.06, z), (dx0 - 0.06, dh + 0.06, z)], colr=shade(WALL, 0.16))
        fr.poly(cam, [(dx0 + d, 0.03, z - 0.01), (dx1 + d, 0.03, z - 0.01), (dx1 + d, dh, z - 0.01), (dx0 + d, dh, z - 0.01)],
                colr="#4a3f3a", outline=shade("#4a3f3a", -0.6), line=3.0)
        for y0, y1 in ((0.18, 0.95), (1.08, 1.92)):                                           # two panels
            fr.poly(cam, [(dx0 + 0.12 + d, y0, z - 0.02), (dx1 - 0.12 + d, y0, z - 0.02), (dx1 - 0.12 + d, y1, z - 0.02),
                          (dx0 + 0.12 + d, y1, z - 0.02)], colr=shade("#4a3f3a", -0.14))
        hx, hy, _, s = cam.proj((dx0 + 0.09 + d, 1.0, z - 0.03))
        fr.c.drawCircle(hx, hy, 0.028 * s, skia.Paint(Color=argb("#c9a65a"), AntiAlias=True))
        fr.poly(cam, [(dx0 + 0.02, 0, z - 0.012), (dx1 - 0.02, 0, z - 0.012), (dx1 - 0.02, 0.03, z - 0.012), (dx0 + 0.02, 0.03, z - 0.012)], colr=WARM)
        fr.ground_ellipse(cam, (dx0 + dx1) / 2, RZ - 0.22, 0.42, 0.22, WARM, 0.22, blur_m=0.10, add=True)
        u = win(T, self.t_feet, self.t_feet + 0.5)                                            # someone is standing there
        for fx in (dx0 + 0.20, dx0 + 0.46):
            x0 = fx + 0.5 * (1 - u)                                                            # they slide in from the right
            if u > 0 and x0 < dx1 - 0.14:
                fr.poly(cam, [(x0, 0, z - 0.014), (x0 + 0.13, 0, z - 0.014), (x0 + 0.13, 0.03, z - 0.014), (x0, 0.03, z - 0.014)], colr="#0c0a0e")
                fr.ground_ellipse(cam, x0 + 0.065, RZ - 0.2, 0.075, 0.2, "#0c0a0e", 0.55 * u, blur_m=0.05)

    def table(self, fr, cam, T):
        L = self.lamp(T)
        (x0, x1), (y0, y1), (z0, z1) = TABLE
        fr.ground_ellipse(cam, (x0 + x1) / 2, (z0 + z1) / 2, 0.42, 0.36, "#000000", 0.35, blur_m=0.10)       # contact shadow
        fr.box(cam, (x0, x1), (y0, y1), (z0, z1), "#3d2e25", light=BULB if L > 0.5 else None)
        fr.box(cam, (BULB[0] - 0.02, BULB[0] + 0.02), (y1, BULB[1] - 0.12), (BULB[2] - 0.02, BULB[2] + 0.02), "#2a2622", line=1.2)
        sh = [(BULB[0] - 0.16, BULB[1] - 0.12, BULB[2]), (BULB[0] + 0.16, BULB[1] - 0.12, BULB[2]),
              (BULB[0] + 0.10, BULB[1] + 0.12, BULB[2]), (BULB[0] - 0.10, BULB[1] + 0.12, BULB[2])]
        fr.poly(cam, sh, colr=shade("#e9c78f", -0.55 * (1 - L)), outline="#5a4a36", line=2.0)
        bx, by, bz, s = cam.proj(BULB)
        if bz > 0.3:                                              # never size a glow from a point behind the lens
            fr.glow(bx, by, 0.9 * s, WARM, a=0.42 * L)
        fr.ground_ellipse(cam, BULB[0] - 0.25, BULB[2] + 0.35, 1.25, 0.95, WARM, 0.13 * L, blur_m=0.35, add=True)   # its pool on the floor

    def grade(self, fr, T, o):
        """Light on a person: the night tint everywhere but the face, and a soft key on it (warmer with the lamp)."""
        if o.get("culled") or not o.get("head"):
            return
        L = self.lamp(T)
        hx, hy = o["head"][:2]
        r = max(8.0, o["head_r"])
        p = skia.Paint()
        p.setBlendMode(skia.BlendMode.kModulate)
        p.setShader(rad((hx, hy), r * 5.5, [argb("#ffffff"), argb("#ffffff"), argb("#a9b4d0")], [0, 0.24, 1]))
        fr.c.drawPaint(p)
        q = skia.Paint()
        q.setBlendMode(skia.BlendMode.kSrcATop)
        ka = 0.08 + 0.18 * L
        q.setShader(rad((hx + 0.3 * r, hy - 0.15 * r), r * 1.9, [argb(WARM, ka), argb(WARM, ka * 0.6), argb(WARM, 0)], [0, 0.5, 1]))
        fr.c.drawPaint(q)

    def draw(self, fr, cam, T):
        self.shell(fr, cam, T)
        outs = {}
        items = [(cam.view(((TABLE[0][0] + TABLE[0][1]) / 2, 0.5, (TABLE[2][0] + TABLE[2][1]) / 2))[2], lambda: self.table(fr, cam, T))]
        for pid, look, pose in self.cast(T):
            def person(pid=pid, look=look, pose=pose):
                fr.c.saveLayer(None, None)                        # so the grade touches this person only
                outs[pid] = rig.draw(fr, cam, look, pose, light=BULB)
                self.grade(fr, T, outs[pid])
                fr.c.restore()
            items.append((cam.view(rig.solve(look, pose)["pelvis"])[2], person))
        for _, fn in sorted(items, key=lambda q: -q[0]):          # far to near
            fn()
        return outs
