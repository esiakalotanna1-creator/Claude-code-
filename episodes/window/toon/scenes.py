"""THE MAN AT THE WINDOW v3: night and rain, the house front, the lamp-lit living room, the upstairs bedroom.

Two worlds, one set. The house never moves; only the two men (and the cameras) do.
  belief (until the twist): the father stands INSIDE the living room looking out; the stranger stands outside in the
      flower bed, forehead and palm on the OUTER face of the glass.
  truth (after it): the father outside in the flower bed in the rain, the stranger inside on the inner face.
The belief world is the truth world turned 180 degrees about the vertical line through the middle of the pane,
(x, y, z) -> (-x, y, -z), people and cameras alike, so the swap inside the full-frame face is exact.
Glass at z = 0; brick wall faces at z = -0.12 (out) and 0.22 (in); garden z < -0.12; living room z 0.22 .. 5.2.
Light (three layers): cool moonlit night outside; a soft key on every face; warm practicals (two coach lanterns
beside the window, the floor lamp and the table lamp inside, the window's own spill) that light what is near them.
Cast tuples: (pid, look, pose, held, glow, after).
"""
import math
import random

import skia

from kit import Room, vignette, win
from kit import lerp as _lerp3
import looks as LK
import rig
import textures as TX
from toon import W, H, Rain, argb, clip_near, lin, paint, rad, shade


def lerp(a, b, u):
    return a + (b - a) * u if isinstance(a, (int, float)) else _lerp3(a, b, u)


Z_OUT, Z_IN = -0.12, 0.22                        # brick wall faces; the glass sits at z = 0
WIN = (-0.62, 0.62, 0.88, 2.10)                  # living-room window opening (x0, x1, y0, y1)
UPWIN = (0.55, 1.75, 3.55, 4.65)                 # the bedroom window above
WALL_X = (-4.6, 4.6)
EAVE = 5.9
SX = 0.04                                        # the stranger's x (truth world)
DX, DZ = -0.10, -0.80                            # the father in the flower bed (truth world)
HEDGES = [((-3.6, -1.05), (-0.98, -0.16), 1.02), ((1.05, 3.6), (-0.98, -0.16), 1.02)]
LANTERNS = [(-1.02, 2.16, Z_OUT - 0.10), (1.02, 2.16, Z_OUT - 0.10)]     # coach lanterns either side of the window
LAMP = (1.0, 3.1)                                # floor lamp, behind the armchair
TLAMP = (0.72, 0.55, 2.47)                       # table lamp on the side table (base point)
STREET = (-3.6, 4.4, -12.9)                      # street lamp head, just past the back fence
MOON = (-18.0, 24.0, -70.0)
NIGHT = "#060a16"
WARM = "#ffb867"
SKY = ("#03050c", "#0a1222", "#1b2438")


def rot(p):
    """The belief world: turned half a circle about the vertical line through the middle of the pane."""
    return (-p[0], p[1], -p[2])


def _hull(pts):
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts

    def half(seq):
        h = []
        for p in seq:
            while len(h) >= 2 and (h[-1][0] - h[-2][0]) * (p[1] - h[-2][1]) - (h[-1][1] - h[-2][1]) * (p[0] - h[-2][0]) <= 0:
                h.pop()
            h.append(p)
        return h
    lo, up = half(pts), half(pts[::-1])
    return lo[:-1] + up[:-1]


def plane_glow(fr, cam, c0, u, v, r, colr, a, n=32):
    """A light pool on a plane (wall or ground): a soft additive ellipse of radius r around c0, axes u and v."""
    if cam.view(c0)[2] < 0.08:
        return
    pts = [rig.add(c0, rig.add(rig.mul(u, r * math.cos(2 * math.pi * i / n)), rig.mul(v, r * math.sin(2 * math.pi * i / n)))) for i in range(n)]
    P = clip_near([cam.view(p) for p in pts])
    if len(P) < 3:
        return
    path = skia.Path()
    for i, (x, y, z) in enumerate(P):
        s = cam.f / z
        (path.moveTo if i == 0 else path.lineTo)(W / 2 + x * s, H * cam.horizon - y * s)
    path.close()
    q = cam.proj(c0)
    b = path.getBounds()
    rr = max(b.width(), b.height()) * 0.5 + 1.0
    fr.c.drawPath(path, paint(shader=rad((q[0], q[1]), rr, [argb(colr, a), argb(colr, a * 0.42), argb(colr, 0)], [0, 0.4, 1],
                                         max(0.05, b.width() / (2 * rr)), max(0.05, b.height() / (2 * rr))), blend="add"))


class House:
    """The house front at night, the garden, the street beyond, and the living room: every shot but the bedroom."""
    name = "house"
    gaze = {}

    def __init__(self, M, lines):
        self.M, self.lines = M, lines
        self.T_UP = M["hand"] - 0.8                 # arm starts to rise (off-frame in the stare)
        self.T_IN = M["hand"] + 0.35                # the hand enters frame from below
        self.T_TOUCH = M["hand"] + 1.55             # fingertips meet the glass
        self.T_FLAT = M["hand"] + 2.2               # palm flat, pads blanched
        self.T_SLIDE = M["slide"] + 0.8
        self.T_SLID = M["slide"] + 3.4
        self.T_SWAP = M["pull"] + 3.85              # inside the full-frame face, after "...of my house."
        self.force = None                           # "belief" / "truth": the cross-fade renders both worlds
        self.allow = [("stranger", "head", "glass", "", 0.008), ("stranger", "hand_R", "glass", "", 0.07),
                      ("stranger", "hand_R", "sill_in", "", 0.06), ("stranger", "wr_R", "glass", "", 0.03)]
        self.room = Room(-3.2, 3.2, Z_IN, 5.2, 2.7, "#86705a", "#5e4630", (LAMP[0], 1.55, LAMP[1]), ceil="#3e342e", base="#3a3028")
        self.room.flat("right", 1.2, 2.2, 1.2, 1.9, "#4d5a4a", frame="#2a2018")                  # a painting
        self.room.flat("back", 0.8, 1.9, 1.35, 1.95, "#6a5448", frame="#2a2018")
        for a0, y0 in ((-0.95, 1.95), (-1.55, 2.2), (-2.15, 2.45)):                            # family photos up the stairs
            self.room.flat("back", a0, a0 + 0.32, y0, y0 + 0.40, "#c8b498", frame="#1a1410")
        self.room.door("right", 3.4, 4.3, inside="#1a1410")                                    # to the kitchen
        rnd = random.Random(21)
        cols = ["#c8742c", "#a8481e", "#d89a3a", "#8a5a2a", "#b5652a", "#e0b050"]
        self.leaves = [(rnd.uniform(-4.5, 4.5), rnd.uniform(-7.0, -1.0), rnd.uniform(0, math.pi), rnd.uniform(0.035, 0.06), rnd.choice(cols))
                       for _ in range(140)]
        self.leaves += [(rnd.uniform(-1.0, 1.0), rnd.uniform(-0.92, -0.2), rnd.uniform(0, math.pi), rnd.uniform(0.03, 0.05), rnd.choice(cols))
                        for _ in range(14)]
        self.clips = [(rnd.uniform(-1.5, -0.6), rnd.uniform(-1.4, -0.98), rnd.uniform(0, math.pi), rnd.uniform(0.02, 0.04)) for _ in range(40)]
        self.flowers = []
        for x in [-0.95 + 0.11 * i for i in range(18)]:
            if abs(x - DX) < 0.30 or abs(x + DX) < 0.30:
                continue                                                                        # where either man stands: trampled
            self.flowers.append((x + rnd.uniform(-0.03, 0.03), -0.30 + rnd.uniform(-0.06, 0.06), rnd.uniform(0.18, 0.30),
                                 rnd.choice(["#8a6ad0", "#e8c040", "#d8603a", "#f2f0e8"])))
        self.trees = [(rnd.uniform(-9, 9), rnd.uniform(-17, -13), rnd.uniform(1.6, 2.8), rnd.uniform(3.5, 6.0)) for _ in range(9)]
        self.houses = []
        for xc in (-14.0, -7.0, 0.6, 7.8, 14.6):                                                # the street's far side
            w, h, rh, zc = rnd.uniform(5.0, 6.4), rnd.uniform(4.6, 5.4), rnd.uniform(1.9, 2.6), rnd.uniform(-23.0, -20.5)
            wins = [(xc + dx, y, rnd.random() < 0.5) for dx in (-0.3 * w, 0.02 * w, 0.3 * w) for y in (1.2, 3.3)]
            self.houses.append((xc, zc, w, h, rh, wins))
        self.puddles = [(rnd.uniform(-3.5, 3.5), rnd.uniform(-7.0, -1.6), rnd.uniform(0.25, 0.6), rnd.uniform(0.12, 0.25)) for _ in range(7)]
        self.rain_far = Rain(n=1500, box=((-10, 10), (0, 6.0), (-16, -4.0)), speed=8.5, seed=11)
        self.rain_near = Rain(n=1300, box=((-5, 5), (0, 6.0), (-4.0, -0.22)), speed=8.5, seed=12)
        r2 = random.Random(8)
        x0, x1, y0, y1 = WIN
        self.beads = []
        while len(self.beads) < 120:                                                            # rain beads on the outer face
            x, y = r2.uniform(x0 + 0.07, x1 - 0.07), r2.uniform(y0 + 0.07, y1 - 0.07)
            if abs(abs(x) - SX) < 0.17 and 1.38 < y < 1.92:
                continue                                                                        # his face wipes them
            if 0.20 < abs(x) < 0.56 and 0.95 < y < 1.52:
                continue                                                                        # and his hand
            self.beads.append((x, y, r2.uniform(0.0025, 0.0075)))
        self.drips = [(r2.choice([r2.uniform(x0 + 0.1, -0.62 + 0.18), r2.uniform(0.44, x1 - 0.1)]), r2.uniform(0.10, 0.22), r2.uniform(0, 7), r2.uniform(0.004, 0.006))
                      for _ in range(6)]
        self._c = {}
        self.ZS = self._solve_zs()

    # ------------------------------------------------------------------------------------------------------
    def world(self, T):
        return self.force or ("belief" if T < self.T_SWAP else "truth")

    def flip(self, T):
        return self.world(T) == "belief"

    @staticmethod
    def inside(cam):
        return cam.pos[2] > 0.0

    def nearest_light(self, p):
        """Only a screen direction for the rig's shading: above and in front of whoever it is, toward the glass."""
        sx = 1.0 if p[2] < 0 else -1.0
        return (p[0] + 0.6 * sx, 2.6, p[2] * 0.2)

    def solids(self):
        x0, x1, y0, y1 = WIN
        return {"wall_L": ((WALL_X[0], x0), (0.0, 5.8), (Z_OUT, Z_IN)), "wall_R": ((x1, WALL_X[1]), (0.0, 5.8), (Z_OUT, Z_IN)),
                "sill_in": ((x0, x1), (0.0, y0), (Z_OUT, Z_IN)), "lintel": ((x0, x1), (y1, 5.8), (Z_OUT, Z_IN)),
                "sill_out": ((x0 - 0.08, x1 + 0.08), (y0 - 0.07, y0), (Z_OUT - 0.07, Z_OUT)),
                "glass": ((x0, x1), (y0, y1), (-0.004, 0.004)),
                "hedge_L": ((-3.6, -1.05), (0.0, 1.02), (-0.98, -0.16)), "hedge_R": ((1.05, 3.6), (0.0, 1.02), (-0.98, -0.16))}

    def _memo(self, key, fn):
        if key not in self._c:
            if len(self._c) > 600:
                self._c.clear()
            self._c[key] = fn()
        return self._c[key]

    # ---- the stranger (built in the truth world, turned for the belief world) ------------------------------
    def _base_pose(self, z):
        # lean 18 / head 14: the forehead reaches the glass while the knees and toes stay clear of the wall under it
        return dict(x=SX, z=z, yaw=0.0, lean=18.0, head_pitch=14.0, head_roll=3.0, gx=0.0, gy=-0.25, nomouth=True,
                    aR=(4.0, 5.0, 12.0), aL=(4.0, 14.0, 12.0), press=1.0)

    def _front_z(self, z):
        J = rig.solve("stranger", self._base_pose(z))
        Hd = rig.Head(None, J["head"], J["Bh"], J["R"], rig.LOOK["stranger"].get("head_shape"))
        return min(Hd.surf(0.0, mu)[2] for mu in [0.25 + 0.05 * i for i in range(10)])

    def _solve_zs(self):
        lo, hi = 0.0, 1.2
        for _ in range(40):
            mid = (lo + hi) / 2
            if self._front_z(mid) < 0.0055:
                lo = mid
            else:
                hi = mid
        return hi

    def hand_state(self, T):
        """Truth-world wrist, finger direction u, palm normal n, spread, curl, press (None before the custom hand)."""
        up = rig.norm((-0.18, 1.0, 0.0))
        n_flat = (0.0, 0.0, -1.0)
        top = (-0.37, 1.30, 0.0)                                                 # wrist when pressed (palm centre ~1.35)
        low = (-0.39, 1.05, 0.0)
        if T < self.T_IN:
            return None
        if T < self.T_TOUCH:                                                     # rising behind the glass, fingers curled
            u_ = win(T, self.T_IN, self.T_TOUCH, "io")
            u = rig.norm(lerp(rig.norm((-0.08, 0.85, -0.5)), up, u_ * 0.8))
            n = rig.norm(rig.sub(n_flat, rig.mul(u, rig.dot(n_flat, u))))
            w = lerp((-0.34, 0.98, 0.16), (top[0], top[1] - 0.02, 0.06), u_)
            spread, curl, press = 0.25 + 0.6 * u_, 0.55 - 0.25 * u_, 0.0
        elif T < self.T_FLAT:                                                    # tips touch, the palm flattens onto the pane
            u_ = win(T, self.T_TOUCH, self.T_FLAT, "out")
            u = rig.norm(lerp(rig.norm(lerp(rig.norm((-0.08, 0.85, -0.5)), up, 0.8)), up, u_))
            n = rig.norm(rig.sub(n_flat, rig.mul(u, rig.dot(n_flat, u))))
            w = lerp((top[0], top[1] - 0.02, 0.06), top, u_)
            spread, curl, press = 0.85 + 0.15 * u_, 0.30 * (1 - u_), u_
        else:
            u, n = up, n_flat
            v = win(T, self.T_SLIDE, self.T_SLID, "io") if T >= self.T_SLIDE else 0.0
            w = lerp(top, low, v)
            spread, curl, press = 1.0, 0.0, 1.0
        # never through the pane: push the hand back until its nearest point is 2 mm off the face of the glass
        mz = LK.hand_min_z(w, u, n, spread, curl)
        w = (w[0], w[1], w[2] + max(0.0, 0.0065 - mz))
        return w, u, n, spread, curl, press

    @staticmethod
    def _turn_hs(hs):
        return (rot(hs[0]), rot(hs[1]), rot(hs[2])) + tuple(hs[3:])

    def hand_world(self, T, flip):
        hs = self.hand_state(T)
        return self._turn_hs(hs) if (hs is not None and flip) else hs

    def stranger(self, T):
        return self._memo(("s", T, self.world(T)), lambda: self._stranger(T))

    def _stranger(self, T):
        p = self._base_pose(self.ZS)
        p["breath"] = 0.5 + 0.5 * math.sin(T * 2 * math.pi / 4.2)
        p["lid"] = 1.0
        p.update(self.gaze_to(T, p))
        hs = self.hand_state(T)
        if T >= self.T_UP:
            hang = rig.solve("stranger", dict(p))["wr_R"]
            if hs is None:                                                       # off-frame rise from his side
                u_ = win(T, self.T_UP, self.T_IN, "io")
                ctl = (hang[0], 1.10, max(hang[2], 0.40))                     # one curve, arcing up over the window board
                end = (-0.34, 0.98, 0.16)
                tgt = tuple((1 - u_) ** 2 * a + 2 * u_ * (1 - u_) * b + u_ ** 2 * c for a, b, c in zip(hang, ctl, end))
            else:
                tgt = hs[0]
            p["ik_R"] = tgt
            J0 = rig.solve("stranger", {k: v for k, v in p.items() if k not in ("ik_R", "pole_R", "arm_near")})
            fk_pole = rig.norm(rig.sub(J0["el_R"], lerp(J0["sh_R"], J0["wr_R"], 0.5)))      # where the elbow already points
            bl = 1.0 if hs is not None else win(T, self.T_UP, self.T_UP + 0.5 * (self.T_IN - self.T_UP), "io")
            p["pole_R"] = rig.norm(lerp(fk_pole, rig.norm((-0.55, -0.75, 0.35)), bl))   # no elbow pop when the reach starts
            p["arm_near"] = {"R": True}
            if hs is not None:
                p["hide_hand_R"] = True
        if self.flip(T):
            p["x"], p["z"], p["yaw"] = -p["x"], -p["z"], 180.0
            for k in ("ik_R", "pole_R"):
                if k in p:
                    p[k] = rot(p[k])
            if hs is not None:
                hs = self._turn_hs(hs)
        after = None
        if hs is not None:
            def after(fr, cam, J, hs=hs):
                LK.draw_glass_hand(fr, cam, *hs, light=(-0.6, 1.0))
        return ("stranger", "stranger", p, None, None, after)

    def gaze_to(self, T, p):
        """The stranger's eyes stay on the father's face (not on the lens). Truth-world pose; turning keeps it."""
        J = rig.solve("stranger", p)
        tgt = (DX, 1.67, DZ + 0.06)
        d = rig.norm(rig.sub(tgt, J["head"]))
        B = J["Bh"]
        return dict(gx=max(-0.6, min(0.6, -rig.dot(d, B.r) * 2.2)), gy=max(-0.45, min(0.45, -rig.dot(d, B.u) * 2.2)))

    def stranger_head(self, T):
        return self._memo(("sh", T, self.world(T)), lambda: rig.solve("stranger", self.stranger(T)[2]))

    # ---- the father ------------------------------------------------------------------------------------------
    def dad_pose(self, T):
        M = self.M
        t_see = M["dad"] + 0.55
        p = dict(x=DX, z=DZ, yaw=180.0, lean=3.0, stance=0.025, aL=(5.0, 6.0, 12.0), aR=(6.0, 5.0, 16.0),
                 fist=1.0, breath=0.5 + 0.5 * math.sin(T * 2 * math.pi / 3.1 + 1.0))
        a = win(T, t_see, t_see + 0.18, "snap")                                   # the eyes stop on him
        b = win(T, t_see + 0.12, t_see + 0.55, "out")                             # then the head comes up
        c = win(T, t_see + 0.6, t_see + 1.6, "io")                                # the face tightens
        p["gy"] = lerp(0.55, -0.12, a)
        p["gx"] = lerp(0.25, 0.02, a)
        p["head_pitch"] = lerp(9.0, -4.0, b)
        p["head_yaw"] = lerp(-6.0, 0.0, b)
        p["brow"] = lerp(0.1, 0.75, c)                 # rig sign: + raises (worried with brow_in < 0)
        p["brow_in"] = lerp(0.0, -0.55, c)
        p["lid"] = lerp(0.88, 1.0, c)
        p["lid_lo"] = lerp(0.1, 0.0, c)
        p["shrug"] = 0.08 * c
        mo = win(T, M["mouth"] + 0.5, M["mouth"] + 1.4, "io") - 0.35 * win(T, M["mouth"] + 2.2, M["mouth"] + 2.8, "io")
        p["mouth"] = 0.30 * mo
        p["mouth_w"] = -0.2 * mo
        if M["mouth"] < T < M["slide"]:
            p["head_roll"] = 0.4 * math.sin(T * 23.0)                             # a fine tremor
        g = win(T, M["shears"] + 1.2, M["shears"] + 2.4, "io")                    # the grip tightens in the insert
        p["grip"] = g
        if self.flip(T):                                                          # belief: inside, at the window
            p["x"], p["z"], p["yaw"] = -DX, -DZ, 0.0
        return p

    def dad(self, T):
        def mk():
            p = self.dad_pose(T)
            return ("dad", "dad", p, {"R": LK.shears(9.0 - 6.0 * p["grip"])}, None, None)
        return self._memo(("d", T, self.world(T)), mk)

    def cast(self, T):
        return [self.stranger(T), self.dad(T)]

    # ---- light on people: night tint everywhere but the face, and a soft key on it ---------------------------
    def grade(self, fr, cam, T, pid, o):
        if o.get("culled") or not o.get("head"):
            return
        hx, hy = o["head"][:2]
        r = max(8.0, o["head_r"])
        indoors = o["J"]["pelvis"][2] > 0.0
        if pid == "stranger":
            tint, key, ka = "#a4aec6", "#ffe8c8", 0.24            # the same in both worlds: the swap must not show
        elif indoors:
            tint, key, ka = "#cdb8a0", "#eef2ff", 0.16            # lamp-warm room, the cool window on his face
        else:
            tint, key, ka = "#929fbc", "#ffdcaa", 0.26            # rain-cold garden, the window's warm spill on his face
        c = fr.c
        p = skia.Paint()
        p.setBlendMode(skia.BlendMode.kModulate)
        p.setShader(rad((hx, hy), r * 5.5, [argb("#ffffff"), argb("#ffffff"), argb(tint)], [0, 0.24, 1]))
        c.drawPaint(p)
        q = skia.Paint()
        q.setBlendMode(skia.BlendMode.kSrcATop)
        q.setShader(rad((hx, hy - 0.15 * r), r * 1.9, [argb(key, ka), argb(key, ka * 0.6), argb(key, 0)], [0, 0.5, 1]))
        c.drawPaint(q)

    # ---- world drawing ----------------------------------------------------------------------------------------
    def bg(self, fr, cam, T):
        if self.inside(cam):
            self._room(fr, cam, T, through=False)
            if cam.fwd[2] < 0:                                     # facing the window: the night through the glass
                g = self._glass_path(fr, cam)
                if g is not None:
                    fr.c.save()
                    fr.c.clipPath(g, skia.ClipOp.kIntersect, True)
                    self._outside_world(fr, cam, T)
                    for (x0, x1), (z0, z1), h in HEDGES:
                        self._hedge(fr, cam, x0, x1, z0, z1, h, HEDGES.index(((x0, x1), (z0, z1), h)))
                    self._outer_reveals(fr, cam)
                    self.rain_near.draw(fr, cam, T, light=self._near_lantern(cam), amax=0.32, zmin=0.3, wmax=1.6)
                    fr.c.restore()
        else:
            self._outside_world(fr, cam, T)
            self._interior(fr, cam, T)

    def _glass_path(self, fr, cam):
        x0, x1, y0, y1 = WIN
        return fr.poly(cam, [(x0, y0, 0.0), (x1, y0, 0.0), (x1, y1, 0.0), (x0, y1, 0.0)], colr="#000000", a=0.0)

    def _near_lantern(self, cam):
        return min(LANTERNS, key=lambda L: math.dist(L, cam.pos))

    def _outside_world(self, fr, cam, T):
        c = fr.c
        hy = H * cam.horizon
        c.drawRect(skia.Rect(0, 0, W, H), paint(shader=lin((0, hy - 1500), (0, hy + 40), [argb(SKY[0]), argb(SKY[1]), argb(SKY[2])], [0, 0.6, 1])))
        if cam.view(MOON)[2] > 1:                                  # the moon behind thin cloud
            q = cam.proj(MOON)
            fr.glow(q[0], q[1], 9.0 * q[3], "#8fa6d0", a=0.20)
            c.drawCircle(q[0], q[1], 1.1 * q[3], paint("#d8e0f0", a=0.55, blur=0.25 * q[3]))
        for xc, zc, w, h, rh, wins in self.houses:                 # the far side of the street
            if cam.view((xc, 2.0, zc))[2] < 1:
                continue
            fr.poly(cam, [(xc - w / 2, 0, zc), (xc + w / 2, 0, zc), (xc + w / 2, h, zc), (xc, h + rh, zc), (xc - w / 2, h, zc)], colr="#0e121c")
            fr.poly(cam, [(xc - w / 2 - 0.3, h - 0.05, zc + 0.05), (xc, h + rh + 0.1, zc + 0.05), (xc + w / 2 + 0.3, h - 0.05, zc + 0.05)],
                    colr="#080a12")
            for wx, wy, lit_ in wins:
                pts = [(wx - 0.42, wy, zc + 0.02), (wx + 0.42, wy, zc + 0.02), (wx + 0.42, wy + 1.0, zc + 0.02), (wx - 0.42, wy + 1.0, zc + 0.02)]
                fr.poly(cam, pts, colr="#e8b464" if lit_ else "#141a26", a=0.85 if lit_ else 1.0)
                if lit_:
                    q = cam.proj((wx, wy + 0.5, zc))
                    fr.glow(q[0], q[1], 1.1 * q[3], "#ffb45a", a=0.12)
            q = cam.proj((xc, 2.4, zc + 0.1))                                                   # a porch light
            fr.glow(q[0], q[1], 0.9 * q[3], "#ffc27a", a=0.25)
        # the road and the pavement, wet: the street lamp's long reflection
        fr.poly(cam, [(-30, 0, -18.5), (30, 0, -18.5), (30, 0, -12.2), (-30, 0, -12.2)], colr="#0b0e16")
        fr.poly(cam, [(-30, 0.002, -12.4), (30, 0.002, -12.4), (30, 0.002, -11.6), (-30, 0.002, -11.6)], colr="#151821")
        if cam.view((STREET[0], 0.0, STREET[2] - 1.5))[2] > 1:
            a, b = cam.proj((STREET[0] + 0.2, 0.0, STREET[2] - 0.6)), cam.proj((STREET[0] + 0.2, 0.0, STREET[2] - 5.0))
            c.drawOval(skia.Rect(a[0] - 0.35 * a[3], b[1], a[0] + 0.35 * a[3], a[1]), paint("#ffa850", a=0.22, blur=0.25 * a[3], blend="add"))
        for x, z, r, h in self.trees:                                                           # dark crowns, lit edge toward the lamp
            q = cam.proj((x, h, z))
            if q[2] > 0.3:
                c.drawCircle(q[0], q[1], r * q[3], paint("#0d1a16"))
                c.drawCircle(q[0] - 0.3 * r * q[3], q[1] - 0.3 * r * q[3], r * 0.7 * q[3], paint("#142420", a=0.9))
                lit_ = max(0.0, 1 - math.dist((x, h, z), STREET) / 6.0)
                if lit_ > 0:
                    c.drawCircle(q[0], q[1], r * 0.8 * q[3], paint("#7a5a2a", a=0.35 * lit_, blur=0.3 * r * q[3]))
        self._street_lamp(fr, cam)
        TX.plane(fr, cam, "lawn", [(-14, 0, -11.4), (14, 0, -11.4), (14, 0, -0.98), (-14, 0, -0.98)], lambda p: (p[0], p[2]))
        fr.poly(cam, [(-14, 0, -11.4), (14, 0, -11.4), (14, 0, -0.98), (-14, 0, -0.98)], colr=NIGHT, a=0.72)
        for x0 in [-9.0 + 0.16 * i for i in range(113)]:                                   # a low picket fence
            lit_ = max(0.0, 1 - abs(x0 - STREET[0]) / 4.0)
            fr.poly(cam, [(x0, 0, -11.4), (x0 + 0.11, 0, -11.4), (x0 + 0.11, 1.05, -11.4), (x0 + 0.055, 1.12, -11.4), (x0, 1.05, -11.4)],
                    colr=shade("#3e424c", 0.35 * lit_))
        fr.poly(cam, [(-9, 0.75, -11.38), (9, 0.75, -11.38), (9, 0.82, -11.38), (-9, 0.82, -11.38)], colr="#2e323a")
        self._window_spill(fr, cam)
        for x, z, rx, rz in self.puddles:                                                       # wet patches catching the light
            fr.ground_ellipse(cam, x, z, rx, rz, "#1a2234", 0.55, blur_m=0.05, y=0.002)
            fr.ground_ellipse(cam, x + 0.1 * rx, z, rx * 0.5, rz * 0.35, "#5a6a88", 0.18, blur_m=0.06, y=0.003, add=True)
        # the flower bed under the window, brick edging along the lawn
        TX.plane(fr, cam, "soil", [(-3.8, 0.003, -0.98), (3.8, 0.003, -0.98), (3.8, 0.003, Z_OUT), (-3.8, 0.003, Z_OUT)], lambda p: (p[0], p[2]))
        fr.poly(cam, [(-3.8, 0.004, -0.98), (3.8, 0.004, -0.98), (3.8, 0.004, Z_OUT), (-3.8, 0.004, Z_OUT)], colr=NIGHT, a=0.55)
        for i in range(32):
            x0 = -3.8 + i * 0.2375
            fr.box(cam, (x0 + 0.005, x0 + 0.23), (0.0, 0.05), (-1.03, -0.97), "#5a3428", line=1.0)
        for x, z, ang, r, colr in self.leaves:
            self._leaf(fr, cam, x, z, ang, r, shade(colr, -0.6))
        for x, z, ang, r in self.clips:                                                     # fresh hedge clippings
            self._leaf(fr, cam, x, z, ang, r, "#24401c")
        for L in LANTERNS:                                                                  # lantern light on the bed below
            plane_glow(fr, cam, (L[0], 0.006, -0.55), (1, 0, 0), (0, 0, 1), 1.0, WARM, 0.22)
        self.rain_far.draw(fr, cam, T, light=STREET, amax=0.30, zmin=0.6, wmax=1.6)

    def _street_lamp(self, fr, cam):
        x, y, z = STREET
        if cam.view((x, 2.0, z))[2] < 1:
            return
        a, b = cam.proj((x, 0.0, z)), cam.proj((x, y, z))
        fr.c.drawLine(a[0], a[1], b[0], b[1], paint("#1a1c22", stroke=max(1.2, 0.08 * a[3])))
        h = cam.proj((x + 0.5, y, z))
        fr.c.drawLine(b[0], b[1], h[0], h[1], paint("#1a1c22", stroke=max(1.0, 0.06 * a[3])))
        # the light cone through the rain and the pool on the pavement
        g0, g1 = cam.proj((x + 0.5 - 1.4, 0.0, z)), cam.proj((x + 0.5 + 1.4, 0.0, z))
        cone = skia.Path()
        cone.moveTo(h[0] - 0.1 * h[3], h[1])
        cone.lineTo(h[0] + 0.1 * h[3], h[1])
        cone.lineTo(g1[0], g1[1])
        cone.lineTo(g0[0], g0[1])
        cone.close()
        fr.c.drawPath(cone, paint(shader=lin((0, h[1]), (0, g0[1]), [argb("#ffb45a", 0.16), argb("#ffb45a", 0.03)]), blend="add", blur=0.2 * h[3]))
        fr.ground_ellipse(cam, x + 0.5, z, 1.6, 1.0, "#ffa850", 0.20, blur_m=0.4, y=0.003, add=True)
        fr.glow(h[0], h[1], 1.6 * h[3], "#ffb45a", a=0.45)
        fr.c.drawCircle(h[0], h[1] + 0.05 * h[3], 0.10 * h[3], paint("#fff0c8"))

    def _window_spill(self, fr, cam):
        """The living room's light through the pane, a warm trapezoid far out on the wet lawn."""
        x0, x1, y0, y1 = WIN
        L = (LAMP[0], 1.55, LAMP[1])
        pts = []
        for (x, y) in ((x0, y0), (x1, y0), (x1, 1.36), (x0, 1.36)):
            t = L[1] / (L[1] - y)
            pts.append((L[0] + (x - L[0]) * t, 0.004, L[2] + (0.0 - L[2]) * t))
        path = fr.poly(cam, pts, colr="#ffb060", a=0.0)
        if path is not None:
            n0 = cam.proj(lerp(pts[0], pts[1], 0.5))
            n1 = cam.proj(lerp(pts[2], pts[3], 0.5))
            fr.c.drawPath(path, paint(shader=lin((n0[0], n0[1]), (n1[0], n1[1]), [argb("#ffb060", 0.20), argb("#ffb060", 0.0)]),
                                      blend="add", blur=0.06 * n0[3]))

    def _leaf(self, fr, cam, x, z, ang, r, colr):
        q = cam.proj((x, 0.006, z))
        if q[2] < 0.25 or not (-60 < q[0] < W + 60 and -60 < q[1] < H + 60):
            return
        e = cam.proj((x + math.cos(ang) * r, 0.006, z + math.sin(ang) * r))
        f = cam.proj((x - math.sin(ang) * r * 0.45, 0.006, z + math.cos(ang) * r * 0.45))
        p = skia.Path()
        p.moveTo(2 * q[0] - e[0], 2 * q[1] - e[1])
        p.quadTo(f[0], f[1], e[0], e[1])
        p.quadTo(2 * q[0] - f[0], 2 * q[1] - f[1], 2 * q[0] - e[0], 2 * q[1] - e[1])
        fr.c.drawPath(p, paint(colr))
        fr.c.drawPath(p, paint(shade(colr, -0.55), stroke=max(0.8, 0.004 * q[3])))

    # ---- the living room ----------------------------------------------------------------------------------
    def _interior(self, fr, cam, T):
        """Seen from the garden: the room through the window hole."""
        x0, x1, y0, y1 = WIN
        hole = self._glass_path(fr, cam)
        if hole is None:
            return
        c = fr.c
        c.save()
        c.clipPath(hole, skia.ClipOp.kIntersect, True)
        self._room(fr, cam, T, through=True)
        self._curtains(fr, cam)
        fr.poly(cam, [(x0, y0, 0.0), (x0, y1, 0.0), (x0, y1, Z_IN), (x0, y0, Z_IN)], colr="#b0a08a")      # inner reveals, lamp-lit
        fr.poly(cam, [(x1, y0, 0.0), (x1, y1, 0.0), (x1, y1, Z_IN), (x1, y0, Z_IN)], colr="#9a8a74")
        fr.poly(cam, [(x0, y1, 0.0), (x1, y1, 0.0), (x1, y1, Z_IN), (x0, y1, Z_IN)], colr="#6f6252")
        fr.box(cam, (x0 - 0.04, x1 + 0.04), (y0 - 0.03, y0), (0.0, Z_IN + 0.05), "#cfc2ac", line=1.0)
        c.restore()

    def _room(self, fr, cam, T, through):
        self.room.draw(fr, cam, T)
        self._rug(fr, cam)
        self._stairs(fr, cam)
        self._bookcase(fr, cam)
        self._armchair(fr, cam)
        self._floor_lamp(fr, cam)
        self._plant(fr, cam)
        fr.c.drawPaint(paint("#160c10", a=0.26))                  # evening: the lamps, not the room, are bright
        self._lamp_light(fr, cam)

    def _rug(self, fr, cam):
        pts = [(-0.3, 0.003, 1.2), (2.4, 0.003, 1.2), (2.4, 0.003, 3.4), (-0.3, 0.003, 3.4)]
        fr.poly(cam, pts, colr="#6a2e26")
        fr.poly(cam, [(-0.15, 0.004, 1.35), (2.25, 0.004, 1.35), (2.25, 0.004, 3.25), (-0.15, 0.004, 3.25)], colr="#8a4a32", outline="#c89a5a", line=1.4)
        fr.poly(cam, [(0.3, 0.005, 1.8), (1.8, 0.005, 1.8), (1.8, 0.005, 2.8), (0.3, 0.005, 2.8)], colr="#a86a3e", outline="#d8b070", line=1.2)

    def _stairs(self, fr, cam):
        """Against the back wall, rising to the left-hand landing: 14 steps with a red runner, white spindles."""
        n, xb, xt, zf, zb = 14, -0.4, -3.0, 4.25, 5.2
        run, rise = (xb - xt) / n, 2.7 / n
        for i in range(n - 1, -1, -1):
            xa = xb - i * run
            ya = i * rise
            fr.box(cam, (xa - run, xa), (0.0, ya + rise), (zf, zb), "#d8d2c4", line=1.0)
            fr.box(cam, (xa - run, xa + 0.01), (ya + rise - 0.005, ya + rise + 0.012), (zf + 0.18, zb - 0.18), "#7a1c22", line=0.8)
        saw = [(xb, 0.0, zf)]
        for i in range(n):
            xa = xb - i * run
            saw += [(xa, (i + 1) * rise, zf), (xa - run, (i + 1) * rise, zf)]
        saw += [(xt, 0.0, zf)]
        fr.poly(cam, saw, colr="#c8c0b0", outline="#5a5248", line=1.2)
        for i in range(n):                                                          # spindles + handrail on the open side
            xa = xb - (i + 0.5) * run
            ya = (i + 1) * rise
            if cam.view((xa, ya, zf))[2] < 0.3:
                continue
            a, b = cam.proj((xa, ya, zf - 0.04)), cam.proj((xa, ya + 0.86, zf - 0.04))
            fr.c.drawLine(a[0], a[1], b[0], b[1], paint("#ece8de", stroke=max(1.2, 0.022 * a[3])))
        fr.box(cam, (xb - 0.04, xb + 0.06), (0.0, 1.15), (zf - 0.09, zf + 0.01), "#3a2418", line=1.0)       # newel post
        if cam.view((xb, 1.0, zf))[2] > 0.3:
            a, b = cam.proj((xb + 0.01, 1.08, zf - 0.04)), cam.proj((xt, 2.7 + 0.9, zf - 0.04))
            fr.c.drawLine(a[0], a[1], b[0], b[1], paint("#3a2418", stroke=max(2.0, 0.05 * a[3])))

    def _bookcase(self, fr, cam):
        """Against the right wall by the window: shelves of books, a clock, a photo."""
        x1, z0, z1 = 3.2, 0.7, 1.75
        fr.box(cam, (x1 - 0.34, x1), (0.0, 2.0), (z0, z1), "#4a3020", line=1.2)
        rnd = random.Random(4)
        for k in range(5):
            y = 0.12 + k * 0.38
            fr.box(cam, (x1 - 0.32, x1 - 0.02), (y, y + 0.03), (z0 + 0.03, z1 - 0.03), "#5a3a26", line=0.8)
            z = z0 + 0.06
            while z < z1 - 0.12:
                w = rnd.uniform(0.03, 0.07)
                hh = rnd.uniform(0.22, 0.32)
                fr.box(cam, (x1 - 0.30, x1 - 0.32 + 0.25), (y + 0.03, y + 0.03 + hh), (z, z + w),
                       rnd.choice(["#7a2a22", "#2a4a6a", "#c8a050", "#3a5a3a", "#8a6a4a", "#e0d8c8"]), line=0.6)
                z += w + 0.004
                if rnd.random() < 0.08:
                    z += 0.12

    def _armchair(self, fr, cam):
        x, z = 1.55, 2.4
        col = "#6a3a2c"
        fr.box(cam, (x - 0.45, x + 0.45), (0.0, 0.42), (z - 0.4, z + 0.45), col, line=1.2)                  # seat base
        fr.box(cam, (x - 0.45, x + 0.45), (0.42, 1.05), (z + 0.28, z + 0.48), shade(col, -0.05), line=1.2)  # back
        for sx in (-1, 1):
            fr.box(cam, (x + sx * 0.45 - (0.14 if sx > 0 else 0), x + sx * 0.45 + (0.0 if sx > 0 else 0.14)), (0.0, 0.66), (z - 0.42, z + 0.48),
                   shade(col, 0.05), line=1.2)
        fr.box(cam, (x - 0.31, x + 0.31), (0.42, 0.52), (z - 0.36, z + 0.28), shade(col, 0.12), line=1.0)  # cushion
        fr.box(cam, (x - 0.22, x + 0.12), (0.52, 0.80), (z + 0.18, z + 0.28), "#c8a868", line=1.0)       # a throw cushion
        fr.box(cam, (x - 1.0, x - 0.65), (0.0, 0.55), (z - 0.1, z + 0.25), "#3a2a1e", line=1.0)            # side table
        tx, ty, tz = TLAMP                                                                              # its lamp
        fr.box(cam, (tx - 0.05, tx + 0.05), (ty, ty + 0.22), (tz - 0.05, tz + 0.05), "#8a6a4a", line=0.8)
        fr.poly(cam, [(tx - 0.09, ty + 0.40, tz), (tx + 0.09, ty + 0.40, tz), (tx + 0.14, ty + 0.22, tz), (tx - 0.14, ty + 0.22, tz)],
                colr="#e8d0a0", outline="#7a5a3a", line=1.0)

    def _floor_lamp(self, fr, cam):
        x, z = LAMP
        if cam.view((x, 1.0, z))[2] < 0.3:
            return
        a, b = cam.proj((x, 0.0, z)), cam.proj((x, 1.45, z))
        fr.c.drawLine(a[0], a[1], b[0], b[1], paint("#2a2420", stroke=max(1.5, 0.025 * a[3])))
        fr.ground_ellipse(cam, x, z, 0.16, 0.16, "#2a2420", 1.0)
        top, bot = 1.72, 1.40
        fr.poly(cam, [(x - 0.13, top, z), (x + 0.13, top, z), (x + 0.22, bot, z), (x - 0.22, bot, z)], colr="#c9b48e", outline="#5a4a38", line=1.2)

    def _plant(self, fr, cam):
        """A tall rubber plant in a pot by the window, standing straight."""
        x, z = -1.15, 0.62
        fr.box(cam, (x - 0.16, x + 0.16), (0.0, 0.38), (z - 0.16, z + 0.16), "#b0603a", line=1.0)
        fr.box(cam, (x - 0.15, x + 0.15), (0.36, 0.38), (z - 0.15, z + 0.15), "#2a1c14", line=0.6)
        if cam.view((x, 0.8, z))[2] < 0.35:
            return
        a, b = cam.proj((x, 0.37, z)), cam.proj((x, 1.45, z))
        fr.c.drawLine(a[0], a[1], b[0], b[1], paint("#3a2a1a", stroke=max(1.0, 0.012 * a[3])))
        for k in range(9):
            yy = 0.62 + k * 0.09
            side = 1 if k % 2 else -1
            p0 = (x, yy, z)
            p1 = (x + side * 0.22, yy + 0.10, z + 0.04 * ((k % 3) - 1))
            q0, q1 = cam.proj(p0), cam.proj(p1)
            if q0[2] < 0.3:
                continue
            m = ((q0[0] + q1[0]) / 2, (q0[1] + q1[1]) / 2)
            nx, ny = -(q1[1] - q0[1]) * 0.28, (q1[0] - q0[0]) * 0.28
            leaf = skia.Path()
            leaf.moveTo(q0[0], q0[1])
            leaf.quadTo(m[0] + nx, m[1] + ny, q1[0], q1[1])
            leaf.quadTo(m[0] - nx, m[1] - ny, q0[0], q0[1])
            fr.c.drawPath(leaf, paint("#2f5a2a"))
            fr.c.drawPath(leaf, paint("#14280f", stroke=max(0.8, 0.004 * q0[3])))

    def _lamp_light(self, fr, cam):
        """Both lamps on: glowing shades, warm pools on the floor, the wall and the chair near them."""
        x, z = LAMP
        if cam.view((x, 1.5, z))[2] > 0.3:
            fr.ground_ellipse(cam, x, z, 1.1, 0.85, "#ffb35a", 0.20, blur_m=0.3, add=True)
            plane_glow(fr, cam, (x, 1.45, 5.198), (1, 0, 0), (0, 1, 0), 1.7, "#ffb060", 0.26)       # the back wall behind it
            q = cam.proj((x, 1.25, z))
            fr.glow(q[0], q[1], 1.0 * q[3], "#ffc07a", a=0.16)
            top, bot = 1.72, 1.40
            fr.poly(cam, [(x - 0.13, top, z), (x + 0.13, top, z), (x + 0.22, bot, z), (x - 0.22, bot, z)], colr="#f6dca4", outline="#8a6a44", line=1.0)
            fr.poly(cam, [(x - 0.21, bot + 0.02, z - 0.001), (x + 0.21, bot + 0.02, z - 0.001), (x + 0.22, bot, z - 0.001), (x - 0.22, bot, z - 0.001)],
                    colr="#fff2d0")
            g = cam.proj((x, 1.52, z))
            fr.glow(g[0], g[1], 0.45 * g[3], "#ffd590", a=0.34)
        tx, ty, tz = TLAMP
        if cam.view((tx, ty + 0.3, tz))[2] > 0.3:
            fr.ground_ellipse(cam, tx, tz, 0.30, 0.30, "#ffb35a", 0.30, blur_m=0.08, y=ty + 0.003, add=True)
            plane_glow(fr, cam, (tx, 0.6, tz), (1, 0, 0), (0, 0, 1), 1.0, "#ffa850", 0.12)
            fr.poly(cam, [(tx - 0.09, ty + 0.40, tz), (tx + 0.09, ty + 0.40, tz), (tx + 0.14, ty + 0.22, tz), (tx - 0.14, ty + 0.22, tz)],
                    colr="#ffe6b4", outline="#9a7a4a", line=0.8)
            g = cam.proj((tx, ty + 0.30, tz))
            fr.glow(g[0], g[1], 0.35 * g[3], "#ffcf88", a=0.32)

    def _curtains(self, fr, cam):
        """Heavy burgundy curtains drawn back to either side: soft fabric panels gathered into an hourglass at a
        gold tie-back, folds running down and pinching at the tie, a brass rod with finials."""
        x0, x1, y0, y1 = WIN
        z = Z_IN + 0.06
        top, bot, tie = y1 + 0.32, 0.40, 1.05
        col = "#7a3438"
        ys = [bot + (top - bot) * i / 16 for i in range(17)]

        def inner_off(y):                                   # how far the inner edge is pulled back from the window
            if y >= tie:
                u = (y - tie) / (top - tie)
                return 0.42 - 0.40 * (1 - (1 - u) ** 2)
            u = (tie - y) / (tie - bot)
            return 0.42 - 0.20 * u ** 1.5
        for side in (-1, 1):
            outer = x0 - 0.62 if side < 0 else x1 + 0.62
            edge = x0 if side < 0 else x1

            def X(f, y):                                    # f = 0 outer edge .. 1 inner edge
                inner = edge - side * inner_off(y)
                return outer + f * (inner - outer)
            pts = [(X(0, y), y, z) for y in ys] + [(X(1, y), y, z + 0.02) for y in reversed(ys)]
            if any(cam.view(p)[2] < 0.12 for p in pts):
                continue
            P = [cam.proj(p) for p in pts]
            path = skia.Path()
            path.addPoly([skia.Point(p[0], p[1]) for p in P], True)
            A, B_ = cam.proj((X(0, 1.6), 1.6, z)), cam.proj((X(1, 1.6), 1.6, z))
            cols, pos = [], []
            for k in range(13):
                cols.append(argb(shade(col, 0.16 if k % 2 else -0.28)))
                pos.append(k / 12)
            fr.c.drawPath(path, paint(shader=lin((A[0], A[1]), (B_[0], B_[1]), cols, pos)))
            for f in (0.17, 0.33, 0.5, 0.67, 0.83):         # folds pinching at the tie-back
                for off, colr, al in ((0.0, shade(col, -0.55), 0.45), (0.05, shade(col, 0.35), 0.25)):
                    line = skia.Path()
                    for i, y in enumerate(ys):
                        q = cam.proj((X(f + off, y), y, z + 0.01))
                        (line.moveTo if i == 0 else line.lineTo)(q[0], q[1])
                    fr.c.drawPath(line, paint(colr, a=al, stroke=max(1.0, 0.012 * A[3])))
            fr.c.drawPath(path, paint(shade(col, -0.7), stroke=1.2))
            t0, t1 = cam.proj((X(-0.02, tie), tie, z + 0.03)), cam.proj((X(1.02, tie), tie, z + 0.03))   # the tie-back
            band = skia.Path()
            band.moveTo(t0[0], t0[1] - 0.016 * t0[3])
            band.quadTo((t0[0] + t1[0]) / 2, (t0[1] + t1[1]) / 2 + 0.012 * t0[3], t1[0], t1[1] - 0.016 * t1[3])
            band.lineTo(t1[0], t1[1] + 0.016 * t1[3])
            band.quadTo((t0[0] + t1[0]) / 2, (t0[1] + t1[1]) / 2 + 0.044 * t0[3], t0[0], t0[1] + 0.016 * t0[3])
            band.close()
            fr.c.drawPath(band, paint(shade(col, -0.35)))
            fr.c.drawPath(band, paint("#c89a48", a=0.8, stroke=1.0))
        fr.box(cam, (x0 - 0.78, x1 + 0.78), (y1 + 0.33, y1 + 0.355), (z - 0.012, z + 0.012), "#b89040", line=0.8)
        for fx in (x0 - 0.82, x1 + 0.82):
            q = cam.proj((fx, y1 + 0.342, z))
            if q[2] > 0.15:
                fr.c.drawCircle(q[0], q[1], 0.035 * q[3], paint("#c8a050"))
                fr.c.drawCircle(q[0], q[1], 0.035 * q[3], paint("#5a4018", stroke=1.0))

    # ---- from inside: the front wall around the window -------------------------------------------------------
    def _wall_in(self, fr, cam, T):
        if cam.fwd[2] >= 0:
            return
        x0, x1, y0, y1 = WIN
        c = fr.c
        hole = fr.poly(cam, [(x0, y0, Z_IN), (x1, y0, Z_IN), (x1, y1, Z_IN), (x0, y1, Z_IN)], colr="#000000", a=0.0)
        c.save()
        if hole is not None:
            c.clipPath(hole, skia.ClipOp.kDifference, True)
        wall = [(-3.2, 0, Z_IN + 0.001), (3.2, 0, Z_IN + 0.001), (3.2, 2.7, Z_IN + 0.001), (-3.2, 2.7, Z_IN + 0.001)]
        fr.poly(cam, wall, shader=lambda p: lin((0, p.getBounds().top()), (0, p.getBounds().bottom()),
                                                [argb("#4e4236"), argb("#6e5c4a"), argb("#584a3c")], [0, 0.6, 1]))
        plane_glow(fr, cam, (0.9, 1.0, Z_IN + 0.002), (1, 0, 0), (0, 1, 0), 2.2, "#ffb060", 0.20)    # lamplight from the room
        fr.poly(cam, [(-3.2, 0, Z_IN + 0.004), (3.2, 0, Z_IN + 0.004), (3.2, 0.12, Z_IN + 0.004), (-3.2, 0.12, Z_IN + 0.004)], colr="#3a3028")
        c.restore()
        # the deep reveals and the window board, then the radiator under it and the curtains
        fr.poly(cam, [(x0, y0, 0.0), (x0, y1, 0.0), (x0, y1, Z_IN), (x0, y0, Z_IN)], colr="#a89880")
        fr.poly(cam, [(x1, y0, 0.0), (x1, y1, 0.0), (x1, y1, Z_IN), (x1, y0, Z_IN)], colr="#8c7c66")
        fr.poly(cam, [(x0, y1, 0.0), (x1, y1, 0.0), (x1, y1, Z_IN), (x0, y1, Z_IN)], colr="#5e5244")
        fr.box(cam, (x0 - 0.04, x1 + 0.04), (y0 - 0.03, y0), (0.0, Z_IN + 0.05), "#d6cab4", line=1.0)
        fr.box(cam, (-0.50, 0.50), (0.14, 0.66), (Z_IN + 0.03, Z_IN + 0.10), "#e2ddd2", line=1.0)
        for k in range(1, 16):
            xx = -0.50 + k * 1.0 / 16
            fr.poly(cam, [(xx - 0.004, 0.16, Z_IN + 0.101), (xx + 0.004, 0.16, Z_IN + 0.101), (xx + 0.004, 0.64, Z_IN + 0.101), (xx - 0.004, 0.64, Z_IN + 0.101)],
                    colr="#a8a296")
        self._curtains(fr, cam)

    # ---- items: the house front, glass, hedges ----------------------------------------------------------------
    def items(self, cam, T):
        if self.inside(cam):
            kg = cam.view((0.0, 1.5, 0.0))[2]
            kw = cam.view((0.0, 1.5, Z_IN))[2]
            if cam.fwd[2] >= 0:
                return []
            return [(kg, lambda fr: (self._sash(fr, cam), self._glass(fr, cam, T)), "glass"),
                    (kw, lambda fr: self._wall_in(fr, cam, T), "wall_in")]
        hz = cam.view((0.0, 1.5, Z_OUT))[2]
        it = [(hz, lambda fr: self._house(fr, cam, T), "house")]
        # garden things stand between the wall and anyone in the garden: they draw right after the house and before
        # every person outside (the father is always well clear of them), so a hedge can never be painted over a man
        kf = hz - 0.01
        for i, ((x0, x1), (z0, z1), h) in enumerate(HEDGES):
            def fn(fr, x0=x0, x1=x1, z0=z0, z1=z1, h=h, i=i):
                self._hedge(fr, cam, x0, x1, z0, z1, h, i)
            it.append((kf - 0.001 * (i + 1), fn, f"hedge{i}"))

        def flowers(fr):
            for x, z, hh, colr in sorted(self.flowers, key=lambda f: -cam.view((f[0], 0.1, f[1]))[2]):
                a, b = cam.proj((x, 0.0, z)), cam.proj((x, hh, z))
                if b[2] < 0.25:
                    continue
                fr.c.drawLine(a[0], a[1], b[0], b[1], paint("#24401c", stroke=max(1.0, 0.008 * a[3])))
                cc = shade(colr, -0.45)
                for j in range(5):
                    q = cam.proj((x + 0.03 * math.cos(j * 1.3), hh - 0.02 * j, z + 0.03 * math.sin(j * 1.3)))
                    fr.c.drawCircle(q[0], q[1], max(1.0, 0.016 * q[3]), paint(cc))
                    fr.c.drawCircle(q[0], q[1], max(1.0, 0.016 * q[3]), paint(shade(cc, -0.6), stroke=max(0.6, 0.003 * q[3])))
        it.append((kf - 0.004, flowers, "flowers"))
        return it

    def _hedge(self, fr, cam, x0, x1, z0, z1, h, i):
        """A clipped box hedge: leaf texture on each visible face, night-dark, warm where a lantern reaches it."""
        C = cam.pos
        faces = [("front", (0, 0, -1), [(x0, 0, z0), (x1, 0, z0), (x1, h, z0), (x0, h, z0)], lambda p: (p[0], -p[1])),
                 ("top", (0, 1, 0), [(x0, h, z0), (x1, h, z0), (x1, h, z1), (x0, h, z1)], lambda p: (p[0], p[2])),
                 ("left", (-1, 0, 0), [(x0, 0, z0), (x0, 0, z1), (x0, h, z1), (x0, h, z0)], lambda p: (p[2], -p[1])),
                 ("right", (1, 0, 0), [(x1, 0, z0), (x1, 0, z1), (x1, h, z1), (x1, h, z0)], lambda p: (p[2], -p[1]))]
        lx = -1.02 if i == 0 else 1.02
        near = (x1 if i == 0 else x0)
        for name, n, pts, uv in faces:
            fc = [sum(q[j] for q in pts) / 4 for j in range(3)]
            if n[0] * (C[0] - fc[0]) + n[1] * (C[1] - fc[1]) + n[2] * (C[2] - fc[2]) <= 0:
                continue
            path = TX.plane(fr, cam, "hedge", pts, uv)
            if path is None:
                continue
            fr.c.drawPath(path, paint(NIGHT, a=0.62 if name != "top" else 0.50))
            fr.c.save()
            fr.c.clipPath(path, skia.ClipOp.kIntersect, True)
            if name == "top":
                plane_glow(fr, cam, (near, h + 0.001, (z0 + z1) / 2), (1, 0, 0), (0, 0, 1), 1.1, WARM, 0.28)
            elif name == "front":
                plane_glow(fr, cam, (near, h * 0.7, z0 - 0.001), (1, 0, 0), (0, 1, 0), 0.9, WARM, 0.16)
            elif (name == "right") == (i == 0):
                plane_glow(fr, cam, (near + (0.001 if i == 0 else -0.001), h * 0.7, (z0 + z1) / 2), (0, 0, 1), (0, 1, 0), 0.9, WARM, 0.22)
            fr.c.restore()
            fr.c.drawPath(path, paint("#050a06", stroke=1.6, a=0.6))
        del lx
        # an untrimmed tuft where he stopped cutting (left hedge, right end), on top of the hedge, never past its ends
        if i == 0:
            rnd = random.Random(5)
            for _ in range(22):
                x, y, z = rnd.uniform(x1 - 0.45, x1 - 0.08), h + rnd.uniform(0.0, 0.07), rnd.uniform(z0 + 0.08, z1 - 0.08)
                q = cam.proj((x, y, z))
                if cam.view((x, y, z))[2] > 0.3:
                    r = rnd.uniform(0.02, 0.035) * q[3]
                    fr.c.drawCircle(q[0], q[1], r, paint(rnd.choice(["#24401c", "#2e4c22", "#1e3818"])))

    def _outer_reveals(self, fr, cam):
        x0, x1, y0, y1 = WIN
        fr.poly(cam, [(x0, y0, Z_OUT), (x0, y1, Z_OUT), (x0, y1, 0.0), (x0, y0, 0.0)], colr="#5a3428")
        fr.poly(cam, [(x1, y0, Z_OUT), (x1, y1, Z_OUT), (x1, y1, 0.0), (x1, y0, 0.0)], colr="#4a2a22")
        fr.poly(cam, [(x0, y1, Z_OUT), (x1, y1, Z_OUT), (x1, y1, 0.0), (x0, y1, 0.0)], colr="#2e1a16")
        fr.box(cam, (x0 - 0.08, x1 + 0.08), (y0 - 0.07, y0), (Z_OUT - 0.07, 0.0), "#7c776c", line=1.2)        # stone sill

    def _house(self, fr, cam, T):
        x0, x1, y0, y1 = WIN
        c = fr.c
        wall = [(WALL_X[0], 0, Z_OUT), (WALL_X[1], 0, Z_OUT), (WALL_X[1], EAVE, Z_OUT), (WALL_X[0], EAVE, Z_OUT)]
        hole = fr.poly(cam, [(x0, y0, Z_OUT), (x1, y0, Z_OUT), (x1, y1, Z_OUT), (x0, y1, Z_OUT)], colr="#000000", a=0.0)
        c.save()
        if hole is not None:
            c.clipPath(hole, skia.ClipOp.kDifference, True)
        wp = TX.plane(fr, cam, "brick", wall, lambda p: (p[0], -p[1]))
        if wp is not None:
            c.drawPath(wp, paint(NIGHT, a=0.66))
        for L in LANTERNS:                                                     # warm pools on the brick round each lantern
            plane_glow(fr, cam, (L[0], L[1] - 0.10, Z_OUT - 0.002), (1, 0, 0), (0, 1, 0), 1.3, WARM, 0.40)
        plane_glow(fr, cam, (0.0, 0.5, Z_OUT - 0.002), (1, 0, 0), (0, 1, 0), 1.6, WARM, 0.10)       # and under the sill
        c.restore()
        if cam.pos[0] < WALL_X[0]:
            sp = fr.poly(cam, [(WALL_X[0], 0, Z_OUT), (WALL_X[0], 0, 8.0), (WALL_X[0], EAVE, 8.0), (WALL_X[0], EAVE, Z_OUT)], colr="#1a1416")
            del sp
        self._outer_reveals(fr, cam)
        for L in LANTERNS:                                                     # the lanterns' light on the reveals
            plane_glow(fr, cam, (x0 if L[0] < 0 else x1, 1.6, -0.06), (0, 0, 1), (0, 1, 0), 0.5, WARM, 0.25)
        fr.box(cam, (x0 - 0.06, x1 + 0.06), (y1, y1 + 0.075), (Z_OUT - 0.01, Z_OUT + 0.01), "#4a2a22", line=1.0)   # soldier course
        self._glass(fr, cam, T)
        self._sash(fr, cam)
        fr.box(cam, (x0 - 0.08, x1 + 0.08), (y0 - 0.07, y0), (Z_OUT - 0.07, 0.0), "#8a8478", line=1.2)        # stone sill
        for L in LANTERNS:
            self._lantern(fr, cam, L)
        self._upstairs(fr, cam, T)
        fr.box(cam, (WALL_X[0] - 0.2, WALL_X[1] + 0.2), (EAVE, EAVE + 0.2), (Z_OUT - 0.3, Z_OUT), "#8e8a82", line=1.2)
        fr.box(cam, (WALL_X[0] - 0.2, WALL_X[1] + 0.2), (EAVE - 0.08, EAVE + 0.02), (Z_OUT - 0.38, Z_OUT - 0.28), "#1a1a1e", line=1.0)
        fr.box(cam, (-4.32, -4.24), (0.0, EAVE), (Z_OUT - 0.1, Z_OUT - 0.02), "#1a1a1e", line=1.0)
        fr.poly(cam, [(WALL_X[0] - 0.3, EAVE + 0.2, Z_OUT - 0.4), (WALL_X[1] + 0.3, EAVE + 0.2, Z_OUT - 0.4),
                      (WALL_X[1] + 0.3, EAVE + 1.9, 3.0), (WALL_X[0] - 0.3, EAVE + 1.9, 3.0)], colr="#1c1a20", outline="#0a080c", line=1.2)
        # rain running off the gutter: a few strings of drops
        for k, gx in enumerate((-3.1, -1.9, -0.7, 0.9, 2.2, 3.4)):
            for j in range(4):
                yy = EAVE - 0.1 - ((T * 6.5 + k * 0.37 + j * 0.31) % 1.0) * EAVE
                a = cam.proj((gx, yy, Z_OUT - 0.33))
                if a[2] < 0.5:
                    continue
                b = cam.proj((gx, yy + 0.22, Z_OUT - 0.33))
                c.drawLine(a[0], a[1], b[0], b[1], paint("#9fb0cc", a=0.35, stroke=max(0.8, 0.006 * a[3])))

    def _lantern(self, fr, cam, L):
        x, y, z = L
        if cam.view(L)[2] < 0.3:
            return
        fr.box(cam, (x - 0.02, x + 0.02), (y - 0.02, y + 0.02), (Z_OUT - 0.06, Z_OUT), "#15151a", line=0.8)       # bracket
        fr.box(cam, (x - 0.07, x + 0.07), (y - 0.12, y + 0.12), (z - 0.07, z + 0.07), "#ffe3a8", line=1.4)        # glass box
        for dx in (-0.07, 0.07):
            for dz in (-0.07, 0.07):
                fr.box(cam, (x + dx - 0.008, x + dx + 0.008), (y - 0.13, y + 0.13), (z + dz - 0.008, z + dz + 0.008), "#15151a", line=0.6)
        fr.poly(cam, [(x - 0.10, y + 0.12, z - 0.10), (x + 0.10, y + 0.12, z - 0.10), (x, y + 0.24, z)], colr="#15151a")
        fr.poly(cam, [(x - 0.10, y + 0.12, z + 0.10), (x - 0.10, y + 0.12, z - 0.10), (x, y + 0.24, z)], colr="#0e0e12")
        q = cam.proj((x, y, z))
        fr.glow(q[0], q[1], 0.55 * q[3], "#ffc27a", a=0.55)
        fr.glow(q[0], q[1], 0.18 * q[3], "#fff2d0", a=0.6)

    def _sash(self, fr, cam):
        x0, x1, y0, y1 = WIN
        fw = 0.055
        for a, b, cc, d in ((x0, x0 + fw, y0, y1), (x1 - fw, x1, y0, y1), (x0, x1, y1 - fw, y1), (x0, x1, y0, y0 + fw)):
            fr.poly(cam, [(a, cc, -0.012), (b, cc, -0.012), (b, d, -0.012), (a, d, -0.012)], colr="#b8b4aa", outline="#4a463e", line=1.0)
        fr.poly(cam, [(x0 + fw, y0 + fw, -0.012), (x1 - fw, y0 + fw, -0.012), (x1 - fw, y0 + fw + 0.012, -0.003), (x0 + fw, y0 + fw + 0.012, -0.003)],
                colr="#8a8478")

    def _glass(self, fr, cam, T):
        x0, x1, y0, y1 = WIN
        c = fr.c
        if cam.view((0.0, 1.5, 0.0))[2] < 0.1:
            return
        g = self._glass_path(fr, cam)
        if g is None:
            return
        c.save()
        c.clipPath(g, skia.ClipOp.kIntersect, True)
        b = g.getBounds()
        q0 = cam.proj((0.0, 1.5, 0.0))
        # a faint cool sheen and one soft diagonal band: no readable reflection
        c.drawPath(g, paint(shader=lin((b.left(), b.top()), (b.left(), b.bottom()), [argb("#9ab0d0", 0.08), argb("#9ab0d0", 0.03), argb("#9ab0d0", 0.02)], [0, 0.55, 1])))
        for (u0, u1, wd, al) in ((0.25, 0.85, 0.10, 0.05), (0.62, 1.10, 0.035, 0.04)):
            p0 = cam.proj((x0 + u0, y1, 0.0))
            p1 = cam.proj((x0 + u1, y0, 0.0))
            band = skia.Path()
            wq = wd * p0[3]
            band.moveTo(p0[0] - wq, p0[1])
            band.lineTo(p0[0] + wq, p0[1])
            band.lineTo(p1[0] + wq, p1[1])
            band.lineTo(p1[0] - wq, p1[1])
            band.close()
            c.drawPath(band, paint("#ffffff", a=al, blur=0.04 * p0[3]))
        if self.inside(cam):                                       # at night a lit room mirrors faintly in its own window
            m = (LAMP[0], 1.55, -LAMP[1])
            if cam.view(m)[2] > 0.3:
                q = cam.proj(m)
                fr.glow(q[0], q[1], 0.5 * q[3], "#ffc27a", a=0.10)
        # rain on the outer face: beads, and a few drops running down
        for x, y, r in self.beads:
            q = cam.proj((x, y, 0.0))
            rr = max(0.8, r * q[3])
            c.drawCircle(q[0], q[1], rr, paint("#c8d4e6", a=0.16))
            c.drawCircle(q[0], q[1], rr, paint("#1a2030", a=0.20, stroke=max(0.5, rr * 0.25)))
            c.drawCircle(q[0] - rr * 0.3, q[1] - rr * 0.3, rr * 0.3, paint("#ffffff", a=0.45))
        for x, sp, ph, r in self.drips:
            span = y1 - y0 - 0.1
            yy = y1 - 0.05 - ((T * sp + ph) % span)
            q = cam.proj((x, yy, 0.0))
            t = cam.proj((x + 0.004, yy + 0.16, 0.0))
            c.drawLine(q[0], q[1], t[0], t[1], paint("#c8d4e6", a=0.12, stroke=max(0.8, r * 1.2 * q[3])))
            c.drawCircle(q[0], q[1], max(1.0, r * q[3]), paint("#d8e2f0", a=0.30))
            c.drawCircle(q[0] - 0.3 * r * q[3], q[1] - 0.3 * r * q[3], max(0.6, 0.35 * r * q[3]), paint("#ffffff", a=0.5))
        # fog on his side of the pane: round the pressed forehead, a breath patch under the nose, the palm print and its smear
        J = self.stranger_head(T)
        Hd = rig.Head(cam, J["head"], J["Bh"], J["R"], rig.LOOK["stranger"].get("head_shape"))
        fh = Hd.surf(0.0, 0.50)
        q = cam.proj((fh[0], fh[1], 0.0))
        c.drawOval(skia.Rect(q[0] - 0.13 * q[3], q[1] - 0.07 * q[3], q[0] + 0.13 * q[3], q[1] + 0.07 * q[3]), paint("#f4f6f8", a=0.16, blur=0.03 * q[3]))
        nose = Hd.surf(0.0, -0.30)
        br = 0.5 + 0.5 * math.sin(T * 2 * math.pi / 4.2 - 1.2)
        q = cam.proj((nose[0], nose[1] - 0.02, 0.0))
        c.drawOval(skia.Rect(q[0] - 0.09 * q[3], q[1] - 0.05 * q[3], q[0] + 0.09 * q[3], q[1] + 0.06 * q[3]),
                   paint("#f4f6f8", a=0.06 + 0.12 * br, blur=0.035 * q[3]))
        if T >= self.T_FLAT - 0.2:
            fl = self.flip(T)
            for tt, a in self._prints(T):
                hs = self.hand_world(tt, fl)
                if hs is None:
                    continue
                path = self._hand_outline(cam, hs)
                c.drawPath(path, paint("#eef2f6", a=a, stroke=0.012 * q[3], blur=0.008 * q[3]))
                c.drawPath(path, paint("#eef2f6", a=a * 0.5, blur=0.01 * q[3]))
        c.restore()
        del q0

    def _prints(self, T):
        """(time of the hand pose, fog alpha): the current contact, then the smear left by the slide, evaporating."""
        out = [(T, 0.10 * win(T, self.T_FLAT - 0.2, self.T_FLAT + 0.6, "io"))]
        k = 0
        while True:
            tt = self.T_SLIDE + 0.26 * k
            k += 1
            if tt > min(T - 0.3, self.T_SLID):
                break
            age = T - tt
            out.append((tt, 0.07 * min(1.0, (age - 0.3) / 0.5) * max(0.0, 1 - age / 6.0)))
        return out

    def _hand_outline(self, cam, hs):
        palm, chains, thumb = LK.hand_points(hs[0], hs[1], hs[2], hs[3], hs[4])
        pr = lambda q: cam.proj((q[0], q[1], 0.0))                                   # noqa: E731
        segs = [rig.smooth([pr(q)[:2] for q in palm], k=0.6)]
        for ch, rr in chains + [thumb]:
            for i in range(len(ch) - 1):
                a, b = pr(ch[i]), pr(ch[i + 1])
                segs.append(rig.capsule(a[:2], rr * a[3], b[:2], rr * b[3]))
        return rig.union(*segs)

    def _upstairs(self, fr, cam, T):
        """The bedroom window above: dark glass, the sheer curtain, a faint amber nightlight behind it."""
        x0, x1, y0, y1 = UPWIN
        g = fr.poly(cam, [(x0, y0, Z_OUT + 0.06), (x1, y0, Z_OUT + 0.06), (x1, y1, Z_OUT + 0.06), (x0, y1, Z_OUT + 0.06)], colr="#0c0e18")
        if g is None:
            return
        c = fr.c
        c.save()
        c.clipPath(g, skia.ClipOp.kIntersect, True)
        q = cam.proj(((x0 + x1) / 2 + 0.2, y0 + 0.3, Z_OUT + 1.2))
        fr.glow(q[0], q[1], 1.0 * q[3], "#ffb060", a=0.22)
        sway = 0.03 * math.sin(T * 0.9)
        for i in range(7):
            xa = x0 + 0.05 + i * 0.12
            pts = [(xa, y1, Z_OUT + 0.07), (xa + 0.10, y1, Z_OUT + 0.07), (xa + 0.10 + sway * (i / 7), y0 + 0.05, Z_OUT + 0.07),
                   (xa + sway * (i / 7), y0 + 0.05, Z_OUT + 0.07)]
            fr.poly(cam, pts, colr="#c8c2b8", a=0.30 if i % 2 else 0.22)
        c.restore()
        fw = 0.05
        for a, bb, cc, d in ((x0 - fw, x0, y0 - fw, y1 + fw), (x1, x1 + fw, y0 - fw, y1 + fw), (x0 - fw, x1 + fw, y1, y1 + fw), (x0, x1, (y0 + y1) / 2 - 0.02, (y0 + y1) / 2 + 0.02)):
            fr.poly(cam, [(a, cc, Z_OUT - 0.005), (bb, cc, Z_OUT - 0.005), (bb, d, Z_OUT - 0.005), (a, d, Z_OUT - 0.005)], colr="#9a968e", outline="#3a362e", line=1.0)
        fr.box(cam, (x0 - 0.08, x1 + 0.08), (y0 - 0.12, y0 - 0.05), (Z_OUT - 0.07, Z_OUT), "#6a665e", line=1.0)

    # ------------------------------------------------------------------------------------------------------------
    def overlay(self, fr, cam, T, outs):
        if not self.inside(cam):                                   # rain between the lens and the house: thin, faint
            self.rain_near.draw(fr, cam, T, light=self._near_lantern(cam), amax=0.26, zmin=0.7, wmax=1.4)

    def post(self, fr, cam, T):
        fr.c.drawPaint(paint("#1c2848", a=0.10, blend="mul"))
        vignette(fr, 0.55)


# =================================================================================================================
class Bedroom:
    """Upstairs at night: the wife asleep on her side facing the crib, the baby asleep under a turning mobile, the
    bedside lamp low, a plug-in nightlight by the crib, a star projector on the dresser, rain on the window."""
    name = "bedroom"
    gaze = {}
    allow = []
    X0, X1, Z0, Z1, HT = -1.56, 2.6, 0.9, 4.6, 2.5
    WINF = (-0.40, 0.90, 0.95, 2.15)                  # window on the far wall (z = Z0): x0, x1, y0, y1
    LAMPB = (-1.31, 0.60, 1.66)                       # bedside lamp base, on the nightstand
    NITE = (-1.545, 0.34, 4.05)                       # plug-in nightlight on the left wall by the crib
    PROJ = (1.55, 0.88, 1.14)                         # star projector on the dresser
    CRIB = ((0.05, 1.18), (3.25, 3.88))
    BED = ((-1.50, 0.75), (2.0, 3.1), 0.55)

    def __init__(self, M):
        self.M = M
        r = random.Random(17)
        self.stars = []                                                    # projected stars on the ceiling and walls
        for _ in range(46):
            a, el = r.uniform(0, 2 * math.pi), r.uniform(0.25, 1.2)
            self.stars.append((a, el, r.uniform(0.6, 1.0), r.uniform(0, 6)))
        self.rain = Rain(n=420, box=((-1.2, 1.8), (0.4, 3.6), (-6.0, 0.5)), speed=8.0, seed=21)
        x0, x1, y0, y1 = self.WINF
        self.beads = [(r.uniform(x0 + 0.06, x1 - 0.06), r.uniform(y0 + 0.06, y1 - 0.06), r.uniform(0.003, 0.007)) for _ in range(70)]

    def nearest_light(self, p):
        return (p[0] + 0.6, 1.5, p[2] + 1.2)

    def solids(self):
        return {}

    def wife(self, T):
        br = math.sin(T * 2 * math.pi / 4.6)
        p = dict(x=0.0, z=0.0, yaw=0.0, lid=0.0, brow=0.1, mouth=0.02, head_roll=0.0, aR=(30.0, 8.0, 60.0), aL=(30.0, 8.0, 60.0),
                 breath=0.5 + 0.5 * br)
        at = (-0.35, 0.71 + 0.004 * br, 2.55)
        p["lie"] = ([((0.0, 1.0, 0.0), 180.0), ((0.0, 0.0, 1.0), 90.0)], at)        # on her side, facing the crib
        p["plant"] = "none"
        return ("wife", "wife", p, None, None, None)

    def cast(self, T):
        return [self.wife(T)]

    def grade(self, fr, cam, T, pid, o):
        if o.get("culled") or not o.get("head"):
            return
        hx, hy = o["head"][:2]
        r = max(8.0, o["head_r"])
        p = skia.Paint()
        p.setBlendMode(skia.BlendMode.kModulate)
        p.setShader(rad((hx, hy), r * 5.0, [argb("#ffffff"), argb("#f4ece4"), argb("#9aa4c0")], [0, 0.26, 1]))
        fr.c.drawPaint(p)
        q = skia.Paint()
        q.setBlendMode(skia.BlendMode.kSrcATop)
        q.setShader(rad((hx + 0.3 * r, hy), r * 1.8, [argb("#ffd8a8", 0.20), argb("#ffd8a8", 0.10), argb("#ffd8a8", 0)], [0, 0.5, 1]))
        fr.c.drawPaint(q)

    # ---- the room shell ----------------------------------------------------------------------------------------
    def _wall(self, fr, cam, pts, uv, base):
        path = TX.plane(fr, cam, "wallpaper", pts, uv)
        if path is not None:
            fr.c.drawPath(path, paint("#0a0e1c", a=0.42))
        return path

    def bg(self, fr, cam, T):
        X0, X1, Z0, Z1, HT = self.X0, self.X1, self.Z0, self.Z1, self.HT
        c = fr.c
        c.drawPaint(paint("#0a0c14"))
        fr.poly(cam, [(X0, HT, Z0), (X1, HT, Z0), (X1, HT, Z1), (X0, HT, Z1)], colr="#262836")                       # ceiling
        TX.plane(fr, cam, "wood", [(X0, 0.0, Z0), (X1, 0.0, Z0), (X1, 0.0, Z1), (X0, 0.0, Z1)], lambda p: (p[0], p[2]))
        fr.poly(cam, [(X0, 0.001, Z0), (X1, 0.001, Z0), (X1, 0.001, Z1), (X0, 0.001, Z1)], colr="#0a0e1c", a=0.42)
        C = cam.pos
        walls = [("far", (0, 0, 1), [(X0, 0, Z0), (X1, 0, Z0), (X1, HT, Z0), (X0, HT, Z0)], lambda p: (p[0], -p[1])),
                 ("left", (1, 0, 0), [(X0, 0, Z1), (X0, 0, Z0), (X0, HT, Z0), (X0, HT, Z1)], lambda p: (-p[2], -p[1])),
                 ("right", (-1, 0, 0), [(X1, 0, Z0), (X1, 0, Z1), (X1, HT, Z1), (X1, HT, Z0)], lambda p: (p[2], -p[1])),
                 ("near", (0, 0, -1), [(X1, 0, Z1), (X0, 0, Z1), (X0, HT, Z1), (X1, HT, Z1)], lambda p: (-p[0], -p[1]))]
        x0, x1, y0, y1 = self.WINF
        for name, n, pts, uv in walls:
            fc = [sum(q[j] for q in pts) / 4 for j in range(3)]
            if n[0] * (C[0] - fc[0]) + n[2] * (C[2] - fc[2]) <= 0:
                continue
            if name == "far":                                                  # the window hole
                hole = fr.poly(cam, [(x0, y0, Z0), (x1, y0, Z0), (x1, y1, Z0), (x0, y1, Z0)], colr="#000000", a=0.0)
                c.save()
                if hole is not None:
                    c.clipPath(hole, skia.ClipOp.kDifference, True)
                self._wall(fr, cam, pts, uv, "#000000")
                c.restore()
            else:
                self._wall(fr, cam, pts, uv, "#000000")
        # skirting boards and the picture rail
        for a, b in (((X0, Z0), (X1, Z0)), ((X0, Z0), (X0, Z1)), ((X1, Z0), (X1, Z1))):
            off = (0.0, 0.006) if a[1] == b[1] else ((0.006, 0.0) if a[0] == X0 else (-0.006, 0.0))
            fr.poly(cam, [(a[0] + off[0], 0, a[1] + off[1]), (b[0] + off[0], 0, b[1] + off[1]), (b[0] + off[0], 0.12, b[1] + off[1]), (a[0] + off[0], 0.12, a[1] + off[1])],
                    colr="#c8c0b0", outline="#5a5448", line=1.0)
            fr.poly(cam, [(a[0] + off[0], 1.98, a[1] + off[1]), (b[0] + off[0], 1.98, b[1] + off[1]), (b[0] + off[0], 2.01, b[1] + off[1]), (a[0] + off[0], 2.01, a[1] + off[1])],
                    colr="#b8b0a0")
        self._window(fr, cam, T)
        self._door(fr, cam)
        self._wall_decor(fr, cam)
        self._dresser(fr, cam, T)
        self._nightstand(fr, cam)
        self._rug(fr, cam)
        self._lights(fr, cam, T)

    def _window(self, fr, cam, T):
        x0, x1, y0, y1 = self.WINF
        z = self.Z0
        g = fr.poly(cam, [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], colr="#0a1222")
        if g is None:
            return
        c = fr.c
        c.save()
        c.clipPath(g, skia.ClipOp.kIntersect, True)
        b = g.getBounds()
        c.drawPath(g, paint(shader=lin((b.left(), b.top()), (b.left(), b.bottom()), [argb("#050a16"), argb("#18223a")])))
        for hx, hw, hh in ((-7.0, 6.0, 5.0), (0.5, 5.5, 4.6), (7.5, 6.0, 5.2)):                 # across the street
            fr.poly(cam, [(hx - hw / 2, 0, -21), (hx + hw / 2, 0, -21), (hx + hw / 2, hh, -21), (hx, hh + 2.2, -21), (hx - hw / 2, hh, -21)], colr="#0c1018")
            q = cam.proj((hx - 1.2, 1.7, -20.9))
            fr.glow(q[0], q[1], 1.3 * q[3], "#ffb45a", a=0.16)
        q = cam.proj((-3.0, 4.4, -12.0))                                                         # the street lamp
        fr.glow(q[0], q[1], 3.0 * q[3], "#ffb45a", a=0.35)
        self.rain.draw(fr, cam, T, light=(-3.0, 4.4, -12.0), amax=0.35, zmin=0.3, wmax=1.4)
        for bx, by, br in self.beads:
            q = cam.proj((bx, by, z + 0.001))
            rr = max(0.8, br * q[3])
            c.drawCircle(q[0], q[1], rr, paint("#c8d4e6", a=0.16))
            c.drawCircle(q[0] - 0.3 * rr, q[1] - 0.3 * rr, 0.3 * rr, paint("#ffffff", a=0.4))
        c.restore()
        # the frame, glazing bars, the sill
        fw = 0.05
        zf = z + 0.012
        for a, bb, cc, d in ((x0 - fw, x0, y0 - fw, y1 + fw), (x1, x1 + fw, y0 - fw, y1 + fw), (x0 - fw, x1 + fw, y1, y1 + fw),
                             (x0 - fw, x1 + fw, y0 - fw, y0), ((x0 + x1) / 2 - 0.018, (x0 + x1) / 2 + 0.018, y0, y1)):
            fr.poly(cam, [(a, cc, zf), (bb, cc, zf), (bb, d, zf), (a, d, zf)], colr="#d8d2c6", outline="#5a5448", line=1.0)
        fr.box(cam, (x0 - 0.10, x1 + 0.10), (y0 - 0.09, y0 - 0.05), (z, z + 0.14), "#e0d8ca", line=1.0)
        # a sheer curtain across part of it, stirring; heavy dusk-blue drapes either side
        sway = 0.035 * math.sin(T * 0.9)
        for i in range(6):
            xa = x0 + 0.02 + i * 0.11
            pts = [(xa, y1 + 0.20, z + 0.07), (xa + 0.11, y1 + 0.20, z + 0.07), (xa + 0.11 + sway * (i / 6), y0 - 0.12, z + 0.09 + sway),
                   (xa + sway * (i / 6), y0 - 0.12, z + 0.09 + sway)]
            fr.poly(cam, pts, colr="#e8e4dc", a=0.30 if i % 2 else 0.20)
        for side in (-1, 1):
            a0, a1 = (x0 - 0.45, x0 + 0.02) if side < 0 else (x1 - 0.02, x1 + 0.45)
            self._drape(fr, cam, a0, a1, 0.15, y1 + 0.25, z + 0.10, "#3e4c6a")
        fr.box(cam, (x0 - 0.55, x1 + 0.55), (y1 + 0.25, y1 + 0.28), (z + 0.09, z + 0.12), "#8a7a5a", line=0.8)

    def _drape(self, fr, cam, a0, a1, yb, yt, z, col, folds=6):
        """One curtain panel: soft vertical folds as a gradient across the panel."""
        P = [(a0, yt, z), (a1, yt, z), (a1, yb, z + 0.02), (a0, yb, z + 0.02)]
        path = fr.poly(cam, P, colr=col, a=0.0)
        if path is None or cam.view((a0, yt, z))[2] < 0.1 or cam.view((a1, yt, z))[2] < 0.1:
            return
        L, R = cam.proj((a0, (yb + yt) / 2, z)), cam.proj((a1, (yb + yt) / 2, z))
        cols, pos = [], []
        for k in range(folds * 2 + 1):
            cols.append(argb(shade(col, 0.14 if k % 2 else -0.30)))
            pos.append(k / (folds * 2))
        fr.c.drawPath(path, paint(shader=lin((L[0], L[1]), (R[0], R[1]), cols, pos)))
        fr.c.drawPath(path, paint(shade(col, -0.7), stroke=1.0))

    def _door(self, fr, cam):
        """The door to the landing on the right wall, ajar: warm light down its edge and across the floor."""
        X1 = self.X1
        a0, a1 = 3.62, 4.40
        if cam.view((X1, 1.0, (a0 + a1) / 2))[2] < 0.2:
            return
        fr.poly(cam, [(X1 - 0.002, 0, a0), (X1 - 0.002, 0, a1), (X1 - 0.002, 2.05, a1), (X1 - 0.002, 2.05, a0)], colr="#ffcf8a", a=0.85)
        op = 0.22
        ea = a1 - (a1 - a0) * math.cos(op * math.pi / 2)
        n_in = (a1 - a0) * math.sin(op * math.pi / 2)
        fr.poly(cam, [(X1, 0, a1), (X1, 2.05, a1), (X1 - n_in, 2.05, ea), (X1 - n_in, 0, ea)], colr="#7a5a40", outline="#2a1e14", line=1.2)
        fr.poly(cam, [(X1 - 0.003, 0.002, a0), (X1 - 1.6, 0.002, a0 - 0.3), (X1 - 1.4, 0.002, a0 + 0.25)], colr="#ffb060", a=0.16, blur=6)

    def _wall_decor(self, fr, cam):
        X0, Z0 = self.X0, self.Z0
        # a framed print above the bed (left wall) and a shelf of toys above the crib
        fr.poly(cam, [(X0 + 0.01, 1.30, 2.18), (X0 + 0.01, 1.30, 2.92), (X0 + 0.01, 1.86, 2.92), (X0 + 0.01, 1.86, 2.18)], colr="#2a2018")
        fr.poly(cam, [(X0 + 0.015, 1.35, 2.23), (X0 + 0.015, 1.35, 2.87), (X0 + 0.015, 1.81, 2.87), (X0 + 0.015, 1.81, 2.23)], colr="#8a9ab0")
        fr.poly(cam, [(X0 + 0.017, 1.35, 2.23), (X0 + 0.017, 1.35, 2.87), (X0 + 0.017, 1.52, 2.87), (X0 + 0.017, 1.60, 2.62), (X0 + 0.017, 1.50, 2.23)], colr="#4a6a5a")
        fr.poly(cam, [(X0 + 0.018, 1.35, 2.23), (X0 + 0.018, 1.35, 2.87), (X0 + 0.018, 1.45, 2.87), (X0 + 0.018, 1.53, 2.40), (X0 + 0.018, 1.44, 2.23)], colr="#2e4a3e")
        q = cam.proj((X0 + 0.019, 1.68, 2.72))
        if q[2] > 0.2:
            fr.c.drawCircle(q[0], q[1], 0.05 * q[3], paint("#f4e8c0"))
        fr.box(cam, (X0, X0 + 0.20), (1.55, 1.58), (3.20, 3.95), "#e2dacc", line=0.8)
        fr.box(cam, (X0 + 0.04, X0 + 0.16), (1.58, 1.76), (3.28, 3.40), "#a8784a", line=0.8)          # a bear
        q = cam.proj((X0 + 0.10, 1.82, 3.34))
        if q[2] > 0.2:
            fr.c.drawCircle(q[0], q[1], 0.07 * q[3], paint("#a8784a"))
            fr.c.drawCircle(q[0], q[1], 0.07 * q[3], paint("#4a3020", stroke=1.0))
            for ex in (-0.05, 0.05):
                e = cam.proj((X0 + 0.10, 1.88, 3.34 + ex))
                fr.c.drawCircle(e[0], e[1], 0.025 * q[3], paint("#a8784a"))
        for k, colr in enumerate(("#c86a5a", "#5a8ac8", "#e0c060", "#6aa86a")):                         # little books
            fr.box(cam, (X0 + 0.03, X0 + 0.17), (1.58, 1.58 + 0.16 + 0.02 * (k % 2)), (3.55 + 0.045 * k, 3.59 + 0.045 * k), colr, line=0.6)
        fr.box(cam, (X0 + 0.04, X0 + 0.16), (1.58, 1.70), (3.80, 3.90), "#f0e8f0", line=0.6)            # a bunny
        # two small framed photos on the far wall by the window
        for x, y in ((-1.05, 1.45), (-0.80, 1.20)):
            fr.poly(cam, [(x, y, Z0 + 0.01), (x + 0.20, y, Z0 + 0.01), (x + 0.20, y + 0.26, Z0 + 0.01), (x, y + 0.26, Z0 + 0.01)], colr="#2a2018")
            fr.poly(cam, [(x + 0.02, y + 0.02, Z0 + 0.012), (x + 0.18, y + 0.02, Z0 + 0.012), (x + 0.18, y + 0.24, Z0 + 0.012), (x + 0.02, y + 0.24, Z0 + 0.012)],
                    colr="#c8b090")

    def _dresser(self, fr, cam, T):
        x0, x1, z0, z1, h = 1.25, 2.45, self.Z0, self.Z0 + 0.48, 0.88
        fr.box(cam, (x0, x1), (0.0, h), (z0, z1), "#e6e0d4", line=1.2)
        for k in range(3):
            y = 0.10 + k * 0.26
            fr.poly(cam, [(x0 + 0.04, y, z1 + 0.003), (x1 - 0.04, y, z1 + 0.003), (x1 - 0.04, y + 0.22, z1 + 0.003), (x0 + 0.04, y + 0.22, z1 + 0.003)],
                    colr="#d8d0c2", outline="#7a7266", line=1.0)
            for kx in (x0 + 0.3, x1 - 0.3):
                q = cam.proj((kx, y + 0.11, z1 + 0.01))
                if q[2] > 0.2:
                    fr.c.drawCircle(q[0], q[1], max(1.0, 0.016 * q[3]), paint("#b89a5a"))
        fr.box(cam, (2.05, 2.30), (h, h + 0.24), (z0 + 0.10, z0 + 0.13), "#2a2018", line=0.8)            # a photo
        fr.poly(cam, [(2.07, h + 0.02, z0 + 0.131), (2.28, h + 0.02, z0 + 0.131), (2.28, h + 0.22, z0 + 0.131), (2.07, h + 0.22, z0 + 0.131)], colr="#c8a888")
        fr.box(cam, (2.32, 2.40), (h, h + 0.12), (z0 + 0.20, z0 + 0.26), "#f0f0f0", line=0.6)            # baby monitor
        q = cam.proj((2.36, h + 0.10, z0 + 0.262))
        if q[2] > 0.2:
            fr.glow(q[0], q[1], 0.05 * q[3], "#5aff7a", a=0.8)
        x, y, z = self.PROJ                                                                     # the star projector
        fr.box(cam, (x - 0.07, x + 0.07), (y, y + 0.04), (z - 0.07, z + 0.07), "#e8e4dc", line=0.8)
        q = cam.proj((x, y + 0.08, z))
        if q[2] > 0.2:
            fr.c.drawCircle(q[0], q[1], 0.065 * q[3], paint("#bcd4ff", a=0.9))
            fr.glow(q[0], q[1], 0.35 * q[3], "#9ec0ff", a=0.35)

    def _nightstand(self, fr, cam):
        x, y, z = self.LAMPB
        fr.box(cam, (-1.54, -1.08), (0.0, 0.60), (1.40, 1.92), "#5a3e2c", line=1.2)
        fr.poly(cam, [(-1.08 + 0.003, 0.36, 1.44), (-1.08 + 0.003, 0.36, 1.88), (-1.08 + 0.003, 0.54, 1.88), (-1.08 + 0.003, 0.54, 1.44)],
                colr="#4a3222", outline="#2a1a10", line=1.0)
        fr.box(cam, (x - 0.07, x + 0.07), (y, y + 0.05), (z - 0.07, z + 0.07), "#8a7050", line=0.8)
        fr.box(cam, (x - 0.012, x + 0.012), (y + 0.05, y + 0.27), (z - 0.012, z + 0.012), "#8a7050", line=0.6)
        fr.box(cam, (-1.22, -1.12), (y, y + 0.07), (1.76, 1.86), "#2a2a30", line=0.6)                     # the clock
        q = cam.proj((-1.119, y + 0.035, 1.81))
        if q[2] > 0.2:
            fr.c.drawRect(skia.Rect(q[0] - 0.035 * q[3], q[1] - 0.015 * q[3], q[0] + 0.035 * q[3], q[1] + 0.015 * q[3]), paint("#ff5a3a", a=0.9))
            fr.glow(q[0], q[1], 0.08 * q[3], "#ff5a3a", a=0.4)
        fr.box(cam, (-1.50, -1.30), (y, y + 0.04), (1.44, 1.58), "#6a3a3a", line=0.6)                     # a book
        fr.box(cam, (-1.20, -1.15), (y, y + 0.11), (1.46, 1.51), "#b8c8d8", line=0.6, a=0.7)              # a glass of water

    def _rug(self, fr, cam):
        x0, z0 = -0.95, 2.70
        pts = [(x0, 0.004, z0), (x0 + 2.2, 0.004, z0), (x0 + 2.2, 0.004, z0 + 1.6), (x0, 0.004, z0 + 1.6)]
        p = TX.plane(fr, cam, "rug", pts, lambda q: (q[0] - x0, q[2] - z0))
        if p is not None:
            fr.c.drawPath(p, paint("#0a0e1c", a=0.38))

    def _lights(self, fr, cam, T):
        """The practicals: the bedside lamp (warm, low), the nightlight by the crib, the projector's stars, the window."""
        X0, Z0 = self.X0, self.Z0
        x, y, z = self.LAMPB
        plane_glow(fr, cam, (X0 + 0.002, 0.95, z), (0, 0, 1), (0, 1, 0), 1.25, "#ffb060", 0.42)
        plane_glow(fr, cam, (x, 0.003, z + 0.3), (1, 0, 0), (0, 0, 1), 1.3, "#ffb060", 0.18)
        plane_glow(fr, cam, (-0.9, 1.0, Z0 + 0.002), (1, 0, 0), (0, 1, 0), 1.0, "#ffb060", 0.16)
        nx, ny, nz = self.NITE
        plane_glow(fr, cam, (X0 + 0.002, ny, nz), (0, 0, 1), (0, 1, 0), 0.8, "#ffa850", 0.34)
        plane_glow(fr, cam, (nx + 0.3, 0.003, nz), (1, 0, 0), (0, 0, 1), 0.9, "#ffa850", 0.16)
        q = cam.proj(self.NITE)
        if q[2] > 0.7:
            fr.c.drawCircle(q[0], q[1], 0.045 * q[3], paint("#ffe0a0"))
            fr.glow(q[0], q[1], 0.25 * q[3], "#ffc070", a=0.5)
        # the window's cold light on the floor in front of it
        x0, x1, y0, y1 = self.WINF
        fr.poly(cam, [(x0, 0.003, Z0), (x1, 0.003, Z0), (x1 + 0.25, 0.003, Z0 + 1.0), (x0 + 0.1, 0.003, Z0 + 1.0)], colr="#7088b8", a=0.10, blur=8)
        # stars from the projector: on the ceiling, the far wall and the left wall, turning very slowly
        px, py, pz = self.PROJ[0], self.PROJ[1] + 0.08, self.PROJ[2]
        for a, el, s, ph in self.stars:
            a2 = a + 0.05 * T
            d = (math.cos(a2) * math.cos(el), math.sin(el), math.sin(a2) * math.cos(el) * 0.9 + 0.15)
            best = None
            for t_ in ((self.HT - py) / d[1] if d[1] > 0 else 1e9,
                       (X0 - px) / d[0] if d[0] < 0 else 1e9,
                       (self.X1 - px) / d[0] if d[0] > 0 else 1e9,
                       (self.Z1 - pz) / d[2] if d[2] > 0 else 1e9,
                       (Z0 - pz) / d[2] if d[2] < 0 else 1e9):
                if t_ > 0 and (best is None or t_ < best):
                    best = t_
            if best is None or best > 50:
                continue
            w = (px + d[0] * best, py + d[1] * best, pz + d[2] * best)
            q = cam.proj(w)
            if q[2] < 0.3 or not (0 < q[0] < W and 0 < q[1] < H):
                continue
            tw = 0.75 + 0.25 * math.sin(T * 1.3 + ph)
            fr.c.drawCircle(q[0], q[1], max(1.2, 0.012 * q[3] * s), paint("#dbe8ff", a=0.65 * tw))
            fr.glow(q[0], q[1], max(3.0, 0.05 * q[3] * s), "#9ec0ff", a=0.22 * tw)

    # ---- items ---------------------------------------------------------------------------------------------------
    def items(self, cam, T):
        it = []
        (bx0, bx1), (bz0, bz1), top = self.BED

        def bed(fr):
            fr.box(cam, (bx0, bx1), (0.10, top - 0.16), (bz0, bz1), "#8e6a72", line=1.2)                   # valance
            fr.box(cam, (bx0 + 0.02, bx1 - 0.02), (top - 0.16, top), (bz0 + 0.02, bz1 - 0.02), "#dcd0c0", line=1.0)
            fr.box(cam, (bx1 - 0.04, bx1 + 0.02), (0.0, 0.62), (bz0 - 0.03, bz1 + 0.03), "#6a4a34", line=1.2)   # footboard
            # the upholstered headboard against the wall, buttoned
            fr.box(cam, (self.X0 + 0.005, bx0 + 0.02), (0.0, 1.25), (bz0 - 0.08, bz1 + 0.08), "#6a5a78", line=1.2)
            for j in range(4):
                for k in range(3):
                    q = cam.proj((bx0 + 0.022, 0.72 + k * 0.17, bz0 + 0.10 + j * 0.30))
                    if q[2] > 0.2:
                        fr.c.drawCircle(q[0], q[1], max(1.0, 0.013 * q[3]), paint("#3e3248"))
            zc_ = (bz0 + bz1) / 2
            self._pillow(fr, cam, (bx0 + 0.36, top + 0.02, zc_), (0.22, 0.0, 0.0), (0.0, 0.0, 0.40), "#f0ebe2", (0, 0.10, 0))          # hers
            # her long hair spread over the pillow behind her head
            hp = [cam.proj((-1.12 + 0.15 * math.cos(a), top + 0.125, 2.50 + 0.15 * math.sin(a))) for a in
                  [2 * math.pi * i / 36 for i in range(36)]]
            if min(p[2] for p in hp) > 0.15:
                path = skia.Path()
                path.addPoly([skia.Point(p[0], p[1]) for p in hp], True)
                b = path.getBounds()
                fr.c.drawPath(path, paint(shader=lin((b.left(), b.top()), (b.right(), b.bottom()), [argb("#b0582c"), argb("#7a3a1c")])))
                fr.c.drawPath(path, paint("#4a2010", stroke=1.2))
                for k in range(7):
                    a0 = 2 * math.pi * k / 7 + 0.3
                    p0 = cam.proj((-1.10 + 0.05 * math.cos(a0), top + 0.126, 2.46 + 0.05 * math.sin(a0)))
                    p1 = cam.proj((-1.10 + 0.17 * math.cos(a0 + 0.25), top + 0.126, 2.46 + 0.14 * math.sin(a0 + 0.25)))
                    fr.c.drawLine(p0[0], p0[1], p1[0], p1[1], paint("#5a2a14", a=0.6, stroke=1.2))
        it.append((cam.view(((bx0 + bx1) / 2, top, bz1 + 0.4))[2] + 5.0, bed, "bed"))   # always under her

        def duvet(fr):
            """A quilt as a shaded quad mesh: flat over the mattress, a mound over her body, sides hanging down;
            a knitted throw across the foot."""
            br = math.sin(T * 2 * math.pi / 4.6)
            zc, xs = 2.58, [-0.86 + (bx1 + 0.04 + 0.86) * i / 23 for i in range(24)]

            def h(x):
                def ss(a, b, v):
                    u = min(1.0, max(0.0, (v - a) / (b - a)))
                    return u * u * (3 - 2 * u)
                body = 0.29 + 0.11 * ss(-0.15, -0.55, x) + 0.02 * math.sin(x * 7.0)
                return max(0.06, body * ss(0.80, 0.45, x) * ss(-0.88, -0.66, x)) * (1 + 0.03 * br)
            zs = [bz0 - 0.04, bz0 - 0.04] + [bz0 + (bz1 - bz0) * j / 17 for j in range(18)] + [bz1 + 0.04, bz1 + 0.04]

            def y(x, j):
                if j in (0, len(zs) - 1):
                    return top - 0.18
                u = (zs[j] - zc) / 0.50
                return top + 0.035 + h(x) * max(0.0, 1 - u * u) ** 0.38
            P = [[(x, y(x, j), zs[j]) for j in range(len(zs))] for x in xs]
            quads = []
            for i in range(len(xs) - 1):
                for j in range(len(zs) - 1):
                    q = [P[i][j], P[i + 1][j], P[i + 1][j + 1], P[i][j + 1]]
                    n = rig.norm(rig.cross(rig.sub(q[1], q[0]), rig.sub(q[3], q[0])))
                    cq = [sum(v[k] for v in q) / 4 for k in range(3)]
                    if rig.dot(n, rig.sub(cam.pos, cq)) < 0:
                        n = rig.mul(n, -1.0)
                    throw = 0.40 < cq[0] < 0.66
                    quads.append((cam.view(cq)[2], q, n, throw, i))
            for i0, side in ((0, -1.0), (len(xs) - 1, 1.0)):
                for j in range(len(zs) - 1):
                    x = xs[i0]
                    q = [(x, top - 0.18, zs[j]), (x, top - 0.18, zs[j + 1]), P[i0][j + 1], P[i0][j]]
                    cq = [sum(v[k] for v in q) / 4 for k in range(3)]
                    quads.append((cam.view(cq)[2], q, (side, 0.0, 0.0), False, i0))
            L = rig.norm((-0.30, 0.80, -0.50))
            for _, q, n, throw, i in sorted(quads, key=lambda t: -t[0]):
                if any(cam.view(v)[2] < 0.06 for v in q):
                    continue
                lam = max(0.0, rig.dot(n, L))
                base = "#9a5a3c" if throw else ("#c9a4a8" if (i // 2) % 2 else "#bf98a0")
                col = shade(base, -0.30 + 0.30 * lam)
                path = skia.Path()
                path.addPoly([skia.Point(*cam.proj(v)[:2]) for v in q], True)
                fr.c.drawPath(path, paint(col))
                fr.c.drawPath(path, paint(col, stroke=1.2))
        it.append((cam.view((-0.35, 0.74, 2.55))[2] - 0.3, duvet, "duvet"))     # just in front of her body, behind the crib

        it.append((cam.view(((self.CRIB[0][0] + self.CRIB[0][1]) / 2, 0.5, (self.CRIB[1][0] + self.CRIB[1][1]) / 2))[2] - 0.2,
                   lambda fr: self._crib(fr, cam, T), "crib"))

        def chair(fr):                                                     # the nursing chair in the corner, a blanket on it
            x0, x1, z0, z1 = 1.75, 2.50, 2.55, 3.30
            fr.box(cam, (x0, x1), (0.0, 0.42), (z0, z1), "#8a9a8a", line=1.2)
            fr.box(cam, (x1 - 0.16, x1), (0.42, 1.05), (z0, z1), "#7a8a7a", line=1.2)
            for zz in (z0, z1 - 0.14):
                fr.box(cam, (x0, x1), (0.42, 0.62), (zz, zz + 0.14), "#7e8e7e", line=1.0)
            fr.box(cam, (x0 + 0.1, x1 - 0.2), (0.42, 0.50), (z0 + 0.16, z1 - 0.16), "#c8b48a", line=1.0)
        it.append((cam.view((2.1, 0.5, 2.9))[2], chair, "chair"))
        it.append((cam.view(self.LAMPB)[2], lambda fr: self._lamp(fr, cam), "lamp"))
        return it

    def _pillow(self, fr, cam, c, u, v, colr, thick):
        """A puffy pillow: a bowed quad (base) and the same quad lifted by `thick` (top), soft gradient fill."""
        def outline(off):
            C = [tuple(c[k] + off[k] + su * u[k] + sv * v[k] for k in range(3)) for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            P = [cam.proj(p) for p in C]
            if min(p[2] for p in P) < 0.15:
                return None
            mid = cam.proj(tuple(c[k] + off[k] for k in range(3)))
            path = skia.Path()
            path.moveTo(P[0][0], P[0][1])
            for i in range(4):
                a, b = P[i], P[(i + 1) % 4]
                mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
                path.quadTo(mx + 0.28 * (mx - mid[0]), my + 0.28 * (my - mid[1]), b[0], b[1])
            path.close()
            return path, mid
        lo = outline((0, 0, 0))
        hi = outline(thick)
        if lo is None or hi is None:
            return
        fr.c.drawPath(lo[0], paint(shade(colr, -0.18)))
        fr.c.drawPath(lo[0], paint(shade(colr, -0.7), stroke=1.2))
        b = hi[0].getBounds()
        r = max(b.width(), b.height()) * 0.7
        fr.c.drawPath(hi[0], paint(shader=rad((hi[1][0], hi[1][1]), r, [argb(shade(colr, 0.12)), argb(shade(colr, -0.05)), argb(shade(colr, -0.25))], [0, 0.6, 1])))
        fr.c.drawPath(hi[0], paint(shade(colr, -0.6), stroke=1.2))

    def _crib(self, fr, cam, T):
        """A white crib: four slatted sides drawn far-to-near round the mattress and the baby, then the mobile."""
        (cx0, cx1), (cz0, cz1) = self.CRIB
        C = cam.pos
        col = "#ece6da"
        sides = [("z0", (cx0, cz0), (cx1, cz0), C[2] < cz0), ("z1", (cx0, cz1), (cx1, cz1), C[2] > cz1),
                 ("x0", (cx0, cz0), (cx0, cz1), C[0] < cx0), ("x1", (cx1, cz0), (cx1, cz1), C[0] > cx1)]

        def side(a, b):
            n = max(2, int(math.dist(a, b) / 0.075))
            for k in range(n + 1):
                u = k / n
                x, z = a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u
                p0, p1 = cam.proj((x, 0.24, z)), cam.proj((x, 0.90, z))
                if p0[2] < 0.15 or p1[2] < 0.15:
                    continue
                fr.c.drawLine(p0[0], p0[1], p1[0], p1[1], paint(col, stroke=max(1.4, 0.024 * p0[3])))
                fr.c.drawLine(p0[0], p0[1], p1[0], p1[1], paint("#6a6050", stroke=max(0.5, 0.004 * p0[3]), a=0.5))
            for y0_, y1_ in ((0.20, 0.27), (0.88, 0.95)):                    # bottom and top rails
                fr.poly(cam, [(a[0], y0_, a[1]), (b[0], y0_, b[1]), (b[0], y1_, b[1]), (a[0], y1_, a[1])], colr=col, outline="#7a7266", line=1.0)

        far = [s for s in sides if not s[3]]
        near = [s for s in sides if s[3]]
        dc = cam.view(((cx0 + cx1) / 2, 0.5, (cz0 + cz1) / 2))[2]
        posts = [(x, z) for x in (cx0, cx1) for z in (cz0, cz1)]

        def post(x, z):
            fr.box(cam, (x - 0.025, x + 0.025), (0.0, 1.0), (z - 0.025, z + 0.025), col, line=1.0)
        for x, z in posts:                                                                      # far corner posts first
            if cam.view((x, 0.5, z))[2] > dc:
                post(x, z)
        for s in far:
            side(s[1], s[2])
        fr.box(cam, (cx0 + 0.01, cx1 - 0.01), (0.27, 0.40), (cz0 + 0.01, cz1 - 0.01), "#dfe6ee", line=1.0)       # mattress, sheet
        # the baby: head toward the bed end, swaddled, a striped blanket over the legs, a bunny by his feet
        zc = (cz0 + cz1) / 2
        br = math.sin(T * 2 * math.pi / 2.2)
        hx = cx0 + 0.24
        def blob(cx, cy, cz, rx, rz, colr, n=28):
            P = [cam.proj((cx + rx * math.cos(2 * math.pi * i / n), cy, cz + rz * math.sin(2 * math.pi * i / n))) for i in range(n)]
            if min(p[2] for p in P) < 0.15:
                return
            path = skia.Path()
            path.addPoly([skia.Point(p[0], p[1]) for p in P], True)
            b = path.getBounds()
            fr.c.drawPath(path, paint(shader=lin((b.left(), b.top()), (b.right(), b.bottom()), [argb(shade(colr, 0.18)), argb(shade(colr, -0.22))])))
            fr.c.drawPath(path, paint(shade(colr, -0.6), stroke=1.2))
        blob(hx + 0.42, 0.405, zc, 0.30, 0.22, "#9ab8d8")                                       # the blanket, tucked in
        for k in range(4):                                                                     # its stripes
            xx = hx + 0.24 + k * 0.10
            a_, b_ = cam.proj((xx, 0.41, zc - 0.17)), cam.proj((xx, 0.41, zc + 0.17))
            if a_[2] > 0.15 and b_[2] > 0.15:
                fr.c.drawLine(a_[0], a_[1], b_[0], b_[1], paint("#e8f0f8", a=0.8, stroke=max(1.0, 0.02 * a_[3])))
        blob(hx + 0.17, 0.44 + 0.004 * br, zc, 0.15, 0.09, "#d8e6f2")                         # the swaddle over his body
        blob(cx1 - 0.14, 0.43, zc + 0.12, 0.06, 0.05, "#f2e6ee")                               # a bunny
        e = cam.proj((cx1 - 0.14, 0.47, zc + 0.12))
        if e[2] > 0.15:
            for dx in (-0.02, 0.02):
                f_ = cam.proj((cx1 - 0.14 + dx, 0.47, zc + 0.08))
                fr.c.drawCircle(f_[0], f_[1] - 0.04 * f_[3], 0.018 * f_[3], paint("#f2e6ee"))
        q = cam.proj((hx, 0.49, zc))
        if q[2] > 0.15:
            r0 = 0.075 * q[3]
            fr.c.drawCircle(q[0], q[1], r0, paint("#f2cfb4"))
            fr.c.drawCircle(q[0] - 0.2 * r0, q[1] - 0.25 * r0, 0.6 * r0, paint("#fff0e0", a=0.35, blur=0.3 * r0))
            fr.c.drawCircle(q[0], q[1], r0, paint("#8a6050", stroke=max(1.0, 0.04 * r0)))
            for sx in (-0.36, 0.36):                                                             # closed eyes, asleep
                arc = skia.Path()
                arc.moveTo(q[0] + (sx - 0.16) * r0, q[1] + 0.02 * r0)
                arc.quadTo(q[0] + sx * r0, q[1] + 0.15 * r0, q[0] + (sx + 0.16) * r0, q[1] + 0.02 * r0)
                fr.c.drawPath(arc, paint("#6a4636", stroke=max(1.0, 0.06 * r0)))
            fr.c.drawCircle(q[0], q[1] + 0.40 * r0, 0.07 * r0, paint("#c07a6a"))
            for cx_ in (-0.5, 0.5):
                fr.c.drawCircle(q[0] + cx_ * r0, q[1] + 0.25 * r0, 0.16 * r0, paint("#f0a090", a=0.35, blur=0.08 * r0))
            hw = skia.Path()
            hw.moveTo(q[0] - 0.2 * r0, q[1] - 0.85 * r0)
            hw.quadTo(q[0] + 0.1 * r0, q[1] - 1.15 * r0, q[0] + 0.25 * r0, q[1] - 0.8 * r0)
            fr.c.drawPath(hw, paint("#8a6a4a", stroke=max(1.0, 0.07 * r0)))
        for s in near:
            side(s[1], s[2])
        for x, z in posts:                                                                      # near corner posts last
            if cam.view((x, 0.5, z))[2] <= dc:
                post(x, z)
        self._mobile(fr, cam, T)

    def _mobile(self, fr, cam, T):
        (cx0, cx1), (cz0, cz1) = self.CRIB
        hub = ((cx0 + cx1) / 2, 1.42, (cz0 + cz1) / 2)
        base = (cx0 + 0.02, 1.0, cz0 + 0.02)
        elbow = (base[0], 1.52, base[2])
        for a, b in ((base, elbow), (elbow, (hub[0], 1.52, hub[2])), ((hub[0], 1.52, hub[2]), hub)):
            p, q = cam.proj(a), cam.proj(b)
            if p[2] > 0.2 and q[2] > 0.2:
                fr.c.drawLine(p[0], p[1], q[0], q[1], paint("#e8e2d6", stroke=max(1.2, 0.014 * p[3])))
        shapes = [("star", "#f2d26a"), ("moon", "#f4ead0"), ("cloud", "#f0f4fa"), ("star", "#a8c8f0"), ("moon", "#f2c6c0")]
        for k, (kind, colr) in enumerate(shapes):
            ang = 2 * math.pi * k / len(shapes) + 0.35 * T
            p = (hub[0] + 0.17 * math.cos(ang), 1.20 + 0.03 * (k % 2), hub[2] + 0.17 * math.sin(ang))
            h0, q = cam.proj(hub), cam.proj(p)
            if q[2] < 0.2:
                continue
            fr.c.drawLine(h0[0], h0[1], q[0], q[1] - 0.04 * q[3], paint("#d8d2c6", a=0.7, stroke=max(0.6, 0.003 * q[3])))
            s = 0.05 * q[3]
            if kind == "star":
                path = skia.Path()
                for i in range(10):
                    rr = s if i % 2 == 0 else s * 0.45
                    a = -math.pi / 2 + i * math.pi / 5 + 0.3 * math.sin(T + k)
                    (path.moveTo if i == 0 else path.lineTo)(q[0] + rr * math.cos(a), q[1] + rr * math.sin(a))
                path.close()
            elif kind == "moon":
                path = skia.Path()
                path.addCircle(q[0], q[1], s * 0.8)
                cut = skia.Path()
                cut.addCircle(q[0] + 0.35 * s, q[1] - 0.15 * s, s * 0.65)
                path = skia.Op(path, cut, skia.PathOp.kDifference_PathOp)
            else:
                path = skia.Path()
                for dx, dy, rr in ((-0.4, 0.1, 0.45), (0.0, -0.15, 0.55), (0.45, 0.1, 0.42)):
                    path.addCircle(q[0] + dx * s, q[1] + dy * s, rr * s)
            fr.c.drawPath(path, paint(colr))
            fr.c.drawPath(path, paint(shade(colr, -0.6), stroke=max(0.8, 0.004 * q[3])))

    def _lamp(self, fr, cam):
        """The bedside lamp: a glowing drum shade on its stem."""
        x, y, z = self.LAMPB
        if cam.view((x, y + 0.4, z))[2] < 0.3:
            return
        fr.poly(cam, [(x - 0.10, y + 0.46, z), (x + 0.10, y + 0.46, z), (x + 0.15, y + 0.26, z), (x - 0.15, y + 0.26, z)],
                colr="#ffe2b0", outline="#9a7a4a", line=1.0)
        g = cam.proj((x, y + 0.36, z))
        fr.glow(g[0], g[1], 0.55 * g[3], "#ffc070", a=0.40)

    def overlay(self, fr, cam, T, outs):
        h = cam.proj((-1.05, 0.80, 2.45))                     # the lamp's bloom on the pillows
        if h[2] > 0.3:
            fr.glow(h[0], h[1], 0.7 * h[3], "#ffb060", a=0.10)

    def post(self, fr, cam, T):
        fr.c.drawPaint(paint("#1a2444", a=0.16, blend="mul"))
        vignette(fr, 0.55)
