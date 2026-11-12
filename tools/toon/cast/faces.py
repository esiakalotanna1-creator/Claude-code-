"""Creepy faces drawn on the head surface (from the Lynn reel's lynn_face, made generic for the kit).

face(...) returns a LOOK extra. Style comes from pose creep_style or the look's creep_style; strength from pose creep
(default: the look's creep, else 1). Pose keys also used: gx, gy (gaze), mouth (opens to speak), frown (corners down).
Rule: creepy faces stay simple and symmetric; no stacked lines, veins or cracks by default.
"""
import skia

import rig
from rig import Head, smooth
from toon import argb, paint, rad, shade

STYLES = {
    # Lynn "M": big even round eyes, tiny pupils, a wide thin mouth slightly open into an abyss
    "M": dict(grin_w=0.64, grin_rise=0.08, grin_open=0.11, teeth=0, gums=0.0, eye_s=1.16, pupil=0.032, iris=0.0,
              sock=0.3, veins=0.0, pale=0.12, lip=0.2, hollow=0.0, lowlid=0, creases=0, abyss=1),
    # the Mara (2026-11-08): deep sunken sockets, small yellowed eyes with pinprick pupils, hollow cheeks, a narrow
    # mouth with the corners turned down, barely parted into darkness
    "MARA": dict(grin_w=0.40, grin_rise=-0.10, grin_open=0.07, teeth=0, gums=0.0, eye_s=0.6, pupil=0.024, iris=0.0,
                 sock=1.0, veins=0.0, pale=0.10, lip=0.0, hollow=1.0, lowlid=0, creases=0, abyss=1, white="#ddd8bf",
                 sock_col="#14121a", rim_blur=0.08),
}


def _vis_run(Hd, cam, pts_lm, lift=1.012, thr=0.04):
    best, cur = [], []
    for lam, mu in pts_lm:
        if Hd.facing(lam, mu) > thr:
            cur.append(cam.proj(Hd.surf(lam, mu, lift))[:2])
        else:
            best, cur = (cur if len(cur) > len(best) else best), []
    return cur if len(cur) > len(best) else best


def face():
    def extra(parts, fr, cam, J, p, ld, lw, out):
        L = rig.LOOK[J["look"]]
        cr = p.get("creep", L.get("creep", 1.0))
        if cr <= 0.01:
            return
        S = STYLES[p.get("creep_style", L.get("creep_style", "M"))]
        R, Bh = J["R"], J["Bh"]
        Hd = Head(cam, J["head"], Bh, R)
        k = cam.proj(J["head"])[3]
        c = fr.c
        sock_col = S.get("sock_col", "#2a1418")

        def draw():
            rings = [(u * R, wa * R * 1.04, db * R * 0.97, 0, bo * R) for u, wa, db, ao, bo in rig.HEAD_RINGS]
            head, _ = rig.lathe(cam, J["head"], Bh, rings)
            if S["pale"] > 0:
                c.save()
                c.clipPath(rig.hair_path(Hd, cam, L), skia.ClipOp.kDifference, True)
                c.drawPath(head, paint("#c8ccd4", a=S["pale"] * cr))
                c.restore()
            if S.get("hollow"):                                  # sunken cheeks under the cheekbones
                for sg in (-1, 1):
                    if Hd.facing(sg * 0.62, -0.30) > 0.1:
                        c.save()
                        c.concat(Hd.decal(sg * 0.62, -0.30))
                        c.drawOval(skia.Rect(-0.17 * R, -0.16 * R, 0.17 * R, 0.20 * R),
                                   paint("#3a3846", a=0.3 * S["hollow"] * cr, blur=0.1 * R))
                        c.restore()
                # temples sunk in as well
                for sg in (-1, 1):
                    if Hd.facing(sg * 0.85, 0.30) > 0.1:
                        c.save()
                        c.concat(Hd.decal(sg * 0.85, 0.30))
                        c.drawOval(skia.Rect(-0.12 * R, -0.14 * R, 0.12 * R, 0.14 * R),
                                   paint("#3a3846", a=0.25 * S["hollow"] * cr, blur=0.05 * R))
                        c.restore()
            for side, lam in ((-1, -0.40), (1, 0.40)):
                if Hd.facing(lam, 0.02) <= 0.12:
                    continue
                c.save()
                c.concat(Hd.decal(lam, 0.02))
                es = S["eye_s"]
                rx, ry = 0.25 * R * es, 0.31 * R * es
                # the socket: a wide soft dark hollow, then a tight rim (a ring alone reads as goggles)
                c.drawOval(skia.Rect(-rx * 1.55, -ry * 1.35, rx * 1.55, ry * 1.6),
                           paint(sock_col, a=S["sock"] * 0.55 * cr, blur=0.09 * R))
                c.drawOval(skia.Rect(-rx * 1.12, -ry * 1.08, rx * 1.12, ry * 1.12),
                           paint(sock_col, a=S["sock"] * 0.6 * cr, blur=S.get("rim_blur", 0.03) * R))
                eye = skia.Path()
                eye.addOval(skia.Rect(-rx, -ry, rx, ry))
                c.drawPath(eye, paint(S.get("white", "#f6f3ea"), a=cr))
                c.save()
                c.clipPath(eye, skia.ClipOp.kIntersect, True)
                c.drawOval(skia.Rect(-rx, -ry, rx, -ry * 0.2), paint(sock_col, a=0.35 * cr, blur=0.03 * R))   # lid shadow
                gx, gy = p.get("gx", 0.0) * 0.10 * R, p.get("gy", 0.0) * 0.12 * R
                if S["iris"]:
                    c.drawCircle(gx, gy, S["iris"] * R, paint(shade("#5a4632", -0.1)))
                c.drawCircle(gx, gy, S["pupil"] * R, paint("#050506"))
                c.drawCircle(gx - 0.03 * R, gy - 0.035 * R, 0.018 * R, paint("#ffffff", a=0.85))   # the glint
                c.restore()
                c.drawPath(eye, paint(sock_col, stroke=0.03 * R, a=cr))
                c.restore()
            if Hd.facing(0.0, -0.45) < -0.1:
                return
            fw = p.get("frown", 0.0)
            keep = 1.0 if S.get("abyss") else 1 - fw
            n, W = 27, S["grin_w"]
            op = max(S["grin_open"] * cr * keep, 0.22 * p.get("mouth", 0.0))
            rise = S["grin_rise"] * (1 - fw) - 0.17 * fw
            lams = [-W + 2 * W * i / (n - 1) for i in range(n)]
            up = [(a, -0.48 + rise * (a / W) ** 2 * W) for a in lams]
            if op < 0.02:
                U = _vis_run(Hd, cam, up)
                if len(U) > 2:
                    c.drawPath(smooth(U, closed=False), paint("#2a1418", stroke=0.05 * R * k * (1 + 0.4 * S["lip"])))
                return
            lo = [(a, mu - op * max(0.0, 1 - (a / W) ** 2) - 0.015) for a, mu in up]
            U, D = _vis_run(Hd, cam, up), _vis_run(Hd, cam, lo)
            if len(U) < 3 or len(D) < 3:
                return
            shape = smooth(U + D[::-1], k=0.5)
            c.drawPath(shape, paint("#000000" if S.get("abyss") else "#2a070a"))
            c.drawPath(smooth(U, closed=False), paint("#2a1216", stroke=0.035 * R * k))
            c.drawPath(smooth(D, closed=False), paint("#2a1216", stroke=0.03 * R * k))

        parts.append(("face", J["head"][2], draw))

    return extra
