"""The Smiling Man and Timmy's pistol, on top of the Timmy cast (looks.py).

  smiler  very tall, thin, pale; an old brown suit (short jacket hem, lapels, white shirt, thin tie), slicked hair.
          His face is drawn on the head surface (smile_face): small even eyes in dark sockets, dead pinprick pupils and a wide
          fixed toothy grin. Pose grin 1 = the smile, 0 = a plain tired face (the smile drop at the gun).
  gun()   a black pistol in the fist; pose "flash" draws a muzzle flash at the barrel.
"""
import math

import skia

import looks as LK  # noqa: F401  (registers kid / onna, puts tools/toon on the path via kit)
import rig
from rig import Head, dot, norm, smooth, sub
from toon import argb, lin, paint, shade

SKIN = "#ebe3d8"
SUIT = "#4a3c30"


def _vis_run(Hd, cam, pts_lm, lift=1.012, thr=0.04):
    best, cur = [], []
    for lam, mu in pts_lm:
        if Hd.facing(lam, mu) > thr:
            cur.append(cam.proj(Hd.surf(lam, mu, lift))[:2])
        else:
            best, cur = (cur if len(cur) > len(best) else best), []
    return cur if len(cur) > len(best) else best


def _faces(J, cam, B):
    return dot(B.f, norm(sub(cam.pos, J["pelvis"]))) > 0


def smile_face(parts, fr, cam, J, p, ld, lw, out):
    g = max(0.0, min(1.0, p.get("grin", 1.0)))
    R, Bh = J["R"], J["Bh"]
    Hd = Head(cam, J["head"], Bh, R)
    k = cam.proj(J["head"])[3]
    c = fr.c

    def face():
        # eyes: even and round in deep dark sockets; dead pinprick pupils (no catchlight) while he smiles
        es = 1.0 - 0.18 * g
        for side, lam in ((-1, -0.40), (1, 0.40)):
            if Hd.facing(lam, 0.02) <= 0.12:
                continue
            c.save()
            c.concat(Hd.decal(lam, 0.02))
            rx, ry = 0.25 * R * es, 0.30 * R * es
            c.drawOval(skia.Rect(-rx * 1.12, -ry * 1.08, rx * 1.12, ry * 1.12), paint("#2a1418", a=0.35 * g, blur=0.035 * R))
            c.drawOval(skia.Rect(-rx * 1.55, -ry * 1.45, rx * 1.55, ry * 1.5), paint("#1a0c10", a=0.42 * g, blur=0.07 * R))
            eye = skia.Path()
            eye.addOval(skia.Rect(-rx, -ry, rx, ry))
            c.drawPath(eye, paint("#f6f3ea"))
            c.save()
            c.clipPath(eye, skia.ClipOp.kIntersect, True)
            gx, gy = p.get("gx", 0.0) * 0.10 * R, p.get("gy", 0.0) * 0.12 * R
            if g < 0.99:
                c.drawCircle(gx, gy, 0.13 * R * (1 - g), paint("#3b2c22"))
            c.drawCircle(gx, gy, (0.022 + 0.048 * (1 - g)) * R, paint("#050506"))
            if g < 0.5:
                c.drawCircle(gx - 0.03 * R, gy - 0.035 * R, 0.018 * R, paint("#ffffff", a=0.85 * (1 - 2 * g)))
            # upper lid comes down as the smile drops (tired, ordinary)
            lid = 0.32 * (1 - g)
            if lid > 0.01:
                c.drawRect(skia.Rect(-rx * 1.2, -ry * 1.2, rx * 1.2, -ry + 2 * ry * lid), paint(shade(SKIN, -0.12)))
            c.restore()
            c.drawPath(eye, paint("#2a1418", stroke=0.03 * R))
            c.restore()
            c.save()                                          # thin flat brows, low over the sockets
            c.concat(Hd.decal(lam * 1.08, 0.29))
            b = skia.Path()
            b.moveTo(-0.22 * R, 0.0)
            b.quadTo(0, -0.02 * R, 0.22 * R, 0.01 * R)
            c.drawPath(b, paint("#1d1612", stroke=0.05 * R))
            c.restore()
        if Hd.facing(0.0, -0.16) > 0.05:                     # nose: a soft shadow only
            c.save()
            c.concat(Hd.decal(0.0, -0.17, 1.03))
            c.drawOval(skia.Rect(-0.10 * R, -0.07 * R, 0.10 * R, 0.08 * R), paint(shade(SKIN, -0.28), a=0.5, blur=0.02 * R))
            c.restore()
        if Hd.facing(0.0, -0.45) < -0.1:
            return
        # the mouth: grin_w 0.95 cheek to cheek, corners high, open on straight even teeth; at g=0 a short flat line
        n = 27
        W = 0.30 + 0.58 * g
        rise = 0.22 * g
        op = 0.13 * g + 0.22 * p.get("mouth", 0.0)
        lams = [-W + 2 * W * i / (n - 1) for i in range(n)]
        up = [(a, -0.48 + rise * (a / W) ** 2 * W) for a in lams]
        if op < 0.02:
            U = _vis_run(Hd, cam, up)
            if len(U) > 2:
                c.drawPath(smooth(U, closed=False), paint("#3a1418", stroke=0.045 * R * k))
            return
        lo = [(a, mu - op * max(0.0, 1 - (a / W) ** 2) - 0.012) for a, mu in up]
        U, D = _vis_run(Hd, cam, up), _vis_run(Hd, cam, lo)
        if len(U) < 3 or len(D) < 3:
            return
        shape = smooth(U + D[::-1], k=0.5)
        c.drawPath(shape, paint("#1a0507"))
        c.save()
        c.clipPath(shape, skia.ClipOp.kIntersect, True)
        tn = 14                                               # one row of big straight teeth, vertical gaps
        sp = 2 * W * 0.92 / tn
        for i in range(tn):
            a = -W * 0.92 + sp * (i + 0.5)
            base = -0.48 + rise * (a / W) ** 2 * W
            depth = op * max(0.0, 1 - (a / W) ** 2) * 0.62
            q = _vis_run(Hd, cam, [(a - sp * 0.42, base + 0.01), (a + sp * 0.42, base + 0.01),
                                   (a + sp * 0.40, base - depth), (a - sp * 0.40, base - depth)])
            if len(q) == 4:
                t = skia.Path()
                t.moveTo(*q[0])
                for qq in q[1:]:
                    t.lineTo(*qq)
                t.close()
                c.drawPath(t, paint("#f3eee2"))
                c.drawPath(t, paint("#8a7a68", stroke=0.006 * R * k, a=0.6))
        c.restore()
        c.drawPath(smooth(U, closed=False), paint("#3a1014", stroke=0.035 * R * k))
        c.drawPath(smooth(D, closed=False), paint("#3a1014", stroke=0.03 * R * k))
        for sg in (-1, 1):                                    # cheek creases pushed up by the grin
            a = sg * W
            q = _vis_run(Hd, cam, [(a * 0.96, -0.48 + rise * W + 0.02), (a * 1.05, -0.48 + rise * W + 0.12)])
            if len(q) == 2 and g > 0.3:
                c.drawLine(*q[0], *q[1], paint(shade(SKIN, -0.45), stroke=0.025 * R * k, a=0.7 * g))

    parts.append(("face", J["head"][2], face))


def suit(parts, fr, cam, J, p, ld, lw, out):
    """Jacket hem over the hips, lapels, a white shirt V, a thin dark tie, two buttons."""
    h, Bb, Bc, P = J["h"], J["Bb"], J["Bc"], J["pelvis"]
    L = rig.LOOK[J["look"]]
    kf = sum(dot(sub(J["kn_" + s], P), Bb.f) for s in ("R", "L")) / 2
    rings = [(u * h, wa * h * L["build"], db * h, 0.0, kf * f * 0.3) for u, wa, db, f in
             ((0.03, 0.100, 0.072, 0.0), (-0.03, 0.106, 0.076, 0.3), (-0.09, 0.110, 0.079, 0.7))]
    path, z = rig.lathe(cam, P, Bb, rings)
    k = cam.proj(P)[3]

    def hem():
        fr.part(path, L["top"], ld, width=0.24 * h * k, line=lw, lit=0.12, dark=0.42)
        if _faces(J, cam, Bb):
            a, b = cam.proj(Bb.w(P, 0.0, 0.03 * h, 0.075 * h)), cam.proj(Bb.w(P, 0.02 * h, -0.09 * h, 0.08 * h + kf * 0.3))
            fr.c.drawLine(a[0], a[1], b[0], b[1], paint(shade(L["top"], -0.5), stroke=lw * 1.1))
    parts.append(("coat", z, hem))

    def front():
        if not _faces(J, cam, Bc):
            return
        W = lambda a, u, b: cam.proj(Bc.w(P, a * h, u * h, b * h))[:2]    # noqa: E731
        shirt = smooth([W(-0.040, 0.298, 0.040), W(0.040, 0.298, 0.040), W(0.0, 0.17, 0.084)], k=0.2)
        fr.c.drawPath(shirt, paint("#e9e6de"))
        tie = smooth([W(-0.010, 0.290, 0.050), W(0.010, 0.290, 0.050), W(0.016, 0.20, 0.080), W(0.0, 0.175, 0.085),
                      W(-0.016, 0.20, 0.080)], k=0.3)
        fr.c.drawPath(tie, paint("#5a1a1e"))
        fr.c.drawPath(shirt, paint(shade(L["top"], -0.6), stroke=lw))
        for sg in (1, -1):
            q = [W(sg * a, u, b) for a, u, b in ((0.042, 0.297, 0.042), (0.085, 0.265, 0.07), (0.02, 0.18, 0.085), (0.0, 0.165, 0.086))]
            fr.c.drawPath(smooth(q, closed=False, k=0.5), paint(shade(L["top"], -0.5), stroke=lw * 1.2))
        for u in (0.12, 0.07):
            x, y = W(0.03, u, 0.088)
            fr.c.drawCircle(x, y, 0.007 * h * k, paint(shade(L["top"], -0.6)))
    parts.append(("overtorso", z, front))


rig.LOOK.update({
    "smiler": dict(h=1.96, skin=SKIN, hair="#17120e", style="neat", hair_mesh=True, top=SUIT, pants=shade(SUIT, -0.08),
                   shoes="#111114", iris="#2a1d16", build=0.84, brow=0.0, extras=(suit, smile_face)),
})


def gun(flash=0.0, sideways=1.0):
    """A black pistol in the fist, barrel along the forearm past the hand; sideways 1 = rolled flat (grip out to the
    side, gangster style), 0 = upright. flash 0..1 draws the muzzle flash."""
    def fn(fr, cam, J, s, hd, fd, k):
        h = J["h"]
        d = rig._screen_dir(cam, J["wr_" + s], fd)
        n = (-d[1], d[0])
        gl = 0.19 * h * k                                   # slide length (cartoon-chunky so it reads at phone size)
        gh = 0.055 * h * k                                  # slide height on screen
        b0 = (hd[0] - d[0] * 0.03 * h * k, hd[1] - d[1] * 0.03 * h * k)
        tip = (b0[0] + d[0] * gl, b0[1] + d[1] * gl)
        gn = 0.085 * h * k * (1 - 0.35 * sideways)          # the grip, under the fist (foreshortened when rolled sideways)
        grip = LK._poly([(b0[0] + d[0] * 0.01 * h * k, b0[1] + d[1] * 0.01 * h * k),
                         (b0[0] + d[0] * 0.045 * h * k, b0[1] + d[1] * 0.045 * h * k),
                         (b0[0] + d[0] * 0.03 * h * k + n[0] * gn, b0[1] + d[1] * 0.03 * h * k + n[1] * gn),
                         (b0[0] - d[0] * 0.005 * h * k + n[0] * gn, b0[1] - d[1] * 0.005 * h * k + n[1] * gn)])
        fr.c.drawPath(grip, paint("#1d1e23"))
        fr.c.drawPath(grip, paint("#050506", stroke=max(1.2, 0.004 * h * k)))
        slide = LK._poly([(b0[0] + n[0] * gh * 0.5, b0[1] + n[1] * gh * 0.5), (tip[0] + n[0] * gh * 0.5, tip[1] + n[1] * gh * 0.5),
                          (tip[0] - n[0] * gh * 0.5, tip[1] - n[1] * gh * 0.5), (b0[0] - n[0] * gh * 0.5, b0[1] - n[1] * gh * 0.5)])
        fr.c.drawPath(slide, paint(shader=lin((b0[0] + n[0] * gh, b0[1] + n[1] * gh), (b0[0] - n[0] * gh, b0[1] - n[1] * gh),
                                              [argb("#4a4e58"), argb("#15161a")])))
        fr.c.drawPath(slide, paint("#050506", stroke=max(1.2, 0.004 * h * k)))
        fr.c.drawLine(b0[0] + d[0] * gl * 0.35 + n[0] * gh * 0.35, b0[1] + d[1] * gl * 0.35 + n[1] * gh * 0.35,
                      tip[0] - d[0] * gl * 0.08 + n[0] * gh * 0.35, tip[1] - d[1] * gl * 0.08 + n[1] * gh * 0.35,
                      paint("#8a8f9c", a=0.6, stroke=max(1.0, 0.004 * h * k)))
        J["prop_tip"] = tip
        if flash > 0.01:
            r = 0.09 * h * k * (0.6 + 0.4 * flash)
            fr.glow(tip[0] + d[0] * r * 0.6, tip[1] + d[1] * r * 0.6, r * 2.2, "#ffcf6a", a=0.7 * flash)
            star = []
            for i in range(10):
                a = math.atan2(d[1], d[0]) + (i - 4.5) * 0.32
                rr = r * (1.0 if i % 2 == 0 else 0.45)
                star.append((tip[0] + math.cos(a) * rr, tip[1] + math.sin(a) * rr))
            fr.c.drawPath(LK._poly([tip] + star), paint("#fff4c8", a=flash))
    fn.under = True                                         # the fist wraps the grip
    return fn
