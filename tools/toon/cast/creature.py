"""Mara species: small ancient nightmare creatures (~0.56 m standing) that crawl into bedrooms and settle on
sleepers. Own skeleton (hunched spine, jutting head, short legs that fold into a deep
squat, thin arms, oversized hands and feet), drawn with the toon engine's shading so it sits in the same world.

    out = creature.draw(fr, cam, "mara", pose, light=(..), rim=dict(d=(-1, -0.3), col="#7fa8ff", a=0.7),
                        cheek=("#a46bff", 0.2, +1))
    out["J"], out["contacts"] (world hand/foot points for mattress dents), out["grab"] (collar / hem / sleeve)

Pose keys (metres scale with the look's h): x, z, yaw, floor, crouch (1 = resting deep squat, 0 = standing), lean
(extra forward pitch), twist, head_yaw, head_pitch, head_roll, breath (-1..1), ankle_R/L (world, planted feet),
ik_R/ik_L (world wrist targets; default: hands planted in front of the feet), pole_R/L, aR/aL (FK like rig: pitch,
roll, bend) when no ik, curl_R/L (0 open .. 1 clenched), palm_R/L (world palm normal, default down),
eyes: eye_open (1 normal .. 1.7 wide), lid (0 open .. 1 shut; default 0.2 heavy-lidded), gx, gy (gaze),
brow (-1 worried/embarrassed .. +1 menacing), jaw (0 shut .. 1 slack), air (no ground shadow).

    py -m cast.creature            (from tools/toon) -> assets/kit/cast/mara.png and thief.png model sheets
"""
import math
import os
import sys

import skia

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import rig  # noqa: E402
from rig import Basis, Head, add, capsule, cross, dot, ik, lathe, mul, norm, rot, smooth, sub, union, _hull  # noqa: E402
from toon import paint, shade  # noqa: E402

LOOK = {
    # the Mara: gaunt, hunched, long ears (left one lower), sparse wiry hair, charcoal nightshirt
    "mara": dict(h=0.56, skin="#6e655c", tips="#5e6470", shirt="#2f3036", hair="#24211f", iris="#dfe6d6",
                 belly=0.0, neck=1.0, cheek=0.0, ear=1.0, hunch=1.0, hollow=1.0, build=1.0),
    # the console thief: same species, round belly, thick neck, broad cheeks, short ears, stockier
    "thief": dict(h=0.56, skin="#736656", tips="#62666f", shirt="#3a3532", hair="#2a2420", iris="#e4e0c8",
                  belly=1.0, neck=1.6, cheek=1.0, ear=0.6, hunch=0.55, hollow=0.0, build=1.22),
}
REST = dict(x=0.0, z=0.0, yaw=0.0, floor=0.0, crouch=1.0, lean=0.0, twist=0.0, head_yaw=0.0, head_pitch=0.0,
            head_roll=0.0, breath=0.0, eye_open=1.0, lid=0.2, gx=0.0, gy=0.0, brow=0.0, jaw=0.0)

# head: narrow skull, long jaw jutting to a pointed chin (u, half-width, half-depth, a_off, b_off) in units of R
HEAD_RINGS = [(-1.22, 0.16, 0.18, 0, 0.30), (-1.08, 0.40, 0.42, 0, 0.22), (-0.85, 0.60, 0.64, 0, 0.12),
              (-0.50, 0.76, 0.80, 0, 0.04), (-0.10, 0.86, 0.90, 0, 0.0), (0.30, 0.88, 0.95, 0, -0.04),
              (0.65, 0.76, 0.86, 0, -0.10), (0.92, 0.48, 0.60, 0, -0.13), (1.04, 0.10, 0.14, 0, -0.13)]


def lerp(a, b, t):
    return a + (b - a) * t


def solve(look, pose):
    L = LOOK[look]
    p = dict(REST)
    p.update(pose)
    s = L["h"] / 0.56
    cr, bd = p["crouch"], L["build"]
    root = (p["x"], p["floor"], p["z"])
    Bb = Basis.yaw(p["yaw"])
    J = {"root": root, "Bb": Bb, "h": L["h"], "s": s, "look": look, "pose": p, "err": {}}
    l1 = l2 = 0.135 * s
    sep = 0.075 * s * bd
    a_def = {k: Bb.w(root, g * sep, 0.026 * s, 0.01 * s * cr) for k, g in (("R", 1), ("L", -1))}
    ank = {k: pose.get("ankle_" + k, a_def[k]) for k in ("R", "L")}
    hip_y = p["floor"] + lerp(0.285, 0.115, cr) * s
    P = Bb.w((root[0], hip_y, root[2]), 0, 0, -0.035 * s * cr)
    for k, g in (("R", 1), ("L", -1)):                     # pelvis low enough that both legs reach their ankles
        hj = Bb.w(P, g * 0.05 * s, 0, 0)
        dx = math.hypot(ank[k][0] - hj[0], ank[k][2] - hj[2])
        reach = (l1 + l2) * 0.985
        if dx < reach:
            P = (P[0], min(P[1], ank[k][1] + 0.02 * s + math.sqrt(reach ** 2 - dx ** 2)), P[2])
    J["pelvis"] = P
    lean = 18 + 30 * cr * L["hunch"] + p["lean"]
    Bc = Bb.turn(p["twist"]).pitch(lean)
    J["Bc"] = Bc
    J["neck"] = Bc.w(P, 0, 0.17 * s, 0.02 * s)
    for k, g in (("R", 1), ("L", -1)):
        J["sh_" + k] = Bc.w(P, g * 0.068 * s * bd, 0.162 * s, -0.012 * s)       # raised shoulders, high and square
        J["hip_" + k] = Bb.w(P, g * 0.05 * s * bd, -0.01 * s, 0.0)
    # the head juts forward off a short neck and stays level to watch (the torso is pitched, the head is not)
    Bh = Bb.turn(p["twist"] + p["head_yaw"]).pitch(lean * 0.25 + p["head_pitch"]).roll(p["head_roll"])
    R = 0.062 * s
    J["Bh"], J["R"] = Bh, R
    J["head"] = add(Bc.w(P, 0, 0.178 * s, 0.05 * s), mul(Bh.u, 0.95 * R * (0.85 + 0.15 * L["neck"])))
    ua, fa = 0.125 * s, 0.12 * s
    for k, g in (("R", 1), ("L", -1)):
        S = J["sh_" + k]
        if ("ik_" + k) in pose or ("aR" not in pose and "aL" not in pose):
            tgt = pose.get("ik_" + k, Bb.w(root, g * 0.09 * s * bd, p["floor"] - root[1] + 0.02 * s, 0.13 * s))
            pole = pose.get("pole_" + k) or norm(Bb.d(g * 1.0, 0.15, -0.25))       # elbows out, near the knees
            E, Wr, err = ik(S, tgt, ua, fa, pole)
            J["err"]["arm_" + k] = err
        else:
            pit, rol, bend = pose.get("a" + k, (10, 8, 20))
            pr, rr = math.radians(pit), math.radians(rol)
            d = norm((g * math.sin(rr), -math.cos(rr) * math.cos(pr), math.cos(rr) * math.sin(pr)))
            perp = (0.0, math.sin(pr), math.cos(pr))
            b = math.radians(bend)
            fl = add(mul(d, math.cos(b)), mul(perp, math.sin(b)))
            E = add(S, mul(Bc.d(*d), ua))
            Wr = add(E, mul(Bc.d(*fl), fa))
        J["el_" + k], J["wr_" + k], J["fdir_" + k] = E, Wr, norm(sub(Wr, E))
        J["hand_" + k] = Wr
    for k, g in (("R", 1), ("L", -1)):                     # knees fold up toward the chest, splayed a little
        K, A, err = ik(J["hip_" + k], ank[k], l1, l2, norm(Bb.d(g * 0.35, 0.8, 0.7)))
        J["kn_" + k], J["ank_" + k] = K, A
        J["err"]["leg_" + k] = err
    if pose.get("lie"):                                    # turned and moved as one rigid body (carried, flying)
        rig._lie(J, pose["lie"])
    return J


def _rim(fr, path, rim, w):
    """Light catching one edge: the band of `path` left when it is shifted away from the light."""
    if not rim:
        return
    dx, dy = rim["d"]
    n = math.hypot(dx, dy) or 1.0
    sh = skia.Path(path)
    sh.offset(-dx / n * w, -dy / n * w)
    band = skia.Op(path, sh, skia.PathOp.kDifference_PathOp)
    if band:
        fr.c.drawPath(band, paint(rim["col"], a=rim.get("a", 0.6), blur=w * 0.35))


def draw(fr, cam, look, pose, light=None, rim=None, cheek=None, shadow=True, held=None):
    """held: (world centre, fn(fr, cam, light)) for a clutched prop, e.g. props.console.carry()."""
    L = LOOK[look]
    J = solve(look, pose)
    p, s, Bb, Bc, Bh, R = J["pose"], J["s"], J["Bb"], J["Bc"], J["Bh"], J["R"]
    c = fr.c
    out = {"look": look, "err": J["err"], "J": J}
    if min(cam.view(J[k])[2] for k in ("pelvis", "head")) < 0.25:
        out["culled"] = True
        return out
    P = cam.proj
    k0 = P(J["pelvis"])[3]
    lw = max(1.2, 0.0055 * k0)               # same line weight per metre as the human rig
    ld = rig.light_dir(cam, light, J["pelvis"])
    skin, tips, shirt = L["skin"], L["tips"], L["shirt"]
    rw = 0.007 * s * k0                                     # rim band width
    if shadow and not p.get("air"):
        fr.ground_ellipse(cam, J["root"][0], J["root"][2], 0.15 * s * L["build"], 0.12 * s, "#000000", 0.4,
                          blur_m=0.04 * s, y=p["floor"] + 0.003)
    parts = []                                              # (depth, fn)
    contacts = []

    def z_of(*w):
        return sum(cam.view(q)[2] for q in w) / len(w)

    # ---- legs and the big feet ----
    def leg(k, g):
        hp, kn, an = J["hip_" + k], J["kn_" + k], J["ank_" + k]
        a, b, e = P(hp), P(kn), P(an)
        kk = a[3]
        path = union(capsule(a[:2], 0.024 * s * kk, b[:2], 0.019 * s * kk), capsule(b[:2], 0.019 * s * kk, e[:2], 0.014 * s * kk))
        f = norm((Bb.f[0], 0.0, Bb.f[2]))
        f = rot(f, (0, 1, 0), -g * 12)                      # feet splay out
        r = cross((0, 1, 0), f)
        sole_y = an[1] - 0.024 * s

        def ring(cf, y, ra, rb, off=0.0, n=18):
            c0 = (an[0] + f[0] * cf + r[0] * off, y, an[2] + f[2] * cf + r[2] * off)
            return [P(add(c0, mul(f, ra * math.cos(t)), mul(r, rb * math.sin(t))))[:2]
                    for t in (2 * math.pi * i / n for i in range(n))]
        foot = rig._poly_path(_hull(ring(0.035 * s, sole_y, 0.068 * s, 0.03 * s) + ring(0.01 * s, sole_y + 0.03 * s, 0.03 * s, 0.022 * s)))
        toes = []
        for i, off in enumerate((-1.5, -0.5, 0.5, 1.5)):
            t0 = (an[0] + f[0] * 0.085 * s + r[0] * off * 0.014 * s, sole_y + 0.01 * s, an[2] + f[2] * 0.085 * s + r[2] * off * 0.014 * s)
            d = rot(f, (0, 1, 0), off * 7)
            t1 = add(t0, mul(d, (0.032 if i in (1, 2) else 0.026) * s), (0, -0.004 * s, 0))
            toes.append((P(t0), P(t1), d, t1))
        contacts.append(("foot", (an[0] + f[0] * 0.04 * s, sole_y, an[2] + f[2] * 0.04 * s), 0.06 * s))

        def fn():
            for t0, t1, d, w1 in toes:
                tp = capsule(t0[:2], 0.009 * s * t0[3], t1[:2], 0.007 * s * t1[3])
                fr.part(tp, skin, ld, width=0.02 * s * t0[3], line=lw * 0.8)
                nl = P(add(w1, mul(d, 0.01 * s)))
                c.drawPath(capsule(t1[:2], 0.005 * s * t1[3], nl[:2], 0.002 * s * t1[3]), paint("#bfb08a"))
            fr.part(foot, skin, ld, width=0.08 * s * kk, line=lw)
            fr.part(path, skin, ld, width=0.04 * s * kk, line=lw)
            c.save()                                        # darker, creased knees
            c.clipPath(path, skia.ClipOp.kIntersect, True)
            c.drawCircle(b[0], b[1], 0.02 * s * kk, paint(shade(skin, -0.35), a=0.6, blur=0.008 * s * kk))
            c.drawLine(b[0] - 0.01 * s * kk, b[1] + 0.004 * s * kk, b[0] + 0.01 * s * kk, b[1] + 0.006 * s * kk,
                       paint(shade(skin, -0.6), stroke=lw * 0.5, a=0.7))
            c.restore()
        parts.append((z_of(hp, kn, an), fn))
        out["foot_" + k] = e[:2]

    # ---- arms: thin, sleeves to mid-forearm, big hands ----
    def arm(k, g):
        S, E, W = J["sh_" + k], J["el_" + k], J["wr_" + k]
        a, b, e = P(S), P(E), P(W)
        kk = a[3]
        limb = union(capsule(a[:2], 0.016 * s * kk, b[:2], 0.013 * s * kk), capsule(b[:2], 0.013 * s * kk, e[:2], 0.011 * s * kk))
        cuff_w = add(E, mul(sub(W, E), 0.5))
        cf = P(cuff_w)
        sleeve = union(capsule(a[:2], 0.021 * s * kk, b[:2], 0.018 * s * kk), capsule(b[:2], 0.018 * s * kk, cf[:2], 0.016 * s * kk))
        fd = J["fdir_" + k]
        pn = norm(p.get("palm_" + k, (0.0, -1.0, 0.0)))
        pn = norm(sub(pn, mul(fd, dot(pn, fd)))) if abs(dot(pn, fd)) < 0.98 else norm(cross(fd, Bc.r))
        sx = norm(cross(fd, pn))
        curl = p.get("curl_" + k, 0.45)
        H = W
        segs = [(H, add(H, mul(fd, 0.04 * s)), 0.021 * s, 0.024 * s, skin)]          # palm
        tips_ = []
        for i, off in enumerate((-1.5, -0.5, 0.5, 1.5)):
            ln = (0.03, 0.024, 0.02) if i in (1, 2) else (0.026, 0.021, 0.017)
            q = add(H, mul(fd, 0.042 * s), mul(sx, off * 0.0125 * s))
            d = rot(fd, pn, -off * 5.0)
            for j, Lj in enumerate(ln):
                d = rot(d, sx, -(10 + 62 * curl) * (0.6 if j == 0 else 1.0))
                nq = add(q, mul(d, Lj * s))
                segs.append((q, nq, (0.0075 - 0.0011 * j) * s, (0.0068 - 0.0011 * j) * s, tips if j == 2 else skin))
                q = nq
            tips_.append((q, d))
            contacts.append(("finger", q, 0.012 * s))
        th0 = add(H, mul(sx, -g * 0.02 * s), mul(fd, 0.012 * s))
        td = norm(add(mul(fd, 0.7), mul(sx, -g * 0.7), mul(pn, 0.25 + 0.4 * curl)))
        th1 = add(th0, mul(td, 0.026 * s))
        th2 = add(th1, mul(norm(add(td, mul(pn, 0.3 + curl))), 0.02 * s))
        segs += [(th0, th1, 0.0085 * s, 0.0075 * s, skin), (th1, th2, 0.0075 * s, 0.006 * s, tips)]
        tips_.append((th2, norm(sub(th2, th1))))

        def hand():
            for a0, b0, r0, r1, colr in sorted(segs, key=lambda q: -(cam.view(q[0])[2] + cam.view(q[1])[2])):
                pa, pb = P(a0), P(b0)
                if min(pa[2], pb[2]) < 0.05:
                    continue
                pth = capsule(pa[:2], r0 * pa[3], pb[:2], r1 * pb[3])
                fr.part(pth, colr, ld, width=2 * r0 * pa[3], line=lw * 0.7, lit=0.12, dark=0.4)
                _rim(fr, pth, rim, rw * 0.5)
                if colr == skin and r0 < 0.01 * s:          # knuckle creases
                    c.drawLine(pb[0] - r1 * pb[3] * 0.6, pb[1], pb[0] + r1 * pb[3] * 0.6, pb[1],
                               paint(shade(skin, -0.55), stroke=max(0.5, lw * 0.35), a=0.6))
            for q, d in tips_:                              # short thick yellowed nails
                a1, b1 = P(q), P(add(q, mul(d, 0.009 * s)))
                if min(a1[2], b1[2]) < 0.05:
                    continue
                c.drawPath(capsule(a1[:2], 0.0045 * s * a1[3], b1[:2], 0.002 * s * a1[3]), paint("#b9aa82"))

        def fn():
            fr.part(limb, skin, ld, width=0.03 * s * kk, line=lw)
            fr.part(sleeve, shirt, ld, width=0.05 * s * kk, line=lw, lit=0.1, dark=0.45)
            _rim(fr, sleeve, rim, rw)
            ax = math.atan2(cf[1] - b[1], cf[0] - b[0])     # ragged cuff: a few teeth past the sleeve end
            for t in (-0.7, 0.0, 0.6):
                x0 = cf[0] + math.cos(ax + math.pi / 2) * t * 0.022 * s * kk
                y0 = cf[1] + math.sin(ax + math.pi / 2) * t * 0.022 * s * kk
                tri = skia.Path()
                tri.moveTo(x0 + math.cos(ax + math.pi / 2) * 0.008 * s * kk, y0 + math.sin(ax + math.pi / 2) * 0.008 * s * kk)
                tri.lineTo(x0 + math.cos(ax) * 0.012 * s * kk, y0 + math.sin(ax) * 0.012 * s * kk)
                tri.lineTo(x0 - math.cos(ax + math.pi / 2) * 0.008 * s * kk, y0 - math.sin(ax + math.pi / 2) * 0.008 * s * kk)
                tri.close()
                c.drawPath(tri, paint(shirt))
            hand()
        fn.arm = True
        parts.append((z_of(S, E, W), fn))
        out["hand_" + k] = P(add(H, mul(fd, 0.04 * s)))[:2]
        J["sleeve_" + k] = cuff_w

    # ---- body: the nightshirt over a hunched back ----
    def body():
        br = 1 + 0.025 * p["breath"]
        hb, bl, bd = L["hunch"], L["belly"], L["build"]
        rt = [(-0.06, 0.072, 0.060, 0.000), (-0.015, 0.071, 0.060, 0.000), (0.04, 0.066, 0.060, -0.006),
              (0.09, 0.072, 0.072, -0.024), (0.128, 0.078, 0.076, -0.034), (0.155, 0.077, 0.064, -0.026),
              (0.174, 0.05, 0.046, -0.008), (0.185, 0.024, 0.024, 0.008)]
        rings = []
        for u, wa, db, bo in rt:
            bump = bl * max(0.0, 1 - abs(u - 0.03) / 0.09)          # the thief's round belly pushes forward
            rings.append((u * s, (wa + 0.035 * bump) * s * bd * (br if 0.06 < u < 0.16 else 1),
                          (db + 0.05 * bump) * s * (br if 0.06 < u < 0.16 else 1), 0, (bo * hb + 0.045 * bump) * s))
        path, zt = lathe(cam, J["pelvis"], Bc, rings)
        # ragged hem: teeth hanging off the bottom ring where it faces the camera
        u0, wa0, db0 = rings[0][0], rings[0][1], rings[0][2]
        teeth = []
        n = 22
        for i in range(n):
            t = 2 * math.pi * (i + 0.5) / n
            nrm = Bc.d(math.cos(t), 0, math.sin(t))
            q = Bc.w(J["pelvis"], wa0 * math.cos(t), u0, db0 * math.sin(t))
            if dot(nrm, norm(sub(cam.pos, q))) < -0.15:
                continue
            ta, tb = Bc.w(J["pelvis"], wa0 * math.cos(t - 0.13), u0 + 0.004 * s, db0 * math.sin(t - 0.13)), \
                Bc.w(J["pelvis"], wa0 * math.cos(t + 0.13), u0 + 0.004 * s, db0 * math.sin(t + 0.13))
            drop = (0.012 + 0.012 * ((i * 0.618) % 1.0)) * s
            teeth.append((ta, add(q, mul(Bc.u, -drop)), tb))
        nk = P(J["neck"])
        hd = P(J["head"])
        kk = nk[3]

        def fn():
            for ta, tq, tb in teeth:
                tri = skia.Path()
                for j, w in enumerate((ta, tq, tb)):
                    (tri.moveTo if j == 0 else tri.lineTo)(*P(w)[:2])
                tri.close()
                fr.part(tri, shade(shirt, -0.08), ld, width=0.03 * s * kk, line=lw * 0.7)

            def occl(cv):
                cv.drawOval(skia.Rect(hd[0] - 0.05 * s * kk, nk[1] - 0.02 * s * kk, hd[0] + 0.05 * s * kk, nk[1] + 0.04 * s * kk),
                            paint("#05060c", a=0.45, blur=0.02 * s * kk))
            fr.part(path, shirt, ld, width=0.16 * s * kk, line=lw, lit=0.12, dark=0.45, occl=occl)
            c.save()
            c.clipPath(path, skia.ClipOp.kIntersect, True)
            # worn seams: a stitched side seam and a darned patch on the back
            for sg in (1, -1):
                a0, b0 = P(Bc.w(J["pelvis"], sg * 0.07 * s * bd, -0.06 * s, 0)), P(Bc.w(J["pelvis"], sg * 0.075 * s * bd, 0.18 * s, -0.01 * s))
                seam = skia.Path()
                seam.moveTo(*a0[:2])
                seam.lineTo(*b0[:2])
                sp = paint(shade(shirt, 0.35), stroke=max(0.6, lw * 0.4), a=0.55)
                sp.setPathEffect(skia.DashPathEffect.Make([3 * lw, 2.5 * lw], 0))
                c.drawPath(seam, sp)
            pc = P(Bc.w(J["pelvis"], -0.025 * s, 0.13 * s, -0.075 * s * hb))
            c.drawRect(skia.Rect(pc[0] - 0.018 * s * kk, pc[1] - 0.014 * s * kk, pc[0] + 0.018 * s * kk, pc[1] + 0.014 * s * kk),
                       paint(shade(shirt, 0.12), a=0.8))
            c.restore()
            _rim(fr, path, rim, rw)
            # neck: short (the thief's thick) rising out of a stretched collar
            nb = P(add(J["neck"], mul(Bc.u, -0.006 * s)))
            nt = P(add(J["head"], mul(Bh.u, -0.6 * R)))
            nr = 0.017 * s * L["neck"] * kk
            fr.part(capsule(nb[:2], nr * 1.1, nt[:2], nr), shade(skin, -0.15), ld, width=2 * nr, line=lw)
            col = skia.Path()
            col.addOval(skia.Rect(nb[0] - nr * 1.5, nb[1] - nr * 0.45, nb[0] + nr * 1.5, nb[1] + nr * 0.5))
            c.drawPath(col, paint(shade(shirt, -0.3), stroke=lw * 1.2))
        parts.append((zt, fn))
        J["_zt"] = zt
        J["collar"] = J["neck"]
        J["hem"] = Bc.w(J["pelvis"], 0, u0, db0)

    # ---- head: narrow face, low brow, deep small pale eyes, crooked flat nose, tight mouth, uneven ears ----
    def head():
        rings = []
        for u, wa, db, ao, bo in HEAD_RINGS:
            wide = 1 + 0.22 * L["cheek"] * max(0.0, 1 - abs(u + 0.55) / 0.6)       # the thief's broad cheeks
            rings.append((u * R, wa * R * wide, db * R, 0, bo * R))
        path, zh = lathe(cam, J["head"], Bh, rings)
        Hd = Head(cam, J["head"], Bh, R * 0.9)               # feature surface sits inside the narrow skull
        hc = P(J["head"])
        kk = hc[3]
        to_cam = norm(sub(cam.pos, J["head"]))
        ears = []
        for sg, drop in ((1, -0.16), (-1, 0.0)):              # lam + = the character's left; that ear sits lower
            out_d = mul(Bh.r, -sg)
            el = L["ear"]
            base = [Hd.surf(sg * 1.30, 0.32 + drop * 0.5, 1.08), Hd.surf(sg * 1.50, 0.06 + drop * 0.5, 1.08),
                    Hd.surf(sg * 1.75, -0.18 + drop * 0.5, 1.08)]
            tip = add(J["head"], mul(out_d, R * (0.95 + 0.75 * el)), mul(Bh.u, R * (0.30 + 0.30 * el + drop)), mul(Bh.f, -R * (0.35 + 0.6 * el)))
            notch = add(mul(base[2], 0.45), mul(tip, 0.55), mul(Bh.u, -0.05 * R))
            upper = add(mul(base[0], 0.5), mul(tip, 0.5), mul(Bh.u, 0.10 * R), mul(Bh.f, 0.06 * R))
            ring = [base[0], upper, tip, notch, base[2], base[1]]
            mid = add(mul(base[1], 0.6), mul(tip, 0.4))
            inner = [add(mul(q, 0.55), mul(mid, 0.45)) for q in ring[:5]]
            near = dot(out_d, to_cam) > -0.15
            ears.append((near, ring, inner))

        def ear_fn(ring, inner):
            def f():
                pth = smooth([P(q)[:2] for q in ring], k=0.35)
                fr.part(pth, skin, ld, width=0.6 * R * kk, line=lw, lit=0.1, dark=0.35)
                c.drawPath(smooth([P(q)[:2] for q in inner], k=0.4), paint(shade(skin, -0.45), a=0.8, blur=0.02 * R * kk))
                _rim(fr, pth, rim, rw * 0.8)
            return f

        def fn():
            for near, ring, inner in ears:
                if not near:
                    ear_fn(ring, inner)()
            fr.part(path, skin, ld, width=2 * R * kk, line=lw, outline=False, lit=0.12, dark=0.38)
            c.save()
            c.clipPath(path, skia.ClipOp.kIntersect, True)
            face(Hd, kk)
            c.restore()
            c.drawPath(path, paint(shade(skin, -0.68), stroke=lw))
            _rim(fr, path, rim, rw)
            relief(Hd, kk)
            hair(Hd, kk)
            for near, ring, inner in ears:
                if near:
                    ear_fn(ring, inner)()
        # the head juts out in front of the hump: over the body unless seen from behind
        zt = J["_zt"]
        parts.append((min(zh, zt - 1e-4) if dot(Bh.f, to_cam) > -0.2 else zh, fn))
        out["head"] = hc[:2]
        out["head_r"] = R * kk

    def face(Hd, kk):
        dk = shade(skin, -0.55)
        eo, lid, brow, jaw = p["eye_open"], p["lid"], p["brow"], p["jaw"]
        # cheek hollows (the Mara) / a soft round cheek (the thief)
        for sg in (-1, 1):
            if Hd.facing(sg * 0.6, -0.32) > 0.1:
                c.save()
                c.concat(Hd.decal(sg * 0.6, -0.32))
                if L["hollow"]:
                    c.drawOval(skia.Rect(-0.2 * R, -0.12 * R, 0.2 * R, 0.16 * R), paint("#1c1712", a=0.32 * L["hollow"], blur=0.08 * R))
                else:
                    c.drawOval(skia.Rect(-0.22 * R, -0.16 * R, 0.22 * R, 0.16 * R), paint("#ffffff", a=0.08, blur=0.08 * R))
                c.restore()
        if cheek:                                           # PC light on one cheek
            colr, a, sg = cheek
            if Hd.facing(sg * 0.55, -0.15) > 0.0:
                c.save()
                c.concat(Hd.decal(sg * 0.55, -0.15))
                c.drawOval(skia.Rect(-0.24 * R, -0.2 * R, 0.24 * R, 0.2 * R), paint(colr, a=a * 0.5, blur=0.12 * R, blend="add"))
                c.restore()
        # deep sockets under a low heavy brow
        by = 0.17 + 0.07 * max(0.0, -brow) * 1.0 + 0.04 * (eo - 1)          # worried/shocked: the brow climbs
        for sg in (-1, 1):
            lam = sg * 0.34
            if Hd.facing(lam, 0.0) <= 0.1:
                continue
            c.save()
            c.concat(Hd.decal(lam, 0.0))
            c.drawOval(skia.Rect(-0.27 * R, -0.21 * R, 0.27 * R, 0.12 * R), paint("#0d0a0a", a=0.6, blur=0.085 * R))
            rx, ry = 0.115 * R * (0.85 + 0.15 * eo), 0.075 * R * eo
            eye = skia.Path()
            eye.addOval(skia.Rect(-rx, -ry, rx, ry))
            c.drawPath(eye, paint("#6f6658"))
            c.save()
            c.clipPath(eye, skia.ClipOp.kIntersect, True)
            gx, gy = p["gx"] * 0.06 * R, p["gy"] * 0.04 * R
            ir = 0.062 * R
            c.drawCircle(gx, gy, ir, paint(L["iris"]))
            c.drawCircle(gx, gy, 0.022 * R, paint("#0a0808"))
            glint = cheek[0] if cheek else "#ffffff"
            c.drawCircle(gx - 0.022 * R, gy - 0.022 * R, 0.013 * R, paint("#ffffff", a=0.95))
            c.drawCircle(gx + 0.02 * R, gy + 0.018 * R, 0.008 * R, paint(glint, a=0.7))
            lt = -ry + 2 * ry * min(1.0, lid / max(0.4, eo))  # upper lid
            c.drawRect(skia.Rect(-rx * 1.2, -ry * 1.3, rx * 1.2, lt), paint(shade(skin, -0.25)))
            c.restore()
            c.drawLine(-rx * 1.1, lt, rx * 1.1, lt, paint(shade(skin, -0.7), stroke=0.02 * R))
            for j in (0, 1):                                # crow's-feet wrinkles at the outer corner
                w = skia.Path()
                x0 = sg * rx * 1.15
                w.moveTo(x0, (j - 0.3) * 0.05 * R)
                w.quadTo(x0 + sg * 0.05 * R, (j - 0.3) * 0.06 * R, x0 + sg * 0.09 * R, (j - 0.1) * 0.09 * R)
                c.drawPath(w, paint(dk, stroke=0.012 * R, a=0.6))
            c.restore()
        # thin tight mouth, corners down; slack jaw opens a small dark gap and drops the lower lip
        if Hd.facing(0.0, -0.58) > 0.05:
            c.save()
            c.concat(Hd.decal(0.0, -0.58 - 0.05 * jaw))
            w = 0.26 * R
            if jaw > 0.05:
                gap = skia.Path()
                gap.moveTo(-w * 0.8, 0)
                gap.quadTo(0, -0.03 * R, w * 0.8, 0)
                gap.quadTo(0, 0.16 * R * jaw, -w * 0.8, 0)
                c.drawPath(gap, paint("#0b0606"))
            m = skia.Path()
            m.moveTo(-w, 0.04 * R)
            m.quadTo(-w * 0.5, -0.01 * R, 0, 0.0)
            m.quadTo(w * 0.5, -0.01 * R, w, 0.045 * R)
            c.drawPath(m, paint("#1a1110", stroke=0.03 * R))
            for sg in (-1, 1):                              # deep creases at the corners
                cr_ = skia.Path()
                cr_.moveTo(sg * w * 1.05, 0.0)
                cr_.quadTo(sg * w * 1.25, 0.08 * R, sg * w * 1.1, 0.18 * R)
                c.drawPath(cr_, paint(dk, stroke=0.015 * R, a=0.55))
            c.restore()

    def relief(Hd, kk):
        """Brow ridge and nose drawn unclipped so they stand off the head in profile."""
        dk = shade(skin, -0.55)
        eo, brow = p["eye_open"], p["brow"]
        by = 0.17 + 0.07 * max(0.0, -brow) * 1.0 + 0.04 * (eo - 1)
        # the brow ridge: one heavy band; menace pulls the inner ends down, worry lifts them
        pts_top, pts_bot = [], []
        for i in range(9):
            lam = -0.62 + 1.24 * i / 8
            inner = 1 - abs(lam) / 0.62
            mu = by - 0.07 * brow * inner + 0.05 * max(0.0, -brow) * inner
            if Hd.facing(lam, mu) <= 0.0:
                continue
            pts_top.append(P(Hd.surf(lam, mu + 0.07, 1.04))[:2])
            pts_bot.append(P(Hd.surf(lam, mu - 0.03, 1.05))[:2])
        if len(pts_top) > 2:
            band = smooth(pts_top + pts_bot[::-1], k=0.5)
            c.drawPath(band, paint(shade(skin, 0.1)))
            sh_ = skia.Path(band)
            sh_.offset(0, 0.035 * R * kk)
            c.drawPath(sh_, paint("#0d0a0a", a=0.35, blur=0.03 * R * kk))
            c.drawPath(smooth(pts_bot, closed=False), paint(shade(skin, -0.6), stroke=0.02 * R * kk))
            if brow < -0.2:                                 # worry lines on the exposed forehead
                for j in range(2):
                    q = [P(Hd.surf(l, by + 0.18 + 0.08 * j, 1.0))[:2] for l in (-0.25, 0.0, 0.25) if Hd.facing(l, by + 0.2) > 0.05]
                    if len(q) == 3:
                        c.drawPath(smooth(q, closed=False), paint(shade(skin, -0.5), stroke=0.012 * R * kk, a=min(1, -brow)))
        # flattened, crooked nose: a bent bridge into a wide flat tip set off-centre
        if Hd.facing(0.05, -0.22) > -0.6:                   # bent bridge as a volume: reads in profile too
            a0, a1 = P(Hd.surf(0.0, 0.02, 1.0)), P(Hd.surf(0.05, -0.22, 1.22))
            fr.part(capsule(a0[:2], 0.07 * R * kk, a1[:2], 0.1 * R * kk), skin, ld, width=0.2 * R * kk, line=lw * 0.8,
                    lit=0.12, dark=0.35)
        if Hd.facing(0.05, -0.22) > 0.05:
            c.save()
            c.concat(Hd.decal(0.07, -0.24, 1.08))
            c.rotate(-10)
            nose = skia.Path()
            nose.addOval(skia.Rect(-0.15 * R, -0.07 * R, 0.13 * R, 0.07 * R))
            fr.part(nose, shade(skin, 0.04), (0.2, 1.0), width=0.3 * R, line=0.012 * R, lit=0.15, dark=0.4)
            c.drawOval(skia.Rect(-0.13 * R, 0.01 * R, 0.11 * R, 0.07 * R), paint("#120c0a", a=0.45, blur=0.02 * R))
            for x in (-0.06, 0.04):
                c.drawOval(skia.Rect((x - 0.018) * R, 0.012 * R, (x + 0.018) * R, 0.032 * R), paint("#120c0a", a=0.8))
            c.restore()

    def hair(Hd, kk):
        """Sparse wiry strands combed back off a high bare forehead, kinked, standing a little off the scalp."""
        colr = L["hair"]
        sw = max(0.6, 0.016 * R * kk)
        Rh = R * 0.92
        to_cam = norm(sub(cam.pos, J["head"]))
        for i in range(9):                                  # parallel strands front-to-back (a sphere's pole
            xi = -0.62 + 1.24 * i / 8                      # would bunch them into a starburst)
            run = []
            for j in range(10):
                u = j / 9
                ph = 0.95 + 0.05 * math.sin(i * 2.1) + u * 1.8
                x = xi + 0.05 * math.sin(i * 3.3 + u * 11)
                ryz = math.sqrt(max(0.0, 1 - x * x)) * (1.08 + 0.04 * u + 0.025 * math.sin(i + u * 7))
                nrm = add(mul(Bh.r, -x), mul(Bh.u, math.sin(ph) * ryz), mul(Bh.f, math.cos(ph) * ryz))
                q = add(J["head"], mul(nrm, Rh))
                vis = dot(norm(nrm), to_cam) > -0.3
                if vis:
                    run.append(P(q)[:2])
                elif len(run) > 1:
                    c.drawPath(smooth(run, closed=False), paint(colr, stroke=sw))
                    run = []
            if len(run) > 1:
                c.drawPath(smooth(run, closed=False), paint(colr, stroke=sw))
        for i in range(5):                                  # a few stray hairs sticking up off the crown
            lam = -0.6 + 0.3 * i
            a, b = P(Hd.surf(lam, 1.2, 1.08)), P(Hd.surf(lam + 0.1, 1.35, 1.35))
            c.drawLine(a[0], a[1], b[0], b[1], paint(colr, stroke=sw * 0.8))

    for k, g in (("R", 1), ("L", -1)):
        leg(k, g)
        arm(k, g)
    body()
    head()
    if held:                                                # a clutched prop: under the arms, over the body
        hc, hfn = held
        zp = min(cam.view(hc)[2], J["_zt"] - 1e-3)
        parts[:] = [(min(z, zp - 2e-3) if getattr(f, "arm", False) else z, f) for z, f in parts]   # gripping hands on top
        parts.append((zp, lambda: hfn(fr, cam, light or (0.0, 2.4, 1.5))))
    for _, fn in sorted(parts, key=lambda q: -q[0]):
        fn()
    out["contacts"] = contacts
    out["grab"] = {"collar": J["collar"], "hem": J["hem"], "sleeve_R": J["sleeve_R"], "sleeve_L": J["sleeve_L"]}
    out["depth"] = P(J["pelvis"])[2]
    return out


# ---- model sheets ------------------------------------------------------------------------------------------
def sheet(look, path):
    from PIL import Image
    from toon import Camera, Frame
    rim = dict(d=(-1.0, -0.4), col="#7fa8ff", a=0.4)
    tiles = []
    L = LOOK[look]

    def tile(cam, pose, cheek=None, carry=False, t=0.0):
        fr = Frame(0.35, bg="#161b2c")
        fr.ground_ellipse(cam, 0, 1.6, 0.6, 0.45, "#222a40", 1.0, blur_m=0.2)
        pose = dict(dict(x=0, z=1.6), **pose)
        held = None
        if carry:                                           # the thief: hunched, hugging the stolen console
            from props import console
            add_, held = console.carry(pose, t=t)
            pose = dict(add_, **pose)
        draw(fr, cam, look, pose, light=(1.2, 1.6, 2.4), rim=rim, cheek=cheek, held=held)
        tiles.append(Image.fromarray(fr.array()))
    wide = Camera((0, 0.24, 0.4), 0, f=2700, horizon=0.42)
    carry = look == "thief"
    for yaw in (0, 40, 90, 140, 180, -90):                  # resting squat (the thief: carrying) turnaround
        tile(wide, dict(yaw=yaw, breath=0.5), carry=carry, t=yaw * 0.01)
    if carry:                                               # mid-shuffle, console wobbling
        tile(wide, dict(yaw=-30, head_yaw=40, gx=-1.0, brow=0.4), carry=True, t=0.4)
    else:
        tile(wide, dict(yaw=25, crouch=0.0, aR=(20, 12, 25), aL=(15, 10, 20), curl_R=0.7, curl_L=0.7))   # standing
    close = Camera((0, 0.3, 1.0), 0, f=2600, horizon=0.45)
    tile(close, dict(yaw=10, lid=0.15), cheek=("#a46bff", 0.2, -1))                                   # watching
    tile(close, dict(yaw=10, eye_open=1.7, lid=0.0, jaw=0.6, brow=-0.8), cheek=("#a46bff", 0.2, -1))  # caught out
    tile(close, dict(yaw=10, head_pitch=28, head_yaw=-30, brow=-1.0, lid=0.45, gy=1.0, jaw=0.15))       # embarrassed
    w, h = tiles[0].size
    img = Image.new("RGB", (w * len(tiles) + 8 * (len(tiles) - 1), h), (255, 0, 255))
    for i, t in enumerate(tiles):
        img.paste(t, (i * (w + 8), 0))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)
    print(path, img.size)


if __name__ == "__main__":
    root = os.path.abspath(os.path.join(HERE, "..", ".."))
    for lk in (sys.argv[1:] or ["mara", "thief"]):
        sheet(lk, os.path.join(root, "assets", "kit", "cast", lk + ".png"))
