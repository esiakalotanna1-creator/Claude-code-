"""Mr. Widemouth (2026-11-11, "Little Timmy vs Mr. Widemouth"): a small furry creature (~0.62 m standing) with an
oversized wide head, a cheek-to-cheek smile, small amber eyes set high and wide, two tall ears (its LEFT ear bent
crooked at the middle), long thin arms with long fingers, big flat long-toed feet and a loose ruff of fur behind the
shoulders (the fold Timmy grabs). Own skeleton, drawn with the toon engine's shading; fur is sculpted clumps fixed
to the body (no strands, no noise), so the silhouette never shimmers.

    out = widemouth.draw(fr, cam, pose, light=lamp_pos, warm=lamp_pos, cool=(dx, dy, dz))
    out["J"], out["contacts"], out["head"], out["head_r"], out["hand_R"/"hand_L"]

Pose keys (metres scale with h): x, z, yaw (rig convention: yaw 0 faces -z), floor, crouch (0 standing .. 1 squat),
lean (extra forward pitch), side (roll), twist, head_yaw, head_pitch, head_roll, breath (-1..1),
ankle_R/L (world, planted), toes (0 flat .. 1 gripping, curled over an edge), ik_R/ik_L (world wrist targets),
pole_R/L, aR/aL (FK pitch, roll, bend), curl_R/L (0 open .. 1 fist; or 4 values: index, middle, ring, thumb),
palm_R/L (world palm normal), eye_open (1 .. 1.6 wide), lid (0 open .. 1 shut), lid_lo (0 .. 1 cheeks push the lower
lids up), gx, gy (gaze -1..1), brow (-1 worried .. +1 menacing), grin (0 flat mouth .. 1 the full wide smile),
open (0 lips shut .. 1 wide open, teeth showing), sag (the open mouth hangs slack: no corner lift), ears (1 up ..
0 flattened back), twitch (deg, the crooked ear), swallow (0..1 the throat bump), scruff (0..1 pulled) with
scruff_at (world grip point), leaf (0..1 a leaf sitting on the head .. on the nose, 2 = fallen), twig (bool),
lie = (rotations, world pelvis) to turn the whole body (thrown, tumbling), air (no ground shadow),
shrug (0..1 the shoulders rise), arms_k (reach allowance, as rig.arms_k).

    py -m cast.widemouth          (from tools/toon) -> assets/kit/cast/widemouth.png model sheet
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
from toon import paint, shade, mix  # noqa: E402

LOOK = dict(h=0.62, fur="#8c7d8e", fur_dk="#6d5f72", muzzle="#e6d9c8", inner="#c48a96", iris="#d9a13c",
            pads="#4d3f4f", nose="#3a2730", mouth="#2b0f16", teeth="#f2ece0", tongue="#a8505c")
REST = dict(x=0.0, z=0.0, yaw=0.0, floor=0.0, crouch=0.0, lean=0.0, side=0.0, twist=0.0, head_yaw=0.0,
            head_pitch=0.0, head_roll=0.0, breath=0.0, eye_open=1.0, lid=0.0, lid_lo=0.0, gx=0.0, gy=0.0,
            brow=0.0, grin=0.7, open=0.0, sag=0.0, ears=1.0, twitch=0.0, swallow=0.0, scruff=0.0, toes=0.0,
            leaf=-1.0, twig=False)
SHAPE = (1.34, 0.92, 0.10)          # head: wide, a little flattened, fuller jowls (the mouth's cheeks)


def lerp(a, b, t):
    return a + (b - a) * t


def solve(pose):
    L = LOOK
    p = dict(REST)
    p.update(pose)
    s = L["h"] / 0.62
    cr = p["crouch"]
    root = (p["x"], p["floor"], p["z"])
    Bb = Basis.yaw(p["yaw"])
    J = {"root": root, "Bb": Bb, "h": L["h"], "s": s, "pose": p, "err": {}}
    l1 = l2 = 0.118 * s
    a_def = {k: Bb.w(root, g * 0.062 * s, 0.022 * s, 0.0) for k, g in (("R", 1), ("L", -1))}
    ank = {k: pose.get("ankle_" + k, a_def[k]) for k in ("R", "L")}
    hip_y = p["floor"] + lerp(0.232, 0.13, cr) * s
    P = (root[0], hip_y, root[2])
    for k, g in (("R", 1), ("L", -1)):                     # pelvis low enough that both legs reach their ankles
        hj = Bb.w(P, g * 0.05 * s, 0, 0)
        dx = math.hypot(ank[k][0] - hj[0], ank[k][2] - hj[2])
        reach = (l1 + l2) * 0.97
        if dx < reach:
            P = (P[0], min(P[1], ank[k][1] + 0.018 * s + math.sqrt(reach ** 2 - dx ** 2)), P[2])
    J["pelvis"] = P
    lean = 6 + 22 * cr + p["lean"]
    Bc = Bb.turn(p["twist"]).pitch(lean).roll(p["side"])
    J["Bc"] = Bc
    br = 1 + 0.02 * p["breath"]
    J["neck"] = Bc.w(P, 0, 0.19 * s * br, 0.012 * s)
    for k, g in (("R", 1), ("L", -1)):
        J["sh_" + k] = Bc.w(P, g * 0.068 * s, (0.178 * br + 0.03 * p.get("shrug", 0.0)) * s, -0.004 * s)   # shrug: the shoulders rise
        J["hip_" + k] = Bb.w(P, g * 0.048 * s, -0.012 * s, 0.0)
    Bh = Bb.turn(p["twist"] + p["head_yaw"]).pitch(lean * 0.35 + p["head_pitch"]).roll(p["head_roll"] + 0.4 * p["side"])
    R = 0.105 * s
    J["Bh"], J["R"] = Bh, R
    J["head"] = add(Bc.w(P, 0, 0.205 * s * br, 0.018 * s), mul(Bh.u, 0.80 * R))
    ak = pose.get("arms_k", 1.0)                           # a pose may lengthen the arms a little (as rig.arms_k)
    ua, fa = 0.128 * s * ak, 0.122 * s * ak
    for k, g in (("R", 1), ("L", -1)):
        S = J["sh_" + k]
        if ("ik_" + k) in pose:
            pole = pose.get("pole_" + k) or norm(Bc.d(g * 0.8, -0.6, -0.3))
            E, Wr, err = ik(S, pose["ik_" + k], ua, fa, pole)
            J["err"]["arm_" + k] = err
        else:
            pit, rol, bend = pose.get("a" + k, (6, 10, 18))
            pr, rr = math.radians(pit), math.radians(rol)
            d = norm((g * math.sin(rr), -math.cos(rr) * math.cos(pr), math.cos(rr) * math.sin(pr)))
            perp = (0.0, math.sin(pr), math.cos(pr))
            b = math.radians(bend)
            fl = add(mul(d, math.cos(b)), mul(perp, math.sin(b)))
            E = add(S, mul(Bc.d(*d), ua))
            Wr = add(E, mul(Bc.d(*fl), fa))
        J["el_" + k], J["wr_" + k], J["fdir_" + k] = E, Wr, norm(sub(Wr, E))
        J["hand_" + k] = add(Wr, mul(J["fdir_" + k], 0.04 * s))
    for k, g in (("R", 1), ("L", -1)):                     # knees forward and a little out
        K, A, err = ik(J["hip_" + k], ank[k], l1, l2, norm(Bb.d(g * 0.3, 0.2, 1.0)))
        J["kn_" + k], J["ank_" + k] = K, A
        J["err"]["leg_" + k] = err
    # the ruff behind the shoulders: where its middle sits, and its grab point (out["grab"]["scruff"])
    J["scruff"] = Bc.w(P, 0.0, 0.185 * s, -0.075 * s)
    if pose.get("lie"):                                    # thrown / tumbling: the whole body turned as one
        rig._lie(J, pose["lie"])
        J["Bb"] = Basis(*(rig.lie_fwd(pose["lie"], P, a, True) for a in (Bb.r, Bb.u, Bb.f)))
    return J


def _rim(fr, path, rim, w):
    """Cool light catching one edge: the band of `path` left when it is shifted away from the light."""
    if not rim or rim.get("a", 0) <= 0.01:
        return
    dx, dy = rim["d"]
    n = math.hypot(dx, dy) or 1.0
    sh = skia.Path(path)
    sh.offset(-dx / n * w, -dy / n * w)
    band = skia.Op(path, sh, skia.PathOp.kDifference_PathOp)
    if band:
        fr.c.drawPath(band, paint(rim["col"], a=rim.get("a", 0.6), blur=w * 0.35))


def rim_from(cam, cool, at, col="#9fb8ff", a=0.55):
    """Rim settings from a world light direction `cool` (the direction the light travels): the band sits on the
    edge the light comes from, stronger when the light comes from behind the subject."""
    v = norm(cool)
    sx = dot(v, cam.right)
    sy = -v[1]
    back = dot(v, cam.fwd)                                   # < 0: the light comes toward the lens (from behind)
    return dict(d=(sx + 1e-3, sy), col=col, a=a * (0.45 + 0.55 * max(0.0, -back)))


def draw(fr, cam, pose, light=None, warm=None, cool=None, shadow=True, warm_col="#ffb35c", cool_col="#9fb8ff",
         rim_a=0.55):
    """light: key light position (world). warm: a warm practical (world point): the side of the face turned to it
    takes an amber glow. cool: the direction the cool window/evening light travels (world): a cool rim on that edge."""
    L = LOOK
    J = solve(pose)
    p, s, Bb, Bc, Bh, R = J["pose"], J["s"], J["Bb"], J["Bc"], J["Bh"], J["R"]
    c = fr.c
    out = {"look": "widemouth", "err": J["err"], "J": J}
    if min(cam.view(J[k])[2] for k in ("pelvis", "head")) < 0.25:
        out["culled"] = True
        return out
    P = cam.proj
    k0 = P(J["pelvis"])[3]
    lw = max(1.2, 0.0055 * k0)
    ld = rig.light_dir(cam, light, J["pelvis"])
    fur, fdk, muz = L["fur"], L["fur_dk"], L["muzzle"]
    rim = rim_from(cam, cool, J["head"], cool_col, rim_a) if cool else None
    rw = 0.008 * s * k0
    if shadow and not p.get("air") and not p.get("lie"):
        fr.ground_ellipse(cam, J["root"][0], J["root"][2], 0.13 * s, 0.10 * s, "#000000", 0.42,
                          blur_m=0.03 * s, y=p["floor"] + 0.003)
        for k in ("R", "L"):                                 # tight contact shadow under each foot
            a = J["ank_" + k]
            f = norm((Bb.f[0], 0, Bb.f[2]))
            fr.ground_ellipse(cam, a[0] + f[0] * 0.04 * s, a[2] + f[2] * 0.04 * s, 0.06 * s, 0.035 * s, "#000000", 0.5,
                              blur_m=0.012 * s, y=p["floor"] + 0.004)
    parts = []
    contacts = []
    to_cam_h = norm(sub(cam.pos, J["head"]))

    def z_of(*w):
        return sum(cam.view(q)[2] for q in w) / len(w)

    def warmth(nrm, at):
        """0..1: how much a surface (normal nrm at point at) faces the warm practical."""
        if not warm:
            return 0.0
        d = norm(sub(warm, at))
        return max(0.0, dot(norm(nrm), d)) * max(0.0, 1.0 - math.dist(warm, at) / 4.5)

    def tuft(base, tip, w0, colr=None, a=1.0):
        """A sculpted fur clump: a soft rounded teardrop from base to tip (world), w0 = half width at the base (m)."""
        pa, pb = P(base), P(tip)
        if min(pa[2], pb[2]) < 0.05:
            return None
        pth = capsule(pa[:2], w0 * pa[3], pb[:2], 0.5 * w0 * pb[3])
        fr.part(pth, colr or fur, ld, width=2 * w0 * pa[3], line=lw * 0.7, lit=0.12, dark=0.35)
        return pth

    # ---- legs and the long-toed feet ----
    def leg(k, g):
        hp, kn, an = J["hip_" + k], J["kn_" + k], J["ank_" + k]
        a, b, e = P(hp), P(kn), P(an)
        kk = a[3]
        path = union(capsule(a[:2], 0.036 * s * kk, b[:2], 0.026 * s * kk), capsule(b[:2], 0.024 * s * kk, e[:2], 0.017 * s * kk))
        up = norm(sub(J["kn_" + k], J["ank_" + k])) if p.get("lie") else (0.0, 1.0, 0.0)
        f = norm(sub(Bb.f, mul(up, dot(Bb.f, up))))
        f = rot(f, up, -g * 10)                              # feet splay out a little
        r = cross(up, f)
        sole = sub(an, mul(up, 0.02 * s))
        tc = p["toes"]

        def ring(cf, yy, ra, rb, n=18):
            c0 = add(sole, mul(f, cf), mul(up, yy))
            return [P(add(c0, mul(f, ra * math.cos(t)), mul(r, rb * math.sin(t))))[:2]
                    for t in (2 * math.pi * i / n for i in range(n))]
        foot = rig._poly_path(_hull(ring(0.03 * s, 0.0, 0.062 * s, 0.032 * s) + ring(0.005 * s, 0.03 * s, 0.032 * s, 0.024 * s)))
        toes = []
        for i, off in enumerate((-1.0, 0.0, 1.0)):            # three long toes; they curl down over an edge
            t0 = add(sole, mul(f, 0.08 * s), mul(r, off * 0.019 * s), mul(up, 0.008 * s))
            d = rot(f, up, off * 9)
            m1 = add(t0, mul(d, 0.028 * s))
            d2 = rot(d, cross(up, d), 55 * tc)               # the far joint bends down
            t1 = add(m1, mul(d2, 0.026 * s))
            toes.append((t0, m1, t1))
            contacts.append(("toe", t1, 0.01 * s))
        contacts.append(("foot", add(sole, mul(f, 0.03 * s)), 0.05 * s))

        def fn():
            fr.part(path, fur, ld, width=0.05 * s * kk, line=lw)
            _rim(fr, path, rim, rw * 0.7)
            for t0, m1, t1 in toes:
                q0, q1, q2 = P(t0), P(m1), P(t1)
                tp = union(capsule(q0[:2], 0.011 * s * q0[3], q1[:2], 0.009 * s * q1[3]),
                           capsule(q1[:2], 0.009 * s * q1[3], q2[:2], 0.007 * s * q2[3]))
                fr.part(tp, fur, ld, width=0.02 * s * q0[3], line=lw * 0.75)
                q3 = P(add(t1, mul(norm(sub(t1, m1)), 0.008 * s)))
                c.drawPath(capsule(q2[:2], 0.005 * s * q2[3], q3[:2], 0.002 * s * q2[3]), paint(L["pads"]))
            fr.part(foot, shade(fur, -0.05), ld, width=0.07 * s * kk, line=lw)
            _rim(fr, foot, rim, rw * 0.6)
        parts.append((z_of(hp, kn, an), fn))
        out["foot_" + k] = e[:2]

    # ---- arms: long and thin, long fingers ----
    def arm(k, g):
        S, E, Wr = J["sh_" + k], J["el_" + k], J["wr_" + k]
        a, b, e = P(S), P(E), P(Wr)
        kk = a[3]
        limb = union(capsule(a[:2], 0.026 * s * kk, b[:2], 0.017 * s * kk), capsule(b[:2], 0.017 * s * kk, e[:2], 0.013 * s * kk))
        fd = J["fdir_" + k]
        pn = norm(p.get("palm_" + k, mul(Bc.r, g * 1.0)))
        pn = norm(sub(pn, mul(fd, dot(pn, fd)))) if abs(dot(pn, fd)) < 0.98 else norm(cross(fd, Bc.f))
        sx = norm(cross(fd, pn))
        cu = p.get("curl_" + k, 0.35)
        cu = list(cu) if isinstance(cu, (list, tuple)) else [cu] * 4
        H_ = Wr
        segs = [(H_, add(H_, mul(fd, 0.032 * s)), 0.017 * s, 0.019 * s, fur)]          # palm
        tips_ = []
        for i, off in enumerate((-1.0, 0.0, 1.0)):            # three long fingers (index, middle, ring)
            ln = (0.032, 0.026, 0.02) if i == 1 else (0.028, 0.023, 0.018)
            q = add(H_, mul(fd, 0.034 * s), mul(sx, off * 0.012 * s))
            d = rot(fd, pn, -off * 6.0)
            for j, Lj in enumerate(ln):
                d = rot(d, sx, -(8 + 74 * cu[i]) * (0.55 if j == 0 else 1.0))
                nq = add(q, mul(d, Lj * s))
                segs.append((q, nq, (0.0072 - 0.0011 * j) * s, (0.0064 - 0.0011 * j) * s, L["pads"] if j == 2 else fur))
                q = nq
            tips_.append((q, d))
            contacts.append(("finger", q, 0.011 * s))
        th0 = add(H_, mul(sx, -g * 0.016 * s), mul(fd, 0.01 * s))
        td = norm(add(mul(fd, 0.7), mul(sx, -g * 0.7), mul(pn, 0.25 + 0.45 * cu[3])))
        th1 = add(th0, mul(td, 0.024 * s))
        th2 = add(th1, mul(norm(add(td, mul(pn, 0.3 + cu[3]))), 0.019 * s))
        segs += [(th0, th1, 0.0078 * s, 0.007 * s, fur), (th1, th2, 0.007 * s, 0.0055 * s, L["pads"])]
        tips_.append((th2, norm(sub(th2, th1))))
        contacts.append(("finger", th2, 0.011 * s))

        def hand():
            for a0, b0, r0, r1, colr in sorted(segs, key=lambda q: -(cam.view(q[0])[2] + cam.view(q[1])[2])):
                pa, pb = P(a0), P(b0)
                if min(pa[2], pb[2]) < 0.05:
                    continue
                pth = capsule(pa[:2], r0 * pa[3], pb[:2], r1 * pb[3])
                fr.part(pth, colr, ld, width=2 * r0 * pa[3], line=lw * 0.7, lit=0.12, dark=0.38)
                _rim(fr, pth, rim, rw * 0.45)
            for q, d in tips_:                                # short dark claws
                a1, b1 = P(q), P(add(q, mul(d, 0.008 * s)))
                if min(a1[2], b1[2]) < 0.05:
                    continue
                c.drawPath(capsule(a1[:2], 0.0038 * s * a1[3], b1[:2], 0.0015 * s * a1[3]), paint("#2a2026"))

        def fn():
            fr.part(limb, fur, ld, width=0.035 * s * kk, line=lw)
            _rim(fr, limb, rim, rw * 0.8)
            tuft(add(Wr, mul(fd, -0.02 * s)), add(Wr, mul(fd, 0.004 * s)), 0.014 * s, shade(fur, 0.02))         # wrist ruff
            hand()
        fn.arm = True
        parts.append((z_of(S, E, Wr), fn))
        out["hand_" + k] = P(add(H_, mul(fd, 0.04 * s)))[:2]

    # ---- body: a soft pear of fur, the pale belly, the ruff behind the shoulders ----
    def body():
        br = 1 + 0.025 * p["breath"]
        rt = [(-0.045, 0.060, 0.056, 0.0), (0.0, 0.074, 0.068, 0.004), (0.05, 0.080, 0.072, 0.006),
              (0.10, 0.076, 0.066, 0.002), (0.145, 0.070, 0.058, -0.004), (0.18, 0.058, 0.050, -0.002),
              (0.205, 0.040, 0.036, 0.004)]
        rings = [(u * s, wa * s * (br if 0.03 < u < 0.16 else 1), db * s * (br if 0.03 < u < 0.16 else 1), 0, bo * s)
                 for u, wa, db, bo in rt]
        path, zt = lathe(cam, J["pelvis"], Bc, rings)
        front = dot(Bc.f, norm(sub(cam.pos, J["pelvis"])))
        kk = P(J["pelvis"])[3]
        # the ruff: clumps round the back of the shoulders, pulled toward the grip when scruffed
        sc, at = p["scruff"], p.get("scruff_at")
        ruff = []
        for i in range(7):
            t = math.radians(200 + 140 * i / 6)               # behind (b < 0) from shoulder to shoulder
            base = Bc.w(J["pelvis"], 0.07 * s * math.cos(t), (0.19 - 0.012 * abs(i - 3)) * s, 0.062 * s * math.sin(t) - 0.004 * s)
            tip = add(base, Bc.d(0.022 * s * math.cos(t), -0.06 * s, 0.022 * s * math.sin(t) - 0.012 * s))
            w0 = (0.034 - 0.002 * abs(i - 3)) * s
            if sc > 0 and at is not None:                     # pulled up into the fist, squeezed thin
                pull = sc * max(0.0, 1.0 - math.dist(base, at) / (0.11 * s))
                tip = add(lerp_v(tip, at, 0.85 * pull), mul(Bc.u, 0.0))
                base = lerp_v(base, at, 0.35 * pull)
                w0 *= 1.0 - 0.45 * pull
            ruff.append((base, tip, w0))
        J["scruff_pts"] = ruff

        def fn_ruff():
            for base, tip, w0 in sorted(ruff, key=lambda q: -cam.view(q[0])[2]):
                pth = tuft(base, tip, w0, shade(fur, -0.06))
                if pth is not None:
                    _rim(fr, pth, rim, rw * 0.6)

        nb = P(J["neck"])

        def fn():
            def occl(cv):                                      # the head's shadow on the chest
                hd = P(J["head"])
                cv.drawOval(skia.Rect(hd[0] - 0.1 * s * kk, nb[1] - 0.03 * s * kk, hd[0] + 0.1 * s * kk, nb[1] + 0.05 * s * kk),
                            paint("#05060c", a=0.4, blur=0.025 * s * kk))
            if front > 0.2:
                fn_ruff()
            fr.part(path, fur, ld, width=0.15 * s * kk, line=lw, lit=0.12, dark=0.42, occl=occl)
            c.save()
            c.clipPath(path, skia.ClipOp.kIntersect, True)
            if front > -0.1:                                   # the pale belly patch, seen from the front half
                bc = P(Bc.w(J["pelvis"], 0, 0.06 * s, 0.07 * s))
                bw = 0.05 * s * kk * max(0.15, front)
                c.drawOval(skia.Rect(bc[0] - bw, bc[1] - 0.07 * s * kk, bc[0] + bw, bc[1] + 0.06 * s * kk),
                           paint(shade(muz, -0.12), a=0.85, blur=0.008 * s * kk))
            if warm:                                            # the lamp's warmth on the side turned to it
                for sg in (1, -1):
                    q = Bc.w(J["pelvis"], sg * 0.07 * s, 0.1 * s, 0.02 * s)
                    wk = warmth(Bc.d(sg, 0, 0.3), q)
                    if wk > 0.02:
                        pq = P(q)
                        c.drawCircle(pq[0], pq[1], 0.08 * s * kk, paint(warm_col, a=0.2 * wk, blur=0.05 * s * kk))
            c.restore()
            _rim(fr, path, rim, rw)
            if p["swallow"] > 0.01 and front > 0.3:            # the throat moves under the chin
                q = P(Bc.w(J["pelvis"], 0, (0.205 - 0.03 * p["swallow"]) * s, 0.055 * s))
                c.drawArc(skia.Rect(q[0] - 0.012 * s * kk, q[1] - 0.006 * s * kk, q[0] + 0.012 * s * kk, q[1] + 0.006 * s * kk),
                          200, 140, False, paint(shade(fur, -0.55), stroke=lw * 0.7, a=0.8 * min(1.0, p["swallow"] * 3)))
            if front <= 0.2:
                fn_ruff()
        parts.append((zt, fn))
        J["_zt"] = zt

    # ---- head ----
    def head():
        Hd = Head(cam, J["head"], Bh, R, SHAPE)
        rings = []
        for i in range(13):                                  # rings from the same surface the face decals use
            mu = -math.pi / 2 + math.pi * i / 12
            q = Hd.surf(0.0, mu)
            u = dot(sub(q, J["head"]), Bh.u)
            wa = abs(dot(sub(Hd.surf(math.pi / 2, mu), J["head"]), Bh.r))
            db = abs(dot(sub(q, J["head"]), Bh.f))
            rings.append((u, max(wa, 1e-4), max(db, 1e-4), 0, 0))
        path, zh = lathe(cam, J["head"], Bh, rings)
        hc = P(J["head"])
        kk = hc[3]
        facing_k = dot(Bh.f, to_cam_h)

        # ears: tall leaves off the top corners; the left one (lam +) is bent crooked halfway up
        ears = []
        for sg in (1, -1):                                    # sg +1 = the character's LEFT (lam +)
            base_c = Hd.surf(sg * 0.62, 0.78, 0.96)
            outward = norm(sub(base_c, J["head"]))
            down = 1.0 - p["ears"]
            up = norm(add(mul(Bh.u, 1.0), mul(Bh.r, -sg * 0.32)))
            up = rot(up, Bh.r, -70 * down)                  # lowered: laid back along the skull
            up = rot(up, Bh.f, sg * 25 * down)
            Lr = 1.15 * R
            fo = norm(add(mul(Bh.f, 0.8), mul(Bh.r, -sg * 0.6)))
            nrm = norm(sub(fo, mul(up, dot(fo, up))))         # the open face looks forward and a little out
            side = norm(cross(nrm, up))
            mid = add(base_c, mul(up, 0.5 * Lr))
            if sg > 0:                                        # the crooked ear: the top half folds outward
                bend = 80 + p["twitch"]
                up2 = rot(up, nrm, sg * bend)
            else:
                up2 = rot(up, nrm, -sg * (6 + 0.3 * p["twitch"]))
            tip = add(mid, mul(up2, 0.55 * Lr))
            w0, w1 = 0.30 * R, 0.24 * R
            side2 = norm(cross(nrm, up2))
            ring = [add(base_c, mul(side, -w0)), add(mid, mul(side, -w1), mul(side2, -0.02 * R)), tip,
                    add(mid, mul(side, w1), mul(side2, 0.02 * R)), add(base_c, mul(side, w0))]
            inner = [add(base_c, mul(side, -0.6 * w0), mul(up, 0.08 * R), mul(nrm, 0.01 * R)),
                     add(mid, mul(side, -0.55 * w1), mul(nrm, 0.01 * R)), add(tip, mul(up2, -0.18 * R), mul(nrm, 0.01 * R)),
                     add(mid, mul(side, 0.55 * w1), mul(nrm, 0.01 * R)), add(base_c, mul(side, 0.6 * w0), mul(up, 0.08 * R), mul(nrm, 0.01 * R))]
            open_face = dot(nrm, norm(sub(cam.pos, mid))) > 0.05
            behind = dot(sub(mid, J["head"]), to_cam_h) < -0.35 * R
            ears.append((behind, ring, inner, open_face, sg, base_c))
        J["ear_tips"] = [e[1][2] for e in ears]

        def ear_fn(ring, inner, open_face, sg):
            def f():
                pts = [P(q)[:2] for q in ring]
                pth = smooth(pts, k=0.5)
                fr.part(pth, fur, ld, width=0.5 * R * kk, line=lw, lit=0.12, dark=0.38)
                if open_face:
                    c.save()
                    c.clipPath(pth, skia.ClipOp.kIntersect, True)
                    c.drawPath(smooth([P(q)[:2] for q in inner], k=0.5), paint(L["inner"], a=0.9, blur=0.02 * R * kk))
                    c.restore()
                _rim(fr, pth, rim, rw * 0.8)
            return f

        def fn():
            for behind, ring, inner, of, sg, _ in ears:
                if behind:
                    ear_fn(ring, inner, of, sg)()
            fr.part(path, fur, ld, width=2.2 * R * kk, line=lw, outline=False, lit=0.14, dark=0.4)
            c.save()
            c.clipPath(path, skia.ClipOp.kIntersect, True)
            face(Hd, kk)
            c.restore()
            c.drawPath(path, paint(shade(fur, -0.7), stroke=lw))
            _rim(fr, path, rim, rw * 1.2)
            relief(Hd, kk)
            for behind, ring, inner, of, sg, _ in ears:
                if not behind:
                    ear_fn(ring, inner, of, sg)()
            props(Hd, kk)
        zt = J["_zt"]
        parts.append((min(zh, zt - 1e-4) if facing_k > -0.25 else zh, fn))
        out["head"] = hc[:2]
        out["head_r"] = 1.3 * R * kk

    def surf_path(Hd, pts_lm, lift=1.0, closed=False):
        return [P(Hd.surf(l, m, lift))[:2] for l, m in pts_lm]

    def face(Hd, kk):
        eo, lid, brow = p["eye_open"], p["lid"], p["brow"]
        grin, opn, sag = p["grin"], p["open"], p["sag"]
        # the pale muzzle: lower face from cheek to cheek (the mouth lives on it)
        if Hd.facing(0.0, -0.3) > -0.2:
            pts = []
            for i in range(25):
                t = 2 * math.pi * i / 24
                lam, mu = 1.22 * math.cos(t), -0.30 + 0.31 * math.sin(t)
                pts.append(P(Hd.surf(lam, mu, 1.002))[:2])
            mz = smooth(pts, k=0.6)
            c.drawPath(mz, paint(muz, a=0.95, blur=0.03 * R * kk))
        # warm lamp on the room-side cheek
        for sg in (-1, 1):
            q = Hd.surf(sg * 0.75, -0.15)
            wk = warmth(sub(q, J["head"]), q)
            if wk > 0.02 and Hd.facing(sg * 0.75, -0.15) > -0.1:
                c.save()
                c.concat(Hd.decal(sg * 0.75, -0.15))
                c.drawOval(skia.Rect(-0.5 * R, -0.4 * R, 0.5 * R, 0.4 * R), paint(warm_col, a=0.3 * wk, blur=0.25 * R))
                c.restore()
        # small amber eyes, high and wide; the smile's cheeks push the lower lids up
        lo = max(p["lid_lo"], 0.22 * grin * (1 - opn))
        for sg in (-1, 1):
            lam, mu = sg * 0.40, 0.25
            if Hd.facing(lam, mu) <= 0.08:
                continue
            c.save()
            c.concat(Hd.decal(lam, mu))
            rx, ry = 0.135 * R, 0.135 * R * eo
            c.drawOval(skia.Rect(-rx * 1.5, -ry * 1.45, rx * 1.5, ry * 1.4), paint("#1b1218", a=0.35, blur=0.06 * R))   # socket
            eye = skia.Path()
            eye.addOval(skia.Rect(-rx, -ry, rx, ry))
            c.drawPath(eye, paint("#f3ece2"))
            c.save()
            c.clipPath(eye, skia.ClipOp.kIntersect, True)
            gx, gy = p["gx"] * 0.06 * R, -p["gy"] * 0.05 * R
            ir = 0.085 * R
            c.drawCircle(gx, gy, ir, paint(L["iris"]))
            c.drawCircle(gx, gy, ir, paint(shade(L["iris"], -0.5), stroke=0.015 * R))
            c.drawCircle(gx, gy, 0.03 * R, paint("#120a0c"))
            c.drawCircle(gx - 0.028 * R, gy - 0.03 * R, 0.017 * R, paint("#ffffff", a=0.85))   # one restrained glint
            lt = -ry + 2 * ry * min(1.0, lid / max(0.4, eo))
            c.drawRect(skia.Rect(-rx * 1.3, -ry * 1.4, rx * 1.3, lt), paint(shade(fur, -0.08)))
            lb = ry - 2 * ry * 0.55 * lo
            lower = skia.Path()
            lower.moveTo(-rx * 1.3, ry * 1.4)
            lower.lineTo(-rx * 1.3, lb + 0.25 * ry * lo)
            lower.quadTo(0, lb - 0.4 * ry * lo, rx * 1.3, lb + 0.25 * ry * lo)
            lower.lineTo(rx * 1.3, ry * 1.4)
            lower.close()
            c.drawPath(lower, paint(mix(fur, muz, 0.5)))
            c.restore()
            c.drawPath(eye, paint("#1e1418", stroke=0.022 * R))
            c.drawLine(-rx * 1.05, lt, rx * 1.05, lt, paint("#1e1418", stroke=0.03 * R)) if lid > 0.05 else None
            c.restore()
        # the mouth: one wide line from cheek to cheek, the corners curling up into the cheeks
        Lm = 0.92 + 0.22 * grin
        lift = 0.55 * grin * (1 - sag)
        m0 = -0.40
        N = 23
        top, bot = [], []
        for i in range(N):
            u = -1 + 2 * i / (N - 1)
            lam = Lm * u
            curve = lift * abs(u) ** 2.2 - 0.03 * grin * (1 - u * u)
            top.append((lam, m0 + curve + 0.012 * opn * (1 - u * u)))
            drop = opn * (0.26 + 0.06 * sag) * (1 - u * u) ** 0.8
            bot.append((lam, m0 + curve - drop))
        vis = [Hd.facing(l, m) > -0.05 for l, m in top]
        if any(vis):
            i0 = vis.index(True)
            i1 = len(vis) - 1 - vis[::-1].index(True)
            T_ = surf_path(Hd, top[i0:i1 + 1], 1.0)
            B_ = surf_path(Hd, bot[i0:i1 + 1], 1.0)
            if opn > 0.03 and len(T_) > 2:
                hole = smooth(T_ + B_[::-1], k=0.5)
                c.drawPath(hole, paint(L["mouth"]))
                c.save()
                c.clipPath(hole, skia.ClipOp.kIntersect, True)
                # a row of small flat teeth under the upper lip, a tongue at the bottom
                tb = surf_path(Hd, [(l, m - 0.07) for l, m in top[i0:i1 + 1]], 1.0)
                c.drawPath(smooth(T_ + tb[::-1], k=0.5), paint(L["teeth"]))
                for j in range(1, len(T_) - 1, 2):
                    c.drawLine(T_[j][0], T_[j][1], tb[j][0], tb[j][1], paint("#b9ad9c", stroke=0.012 * R * kk))
                tg = surf_path(Hd, [(l * 0.55, m + 0.03) for l, m in bot[i0:i1 + 1]], 1.0)
                c.drawPath(smooth(tg + B_[::-1], k=0.5), paint(L["tongue"], a=0.9))
                c.restore()
                c.drawPath(hole, paint("#24101a", stroke=0.03 * R * kk))
            else:
                c.drawPath(smooth(T_, closed=False, k=0.6), paint("#24101a", stroke=0.045 * R * kk))
            # the cheeks bunch up at the corners: a short crease past each end
            for idx, sg in ((i0, -1), (i1, 1)):
                l, m = top[idx]
                if abs(l) < 0.6 * Lm or Hd.facing(l, m) < 0.05:
                    continue
                cr_ = [P(Hd.surf(l + sg * 0.03, m + 0.01))[:2], P(Hd.surf(l + sg * 0.09, m + 0.07 + 0.05 * grin))[:2],
                       P(Hd.surf(l + sg * 0.06, m + 0.14 + 0.06 * grin))[:2]]
                c.drawPath(smooth(cr_, closed=False), paint(shade(muz, -0.55), stroke=0.022 * R * kk, a=0.4 + 0.5 * grin))
        out["mouth_w"] = Lm

    def relief(Hd, kk):
        """Brow tufts and the nose, drawn unclipped so they stand off the head in profile."""
        brow = p["brow"]
        eo = p["eye_open"]
        for sg in (-1, 1):                                   # a short thick tuft over each eye
            lam0 = sg * 0.40
            if Hd.facing(lam0, 0.42) <= 0.05:
                continue
            raise_ = 0.05 * (eo - 1) + 0.05 * max(0.0, -brow)
            inner_y = 0.42 + raise_ - 0.06 * brow + 0.06 * max(0.0, -brow)
            outer_y = 0.44 + raise_ + 0.03 * brow - 0.03 * max(0.0, -brow)
            a = P(Hd.surf(lam0 - sg * 0.13, inner_y, 1.03))[:2]
            m = P(Hd.surf(lam0, (inner_y + outer_y) / 2 + 0.02, 1.035))[:2]
            b = P(Hd.surf(lam0 + sg * 0.15, outer_y, 1.03))[:2]
            c.drawPath(smooth([a, m, b], closed=False), paint(shade(fur, -0.45), stroke=0.07 * R * kk))
        # the small dark nose: a soft rounded triangle just above the mouth
        if Hd.facing(0.0, -0.12) > -0.3:
            q = [P(Hd.surf(-0.07, -0.08, 1.07))[:2], P(Hd.surf(0.07, -0.08, 1.07))[:2], P(Hd.surf(0.0, -0.16, 1.09))[:2]]
            pth = smooth(q, k=0.8)
            fr.part(pth, L["nose"], ld, width=0.15 * R * kk, line=lw * 0.6, lit=0.25, dark=0.4)
            hl = P(Hd.surf(-0.02, -0.09, 1.09))
            c.drawCircle(hl[0], hl[1], 0.012 * R * kk, paint("#ffffff", a=0.5))
        # fur clumps on top of the head and the cheek ruffs that widen the silhouette
        for lam, mu, dl, dm, w in ((-0.12, 0.95, -0.12, 0.25, 0.13), (0.14, 0.95, 0.14, 0.25, 0.12)):
            b0 = Hd.surf(lam, mu, 0.98)
            t0 = add(b0, mul(Bh.u, 0.16 * R), mul(Bh.r, -dl * R), mul(Bh.f, -0.1 * R))
            if dot(norm(sub(b0, J["head"])), to_cam_h) > -0.5:
                tuft(b0, t0, w * R)
        for sg in (-1, 1):
            for j, (mu, ln) in enumerate(((-0.05, 0.30), (-0.30, 0.26))):
                b0 = Hd.surf(sg * 1.35, mu, 0.97)
                outd = norm(sub(b0, J["head"]))
                t0 = add(b0, mul(outd, ln * R), mul(Bh.u, -0.12 * R))
                if dot(outd, to_cam_h) > -0.75:
                    pth = tuft(b0, t0, 0.11 * R)
                    if pth is not None:
                        _rim(fr, pth, rim, rw * 0.5)

    def props(Hd, kk):
        """A twig caught behind the right ear and a leaf on the head / slipping down the nose (the hedge)."""
        if p["twig"]:
            b0 = Hd.surf(-0.66, 0.55, 1.0)
            t0 = add(b0, mul(Bh.u, 0.5 * R), mul(Bh.r, 0.35 * R), mul(Bh.f, -0.1 * R))
            pa, pb = P(b0), P(t0)
            c.drawLine(pa[0], pa[1], pb[0], pb[1], paint("#4a3826", stroke=0.035 * R * kk))
            mid = P(add(b0, mul(sub(t0, b0), 0.6)))
            sp = P(add(b0, mul(sub(t0, b0), 0.6), mul(Bh.r, -0.18 * R), mul(Bh.u, 0.12 * R)))
            c.drawLine(mid[0], mid[1], sp[0], sp[1], paint("#4a3826", stroke=0.022 * R * kk))
            leaf_at(sp, 0.12 * R * kk, 40)
        lf = p["leaf"]
        if lf >= 0:
            if lf <= 1.0:                                     # on the crown, then sliding down the forehead to the nose
                mu = lerp(1.0, -0.06, lf)
                q = Hd.surf(0.06, mu, 1.08)
                if Hd.facing(0.06, mu) > -0.2 or lf < 0.2:
                    leaf_at(P(q), 0.16 * R * kk, -30 + 50 * lf)

    def leaf_at(pt, size, ang):
        c.save()
        c.translate(pt[0], pt[1])
        c.rotate(ang)
        lf = skia.Path()
        lf.moveTo(-size, 0)
        lf.quadTo(0, -size * 0.6, size, 0)
        lf.quadTo(0, size * 0.6, -size, 0)
        lf.close()
        fr.part(lf, "#5f7a3a", (0.3, 1.0), width=size, line=max(0.8, size * 0.08), lit=0.2, dark=0.35)
        c.drawLine(-size * 0.9, 0, size * 0.9, 0, paint("#3e5326", stroke=max(0.6, size * 0.06)))
        c.restore()

    for k, g in (("R", 1), ("L", -1)):
        leg(k, g)
        arm(k, g)
    body()
    head()
    for _, fn in sorted(parts, key=lambda q: -q[0]):
        fn()
    out["contacts"] = contacts
    out["grab"] = {"scruff": J["scruff"]}
    out["depth"] = P(J["pelvis"])[2]
    return out


def lerp_v(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


# ---- model sheet -----------------------------------------------------------------------------------------------
def sheet(path):
    from PIL import Image, ImageDraw
    from toon import Camera, Frame
    tiles = []
    warm = (1.4, 1.0, 2.2)                                   # an amber lamp front-right of the creature

    def tile(cam, pose, label):
        fr = Frame(0.36, bg="#1c2033")
        fr.ground_ellipse(cam, 0, 1.6, 0.7, 0.5, "#2a3048", 1.0, blur_m=0.25)
        pose = dict(dict(x=0, z=1.6, yaw=0), **pose)
        draw(fr, cam, pose, light=(1.0, 1.4, 2.6), warm=warm, cool=(-0.6, -0.25, 0.4))
        im = Image.fromarray(fr.array())
        d = ImageDraw.Draw(im)
        d.rectangle((0, im.height - 26, im.width, im.height), fill=(0, 0, 0))
        d.text((8, im.height - 21), label, fill=(255, 230, 120))
        tiles.append(im)
    wide = Camera((0, 0.36, 0.0), 0, f=2300, horizon=0.45)
    for yaw, lab in ((0, "front"), (35, "3/4"), (90, "side"), (180, "back")):
        tile(wide, dict(yaw=yaw, breath=0.3), lab)
    close = Camera((0, 0.47, 0.55), 0, f=1900, horizon=0.5)
    E = [("watching (still smile)", dict(yaw=15, grin=0.75, gx=-0.3)),
         ("talking: 'Jump'", dict(yaw=15, grin=0.9, open=0.45, gx=-0.3)),
         ("'You first': eyes stop", dict(yaw=15, grin=0.55, open=0.05, eye_open=1.2, lid=0.0, ears=0.35, brow=-0.6)),
         ("excuse: corners only", dict(yaw=15, grin=0.35, open=0.0, eye_open=1.0, lid=0.25, gy=-0.8, ears=0.5, brow=-0.7, swallow=0.8)),
         ("'WAIT-'", dict(yaw=15, grin=0.1, open=0.95, sag=1.0, eye_open=1.55, lid=0.0, ears=0.0, brow=-1.0)),
         ("hedge: dazed, leaf", dict(yaw=15, grin=0.0, open=0.35, sag=1.0, lid=0.35, gy=0.9, ears=0.6, twig=True, leaf=0.8)),
         ("ankle: wince", dict(yaw=20, grin=0.0, open=0.2, sag=1.0, lid=0.7, brow=-0.9, ears=0.25))]
    for lab, pose in E:
        tile(close, pose, lab)
    w, h = tiles[0].size
    cols = 4
    rows = -(-len(tiles) // cols)
    img = Image.new("RGB", (w * cols + 8 * (cols - 1), h * rows + 8 * (rows - 1)), (0, 0, 0))
    for i, t in enumerate(tiles):
        img.paste(t, ((i % cols) * (w + 8), (i // cols) * (h + 8)))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)
    print(path, img.size)


if __name__ == "__main__":
    root = os.path.abspath(os.path.join(HERE, "..", ".."))
    sheet(sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, "assets", "kit", "cast", "widemouth.png"))
