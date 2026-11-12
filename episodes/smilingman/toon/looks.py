"""Kuchisake-onna cast and props for the toon rig.

Costume layers plug into rig.draw through LOOK["extras"] (each fn appends (kind, depth, draw) parts; kinds
under / coat / overtorso / face / top slot into the fixed layering):
  onna  long straight black hair (front curtains + a back sheet), beige trench coat with a belt and lapels,
        a white surgical mask (pose mask 1 on .. 0 off, mask_hang 1 = hanging from her left ear), and the
        slit mouth (pose slit 0 closed line .. 1 open grin) running from cheek to cheek.
  kid   yellow school cap, navy shorts (bare knees, white socks), red randoseru backpack with straps.
Props: umbrella() is drawn after its holder (world space, above the head); scissors() is a held prop.
"""
import math

import skia

import rig
from rig import Head, add, dot, mul, norm, sub, smooth, capsule, union
from toon import argb, lin, paint, shade

SKIN_ONNA = "#efe4da"


# ---- small helpers ---------------------------------------------------------------------------------------
def _poly(pts):
    p = skia.Path()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    p.close()
    return p


def obox(fr, cam, B, o, xs, ys, zs, colr, line=1.6, k_top=0.12, k_side=-0.2):
    """Box in basis B (xs along r, ys along u, zs along f) at origin o; visible faces shaded."""
    (a0, a1), (u0, u1), (b0, b1) = xs, ys, zs
    P = lambda a, u, b: B.w(o, a, u, b)                      # noqa: E731
    faces = [((0, 0, 1), [(a0, u0, b1), (a1, u0, b1), (a1, u1, b1), (a0, u1, b1)], 0.0),
             ((0, 0, -1), [(a0, u0, b0), (a1, u0, b0), (a1, u1, b0), (a0, u1, b0)], 0.0),
             ((0, 1, 0), [(a0, u1, b0), (a1, u1, b0), (a1, u1, b1), (a0, u1, b1)], k_top),
             ((0, -1, 0), [(a0, u0, b0), (a1, u0, b0), (a1, u0, b1), (a0, u0, b1)], -0.4),
             ((1, 0, 0), [(a1, u0, b0), (a1, u0, b1), (a1, u1, b1), (a1, u1, b0)], k_side),
             ((-1, 0, 0), [(a0, u0, b0), (a0, u0, b1), (a0, u1, b1), (a0, u1, b0)], k_side)]
    for n, pts, k in faces:
        wn = B.d(*n)
        W = [P(*q) for q in pts]
        fc = mul(add(add(W[0], W[1]), add(W[2], W[3])), 0.25)
        if dot(wn, sub(cam.pos, fc)) <= 0:
            continue
        fr.poly(cam, W, colr=shade(colr, k), outline=shade(colr, -0.72), line=line)


def _faces_cam(J, cam, B=None):
    B = B or J["Bc"]
    return dot(B.f, norm(sub(cam.pos, J["pelvis"]))) > 0


def _vis_run(Hd, cam, pts_lm, lift=1.03, thr=0.04, closed=False):
    """Project head-surface points (lam, mu), keeping the longest visible contiguous run. closed: the list is a loop,
    so a run crossing its start is one run (the mask lost half its outline when she turned her head)."""
    pts_lm = list(pts_lm)
    if closed:
        vis = [Hd.facing(lam, mu) > thr for lam, mu in pts_lm]
        if not all(vis) and any(vis):
            i0 = vis.index(False)
            pts_lm = pts_lm[i0:] + pts_lm[:i0]
    best, cur = [], []
    for lam, mu in pts_lm:
        if Hd.facing(lam, mu) > thr:
            cur.append(cam.proj(Hd.surf(lam, mu, lift))[:2])
        else:
            best, cur = (cur if len(cur) > len(best) else best), []
    return cur if len(cur) > len(best) else best


# ---- onna --------------------------------------------------------------------------------------------------
def onna_coat(parts, fr, cam, J, p, ld, lw, out):
    h, Bb, P = J["h"], J["Bb"], J["pelvis"]
    L = rig.LOOK[J["look"]]
    # the skirt follows the knees a little, so a stepping knee does not poke through the front
    kf = sum(dot(sub(J["kn_" + s], P), Bb.f) for s in ("R", "L")) / 2
    rings = []
    for u, wa, db, f in ((0.02, 0.098, 0.070, 0.0), (-0.05, 0.110, 0.080, 0.25), (-0.13, 0.121, 0.088, 0.6),
                         (-0.20, 0.130, 0.095, 0.85), (-0.255, 0.136, 0.100, 1.0)):
        rings.append((u * h, wa * h * L["build"], db * h, 0.0, kf * f * 0.55))
    path, z = rig.lathe(cam, P, Bb, rings)
    belt, _ = rig.lathe(cam, P, Bb, [(0.012 * h, 0.101 * h * L["build"], 0.073 * h, 0, 0),
                                     (-0.016 * h, 0.104 * h * L["build"], 0.075 * h, 0, 0)])
    k = cam.proj(P)[3]

    def fn():
        fr.part(path, L["top"], ld, width=0.26 * h * k, line=lw, lit=0.12, dark=0.42)
        if _faces_cam(J, cam, Bb):                           # front opening of the coat
            a, b = cam.proj(Bb.w(P, 0.0, 0.0, 0.074 * h)), cam.proj(Bb.w(P, 0.012 * h, -0.25 * h, 0.10 * h + kf * 0.55))
            fr.c.drawLine(a[0], a[1], b[0], b[1], paint(shade(L["top"], -0.5), stroke=lw * 1.1))
        fr.part(belt, shade(L["top"], -0.32), ld, width=0.05 * h * k, line=lw, lit=0.1, dark=0.3)
    parts.append(("coat", z, fn))

    def lapels():
        if not _faces_cam(J, cam):
            return
        Bc = J["Bc"]
        for sg in (1, -1):
            q = [cam.proj(Bc.w(P, sg * a * h, u * h, b * h))[:2] for a, u, b in
                 ((0.035, 0.295, 0.045), (0.075, 0.27, 0.075), (0.02, 0.19, 0.085), (0.0, 0.17, 0.086))]
            fr.c.drawPath(smooth(q, closed=False, k=0.5), paint(shade(L["top"], -0.45), stroke=lw * 1.2))
        for u in (0.12, 0.06):                               # two coat buttons
            x, y, _, s = cam.proj(Bc.w(P, 0.035 * h, u * h, 0.088 * h))
            fr.c.drawCircle(x, y, 0.008 * h * s, paint(shade(L["top"], -0.55)))
    parts.append(("overtorso", z, lapels))


def onna_hair(parts, fr, cam, J, p, ld, lw, out):
    h, R, P, Bc, Bh = J["h"], J["R"], J["pelvis"], J["Bc"], J["Bh"]
    L = rig.LOOK[J["look"]]
    Hd = Head(cam, J["head"], Bh, R)
    k = cam.proj(J["head"])[3]
    front = dot(Bh.f, norm(sub(cam.pos, J["head"]))) > 0
    hair = L["hair"]

    q = [Hd.surf(-1.30, 0.95, 1.05), Hd.surf(-1.55, -0.2, 1.10), Hd.surf(-2.3, -0.55, 1.12), Bc.w(P, 0.08 * h, 0.31 * h, -0.105 * h), Bc.w(P, 0.115 * h, 0.235 * h, -0.085 * h),
         Bc.w(P, 0.10 * h, 0.12 * h, -0.115 * h), Bc.w(P, 0.0, 0.105 * h, -0.125 * h), Bc.w(P, -0.10 * h, 0.12 * h, -0.115 * h),
         Bc.w(P, -0.115 * h, 0.235 * h, -0.085 * h), Bc.w(P, -0.08 * h, 0.31 * h, -0.105 * h), Hd.surf(2.3, -0.55, 1.12), Hd.surf(1.55, -0.2, 1.10), Hd.surf(1.30, 0.95, 1.05), Hd.surf(math.pi, 1.20, 1.03)]   # top at the crown: no edge across the back of the head
    sheet_path = smooth(rig._hull([tuple(cam.proj(w)[:2]) for w in q]), k=0.8)   # hull: edge-on it folded and left holes

    def sheet():                                             # long hair down her back
        fr.part(sheet_path, shade(hair, -0.05), (ld[0] * 0.5, 1.0), width=2 * R * k, line=lw, lit=0.14, dark=0.5)
        if not front:                                         # a few strands catching the lamp
            for a in (-0.05, 0.03, 0.08):
                s0, s1 = cam.proj(Bh.w(J["head"], a * h, 0.0, -1.05 * R)), cam.proj(Bc.w(P, a * h * 1.2, 0.13 * h, -0.08 * h))
                fr.c.drawLine(s0[0], s0[1], s1[0], s1[1], paint("#5a6a8a", a=0.35, stroke=lw * 0.8))
    parts.append(("under" if front else "face", J["head"][2], sheet))

    # two straight curtains framing the face, over the shoulders. A side turned away goes under the head (over the
    # coat) so the head hides it; skipping it popped the strand off in one frame (15.83 s)
    near = []
    for sg in (1, -1):                                       # sg = +1 the character's right (screen-left when facing us)
        lam = -sg
        q = [Hd.surf(lam * 0.80, 0.62, 1.07), Hd.surf(lam * 1.18, 0.30, 1.12), Hd.surf(lam * 1.22, -0.55, 1.15),
             Bc.w(P, sg * 0.105 * h, 0.235 * h, 0.035 * h), Bc.w(P, sg * 0.10 * h, 0.15 * h, 0.062 * h),
             Bc.w(P, sg * 0.06 * h, 0.145 * h, 0.08 * h), Bc.w(P, sg * 0.055 * h, 0.235 * h, 0.07 * h),
             Hd.surf(lam * 0.92, -0.75, 1.06), Hd.surf(lam * 0.84, -0.1, 1.04), Hd.surf(lam * 0.74, 0.40, 1.04),
             Hd.surf(lam * 0.66, 0.62, 1.05)]                # top tucked up inside the hair cap
        path = smooth([cam.proj(w)[:2] for w in q], k=0.7)
        facing = Hd.facing(lam * 1.0, 0.1) > -0.45           # switch only once its top is over the back of the head (hair on hair)

        def curtain(path=path):
            fr.part(path, hair, (ld[0] * 0.5, 1.0), width=0.9 * R * k, line=lw, lit=0.16, dark=0.45, rim=0.1)
        parts.append(("face" if facing else "overtorso", J["head"][2], curtain))
        if facing:
            near.append(path)

    def curtains():
        drawn = skia.Path(sheet_path) if front else None    # hair the cap may merge into (the sheet sits behind the head when front)
        for path in near:
            drawn = path if drawn is None else skia.Op(drawn, path, skia.PathOp.kUnion_PathOp)
        if drawn is None:
            return
        # cap again, no outline, plus a hair-coloured stroke clipped to the other hair: no seam where hair meets hair,
        # the hairline outline against the skin stays
        cap = rig.hair_path(Hd, cam, L)
        if not front:
            # from behind only the near curtain's top needs covering: a full cap laid over the back sheet popped the
            # round skull into view the frame a curtain became near (R2 turn, 70.03 s)
            fr.c.save()
            fr.c.clipPath(drawn, skia.ClipOp.kIntersect, True)
        fr.part(cap, hair, (ld[0] * 0.5, 1.0), width=2 * R * k, line=lw, lit=0.16, dark=0.45, rim=0.12, outline=False)
        if not front:
            fr.c.restore()
        fr.c.save()
        fr.c.clipPath(drawn, skia.ClipOp.kIntersect, True)
        fr.c.drawPath(cap, paint(shade(hair, -0.05), stroke=lw * 1.6))
        fr.c.restore()
    parts.append(("face", J["head"][2], curtains))


HANG_SIDE = 1                    # Head.surf longitude sign of her LEFT ear (-r), where the mask ends up hanging


def onna_face(parts, fr, cam, J, p, ld, lw, out):
    """Mask, the hanging mask and the slit mouth, all on the head surface."""
    R, Bh = J["R"], J["Bh"]
    Hd = Head(cam, J["head"], Bh, R)
    k = cam.proj(J["head"])[3]
    m = p.get("mask", 0.0)
    slit = p.get("slit", -1.0)
    talk = p.get("mask_talk", 0.0)

    def mouth():
        if slit < 0 or Hd.facing(0.0, -0.45) < -0.1:
            return
        n = 25
        lams = [-1.02 + 2.04 * i / (n - 1) for i in range(n)]
        up = [(a, -0.47 + 0.30 * a * a) for a in lams]                    # rises toward the ears
        op = max(0.0, slit)
        lo = [(a, -0.47 + 0.30 * a * a - op * 0.30 * max(0.0, 1 - (a / 0.62) ** 2) - 0.02) for a in lams]
        U, D = _vis_run(Hd, cam, up, 1.012), _vis_run(Hd, cam, lo, 1.012)
        if len(U) < 3 or len(D) < 3:
            return
        c = fr.c
        shape = smooth(U + D[::-1], k=0.5)
        c.drawPath(shape, paint("#2a0507"))
        if op > 0.05:                                        # teeth: a pale band under the upper edge, then gaps
            c.save()
            c.clipPath(shape, skia.ClipOp.kIntersect, True)
            T = _vis_run(Hd, cam, [(a, mu - 0.055 * op) for a, mu in up if abs(a) < 0.6], 1.012)
            if len(T) > 2:
                c.drawPath(smooth(T, closed=False), paint("#e8e2d6", stroke=0.13 * R * k * op))
                for i in range(1, len(T) - 1, 2):
                    c.drawLine(T[i][0], T[i][1] - 0.07 * R * k, T[i][0], T[i][1] + 0.07 * R * k, paint("#2a0507", stroke=0.018 * R * k))
            c.restore()
        c.drawPath(smooth(U, closed=False), paint("#5a0d12", stroke=0.05 * R * k))
        c.drawPath(smooth(D, closed=False), paint("#5a0d12", stroke=0.04 * R * k))
        for i in (2, 5, n - 6, n - 3):                       # stitch nicks across the outer cuts
            a, mu = up[i]
            if Hd.facing(a, mu) > 0.05:
                p0, p1 = cam.proj(Hd.surf(a, mu + 0.06, 1.012)), cam.proj(Hd.surf(a, mu - 0.08, 1.012))
                c.drawLine(p0[0], p0[1], p1[0], p1[1], paint("#5a0d12", stroke=0.022 * R * k))

    def mask():
        if m <= 0.12 or Hd.facing(0.0, -0.4) < -0.15:      # below 0.12 the hanging mask (hang) has taken over
            return
        drop = (1 - m) * 0.55
        top, bot, wide = -0.04 - drop, -0.86 - drop * 0.5, 0.66
        puff = 1.035 + 0.02 * talk
        # coming off, it folds toward the ear it will hang from, so it never vanishes in place
        w = min(1.0, m * 1.15)
        A = HANG_SIDE * wide
        fold = lambda e: [(A + (a - A) * w, mu) for a, mu in e]          # noqa: E731
        edge = fold([(-wide + 2 * wide * i / 14, top) for i in range(15)] +
                    [(wide - 0.05 * i / 6, top + (bot + 0.06 - top) * i / 6) for i in range(1, 7)] +
                    [(wide * 0.82 - 2 * wide * 0.82 * i / 14, bot) for i in range(15)] +
                    [(-wide + 0.05 * (6 - i) / 6, top + (bot + 0.06 - top) * (6 - i) / 6) for i in range(0, 6)])
        pts = _vis_run(Hd, cam, edge, puff, thr=-0.05, closed=True)
        if len(pts) < 5:
            return
        path = smooth(pts, k=0.4)
        fr.part(path, "#f1f1ec", (ld[0] * 0.5, 1.0), width=1.4 * R * k, line=lw, lit=0.10, dark=0.24)
        for mu in (top - 0.22, top - 0.42, top - 0.60):      # pleats
            q = _vis_run(Hd, cam, fold([(-wide * 0.9 + 1.8 * wide * 0.9 * i / 10, mu) for i in range(11)]), puff + 0.004)
            if len(q) > 2:
                fr.c.drawPath(smooth(q, closed=False), paint("#b8bcc6", stroke=0.02 * R * k))
        for sg in (-1, 1):                                   # ear loops (the far one is in her hand while it comes off)
            if m < 0.98 and sg != HANG_SIDE:
                continue
            if Hd.facing(sg * 1.2, -0.2) > -0.2:
                q = _vis_run(Hd, cam, [(sg * (wide + (1.12 - wide) * i / 6), top - 0.05 - 0.02 * i) for i in range(7)], 1.04, thr=0.05)   # ends under the hair curtain, never out over it
                if len(q) > 1:
                    fr.c.drawPath(smooth(q, closed=False), paint("#e8e8e2", stroke=0.025 * R * k))

    def hang():
        mh = min(1.0, p.get("mask_hang", 0.0))
        if mh <= 0.02:
            return
        # hangs from her LEFT ear (-r side), swinging a little; loop from the ear down to the mask; grows in (mh) as
        # the folding face mask (mask) shrinks toward this ear
        sw = math.sin(p.get("t", 0.0) * 2.1) * 0.06 * R
        ear = Bh.w(J["head"], -1.0 * R, -0.34 * R, -0.12 * R)      # behind the jaw, under the near hair curtain
        c0 = add(ear, mul(add(mul(J["Bc"].u, -0.55 * R), mul(Bh.r, -0.08 * R + sw), mul(Bh.f, 0.1 * R)), mh))
        q = [add(c0, add(mul(Bh.r, a * R * mh), mul(J["Bc"].u, u * R * mh))) for a, u in ((-0.22, 0.18), (0.22, 0.2), (0.2, -0.22), (-0.2, -0.24))]
        P = [cam.proj(w)[:2] for w in q]
        e = cam.proj(ear)[:2]
        fr.c.drawLine(e[0], e[1], P[0][0], P[0][1], paint("#e8e8e2", stroke=0.025 * R * k))
        fr.c.drawLine(e[0], e[1], P[1][0], P[1][1], paint("#e8e8e2", stroke=0.025 * R * k))
        fr.part(_poly(P), "#f1f1ec", ld, width=0.5 * R * k, line=lw, lit=0.1, dark=0.25)
    def handprint():
        """Timmy's red handprint on her right cheek (pose handprint 0..1), over the mask edge and the skin."""
        a = p.get("handprint", 0.0)
        if a <= 0.02:
            return
        c0, d, n = (-0.70, -0.40), (-0.40, 0.92), (0.92, 0.40)          # palm centre; fingers point up toward her ear
        blobs = [(c0, 0.21, 0.20, 0.0)]
        for i, off in enumerate((-0.19, -0.065, 0.065, 0.19)):
            ln = (0.26, 0.34, 0.32, 0.25)[i]
            blobs.append(((c0[0] + n[0] * off + d[0] * (0.17 + ln / 2), c0[1] + n[1] * off + d[1] * (0.17 + ln / 2)), 0.05, ln / 2, 0.0))
        blobs.append(((c0[0] + 0.24, c0[1] - 0.12), 0.055, 0.14, -0.9))          # thumb
        for (cl, cm), rw, rl, rot in blobs:
            ang = math.atan2(d[1], d[0]) + rot
            ca, sa = math.cos(ang), math.sin(ang)
            ring = [(cl + rl * math.cos(t) * ca - rw * math.sin(t) * sa, cm + rl * math.cos(t) * sa + rw * math.sin(t) * ca)
                    for t in [2 * math.pi * i / 16 for i in range(16)]]
            pts = _vis_run(Hd, cam, ring, 1.045, thr=0.18, closed=True)
            if len(pts) > 4:
                fr.c.drawPath(smooth(pts, k=0.4), paint("#d42a35", a=0.72 * a))
    parts.append(("face", J["head"][2], mouth))
    parts.append(("face", J["head"][2] - 1e-4, mask))
    parts.append(("face", J["head"][2] - 2e-4, handprint))
    # drawn before the hair curtains (equal kind sorts by the larger key first) so the near curtain covers the loop's
    # ear end; when that ear faces away the mask hangs behind her (it was painted across her nose)
    far = Hd.facing(HANG_SIDE * 1.45, -0.3) < -0.05
    parts.append(("under" if far else "face", J["head"][2] + 1e-4, hang))


# ---- kid -----------------------------------------------------------------------------------------------------
def kid_legs(parts, fr, cam, J, p, ld, lw, out):
    """Shorts: bare knees and shins, white knee socks, the shoes redrawn on top."""
    h = J["h"]
    L = rig.LOOK[J["look"]]
    for s in ("R", "L"):
        hp, kn, an = cam.proj(J["hip_" + s]), cam.proj(J["kn_" + s]), cam.proj(J["ank_" + s])
        k = hp[3]
        th = (hp[0] + (kn[0] - hp[0]) * 0.62, hp[1] + (kn[1] - hp[1]) * 0.62)
        so = (kn[0] + (an[0] - kn[0]) * 0.45, kn[1] + (an[1] - kn[1]) * 0.45)
        skin_p = union(capsule(th, 0.038 * h * k, kn[:2], 0.036 * h * k), capsule(kn[:2], 0.036 * h * k, so, 0.031 * h * k))
        sock = capsule(so, 0.033 * h * k, an[:2], 0.029 * h * k)
        shoe, sole = rig.shoe_paths(cam, J["ank_" + s], J["Bb"].f, h)
        hem = capsule(hp[:2], 0.056 * h * k, th, 0.052 * h * k)

        def fn(skin_p=skin_p, sock=sock, shoe=shoe, sole=sole, hem=hem, k=k):
            fr.part(skin_p, L["skin"], ld, width=0.08 * h * k, line=lw)
            fr.part(sock, "#eceef2", ld, width=0.07 * h * k, line=lw)
            fr.part(hem, L["pants"], ld, width=0.1 * h * k, line=lw)
            fr.part(shoe, L["shoes"], ld, width=0.07 * h * k, line=lw, lit=0.3)
            fr.c.drawPath(sole, paint(shade(L["shoes"], -0.35)))
            fr.c.drawPath(shoe, paint(shade(L["shoes"], -0.72), stroke=lw))
        parts.append(("coat", (hp[2] + an[2]) / 2 + (0.001 if s == "L" else 0), fn))


def kid_pack(parts, fr, cam, J, p, ld, lw, out):
    h, P, Bc = J["h"], J["pelvis"], J["Bc"]
    if p.get("nopack"):                              # taken off (smilingman): drawn as a prop instead
        return
    back_view = not _faces_cam(J, cam)
    red = "#c0262c"

    def pack():
        obox(fr, cam, Bc, P, (-0.088 * h, 0.088 * h), (0.105 * h, 0.27 * h), (-0.17 * h, -0.075 * h), red, line=lw)
        obox(fr, cam, Bc, P, (-0.091 * h, 0.091 * h), (0.14 * h, 0.275 * h), (-0.176 * h, -0.168 * h), shade(red, 0.08), line=lw)
        x, y, _, s = cam.proj(Bc.w(P, 0.0, 0.15 * h, -0.178 * h))
        if back_view:
            fr.c.drawRoundRect(skia.Rect(x - 0.012 * h * s, y - 0.008 * h * s, x + 0.012 * h * s, y + 0.008 * h * s),
                               0.004 * h * s, 0.004 * h * s, paint("#e2b84a"))
    parts.append(("overtorso" if back_view else "under", P[2], pack))

    def straps():
        if back_view:
            return
        for sg in (1, -1):
            q = [cam.proj(Bc.w(P, sg * a * h, u * h, b * h))[:2] for a, u, b in ((0.06, 0.29, 0.0), (0.07, 0.25, 0.07), (0.075, 0.15, 0.072))]
            fr.c.drawPath(smooth(q, closed=False), paint("#1a1a22", stroke=0.022 * h * cam.proj(P)[3]))
    parts.append(("overtorso", P[2], straps))


def kid_cap(parts, fr, cam, J, p, ld, lw, out):
    R, Bh = J["R"], J["Bh"]
    Hd = Head(cam, J["head"], Bh, R)
    k = cam.proj(J["head"])[3]
    yel = "#d9a43a"                                # mustard knit beanie

    # the rim is a tilted plane cut (brow line in front, low at the back): the cap stays convex on screen
    mu_f, mu_b = 0.52, -0.05
    ta = math.atan((math.sin(mu_b) - math.sin(mu_f)) / (math.cos(mu_f) + math.cos(mu_b)))
    cn, sn = math.cos(ta), math.sin(ta)
    d0 = cn * math.sin(mu_f) + sn * math.cos(mu_f)

    def edge_mu(lam):
        A, Bq = cn, sn * math.cos(lam)
        return math.asin(max(-1.0, min(1.0, d0 / math.hypot(A, Bq)))) - math.atan2(Bq, A)

    c_v = cam.view(J["head"])

    def facing(w):                                 # >0 where the knit surface faces the camera
        v = cam.view(w)
        nrm = (v[0] - c_v[0], v[1] - c_v[1], v[2] - c_v[2])
        return -(nrm[0] * v[0] + nrm[1] * v[1] + nrm[2] * v[2]) / (math.sqrt(sum(q * q for q in nrm)) * math.sqrt(sum(q * q for q in v))) + 0.03

    def cap():
        # crown = hull of the camera-facing part of the dome. The edge points are interpolated to where the surface
        # turns away (not snapped to grid samples): a sample flipping in/out made the outline jump on head trembles
        NL, NT = 64, 7
        P, F = [], []
        for i in range(NL):
            lam = 2 * math.pi * i / NL
            m0 = edge_mu(lam)
            ws = [Hd.surf(lam, m0 + (math.pi / 2 - m0) * t / (NT - 1), 1.025 + 0.065 * math.sqrt(t / (NT - 1))) for t in range(NT)]   # hugs the head at the edge, puffs above (no brim lip)
            P.append([cam.proj(w)[:2] for w in ws])
            F.append([facing(w) for w in ws])
        crown = []
        for i in range(NL):
            for t in range(NT):
                if F[i][t] > 0:
                    crown.append(tuple(P[i][t]))
                for i2, t2 in (((i + 1) % NL, t), (i, t + 1)):
                    if t2 < NT and (F[i][t] > 0) != (F[i2][t2] > 0):
                        s = F[i][t] / (F[i][t] - F[i2][t2])
                        crown.append((P[i][t][0] + s * (P[i2][t2][0] - P[i][t][0]), P[i][t][1] + s * (P[i2][t2][1] - P[i][t][1])))
        if len(crown) < 3:
            return
        hull = smooth(rig._hull(crown), k=0.6)

        def vis_run(gf, ptf, N=48):
            """Points ptf(lam) along the rim where gf(lam) > 0, as one run with its two ends found by bisection
            (grid-snapped ends popped). Returns [] or [(lam, pts), ...]; a closed ring when all is visible."""
            dl = 2 * math.pi / N
            vis = [gf(dl * i) > 0 for i in range(N)]
            if all(vis):
                return [(dl * i, ptf(dl * i)) for i in range(N)]

            def cross(a0, a1):
                for _ in range(14):
                    am = 0.5 * (a0 + a1)
                    if (gf(am) > 0) == (gf(a0) > 0):
                        a0 = am
                    else:
                        a1 = am
                return 0.5 * (a0 + a1)
            start = vis.index(False)                    # walk from a hidden point so the run never wraps
            out = []
            for j in range(1, N + 1):
                a_i = dl * (start + j)
                if not vis[(start + j) % N]:
                    if out:
                        c = cross(a_i - dl, a_i)
                        out.append((c, ptf(c)))
                        break
                    continue
                if not out:
                    c = cross(a_i - dl, a_i)
                    out.append((c, ptf(c)))
                out.append((a_i, ptf(a_i)))
            return out

        # cut the crown along the visible rim: a straight hull bottom left a thin lip past the face at the sides
        rim = vis_run(lambda a: facing(Hd.surf(a, edge_mu(a), 1.025)), lambda a: cam.proj(Hd.surf(a, edge_mu(a), 1.025))[:2])
        fr.c.save()
        if 1 < len(rim) < 48:
            pts = [q for _, q in rim]
            top = cam.proj(Hd.surf(0.0, math.pi / 2, 1.09))[:2]
            cx, cy = sum(q[0] for q in pts) / len(pts), sum(q[1] for q in pts) / len(pts)
            ux, uy = top[0] - cx, top[1] - cy
            n = math.hypot(ux, uy) or 1.0
            ux, uy = ux / n * 4 * R * k, uy / n * 4 * R * k
            clip = skia.Path()
            ex = []
            for q in (pts[-1], pts[0]):
                ox, oy = q[0] - cx, q[1] - cy
                m = math.hypot(ox, oy) or 1.0
                ex.append((q[0] + ux + ox / m * 0.8 * R * k, q[1] + uy + oy / m * 0.8 * R * k))
            clip.moveTo(*pts[0])
            for q in pts[1:]:
                clip.lineTo(*q)
            clip.lineTo(*ex[0])
            clip.lineTo(*ex[1])
            clip.close()
            fr.c.clipPath(clip, skia.ClipOp.kIntersect, True)
        fr.part(hull, yel, (ld[0] * 0.5, 1.0), width=2.2 * R * k, line=lw, lit=0.18, dark=0.4)
        if 1 < len(rim) < 48:                           # the cut edge needs its own outline
            fr.c.drawPath(smooth([q for _, q in rim], closed=False, k=0.4), paint(shade(yel, -0.72), stroke=lw))
        fr.c.restore()
        # the folded cuff: a darker ribbed band along the rim where both its edges face the camera
        band = vis_run(lambda a: min(Hd.facing(a, edge_mu(a) + 0.02), Hd.facing(a, edge_mu(a) + 0.30)) - 0.02,
                       lambda a: (cam.proj(Hd.surf(a, edge_mu(a) + 0.02, 1.028))[:2], cam.proj(Hd.surf(a, edge_mu(a) + 0.30, 1.052))[:2]))
        if len(band) > 2:
            lo, hi = [b[0] for _, b in band], [b[1] for _, b in band]
            fr.part(smooth(lo + hi[::-1], k=0.4), shade(yel, -0.12), (ld[0] * 0.5, 1.0), width=0.5 * R * k, line=lw, lit=0.1, dark=0.3)
            for _, (a, b) in band[1:-1]:
                fr.c.drawLine(a[0], a[1], b[0], b[1], paint(shade(yel, -0.4), a=0.55, stroke=0.018 * R * k))
    parts.append(("face", J["head"][2], cap))


rig.LOOK.update({
    "onna": dict(h=1.74, skin=SKIN_ONNA, hair="#0a0a0e", style="long", top="#b59c74", pants="#24242c",
                 shoes="#141418", iris="#1c1210", build=0.86, brow=0.75,
                 extras=(onna_coat, onna_hair, onna_face), arms_under_hair=True),
    "kid": dict(h=1.22, skin="#f1c7a6", hair="#16120e", style="buzz", top="#2c3656", pants="#232a44",
                shoes="#3a2a20", iris="#2a1d16", build=0.86, brow=0.9, extras=(kid_legs, kid_pack, kid_cap)),
    # the school-gate crowd and the flashback
    "par1": dict(h=1.70, skin="#e9bf9b", hair="#1a1612", style="neat", top="#5a5f6e", pants="#2f3340",
                 shoes="#1d1f27", iris="#2a1d16", build=1.02, brow=1.0),
    "par2": dict(h=1.60, skin="#efc6a4", hair="#2a1e16", style="neat", top="#7a5a4a", pants="#3e3a48",
                 shoes="#2a2630", iris="#3a2a20", build=0.9, brow=0.8, back=True),
    "par3": dict(h=1.66, skin="#e6b78f", hair="#141210", style="buzz", top="#3f5a4a", pants="#2a2e38",
                 shoes="#1d1f27", iris="#2a1d16", build=1.0, brow=1.0),
    "kid2": dict(h=1.18, skin="#efc6a4", hair="#1a1410", style="neat", top="#2c3656", pants="#232a44",
                 shoes="#3a2a20", iris="#2a1d16", build=0.85, brow=0.85, back=True, extras=(kid_legs, kid_pack, kid_cap)),
    "kid3": dict(h=1.26, skin="#e6b78f", hair="#0e0c0a", style="messy", top="#2c3656", pants="#232a44",
                 shoes="#3a2a20", iris="#2a1d16", build=0.88, brow=0.9, extras=(kid_legs, kid_pack, kid_cap)),
})


# ---- props -------------------------------------------------------------------------------------------------
def umbrella(fr, cam, hand, axis=(0.0, 1.0, 0.0), length=0.78, radius=0.52, colr="#16161c", clear=False, T=0.0,
             open_k=1.0, drips=True):
    """Umbrella from the hand along `axis` (world): shaft, J-handle, a 8-panel canopy; seen from below it shows
    its ribs. Returns the canopy rim points (world) for rain sheltering."""
    ax = norm(axis)
    top = add(hand, mul(ax, length))
    t1 = norm(rig.cross(ax, (0.0, 0.0, 1.0) if abs(ax[2]) < 0.9 else (1.0, 0.0, 0.0)))
    t2 = rig.cross(ax, t1)
    rr = radius * (0.25 + 0.75 * open_k)
    drop = 0.26 * open_k + 0.42 * (1 - open_k)
    rim = [add(top, mul(ax, -drop), mul(t1, rr * math.cos(2 * math.pi * i / 8)), mul(t2, rr * math.sin(2 * math.pi * i / 8)))
           for i in range(8)]
    apex = add(top, mul(ax, 0.06))
    s_h, s_t = cam.proj(hand), cam.proj(apex)
    if min(s_h[2], s_t[2]) < 0.2:
        return rim
    k = s_h[3]
    fr.c.drawLine(s_h[0], s_h[1], s_t[0], s_t[1], paint("#2a2a30" if not clear else "#d8dde6", stroke=max(1.5, 0.012 * k)))
    hook = cam.proj(add(hand, mul(ax, -0.08)))
    fr.c.drawLine(s_h[0], s_h[1], hook[0], hook[1], paint("#3a2a1e", stroke=max(2.0, 0.022 * k)))
    # panels back to front
    panels = []
    for i in range(8):
        a, b = rim[i], rim[(i + 1) % 8]
        mid = mul(add(add(a, b), apex), 1 / 3)
        nrm = rig.cross(sub(a, apex), sub(b, apex))
        panels.append((cam.view(mid)[2], i, [apex, a, b], dot(nrm, sub(cam.pos, mid)) > 0))
    for _, i, tri, outside in sorted(panels, key=lambda q: -q[0]):
        sh = (0.1 if i % 2 else -0.08) + (0.0 if outside else -0.25)
        if clear:
            fr.poly(cam, tri, colr="#cfe0f0", a=0.22 if outside else 0.16, outline="#e8f2ff", line=1.3)
        else:
            fr.poly(cam, tri, colr=shade(colr, sh), outline=shade(colr, -0.6), line=1.5)
    if drips and open_k > 0.8:                               # drops falling off the rim tips
        for i, q in enumerate(rim):
            u = (T * 1.6 + i * 0.37) % 1.0
            d = add(q, (0, -u * u * 1.4, 0))
            x, y, z, s = cam.proj(d)
            if z > 0.3:
                fr.c.drawLine(x, y, x, y + 0.03 * s, paint("#bcd0f0", a=0.6 * (1 - u), stroke=max(1.0, 0.006 * s)))
    return rim


def scissors(open_deg=10.0, out_k=1.0):
    """Long tailor's shears in the fist: two blades along the forearm, pivot just past the hand."""
    def fn(fr, cam, J, s, hd, fd, k):
        if out_k <= 0.01:
            return
        h = J["h"]
        d = rig._screen_dir(cam, J["wr_" + s], fd)
        Ln = 0.24 * h * k * out_k
        piv = (hd[0] + d[0] * 0.035 * h * k * out_k, hd[1] + d[1] * 0.035 * h * k * out_k)
        for sgn, colr in ((1, "#c9ced8"), (-1, "#e9edf4")):
            a = math.atan2(d[1], d[0]) + sgn * math.radians(open_deg / 2)
            v = (math.cos(a), math.sin(a))
            n = (-v[1], v[0])
            tip = (piv[0] + v[0] * Ln, piv[1] + v[1] * Ln)
            wb = 0.016 * h * k
            blade = _poly([(piv[0] + n[0] * wb * sgn, piv[1] + n[1] * wb * sgn), tip, (piv[0] - n[0] * wb * 0.3 * sgn, piv[1] - n[1] * wb * 0.3 * sgn)])
            fr.c.drawPath(blade, paint(shader=lin(piv, (piv[0] + n[0] * wb, piv[1] + n[1] * wb), [argb("#7d8596"), argb(colr)])))
            fr.c.drawPath(blade, paint("#1c2028", stroke=max(1.2, 0.0035 * h * k)))
            # finger loop behind the pivot
            back = (hd[0] - v[0] * 0.02 * h * k, hd[1] - v[1] * 0.02 * h * k)
            fr.c.drawCircle(back[0] + n[0] * sgn * 0.012 * h * k, back[1] + n[1] * sgn * 0.012 * h * k, 0.016 * h * k,
                            paint("#20232c", stroke=max(1.5, 0.008 * h * k)))
        fr.c.drawCircle(piv[0], piv[1], 0.006 * h * k, paint("#3a3e48"))
        fr.glow(piv[0] + d[0] * Ln * 0.6, piv[1] + d[1] * Ln * 0.6, 0.04 * h * k, "#ffffff", a=0.25)
        J["prop_tip"] = (piv[0] + d[0] * Ln, piv[1] + d[1] * Ln)
    fn.under = True              # drawn before the hand: the fist covers the loops and the blade roots (they clipped the palm)
    return fn


SWEET_COLS = ("#e8434a", "#f2c51c", "#5ab0e8", "#7ad06a", "#f08ad0", "#ffffff")


def sweet(fr, cam, pos, spin, colr, size=0.035):
    """A wrapped sweet: a shiny oval with twisted wrapper ends (world centre, size in metres)."""
    x, y, z, s = cam.proj(pos)
    if z < 0.3:
        return
    r = size * s
    m = skia.Matrix()
    m.setRotate(math.degrees(spin))
    m.postTranslate(x, y)
    body = skia.Path()
    body.addOval(skia.Rect(-r, -r * 0.62, r, r * 0.62))
    ends = _poly([(-r * 0.8, 0), (-r * 1.9, -r * 0.7), (-r * 1.9, r * 0.7)])
    ends2 = _poly([(r * 0.8, 0), (r * 1.9, -r * 0.7), (r * 1.9, r * 0.7)])
    pth = union(body, ends, ends2)
    pth.transform(m)
    fr.part(pth, colr, (0.3, 1.0), width=2 * r, line=max(1.0, 0.12 * r), lit=0.4, dark=0.4)
    fr.c.drawCircle(x - 0.3 * r, y - 0.25 * r, 0.22 * r, paint("#ffffff", a=0.7))
