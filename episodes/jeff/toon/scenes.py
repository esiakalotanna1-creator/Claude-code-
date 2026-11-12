"""Sets and choreography for the full Jeff reel (times T are reel seconds, from toon/timeline.json).

Each scene is one 3D world on one timeline: bg() draws what is always behind everyone (sky, walls, windows),
items() the depth-sorted set pieces, cast() the people, overlay() things attached to people (liquid, gauze,
dropped props) and post() screen washes. solids() mirrors the set as collision boxes for the checks.
"""
import math

import numpy as np
import skia

import rig
from anim import EASE, HOLD, Track, blink, move  # noqa: F401
from toon import Camera, Rain, W, H, argb, lin, paint, shade  # noqa: F401
import busstop as B


def hold(*names):
    return {n: HOLD for n in names}


def win(T, a, b, e="io"):
    return EASE[e]((T - a) / max(1e-6, b - a))


def lerp(a, b, u):
    return tuple(x + (y - x) * u for x, y in zip(a, b))


def blend_ik(look, p, side, target, w):
    """IK toward a world target with weight w; the FK elbow is the pole, so w = 0 matches the FK arm exactly."""
    if w <= 0:
        return
    J = rig.solve(look, p)
    p["ik_" + side] = lerp(J["wr_" + side], target, min(1.0, w))
    p["pole_" + side] = rig.norm(rig.sub(J["el_" + side], J["sh_" + side]))


def ankles(look, p):
    J = rig.solve(look, {k: v for k, v in p.items() if not k.startswith("ankle_")})
    return {"R": J["ank_R"], "L": J["ank_L"]}


def talk(T, a, b, rate=7.0, amp=0.32):
    """Mouth flaps while speaking between a and b."""
    if not a < T < b:
        return 0.0
    return amp * max(0.0, math.sin(2 * math.pi * rate * (T - a))) * min(1.0, (T - a) / 0.08, (b - T) / 0.08)


def vignette(fr, k=0.55):
    fr.c.drawRect(skia.Rect(0, 0, W, H), paint(shader=skia.GradientShader.MakeRadial(
        skia.Point(W / 2, H * 0.45), H * 0.75, [argb("#000000", 0), argb("#000000", 0), argb("#000008", k)], [0, 0.55, 1])))


def wash(fr, colr, a, blend="add"):
    if a > 0.002:
        fr.c.drawRect(skia.Rect(0, 0, W, H), paint(colr, a=a, blend=blend))


# =========================================================================================================
# interior kit
# =========================================================================================================
class Room:
    """A box room. Walls: back z=z1, front z=z0, left x=x0, right x=x1 (each with a coordinate `a` along it:
    x for back/front, z for left/right). Decorations sit on the wall planes and are always behind people."""

    def __init__(self, x0, x1, z0, z1, h, wall, floor, light, ceil=None, planks=True, base="#20242e"):
        self.x0, self.x1, self.z0, self.z1, self.h = x0, x1, z0, z1, h
        self.wall, self.floor, self.light, self.ceil = wall, floor, light, ceil or shade(wall, -0.35)
        self.planks, self.base = planks, base
        self.deco = []
        self.pools = []                 # (x, z, rx, rz, colr, a) light pools on the floor (additive)

    def pt(self, wall, a, y, off=0.0):
        """World point on a wall plane; off > 0 = into the room."""
        return {"back": (a, y, self.z1 - off), "front": (a, y, self.z0 + off),
                "left": (self.x0 + off, y, a), "right": (self.x1 - off, y, a)}[wall]

    def quad(self, wall, a0, a1, y0, y1, off=0.0):
        return [self.pt(wall, a0, y0, off), self.pt(wall, a1, y0, off), self.pt(wall, a1, y1, off), self.pt(wall, a0, y1, off)]

    def faces(self, wall, cam):
        n = {"back": (0, 0, -1), "front": (0, 0, 1), "left": (1, 0, 0), "right": (-1, 0, 0)}[wall]
        p = self.pt(wall, 0.0, 1.0)
        if wall in ("back", "front"):
            p = (cam.pos[0], 1.0, p[2])
        else:
            p = (p[0], 1.0, cam.pos[2])
        return n[0] * (cam.pos[0] - p[0]) + n[2] * (cam.pos[2] - p[2]) > 0

    def window(self, wall, a0, a1, y0, y1, sky="#0c1630", glow=("#9fb8ff", 0.35), seed=1):
        out = {"back": ((a0 - 1.5, a1 + 1.5), (-0.5, self.h + 2), (self.z1 + 0.4, self.z1 + 7)),
               "front": ((a0 - 1.5, a1 + 1.5), (-0.5, self.h + 2), (self.z0 - 7, self.z0 - 0.4)),
               "left": ((self.x0 - 7, self.x0 - 0.4), (-0.5, self.h + 2), (a0 - 1.5, a1 + 1.5)),
               "right": ((self.x1 + 0.4, self.x1 + 7), (-0.5, self.h + 2), (a0 - 1.5, a1 + 1.5))}[wall]
        rain = Rain(n=700, box=out, speed=7.0, seed=seed)
        self.deco.append(("window", wall, (a0, a1, y0, y1, sky, glow, rain, out)))

    def door(self, wall, a0, a1, y1=2.05, colr="#6b4a34", inside="#06070b", open_fn=None, hinge="a0", spill=None):
        self.deco.append(("door", wall, (a0, a1, y1, colr, inside, open_fn, hinge, spill)))

    def flat(self, wall, a0, a1, y0, y1, colr, a=1.0, frame=None, off=0.005):
        self.deco.append(("flat", wall, (a0, a1, y0, y1, colr, a, frame, off)))

    def draw(self, fr, cam, T):
        x0, x1, z0, z1, h = self.x0, self.x1, self.z0, self.z1, self.h
        fr.poly(cam, [(x0, h, z0), (x1, h, z0), (x1, h, z1), (x0, h, z1)], colr=self.ceil)
        fr.poly(cam, [(x0, 0, z0), (x1, 0, z0), (x1, 0, z1), (x0, 0, z1)], colr=self.floor)
        if self.planks:
            for x in np.arange(x0, x1, 0.22):
                fr.poly(cam, [(x, 0, z0), (x + 0.012, 0, z0), (x + 0.012, 0, z1), (x, 0, z1)], colr=shade(self.floor, -0.35), a=0.6)
        for wall in ("back", "front", "left", "right"):
            if not self.faces(wall, cam):
                continue
            a0, a1 = (x0, x1) if wall in ("back", "front") else (z0, z1)
            fr.poly(cam, self.quad(wall, a0, a1, 0, h), shader=lambda p: lin((0, p.getBounds().top()), (0, p.getBounds().bottom()),
                                                                              [argb(shade(self.wall, -0.25)), argb(self.wall), argb(shade(self.wall, -0.15))], [0, 0.6, 1]))
            fr.poly(cam, self.quad(wall, a0, a1, 0, 0.12, 0.004), colr=self.base)
        for kind, wall, d in self.deco:
            if not self.faces(wall, cam):
                continue
            getattr(self, "_" + kind)(fr, cam, T, wall, d)
        for x, z, rx, rz, colr, a in self.pools:
            fr.ground_ellipse(cam, x, z, rx, rz, colr, a, blur_m=min(rx, rz) * 0.5, y=0.002, add=True)
        # the room's main light: a warm pool on the walls and floor
        lx, ly, lz = self.light
        x, y, _, s = cam.proj(self.light)
        if cam.view(self.light)[2] > 0.1:
            fr.glow(x, y, 2.6 * s, "#ffb070", a=0.10)

    def _window(self, fr, cam, T, wall, d):
        a0, a1, y0, y1, sky, glow, rain, out = d
        q = self.quad(wall, a0, a1, y0, y1, 0.002)
        path = fr.poly(cam, q, shader=lambda p: lin((0, p.getBounds().top()), (0, p.getBounds().bottom()), [argb(sky), argb(shade(sky, -0.4))]))
        if path is None:
            return
        fr.c.save()
        fr.c.clipPath(path, skia.ClipOp.kIntersect, True)
        cx = ((out[0][0] + out[0][1]) / 2, 3.0, (out[2][0] + out[2][1]) / 2)
        if cam.view(cx)[2] > 0.2:
            x, y, _, s = cam.proj(cx)
            fr.glow(x, y, 2.5 * s, glow[0], a=glow[1])
        rain.draw(fr, cam, T, colr=(0.75, 0.82, 0.95))
        fr.c.restore()
        fr.c.drawPath(path, paint("#ffffff", a=0.05))
        fc = "#c9c2b4"
        for (b0, b1, c0, c1) in ((a0 - 0.05, a1 + 0.05, y0 - 0.06, y0), (a0 - 0.05, a1 + 0.05, y1, y1 + 0.05),
                                 (a0 - 0.05, a0, y0, y1), (a1, a1 + 0.05, y0, y1), ((a0 + a1) / 2 - 0.02, (a0 + a1) / 2 + 0.02, y0, y1),
                                 (a0, a1, (y0 + y1) / 2 - 0.02, (y0 + y1) / 2 + 0.02)):
            fr.poly(cam, self.quad(wall, b0, b1, c0, c1, 0.01), colr=shade(fc, -0.35), outline=shade(fc, -0.7), line=1.2)
        fr.poly(cam, self.quad(wall, a0 - 0.08, a1 + 0.08, y0 - 0.1, y0 - 0.06, 0.06), colr=shade(fc, -0.2))   # sill

    def _door(self, fr, cam, T, wall, d):
        a0, a1, y1, colr, inside, open_fn, hinge, spill = d
        op = open_fn(T) if open_fn else 0.0
        fr.poly(cam, self.quad(wall, a0, a1, 0, y1, 0.002), colr=inside)
        if spill and op > 0:
            sc, sa = spill
            fr.poly(cam, self.quad(wall, a0, a1, 0, y1, 0.003), colr=sc, a=sa * min(1.0, op * 3))
        # the slab swings out of the room around its hinge (behind the wall plane)
        w = a1 - a0
        th = op * math.pi / 2
        ha, sg = (a0, 1) if hinge == "a0" else (a1, -1)
        ea = ha + sg * w * math.cos(th)
        n_out = -w * math.sin(th)
        slab = [self.pt(wall, ha, 0.0, 0.0), self.pt(wall, ha, y1, 0.0), self.pt(wall, ea, y1, n_out), self.pt(wall, ea, 0.0, n_out)]
        fr.poly(cam, slab, colr=shade(colr, -0.1 - 0.3 * op), outline=shade(colr, -0.7), line=1.5)
        if op < 0.25:
            k = self.pt(wall, ha + sg * w * 0.85 * math.cos(th), 1.0, n_out * 0.85 + 0.02)
            if cam.view(k)[2] > 0.1:
                x, y, _, s = cam.proj(k)
                fr.c.drawCircle(x, y, 0.025 * s, paint("#c8b27a"))
        for (b0, b1, c0, c1) in ((a0 - 0.07, a0, 0, y1 + 0.07), (a1, a1 + 0.07, 0, y1 + 0.07), (a0 - 0.07, a1 + 0.07, y1, y1 + 0.07)):
            fr.poly(cam, self.quad(wall, b0, b1, c0, c1, 0.02), colr=shade("#d8d0c0", -0.25), outline=shade("#d8d0c0", -0.7), line=1.2)

    def door_edge(self, wall, a0, a1, op, y, hinge="a0"):
        w = a1 - a0
        th = op * math.pi / 2
        ha, sg = (a0, 1) if hinge == "a0" else (a1, -1)
        return self.pt(wall, ha + sg * w * math.cos(th), y, -w * math.sin(th))

    def _flat(self, fr, cam, T, wall, d):
        a0, a1, y0, y1, colr, a, frame, off = d
        if frame:
            fr.poly(cam, self.quad(wall, a0 - 0.04, a1 + 0.04, y0 - 0.04, y1 + 0.04, off), colr=frame)
        fr.poly(cam, self.quad(wall, a0, a1, y0, y1, off + 0.002), colr=colr, a=a)


def lamp_item(cam, pos, on, shade_c="#f3d9a8"):
    """Bedside lamp: base, glowing shade, light bloom. on: 0..1."""
    x, y, z = pos

    def fn(fr):
        fr.box(cam, (x - 0.06, x + 0.06), (y, y + 0.05), (z - 0.06, z + 0.06), "#3b3026")
        fr.box(cam, (x - 0.012, x + 0.012), (y, y + 0.26), (z - 0.012, z + 0.012), "#5a4a36")
        fr.box(cam, (x - 0.11, x + 0.11), (y + 0.22, y + 0.38), (z - 0.11, z + 0.11), shade(shade_c, -0.55 * (1 - on)))
        if on > 0:
            p = cam.proj((x, y + 0.3, z))
            if p[2] > 0.1:
                fr.glow(p[0], p[1], 0.9 * p[3], "#ffb46a", a=0.55 * on)
                fr.glow(p[0], p[1], 0.25 * p[3], "#fff0d0", a=0.6 * on)
    return (cam.view((x, y + 0.3, z))[2], fn, "lamp")


def bed_items(cam, xs, zs, top=0.55, sheet="#dfe4ea", frame="#6b4f3a", pillow_z=None, blanket=None, name="bed",
              rail=None, skirt=False):
    """Bed as drawables. The base is anchored on its far side from the camera so that someone sitting on it is
    drawn after it; the blanket (over a sitter's legs) is anchored at its near edge so it covers them."""
    (x0, x1), (z0, z1) = xs, zs
    far_z = z1 + 0.6 if cam.pos[2] < (z0 + z1) / 2 else z0 - 0.6
    items = []

    def base(fr):
        fr.box(cam, (x0, x1), (0.12, top - 0.16), (z0, z1), frame, light=None)
        fr.box(cam, (x0 + 0.02, x1 - 0.02), (top - 0.16, top), (z0 + 0.02, z1 - 0.02), sheet)
        for lx in (x0 + 0.04, x1 - 0.06):
            for lz in (z0 + 0.04, z1 - 0.06):
                fr.box(cam, (lx, lx + 0.04), (0, 0.12), (lz, lz + 0.04), shade(frame, -0.3))
        if pillow_z is not None:
            fr.box(cam, (x0 + 0.1, x1 - 0.1), (top, top + 0.12), (pillow_z[0], pillow_z[1]), "#f4f1ea")
        if rail:
            fr.box(cam, (x0, x1), (top + 0.0, top + 0.75), (z1 - 0.05, z1), shade(frame, -0.1))
    items.append((cam.view(((x0 + x1) / 2, top, far_z))[2], base, name))
    if skirt and cam.pos[2] < z0:
        # near end face drawn again in front, so someone standing beside the bed is hidden behind it
        def front(fr):
            fr.box(cam, (x0, x1), (0.12, top - 0.16), (z0, z0 + 0.03), frame, light=None)
            fr.box(cam, (x0 + 0.02, x1 - 0.02), (top - 0.16, top), (z0 + 0.02, z0 + 0.05), sheet)
            for lx in (x0 + 0.04, x1 - 0.06):
                fr.box(cam, (lx, lx + 0.04), (0, 0.12), (z0 + 0.04, z0 + 0.08), shade(frame, -0.3))
        items.append((cam.view(((x0 + x1) / 2, top, z0 - 0.3))[2], front, name + "_front"))
    if blanket:
        bx, bz, bc = blanket

        def bl(fr):
            fr.box(cam, bx, (top - 0.02, top + 0.2), bz, bc)
            fr.box(cam, (bx[0] - 0.01, bx[1] + 0.01), (top + 0.12, top + 0.2), (bz[1] - 0.12, bz[1]), shade(bc, 0.2))
        near = bz[0] if cam.pos[2] < bz[0] else bz[1]
        items.append((cam.view(((bx[0] + bx[1]) / 2, top, near - 0.3 if cam.pos[2] < bz[0] else near + 0.3))[2], bl, name + "_blanket"))
    return items


def box_item(cam, xs, ys, zs, colr, name, light=None, anchor=None):
    c = anchor or ((xs[0] + xs[1]) / 2, (ys[0] + ys[1]) / 2, (zs[0] + zs[1]) / 2)
    return (cam.view(c)[2], lambda fr: fr.box(cam, xs, ys, zs, colr, light=light), name)


def seated(look, x, z, yaw, seat_y, feet_fwd, feet_y=None, **kw):
    """A sitting pose: pelvis at the seat height, ankles in front (on the floor, or on the mattress)."""
    h = rig.LOOK[look]["h"]
    p = dict(x=x, z=z, yaw=yaw, crouch=0.47 - (seat_y + 0.06) / h)
    p.update(kw)
    Bb = rig.Basis.yaw(yaw)
    fy = 0.035 * h if feet_y is None else feet_y
    p["ankle_R"] = Bb.w((x, 0, z), 0.065 * h, fy, feet_fwd)
    p["ankle_L"] = Bb.w((x, 0, z), -0.065 * h, fy, feet_fwd)
    p["plant"] = "both" if feet_y is None else "none"
    return p


# =========================================================================================================
# 1. bus stop (reuses the approved sample: local time t = T - TB)
# =========================================================================================================
TB = 11.45


class Bus:
    light = B.LIGHT
    name = "bus"

    def __init__(self):
        self._prep()

    # ---- fight / police / forget choreography on top of the sample's last poses --------------------------
    def _prep(self):
        base = {n: p for n, p, _, _ in B.cast(6.38)}
        self.base = base
        self.jeff_ank0 = {"R": base["jeff"]["ankle_R"], "L": base["jeff"]["ankle_L"]}
        jb, rb = base["jeff"], base["randy"]
        self.JF = Track([
            (6.38, dict(x=jb["x"], lean=1.0, twist=0.0, mouth=0.0, smile=-0.55, head_pitch=5.0, brow=-0.25, brow_in=1.0, lid=0.70,
                        shrug=0.2, aR=(-14.0, 24.0, 22.0), head_yaw=2.0, lid_lo=0.25)),
            (6.42, hold("x", "lean")), (6.84, dict(x=jb["x"] + 0.23, lean=6.0), "io"),
            (6.75, hold("mouth", "smile")), (6.90, dict(mouth=0.3, smile=-0.3), "out"),
            (7.18, hold("aR")), (7.45, dict(aR=(-36.0, 28.0, 122.0)), "io"),               # cock the fist
            (7.45, hold("lean", "twist")), (7.70, dict(lean=-2.0, twist=-14.0, aR=(-42.0, 30.0, 128.0)), "io"),
            (7.85, dict(lean=10.0, twist=12.0), "snap"),                                    # the punch
            (7.95, hold("aR")), (8.35, dict(aR=(-6.0, 20.0, 70.0)), "io"),
            (8.30, dict(lean=4.0, twist=0.0), "back"),
            (9.00, hold("head_pitch", "brow", "brow_in", "lid", "mouth", "smile", "shrug", "aR", "lid_lo")),
            (9.70, dict(head_pitch=20.0, brow=0.4, brow_in=-0.6, lid=0.72, mouth=0.0, smile=-0.1, shrug=0.4,
                        aR=(4.0, 8.0, 14.0), lid_lo=0.0), "io"),                            # police: guilt
        ])
        self.RF = Track([
            (6.38, dict(lean=4.0, smile=0.65, head_pitch=-8.0, head_yaw=-6.0, brow=0.0, brow_in=0.5, lid=0.78, lid_lo=0.3, mouth=0.0,
                        aL=(40.0, 26.0, 82.0), side=0.0, x=rb["x"])),
            (6.70, hold("smile", "brow", "brow_in", "mouth", "lid", "lid_lo")),
            (6.85, dict(smile=-0.2, brow=0.6, brow_in=-0.6, mouth=0.4, lid=0.95, lid_lo=0.0), "out"),
            (6.75, hold("lean", "side")), (7.00, dict(lean=12.0, side=-6.0), "io"),
            (7.18, hold("aL")), (7.45, dict(aL=(28.0, 8.0, 100.0)), "io"),
            (7.20, hold("lean", "side")), (7.50, dict(lean=2.0, side=0.0), "io"),
            (7.84, hold("head_yaw", "head_pitch", "lean", "side", "mouth", "lid", "brow", "brow_in", "x")),
            (7.92, dict(head_yaw=-34.0, head_pitch=-18.0, lean=-14.0, side=8.0, mouth=0.5, lid=0.3, brow=0.2, brow_in=-0.8), "snap"),
            (8.40, dict(head_yaw=-12.0, head_pitch=14.0, lean=18.0, side=3.0, lid=0.6, mouth=0.25, x=rb["x"] + 0.31), "io"),
            (8.74, dict(lean=16.0, head_pitch=12.0), "back"),
            (10.0, hold("head_pitch", "head_yaw", "lean", "brow", "brow_in", "lid", "smile", "mouth")),
            (10.6, dict(head_pitch=0.0, head_yaw=-4.0, lean=8.0, brow=-0.2, brow_in=0.9, lid=0.7, smile=-0.4, mouth=0.0), "io"),
            (12.6, hold("lean", "head_pitch", "lid", "brow_in")),
            (13.2, dict(lean=3.0, head_pitch=-4.0, lid=0.55, brow_in=1.0), "io"),
        ])
        # Randy's wrist path while Jeff holds it: from where it is at 6.68, wrenched down and out
        p = dict(base["randy"])
        p.update(self.RF(6.68))
        self.W0 = rig.solve("randy", p)["wr_L"]
        self.GD = (-0.05, -0.32, -0.10)
        self.randy_ank0 = {"R": base["randy"]["ankle_R"], "L": base["randy"]["ankle_L"]}
        self.bully_ank0 = {n: {"R": base[n]["ankle_R"], "L": base[n]["ankle_L"]} for n in ("bully", "bully2")}
        self.KD = 6.98                       # the knife leaves Randy's hand
        q = dict(base["randy"])
        q.update(self.RF(self.KD))
        q["ik_L"] = self.G(self.KD)
        self.K0 = rig.solve("randy", q)["hand_L"]
        # Liu steps in front of Jeff and raises his hands (police)
        lb = dict(base["liu"])
        self.LIU0 = lb
        self.LF = Track([
            (9.00, dict(x=lb["x"], z=lb["z"], yaw=lb["yaw"], crouch=lb["crouch"], lean=lb["lean"], shrug=lb["shrug"], aR=lb["aR"], aL=lb["aL"],
                        head_yaw=lb["head_yaw"], head_pitch=lb["head_pitch"], brow=lb["brow"], brow_in=lb["brow_in"])),
            (9.60, dict(x=-0.64, z=5.72, yaw=-55.0, crouch=0.0, lean=0.0, head_yaw=0.0, head_pitch=0.0), "io"),
            (9.45, hold("aR", "aL", "shrug")), (10.0, dict(aR=(70.0, 25.0, 95.0), aL=(70.0, 25.0, 95.0), shrug=0.3), "out"),
            (9.8, hold("brow", "brow_in")), (10.2, dict(brow=0.3, brow_in=0.35), "io"),
        ])
        end = dict(lb)
        end.update(self.LF(10.5))
        self.liu_ank = (ankles("liu", lb), ankles("liu", end))

    def G(self, t):
        return rig.add(self.W0, rig.mul(self.GD, win(t, 6.68, 7.05)))

    def knife_at(self, t):
        """World pose of the dropped knife: falling and spinning, then flat on the ground."""
        dt = t - self.KD
        x0, y0, z0 = self.K0
        tl = math.sqrt(max(0.0, y0 - 0.015) / 4.9)
        if dt < tl:
            return (x0 + 0.35 * dt, y0 - 4.9 * dt * dt, z0 - 0.1 * dt), math.radians(40 + 700 * dt), False
        return (x0 + 0.35 * tl, 0.012, z0 - 0.1 * tl), math.radians(25), True

    def cast(self, T):
        t = T - TB
        out = []
        for name, p, held, glow in B.cast(max(t, 0.0)):
            if t < 0 and name in B.WALKERS:
                continue
            p = dict(p)
            if t < 0:
                self._idle(name, p, t)
            if t > 6.38:
                held = self._after(name, p, t, held)
                if name == "jeff":
                    glow = None
            out.append((name, name, p, held, glow))
        if t > 6.38:          # Jeff's grip and punch are solved against Randy's final pose this frame
            rp = next(p for n, _, p, _, _ in out if n == "randy")
            jp = next(p for n, _, p, _, _ in out if n == "jeff")
            RJ = rig.solve("randy", rp)
            if 6.45 <= t < 7.45:
                if t < 7.18:
                    tgt, w = rig.add(self.G(t), (-0.05, 0.035, 0.0)), win(t, 6.45, 6.68)
                else:
                    tgt, w = rig.add(self.G(7.18), (-0.05, 0.035, 0.0)), 1 - win(t, 7.18, 7.45)
                blend_ik("jeff", jp, "R", tgt, w)
            elif 7.70 <= t < 8.35:
                face = RJ["Bh"].w(RJ["head"], -0.55 * RJ["R"], -0.25 * RJ["R"], 0.9 * RJ["R"])
                w = win(t, 7.70, 7.85, "snap") if t < 7.95 else 1 - win(t, 7.95, 8.35)
                blend_ik("jeff", jp, "R", face, w)
        return out

    def _idle(self, name, p, t):
        # before the bullies arrive (t < 0): Liu glances up at Jeff and says something; both blink
        if name == "liu":
            u = win(t, -4.6, -4.1) * (1 - win(t, -1.6, -1.0))
            p["head_yaw"] += 20 * u
            p["head_pitch"] += -6 * u
            p["gx"] += 0.4 * u
            p["mouth"] = talk(t, -3.9, -2.6, 6.0, 0.25)
            p["lid"] = p["lid"] * blink(t, [-5.0, -2.2])
        if name == "jeff":
            p["lid"] = p["lid"] * blink(t, [-4.4, -1.7])
            u = win(t, -3.0, -2.6) * (1 - win(t, -2.2, -1.8))
            p["gx"] += 0.5 * u                               # eyes flick to Liu while he talks, then back
            p["smile"] = 0.25 * u

    def _after(self, name, p, t, held):
        h = rig.LOOK[name]["h"]
        if name == "jeff":
            p.update(self.JF(t))
            dx = p["x"] - self.base["jeff"]["x"]
            a = self.jeff_ank0
            p.update(rig.replant(t, a, [("R", 6.42, 0.22, rig.add(a["R"], (0.28, 0, 0))), ("L", 6.62, 0.22, rig.add(a["L"], (0.20, 0, 0)))], h))
            p.pop("ik_L", None)
            p.pop("ik_R", None)
            J0 = rig.solve("jeff", p)
            p["ik_L"] = J0["Bb"].w(J0["pelvis"], -0.12 * h, 0.02 * h, 0.06 * h)    # phone hand stays by the hip
            del dx
            return {"L": rig.phone(on=False)}
        if name == "randy":
            p.update(self.RF(t))
            a = self.randy_ank0
            p.update(rig.replant(t, a, [("L", 7.92, 0.24, rig.add(a["L"], (0.32, 0, 0))), ("R", 8.12, 0.24, rig.add(a["R"], (0.30, 0, 0)))], h))
            p.pop("ik_L", None)
            if 6.68 <= t < 7.18:                           # wrist held by Jeff
                blend_ik("randy", p, "L", self.G(t), 1.0)
            elif 7.18 <= t < 7.45:                         # released: the arm eases back to its own pose
                blend_ik("randy", p, "L", self.G(7.18), 1 - win(t, 7.18, 7.45))
            if t >= 7.95:                                   # hand to the hit cheek, later lowered
                J = rig.solve("randy", {k: v for k, v in p.items() if k not in ("ik_L", "pole_L")})
                cheek = J["Bh"].w(J["head"], -0.85 * J["R"], -0.45 * J["R"], 0.55 * J["R"])
                w = win(t, 7.95, 8.25) * (1 - win(t, 12.9, 13.4))
                blend_ik("randy", p, "L", cheek, w)
            return {"L": rig.knife(1.0)} if t < self.KD else None
        if name in ("bully", "bully2"):
            a = self.bully_ank0[name]
            u = win(t, 7.95, 8.45)
            p["x"] += 0.22 * u
            p.update(rig.replant(t, a, [("R", 7.95, 0.24, rig.add(a["R"], (0.22, 0, 0))), ("L", 8.18, 0.24, rig.add(a["L"], (0.22, 0, 0)))], h))
            s = win(t, 7.88, 8.05, "out")
            p["brow"] = p.get("brow", 0) + 0.7 * s
            p["brow_in"] = p.get("brow_in", 0) * (1 - s) - 0.5 * s
            p["mouth"] = 0.3 * s
            p["smile"] = p.get("smile", 0) * (1 - s)
            p["lean"] = p.get("lean", 0) - 4 * s
            return held
        if name == "liu":
            s = win(t, 7.86, 8.0, "out")
            p["mouth"] = 0.3 * s * (1 - win(t, 9.2, 9.6))
            if t >= 9.0:
                p.update(self.LF(t))
                p.update(rig.replant(t, self.liu_ank[0], [("R", 9.05, 0.28, self.liu_ank[1]["R"]), ("L", 9.30, 0.28, self.liu_ank[1]["L"])], h))
                p["mouth"] = talk(t, 10.85, 12.35, 6.5, 0.28)
                p["gx"], p["gy"] = 0.0, 0.0
            return held
        return held

    # ---- set ---------------------------------------------------------------------------------------------
    def bg(self, fr, cam, T):
        B.draw_sky(fr, cam)
        B.draw_far(fr, cam)
        B.draw_ground(fr, cam)

    def items(self, cam, T):
        it = B.shelter_items(cam)
        t = T - TB
        if t >= self.KD:
            (x, y, z), th, flat = self.knife_at(t)

            def kn(fr):
                if flat:
                    d = (math.cos(th) * 0.1, 0.0, math.sin(th) * 0.1)
                else:
                    d = (math.cos(th) * 0.1, math.sin(th) * 0.1, 0.0)
                a, b = cam.proj(rig.sub((x, y, z), d)), cam.proj(rig.add((x, y, z), d))
                m = cam.proj((x, y, z))
                fr.c.drawLine(a[0], a[1], m[0], m[1], paint("#2a1c16", stroke=max(2.0, 0.025 * m[3])))
                fr.c.drawLine(m[0], m[1], b[0], b[1], paint("#d9dfea", stroke=max(1.5, 0.018 * m[3])))
            it.append((cam.view((x, y, z))[2], kn, "knife"))
        return it

    def solids(self):
        return B.solids()

    def overlay(self, fr, cam, T, outs):
        B.RAIN.draw(fr, cam, T, light=B.LIGHT)

    def post(self, fr, cam, T):
        t = T - TB
        if t > 8.74:                                          # police lights from off-screen left
            u = win(t, 8.74, 9.3)
            ph = (T * 2.6) % 1.0
            red = 0.5 + 0.5 * math.cos(2 * math.pi * ph)
            for colr, k in (("#ff2a3a", red), ("#2a5cff", 1 - red)):
                fr.c.drawRect(skia.Rect(0, 0, W, H), paint(blend="add", shader=skia.GradientShader.MakeRadial(
                    skia.Point(-200, H * 0.42), W * 1.2, [argb(colr, 0.42 * u * k), argb(colr, 0)], [0, 1])))
        vignette(fr)

    allow = [("jeff", "hand_R", "randy", "hand_L", 0.09), ("jeff", "hand_R", "randy", "head", 0.05),
             ("jeff", "elbow_R", "randy", "hand_L", 0.03), ("jeff", "hand_R", "randy", "elbow_L", 0.04)]
    gaze = {"jeff": [(0.0, "jeff", "hand_L"), (TB + 2.55, "randy", "head"), (TB + 9.6, "liu", "head")],
            "liu": [(TB + 3.0, "randy", "head")], "randy": [(TB + 4.45, "jeff", "head")]}


# =========================================================================================================
# 2. hospital room (hook flash-forward + the bandages scene)
# =========================================================================================================
HOOK_DT = 35.6          # the hook shows the same moment as the unwrapping scene: story time = T + 35.6


class Hospital:
    name = "hospital"
    light = (0.0, 2.65, 2.4)

    def __init__(self):
        r = Room(-3.2, 3.2, -1.8, 5.2, 2.8, "#7d978d", "#8f9895", self.light, ceil="#5e6e69", planks=False, base="#4f5b58")
        r.window("back", -2.5, -1.1, 1.0, 2.2, seed=11)
        r.window("front", 0.5, 1.8, 1.0, 2.2, seed=12)
        r.flat("back", 0.6, 2.2, 0.0, 2.6, "#a9b7c9", a=0.9)                       # curtain
        r.flat("left", 0.8, 1.6, 1.3, 1.8, "#e6e2d6", frame="#5a5040")              # notice board
        r.door("right", 0.2, 1.1, colr="#c4c9cc", inside="#2a3032")
        r.pools.append((0.0, 2.6, 1.8, 1.4, "#ffe2b8", 0.10))
        r.pools.append((-1.8, 4.4, 0.9, 0.6, "#9fb8ff", 0.08))
        self.room = r
        self.J = Track([
            (0.0, dict(wrap=1.0, head_yaw=0.0, head_pitch=6.0, shrug=0.1)),
            (35.75, hold("wrap")), (38.55, dict(wrap=0.0), "io"),
            (37.2, hold("head_pitch")), (37.8, dict(head_pitch=-2.0), "io"),
            (41.8, hold("shrug", "head_pitch")), (42.1, dict(shrug=0.45, head_pitch=-10.0), "out"),
        ])
        self.MOM = Track([
            (0.0, dict(brow=0.45, brow_in=-0.35, smile=0.25, mouth=0.0, lid=0.95, lean=4.0, head_pitch=5.0)),
            (39.50, hold("smile", "mouth", "brow", "brow_in", "lid", "lean")),
            (39.70, dict(smile=-0.45, mouth=0.35, brow=0.95, brow_in=-0.95, lid=1.0, lean=-3.0), "out"),
            (42.2, hold("lean", "head_pitch")), (42.5, dict(lean=-7.0, head_pitch=3.0), "out"),
        ])
        self.DOC = Track([
            (0.0, dict(brow=0.1, mouth=0.0, lean=6.0, head_pitch=10.0, aL=(30.0, 6.0, 85.0))),
            (38.40, hold("brow", "lean", "mouth", "head_pitch")), (38.60, dict(brow=0.75, lean=-4.0, mouth=0.2, head_pitch=4.0), "out"),
        ])

    def cast(self, T):
        T = T + HOOK_DT if T < 30 else T
        out = []
        # Jeff on the bed edge, hands on his knees; later the mirror comes up and he laughs
        jp = seated("jeffw", 0.0, 2.65, 0.0, 0.56, 0.36)
        jp.update(self.J(T))
        if T > 41.8:
            jp["shrug"] += 0.22 * abs(math.sin(2 * math.pi * 4.2 * (T - 41.8)))
            jp["head_pitch"] += 3 * math.sin(2 * math.pi * 4.2 * (T - 41.8))
        J0 = rig.solve("jeffw", jp)
        for s in ("R", "L"):
            knee = rig.add(lerp(J0["hip_" + s], J0["kn_" + s], 0.72), (0, 0.06, 0))     # on the thigh
            sh = J0["sh_" + s]
            d = rig.sub(knee, sh)
            reach = 0.97 * 0.32 * J0["h"]                         # clamp into reach so the hand really rests there
            jp["ik_" + s] = rig.add(sh, rig.mul(rig.norm(d), min(math.dist(knee, sh), reach)))
        held = None
        if T > 40.6:                                          # the mirror rises to his face
            m = J0["Bh"].w(J0["head"], -0.17, -0.10, 0.30)          # in his left hand, beside the face (seen from behind)
            J1 = rig.solve("jeffw", jp)
            jp["ik_L"] = lerp(J1["wr_L"], m, win(T, 40.6, 41.25))
            held = {"L": rig.hand_mirror(face="#f2f2ee")}
        out.append(("jeff", "jeffw", jp, held, None))
        # the doctor unwinds the gauze with his right hand (loops beside the head), left hand holds the roll
        dp = dict(x=0.56, z=2.27, yaw=-116.0)
        dp.update(self.DOC(T))
        if T > 38.8:                                          # steps back from the bed once the gauze is off
            a0 = ankles("doctor", dp)
            a1 = ankles("doctor", dict(dp, x=0.95, z=1.95, yaw=-130.0))
            u = win(T, 38.8, 39.5)
            dp.update(x=0.56 + 0.39 * u, z=2.27 - 0.32 * u, yaw=-116.0 - 14.0 * u)
            dp.update(rig.replant(T, a0, [("R", 38.8, 0.32, a1["R"]), ("L", 39.1, 0.32, a1["L"])], rig.LOOK["doctor"]["h"]))
        JH = J0["head"]
        if 35.6 < T < 38.7:
            w = win(T, 35.6, 35.85) * (1 - win(T, 38.5, 38.7))
            ph = 2 * math.pi * (T - 35.7) / 0.85
            tgt = rig.add(JH, (0.27, 0.02 + 0.07 * math.cos(ph), 0.05 * math.sin(ph)))      # loop stays clear of his head
            dp["aR"] = (30.0, 10.0, 70.0)
            blend_ik("doctor", dp, "R", tgt, w)
        else:
            dp["aR"] = (30.0, 10.0, 70.0)
        out.append(("doctor", "doctor", dp, {"L": _gauze_roll}, None))
        mp = dict(x=-0.75, z=1.95, yaw=133.0)
        mp.update(self.MOM(T))
        if T > 43.6:
            mp["mouth"] = 0.25 + 0.07 * math.sin(T * 17)
            mp["head_yaw"] = 6 * math.sin(2 * math.pi * 0.9 * (T - 44.0)) * win(T, 44.0, 44.4)
        Jm = rig.solve("mother", mp)
        # hands held together in front of the chest, each on its own side (+r is her right), elbows tucked down at
        # her sides so the forearms never cross; at the reveal both hands rise to her chin
        Bc = Jm["Bc"]
        chest = Bc.w(Jm["pelvis"], 0.0, 0.20 * 1.63, 0.17)
        chin = Jm["Bh"].w(Jm["head"], 0.0, -1.05 * Jm["R"], 0.95 * Jm["R"])
        u = win(T, 39.75, 40.2) if T > 39.7 else 0.0
        for s, sgn in (("R", 1), ("L", -1)):
            mp["ik_" + s] = lerp(rig.add(chest, Bc.d(sgn * 0.04, 0, 0)), rig.add(chin, Bc.d(sgn * 0.05, 0, 0)), u)
            mp["pole_" + s] = rig.norm(Bc.d(sgn * 0.45, -1.0, 0.1))
        out.append(("mother", "mother", mp, None, None))
        fp = dict(x=-1.35, z=2.4, yaw=102.0, brow=0.5, brow_in=-0.5, lid=0.9, head_pitch=10.0, aR=(6.0, 6.0, 25.0), aL=(10.0, 8.0, 30.0))
        fp["brow"] += 0.4 * win(T, 42.2, 42.5, "out")
        fp["lean"] = -6 * win(T, 42.2, 42.5, "out")
        out.append(("father", "father", fp, None, None))
        lp = dict(x=-1.25, z=1.45, yaw=131.0, brow=0.6, brow_in=-0.7, lid=0.95, head_pitch=6.0, aR=(8.0, 6.0, 20.0), aL=(8.0, 6.0, 20.0))
        lp["shrug"] = 0.6 * win(T, 42.2, 42.5, "out")
        out.append(("liu", "liu", lp, None, None))
        offs = {"jeff": 0.0, "doctor": 1.3, "mother": 2.1, "father": 0.7, "liu": 3.0}
        for pid, look, p, _, _ in out:
            p["lid"] = p.get("lid", 1.0) * blink(T, [36.4 + offs[pid], 40.9 + offs[pid] * 0.7, 44.1 + offs[pid] * 0.5])
        return out

    def bg(self, fr, cam, T):
        self.room.draw(fr, cam, T + HOOK_DT if T < 30 else T)

    def items(self, cam, T):
        it = bed_items(cam, (-1.0, 1.0), (2.5, 3.45), top=0.55, sheet="#e9edf2", frame="#9aa3ab", rail=True)
        it.append(box_item(cam, (-1.42, -1.38), (0.0, 1.9), (3.18, 3.22), "#b8bec4", "iv"))
        it.append(box_item(cam, (-1.5, -1.3), (1.45, 1.75), (3.15, 3.25), "#cfe3e8", "ivbag"))

        def monitor(fr):
            fr.box(cam, (1.25, 1.31), (0.0, 1.05), (3.2, 3.26), "#8a9096")
            fr.box(cam, (1.05, 1.5), (1.05, 1.38), (3.15, 3.3), "#2a3036")
            pts = [(1.08 + 0.02 * i, 1.2 + (0.08 if i % 7 == 3 else 0.0) - (0.05 if i % 7 == 4 else 0.0), 3.145) for i in range(20)]
            if cam.pos[2] < 3.15:
                q = [cam.proj(p)[:2] for p in pts]
                path = skia.Path()
                path.moveTo(*q[0])
                for x in q[1:]:
                    path.lineTo(*x)
                fr.c.drawPath(path, paint("#5dff8a", stroke=2.0))
                x, y, _, s = cam.proj((1.27, 1.2, 3.14))
                fr.glow(x, y, 0.3 * s, "#3dff7a", a=0.25)
        it.append((cam.view((1.27, 0.7, 3.23))[2], monitor, "monitor"))

        def ceiling(fr):
            fr.box(cam, (-0.6, 0.6), (2.74, 2.8), (2.1, 2.7), "#f4f8ff")
        it.append((cam.view((0, 2.77, 9.0))[2], ceiling, "ceiling"))
        return it

    def overlay(self, fr, cam, T, outs):
        T = T + HOOK_DT if T < 30 else T
        j, d = outs.get("jeff"), outs.get("doctor")
        if j and d and "wrap_pt" in j and 35.7 < T < 38.6 and d.get("hand_R"):
            a, b = j["wrap_pt"], d["hand_R"]
            path = skia.Path()
            path.moveTo(*a)
            path.quadTo((a[0] + b[0]) / 2, max(a[1], b[1]) + 30, *b)
            fr.c.drawPath(path, paint("#e9e3d6", stroke=max(3.0, j["head_r"] * 0.16)))
            fr.c.drawPath(path, paint("#a89f8e", stroke=max(1.0, j["head_r"] * 0.04), a=0.6))
            hang = skia.Path()
            hang.moveTo(*b)
            hang.quadTo(b[0] + 10, b[1] + 60, b[0] - 5, b[1] + 120)
            fr.c.drawPath(hang, paint("#e9e3d6", stroke=max(3.0, j["head_r"] * 0.14)))

    def post(self, fr, cam, T):
        vignette(fr, 0.5)

    def solids(self):
        return {"bed": ((-1.0, 1.0), (0.0, 0.55), (2.5, 3.45)), "iv": ((-1.42, -1.38), (0.0, 1.9), (3.18, 3.22)),
                "monitor": ((1.05, 1.5), (0.0, 1.38), (3.15, 3.3))}

    allow = [("jeff", "", "bed", "", 0.2), ("doctor", "hand_R", "jeff", "head", 0.03)]
    gaze = {"mother": [(0.0, "jeff", "head")], "doctor": [(0.0, "jeff", "head")]}


def _gauze_roll(fr, cam, J, s, hd, fd, k):
    r = 0.03 * J["h"] * k
    fr.part(_circle(hd[0], hd[1] - r * 0.3, r), "#ece6da", (0.3, 1.0), width=2 * r, line=1.2)


def _circle(x, y, r):
    p = skia.Path()
    p.addCircle(x, y, r)
    return p


# =========================================================================================================
# 3. upstairs hallway at the party
# =========================================================================================================
class Party:
    name = "party"
    light = (0.0, 2.4, 3.2)

    def __init__(self):
        r = Room(-1.2, 1.2, -0.6, 9.0, 2.6, "#5b3040", "#4a3428", self.light, ceil="#2e1a22", base="#2a1a1a")
        for z0 in (1.0, 5.2):
            r.door("left", z0, z0 + 0.85, colr="#5a3a2a", inside="#08060a")
            r.door("right", z0 + 0.6, z0 + 1.45, colr="#5a3a2a", inside="#08060a")
        r.flat("left", 3.0, 3.6, 1.3, 1.8, "#8a7a5a", frame="#2a1a10")
        r.flat("right", 3.4, 4.1, 1.25, 1.75, "#5a6a8a", frame="#2a1a10")
        r.window("back", 0.3, 0.95, 1.1, 1.9, seed=21)
        r.flat("back", -1.15, -0.2, 0.0, 2.2, "#ff5ac8", a=0.0)
        self.room = r

    def cast(self, T):
        out = []
        tt = T - 25.82
        jp = dict(x=0.0, z=3.0, yaw=0.0, aR=(-28.0, 18.0, 28.0), aL=(-28.0, 18.0, 28.0), brow=0.8, brow_in=-0.8, lid=1.0, mouth=0.25,
                  shrug=0.6, lean=-3.0, head_pitch=2.0, gx=0.4)
        jp["twist"] = 11 * math.sin(2 * math.pi * 0.9 * tt)
        jp["side"] = 4 * math.sin(2 * math.pi * 0.9 * tt + 1.2)
        jp["head_yaw"] = 16 * math.sin(2 * math.pi * 0.6 * tt) * (1 - win(T, 28.7, 28.95))
        jp["mouth"] = 0.25 + talk(T, 26.0, 28.6, 3.0, 0.12)
        if T > 28.82:                                         # soaked: eyes shut, head down, coughing
            s = win(T, 28.82, 28.95, "out")
            jp.update(lid=1 - 0.95 * s, head_pitch=2 + 16 * s, brow_in=-0.8 + 1.4 * s, brow=0.8 - 0.4 * s, smile=-0.6 * s, shrug=0.6 + 0.3 * s)
            jp["head_yaw"] = -14 * s + 5 * math.sin(T * 13) * s
        jp["lid"] *= blink(T, [26.6, 27.9])
        J = rig.solve("jeff", jp)
        out.append(("jeff", "jeff", jp, None, None))
        h = 1.7
        for pid, x, yaw, sg in (("bully", -0.62, 90.0, -1), ("bully2", 0.62, -90.0, 1)):
            bp = dict(x=x, z=3.12, yaw=yaw, lean=6.0, smile=0.5, brow_in=0.6, lid=0.85, head_pitch=4.0, head_yaw=-25.0 * sg * -1)
            bp["side"] = jp["side"] * 0.4
            s = "R" if sg < 0 else "L"
            up = lerp(J["sh_" + s], J["el_" + s], 0.55)
            el = J["el_" + s]
            near = "R" if sg < 0 else "L"           # the bully's camera-side hand takes Jeff's elbow
            far = "L" if near == "R" else "R"
            bp["ik_" + near] = rig.add(el, (sg * 0.05, 0.03, -0.05))
            bp["ik_" + far] = rig.add(up, (sg * 0.05, 0.035, 0.06))
            out.append((pid, pid, bp, None, None))
        rp = dict(x=0.42, z=2.45, yaw=-150.0, smile=0.55, brow_in=0.8, lid=0.8, lean=4.0, aL=(10.0, 8.0, 40.0), aR=(6.0, 8.0, 18.0),
                  head_pitch=-4.0, gx=0.0)
        rp["lean"] += 8 * win(T, 28.3, 28.7)
        held = {"L": rig.bottle(110 * win(T, 28.55, 28.95) * (1 - win(T, 30.45, 30.75)))}
        top = rig.add(J["head"], (0.12, 0.26, -0.12))
        blend_ik("randy", rp, "L", top, win(T, 28.2, 28.65) * (1 - win(T, 30.5, 30.85)))
        if T >= 30.87:                         # the match insert: matchbox in the left hand, match in the right
            rp = dict(x=0.42, z=2.45, yaw=-150.0, smile=0.7, brow_in=0.9, lid=0.72, lean=2.0, head_pitch=8.0, gx=0.0, gy=0.6,
                      aL=(30.0, -18.0, 100.0), aR=(40.0, 6.0, 90.0))       # box at chest height: the strike stays below the face
            JR = rig.solve("randy", rp)
            box = rig.add(JR["hand_L"], rig.mul(JR["Bc"].r, -0.01))
            start = rig.add(box, (0.0, 0.05, 0.0))
            sw = rig.add(start, rig.add(rig.mul(JR["Bc"].r, -0.10), (0, -0.05, 0)))
            face = JR["Bc"].w(JR["pelvis"], 0.22, 0.29 * 1.8, 0.30)       # below and beside the face, so it stays visible
            if T < 31.30:
                tgt = lerp(JR["wr_R"], start, win(T, 30.87, 31.15))
            elif T < 31.42:
                tgt = lerp(start, sw, win(T, 31.30, 31.42, "snap"))
            elif T < 32.2:
                tgt = lerp(sw, face, win(T, 31.45, 31.9))
            else:
                tgt = lerp(face, rig.add(face, rig.mul(JR["Bb"].f, 0.25)), win(T, 32.2, 32.38, "snap"))
            rp["ik_R"] = tgt
            lit = 0.0 if T < 31.42 else (1.6 - 0.6 * win(T, 31.42, 31.7))
            held = {"L": rig.matchbox(), "R": rig.match(lit if T < 32.36 else 0.0, T)}
            glow = (rig.add(JR["head"], (0, -0.12, 0)), 0.45, "#ff9a40", 0.45 * min(lit, 1.0)) if lit and T < 32.36 else None
            out.append(("randy", "randy", rp, held, glow))
            return out
        out.append(("randy", "randy", rp, held, None))
        return out

    def bg(self, fr, cam, T):
        self.room.draw(fr, cam, T)
        # party light pulsing up the stairwell at the far end
        p = cam.proj((-0.6, 1.2, 8.9))
        if cam.view((-0.6, 1.2, 8.9))[2] > 0.2:
            beat = 0.5 + 0.5 * math.sin(T * 2 * math.pi * 2.0)
            fr.glow(p[0], p[1], 1.6 * p[3], "#ff4ab8" if int(T * 2) % 2 else "#7a4aff", a=0.35 + 0.2 * beat)

    def items(self, cam, T):
        it = []

        def bulb(fr):
            x, y, _, s = cam.proj(self.light)
            fr.c.drawCircle(x, y, 0.05 * s, paint("#fff2d0"))
            fr.glow(x, y, 1.4 * s, "#ffb46a", a=0.35)
        it.append((cam.view(self.light)[2] + 3, bulb, "bulb"))
        it.append(box_item(cam, (0.9, 1.2), (0.0, 0.75), (6.6, 7.1), "#3e2a20", "dresser"))
        return it

    def overlay(self, fr, cam, T, outs):
        r, j = outs.get("randy"), outs.get("jeff")
        if r and j and j.get("head") and 28.8 < T < 30.6 and "prop_tip" in r["J"]:
            a = r["J"]["prop_tip"]
            b = (j["head"][0] + 0.15 * j["head_r"], j["head"][1] - 0.8 * j["head_r"])
            path = skia.Path()
            path.moveTo(*a)
            path.cubicTo(a[0], a[1] + 40, b[0] + 6 * math.sin(T * 40), (a[1] + b[1]) / 2, *b)
            fr.c.drawPath(path, paint("#e8d9a0", a=0.6, stroke=max(3.0, j["head_r"] * 0.09)))
            fr.c.drawPath(path, paint("#ffffff", a=0.35, stroke=max(1.0, j["head_r"] * 0.03)))
        if j and j.get("head") and T > 28.85:                 # liquid running down the face and shirt, drips
            R = j["head_r"]
            rng = np.random.default_rng(3)
            for i in range(9):
                x = j["head"][0] + rng.uniform(-0.9, 0.9) * R
                y0 = j["head"][1] - rng.uniform(0.2, 0.8) * R
                L = R * (0.4 + 1.6 * min(1.0, (T - 28.85) * rng.uniform(0.5, 1.2)))
                fr.c.drawLine(x, y0, x + rng.uniform(-4, 4), y0 + L, paint("#d9e6ff", a=0.35, stroke=max(1.2, R * 0.05)))
            for i in range(6):
                ph = (T * 1.3 + i / 6) % 1.0
                x = j["head"][0] + (i - 2.5) * 0.3 * R
                y = j["head"][1] + R * 1.0 + ph * R * 3
                fr.c.drawCircle(x, y, max(1.5, R * 0.035), paint("#e9f0ff", a=0.6 * (1 - ph)))

    def post(self, fr, cam, T):
        if 32.36 < T < 32.6 and cam.pos[1] < 1.4:                    # the thrown match flies at the lens
            u = (T - 32.36) / 0.24
            fr.glow(W * 0.5, H * 0.45, 120 + 900 * u, "#ff9a40", a=0.6 * u)
        vignette(fr, 0.55)
        if T > 32.5:                                           # the flare, then black
            a = win(T, 32.5, 32.62, "out")
            fr.c.drawRect(skia.Rect(0, 0, W, H), paint("#ff7a1a", a=a * (1 - win(T, 32.62, 32.95))))
            fr.c.drawRect(skia.Rect(0, 0, W, H), paint("#000000", a=win(T, 32.62, 32.95)))

    def solids(self):
        return {"wall_l": ((-1.3, -1.2), (0, 2.6), (-0.6, 9.0)), "wall_r": ((1.2, 1.3), (0, 2.6), (-0.6, 9.0)),
                "dresser": ((0.9, 1.2), (0.0, 0.75), (6.6, 7.1))}

    allow = [("bully", "hand", "jeff", "", 0.07), ("bully2", "hand", "jeff", "", 0.07),
             ("randy", "hand_L", "jeff", "head", 0.02)]
    gaze = {"randy": [(0.0, "jeff", "head")]}


# =========================================================================================================
# 4. home hallway at night, 5. parents' bedroom, 6. Liu's bedroom
# =========================================================================================================
class Hall:
    name = "hall"
    light = (-0.85, 0.35, 2.2)                               # a small night-light low on the left wall

    def __init__(self):
        r = Room(-0.9, 0.9, -1.0, 8.0, 2.5, "#3a4460", "#3e3129", self.light, ceil="#1c2233", base="#1e2230")
        r.door("left", 3.0, 3.8, colr="#5c4636", inside="#05060a")
        r.door("right", 5.6, 6.4, colr="#5c4636", inside="#05060a", open_fn=self.door_open, hinge="a1", spill=("#dfe8ff", 0.95))
        r.flat("left", 5.0, 5.7, 1.3, 1.85, "#6a6a52", frame="#2a1e14")
        r.window("back", -0.45, 0.45, 1.0, 2.0, seed=31)
        r.pools.append((-0.6, 2.2, 0.5, 0.35, "#ffb46a", 0.25))
        self.room = r
        self.MW = dict(start=(0.42, 0, 3.45), yaw=180.0, step=0.5, rate=1.9, n=4, t0=45.95)

    def door_open(self, T):
        return 0.06 + 0.55 * win(T, 48.95, 49.4)

    def cast(self, T):
        h = rig.LOOK["mother"]["h"]
        g = rig.gait(T, self.MW["start"], self.MW["yaw"], self.MW["step"], self.MW["rate"], n=self.MW["n"], t0=self.MW["t0"], h=h)
        sw = g["swing"]
        p = dict(x=g["x"], z=g["z"], yaw=180.0, bob=g.get("bob", 0.0), lean=3.0, ankle_R=g["ankle_R"], ankle_L=g["ankle_L"],
                 aR=(-sw * 16 + 2, 7.0, 22.0), aL=(sw * 16 + 2, 7.0, 22.0), brow=0.35, brow_in=-0.45, lid=0.9, head_pitch=6.0,
                 plant=g["plant"])
        stop = self.MW["t0"] + self.MW["n"] / self.MW["rate"]
        if T > stop:
            a0 = {"R": g["ankle_R"], "L": g["ankle_L"]}
            fin = dict(p, x=0.45, z=5.72, yaw=100.0)
            a1 = ankles("mother", fin)
            u = win(T, 48.1, 48.7)
            p["x"] = g["x"] + (0.45 - g["x"]) * u
            p["z"] = g["z"] + (5.72 - g["z"]) * u
            p["yaw"] = 180.0 + (100.0 - 180.0) * u
            p.update(rig.replant(T, a0, [("R", 48.12, 0.3, a1["R"]), ("L", 48.40, 0.3, a1["L"])], h))
            p["head_yaw"] = 0.0
            p["lean"] = 3.0 + 4 * win(T, 48.5, 48.9)
            hz = win(T, 49.12, 49.3, "out")
            p.update(brow=0.35 + 0.6 * hz, brow_in=-0.45 - 0.5 * hz, mouth=0.42 * hz, lid=0.9 + 0.1 * hz, lid_lo=0.0, lean=p["lean"] - 6 * hz,
                     shrug=0.5 * hz)
            edge = rig.add(self.room.door_edge("right", 5.6, 6.4, self.door_open(T), 1.0, hinge="a1"), (-0.08, 0, 0.12))   # fingers on the edge, not in the wall
            reach = win(T, 48.55, 48.95) * (1 - win(T, 49.02, 49.3))      # pushes, then lets the door swing on
            p["aR"], p["aL"] = (10.0, 8.0, 30.0), (8.0, 6.0, 22.0)
            blend_ik("mother", p, "R", edge, reach)
            Jm = rig.solve("mother", p)
            mouth = Jm["Bh"].w(Jm["head"], 0.0, -0.6 * Jm["R"], 1.15 * Jm["R"])
            blend_ik("mother", p, "L", mouth, win(T, 49.45, 49.85))
        p["lid"] *= blink(T, [46.6, 47.9])
        op = self.door_open(T)
        Jm = rig.solve("mother", p)
        glow = (rig.add(Jm["head"], (0.3, 0.0, 0.1)), 0.35, "#dfe8ff", 0.15 + 0.6 * win(T, 48.95, 49.4) if op > 0.07 else 0.08)
        return [("mother", "mother", p, None, glow)]

    def bg(self, fr, cam, T):
        self.room.draw(fr, cam, T)
        op = self.door_open(T)
        # light from Jeff's room spilling across the hallway floor through the gap
        e = self.room.door_edge("right", 5.6, 6.4, op, 0.0, hinge="a1")
        q = [(0.9, 0.003, 5.6), (e[0], 0.003, e[2]), (-0.4, 0.003, 6.4 + 0.3 * op), (-0.4, 0.003, 5.6 - 0.2 * op)]
        fr.poly(cam, q, colr="#cfdcff", a=0.12 + 0.3 * op)

    def items(self, cam, T):
        def nl(fr):
            x, y, _, s = cam.proj(self.light)
            fr.glow(x, y, 0.6 * s, "#ffb46a", a=0.6)
            fr.c.drawCircle(x, y, 0.03 * s, paint("#ffe6b8"))
        return [(cam.view(self.light)[2] + 3, nl, "nightlight")]

    def overlay(self, fr, cam, T, outs):
        pass

    def post(self, fr, cam, T):
        if cam.pos[0] > 0.95:                       # seen from inside Jeff's dark room: only the door opening shows
            q = [cam.proj(p)[:2] for p in ((0.9, 0.0, 5.6), (0.9, 2.05, 5.6), (0.9, 2.05, 6.4), (0.9, 0.0, 6.4))]
            hole = skia.Path()
            hole.moveTo(*q[0])
            for x in q[1:]:
                hole.lineTo(*x)
            hole.close()
            full = skia.Path()
            full.addRect(skia.Rect(-10, -10, W + 10, H + 10))
            fr.c.drawPath(skia.Op(full, hole, skia.PathOp.kDifference_PathOp), paint("#07080d"))
            e0 = self.room.door_edge("right", 5.6, 6.4, self.door_open(T), 0.0, hinge="a1")
            e1 = self.room.door_edge("right", 5.6, 6.4, self.door_open(T), 2.05, hinge="a1")
            fr.poly(cam, [(0.9, 0.0, 6.4), (0.9, 2.05, 6.4), e1, e0], colr="#1e2129", outline="#2c303b", line=2.0)    # the door's dark inner face
            fr.c.drawPath(hole, paint("#cfdcff", a=0.05, blend="add"))
        vignette(fr, 0.6)

    def solids(self):
        return {"wall_l": ((-1.0, -0.9), (0, 2.5), (-1, 8)), "wall_r": ((0.9, 1.0), (0, 2.5), (-1, 5.6)),
                "wall_r2": ((0.9, 1.0), (0, 2.5), (6.4, 8))}

    allow = [("mother", "hand_R", "wall_r", "", 0.04)]
    gaze = {}


class Bedroom:
    """Parents' room (kind="parents") or Liu's room (kind="liu"): bed against the back wall, door top-left,
    window with rain on the right, a lamp on the nightstand."""

    def __init__(self, kind):
        self.kind = kind
        self.name = kind
        if kind == "parents":
            self.light = (-1.27, 0.95, 3.62)
            r = Room(-2.6, 2.0, -1.2, 4.0, 2.5, "#33405c", "#3e3129", self.light, ceil="#1a2030", base="#1e2230")
            r.door("back", -2.05, -1.35, colr="#5c4636", inside="#0d1018", open_fn=lambda T: 0.85)
            r.window("back", 0.9, 1.7, 1.0, 2.0, seed=41)
            r.flat("back", -0.8, 0.8, 0.9, 1.25, "#4a3428")                 # headboard
            r.flat("left", 0.5, 1.4, 1.2, 1.8, "#6a7a6a", frame="#2a1e14")
            r.pools.append((1.3, 3.4, 0.6, 0.4, "#9fb8ff", 0.10))
            self.bed = ((-0.9, 0.9), (2.0, 4.0))
        else:
            self.light = (1.35, 2.0, 4.5)                                      # moonlight through the window
            r = Room(-2.4, 2.2, -1.2, 4.0, 2.5, "#2e3a58", "#3a2f2a", self.light, ceil="#181e2e", base="#1c2030")
            r.door("back", -2.1, -1.4, colr="#5c4636", inside="#1a1e28", open_fn=lambda T: 0.7, spill=("#3a4258", 0.6))
            r.window("back", 0.9, 1.8, 1.0, 2.0, sky="#16244a", glow=("#cfe0ff", 0.55), seed=51)
            r.flat("back", -0.4, 0.5, 0.75, 1.05, "#4a3428")
            r.flat("left", 0.4, 1.1, 1.3, 2.0, "#a8423a", frame="#202020")    # a band poster
            r.flat("left", 1.4, 1.9, 1.4, 1.9, "#3a7a9a", frame="#202020")
            r.pools.append((0.6, 2.9, 0.9, 0.5, "#9fb8ff", 0.14))
            self.bed = ((-0.45, 0.55), (2.0, 4.0))
        self.room = r
        if kind == "parents":
            self.MW = dict(start=(-1.72, 0, 4.35), yaw=0.0, step=0.42, rate=2.6, n=3, t0=49.96)   # straight in, left of the nightstand

    # ---- parents ---------------------------------------------------------------------------------------
    def _parents(self, T):
        out = []
        fp = seated("father", -0.35, 3.45, 0.0, 0.56, 0.62, feet_y=0.62, lean=-18.0, lid=0.0, head_pitch=4.0, head_yaw=0.0,
                    aR=(14.0, 10.0, 60.0), aL=(14.0, 10.0, 60.0), brow=0.0)
        wake = win(T, 52.1, 52.3, "out")
        fp["lid"] = 1.0 * wake
        fp["brow"] = 0.6 * wake
        fp["brow_in"] = -0.5 * wake
        fp["head_yaw"] = -30 * win(T, 52.2, 52.5)
        fp["lean"] = -18 + 22 * win(T, 52.4, 52.95)
        fp["mouth"] = 0.2 * wake
        if T > 53.15:                                          # reaches for the drawer
            u = win(T, 53.15, 53.75)
            fp["lean"] += 16 * u
            fp["side"] = 22 * u
            fp["head_yaw"] = -30 + 0 * u
            fp["head_pitch"] = 4 + 16 * u
            handle = (-1.27, 0.5, 3.32)
            blend_ik("father", fp, "R", handle, u)
            fp["head_yaw"] = -30 - 30 * win(T, 54.0, 54.25, "out")          # turns to the doorway
        out.append(("father", "father", fp, None, None))
        h = rig.LOOK["mother"]["h"]
        g = rig.gait(T, self.MW["start"], self.MW["yaw"], self.MW["step"], self.MW["rate"], n=self.MW["n"], t0=self.MW["t0"], h=h)
        sw = g["swing"]
        mp = dict(x=g["x"], z=g["z"], yaw=self.MW["yaw"], bob=g.get("bob", 0.0), lean=10.0, ankle_R=g["ankle_R"], ankle_L=g["ankle_L"],
                  aR=(-sw * 20 + 4, 9.0, 40.0), aL=(sw * 20 + 4, 9.0, 40.0), brow=0.95, brow_in=-0.95, lid=1.0, mouth=0.25, plant=g["plant"],
                  head_pitch=0.0)
        stop = self.MW["t0"] + self.MW["n"] / self.MW["rate"]
        if T > stop:
            a0 = {"R": g["ankle_R"], "L": g["ankle_L"]}
            fin = dict(mp, x=-1.15, z=3.08, yaw=118.0)
            a1 = ankles("mother", fin)
            u = win(T, stop + 0.02, stop + 0.62)
            mp["x"] = g["x"] + (-1.15 - g["x"]) * u
            mp["z"] = g["z"] + (3.08 - g["z"]) * u
            mp["yaw"] = self.MW["yaw"] + (118.0 - self.MW["yaw"]) * u
            mp.update(rig.replant(T, a0, [("R", stop + 0.02, 0.3, a1["R"]), ("L", stop + 0.3, 0.3, a1["L"])], h))
            mp["lean"] = 10 + 14 * win(T, 51.4, 51.7) - 18 * win(T, 52.95, 53.3)
            mp["aR"], mp["aL"] = (10.0, 8.0, 30.0), (20.0, 8.0, 60.0)
            mp["mouth"] = 0.15 + talk(T, 51.95, 52.45, 7.0, 0.3)
            mp["head_pitch"] = 14.0
            Jf = rig.solve("father", fp)
            sh = rig.add(Jf["sh_R"], (0.0, 0.03 + 0.03 * math.sin(T * 26) * win(T, 51.75, 51.9) * (1 - win(T, 52.8, 52.95)), -0.04))
            blend_ik("mother", mp, "R", sh, win(T, 51.45, 51.75) * (1 - win(T, 52.95, 53.25)))
            if T > 53.0:                                        # steps back, then turns to the doorway
                b0 = a1
                fin2 = dict(fin, x=-1.35, z=2.35, yaw=118.0)
                b1 = ankles("mother", fin2)
                v = win(T, 53.05, 53.6)
                mp["x"] = -1.15 + (-1.35 + 1.15) * v
                mp["z"] = 3.08 + (2.35 - 3.08) * v
                mp["yaw"] = 118.0
                mp.update(rig.replant(T, b0, [("R", 53.05, 0.28, b1["R"]), ("L", 53.32, 0.28, b1["L"])], h))
                mp["head_yaw"] = -70 * win(T, 53.9, 54.2, "out")
                mp["head_pitch"] = 2.0
                mp["mouth"] = 0.15 + 0.3 * win(T, 54.15, 54.3)
        out.append(("mother", "mother", mp, None, None))
        if T > 53.35:                                           # the figure fills the doorway
            sp = dict(x=-1.68, z=4.5, yaw=0.0, lean=2.0, head_pitch=6.0)
            a = ankles("shadow", sp)
            sp["z"] = 4.5 - 0.25 * win(T, 53.4, 53.8)
            sp.update(rig.replant(T, a, [("R", 53.4, 0.3, rig.add(a["R"], (0, 0, -0.25))), ("L", 53.62, 0.3, rig.add(a["L"], (0, 0, -0.25)))],
                                  rig.LOOK["shadow"]["h"]))
            out.append(("figure", "shadow", sp, None, None))
        return out

    # ---- Liu ---------------------------------------------------------------------------------------------
    def _liu(self, T):
        out = []
        lp = seated("liup", 0.05, 3.45, 0.0, 0.56, 0.6, feet_y=0.62, lean=-22.0, lid=0.0, head_pitch=6.0, aR=(14.0, 8.0, 50.0),
                    aL=(14.0, 8.0, 50.0))
        lp["lid"] = win(T, 55.9, 56.15, "out") * (1 - 0.6 * (1 - win(T, 56.15, 56.6)))
        lp["lid"] = max(lp["lid"], 0.0) * blink(T, [57.0])
        lp["lean"] = -22 + 14 * win(T, 56.5, 57.2)
        lp["head_yaw"] = 30 * win(T, 57.6, 58.6)                 # turns to the figure
        lp["gx"] = -0.6 * win(T, 57.5, 57.8)
        fear = win(T, 58.6, 59.2)
        lp.update(brow=0.9 * fear, brow_in=-0.9 * fear, mouth=0.12 * fear, shrug=0.6 * fear)
        if T > 59.9:
            u = win(T, 59.9, 61.0)
            lp["lean"] = -8 - 18 * u
            lp["shrug"] = 0.6 + 0.3 * u
            lp["lid"] = 1.0
            lp["mouth"] = 0.22 + 0.05 * math.sin(T * 21)
            lp["brow"], lp["brow_in"] = 1.0, -1.0
            lp["head_yaw"] = 30 - 10 * u
        out.append(("liu", "liup", lp, None, None))
        look = "jeffk" if T >= 64.0 else "shadow"
        sp = dict(x=-0.65, z=3.2, yaw=125.0, lean=0.0, head_pitch=4.0, grin=win(T, 58.6, 59.3), aR=(6.0, 6.0, 16.0), aL=(6.0, 6.0, 16.0))
        u = win(T, 63.2, 64.2)                                 # after the whisper he rises a little, still bent over
        sp["lean"] = 45 * win(T, 59.9, 61.3) - 20 * u
        sp["head_pitch"] = 4 + 8 * win(T, 59.9, 61.3) + 6 * u
        sp["head_roll"] = 14 * u
        if look == "jeffk":
            sp.update(smile=1.4, mouth=0.3, mouth_w=1.0, gx=0.35, gy=0.45, brow=-0.2, brow_in=0.6)
        if T >= 57.4:                                          # revealed by the cut to his side of the bed
            out.append(("figure", look, sp, None, ((-0.2, 1.8, 3.9), 0.5, "#cfe0ff", 0.25) if look == "jeffk" else None))
        return out

    def cast(self, T):
        return self._parents(T) if self.kind == "parents" else self._liu(T)

    def lamp_on(self, T):
        if self.kind != "parents":
            return 0.0
        if T < 54.45:
            return 1.0
        return 0.0 if T > 54.62 else (0.5 + 0.5 * math.cos((T - 54.45) * 60)) * (1 - win(T, 54.45, 54.62))

    def bg(self, fr, cam, T):
        self.room.draw(fr, cam, T)
        if self.kind == "liu":                                  # moonbeam through the window onto the bed
            q = [(0.9, 1.0, 3.98), (1.8, 1.0, 3.98), (0.9, 0.56, 2.6), (0.1, 0.56, 2.8)]
            fr.poly(cam, q, colr="#9fb8ff", a=0.06)

    def items(self, cam, T):
        (x0, x1), (z0, z1) = self.bed
        if self.kind == "parents":
            it = bed_items(cam, (x0, x1), (z0, z1), sheet="#d9dce4", frame="#5a3e2c", pillow_z=(3.6, 3.95),
                           blanket=((x0 + 0.04, x1 - 0.04), (z0 + 0.04, 3.32), "#5a6c94"), skirt=True)
            it.append(box_item(cam, (-1.5, -1.05), (0.0, 0.62), (3.35, 3.9), "#5a3e2c", "nightstand"))
            it.append(box_item(cam, (-1.42, -1.13), (0.36, 0.56), (3.33, 3.36), "#6a4a34", "drawer"))
            it.append(lamp_item(cam, (-1.27, 0.62, 3.62), self.lamp_on(T)))
        else:
            it = bed_items(cam, (x0, x1), (z0, z1), sheet="#c9d0e0", frame="#4a5a7a", pillow_z=(3.6, 3.95),
                           blanket=((x0 + 0.03, x1 - 0.03), (z0 + 0.04, 3.3), "#3f5a8a"))
            it.append(box_item(cam, (0.8, 1.2), (0.0, 0.55), (3.45, 3.9), "#4a3a30", "nightstand"))
        return it

    def overlay(self, fr, cam, T, outs):
        pass

    def post(self, fr, cam, T):
        if self.kind == "parents":
            wash(fr, "#000000", 0.45 * (1 - self.lamp_on(T)) if T > 54.45 else 0.0, blend=None)
            if T > 54.6:
                wash(fr, "#000000", win(T, 54.6, 54.8), blend=None)
        vignette(fr, 0.6)

    def solids(self):
        (x0, x1), (z0, z1) = self.bed
        s = {"bed": ((x0, x1), (0.0, 0.55), (z0, z1))}
        s["nightstand"] = ((-1.5, -1.05), (0.0, 0.62), (3.35, 3.9)) if self.kind == "parents" else ((0.8, 1.2), (0.0, 0.55), (3.45, 3.9))
        return s

    allow = [("father", "", "bed", "", 0.2), ("liu", "", "bed", "", 0.2), ("mother", "hand_R", "father", "", 0.05),
             ("father", "hand_R", "nightstand", "", 0.03), ("figure", "head", "liu", "", 0.0)]
    gaze = {}
