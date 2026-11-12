"""Cast for THE MAN AT THE WINDOW v2 (designs: see the cast block below; own identity, Kuchisake quality bar).
  glass_hand an articulated right hand (palm, 4 fingers x 3 phalanges, thumb) that presses flat on the inside of the
             window: fingertips touch first, the palm flattens, pads blanch.
  shears     garden shears for the close insert, drawn in 3D in the fist's frame (blades, pivot bolt, red grips).
"""
import math
import random

import skia

import kit  # noqa: F401  (tools/toon + jeff + smilingman on the path)
import rig
import smiler as SM
from rig import Head, smooth
from toon import argb, lin, paint, rad, shade

SKIN = "#dcc89c"                                      # slightly yellow, waxy
LIP = "#a01822"
HAIR = "#1c1612"


# ---- the stranger: version A, softened: less scary, nothing grotesque ----------
def _run(Hd, cam, pts, lift=1.012):
    return SM._vis_run(Hd, cam, pts, lift=lift)


def _soft_stroke(c, pts, colr, w, a, blur):
    if len(pts) >= 2:
        c.drawPath(smooth(pts, closed=False), paint(colr, a=a, stroke=w, blur=blur))


STRANGER = dict(skin=SKIN, lip=LIP, smile=True, brow_col="#2a1e16", brow_w=0.035, bag_a=0.14, socket_a=0.10,
                strands=9, side_strands=False, contour=0.45, press=True)          # softened 2026-11-11: version A, less scary, nothing grotesque
DAD = dict(skin="#e2b48e", lip="#b06a5c", smile=False, brow_col="#3a281c", brow_w=0.055, bag_a=0.16, socket_a=0.14,
           strands=0, contour=0.55, press=False)
WIFE = dict(skin="#efc8a6", lip="#c27c72", smile=False, brow_col="#5a3820", brow_w=0.040, bag_a=0.06, socket_a=0.08,
            strands=0, contour=0.35, press=False)


def natural_face(cfg):
    """Face drawn on the head surface with natural contours. cfg: STRANGER (fixed broad smile, forehead press,
    tangled strands) or DAD (plain mouth that parts, worried brows). Pose keys: gx gy brow brow_in lid mouth mouth_w press."""
    SK = cfg["skin"]

    def extra(parts, fr, cam, J, p, ld, lw, out):
        R, Bh = J["R"], J["Bh"]
        Hd = Head(cam, J["head"], Bh, R)
        k = cam.proj(J["head"])[3]
        c = fr.c
        press = p.get("press", 0.0) if cfg["press"] else 0.0
        lx = 1.0 if ld[0] > 0 else -1.0                 # which screen side the light comes from
        ca = cfg["contour"]

        def face():
            rings = [(u * R, wa * R * 1.04, db * R * 0.97, 0, bo * R) for u, wa, db, ao, bo in rig.HEAD_RINGS]
            head, _ = rig.lathe(cam, J["head"], Bh, rings)
            c.save()
            c.clipPath(head, skia.ClipOp.kIntersect, True)
            dark = shade(SK, -0.55)
            # --- contours: temples, sockets, cheekbone hollows, jaw, chin ----------------------------------
            for sg in (-1, 1):
                q = _run(Hd, cam, [(sg * 0.62, 0.42), (sg * 0.72, 0.20), (sg * 0.74, -0.02)])
                _soft_stroke(c, q, dark, 0.16 * R * k, 0.22 * ca, 0.07 * R * k)
                q = _run(Hd, cam, [(sg * 0.22, -0.30), (sg * 0.50, -0.30), (sg * 0.70, -0.18)])
                _soft_stroke(c, q, dark, 0.10 * R * k, (0.20 if sg == lx else 0.30) * ca, 0.06 * R * k)
                q = _run(Hd, cam, [(sg * 0.30, 0.22), (sg * 0.52, 0.16), (sg * 0.58, -0.02)])
                _soft_stroke(c, q, dark, 0.08 * R * k, 0.18 * ca, 0.05 * R * k)
            q = _run(Hd, cam, [(-0.22, -0.80), (0.0, -0.86), (0.22, -0.80)])
            _soft_stroke(c, q, dark, 0.10 * R * k, 0.25 * ca, 0.06 * R * k)
            q = _run(Hd, cam, [(-0.10, -0.70), (0.0, -0.71), (0.10, -0.70)])
            _soft_stroke(c, q, shade(SK, 0.35), 0.06 * R * k, 0.35 * ca, 0.04 * R * k)
            for sg in (-1, 1):
                if Hd.facing(sg * 0.42, -0.22) > 0.15:
                    x, y = cam.proj(Hd.surf(sg * 0.42, -0.22, 1.01))[:2]
                    c.drawCircle(x, y, 0.16 * R * k, paint(shade(SK, 0.30), a=0.30 if sg == lx else 0.12, blur=0.07 * R * k))
                    c.drawCircle(x, y + 0.04 * R * k, 0.12 * R * k, paint("#c46a5a", a=0.10, blur=0.06 * R * k))
            # --- the forehead pressed on the glass: a slightly flattened, paler patch, the skin bunched below ---
            if press > 0 and Hd.facing(0.0, 0.47) > 0.1:
                c.save()
                c.concat(Hd.decal(0.0, 0.47, 1.005))
                o = skia.Rect(-0.27 * R, -0.11 * R, 0.27 * R, 0.10 * R)
                c.drawOval(o.makeOutset(0.05 * R, 0.04 * R), paint(shade(SK, -0.25), a=0.22 * press, blur=0.04 * R))
                c.drawOval(o, paint(shade(SK, 0.16), a=0.55 * press, blur=0.025 * R))
                c.drawOval(o.makeInset(0.07 * R, 0.035 * R), paint("#f2e6cc", a=0.22 * press, blur=0.03 * R))
                for i in (-1, 0, 1):
                    ln = skia.Path()
                    ln.moveTo(-0.20 * R, 0.15 * R + 0.03 * R * i)
                    ln.quadTo(0, 0.185 * R + 0.03 * R * i, 0.20 * R, 0.15 * R + 0.03 * R * i)
                    c.drawPath(ln, paint(shade(SK, -0.45), a=0.20 * press, stroke=0.010 * R, blur=0.004 * R))
                c.restore()
            # --- eyes: almond; the stranger's do NOT smile; the father's open wider as fear sets in ------------
            gx, gy = p.get("gx", 0.0), p.get("gy", 0.0)
            lid = p.get("lid", 0.92)
            brow, brow_in = p.get("brow", 0.0), p.get("brow_in", 0.0)
            for side, lam in ((-1, -0.38), (1, 0.38)):
                if Hd.facing(lam, 0.02) <= 0.10:
                    continue
                c.save()
                c.concat(Hd.decal(lam, 0.03))
                rx = 0.155 * R
                ry = 0.085 * R * (1.0 if cfg["smile"] else 0.82 + 1.3 * max(0.0, lid - 0.88))
                c.drawOval(skia.Rect(-rx * 1.6, -ry * 2.0, rx * 1.5, ry * 2.1), paint("#3a2618", a=cfg["socket_a"], blur=0.06 * R))
                bag = skia.Path()
                bag.moveTo(-rx * 0.9, ry * 1.25)
                bag.quadTo(0, ry * 2.4, rx * 1.0, ry * 1.1)
                c.drawPath(bag, paint("#4a3020", a=cfg["bag_a"], stroke=0.02 * R, blur=0.008 * R))
                if lid < 0.2:                                            # asleep: a lid of skin and a lash line
                    shut = skia.Path()
                    shut.moveTo(-rx, ry * 0.10)
                    shut.cubicTo(-rx * 0.55, -ry * 1.0, rx * 0.45, -ry * 1.1, rx, -ry * 0.05)
                    shut.quadTo(0, ry * 1.0, -rx, ry * 0.10)
                    c.drawPath(shut, paint(shade(SK, -0.10), blur=0.01 * R))
                    lash = skia.Path()
                    lash.moveTo(-rx * 0.95, ry * 0.12)
                    lash.quadTo(0, ry * 0.95, rx * 0.95, -ry * 0.02)
                    c.drawPath(lash, paint("#2a1a12", stroke=0.020 * R))
                else:
                    eye = skia.Path()
                    eye.moveTo(-rx, ry * 0.15)
                    eye.cubicTo(-rx * 0.55, -ry * 1.15, rx * 0.45, -ry * 1.25, rx, -ry * 0.05)
                    eye.cubicTo(rx * 0.5, ry * 1.05, -rx * 0.5, ry * 1.1, -rx, ry * 0.15)
                    eye.close()
                    c.drawPath(eye, paint("#ece4cf"))
                    c.save()
                    c.clipPath(eye, skia.ClipOp.kIntersect, True)
                    c.drawRect(skia.Rect(-rx, -ry * 1.3, rx, ry * 1.3), paint(shader=lin((0, -ry), (0, ry * 0.4), [argb("#8f7f6a", 0.85), argb("#ece4cf", 0.0)])))
                    ix, iy = gx * 0.09 * R, gy * 0.05 * R
                    ir = 0.070 * R
                    irc = ("#6a5236", "#4a3826", "#2a1e14") if cfg["smile"] else ("#7a5636", "#4e3622", "#2a1c12")
                    c.drawCircle(ix, iy, ir, paint(shader=rad((ix, iy), ir, [argb(irc[0]), argb(irc[1]), argb(irc[2])], [0, 0.6, 1])))
                    c.drawCircle(ix, iy, 0.026 * R, paint("#070505"))
                    c.drawCircle(ix - 0.022 * R, iy - 0.026 * R, 0.012 * R, paint("#fff6e6", a=0.85))
                    c.restore()
                    c.drawPath(eye, paint("#1c120e", stroke=0.010 * R))
                    lidp = skia.Path()
                    lidp.moveTo(-rx * 1.02, ry * 0.12)
                    lidp.cubicTo(-rx * 0.55, -ry * 1.2, rx * 0.45, -ry * 1.3, rx * 1.04, -ry * 0.08)
                    c.drawPath(lidp, paint("#140c0a", stroke=0.030 * R))
                    cr = skia.Path()
                    cr.moveTo(-rx * 0.85, -ry * 0.95 - 0.02 * R)
                    cr.cubicTo(-rx * 0.4, -ry * 2.0 - 0.02 * R, rx * 0.5, -ry * 2.0 - 0.02 * R, rx * 0.95, -ry * 0.9 - 0.02 * R)
                    c.drawPath(cr, paint("#4a3020", a=0.55, stroke=0.012 * R))
                c.restore()
                # brows: the stranger's thin and level (calm); the father's rise and knit inward (-brow = worried)
                c.save()
                c.concat(Hd.decal(lam * 1.06, 0.27))
                up = -0.05 * R * max(0.0, -brow)                         # decal y grows downward
                inn = -0.06 * R * max(0.0, -brow_in)
                b = skia.Path()
                bw = cfg["brow_w"] * R
                outer, inner = (side * 0.22 * R, up + 0.01 * R), (-side * 0.20 * R, up + inn + 0.01 * R)
                b.moveTo(*inner)
                b.quadTo(side * 0.02 * R, up + inn * 0.5 - 0.045 * R, *outer)
                c.drawPath(b, paint(cfg["brow_col"], stroke=bw, a=0.9))
                if not cfg["smile"]:
                    c.drawPath(b, paint(cfg["brow_col"], stroke=bw * 1.6, a=0.25, blur=bw * 0.4))
                    if brow_in < -0.1:                                    # a worry line between the brows
                        for sg in (-1, 1):
                            pass
                c.restore()
            if not cfg["smile"] and brow_in < -0.1 and Hd.facing(0.0, 0.32) > 0.1:
                c.save()
                c.concat(Hd.decal(0.0, 0.32))
                for sg in (-0.035, 0.035):
                    ln = skia.Path()
                    ln.moveTo(sg * R, 0.04 * R)
                    ln.quadTo(sg * 1.3 * R, -0.02 * R, sg * R, -0.07 * R)
                    c.drawPath(ln, paint(shade(SK, -0.4), a=0.28 * min(1.0, -brow_in / 0.5), stroke=0.008 * R, blur=0.005 * R))
                c.restore()
            # --- nose ---------------------------------------------------------------------------------------
            if Hd.facing(0.0, -0.16) > 0.05:
                q = _run(Hd, cam, [(-lx * 0.10, 0.14), (-lx * 0.12, 0.0), (-lx * 0.15, -0.12)])
                _soft_stroke(c, q, dark, 0.05 * R * k, 0.35, 0.03 * R * k)
                c.save()
                c.concat(Hd.decal(0.0, -0.18, 1.04))
                c.drawOval(skia.Rect(-0.08 * R, -0.07 * R, 0.08 * R, 0.07 * R), paint(shade(SK, -0.25), a=0.45, blur=0.025 * R))
                c.drawOval(skia.Rect(-0.04 * R + lx * 0.02 * R, -0.06 * R, 0.03 * R + lx * 0.02 * R, -0.01 * R), paint("#fff4dc", a=0.45, blur=0.012 * R))
                for sg in (-1, 1):
                    c.drawOval(skia.Rect(sg * 0.075 * R - 0.032 * R, 0.035 * R, sg * 0.075 * R + 0.032 * R, 0.07 * R), paint("#2a1610", a=0.75))
                    al = skia.Path()
                    al.moveTo(sg * 0.11 * R, -0.04 * R)
                    al.quadTo(sg * 0.16 * R, 0.02 * R, sg * 0.11 * R, 0.07 * R)
                    c.drawPath(al, paint(shade(SK, -0.5), stroke=0.016 * R, a=0.7))
                c.restore()
            if cfg["smile"]:
                _smile(c, Hd, cam, R, k, SK)
            else:
                _mouth(c, Hd, cam, R, k, SK, cfg["lip"], p.get("mouth", 0.0), p.get("mouth_w", 0.0))
            # --- tangled strands over the forehead, some pressed flat on the glass ---------------------------
            rnd = random.Random(11)
            for i in range(cfg["strands"]):
                a0 = rnd.uniform(-0.80, 0.80)
                mu0 = 0.66 + rnd.uniform(-0.03, 0.06)
                mu1 = rnd.uniform(0.34, 0.56) if abs(a0) < 0.45 else rnd.uniform(0.10, 0.36)
                if abs(a0) < 0.22 and press > 0:
                    mu1 = max(mu1, 0.50)                    # clear of the press patch
                pts = []
                for j in range(7):
                    u = j / 6
                    pts.append((a0 + 0.025 * math.sin(u * 3.0 + i) + rnd.uniform(-0.008, 0.008) + 0.10 * u * (1 if a0 > 0 else -1),
                                mu0 + (mu1 - mu0) * u))
                q = _run(Hd, cam, pts, lift=1.02)
                if len(q) > 2:
                    w = rnd.uniform(0.012, 0.024) * R * k
                    c.drawPath(smooth(q, closed=False), paint(HAIR, stroke=w * 1.8, a=0.25, blur=w * 0.6))
                    c.drawPath(smooth(q, closed=False), paint(HAIR, stroke=w, a=0.92))
                    c.drawPath(smooth(q, closed=False), paint("#5a4a3c", stroke=w * 0.25, a=0.35))
            c.restore()
            # lank strands down the side hair (over the hair cap, not clipped to the face)
            if cfg["strands"] and cfg.get("side_strands", True):
                rs = random.Random(3)
                for i in range(14):
                    lam = rs.choice((-1, 1)) * rs.uniform(0.85, 1.75)
                    pts = [(lam * (1 + 0.04 * j) + rs.uniform(-0.01, 0.01), 1.05 - 0.26 * j) for j in range(7)]
                    q = [cam.proj(Hd.surf(a, b, 1.075))[:2] for a, b in pts if Hd.facing(a, b) > -0.05]
                    if len(q) > 2:
                        c.drawPath(smooth(q, closed=False), paint(rs.choice(("#3a3028", "#0c0a08")), stroke=rs.uniform(0.008, 0.016) * R * k, a=0.35))

        parts.append(("face", J["head"][2], face))
    return extra


def _smile(c, Hd, cam, R, k, SK):
    """The stranger's smile: very broad, fixed; red lips, a thin line of teeth, no fangs."""
    if Hd.facing(0.0, -0.47) <= -0.05:
        return
    for sg in (-1, 1):                                                             # nasolabial folds, deepened
        q = _run(Hd, cam, [(sg * 0.17, -0.25), (sg * 0.40, -0.34), (sg * 0.62, -0.46), (sg * 0.70, -0.58)])
        _soft_stroke(c, q, shade(SK, -0.5), 0.025 * R * k, 0.22, 0.01 * R * k)
        _soft_stroke(c, q, shade(SK, -0.45), 0.08 * R * k, 0.07, 0.04 * R * k)
    n, W = 29, 0.54
    lams = [-W + 2 * W * i / (n - 1) for i in range(n)]
    upr = [(a, -0.44 + 0.13 * (a / W) ** 2) for a in lams]
    top = [(a, mu + 0.035 * max(0.0, 1 - (a / W) ** 2) + 0.012 - 0.012 * abs(a / W)) for a, mu in upr]
    bot = [(a, mu - 0.07 * max(0.0, 1 - (a / W) ** 4)) for a, mu in upr]
    op = [(a, mu - 0.03 * max(0.0, 1 - (a / W) ** 2)) for a, mu in upr]
    T, U, D, O = _run(Hd, cam, top), _run(Hd, cam, upr), _run(Hd, cam, bot), _run(Hd, cam, op)
    if min(len(T), len(D), len(U), len(O)) <= 3:
        return
    lips = smooth(T + D[::-1], k=0.5)
    c.drawPath(lips, paint(LIP))
    c.save()
    c.clipPath(lips, skia.ClipOp.kIntersect, True)
    c.drawPath(lips, paint(shader=lin(T[len(T) // 2], D[len(D) // 2], [argb(shade(LIP, -0.35)), argb(LIP), argb(shade(LIP, 0.2))], [0, 0.5, 1])))
    c.drawPath(smooth(U + O[::-1], k=0.5), paint("#e9dfcb"))
    c.drawPath(smooth(O, closed=False), paint("#3a1012", stroke=0.012 * R * k))
    for i in range(1, 8):
        a = -0.30 + 0.6 * i / 8
        q = _run(Hd, cam, [(a, -0.44 + 0.13 * (a / W) ** 2), (a, -0.44 + 0.13 * (a / W) ** 2 - 0.026)])
        if len(q) == 2:
            pass                                                                  # (tooth dividers dropped: softer)
    lo = len(D) // 2
    c.drawCircle(D[lo][0], D[lo][1] - 0.02 * R * k, 0.05 * R * k, paint("#f6c0b8", a=0.35, blur=0.02 * R * k))
    c.restore()
    c.drawPath(smooth(U, closed=False), paint("#2a0608", stroke=0.016 * R * k))
    c.drawPath(lips, paint(shade(LIP, -0.55), stroke=0.010 * R * k))
    for sg in (-1, 1):
        q = _run(Hd, cam, [(sg * W * 0.97, -0.44 + 0.13), (sg * W * 1.06, -0.44 + 0.08), (sg * W * 1.08, -0.52)])
        _soft_stroke(c, q, shade(SK, -0.5), 0.018 * R * k, 0.3, 0.005 * R * k)


def _mouth(c, Hd, cam, R, k, SK, lip, mouth, mouth_w):
    """An ordinary closed mouth; mouth 0..0.3 parts the lips (dark gap, a hint of upper teeth)."""
    if Hd.facing(0.0, -0.47) <= -0.05:
        return
    for sg in (-1, 1):                                                             # light nasolabial folds
        q = _run(Hd, cam, [(sg * 0.16, -0.24), (sg * 0.30, -0.36), (sg * 0.38, -0.50)])
        _soft_stroke(c, q, shade(SK, -0.45), 0.06 * R * k, 0.18, 0.03 * R * k)
    n, W = 21, 0.30 * (1 + 0.35 * mouth_w)
    op = min(1.0, mouth / 0.3) * 0.075
    lams = [-W + 2 * W * i / (n - 1) for i in range(n)]
    seam = [(a, -0.45 - 0.012 * (a / W) ** 2) for a in lams]                        # corners a touch down: tense
    upr = [(a, mu + op * 0.25 * max(0.0, 1 - (a / W) ** 2)) for a, mu in seam]
    lwr = [(a, mu - op * 0.75 * max(0.0, 1 - (a / W) ** 2)) for a, mu in seam]
    top = [(a, mu + 0.028 * max(0.0, 1 - (a / W) ** 2)) for a, mu in upr]
    bot = [(a, mu - 0.045 * max(0.0, 1 - (a / W) ** 4)) for a, mu in lwr]
    T, U, L2, D = _run(Hd, cam, top), _run(Hd, cam, upr), _run(Hd, cam, lwr), _run(Hd, cam, bot)
    if min(len(T), len(U), len(L2), len(D)) <= 3:
        return
    c.drawPath(smooth(T + U[::-1], k=0.5), paint(shade(lip, -0.12), a=0.85))        # upper lip
    c.drawPath(smooth(L2 + D[::-1], k=0.5), paint(lip, a=0.85))                     # lower lip
    if op > 0.004:
        gap = smooth(U + L2[::-1], k=0.5)
        c.drawPath(gap, paint("#2a0e0c"))
        c.save()
        c.clipPath(gap, skia.ClipOp.kIntersect, True)
        tt = _run(Hd, cam, [(a, mu - 0.022) for a, mu in upr[3:-3]])
        if len(tt) > 2:
            c.drawPath(smooth(U[3:-3] + tt[::-1], k=0.5), paint("#d8cdb8", a=0.8))
        c.restore()
    c.drawPath(smooth(U, closed=False), paint(shade(lip, -0.6), stroke=0.012 * R * k))
    lo = len(D) // 2
    c.drawCircle(D[lo][0], D[lo][1] - 0.015 * R * k, 0.04 * R * k, paint(shade(lip, 0.35), a=0.3, blur=0.02 * R * k))
    q = _run(Hd, cam, [(-0.12, -0.60), (0.0, -0.62), (0.12, -0.60)])               # chin crease below the lip
    _soft_stroke(c, q, shade(SK, -0.4), 0.03 * R * k, 0.25, 0.02 * R * k)


stranger_face = natural_face(STRANGER)


def stubble(parts, fr, cam, J, p, ld, lw, out):
    """Five o'clock shadow: jaw wash plus fine speckle."""
    R, Bh = J["R"], J["Bh"]
    shp = rig.LOOK[J["look"]].get("head_shape")
    Hd = Head(cam, J["head"], Bh, R, shp)
    k = cam.proj(J["head"])[3]

    def face():
        c = fr.c
        head, _ = rig.lathe(cam, J["head"], Bh, rig.head_rings(R, shp))
        loop = ([(-1.2, 0.08), (-1.0, -0.12), (-0.72, -0.28), (-0.42, -0.36), (-0.15, -0.38), (0.0, -0.37), (0.15, -0.38),
                 (0.42, -0.36), (0.72, -0.28), (1.0, -0.12), (1.2, 0.08)] +
                [(1.45, -0.3), (1.1, -1.2), (0.0, -1.5), (-1.1, -1.2), (-1.45, -0.3)])
        pts = [cam.proj(Hd.surf(a, b, 1.01))[:2] for a, b in loop if Hd.facing(a, b) > -0.3]
        if len(pts) < 4:
            return
        c.save()
        c.clipPath(head, skia.ClipOp.kIntersect, True)
        c.drawPath(smooth(pts, k=0.4), paint("#2a2422", a=0.22, blur=0.06 * R * k))      # a soft shadow, no speckle
        c.restore()

    parts.append(("face", J["head"][2] + 1e-4, face))



def _vis_run(Hd, cam, pts_lm, lift=1.012, thr=0.04):
    """Head-surface points (lam, mu) projected, keeping the longest visible run."""
    best, cur = [], []
    for lam, mu in pts_lm:
        if Hd.facing(lam, mu) > thr:
            cur.append(cam.proj(Hd.surf(lam, mu, lift))[:2])
        else:
            best, cur = (cur if len(cur) > len(best) else best), []
    return cur if len(cur) > len(best) else best

# ---- the cast: own designs for this story ---------------------
# Kuchisake-onna is the quality bar only (clean matte shapes, stable proportions, expressive faces); nothing here
# reuses her face, hair or palette. Each face is drawn on its own head shape (rig look "head_shape").
#   stranger  very tall and narrow: a long egg-shaped head, a high bare forehead under thin tangled ash-brown hair,
#             small close-set eyes with pinprick pupils under flat heavy lids (they never blink or smile), a long thin
#             nose, and a broad CLOSED red-lipped smile that bunches his cheeks up into round apples. Mustard cardigan
#             buttoned to the collar. Personality: an over-polite neighbour who has been standing there for hours.
#   dad       broad and solid: a square jaw, thick straight brows, warm brown almond eyes, a broad rounded nose,
#             stubble, short side-parted brown hair, olive work jacket.
#   wife      soft and round: a rounded face with a small chin, long lashes, a small nose, a few freckles,
#             auburn hair; seen asleep.

def _cubic(p0, p1, p2, p3):
    s = skia.Path()
    s.moveTo(*p0)
    s.cubicTo(*p1, *p2, *p3)
    return s


CAST = {
    "stranger": dict(eye_lam=0.28, eye_mu=0.10, eye_rx=0.13, eye_ry=0.105, white="#f2eedc", iris="#7a6a48", pupil=0.030,
                     lid_flat=0.40, lid_w=0.030, brow_col="#4a4036", brow_w=0.022, brow_mu=0.36, brow_arch=0.07,
                     brow_lift=0.03, nose="long", mouth="smile", lash=False, bag=0.2, freckles=0, cheeks=1.0),
    "dad": dict(eye_lam=0.36, eye_mu=0.05, eye_rx=0.15, eye_ry=0.105, white="#f6f3ea", iris="#6b4a2e", pupil=0.036,
                lid_flat=0.15, lid_w=0.030, brow_col="#3a2a1e", brow_w=0.060, brow_mu=0.30, brow_arch=0.025,
                brow_lift=0.0, nose="broad", mouth="plain", lash=False, bag=0.0, freckles=0, cheeks=0.0),
    "wife": dict(eye_lam=0.37, eye_mu=0.02, eye_rx=0.15, eye_ry=0.12, white="#f8f5ee", iris="#5a7a5a", pupil=0.034,
                 lid_flat=0.0, lid_w=0.026, brow_col="#6b3f24", brow_w=0.030, brow_mu=0.29, brow_arch=0.05,
                 brow_lift=0.0, nose="button", mouth="small", lash=True, bag=0.0, freckles=9, cheeks=0.35),
}


def cast_face(name):
    """LOOK extra drawing one of CAST's faces on the head surface (the rig face is off: look face="custom").
    Pose keys: gx gy (gaze), lid (1 open .. 0 shut), brow (+ raises), brow_in (- worried, + angry),
    mouth (0..0.3 parts the lips), mouth_w, press (stranger: forehead on the glass)."""
    cfg = CAST[name]

    def extra(parts, fr, cam, J, p, ld, lw, out):
        L = rig.LOOK[J["look"]]
        R, Bh = J["R"], J["Bh"]
        Hd = Head(cam, J["head"], Bh, R, L.get("head_shape"))
        k = cam.proj(J["head"])[3]
        c = fr.c
        SK = L["skin"]
        line = shade(SK, -0.72)
        lx = 1.0 if ld[0] > 0 else -1.0
        gx, gy = p.get("gx", 0.0), p.get("gy", 0.0)
        lid = max(0.0, min(1.0, p.get("lid", 1.0)))
        brow, brow_in = p.get("brow", 0.0), p.get("brow_in", 0.0)

        def onface(lam, mu, thr=0.10):
            return Hd.facing(lam, mu) > thr

        def eyes():
            for side, lam in ((-1, -cfg["eye_lam"]), (1, cfg["eye_lam"])):
                if not onface(lam, cfg["eye_mu"], 0.12):
                    continue
                c.save()
                c.concat(Hd.decal(lam, cfg["eye_mu"]))
                rx, ry = cfg["eye_rx"] * R, cfg["eye_ry"] * R
                if cfg["bag"]:                                       # a clean grey-violet crescent under each eye
                    bag = skia.Path()
                    bag.moveTo(-rx * 1.05, ry * 0.55)
                    bag.quadTo(0, ry * 2.25, rx * 1.05, ry * 0.55)
                    bag.quadTo(0, ry * 1.45, -rx * 1.05, ry * 0.55)
                    c.drawPath(bag, paint("#8c7a86", a=0.45 * cfg["bag"], blur=0.012 * R))
                if lid < 0.15:                                       # shut: one curved lash line, lashes on the wife
                    sh = skia.Path()
                    sh.moveTo(-rx, 0)
                    sh.quadTo(0, ry * 0.85, rx, 0)
                    c.drawPath(sh, paint(line, stroke=0.026 * R))
                    if cfg["lash"]:
                        for t in (0.25, 0.5, 0.75):
                            x = -rx + 2 * rx * t
                            y = ry * 0.85 * 2 * t * (1 - t) * 1.0
                            c.drawLine(x, y, x + side * 0.02 * R, y + 0.045 * R, paint(line, stroke=0.012 * R))
                    c.restore()
                    continue
                eye = skia.Path()
                eye.moveTo(-rx, 0)
                eye.cubicTo(-rx * 0.6, -ry * 1.35, rx * 0.6, -ry * 1.35, rx, 0)
                eye.cubicTo(rx * 0.6, ry * 1.25, -rx * 0.6, ry * 1.25, -rx, 0)
                eye.close()
                c.drawPath(eye, paint(cfg["white"]))
                c.save()
                c.clipPath(eye, skia.ClipOp.kIntersect, True)
                ix, iy = gx * 0.07 * R, -gy * 0.05 * R
                if cfg["iris"]:
                    ir = 0.072 * R
                    c.drawCircle(ix, iy, ir, paint(shader=rad((ix, iy - ir * 0.3), ir * 1.2,
                                                              [argb(shade(cfg["iris"], 0.3)), argb(cfg["iris"]), argb(shade(cfg["iris"], -0.45))], [0, 0.55, 1])))
                c.drawCircle(ix, iy, cfg["pupil"] * R, paint("#0d0a0a"))
                c.drawCircle(ix - 0.022 * R, iy - 0.024 * R, 0.014 * R, paint("#ffffff", a=0.9 if cfg["iris"] else 0.55))
                # the upper lid: lid 1 = open; lid_flat lowers a straight heavy lid over the top of the eye (the stare)
                top = -ry * 1.3 + (1.0 - lid) * ry * 2.3 + cfg["lid_flat"] * ry * 0.9
                lp = skia.Path()
                lp.moveTo(-rx * 1.3, -ry * 2.0)
                lp.lineTo(rx * 1.3, -ry * 2.0)
                lp.lineTo(rx * 1.3, top + side * brow_in * 0.0)
                lp.quadTo(0, top + ry * 0.25 * (1 - cfg["lid_flat"]), -rx * 1.3, top)
                lp.close()
                c.drawPath(lp, paint(shade(SK, -0.10)))
                c.drawRect(skia.Rect(-rx, top, rx, top + ry * 0.45), paint("#000000", a=0.18, blur=0.02 * R))
                c.restore()
                c.drawPath(eye, paint(line, stroke=0.012 * R))
                # upper lid line (heavier) along the lid edge, clipped to the eye opening
                ln = skia.Path()
                yt = max(top, -ry * 1.0)
                ln.moveTo(-rx * 1.02, min(0.0, yt + ry * 0.9) if lid < 0.5 else -ry * 0.05)
                ln.quadTo(0, yt - (0.25 * ry if cfg["lid_flat"] < 0.3 else 0.0), rx * 1.04, min(0.0, yt + ry * 0.9) if lid < 0.5 else -ry * 0.08)
                c.drawPath(ln, paint(line, stroke=cfg["lid_w"] * R))
                if cfg["lash"]:
                    c.drawLine(side * rx * 0.95, -ry * 0.15, side * rx * 1.25, -ry * 0.55, paint(line, stroke=0.018 * R))
                c.restore()

        def brows():
            for side, lam in ((-1, -cfg["eye_lam"] * 1.05), (1, cfg["eye_lam"] * 1.05)):
                if not onface(lam, cfg["brow_mu"], 0.12):
                    continue
                c.save()
                c.concat(Hd.decal(lam, cfg["brow_mu"]))
                up = -(0.05 * brow + cfg["brow_lift"]) * R               # decal y grows downward
                inner_dy = 0.05 * R * brow_in                             # + angry: inner end down; - worried: up
                w = cfg["brow_w"] * R
                inner = (-side * 0.15 * R, up + inner_dy)
                outer = (side * 0.17 * R, up + 0.01 * R)
                mid = (side * 0.01 * R, up - cfg["brow_arch"] * R + inner_dy * 0.4)
                b = skia.Path()
                b.moveTo(*inner)
                b.quadTo(*mid, *outer)
                c.drawPath(b, paint(cfg["brow_col"], stroke=w))
                c.restore()
            if brow_in < -0.15 and onface(0.0, cfg["brow_mu"] - 0.02):   # two short worry marks between the brows
                c.save()
                c.concat(Hd.decal(0.0, cfg["brow_mu"] - 0.02))
                for sg in (-1, 1):
                    m = skia.Path()
                    m.moveTo(sg * 0.035 * R, 0.035 * R)
                    m.quadTo(sg * 0.045 * R, 0.0, sg * 0.03 * R, -0.04 * R)
                    c.drawPath(m, paint(line, a=0.5 * min(1.0, -brow_in / 0.5), stroke=0.010 * R))
                c.restore()

        def nose():
            if not onface(0.0, -0.10, 0.05):
                return
            kind = cfg["nose"]
            if kind == "long":                                       # a long narrow wedge down the face, shaded on one side
                c.save()
                c.concat(Hd.decal(0.0, -0.08, 1.03))
                w = skia.Path()
                w.moveTo(-lx * 0.02 * R, -0.10 * R)
                w.quadTo(-lx * 0.06 * R, 0.0, -lx * 0.07 * R, 0.13 * R)
                w.quadTo(0.0, 0.19 * R, lx * 0.06 * R, 0.13 * R)
                c.drawPath(w, paint(line, stroke=0.016 * R, a=0.9))
                sh = skia.Path(w)
                sh.close()
                c.drawPath(sh, paint(shade(SK, -0.22), a=0.35, blur=0.015 * R))
                c.drawOval(skia.Rect(-0.03 * R, 0.07 * R, 0.03 * R, 0.12 * R), paint("#ffffff", a=0.28, blur=0.01 * R))
                c.restore()
            elif kind == "broad":                                    # a broad rounded bulb with two small nostrils
                c.save()
                c.concat(Hd.decal(0.0, -0.17, 1.04))
                c.drawOval(skia.Rect(-0.12 * R, -0.08 * R, 0.12 * R, 0.08 * R), paint(shade(SK, -0.16)))
                c.drawOval(skia.Rect(-0.12 * R, -0.08 * R, 0.12 * R, 0.08 * R), paint(line, stroke=0.012 * R, a=0.7))
                c.drawOval(skia.Rect(-0.06 * R, -0.06 * R, 0.02 * R, -0.01 * R), paint("#ffffff", a=0.35, blur=0.012 * R))
                for sg in (-1, 1):
                    c.drawOval(skia.Rect(sg * 0.05 * R - 0.022 * R, 0.03 * R, sg * 0.05 * R + 0.022 * R, 0.06 * R), paint("#2a1812", a=0.7))
                c.restore()
            else:                                                    # a small button tip
                c.save()
                c.concat(Hd.decal(0.0, -0.15, 1.03))
                arc = skia.Path()
                arc.moveTo(-0.055 * R, 0.0)
                arc.quadTo(0.0, 0.07 * R, 0.055 * R, 0.0)
                c.drawPath(arc, paint(line, stroke=0.014 * R, a=0.8))
                c.drawOval(skia.Rect(-0.03 * R, -0.05 * R, 0.02 * R, -0.01 * R), paint("#ffffff", a=0.3, blur=0.01 * R))
                c.restore()

        def mouth():
            if not onface(0.0, -0.48, -0.05):
                return
            if cfg["mouth"] == "smile":
                _closed_smile(fr, c, Hd, cam, R, k, SK, ld, lw)
                return
            m, mw = p.get("mouth", 0.0), p.get("mouth_w", 0.0)
            W = (0.24 if cfg["mouth"] == "plain" else 0.17) * (1 + 0.35 * mw)
            mu0 = -0.40 if cfg["mouth"] == "plain" else -0.45
            op = min(1.0, m / 0.3) * 0.07
            n = 15
            lams = [-W + 2 * W * i / (n - 1) for i in range(n)]
            up = _vis_run(Hd, cam, [(a, mu0 + 0.2 * op * max(0.0, 1 - (a / W) ** 2)) for a in lams])
            dn = _vis_run(Hd, cam, [(a, mu0 - op * max(0.0, 1 - (a / W) ** 2)) for a in lams])
            if len(up) < 3:
                return
            if op > 0.004 and len(dn) == len(up):
                gap = smooth(up + dn[::-1], k=0.5)
                c.drawPath(gap, paint("#3a1412"))
                c.save()
                c.clipPath(gap, skia.ClipOp.kIntersect, True)
                c.drawPath(smooth(up, closed=False), paint("#efe9dc", stroke=0.03 * R * k))
                c.restore()
            c.drawPath(smooth(up, closed=False), paint(line, stroke=0.016 * R * k))
            lo = _vis_run(Hd, cam, [(-W * 0.5, mu0 - 0.07 - op), (0.0, mu0 - 0.085 - op), (W * 0.5, mu0 - 0.07 - op)])
            if len(lo) == 3:                                         # lower-lip hint
                c.drawPath(smooth(lo, closed=False), paint(shade(SK, -0.35), stroke=0.014 * R * k, a=0.55))

        def extras_skin():
            if cfg["freckles"]:
                rnd = random.Random(5)
                for i in range(cfg["freckles"]):
                    sg = 1 if i % 2 else -1
                    lam, mu = sg * rnd.uniform(0.18, 0.42), rnd.uniform(-0.20, -0.06)
                    if onface(lam, mu):
                        x, y = cam.proj(Hd.surf(lam, mu, 1.01))[:2]
                        c.drawCircle(x, y, 0.011 * R * k, paint("#a8603e", a=0.55))
            if cfg["cheeks"]:
                for sg in (-1, 1):
                    if onface(sg * 0.44, -0.24):
                        x, y = cam.proj(Hd.surf(sg * 0.44, -0.24, 1.01))[:2]
                        c.drawCircle(x, y, 0.15 * R * k, paint("#d9826e", a=0.12 * cfg["cheeks"], blur=0.06 * R * k))

        def draw():
            head = rig.lathe(cam, J["head"], Bh, rig.head_rings(R, L.get("head_shape")))[0]
            c.save()
            c.clipPath(head, skia.ClipOp.kIntersect, True)
            extras_skin()
            if name == "stranger":
                _press_patch(c, Hd, R, SK, p.get("press", 0.0))
            eyes()
            brows()
            nose()
            mouth()
            c.restore()

        parts.append(("face", J["head"][2], draw))
    return extra


def _press_patch(c, Hd, R, SK, press):
    """The forehead flattened on the glass: a pale flat oval, the skin bunched in two soft folds under it."""
    if press <= 0 or Hd.facing(0.0, 0.52) < 0.1:
        return
    c.save()
    c.concat(Hd.decal(0.0, 0.52, 1.005))
    c.drawOval(skia.Rect(-0.30 * R, -0.12 * R, 0.30 * R, 0.11 * R), paint(shade(SK, 0.18), a=0.55 * press, blur=0.025 * R))
    for i in (0, 1):
        f = skia.Path()
        f.moveTo(-0.20 * R, 0.15 * R + 0.035 * R * i)
        f.quadTo(0, 0.19 * R + 0.035 * R * i, 0.20 * R, 0.15 * R + 0.035 * R * i)
        c.drawPath(f, paint(shade(SK, -0.45), a=0.30 * press, stroke=0.012 * R))
    c.restore()


def _closed_smile(fr, c, Hd, cam, R, k, SK, ld, lw):
    """The stranger's smile: broad and closed, full red lips pressed together, the corners curling up into round
    cheek apples. No teeth, no slit to the ears, no open mouth."""
    A = 0.48
    n = 25
    lams = [-A + 2 * A * i / (n - 1) for i in range(n)]
    mid = lambda a: -0.49 + 0.14 * (a / A) ** 2                                  # noqa: E731
    fat = lambda a: max(0.0, 1 - (a / A) ** 2) ** 0.6                            # noqa: E731
    U = _vis_run(Hd, cam, [(a, mid(a) + 0.007 + 0.034 * fat(a)) for a in lams])
    D = _vis_run(Hd, cam, [(a, mid(a) - 0.007 - 0.052 * fat(a)) for a in lams])
    S = _vis_run(Hd, cam, [(a, mid(a)) for a in lams])
    if len(U) < 3 or len(D) < 3:
        return
    for sg in (-1, 1):                                                          # cheek apples pushed up by the smile
        if Hd.facing(sg * 0.50, -0.26) > 0.1:
            x, y = cam.proj(Hd.surf(sg * 0.50, -0.26, 1.01))[:2]
            c.drawCircle(x, y, 0.15 * R * k, paint(shade(SK, 0.22), a=0.35, blur=0.05 * R * k))
            c.drawCircle(x, y + 0.03 * R * k, 0.12 * R * k, paint("#d07a62", a=0.12, blur=0.05 * R * k))
        q = _vis_run(Hd, cam, [(sg * 0.20, -0.20), (sg * 0.40, -0.30), (sg * (A + 0.04), mid(A) + 0.05)])
        if len(q) == 3:                                                         # the crease from the nose to the corner
            c.drawPath(smooth(q, closed=False), paint(shade(SK, -0.42), stroke=0.016 * R * k, a=0.45))
        q = _vis_run(Hd, cam, [(sg * (A - 0.01), mid(A) + 0.03), (sg * (A + 0.05), mid(A) - 0.01), (sg * (A + 0.03), mid(A) - 0.05)])
        if len(q) == 3:                                                         # a little dimple curl at each corner
            c.drawPath(smooth(q, closed=False), paint(shade(SK, -0.5), stroke=0.014 * R * k, a=0.8))
    lips = smooth(U + D[::-1], k=0.5)
    fr.part(lips, "#b23a40", ld, width=0.2 * R * k, line=max(1.0, lw * 0.7), lit=0.18, dark=0.30)
    if len(S) > 2:
        c.drawPath(smooth(S, closed=False), paint("#3a0a0c", stroke=0.016 * R * k))
    lo = len(D) // 2
    c.drawOval(skia.Rect(D[lo][0] - 0.07 * R * k, D[lo][1] - 0.045 * R * k, D[lo][0] + 0.07 * R * k, D[lo][1] - 0.015 * R * k),
               paint("#ffffff", a=0.22, blur=0.012 * R * k))


rig.LOOK.update({
    "stranger": dict(h=1.88, skin=SKIN, hair=HAIR, style="lank", mu_front=0.62, hair_mesh=True, top="#6b5a44",
                     pants="#2c2a28", shoes="#151417", iris="#3a2a1e", build=0.82, brow=0.0, head=0.86, face="custom", neck_shade=-0.58,
                     extras=(stranger_face,)),
    "dad": dict(h=1.80, skin="#e2b48e", hair="#4a3626", style="short", top="#5b6648", pants="#3b4a63",
                shoes="#3a2a1e", iris="#6b4a2e", build=1.10, brow=1.0, face="custom", head_shape=(1.0, 1.0, 0.0),
                neck_shade=-0.40, extras=(stubble, cast_face("dad"))),
    "wife": dict(h=1.66, skin="#efc8a6", hair="#9a4a26", style="neat", top="#b8868a", pants="#b8868a",
                 shoes="#d9c7b8", iris="#5a7a5a", build=0.9, brow=0.7, face="custom", head_shape=(0.98, 1.0, -0.10),
                 extras=(cast_face("wife"),)),
})


# ---- the hand on the glass ---------------------------------------------------------------------------------
FINGERS = [  # base offset along r (thumb side negative), along u, segment lengths, spread angle (deg) at s=1
    (-0.031, 0.000, (0.042, 0.025, 0.020), -13.0, 0.0095),
    (-0.010, 0.006, (0.047, 0.029, 0.021), -3.0, 0.0100),
    (0.011, 0.002, (0.044, 0.027, 0.020), 7.0, 0.0095),
    (0.030, -0.010, (0.034, 0.021, 0.018), 18.0, 0.0085),
]


def _rot_in_plane(u, r, deg):
    a = math.radians(deg)
    return rig.norm(rig.add(rig.mul(u, math.cos(a)), rig.mul(r, math.sin(a))))


def hand_points(wrist, u, n, spread=1.0, curl=0.0):
    """3D chains of the right hand: returns (palm corners, [finger chains], thumb chain, radii). u = finger direction,
    n = out of the palm (toward the glass), r = toward the pinky."""
    r = rig.norm(rig.cross(u, n))
    P = lambda a, b, c_=0.0: rig.add(wrist, rig.mul(r, a), rig.mul(u, b), rig.mul(n, c_))       # noqa: E731
    palm = [P(-0.040, 0.012), P(-0.044, 0.060), P(-0.036, 0.092), P(0.040, 0.088), P(0.044, 0.050), P(0.038, 0.010), P(0.0, -0.004)]
    chains = []
    for dr, du, segs, sp, rad_ in FINGERS:
        d = _rot_in_plane(u, r, sp * spread)
        pt = P(dr, 0.088 + du)
        ch = [pt]
        bend = 0.0
        for i, L in enumerate(segs):
            bend += curl * (22.0 + 14.0 * i)                                   # each joint curls a little more
            b = math.radians(bend)
            dd = rig.norm(rig.add(rig.mul(d, math.cos(b)), rig.mul(n, math.sin(b))))
            pt = rig.add(pt, rig.mul(dd, L))
            ch.append(pt)
        chains.append((ch, rad_))
    td = _rot_in_plane(u, r, -(30.0 + 16.0 * spread))       # out ~45 deg from the fingers, not along the forearm
    tb = P(-0.036, 0.026)
    thumb = [tb]
    pt = tb
    for i, L in enumerate((0.034, 0.026, 0.019)):
        b = math.radians(curl * 18.0 * i)
        dd = rig.norm(rig.add(rig.mul(td, math.cos(b)), rig.mul(n, math.sin(b) * 0.6)))
        pt = rig.add(pt, rig.mul(dd, L))
        thumb.append(pt)
    return palm, chains, (thumb, 0.0135)


def draw_glass_hand(fr, cam, wrist, u, n, spread, curl, press, light=(0.4, 1.0)):
    """Draw the palm-forward hand (seen through the glass from outside). Returns the hand outline path."""
    palm, chains, thumb = hand_points(wrist, u, n, spread, curl)
    pr = lambda q: cam.proj(q)                                                 # noqa: E731
    k = pr(wrist)[3]
    pp = [pr(q)[:2] for q in palm]
    outline = smooth(pp, k=0.6)
    paths = [outline]
    segs = []
    for ch, rr in chains + [thumb]:
        for i in range(len(ch) - 1):
            a, b = pr(ch[i]), pr(ch[i + 1])
            r0 = rr * (1.0 - 0.10 * i) * a[3]
            r1 = rr * (1.0 - 0.10 * (i + 1)) * b[3]
            segs.append(rig.capsule(a[:2], r0, b[:2], r1))
        paths.append(rig.union(*segs[-(len(ch) - 1):]))
    hand = rig.union(*paths)
    fr.part(hand, SKIN, light, width=0.09 * k, line=max(1.2, 0.0025 * k), lit=0.14, dark=0.30)
    c = fr.c
    c.save()
    c.clipPath(hand, skia.ClipOp.kIntersect, True)
    for ch, rr in chains:                                                      # outline each finger so the gaps read
        pts = [pr(q)[:2] for q in ch]
        w = [rr * pr(q)[3] for q in ch]
        sp = rig.union(*[rig.capsule(pts[i], w[i], pts[i + 1], w[i + 1]) for i in range(len(pts) - 1)])
        c.drawPath(sp, paint(shade(SKIN, -0.6), stroke=max(1.0, 0.0022 * k), a=0.8))
    if press > 0:                                                              # blanched contact: pads and the heel
        for ch, rr in chains + [thumb]:
            q = pr(ch[-1])
            c.drawCircle(q[0], q[1], rr * q[3] * 1.05, paint("#f6ecd6", a=0.55 * press, blur=rr * q[3] * 0.3))
    c.restore()
    return hand


def hand_min_z(wrist, u, n, spread, curl):
    palm, chains, thumb = hand_points(wrist, u, n, spread, curl)
    zs = [q[2] - 0.012 for q in palm]
    for ch, rr in chains + [thumb]:
        zs += [q[2] - rr for q in ch]
    return min(zs)


# ---- shears: drawn in 3D in the fist's frame (close insert) and as the rig prop elsewhere --------------------
def shears_geo(grip_pt, d, side, open_deg):
    """Hedge shears hanging from a fist that holds both handles. grip_pt: centre of the fist; d: unit direction down
    the tool; side: unit lateral (the plane the blades open in). Returns the pivot and the pieces."""
    pv = rig.add(grip_pt, rig.mul(d, 0.25))                                    # handles 25 cm down to the bolt
    a = math.radians(open_deg / 2)
    out = []
    for sg in (1, -1):
        out.append(("handle", rig.add(grip_pt, rig.mul(side, sg * 0.007)), rig.add(pv, rig.mul(side, sg * 0.006)), sg))
        bd = rig.norm(rig.add(rig.mul(d, math.cos(a)), rig.mul(side, sg * math.sin(a))))
        out.append(("blade", rig.add(pv, rig.mul(side, sg * 0.004)), rig.add(pv, rig.mul(bd, 0.25)), sg))
    return pv, out


def draw_shears3d(fr, cam, grip_pt, d, side, open_deg):
    pv, pieces = shears_geo(grip_pt, d, side, open_deg)
    for kind, a3, b3, sg in sorted(pieces, key=lambda q: -cam.view(q[2])[2]):
        a, b = cam.proj(a3), cam.proj(b3)
        k = (a[3] + b[3]) / 2
        if kind == "handle":                                                    # red grip, then a short steel shank
            m3 = rig.add(a3, rig.mul(rig.sub(b3, a3), 0.72))
            m = cam.proj(m3)
            fr.c.drawLine(m[0], m[1], b[0], b[1], paint("#5a5c64", stroke=0.016 * k))
            fr.c.drawLine(m[0], m[1], b[0], b[1], paint("#1f2026", stroke=max(1.0, 0.0025 * k), a=0.0))
            grip = rig.capsule(a[:2], 0.016 * a[3], m[:2], 0.013 * m[3])
            fr.part(grip, "#b3342b", (0.4, 1.0), width=0.03 * k, line=max(1.0, 0.002 * k))
        else:                                                                   # broad blade, blunt tip, bevelled edge
            dx, dy = b[0] - a[0], b[1] - a[1]
            nn = math.hypot(dx, dy) or 1.0
            px, py = -dy / nn * sg, dx / nn * sg
            w0, w1 = 0.024 * a[3], 0.010 * b[3]
            blade = skia.Path()
            blade.moveTo(a[0] + px * w0, a[1] + py * w0)
            blade.lineTo(b[0] + px * w1, b[1] + py * w1)
            blade.quadTo(b[0] + dx / nn * w1 * 0.8, b[1] + dy / nn * w1 * 0.8, b[0] - px * w1 * 0.2, b[1] - py * w1 * 0.2)
            blade.lineTo(a[0] - px * w0 * 0.2, a[1] - py * w0 * 0.2)
            blade.close()
            fr.c.drawPath(blade, paint(shader=lin((a[0] + px * w0, a[1] + py * w0), (a[0] - px * w0 * 0.2, a[1] - py * w0 * 0.2),
                                                  [argb("#5f6878"), argb("#c9d0da"), argb("#eef2f6")], [0, 0.6, 1])))
            fr.c.drawLine(a[0] - px * w0 * 0.2, a[1] - py * w0 * 0.2, b[0] - px * w1 * 0.2, b[1] - py * w1 * 0.2,
                          paint("#ffffff", a=0.7, stroke=max(1.0, 0.003 * k)))
            fr.c.drawPath(blade, paint("#1f232b", stroke=max(1.0, 0.0025 * k)))
    q = cam.proj(pv)
    fr.c.drawCircle(q[0], q[1], 0.012 * q[3], paint("#4a4a52"))
    fr.c.drawCircle(q[0], q[1], 0.012 * q[3], paint("#15161a", stroke=max(1.0, 0.002 * q[3])))
    fr.c.drawCircle(q[0] - 0.003 * q[3], q[1] - 0.003 * q[3], 0.004 * q[3], paint("#c9ccd4", a=0.8))


def shears(open_deg=6.0):
    """Rig prop: hanging shears for the medium and wide shots (blades down along the forearm line)."""
    def fn(fr, cam, J, s, hd, fd, k):
        w = J["wr_" + s]
        fore = rig.norm(rig.sub(w, J["el_" + s]))
        g = rig.add(w, rig.mul(fore, 0.05))                                     # the fist
        d = rig.norm(rig.add(rig.mul(fore, 0.35), (0.0, -0.65, 0.0)))          # the tool hangs, close to plumb
        side = rig.norm(rig.cross(d, J["Bb"].r))                                # blades open front-to-back: seen from the side
        draw_shears3d(fr, cam, g, d, side, open_deg)
    fn.under = True
    return fn
