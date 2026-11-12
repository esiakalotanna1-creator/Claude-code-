"""The Mara: the nightmare spirit of Scandinavian folklore (Sweden, Norway) that sits on a sleeper's chest so they
can't move or call out, the old explanation for sleep paralysis.

Look "mara": tall and gaunt, ashen grey-blue skin, long tangled near-black hair (cast.hair strands with tangle and
flyaways), a sunken creepy face (cast.faces style MARA), an old undyed robe with folds and a frayed hem that works
standing, kneeling or sitting (it is built along the legs, not as a fixed skirt), and long dark hands with cracked
nails in place of the rig's mitten hands.

Pose keys (on top of the rig's): t, breeze (hair drift), curl_R / curl_L (0 open .. 1 fingers clenched),
palm_R / palm_L (world palm normal, default down), creep (face strength, default 1), frown.
"""
import math

import skia

import rig
from rig import add, cross, dot, mul, norm, sub, smooth
from toon import paint, shade

from cast import faces, hair

SKIN = "#a9adb8"          # ashen; reads near-black in the bedroom's blue night light
HAND = "#5d606c"          # the long dark hands (the brief: "a long, dark hand")
NAIL = "#c9b98c"
ROBE = "#6f685c"          # old undyed wool/linen


def robe(parts, fr, cam, J, p, ld, lw, out):
    """Robe from the waist down, built per leg (hip -> knee -> 75% down the shin) plus the cloth spanning between
    the legs, so it drapes over a seated lap as well as hanging straight when she stands."""
    h, Bb, P = J["h"], J["Bb"], J["pelvis"]
    L = rig.LOOK[J["look"]]
    col = L["top"]
    k = cam.proj(P)[3]
    hem = {}
    legs = []
    for s, sg in (("R", 1), ("L", -1)):
        hip = J["hip_" + s]
        kn, an = J["kn_" + s], J["ank_" + s]
        end = add(kn, mul(sub(an, kn), 0.78))
        hip_o = add(hip, mul(Bb.r, sg * 0.035 * h))           # the cloth hangs wider than the hip joint
        legs.append((s, hip_o, kn, end))
        hem[s] = end
    # outline of the whole robe: outer edge of R leg, hem across, outer edge of L leg, waist across
    waist = [Bb.w(P, sg * 0.105 * h * L["build"], 0.03 * h, 0.0) for sg in (1, -1)]

    def side(pt_list, sg):
        return [add(q, mul(Bb.r, sg * w * h)) for q, w in pt_list]

    (sR, hR, kR, eR), (sL, hL, kL, eL) = legs
    outer_R = side([(hR, 0.02), (kR, 0.075), (eR, 0.085)], 1)
    outer_L = side([(hL, 0.02), (kL, 0.075), (eL, 0.085)], -1)
    # hull of each leg sample widened sideways AND front/back, so the robe stays a robe from the side too
    vol = list(waist)
    for q, w in ((hR, 0.045), (kR, 0.07), (eR, 0.09), (hL, 0.045), (kL, 0.07), (eL, 0.09)):
        vol += [add(q, mul(Bb.r, sg * w * h)) for sg in (1, -1)] + [add(q, mul(Bb.f, sg * w * h)) for sg in (1, -1)]
    pts = [cam.proj(q) for q in vol]
    if min(q[2] for q in pts) < 0.2:
        return
    path = smooth(rig._hull([q[:2] for q in pts]), k=0.35)
    z = sum(q[2] for q in pts) / len(pts)

    def fn():
        fr.part(path, col, ld, width=0.28 * h * k, line=lw, lit=0.12, dark=0.45)
        c = fr.c
        c.save()
        c.clipPath(path, skia.ClipOp.kIntersect, True)
        # folds: from the waist down each leg and into the gap between the knees
        for a, b in ((waist[0], eR), (waist[1], eL), (Bb.w(P, 0.0, 0.0, 0.08 * h), mul(add(eR, eL), 0.5)),
                     (Bb.w(P, 0.05 * h, 0.0, 0.08 * h), mul(add(kR, eR), 0.5)), (Bb.w(P, -0.05 * h, 0.0, 0.08 * h), mul(add(kL, eL), 0.5))):
            pa, pb = cam.proj(a), cam.proj(b)
            m = ((pa[0] + pb[0]) / 2 + 0.01 * h * k, (pa[1] + pb[1]) / 2)
            fold = skia.Path()
            fold.moveTo(pa[0], pa[1])
            fold.quadTo(m[0], m[1], pb[0], pb[1])
            c.drawPath(fold, paint(shade(col, -0.45), stroke=lw * 1.3, a=0.55, blur=lw * 0.6))
        # worn, lighter patches at the knees
        for kn in (kR, kL):
            q = cam.proj(kn)
            c.drawOval(skia.Rect(q[0] - 0.04 * h * k, q[1] - 0.03 * h * k, q[0] + 0.04 * h * k, q[1] + 0.03 * h * k),
                       paint(shade(col, 0.25), a=0.25, blur=0.02 * h * k))
        c.restore()
        # the frayed hem: a jagged fringe hanging under the bottom edge
        a, b = cam.proj(outer_R[-1]), cam.proj(outer_L[-1])
        n = 14
        fringe = skia.Path()
        fringe.moveTo(a[0], a[1])
        for i in range(1, n + 1):
            u = i / n
            x, y = a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u
            drop = (0.018 + 0.012 * math.sin(i * 2.7)) * h * k
            xm, ym = a[0] + (b[0] - a[0]) * (u - 0.5 / n), a[1] + (b[1] - a[1]) * (u - 0.5 / n)
            fringe.lineTo(xm, ym + drop)
            fringe.lineTo(x, y)
        fringe.close()
        c.drawPath(fringe, paint(shade(col, -0.2)))
        c.drawPath(fringe, paint(shade(col, -0.72), stroke=lw * 0.8))
    parts.append(("coat", z, fn))

    def neckline():                                           # a loose, low V collar with a worn edge
        Bc = J["Bc"]
        if dot(Bc.f, norm(sub(cam.pos, J["neck"]))) <= 0:
            return
        q = [cam.proj(Bc.w(P, a * h, u * h, b * h))[:2] for a, u, b in
             ((0.07, 0.30, 0.03), (0.035, 0.24, 0.075), (0.0, 0.21, 0.085), (-0.035, 0.24, 0.075), (-0.07, 0.30, 0.03))]
        fr.c.drawPath(smooth(q, closed=False, k=0.5), paint(shade(col, -0.55), stroke=lw * 1.4))
        fr.c.drawPath(smooth(q, closed=False, k=0.5), paint(shade(col, 0.2), stroke=lw * 0.5, a=0.6))
    parts.append(("overtorso", z, neckline))


def claws(parts, fr, cam, J, p, ld, lw, out):
    """Long dark fingers in world space from each hand, nails cracked; replaces the rig's mitten hand."""
    h = J["h"]
    for s, sg in (("R", 1), ("L", -1)):
        p["hide_hand_" + s] = True
        H, fd = J["hand_" + s], J["fdir_" + s]
        pn = norm(p.get("palm_" + s, (0.0, -1.0, 0.0)))
        pn = norm(sub(pn, mul(fd, dot(pn, fd)))) if abs(dot(pn, fd)) < 0.98 else norm(cross(fd, J["Bc"].r))
        sx = norm(cross(fd, pn))
        curl = p.get("curl_" + s, 0.15)
        segs = []                                              # (a, b, r0, r1, colour)
        base = add(H, mul(fd, -0.015 * h))
        segs.append((base, add(H, mul(fd, 0.02 * h)), 0.026 * h, 0.024 * h, HAND))       # palm
        tips = []
        for i, off in enumerate((-1.5, -0.5, 0.5, 1.5)):
            ln = (0.040, 0.032, 0.026) if i in (1, 2) else (0.034, 0.028, 0.022)
            q = add(H, mul(fd, 0.026 * h), mul(sx, off * 0.0105 * h))
            d = rig.rot(fd, sx, 0.0)
            spread = rig.rot(d, pn, -off * 4.0)
            d = spread
            for j, L in enumerate(ln):
                d = rig.rot(d, sx, -(12 + 70 * curl) * (0.6 if j == 0 else 1.0))   # bend toward the palm side
                nq = add(q, mul(d, L * h))
                segs.append((q, nq, (0.0085 - 0.0012 * j) * h, (0.0075 - 0.0012 * j) * h, HAND))
                q = nq
            tips.append((q, d, i))
        th0 = add(H, mul(sx, -sg * 0.018 * h), mul(fd, 0.0))
        td = norm(add(mul(fd, 0.7), mul(sx, -sg * 0.7), mul(pn, 0.2 + 0.4 * curl)))
        th1 = add(th0, mul(td, 0.03 * h))
        th2 = add(th1, mul(norm(add(td, mul(pn, 0.3 + curl))), 0.024 * h))
        segs += [(th0, th1, 0.009 * h, 0.008 * h, HAND), (th1, th2, 0.008 * h, 0.0065 * h, HAND)]
        tips.append((th2, norm(sub(th2, th1)), 9))
        zs = cam.proj(H)[2]

        def fn(segs=segs, tips=tips, s=s):
            for a, b, r0, r1, colr in sorted(segs, key=lambda q: -(cam.view(q[0])[2] + cam.view(q[1])[2])):
                pa, pb = cam.proj(a), cam.proj(b)
                if min(pa[2], pb[2]) < 0.1:
                    continue
                fr.part(rig.capsule(pa[:2], r0 * pa[3], pb[:2], r1 * pb[3]), colr, ld, width=2 * r0 * pa[3], line=lw * 0.8,
                        lit=0.1, dark=0.4)
            for q, d, i in tips:                               # long yellowed nails, some split down the middle
                a, b = cam.proj(q), cam.proj(add(q, mul(d, 0.016 * h)))
                if min(a[2], b[2]) < 0.1:
                    continue
                fr.part(rig.capsule(a[:2], 0.0055 * h * a[3], b[:2], 0.0025 * h * b[3]), NAIL, ld,
                        width=0.011 * h * a[3], line=lw * 0.6, lit=0.2, dark=0.3)
                if i in (0, 2, 9):
                    m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                    fr.c.drawLine(a[0], a[1], m[0] + 0.002 * h * a[3], m[1], paint("#3a3226", stroke=max(0.6, lw * 0.35)))
        fn.side = s
        parts.append(("arm", zs - 0.001, fn))


def _noface(parts, fr, cam, J, p, ld, lw, out):
    p["noeyes"] = True                                         # cast.faces draws the eyes and the mouth
    p["nomouth"] = True


rig.LOOK.update({
    "mara": dict(h=1.78, skin=SKIN, hair="#121116", style="long", top=ROBE, pants=ROBE, shoes=HAND,
                 iris="#1c1210", build=0.80, brow=0.3, creep_style="MARA", arms_under_hair=True, no_nose_arc=True,
                 extras=(_noface, robe, hair.strands(n_back=30, length=0.62, width=0.017, tangle=1.0, fly=3),
                         faces.face(), claws)),
})
