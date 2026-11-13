"""The cast of LEAVE A MESSAGE. Each character has their own silhouette, face and palette, built from the script:

    maya   27. Grief kept tidy. Dark curls pulled up into a big loose bun, round tortoiseshell glasses, an oversized
           oat cardigan over a charcoal tee, leggings. Warm brown skin, dark brown eyes. Soft, slightly long face.
    theo   16. All elbows. Messy chestnut hair, freckles, an oversized faded-teal hoodie (hood bunched at the neck,
           drawstrings, kangaroo pocket), big headphones round his neck, grey joggers. Pale, hazel eyes. Narrow build.
    frank  58. Maya's dad, seen in memory and in a photo. Big, warm, square-jawed: a short salt-and-pepper beard and
           moustache, thick brows, a rust work shirt with a cream collar. Grey-blue eyes, laughter in them.

Costume layers are look extras: fn(parts, fr, cam, J, p, ld, lw, out) appending (kind, depth, draw_fn).
Model sheets (from tools/toon):  python -m cast.sheet ../../episodes/callback/toon/looks.py maya
"""
import math

import skia

import rig
from rig import Head, add, dot, lathe, mul, norm, smooth, sub
from toon import argb, paint, shade


# ---- helpers ------------------------------------------------------------------------------------------------
def _k(cam, J):
    return cam.proj(J["neck"])[3]


def _facing_body(cam, J):
    """+1 when the chest faces the lens, -1 when the back does."""
    return dot(J["Bc"].f, norm(sub(cam.pos, J["neck"])))


def _facing_head(cam, J):
    return dot(J["Bh"].f, norm(sub(cam.pos, J["head"])))


_T_RINGS = [(-0.07, 0.104, 0.074), (0.05, 0.098, 0.068), (0.17, 0.112, 0.078), (0.245, 0.124, 0.074),
            (0.275, 0.118, 0.068), (0.292, 0.088, 0.056), (0.300, 0.046, 0.040)]


def _ring(u):
    """Torso half-width and half-depth (fractions of h) at height u (fraction of h, before tf)."""
    for (u0, w0, d0), (u1, w1, d1) in zip(_T_RINGS, _T_RINGS[1:]):
        if u0 <= u <= u1:
            t = (u - u0) / (u1 - u0)
            return w0 + (w1 - w0) * t, d0 + (d1 - d0) * t
    return _T_RINGS[-1][1:] if u > 0.3 else _T_RINGS[0][1:]


def chest(J, L, u, x, lift=1.012):
    """A point on the front of the torso: u = height (fraction of h, as in the rig's torso rings), x = across
    (fraction of h; + toward the torso basis' r axis)."""
    h, tf = J["h"], J["tf"]
    w, d = _ring(u)
    w *= L["build"]
    xx = max(-0.98, min(0.98, x / w))
    z = d * math.sqrt(1 - xx * xx) * lift
    return J["Bc"].w(J["pelvis"], x * h, (u * tf if u > 0 else u) * h, z * h)


def _surf_path(Hd, cam, pts, closed=True, k=0.8, min_face=-0.35):
    q = [cam.proj(Hd.surf(lam, mu, lift))[:2] for lam, mu, lift in pts if Hd.facing(lam, mu) > min_face]
    return smooth(q, closed=closed, k=k) if len(q) >= 3 else None


# ---- maya -----------------------------------------------------------------------------------------------------
def hair_bun(colr, tie="#b5523f"):
    """A big loose bun high on the back of the head, a hair tie under it, two loose curls at the nape."""
    def extra(parts, fr, cam, J, p, ld, lw, out):
        R, Bh, hc = J["R"], J["Bh"], J["head"]
        k = cam.proj(hc)[3]
        c0 = Bh.w(hc, 0.0, 1.02 * R, -0.22 * R)
        rb = 0.52 * R
        rings = [(u * rb, math.sqrt(max(0.0, 1 - u * u)) * rb * 1.08, math.sqrt(max(0.0, 1 - u * u)) * rb, 0, 0)
                 for u in (-0.92, -0.6, -0.25, 0.1, 0.45, 0.75, 0.95)]
        path, z = lathe(cam, c0, Bh, rings)
        tie_rings = [(-0.95 * rb, 0.62 * rb, 0.58 * rb, 0, 0), (-0.80 * rb, 0.66 * rb, 0.62 * rb, 0, 0)]
        tpath, _ = lathe(cam, c0, Bh, tie_rings)
        front = _facing_head(cam, J) > -0.1

        def draw():
            fr.part(path, colr, ld, width=2 * rb * k, line=lw, lit=0.18, dark=0.5, rim=0.1)
            c = fr.c
            c.save()
            c.clipPath(path, skia.ClipOp.kIntersect, True)
            for i in range(6):                                  # curl clumps: soft darker arcs
                a = i * 1.05 + 0.3
                pa = cam.proj(Bh.w(c0, math.cos(a) * rb * 0.55, math.sin(a) * rb * 0.6, rb * 0.6))
                pb = cam.proj(Bh.w(c0, math.cos(a + 1.3) * rb * 0.85, math.sin(a + 1.3) * rb * 0.75, rb * 0.3))
                arc = skia.Path()
                arc.moveTo(pa[0], pa[1])
                arc.quadTo((pa[0] + pb[0]) / 2 + 0.08 * rb * k, (pa[1] + pb[1]) / 2 - 0.1 * rb * k, pb[0], pb[1])
                c.drawPath(arc, paint(shade(colr, -0.55), stroke=max(1.0, 0.07 * rb * k), a=0.55))
            c.restore()
            fr.part(tpath, tie, ld, width=1.2 * rb * k, line=lw * 0.8, lit=0.15, dark=0.4)
        parts.append(("overtorso" if front else "top", z, draw))
    return extra


def round_glasses(frame="#5a3a26"):
    """Round tortoiseshell frames, a little bigger than the eyes so the eyes always sit inside them."""
    def extra(parts, fr, cam, J, p, ld, lw, out):
        R = J["R"]
        L = rig.LOOK[J["look"]]
        Hd = Head(cam, J["head"], J["Bh"], R, L.get("head_shape"))

        def draw():
            c = fr.c
            seen = []
            for lam in (-0.40, 0.40):
                if Hd.facing(lam, 0.02) > 0.10:
                    c.save()
                    c.concat(Hd.decal(lam, 0.0, 1.05))
                    rim = skia.Path()
                    rim.addOval(skia.Rect(-0.33 * R, -0.33 * R, 0.33 * R, 0.33 * R))
                    c.drawPath(rim, paint("#e8f2ff", a=0.10))
                    glare = skia.Path()                          # one soft diagonal glint
                    glare.moveTo(-0.18 * R, -0.22 * R)
                    glare.lineTo(-0.02 * R, -0.30 * R)
                    glare.lineTo(-0.20 * R, 0.02 * R)
                    glare.close()
                    c.drawPath(glare, paint("#ffffff", a=0.18))
                    c.drawPath(rim, paint(shade(frame, -0.45), stroke=0.075 * R))
                    c.drawPath(rim, paint(frame, stroke=0.045 * R))
                    c.restore()
                    seen.append(lam)
            if len(seen) == 2 and Hd.facing(0.0, 0.08) > 0.05:      # bridge
                a = cam.proj(Hd.surf(-0.12, 0.10, 1.07))
                b = cam.proj(Hd.surf(0.12, 0.10, 1.07))
                m = cam.proj(Hd.surf(0.0, 0.14, 1.09))
                br = skia.Path()
                br.moveTo(a[0], a[1])
                br.quadTo(m[0], m[1], b[0], b[1])
                c.drawPath(br, paint(frame, stroke=max(1.0, 0.045 * R * a[3])))
            for lam, sg in ((-0.40, -1), (0.40, 1)):                  # arms back to the ears
                if Hd.facing(sg * 1.2, 0.05) > -0.05:
                    a = cam.proj(Hd.surf(sg * 0.74, 0.06, 1.05))
                    b = cam.proj(Hd.surf(sg * 1.45, 0.0, 1.04))
                    c.drawLine(a[0], a[1], b[0], b[1], paint(frame, stroke=max(1.0, 0.04 * R * a[3])))
        if _facing_head(cam, J) > -0.2:
            parts.append(("face", 0.0, draw))
    return extra


def open_cardigan(tee, rib=None):
    """The top is the cardigan; this draws the tee showing down the open front, with ribbed cardigan edges."""
    def extra(parts, fr, cam, J, p, ld, lw, out):
        L = rig.LOOK[J["look"]]
        if _facing_body(cam, J) < 0.08:
            return
        h, k = J["h"], _k(cam, J)
        rb = rib or shade(L["top"], 0.08)
        us = [0.288, 0.26, 0.22, 0.17, 0.11, 0.05, -0.01]
        left = [chest(J, L, u, -(0.026 + 0.012 * i)) for i, u in enumerate(us)]
        right = [chest(J, L, u, (0.026 + 0.012 * i)) for i, u in enumerate(us)]
        neck_dip = chest(J, L, 0.255, 0.0)
        pts = [cam.proj(q) for q in left + right[::-1]]
        if min(q[2] for q in pts) < 0.2:
            return
        tee_pts = [cam.proj(q)[:2] for q in left] + [cam.proj(q)[:2] for q in right[::-1]]
        z = sum(q[2] for q in pts) / len(pts)

        def draw():
            c = fr.c
            path = smooth(tee_pts, k=0.4)
            fr.part(path, tee, ld, width=0.1 * h * k, line=lw, lit=0.08, dark=0.35)
            nd = cam.proj(neck_dip)                              # the tee's round neckline
            c.save()
            c.clipPath(path, skia.ClipOp.kIntersect, True)
            c.drawOval(skia.Rect(nd[0] - 0.026 * h * k, nd[1] - 0.05 * h * k, nd[0] + 0.026 * h * k, nd[1] + 0.006 * h * k),
                       paint(shade(tee, -0.4), a=0.85))
            c.restore()
            for side in (left, right):                           # ribbed button bands
                q = [cam.proj(v)[:2] for v in side]
                c.drawPath(smooth(q, closed=False), paint(shade(rb, -0.5), stroke=0.022 * h * k))
                c.drawPath(smooth(q, closed=False), paint(rb, stroke=0.016 * h * k))
            for u in (0.06, 0.13):                               # two buttons, undone
                b = cam.proj(chest(J, L, u, -(0.030 + 0.012 * (0.288 - u) / 0.05), 1.03))
                c.drawCircle(b[0], b[1], 0.007 * h * k, paint("#6b4a32"))
        parts.append(("overtorso", z, draw))
    return extra


def tears():
    """pose "tear" 0..1: a wet shine along the lower lids and, past 0.5, a drop running down one cheek."""
    def extra(parts, fr, cam, J, p, ld, lw, out):
        t = p.get("tear", 0.0)
        if t <= 0.02 or _facing_head(cam, J) < 0.2:
            return
        R = J["R"]
        L = rig.LOOK[J["look"]]
        Hd = Head(cam, J["head"], J["Bh"], R, L.get("head_shape"))

        def draw():
            c = fr.c
            for lam in (-0.40, 0.40):
                if Hd.facing(lam, -0.27) < 0.15:
                    continue
                q = [cam.proj(Hd.surf(lam + d, -0.27 - 0.03 * (1 - abs(d) / 0.2), 1.01))[:2] for d in (-0.2, -0.1, 0.0, 0.1, 0.2)]
                k = cam.proj(Hd.surf(lam, -0.27, 1.0))[3]
                c.drawPath(smooth(q, closed=False), paint("#e8f4ff", a=0.55 * min(1.0, t * 1.5), stroke=0.045 * R * k))
            if t > 0.5 and Hd.facing(0.30, -0.5) > 0.2:
                u = min(1.0, (t - 0.5) / 0.5)
                a = cam.proj(Hd.surf(0.30, -0.31, 1.01))
                b = cam.proj(Hd.surf(0.33, -0.31 - 0.35 * u, 1.01))
                k = a[3]
                c.drawLine(a[0], a[1], b[0], b[1], paint("#e8f4ff", a=0.45, stroke=0.035 * R * k))
                c.drawCircle(b[0], b[1], 0.04 * R * k, paint("#f4faff", a=0.8))
        parts.append(("face", 0.0, draw))
    return extra


# ---- theo -----------------------------------------------------------------------------------------------------
def hood(colr):
    """The hood of the hoodie, bunched in a soft roll round the back and sides of the neck."""
    def extra(parts, fr, cam, J, p, ld, lw, out):
        h, Bc, P = J["h"], J["Bc"], J["pelvis"]
        tf = J["tf"]
        o = Bc.w(P, 0, 0.0, -0.022 * h)
        rings = [(0.270 * tf * h, 0.080 * h, 0.064 * h, 0, -0.004 * h), (0.300 * tf * h, 0.088 * h, 0.072 * h, 0, -0.012 * h),
                 (0.330 * tf * h, 0.080 * h, 0.068 * h, 0, -0.022 * h), (0.352 * tf * h, 0.058 * h, 0.052 * h, 0, -0.030 * h)]
        path, z = lathe(cam, o, Bc, rings)
        k = _k(cam, J)
        front = _facing_body(cam, J) > -0.1

        def draw():
            fr.part(path, colr, ld, width=0.18 * h * k, line=lw, lit=0.12, dark=0.45)
            c = fr.c
            c.save()
            c.clipPath(path, skia.ClipOp.kIntersect, True)
            ins = cam.proj(Bc.w(P, 0, 0.318 * tf * h, -0.03 * h))      # the hood's dark inside, seen over the shoulders
            c.drawOval(skia.Rect(ins[0] - 0.05 * h * k, ins[1] - 0.012 * h * k, ins[0] + 0.05 * h * k, ins[1] + 0.02 * h * k),
                       paint(shade(colr, -0.6), a=0.6, blur=0.008 * h * k))
            c.restore()
        parts.append(("overtorso" if front else "top", z, draw))
    return extra


def hoodie_front(colr):
    """Drawstrings with metal tips, and the kangaroo pocket."""
    def extra(parts, fr, cam, J, p, ld, lw, out):
        L = rig.LOOK[J["look"]]
        if _facing_body(cam, J) < 0.1:
            return
        h, k = J["h"], _k(cam, J)
        sway = 0.004 * math.sin(p.get("t", 0.0) * 2.1)

        def draw():
            c = fr.c
            pk = [chest(J, L, u, x, 1.02) for u, x in ((0.115, -0.060), (0.115, 0.060), (0.02, 0.078), (0.02, -0.078))]
            q = [cam.proj(v)[:2] for v in pk]
            pocket = smooth(q, k=0.25)
            c.drawPath(pocket, paint(shade(colr, -0.1)))
            c.drawPath(pocket, paint(shade(colr, -0.55), stroke=lw * 0.9))
            for sg in (-1, 1):
                a = cam.proj(chest(J, L, 0.283, sg * 0.022, 1.03))
                m = cam.proj(chest(J, L, 0.24, sg * 0.026 + sway, 1.04))
                b = cam.proj(chest(J, L, 0.195, sg * 0.024 + sway, 1.05))
                s = skia.Path()
                s.moveTo(a[0], a[1])
                s.quadTo(m[0], m[1], b[0], b[1])
                c.drawPath(s, paint("#e9e6dc", stroke=0.007 * h * k))
                c.drawLine(b[0], b[1], b[0], b[1] + 0.016 * h * k, paint("#9aa0a8", stroke=0.010 * h * k))
        parts.append(("overtorso", 0.0, draw))
    return extra


def neck_headphones(colr="#24262e", accent="#d9583a"):
    """Big over-ear headphones resting round his neck: the band behind, a cup each side of the collar."""
    def extra(parts, fr, cam, J, p, ld, lw, out):
        h, Bc, P, tf = J["h"], J["Bc"], J["pelvis"], J["tf"]
        k = _k(cam, J)
        front = _facing_body(cam, J)
        band = [(0.346 * tf * h, 0.074 * h, 0.064 * h, 0, -0.012 * h), (0.356 * tf * h, 0.074 * h, 0.064 * h, 0, -0.012 * h)]
        bpath, zb = lathe(cam, P, Bc, band)
        cups = []
        for sg in (-1, 1):
            cc = Bc.w(P, sg * 0.074 * h, 0.322 * tf * h, 0.018 * h)
            cups.append((cam.proj(cc), sg))

        def draw_band():
            fr.part(bpath, colr, ld, width=0.02 * h * k, line=lw * 0.8, lit=0.2, dark=0.4)

        def draw_cups():
            for q, sg in cups:
                if q[2] < 0.2:
                    continue
                r = 0.034 * h * q[3]
                cup = skia.Path()
                cup.addOval(skia.Rect(q[0] - r * 0.78, q[1] - r, q[0] + r * 0.78, q[1] + r))
                fr.part(cup, colr, ld, width=2 * r, line=lw * 0.8, lit=0.25, dark=0.45)
                fr.c.drawOval(skia.Rect(q[0] - r * 0.42, q[1] - r * 0.55, q[0] + r * 0.42, q[1] + r * 0.55), paint(accent))
        parts.append(("overtorso" if front > -0.1 else "top", zb, draw_band))
        parts.append(("overtorso", 0.0, draw_cups) if front > 0.25 else ("under", 1e9, draw_cups) if front < -0.3 else ("overtorso", 0.0, draw_cups))
    return extra


def freckles(colr="#b5704f"):
    def extra(parts, fr, cam, J, p, ld, lw, out):
        R = J["R"]
        L = rig.LOOK[J["look"]]
        Hd = Head(cam, J["head"], J["Bh"], R, L.get("head_shape"))
        dots = [(sg * lam, mu) for sg in (-1, 1) for lam, mu in ((0.32, -0.36), (0.42, -0.33), (0.52, -0.38), (0.38, -0.43),
                                                                 (0.48, -0.45), (0.58, -0.32), (0.28, -0.42))] + [(-0.07, -0.27), (0.07, -0.26), (0.0, -0.30)]

        def draw():
            for lam, mu in dots:
                if Hd.facing(lam, mu) > 0.25:
                    q = cam.proj(Hd.surf(lam, mu, 1.004))
                    fr.c.drawCircle(q[0], q[1], max(0.7, 0.018 * R * q[3]), paint(colr, a=0.55))
        if _facing_head(cam, J) > 0.0:
            parts.append(("face", 0.0, draw))
    return extra


# ---- frank ----------------------------------------------------------------------------------------------------
def beard(colr):
    """A short full beard and moustache; the mouth shows through, so he can talk and smile."""
    def extra(parts, fr, cam, J, p, ld, lw, out):
        R = J["R"]
        L = rig.LOOK[J["look"]]
        if _facing_head(cam, J) < -0.25:
            return
        Hd = Head(cam, J["head"], J["Bh"], R, L.get("head_shape"))
        upper = [(-1.30, -0.08, 1.03), (-1.16, -0.30, 1.04), (-0.92, -0.44, 1.045), (-0.62, -0.52, 1.05), (-0.36, -0.50, 1.05),
                 (0.36, -0.50, 1.05), (0.62, -0.52, 1.05), (0.92, -0.44, 1.045), (1.16, -0.30, 1.04), (1.30, -0.08, 1.03)]
        lower = [(1.26, -0.50, 1.06), (0.92, -0.86, 1.09), (0.45, -1.02, 1.12), (0.0, -1.07, 1.14), (-0.45, -1.02, 1.12),
                 (-0.92, -0.86, 1.09), (-1.26, -0.50, 1.06)]
        k = cam.proj(J["head"])[3]

        def draw():
            c = fr.c
            path = _surf_path(Hd, cam, upper + lower, k=0.7)
            if path is None:
                return
            if Hd.facing(0.0, -0.5) > 0.05:                         # the mouth shows through
                hole = skia.Path()
                op = max(0.0, p.get("mouth", 0.0))
                hole.addOval(skia.Rect(-0.25 * R, -0.09 * R, 0.25 * R, (0.11 + 0.3 * op) * R))
                hole.transform(Hd.decal(0.0, -0.50, 1.0))
                path = skia.Op(path, hole, skia.PathOp.kDifference_PathOp) or path
            fr.part(path, colr, ld, width=1.6 * R * k, line=lw, lit=0.14, dark=0.42)
            c.save()
            c.clipPath(path, skia.ClipOp.kIntersect, True)
            for i in range(14):                                     # short hair strokes, combed down
                lam, mu = -1.1 + i * 0.17, -0.55 - 0.25 * math.sin(i * 1.7) ** 2
                if Hd.facing(lam, mu) > 0.1:
                    a = cam.proj(Hd.surf(lam, mu, 1.08))
                    b = cam.proj(Hd.surf(lam * 0.95, mu - 0.14, 1.10))
                    c.drawLine(a[0], a[1], b[0], b[1], paint(shade(colr, -0.45), stroke=max(1.0, 0.02 * R * k), a=0.6))
            c.restore()
            if Hd.facing(0.0, -0.40) > 0.1:                         # moustache
                mu_pts = [(-0.36, -0.50, 1.06), (-0.22, -0.40, 1.07), (0.0, -0.37, 1.075), (0.22, -0.40, 1.07), (0.36, -0.50, 1.06),
                          (0.18, -0.45, 1.07), (0.0, -0.43, 1.075), (-0.18, -0.45, 1.07)]
                m = _surf_path(Hd, cam, mu_pts, k=0.6, min_face=0.0)
                if m is not None:
                    fr.part(m, shade(colr, -0.08), ld, width=0.8 * R * k, line=lw, lit=0.14, dark=0.4)
        parts.append(("face", 0.0, draw))
    return extra


def shirt_collar(colr):
    def extra(parts, fr, cam, J, p, ld, lw, out):
        L = rig.LOOK[J["look"]]
        if _facing_body(cam, J) < 0.1:
            return
        h, k = J["h"], _k(cam, J)

        def draw():
            c = fr.c
            for sg in (-1, 1):
                q = [cam.proj(chest(J, L, u, sg * x, 1.04))[:2] for u, x in ((0.296, 0.012), (0.292, 0.050), (0.255, 0.030), (0.262, 0.004))]
                path = smooth(q, k=0.2)
                fr.part(path, colr, ld, width=0.05 * h * k, line=lw, lit=0.12, dark=0.3)
            for u in (0.21, 0.15, 0.09):
                b = cam.proj(chest(J, L, u, 0.0, 1.03))
                c.drawCircle(b[0], b[1], 0.006 * h * k, paint("#e6dcc6"))
            q = [cam.proj(chest(J, L, u, 0.0, 1.02))[:2] for u in (0.25, 0.0)]
            c.drawLine(q[0][0], q[0][1], q[1][0], q[1][1], paint(shade(L["top"], -0.5), stroke=lw * 0.8))
        parts.append(("overtorso", 0.0, draw))
    return extra


rig.LOOK["maya"] = dict(h=1.66, skin="#b97d58", hair="#20150f", style="short", brow_mu=0.43, mu_front=0.66, top="#d6c4a2", pants="#2c2c38",
                        shoes="#e8e2d6", iris="#4a2c1a", build=0.92, brow=1.05, brow_col="#1c120c", head_shape=(0.97, 1.04, 0.0),
                        extras=(hair_bun("#20150f"), open_cardigan("#3a3d4a"), tears(), round_glasses()))
rig.LOOK["theo"] = dict(h=1.71, skin="#f2cfb3", hair="#6b3a22", style="messy", top="#4f8a8b", pants="#8b8f99",
                        shoes="#e9e9ef", iris="#6c7a3c", build=0.84, brow=0.9, brow_col="#4a2616", head_shape=(0.96, 1.0, 0.0),
                        extras=(hood("#4f8a8b"), hoodie_front("#4f8a8b"), neck_headphones(), freckles()))
rig.LOOK["frank"] = dict(h=1.80, skin="#e2ad8a", hair="#7d7770", style="short", top="#9a4a32", pants="#3a4458",
                         shoes="#3a2a20", iris="#5b7a96", build=1.14, brow=1.35, brow_col="#4d4640", head_shape=(1.04, 1.0, 0.14), mu_front=0.55,
                         extras=(beard("#8a8279"), shirt_collar("#ece3cf")))
