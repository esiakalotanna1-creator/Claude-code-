"""Connected cartoon character rigs for the toon renderer.

A character is a small 3D skeleton (pelvis, chest, neck, head, shoulder-elbow-wrist, hip-knee-ankle)
posed in world space and drawn through the camera. Body volumes are lathed from elliptic rings, so the
same design holds from the front, three-quarter and side views; face features are decals placed on the
head surface, so they foreshorten and turn with the head. Limbs keep their lengths: arms and legs are
2-bone chains (FK angles or IK targets), feet are IK-planted at given world ankle positions.

    j = draw(fr, cam, "jeff", pose, light=(0, 2.4, 6.2))
    j["hand_R"], j["head"], j["ankle_L"] ...      # screen/world joints for props and the checks
"""
import math

import skia

from toon import Frame, paint, shade, argb, lin, rad, hexrgb, mix  # noqa: F401

# ---- design ----------------------------------------------------------------------------------------
LOOK = {
    "jeff": dict(h=1.70, skin="#f1c7a6", hair="#3a2a22", style="messy", top="#e6e9f0", pants="#4b556b",
                 shoes="#262a36", iris="#4f7396", build=1.0, hood=True, brow=1.0),
    "liu": dict(h=1.56, skin="#f1c7a6", hair="#17181f", style="neat", top="#5f7f52", pants="#30598a",
                shoes="#22252e", iris="#3d2f28", build=0.92, hood=True, brow=0.9),
    "randy": dict(h=1.80, skin="#efc19c", hair="#d8772c", style="spiky", top="#b73a3c", pants="#3a3f4c",
                  shoes="#e9e9ee", iris="#5d8a4a", build=1.14, hood=False, brow=1.15),
    "bully": dict(h=1.74, skin="#a66f4d", hair="#16161c", style="buzz", top="#5b3e7a", pants="#7a5a3d",
                  shoes="#1d1f27", iris="#2a1d16", build=1.08, hood=False, brow=1.1),
    "bully2": dict(h=1.68, skin="#e6b78f", hair="#5b3b22", style="messy", top="#6d7a8c", pants="#5b4734",
                   shoes="#1d1f27", iris="#3e5f7a", build=1.0, hood=True, brow=1.0),
    # after the fire: bone-white skin, black hair, hospital gown (face only ever seen bandaged or from behind)
    "jeffw": dict(h=1.70, skin="#efedea", hair="#0e0e12", style="messy", top="#9fb8cc", pants="#9fb8cc",
                  shoes="#d6dae3", iris="#4f7396", build=1.0, brow=1.0),
    # the reveal: carved smile, lidless dark-ringed eyes, long black hair, white top
    "jeffk": dict(h=1.70, skin="#f3f2ef", hair="#0b0b0f", style="messy", top="#e6e9f0", pants="#2b2f3a",
                  shoes="#1d1f27", iris="#2c4a6b", build=1.0, brow=1.0, back=True, killer=True),
    "mother": dict(h=1.63, skin="#efc6a4", hair="#5a3a26", style="neat", top="#8a6f9a", pants="#3e3a48",
                   shoes="#2a2630", iris="#5a4636", build=0.9, brow=0.8, back=True),
    "father": dict(h=1.80, skin="#e9bf9b", hair="#3b2d24", style="buzz", top="#5c6b7a", pants="#3a3f4c",
                   shoes="#22252e", iris="#4a3a2c", build=1.1, brow=1.1),
    "doctor": dict(h=1.74, skin="#c98e6a", hair="#1b1714", style="neat", top="#3f9d95", pants="#3f9d95",
                   shoes="#e9e9ee", iris="#2a1d16", build=1.0, brow=1.0),
    "liup": dict(h=1.56, skin="#f1c7a6", hair="#17181f", style="neat", top="#6b7f9e", pants="#4a5876",
                 shoes="#6b7f9e", iris="#3d2f28", build=0.92, brow=0.9),
    # a figure in the dark: body only, no face features (an optional faint grin)
    "shadow": dict(h=1.70, skin="#0d0e13", hair="#060709", style="messy", top="#0b0c11", pants="#090a0e",
                   shoes="#060709", iris="#000000", build=1.0, brow=1.0, back=True, sil=True),
}

REST = dict(x=0.0, z=0.0, yaw=0.0, crouch=0.0, bob=0.0, lean=0.0, side=0.0, twist=0.0,
            head_yaw=0.0, head_pitch=0.0, head_roll=0.0, shrug=0.0, breath=0.0,
            aR=(4.0, 6.0, 14.0), aL=(4.0, 6.0, 14.0),       # shoulder pitch fwd, roll out, elbow bend (deg)
            fist=0.0, stance=0.0, floor=0.0,                # floor: ground height under him (a raised sidewalk)
            lid=1.0, lid_lo=0.0, brow=0.0, brow_in=0.0, gx=0.0, gy=0.0, mouth=0.0, smile=0.0, mouth_w=0.0)


# ---- small vector kit ------------------------------------------------------------------------------
def add(*v):
    return tuple(sum(c) for c in zip(*v))


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm(a):
    n = math.sqrt(dot(a, a)) or 1.0
    return (a[0] / n, a[1] / n, a[2] / n)


def rot(v, axis, deg):
    """Rodrigues rotation of v about a unit axis."""
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    return add(mul(v, c), mul(cross(axis, v), s), mul(axis, dot(axis, v) * (1 - c)))


class Basis:
    def __init__(self, r, u, f):
        self.r, self.u, self.f = r, u, f

    @staticmethod
    def yaw(deg):
        y = math.radians(deg)
        return Basis((-math.cos(y), 0.0, -math.sin(y)), (0.0, 1.0, 0.0), (math.sin(y), 0.0, -math.cos(y)))

    def turn(self, deg):          # about own up (positive turns toward the character's left... see yaw)
        return Basis(rot(self.r, self.u, -deg), self.u, rot(self.f, self.u, -deg))

    def pitch(self, deg):         # positive leans/looks forward-down
        return Basis(self.r, rot(self.u, self.r, deg), rot(self.f, self.r, deg))

    def roll(self, deg):          # positive tilts toward the character's right
        return Basis(rot(self.r, self.f, -deg), rot(self.u, self.f, -deg), self.f)

    def w(self, o, a, u, b):
        return add(o, mul(self.r, a), mul(self.u, u), mul(self.f, b))

    def d(self, a, u, b):
        return add(mul(self.r, a), mul(self.u, u), mul(self.f, b))


def ik(root, target, l1, l2, pole):
    """2-bone IK. Returns (mid joint, end point actually reached, reach error in metres)."""
    D = sub(target, root)
    d = math.sqrt(dot(D, D))
    dmax = (l1 + l2) * 0.999
    err = max(0.0, d - dmax)
    d = min(max(d, abs(l1 - l2) + 1e-4), dmax)
    dn = norm(D)
    a = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
    h = math.sqrt(max(0.0, l1 * l1 - a * a))
    p = sub(pole, mul(dn, dot(pole, dn)))
    p = norm(p) if dot(p, p) > 1e-9 else norm(cross(dn, (0, 0, 1)))
    mid = add(root, mul(dn, a), mul(p, h))
    return mid, add(root, mul(dn, d)), err


# ---- screen path helpers ---------------------------------------------------------------------------
def smooth(pts, closed=True, k=1.0):
    """Catmull-Rom through screen points -> skia.Path."""
    p = skia.Path()
    n = len(pts)
    if n < 2:
        return p
    p.moveTo(*pts[0])
    rng = range(n) if closed else range(n - 1)
    for i in rng:
        p0, p1, p2, p3 = pts[i - 1 if i > 0 or closed else 0], pts[i], pts[(i + 1) % n], pts[(i + 2) % n if closed else min(i + 2, n - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6 * k, p1[1] + (p2[1] - p0[1]) / 6 * k)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6 * k, p2[1] - (p3[1] - p1[1]) / 6 * k)
        p.cubicTo(*c1, *c2, *p2)
    if closed:
        p.close()
    return p


def capsule(p0, r0, p1, r1, n=12):
    """Tapered capsule between two screen points (radii in px)."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy) or 1e-3
    ang = math.atan2(dy, dx)
    k = max(-0.99, min(0.99, (r0 - r1) / L))
    off = math.asin(k)
    pts = []
    for i in range(n + 1):                      # end cap around p1
        t = ang - (math.pi / 2 - off) + (math.pi - 2 * off) * i / n
        pts.append((p1[0] + r1 * math.cos(t), p1[1] + r1 * math.sin(t)))
    for i in range(n + 1):                      # start cap around p0
        t = ang + (math.pi / 2 - off) + (math.pi + 2 * off) * i / n
        pts.append((p0[0] + r0 * math.cos(t), p0[1] + r0 * math.sin(t)))
    path = skia.Path()
    path.moveTo(*pts[0])
    for q in pts[1:]:
        path.lineTo(*q)
    path.close()
    return path


def union(*paths):
    out = paths[0]
    for p in paths[1:]:
        try:
            out = skia.Op(out, p, skia.PathOp.kUnion_PathOp)
        except RuntimeError:                                 # (Skia gives up on some very small or degenerate shapes: the two are then drawn as they are)
            out = skia.Path(out)
            out.addPath(p)
    return out


def lathe(cam, o, B, rings, n=28):
    """Silhouette of a stack of elliptic rings [(u, wa, db, a_off, b_off)] in basis B at origin o."""
    left, right, depth, allp = [], [], [], []
    nx, ok = _axis_normal(cam, o, B, rings[0][0], rings[-1][0], max(r[1] for r in rings))
    for u, wa, db, ao, bo in rings:
        best_l, best_r = None, None
        for i in range(n):
            t = 2 * math.pi * i / n
            P = B.w(o, ao + wa * math.cos(t), u, bo + db * math.sin(t))
            x, y, z, s = cam.proj(P)
            q = x * nx[0] + y * nx[1]                  # across the axis as it shows on screen (x when upright)
            if best_l is None or q < best_l[0]:
                best_l = (q, x, y)
            if best_r is None or q > best_r[0]:
                best_r = (q, x, y)
            depth.append(z)
            allp.append((x, y))
        left.append(best_l[1:])
        right.append(best_r[1:])
    if not ok:                                         # axis end-on to the lens (a body lying toward it): the hull
        return smooth(_hull(allp)), sum(depth) / len(depth)
    return smooth(left + right[::-1]), sum(depth) / len(depth)


def _axis_normal(cam, o, B, u0, u1, wmax):
    """Screen unit normal of a basis' up axis (= (1, 0) for an upright body) and whether the axis is long enough
    on screen (not end-on) for left/right silhouette extremes."""
    a, b = cam.proj(B.w(o, 0, u0, 0)), cam.proj(B.w(o, 0, u1, 0))
    d = (b[0] - a[0], b[1] - a[1])
    L = math.hypot(*d)
    if L < 1e-6:
        return (1.0, 0.0), False
    w = abs(wmax) * 2 * cam.proj(B.w(o, 0, (u0 + u1) / 2, 0))[3]
    return (-d[1] / L, d[0] / L), L > 0.6 * w


# ---- the head ----------------------------------------------------------------------------------------
HEAD_RINGS = [(-1.00, 0.22, 0.25, 0, 0.20), (-0.86, 0.55, 0.58, 0, 0.12), (-0.60, 0.86, 0.84, 0, 0.05),
              (-0.25, 1.00, 0.95, 0, 0), (0.15, 1.04, 0.98, 0, 0), (0.55, 0.95, 0.92, 0, -0.02),
              (0.85, 0.66, 0.66, 0, -0.04), (1.02, 0.28, 0.30, 0, -0.05), (1.07, 0.02, 0.02, 0, -0.05)]


def head_rings(R, shape=None):
    """HEAD_RINGS scaled to a head of radius R. shape = look "head_shape" (sx, sy, jaw): sx widens, sy lengthens,
    jaw > 0 widens the lower half (square jaw), < 0 narrows it (pointed chin). None = the standard head."""
    sx, sy, jaw = shape or (1.0, 1.0, 0.0)
    return [(u * R * sy, wa * R * 1.04 * sx * (1 + jaw * max(0.0, -u)), db * R * 0.97 * (1 + 0.5 * jaw * max(0.0, -u)), 0, bo * R)
            for u, wa, db, ao, bo in HEAD_RINGS]


class Head:
    def __init__(self, cam, c, B, R, shape=None):
        self.cam, self.c, self.B, self.R = cam, c, B, R
        self.shape = shape or (1.0, 1.0, 0.0)

    def surf(self, lam, mu, lift=1.0):
        """Point on the head at longitude lam (0 = face centre, + toward the screen right when the face
        looks at the camera) and latitude mu (radians)."""
        R = self.R * lift
        sx, sy, jaw = self.shape
        lo = max(0.0, -math.sin(mu))
        return self.B.w(self.c, -math.sin(lam) * math.cos(mu) * R * 1.04 * sx * (1 + jaw * lo), math.sin(mu) * R * 1.02 * sy,
                        math.cos(lam) * math.cos(mu) * R * 0.97 * (1 + 0.5 * jaw * lo))

    def facing(self, lam, mu):
        p = self.surf(lam, mu)
        n = norm(sub(p, self.c))
        return dot(n, norm(sub(self.cam.pos, p)))

    def decal(self, lam, mu, lift=1.0):
        """skia.Matrix mapping decal coords (metres; x right, y down as seen from the front) onto the
        head surface at (lam, mu)."""
        e = 1e-3
        p = self.surf(lam, mu, lift)
        pe = self.surf(lam + e / self.R, mu, lift)
        ps = self.surf(lam, mu - e / self.R, lift)
        o, a, b = self.cam.proj(p), self.cam.proj(pe), self.cam.proj(ps)
        m = skia.Matrix()
        m.setAll((a[0] - o[0]) / e, (b[0] - o[0]) / e, o[0], (a[1] - o[1]) / e, (b[1] - o[1]) / e, o[1], 0, 0, 1)
        return m


def draw_eye(c, R, side, ex, L, light):
    """Eye in decal coords centred at 0; side = +1 for the screen-right eye (frontal), -1 left."""
    rx, ry = 0.25 * R, 0.31 * R
    eye = skia.Path()
    eye.addOval(skia.Rect(-rx, -ry, rx, ry))
    if L.get("killer"):                       # no lids: a sooty ring, a wide white eye, a small pupil
        rx, ry = 0.21 * R, 0.25 * R
        eye = skia.Path()
        eye.addOval(skia.Rect(-rx, -ry, rx, ry))
        c.drawOval(skia.Rect(-rx * 1.35, -ry * 1.3, rx * 1.35, ry * 1.35), paint("#1a0a0e", a=0.75, blur=0.06 * R))
        c.drawPath(eye, paint("#f4f4f0"))
        gx, gy = ex["gx"] * 0.12 * R, ex["gy"] * 0.14 * R
        c.drawCircle(gx, gy, 0.11 * R, paint(L["iris"]))
        c.drawCircle(gx, gy, 0.065 * R, paint("#050506"))
        c.drawCircle(gx - 0.04 * R, gy - 0.045 * R, 0.025 * R, paint("#ffffff", a=0.9))
        c.drawPath(eye, paint("#1a0a0e", stroke=0.035 * R))
        return
    glow = L.get("glow")                                 # look "glow": the whole eye is lit in that colour, the pupil its brightest point
    # lids first: the white and iris are drawn only where the eye is open (eye minus both lids), so a closing eye
    # shows the head's own shaded skin, never a flat skin-coloured disc
    lid = max(0.0, min(1.0, ex["lid"]))
    yl = -ry * 1.05 + (1.0 - lid) * ry * 1.85
    tilt = side * ex["brow_in"] * 0.06 * R               # angry (+) lids slope down toward the nose; worried (-) lift there
    up = skia.Path()
    up.moveTo(-rx * 1.3, -ry * 1.4)
    up.lineTo(rx * 1.3, -ry * 1.4)
    up.lineTo(rx * 1.3, yl - tilt)
    up.quadTo(0, yl - ry * 0.25 * lid, -rx * 1.3, yl + tilt)
    up.close()
    yb = ry * 1.05 - ex["lid_lo"] * ry * 0.9
    lo = skia.Path()
    lo.moveTo(-rx * 1.3, ry * 1.4)
    lo.lineTo(rx * 1.3, ry * 1.4)
    lo.lineTo(rx * 1.3, yb)
    lo.quadTo(0, yb + ry * 0.2, -rx * 1.3, yb)
    lo.close()
    vis = skia.Op(skia.Op(eye, up, skia.PathOp.kDifference_PathOp), lo, skia.PathOp.kDifference_PathOp)
    has = vis is not None and not vis.isEmpty() and lid > 0.06
    if glow and has:
        c.save()
        c.clipPath(vis, skia.ClipOp.kIntersect, True)
        c.drawOval(skia.Rect(-rx * 1.7, -ry * 1.6, rx * 1.7, ry * 1.6), paint(glow, a=0.4, blur=0.09 * R))
        c.restore()
    if has:
        c.save()
        c.clipPath(vis, skia.ClipOp.kIntersect, True)
        c.drawPath(eye, paint(shade(glow, 0.55) if glow else "#fbfbff"))
        if not glow:
            c.drawRect(skia.Rect(-rx, -ry, rx, ry), paint(shader=lin((0, -ry), (0, ry), [argb("#c9cfe0"), argb("#fbfbff")], [0, 0.6])))
        gx, gy = ex["gx"] * 0.13 * R, ex["gy"] * 0.15 * R
        ir = L.get("iris_r", 0.17) * R                   # look "iris_r": a smaller iris reads as a fixed stare
        iris = glow or L["iris"]
        c.drawCircle(gx, gy, ir, paint(shader=rad((gx, gy - ir * 0.3), ir * 1.2, [argb(shade(iris, 0.25)), argb(iris), argb(shade(iris, -0.5 if not glow else -0.15))], [0, 0.55, 1])))
        c.drawCircle(gx, gy, ir * 0.52, paint(shade(glow, 0.8) if glow else "#0b0c12"))
        c.drawCircle(gx - ir * 0.38, gy - ir * 0.42, ir * 0.28, paint("#ffffff", a=0.95))
        c.drawCircle(gx + ir * 0.35, gy + ir * 0.3, ir * 0.12, paint("#ffffff", a=0.7))
        # a soft lid shadow along the top of the white
        c.drawRect(skia.Rect(-rx, -ry * 1.1, rx, yl + ry * 0.16), paint(shade(L["skin"], -0.5), a=0.12, blur=0.04 * R))
        c.restore()
    # lash line: the top edge of the open eye (the lid edge, or the eye's own rim when wide open), so the line always
    # hugs the eye; a free arc floats above a wide-open eye and reads as a second brow
    ink = paint("#1a1214", stroke=0.05 * R)
    ink.setStrokeCap(skia.Paint.kRound_Cap)
    if has and lid >= 0.3:
        if yl - 0.125 * ry * lid < -0.97 * ry:            # lid edge above the eye: the eye's own upper rim is the lash
            c.drawArc(skia.Rect(-rx, -ry, rx, ry), 208 - 6 * side, 124, False, ink)
        else:                                            # the lid edge across the eye, kept inside the eye
            c.save()
            ov = skia.Path()
            ov.addOval(skia.Rect(-rx * 1.02, -ry * 1.02, rx * 1.02, ry * 1.02))
            c.clipPath(ov, skia.ClipOp.kIntersect, True)
            edge = skia.Path()
            edge.moveTo(-rx * 1.3, yl + tilt)
            edge.quadTo(0, yl - ry * 0.25 * lid, rx * 1.3, yl - tilt)
            c.drawPath(edge, ink)
            c.restore()
        c.drawPath(vis, paint(shade(L["skin"], -0.6), stroke=0.018 * R, a=0.7))      # the thin rim round the white
    else:                                                # shut, or nearly: one lash line, kept inside the eye
        c.save()
        c.clipRect(skia.Rect(-rx * 1.08, -ry * 1.6, rx * 1.08, ry * 1.6))
        lash = skia.Path()
        lash.moveTo(-rx * 1.05, yl + tilt * 0.8)
        lash.quadTo(0, yl + ry * 0.12, rx * 1.05, yl - tilt * 0.8)
        c.drawPath(lash, ink)
        c.restore()

BROW_MU = 0.37


def draw_brow(c, R, side, ex, L):
    """Thick tapered brow above the eye (decal coords at the brow centre). side: +1 screen-right."""
    k = L["brow"]
    raise_ = ex["brow"] * 0.13 * R
    inner = ex["brow_in"] * 0.12 * R              # + angry: the inner end drops
    xi, xo = -side * 0.26 * R, side * 0.24 * R
    yi, yo = -raise_ + inner, -raise_ - ex["brow_in"] * 0.03 * R + 0.02 * R
    ym = min(yi, yo) - 0.06 * R
    th_i, th_o = 0.10 * R * k, 0.05 * R * k
    p = skia.Path()
    p.moveTo(xi, yi - th_i / 2)
    p.quadTo(0, ym - th_i * 0.6, xo, yo - th_o / 2)
    p.lineTo(xo, yo + th_o / 2)
    p.quadTo(0, ym + th_i * 0.5, xi, yi + th_i / 2)
    p.close()
    c.drawPath(p, paint(L.get("brow_col") or shade(L["hair"], -0.5)))


def draw_mouth(c, R, ex, L):
    w = 0.36 * R * (1 + 0.35 * ex["mouth_w"]) * (1.25 if L.get("killer") else 1.0)
    sm = ex["smile"] * 0.08 * R
    o = max(0.0, ex["mouth"]) * 0.32 * R
    line = shade(L["skin"], -0.62)
    if o > 0.01 * R:
        m = skia.Path()
        m.moveTo(-w / 2, -sm)
        m.quadTo(0, -o * 0.35 + sm * 0.6, w / 2, -sm)
        m.quadTo(0, o + sm * 0.8, -w / 2, -sm)
        m.close()
        c.drawPath(m, paint("#3a1418"))
        c.save()
        c.clipPath(m, skia.ClipOp.kIntersect, True)
        c.drawRect(skia.Rect(-w, -o, w, -o * 0.35 + 0.05 * R), paint("#f4f1ec"))
        c.drawOval(skia.Rect(-w * 0.3, o * 0.35, w * 0.3, o * 1.2), paint("#b8505a"))
        c.restore()
        c.drawPath(m, paint(line, stroke=0.03 * R))
    else:
        m = skia.Path()
        m.moveTo(-w / 2, -sm)
        m.quadTo(0, sm * 1.4, w / 2, -sm)
        c.drawPath(m, paint(line, stroke=0.04 * R))


def _lank_locks(head, cam, mu_h, path):
    """Style "lank": three limp, slightly tangled locks falling from the hairline onto the forehead, off the centre
    (the middle of the forehead stays bare), and two short flat tufts sticking out over the ears."""
    for lam, drop, sw in ((-0.42, 0.26, 0.10), (-0.20, 0.17, -0.06), (0.36, 0.22, 0.08)):
        if head.facing(lam, mu_h(lam)) < 0.05:
            continue
        m = mu_h(lam)
        q = [head.surf(lam - 0.07, m + 0.03, 1.03), head.surf(lam + sw * 0.5, m - drop * 0.6, 1.025),
             head.surf(lam + sw, m - drop, 1.02), head.surf(lam + sw * 0.4 + 0.02, m - drop * 0.45, 1.025),
             head.surf(lam + 0.07, m + 0.03, 1.03)]
        path = union(path, smooth([cam.proj(v)[:2] for v in q], k=0.5))
    for lam in (-1.45, 1.45):
        if head.facing(lam, 0.3) < -0.3:
            continue
        b0, b1 = head.surf(lam - 0.2, 0.42, 1.04), head.surf(lam + 0.2, 0.30, 1.04)
        tip = head.surf(lam + (0.25 if lam > 0 else -0.25), 0.22, 1.16)
        tri = skia.Path()
        tri.moveTo(*cam.proj(b0)[:2])
        tri.lineTo(*cam.proj(tip)[:2])
        tri.lineTo(*cam.proj(b1)[:2])
        tri.close()
        path = union(path, tri)
    return path


def hair_path(head, cam, L, lift=0.0, t=0.0):
    """Visible hair region: the projected hairline where it faces the camera, closed over the top of the
    head along the enlarged head silhouette; style spikes are unioned on. lift 0..1: locks standing up off the
    crown and swaying (pose key hair_lift: a power-up)."""
    R = head.R
    style = L["style"]
    # hairline latitude by longitude: low at the back and sides, a fringe across the forehead
    def mu_h(lam):
        a = abs((lam + math.pi) % (2 * math.pi) - math.pi)      # 0 front .. pi back
        if style == "buzz":
            base = 0.62 if a < 1.0 else 0.15 - 0.1 * (a - 1.0) / 0.6 if a < 1.6 else 0.05 - 0.75 * min(1.0, (a - 1.6) / 0.7)      # (behind the ear it goes down to the nape: from behind a head is hair, not a bare skull)
        elif style == "long":                                    # centre-parted long hair: covers sides and back to the jaw
            mf = L.get("mu_front", 0.42)                         # optional higher hairline (a bare forehead)
            base = mf if a < 0.95 else mf - (a - 0.95) * 3.0
        elif style == "short":                                   # an ordinary men's cut: above the ears, level at the nape
            # level fringe, a short step at the temple, level above the ear, a short drop behind it, level at the nape
            mf = L.get("mu_front", 0.42)                         # optional higher hairline (hair pulled back)
            prof = [(0.0, mf), (0.95, mf - 0.02), (1.15, 0.20), (1.65, 0.14), (1.9, 0.02), (2.35, -0.76), (3.2, -0.76)]
            base = next(b0 + (b1 - b0) * (a - a0) / (a1 - a0) for (a0, b0), (a1, b1) in zip(prof, prof[1:]) if a <= a1)
        elif style == "lank":                                    # thin receding hair: a high bare forehead, temples receding further
            mf = L.get("mu_front", 0.66)
            prof = [(0.0, mf), (0.35, mf), (0.70, mf + 0.10), (1.30, 0.24), (2.0, 0.08), (2.8, -0.45), (3.2, -0.50)]
            base = next(b0 + (b1 - b0) * (a - a0) / (a1 - a0) for (a0, b0), (a1, b1) in zip(prof, prof[1:]) if a <= a1)
        else:
            base = 0.42 if a < 0.9 else 0.42 - (a - 0.9) * 0.55 if a < 1.6 else 0.035 - 0.85 * min(1.0, (a - 1.6) / 0.7)      # (behind the ear: down to the nape)
        if a < 1.0 and style in ("messy", "spiky", "neat", "short", "lank"):     # angular fringe locks
            n = {"messy": 5, "spiky": 4, "neat": 6, "short": 6, "lank": 7}[style]
            ph = (lam + 1.0) / 2.0 * n
            tooth = abs((ph % 1.0) - 0.5) * 2
            depth = {"messy": 0.26, "spiky": 0.18, "neat": 0.12, "short": 0.08, "lank": 0.07}[style]
            base -= depth * (1 - tooth) * (1 - a)
        return max(base, -0.92)
    if L.get("hair_mesh"):
        # the cap as a quad mesh on the 1.06 shell, front-facing quads only: exact at any head pitch/roll (the
        # hairline+silhouette join below breaks when the head is thrown back or rolled hard)
        mesh = skia.Path()
        NL, NM = 64, 7
        for i in range(NL):
            l0, l1 = -math.pi + 2 * math.pi * i / NL, -math.pi + 2 * math.pi * (i + 1) / NL
            m0, m1 = mu_h(l0), mu_h(l1)
            for j in range(NM):
                a0, a1 = j / NM, (j + 1) / NM
                # lift 1.0 at the hairline -> 1.06 by the crown: no parallax over the eyes seen from below
                g0, g1 = 1.0 + 0.06 * min(1.0, 3 * a0), 1.0 + 0.06 * min(1.0, 3 * a1)
                q = [head.surf(l0, m0 + (math.pi / 2 - m0) * a0, g0), head.surf(l1, m1 + (math.pi / 2 - m1) * a0, g0),
                     head.surf(l1, m1 + (math.pi / 2 - m1) * a1, g1), head.surf(l0, m0 + (math.pi / 2 - m0) * a1, g1)]
                cq = [sum(v[k] for v in q) / 4 for k in range(3)]
                if dot(norm(sub(cq, head.c)), norm(sub(cam.pos, cq))) <= -0.02:
                    continue
                s = [cam.proj(v)[:2] for v in q]
                if (s[1][0] - s[0][0]) * (s[2][1] - s[0][1]) - (s[1][1] - s[0][1]) * (s[2][0] - s[0][0]) < 0:
                    s = s[::-1]                        # one winding for all, so the fill is their union
                mesh.addPoly([skia.Point(*v) for v in s], True)
        try:
            mesh = skia.Simplify(mesh)
        except RuntimeError:                           # degenerate quads (e.g. a tiny far head): the raw union still fills
            pass
        return _lank_locks(head, cam, mu_h, mesh) if style == "lank" else mesh
    pts, vis = [], []
    N = 72
    for i in range(N):
        lam = -math.pi + 2 * math.pi * i / N
        mu = mu_h(lam)
        p = head.surf(lam, mu, 1.06)
        pts.append(cam.proj(p)[:2])
        vis.append(dot(norm(sub(p, head.c)), norm(sub(cam.pos, p))) > 0.0)
    if not any(vis):
        run = []
    else:
        start = next(i for i in range(N) if vis[i] and not vis[i - 1]) if not all(vis) else 0
        run = []
        for k in range(N):
            i = (start + k) % N
            if not vis[i]:
                break
            run.append(pts[i])
    # enlarged head silhouette, closed over the top between the run's ends
    ring_l, ring_r = [], []
    nx, _ = _axis_normal(cam, head.c, head.B, -0.80 * R, 1.10 * R, R)
    for u in (-0.80, -0.50, -0.20, 0.10, 0.40, 0.65, 0.86, 1.02, 1.10):
        w = math.sqrt(max(0.0, 1 - (u / 1.12) ** 2)) * 1.10
        bl, br = None, None
        for i in range(28):
            t = 2 * math.pi * i / 28
            P = head.B.w(head.c, w * math.cos(t) * R * 1.04 * head.shape[0], u * R * head.shape[1], w * math.sin(t) * R * 0.97 - 0.04 * R)
            x, y = cam.proj(P)[:2]
            q = x * nx[0] + y * nx[1]                  # across the head's axis on screen (x when upright)
            if bl is None or q < bl[0]:
                bl = (q, x, y)
            if br is None or q > br[0]:
                br = (q, x, y)
        ring_l.append(bl[1:])
        ring_r.append(br[1:])
    cap = ring_l + ring_r[::-1]                       # left side bottom->top, right side top->bottom
    if run:
        # join: hairline run (screen-left to right as it is ordered), then the cap arc back over the top
        if run[0][0] * nx[0] + run[0][1] * nx[1] > run[-1][0] * nx[0] + run[-1][1] * nx[1]:
            run = run[::-1]
        L0, R0 = run[0], run[-1]
        il = min(range(len(ring_l)), key=lambda i: math.dist(ring_l[i], L0))
        ir = min(range(len(ring_r)), key=lambda i: math.dist(ring_r[i], R0))
        outline = run + ring_r[ir + 1:] + ring_l[il + 1:][::-1]
        path = smooth(outline, k=0.6)
    else:
        path = smooth(cap)
    if style == "spiky":
        for lam in (-0.9, -0.35, 0.2, 0.75, 1.5, 2.4):
            if head.facing(lam, 0.9) < -0.6:
                continue
            b0, b1 = head.surf(lam - 0.28, 0.80, 1.05), head.surf(lam + 0.28, 0.80, 1.05)
            tip = head.surf(lam + 0.15, 1.15, 1.55)
            tri = skia.Path()
            tri.moveTo(*cam.proj(b0)[:2])
            tri.lineTo(*cam.proj(tip)[:2])
            tri.lineTo(*cam.proj(b1)[:2])
            tri.close()
            path = union(path, tri)
    if style == "lank":
        path = _lank_locks(head, cam, mu_h, path)
    if style == "messy":
        for lam, mu in ((0.6, 0.95), (-0.5, 1.0), (1.6, 0.6)):
            if head.facing(lam, mu) < -0.5:
                continue
            b0, b1 = head.surf(lam - 0.3, mu - 0.15, 1.04), head.surf(lam + 0.25, mu - 0.1, 1.04)
            tip = head.surf(lam + 0.45, mu + 0.05, 1.32)
            tri = skia.Path()
            tri.moveTo(*cam.proj(b0)[:2])
            tri.lineTo(*cam.proj(tip)[:2])
            tri.lineTo(*cam.proj(b1)[:2])
            tri.close()
            path = union(path, tri)
    if lift > 0.02 and not L.get("hair_mesh"):
        for i, lam in enumerate((-1.15, -0.5, 0.15, 0.8, 1.7, 2.6)):
            if head.facing(lam, 0.9) < -0.6:
                continue
            b0, b1 = head.surf(lam - 0.3, 0.76, 1.04), head.surf(lam + 0.3, 0.76, 1.04)
            tip = head.surf(lam + 0.12 * math.sin(9.0 * t + 1.7 * i), 1.22, 1.05 + (0.55 + 0.2 * (i % 2)) * lift)
            tri = skia.Path()
            tri.moveTo(*cam.proj(b0)[:2])
            tri.lineTo(*cam.proj(tip)[:2])
            tri.lineTo(*cam.proj(b1)[:2])
            tri.close()
            path = union(path, tri)
    return path


# ---- the full character --------------------------------------------------------------------------------
def light_dir(cam, light, at):
    if light is None:
        return (0.3, 1.0)
    a, b = cam.proj(light), cam.proj(at)
    d = (b[0] - a[0], b[1] - a[1])
    n = math.hypot(*d) or 1.0
    return (d[0] / n * 0.7 + 0.1, d[1] / n + 0.3)


def pose_full(pose):
    p = dict(REST)
    p.update(pose)
    return p


def solve(look, pose):
    """Skeleton in world space. pose: REST keys plus optional ik_R/ik_L (world wrist targets) and
    ankle_R/ankle_L (world ankle positions; planted feet)."""
    L = LOOK[look]
    p = pose_full(pose)
    h, bd = L["h"], L["build"]
    # proportions (1.0 = the standard body). Legs trade length with the torso, so `h` is still the standing height
    lg, ar, hd = L.get("legs", 1.0), L.get("arms", 1.0) * pose.get("arms_k", 1.0), L.get("head", 1.0)     # arms_k: a pose may lengthen the arms a little
    tf = 1.0 - (lg - 1.0) * 0.416 / 0.30                 # what is left for the torso
    root = (p["x"], p["floor"], p["z"])
    Bb = Basis.yaw(p["yaw"])
    J = {"root": root, "Bb": Bb, "h": h, "tf": tf}
    hip_y = p["floor"] + (0.054 + 0.416 * lg) * h - p["crouch"] * h + p["bob"]
    # default ankles under the hips; planted ankles override
    sep = 0.062 * h + p["stance"] * h
    a_def = {s: Bb.w(root, sgn * sep, 0.035 * h, 0.0) for s, sgn in (("R", 1), ("L", -1))}
    ank = {s: pose.get("ankle_" + s, a_def[s]) for s in ("R", "L")}
    l1, l2 = 0.208 * h * lg, 0.208 * h * lg
    # keep the pelvis low enough that both legs reach their ankles
    pel_xz = root
    for s, sgn in (("R", 1), ("L", -1)):
        hj = Bb.w((pel_xz[0], 0, pel_xz[2]), sgn * 0.052 * h, 0, 0)
        dx = math.hypot(ank[s][0] - hj[0], ank[s][2] - hj[2])
        reach = (l1 + l2) * 0.985
        if dx < reach:
            hip_y = min(hip_y, ank[s][1] + 0.04 * h + math.sqrt(reach ** 2 - dx ** 2))
    P = (root[0], hip_y, root[2])
    J["pelvis"] = P
    Bc = Bb.turn(p["twist"]).pitch(p["lean"]).roll(p["side"])
    J["Bc"] = Bc
    N = Bc.w(P, 0, 0.30 * h * tf, -0.004 * h)
    J["neck"] = N
    sw = 0.118 * h * bd
    for s, sgn in (("R", 1), ("L", -1)):
        J["sh_" + s] = Bc.w(P, sgn * sw, 0.272 * h * tf + p["shrug"] * 0.028 * h, -0.006 * h)
        J["hip_" + s] = Bb.w(P, sgn * 0.052 * h, -0.035 * h, 0.0)
    Bh = Bb.turn(p["twist"] + p["head_yaw"]).pitch(p["lean"] * 0.4 + p["head_pitch"]).roll(p["head_roll"] + p["side"] * 0.5)
    R = 0.104 * h * hd
    J["Bh"], J["R"] = Bh, R
    neck_top = add(N, mul(Bc.u, 0.04 * h))
    J["head"] = Bh.w(neck_top, 0, 0.86 * R, 0.10 * R)
    # arms
    ua, fa = 0.165 * h * ar, 0.155 * h * ar
    J["err"] = {}
    for s, sgn in (("R", 1), ("L", -1)):
        S = J["sh_" + s]
        if ("ik_" + s) in pose:
            pole = pose.get("pole_" + s) or norm(Bc.d(sgn * 0.5, -0.5, -1.0))
            E, Wr, err = ik(S, pose["ik_" + s], ua, fa, pole)
            J["err"]["arm_" + s] = err
            fdir = norm(sub(Wr, E))
        else:
            pit, rol, bend = p["a" + s]
            pr, rr = math.radians(pit), math.radians(rol)
            d = norm((sgn * math.sin(rr), -math.cos(rr) * math.cos(pr), math.cos(rr) * math.sin(pr)))
            # elbow bends in the arm's pitch plane: continuous for every pitch (no sudden elbow flip)
            perp = (0.0, math.sin(pr), math.cos(pr))
            b = math.radians(bend)
            fl = add(mul(d, math.cos(b)), mul(perp, math.sin(b)))
            dw, fw = Bc.d(*d), Bc.d(*fl)
            E = add(S, mul(dw, ua))
            Wr = add(E, mul(fw, fa))
            fdir = norm(fw)
        J["el_" + s], J["wr_" + s], J["fdir_" + s] = E, Wr, fdir
        J["hand_" + s] = add(Wr, mul(fdir, 0.035 * h))
    # legs: IK to the ankles, knees forward (kpole_R/L: another way for a knee to point, e.g. up for a kick)
    for s in ("R", "L"):
        K, A, err = ik(J["hip_" + s], ank[s], l1, l2, pose.get("kpole_" + s) or add(Bb.f, (0, 0.15, 0)))
        J["kn_" + s], J["ank_" + s] = K, A
        J["err"]["leg_" + s] = err
        J["ankle_target_" + s] = ank[s]
        J["fdir_footf_" + s], J["fdir_footu_" + s] = Bb.f, Bb.u
    J["pose"], J["look"] = p, look
    if pose.get("lie"):
        _lie(J, pose["lie"])
    if pose.get("point_toes"):                           # kneeling / crawling: the foot lies back along the shin,
        for s in ("R", "L"):                             # instep on the floor, sole up
            f = norm(sub(J["ank_" + s], J["kn_" + s]))
            J["fdir_footf_" + s] = f
            J["fdir_footu_" + s] = norm(sub((0.0, -1.0, 0.0), mul(f, -f[1])))
    for s in ("R", "L"):                                 # on tiptoe: toe_R/L 0..1 pitches the foot down about its right
        t = pose.get("toe_" + s, 0.0)                    # axis (heel up); the caller raises the ankle by TOE_LIFT * t * h
        fy = pose.get("fyaw_" + s, 0.0)                  # fyaw_R/L: the foot turned out/in about the vertical (swivels)
        if t or fy:                                      # t < 0: a heel tap (toe up, the heel stays on the floor)
            f, r = rot(Bb.f, (0.0, 1.0, 0.0), fy), rot(Bb.r, (0.0, 1.0, 0.0), fy)
            J["fdir_footf_" + s] = rot(f, r, 50.0 * t)
            J["fdir_footu_" + s] = rot(Bb.u, r, 50.0 * t)
    if pose.get("head_at") is not None:                  # the head is off the body (a doll's, a monster's): it is where the pose says, a world point, facing head_face (a yaw), rolled head_spin degrees; the neck stays on the shoulders
        J["head"] = tuple(pose["head_at"])
        J["Bh"] = Basis.yaw(pose.get("head_face", 0.0)).roll(pose.get("head_spin", 0.0))
        J["headless"] = True
    return J


def lie_fwd(lie, pelvis, pt, direction=False):
    """pose["lie"] = (rotations [(world axis, deg), ...], world point for the pelvis): the upright skeleton turned
    as one rigid body about its pelvis (lying on a side, prone, on the back) and moved there (None: the pelvis
    stays where it is)."""
    rots, at = lie
    v = pt if direction else sub(pt, pelvis)
    for ax, deg in rots:
        v = rot(v, norm(ax), deg)
    return v if direction else add(pelvis if at is None else at, v)


def lie_inv(lie, pelvis, pt):
    """World point -> where it sits on the upright skeleton (for IK targets of a lying figure)."""
    rots, at = lie
    v = sub(pt, at)
    for ax, deg in reversed(rots):
        v = rot(v, norm(ax), -deg)
    return add(pelvis, v)


def _lie(J, lie):
    P0 = J["pelvis"]
    for k, v in list(J.items()):
        if isinstance(v, Basis):
            J[k] = Basis(*(lie_fwd(lie, P0, a, True) for a in (v.r, v.u, v.f)))
        elif k in ("root", "pose", "look", "h", "R", "err") or k.startswith("ankle_target"):
            continue
        elif isinstance(v, tuple) and len(v) == 3:
            J[k] = lie_fwd(lie, P0, v, k.startswith("fdir_"))
    J["root"] = (J["pelvis"][0], J["root"][1], J["pelvis"][2])


def _hull(pts):
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts
    def half(seq):
        out = []
        for p in seq:
            while len(out) >= 2 and (out[-1][0] - out[-2][0]) * (p[1] - out[-2][1]) - (out[-1][1] - out[-2][1]) * (p[0] - out[-2][0]) <= 0:
                out.pop()
            out.append(p)
        return out
    lo, up = half(pts), half(reversed(pts))
    return lo[:-1] + up[:-1]


def _poly_path(pts):
    path = skia.Path()
    path.moveTo(*pts[0])
    for q in pts[1:]:
        path.lineTo(*q)
    path.close()
    return path


def shoe_paths(cam, ank, f, h, u=(0.0, 1.0, 0.0)):
    """A shoe as a 3D volume (sole ring on the ground + a smaller toe-cap ring), projected and hulled, so it
    reads as a shoe from the front, side and back. Returns (shoe outline, visible sole band).
    u: the leg's up (a lying figure's soles are not on the floor)."""
    f = norm(sub(f, mul(u, dot(f, u))))
    r = cross(u, f)
    y0 = -0.035 * h                                        # sole under the ankle along -u (lifts with it)

    def ring(cf, y, a, b, n=20):
        c0 = add(ank, mul(u, y), mul(f, cf))
        return [cam.proj(add(c0, add(mul(f, a * math.cos(t)), mul(r, b * math.sin(t)))))[:2]
                for t in (2 * math.pi * i / n for i in range(n))]
    ground = ring(0.03 * h, y0, 0.072 * h, 0.034 * h)
    ground_up = ring(0.03 * h, y0 + 0.014 * h, 0.072 * h, 0.034 * h)
    top = ring(0.012 * h, y0 + 0.05 * h, 0.042 * h, 0.028 * h)
    shoe = _poly_path(_hull(ground + top))
    upper = _poly_path(_hull(ground_up + top))
    return shoe, skia.Op(shoe, upper, skia.PathOp.kDifference_PathOp)


CAMO = ("#3f4a2a", "#6b5436", "#23261c", "#5d6b3c")    # woodland: dark green, brown, near-black, moss


def _pattern(L, c, path, o, k, seed, lw, colr):
    """Look "pattern": "camo" lays solid woodland blotches over a clothing part, clipped to it, outline redrawn.
    The blotches sit in metres round the part's projected joint o, so they ride with the limb."""
    if L.get("pattern") != "camo":
        return
    c.save()
    c.clipPath(path, skia.ClipOp.kIntersect, True)
    for i in range(46):
        u = ((i * 0.6180339 + seed * 0.37) % 1.0) - 0.5
        v = ((i * 0.4142136 + seed * 0.23) % 1.0) - 0.5
        r = (0.035 + 0.035 * ((i * 0.7548776) % 1.0)) * k
        cx, cy = o[0] + u * 0.9 * k, o[1] + v * 0.9 * k
        pts = []
        for j in range(7):
            a = 2 * math.pi * j / 7 + i
            rr = r * (0.6 + 0.6 * ((i * 3 + j * 0.618) % 1.0))
            pts.append((cx + math.cos(a) * rr * 1.5, cy + math.sin(a) * rr))
        c.drawPath(smooth(pts, k=0.5), paint(CAMO[i % 4]))
    c.drawPath(path, paint("#000000", a=0.28, stroke=0.05 * k, blur=0.025 * k))   # keep the part's roundness
    c.restore()
    c.drawPath(path, paint(shade(colr, -0.72), stroke=lw))


def _grin(c, cam, Hd, k, ex, L):
    """Look face "grin": small fixed dots for eyes and a smile that is too wide, laid on the head's surface so it
    turns with the head. It opens a little when the character speaks; nothing else in the face moves."""
    R, eye = Hd.R, L.get("glow") or "#0b0c12"
    for lam in (-0.40, 0.40):
        if Hd.facing(lam, 0.05) > 0.12:
            q = cam.proj(Hd.surf(lam, 0.05, 1.005))
            if L.get("glow"):
                c.drawCircle(q[0], q[1], 0.22 * R * k, paint(eye, a=0.45, blur=0.07 * R * k))
            c.drawCircle(q[0], q[1], 0.09 * R * k, paint(eye))
            c.drawCircle(q[0] - 0.025 * R * k, q[1] - 0.03 * R * k, 0.026 * R * k, paint("#ffffff", a=0.9))
    vis = [l for l in (-0.68 + 1.36 * i / 12 for i in range(13)) if Hd.facing(l, -0.45) > 0.03]
    if len(vis) < 3:
        return
    drop = 0.12 * max(0.0, ex["mouth"])
    up = [cam.proj(Hd.surf(l, -0.34 - 0.10 * (1 - (l / 0.68) ** 2), 1.005))[:2] for l in vis]
    lo = [cam.proj(Hd.surf(l, -0.34 - (0.30 + drop) * (1 - (l / 0.68) ** 2), 1.005))[:2] for l in vis]
    m = smooth(up + lo[::-1], k=0.5)
    c.drawPath(m, paint("#f4f1ec"))
    for a, b in list(zip(up, lo))[1:-1]:                     # the teeth
        c.drawLine(a[0], a[1], b[0], b[1], paint("#2a1418", stroke=0.018 * R * k))
    c.drawPath(smooth([((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in zip(up, lo)], closed=False), paint("#2a1418", stroke=(0.022 + 0.6 * drop) * R * k))
    c.drawPath(m, paint("#1a0d10", stroke=0.035 * R * k))


def _long_hair(parts, fr, cam, J, Hd, L, ld, lw, rear, zh):
    """Hair that reads as long from the front as well as from behind: a lock falling over each shoulder (style
    "long" to the collarbone, look "long" well onto the chest), and for look "long" a sheet down the back."""
    R, h, Bc, P, N, k = Hd.R, J["h"], J["Bc"], J["pelvis"], J["neck"], cam.proj(J["head"])[3]
    tf, far = J["tf"], 1.0 if L.get("long") else 0.55
    dark = shade(L["hair"], -0.1)
    if L.get("long"):
        def sheet():
            q = [Hd.surf(-1.4, 0.3, 1.07), Hd.surf(-1.75, -0.55, 1.1), Bc.w(P, 0.118 * h, 0.2 * h * tf, -0.072 * h), Bc.w(P, 0.085 * h, 0.07 * h * tf, -0.085 * h),
                 Bc.w(P, -0.085 * h, 0.07 * h * tf, -0.085 * h), Bc.w(P, -0.118 * h, 0.2 * h * tf, -0.072 * h), Hd.surf(1.75, -0.55, 1.1), Hd.surf(1.4, 0.3, 1.07), Hd.surf(math.pi, 0.7, 1.06)]
            fr.part(smooth([cam.proj(w)[:2] for w in q], k=0.7), dark, (ld[0] * 0.5, 1.0), width=2 * R * k, line=lw, lit=0.10, dark=0.45)
        parts.append(("hairback_rear" if rear else "under", zh, sheet))
    if rear:
        return
    for sg in (-1.0, 1.0):                                   # +1: the character's left, screen right when it faces the lens
        if Hd.facing(sg * 1.15, 0.0) < -0.12:
            continue

        def lock(sg=sg):
            q = [Hd.surf(sg * 1.55, 0.3, 1.07), Hd.surf(sg * 1.6, -0.5, 1.1), Bc.w(N, -sg * 0.108 * h, -0.03 * h, 0.04 * h), Bc.w(N, -sg * 0.1 * h, -0.145 * h * far, 0.062 * h),
                 Bc.w(N, -sg * 0.05 * h, -0.13 * h * far, 0.072 * h), Bc.w(N, -sg * 0.058 * h, -0.02 * h, 0.055 * h), Hd.surf(sg * 1.0, -0.55, 1.06), Hd.surf(sg * 0.98, 0.3, 1.05)]
            fr.part(smooth([cam.proj(w)[:2] for w in q], k=0.7), L["hair"], (ld[0] * 0.5, 1.0), width=0.9 * R * k, line=lw, lit=0.14, dark=0.4)
        parts.append(("face", zh, lock))


WEAR = ("none", "cap", "brim_hat", "glasses", "backpack", "scarf", "cape", "tie", "wings", "horns", "crown")
BOTTOMS = ("pants", "shorts", "skirt", "dress")
ANIMALS = ("none", "cat", "dog", "rabbit", "mouse", "bear")


def _bottom(parts, fr, cam, J, L, ld, lw):
    """Look "bottom": a skirt (short, flared, in the pants colour) or a dress (the top's colour, from above the waist
    to the shins). The cloth is the hull of points along both legs, widened, so it follows them in any pose."""
    kind, h, Bb, P = L.get("bottom"), J["h"], J["Bb"], J["pelvis"]
    vol = [Bb.w(P, sg * 0.11 * h * L["build"], 0.06 * h, b * 0.072 * h) for sg in (1, -1) for b in (1, -1)]
    for s in ("R", "L"):
        hip, kn, an = J["hip_" + s], J["kn_" + s], J["ank_" + s]
        up = max(0.0, min(1.0, (0.78 - dot(norm(sub(kn, hip)), (0.0, -1.0, 0.0))) / 0.5))      # how far this thigh is from hanging down, 0..1 (a kick, a high knee): the leg then comes out of the cloth, which stays on the thigh
        up = up * up * (3 - 2 * up)
        along = [(hip, 0.062), (add(hip, mul(sub(kn, hip), 0.62)), 0.092)] if kind == "skirt" else \
            [(hip, 0.062), (add(hip, mul(sub(kn, hip), 1.0 - 0.3 * up)), 0.086 - 0.02 * up), (add(kn, mul(sub(an, kn), 0.68 * (1 - up) - 0.25 * up)), 0.102 - 0.045 * up)]
        for q, w in along:
            vol += [add(q, mul(Bb.r, sg * w * h)) for sg in (1, -1)] + [add(q, mul(Bb.f, sg * w * h)) for sg in (1, -1)]
    pts = [cam.proj(q) for q in vol]
    if min(q[2] for q in pts) < 0.2:
        return
    path, k = smooth(_hull([q[:2] for q in pts]), k=0.35), cam.proj(P)[3]
    colr = L["top"] if kind == "dress" else L["pants"]
    parts.append(("coat", sum(q[2] for q in pts) / len(pts), lambda: fr.part(path, colr, ld, width=0.28 * h * k, line=lw, lit=0.12, dark=0.42)))


def _animal(parts, fr, cam, J, Hd, L, p, ld, lw, rear):
    """Look "animal": the human figure with the ears, tail and nose of a cartoon cat, dog, rabbit, mouse or bear."""
    kind, h, R, Bh, Bb, P, hc, c = L.get("animal"), J["h"], J["R"], J["Bh"], J["Bb"], J["pelvis"], J["head"], fr.c
    k, t, fur = cam.proj(hc)[3], p.get("t", 0.0), L["hair"]
    S = lambda pts: [cam.proj(w)[:2] for w in pts]           # noqa: E731

    def ears():
        for sg in (-1.0, 1.0):
            if kind == "cat":
                q = [Hd.surf(sg * 0.25, 0.8, 1.0), add(hc, mul(Bh.u, 1.62 * R), mul(Bh.r, -sg * 0.72 * R)), Hd.surf(sg * 1.2, 0.62, 1.0)]
            else:
                cx, cy, rx, ry = {"dog": (1.0, -0.12, 0.23, 0.62), "rabbit": (0.42, 1.75, 0.24, 0.95), "mouse": (0.95, 1.0, 0.52, 0.52), "bear": (0.72, 0.98, 0.3, 0.3)}[kind]
                q = [add(hc, mul(Bh.r, -sg * (cx + rx * math.cos(a)) * R), mul(Bh.u, (cy + ry * math.sin(a)) * R)) for a in (2 * math.pi * i / 12 for i in range(12))]
            path = smooth(S(q), k=0.5) if kind != "cat" else _poly_path(S(q))
            fr.part(path, fur, ld, width=0.6 * R * k, line=lw, lit=0.14, dark=0.4)
            if kind in ("cat", "rabbit", "mouse"):           # the pale inside
                m = skia.Matrix()
                b = path.getBounds()
                m.setScale(0.55, 0.6, b.centerX(), b.centerY() + 0.12 * b.height())
                inner = skia.Path(path)
                inner.transform(m)
                c.drawPath(inner, paint("#f0b8b8", a=0.85))
    parts.append(("under" if kind != "dog" else "face", 0.0, ears))      # behind the head; a dog's hang over its sides

    def tail():
        sway = math.sin((5.0 if kind == "dog" else 1.6) * t)
        if kind in ("rabbit", "bear"):
            q = cam.proj(Bb.w(P, 0.0, -0.01 * h, -0.095 * h))
            c.drawCircle(q[0], q[1], (0.05 if kind == "rabbit" else 0.03) * h * q[3], paint("#f4f1ec" if kind == "rabbit" else fur))
            c.drawCircle(q[0], q[1], (0.05 if kind == "rabbit" else 0.03) * h * q[3], paint(shade(fur, -0.7), stroke=lw))
            return
        ln, up = {"cat": (0.3, 0.2), "dog": (0.18, 0.12), "mouse": (0.34, -0.03)}[kind]
        q = S([Bb.w(P, 0.0, -0.02 * h, -0.07 * h), Bb.w(P, 0.03 * sway * h, 0.02 * h, -(0.07 + 0.5 * ln) * h), Bb.w(P, 0.09 * sway * h, up * h, -(0.07 + 0.85 * ln) * h),
               Bb.w(P, 0.13 * sway * h, (up + 0.07) * h, -(0.07 + ln) * h)])
        w = (0.013 if kind == "mouse" else 0.03) * h * k
        c.drawPath(smooth(q, closed=False), paint(shade(fur, -0.7), stroke=w + 2 * lw))
        c.drawPath(smooth(q, closed=False), paint("#e8a8a8" if kind == "mouse" else fur, stroke=w))
    parts.append(("overtorso" if rear else "under", 0.0, tail))

    def nose():
        if Hd.facing(0.0, -0.17) < 0.1:
            return
        c.save()
        c.concat(Hd.decal(0.0, -0.17, 1.04))
        c.drawOval(skia.Rect(-0.1 * R, -0.07 * R, 0.1 * R, 0.07 * R), paint("#1c1416"))
        if kind in ("cat", "mouse"):                         # whiskers
            for sg in (-1, 1):
                for dy in (-0.05, 0.03, 0.11):
                    c.drawLine(sg * 0.2 * R, 0.06 * R, sg * 0.62 * R, dy * R, paint("#1c1416", a=0.8, stroke=0.016 * R))
        c.restore()
    parts.append(("face", 0.0, nose))


def _wear(parts, fr, cam, J, Hd, L, p, ld, lw, rear):
    """Look "wear": one thing worn, drawn from a handful of world points so that it moves with the body. `rear`:
    the lens sees the character's back (decided once per shot by the caller when it can be, so nothing swaps
    layers by itself)."""
    kind, h, R, Bc, Bh, P, N, hc = L.get("wear"), J["h"], J["R"], J["Bc"], J["Bh"], J["pelvis"], J["neck"], J["head"]
    k, c, tf = cam.proj(hc)[3], fr.c, J["tf"]
    S = lambda pts: [cam.proj(w)[:2] for w in pts]           # noqa: E731
    front = dot(Bh.f, norm(sub(cam.pos, hc))) > 0
    if kind in ("cap", "brim_hat"):
        colr = shade(L["top"], -0.3) if kind == "cap" else "#1d1b22"
        if kind == "cap":
            dome, _ = lathe(cam, hc, Bh, [(u * R, w * R, w * R * 0.96, 0, -0.03 * R) for u, w in ((0.36, 1.07), (0.6, 1.0), (0.85, 0.74), (1.02, 0.4), (1.1, 0.06))])
            brim = smooth(_hull(S([Bh.w(hc, math.sin(a) * rr * R, 0.37 * R, math.cos(a) * rr * R * (1.0 if rr < 1.1 else 1.0) + (0.0 if rr < 1.1 else 0.72 * R * math.cos(a)))
                                   for a in (-1.0, -0.6, -0.2, 0.2, 0.6, 1.0) for rr in (1.0, 1.12)])), k=0.5)
            order = [(dome, colr, 2 * R * k), (brim, shade(colr, -0.15), R * k)] if front else [(brim, shade(colr, -0.15), R * k), (dome, colr, 2 * R * k)]
        else:                                                # a wide flat hat: the brim is a disc, the crown a low drum
            Bt = Bh.pitch(-9.0)                               # (worn pushed back a little: the brim is clear of the brow)
            b0 = 0.64                                         # how high on the head the brim sits, in head radii (the eyes are at 0.02, the hairline about 0.42)
            brim, _ = lathe(cam, hc, Bt, [(b0 * R, 1.62 * R, 1.62 * R, 0, 0), ((b0 + 0.05) * R, 1.62 * R, 1.62 * R, 0, 0)], n=36)
            crown, _ = lathe(cam, hc, Bt, [((b0 + 0.16) * R, 0.92 * R, 0.9 * R, 0, 0), (1.08 * R, 0.88 * R, 0.86 * R, 0, 0), (1.2 * R, 0.7 * R, 0.68 * R, 0, 0)])
            band0, _ = lathe(cam, hc, Bt, [((b0 + 0.03) * R, 0.93 * R, 0.91 * R, 0, 0), ((b0 + 0.19) * R, 0.925 * R, 0.905 * R, 0, 0)])
            order = [(brim, shade(colr, 0.06), 2 * R * k), (band0, shade(L["top"], -0.1), 2 * R * k), (crown, colr, 2 * R * k)]
            bc = Bt.w(hc, 0.0, (b0 + 0.025) * R, 0.0)
            Bh = Bt
            if dot(Bh.u, sub(cam.pos, bc)) < 0:              # the lens is under the brim (a head thrown back, a low camera): the far half of the brim is behind the head and the crown behind the brim
                c0, c1, c2, hq = cam.proj(bc), cam.proj(add(bc, mul(Bh.r, R))), cam.proj(add(bc, mul(Bh.f, -R))), cam.proj(hc)
                ax = (c1[0] - c0[0], c1[1] - c0[1])
                al = math.hypot(*ax) or 1.0
                ax = (ax[0] / al, ax[1] / al)
                nn = (-ax[1], ax[0]) if (c2[0] - c0[0]) * -ax[1] + (c2[1] - c0[1]) * ax[0] > 0 else (ax[1], -ax[0])
                far, Lh = skia.Path(), 6 * R * k
                far.addPoly([skia.Point(c0[0] - ax[0] * Lh, c0[1] - ax[1] * Lh), skia.Point(c0[0] + ax[0] * Lh, c0[1] + ax[1] * Lh),
                             skia.Point(c0[0] + ax[0] * Lh + nn[0] * Lh, c0[1] + ax[1] * Lh + nn[1] * Lh), skia.Point(c0[0] - ax[0] * Lh + nn[0] * Lh, c0[1] - ax[1] * Lh + nn[1] * Lh)], True)
                skull = skia.Path()
                skull.addCircle(hq[0], hq[1], 1.04 * R * k)
                try:
                    hid = skia.Op(skull, far, skia.PathOp.kIntersect_PathOp)
                    brim, crown = skia.Op(brim, hid, skia.PathOp.kDifference_PathOp), skia.Op(crown, hid, skia.PathOp.kDifference_PathOp)
                    order = [(crown, colr, 2 * R * k), None, (brim, shade(colr, -0.05), 2 * R * k), hid]
                    b0 = None
                except RuntimeError:
                    pass

        def hat():
            for it in order:
                if isinstance(it, skia.Path):
                    continue
                if it is None:                               # (the band goes on before the brim that hides it from below; its far half is behind the head)
                    band, _ = lathe(cam, hc, Bh, [(0.67 * R, 0.93 * R, 0.91 * R, 0, 0), (0.83 * R, 0.925 * R, 0.905 * R, 0, 0)])
                    try:
                        band = skia.Op(band, order[-1], skia.PathOp.kDifference_PathOp)
                    except RuntimeError:
                        pass
                    c.drawPath(band, paint(shade(L["top"], -0.1)))
                    continue
                path, cl, w = it
                fr.part(path, cl, ld, width=w, line=lw, lit=0.14, dark=0.4)
            pass                                             # (the band of a wide hat is one of its parts now, under the crown: see `order`)
        parts.append(("face", 0.0, hat))
    elif kind == "glasses":
        def glasses():
            mid = []
            for lam in (-0.40, 0.40):
                if Hd.facing(lam, 0.02) > 0.12:
                    c.save()
                    c.concat(Hd.decal(lam, 0.03, 1.03))
                    rim = skia.Path()
                    rim.addRoundRect(skia.Rect(-0.3 * R, -0.25 * R, 0.3 * R, 0.25 * R), 0.1 * R, 0.1 * R)
                    c.drawPath(rim, paint("#dff0ff", a=0.16))
                    c.drawPath(rim, paint("#15161c", stroke=0.06 * R))
                    c.restore()
                    mid.append(lam)
                    a, b = S([Hd.surf(lam + 0.38 * (1 if lam > 0 else -1), 0.05, 1.04), Hd.surf(1.5 * (1 if lam > 0 else -1), 0.08, 1.03)])
                    c.drawLine(a[0], a[1], b[0], b[1], paint("#15161c", stroke=0.05 * R * k))
            if len(mid) == 2:
                a, b = S([Hd.surf(-0.1, 0.05, 1.04), Hd.surf(0.1, 0.05, 1.04)])
                c.drawLine(a[0], a[1], b[0], b[1], paint("#15161c", stroke=0.05 * R * k))
        parts.append(("face", 0.0, glasses))
    elif kind == "horns":
        def horns():
            for sg in (-1.0, 1.0):
                base = Hd.surf(sg * 0.75, 0.92, 0.97)
                d = norm(add(mul(Bh.u, 1.0), mul(Bh.r, -sg * 0.55), mul(Bh.f, 0.15)))
                a = norm(cross(d, Bh.f))
                b = cross(d, a)
                ring = [add(base, mul(a, 0.17 * R * math.cos(t)), mul(b, 0.17 * R * math.sin(t))) for t in (2 * math.pi * i / 10 for i in range(10))]
                tip = add(base, mul(d, 0.5 * R), mul(Bh.r, -sg * 0.16 * R), mul(Bh.u, 0.12 * R))
                fr.part(smooth(_hull(S(ring + [add(base, mul(d, 0.3 * R)), tip])), k=0.3), "#e6dcc6", ld, width=0.4 * R * k, line=lw, lit=0.2, dark=0.4)
        parts.append(("face", 0.0, horns))
    elif kind == "crown":
        def crown():
            band, _ = lathe(cam, hc, Bh, [(0.66 * R, 0.84 * R, 0.82 * R, 0, -0.03 * R), (0.86 * R, 0.86 * R, 0.84 * R, 0, -0.03 * R)])
            path = band
            for i in range(8):
                lam = 2 * math.pi * i / 8
                n3 = add(mul(Bh.r, -math.sin(lam)), mul(Bh.f, math.cos(lam)))
                if dot(n3, norm(sub(cam.pos, hc))) < -0.25:
                    continue
                tri = _poly_path(S([Bh.w(hc, -math.sin(lam + da) * 0.85 * R, u * R, math.cos(lam + da) * 0.83 * R - 0.03 * R) for da, u in ((-0.3, 0.84), (0.0, 1.22), (0.3, 0.84))]))
                path = union(path, tri)
            fr.part(path, "#e8b93a", ld, width=1.2 * R * k, line=lw, lit=0.3, dark=0.35)
        parts.append(("face", 0.0, crown))
    elif kind == "backpack":
        colr = mix(L["pants"], "#8a6a3c", 0.65)

        def pack():
            box = [Bc.w(P, sx * 0.1 * h, u * h * tf, b * h) for sx in (-1, 1) for u in (0.045, 0.285) for b in (-0.062, -0.165)]
            fr.part(smooth(_hull(S(box)), k=0.3), colr, ld, width=0.22 * h * k, line=lw, lit=0.14, dark=0.4)
            a, b = S([Bc.w(P, 0.0, 0.2 * h * tf, -0.168 * h), Bc.w(P, 0.0, 0.08 * h * tf, -0.168 * h)])
            if rear:
                c.drawLine(a[0], a[1], b[0], b[1], paint(shade(colr, -0.45), stroke=lw * 1.4))

        def straps():
            for sx in (-1, 1):
                q = S([Bc.w(P, sx * 0.075 * h, 0.292 * h * tf, -0.03 * h), Bc.w(P, sx * 0.082 * h, 0.27 * h * tf, 0.05 * h), Bc.w(P, sx * 0.095 * h, 0.15 * h * tf, 0.068 * h)])
                c.drawPath(smooth(q, closed=False, k=0.6), paint(shade(colr, -0.3), stroke=0.022 * h * k))
        parts.append(("overtorso" if rear else "under", 0.0, pack))
        if not rear:
            parts.append(("overtorso", 0.0, straps))
    elif kind == "scarf":
        colr = "#e8e2d0" if hexrgb(L["top"])[0] > 0.55 and hexrgb(L["top"])[1] < 0.4 else "#b3312c"

        def scarf():
            band, _ = lathe(cam, N, Bc, [(-0.012 * h, 0.056 * h, 0.05 * h, 0, 0), (0.02 * h, 0.06 * h, 0.054 * h, 0, 0), (0.048 * h, 0.052 * h, 0.047 * h, 0, 0)])
            if not rear:                                     # the end hanging down the chest
                tail = S([Bc.w(N, a * h, u * h, b * h) for a, u, b in ((0.01, 0.0, 0.05), (0.055, 0.0, 0.05), (0.07, -0.17, 0.07), (0.025, -0.18, 0.075))])
                fr.part(_poly_path(tail), shade(colr, -0.08), ld, width=0.08 * h * k, line=lw, lit=0.12, dark=0.35)
            fr.part(band, colr, ld, width=0.12 * h * k, line=lw, lit=0.14, dark=0.38)
        parts.append(("overtorso", 0.0, scarf))
    elif kind == "tie":
        colr = "#1f2a44" if hexrgb(L["top"])[0] > 0.55 and hexrgb(L["top"])[1] < 0.4 else "#7a1f24"

        def tie():
            if rear or dot(Bc.f, norm(sub(cam.pos, N))) < 0.15:
                return
            q = S([Bc.w(P, a * h, u * h * tf, b * h) for a, u, b in ((-0.013, 0.288, 0.05), (0.013, 0.288, 0.05), (0.02, 0.262, 0.063), (0.027, 0.13, 0.083), (0.0, 0.095, 0.086),
                                                                    (-0.027, 0.13, 0.083), (-0.02, 0.262, 0.063))])
            c.drawPath(_poly_path(q), paint(colr))
            c.drawPath(_poly_path(q), paint(shade(colr, -0.7), stroke=lw * 0.8))
        parts.append(("overtorso", 0.0, tie))
    elif kind == "cape":
        colr = shade(L["top"], -0.4)

        def cape():
            sway = 0.02 * h * math.sin(1.6 * p.get("t", 0.0))
            low = J["root"][1] + 0.2 * h
            q = [Bc.w(P, 0.125 * h, 0.285 * h * tf, -0.02 * h), Bc.w(P, 0.15 * h, 0.12 * h * tf, -0.09 * h), (P[0] + J["Bb"].r[0] * 0.2 * h - J["Bb"].f[0] * 0.12 * h + sway, low, P[2] + J["Bb"].r[2] * 0.2 * h - J["Bb"].f[2] * 0.12 * h),
                 (P[0] - J["Bb"].r[0] * 0.2 * h - J["Bb"].f[0] * 0.12 * h + sway, low, P[2] - J["Bb"].r[2] * 0.2 * h - J["Bb"].f[2] * 0.12 * h), Bc.w(P, -0.15 * h, 0.12 * h * tf, -0.09 * h),
                 Bc.w(P, -0.125 * h, 0.285 * h * tf, -0.02 * h)]
            fr.part(smooth(S(q), k=0.45), colr, ld, width=0.3 * h * k, line=lw, lit=0.1, dark=0.45)
        parts.append(("overtorso" if rear else "under", 0.0, cape))
    elif kind == "wings":
        s = 0.72 + 0.28 * math.sin(2 * math.pi * 0.8 * p.get("t", 0.0)) if p.get("wing") else 0.6      # they beat slowly when the body floats

        def wings():
            for sx in (-1.0, 1.0):
                q = [Bc.w(P, sx * a * h, u * h * tf, b * h) for a, u, b in ((0.03, 0.27, -0.06), (0.25 * s, 0.47 + 0.05 * s, -0.12), (0.62 * s, 0.36 + 0.12 * s, -0.16), (0.47 * s, 0.2, -0.15),
                                                                           (0.5 * s, 0.08, -0.15), (0.33 * s, 0.02, -0.13), (0.3 * s, -0.09, -0.12), (0.16 * s, 0.0, -0.09), (0.04, 0.1, -0.06))]
                sq = S(q)
                fr.part(_poly_path(sq), "#2e2233", ld, width=0.35 * h * k, line=lw, lit=0.1, dark=0.45)
                for i in (2, 4, 6):                          # the bones
                    c.drawLine(sq[1][0], sq[1][1], sq[i][0], sq[i][1], paint("#5a4a66", stroke=lw * 1.2))
        parts.append(("overtorso" if rear else "under", 0.0, wings))


def draw(fr, cam, look, pose, light=None, glow=None, held=None, shadow=True):
    """Draw one character; returns screen data for the checks."""
    L = LOOK[look]
    J = solve(look, pose)
    p, h, Bb, Bc = J["pose"], J["h"], J["Bb"], J["Bc"]
    c = fr.c
    # cull characters behind or right next to the lens (they would project as giant shapes)
    if min(cam.view(J[k])[2] for k in ("pelvis", "head", "ank_R", "ank_L")) < 0.45:
        return {"look": look, "err": J["err"], "J": J, "culled": True, "head": None, "head_r": 0}
    P = lambda w: cam.proj(w)              # noqa: E731
    s_px = P(J["pelvis"])[3]
    lw = max(1.4, 0.0055 * s_px)
    ld = light_dir(cam, light, J["pelvis"])
    out = {"look": look, "err": J["err"]}
    # contact shadows on the ground: soft body pool plus one under each shoe
    if shadow and not pose.get("air"):                   # air: jumping / falling, no ground under him
        fl = max(p.get("floor_R", p["floor"]), p.get("floor_L", p["floor"]))   # the hips' floor may be a mean
        fr.ground_ellipse(cam, J["root"][0], J["root"][2], 0.24 * h * L["build"] * 0.9, 0.13 * h, "#000000", 0.35, blur_m=0.06, y=fl + 0.003)
        for s in ("R", "L"):
            a = J["ank_" + s]
            fs = p.get("floor_" + s, fl)
            fr.ground_ellipse(cam, a[0] + Bb.f[0] * 0.03 * h, a[2] + Bb.f[2] * 0.03 * h, 0.07 * h, 0.045 * h,
                              "#000000", 0.6 * max(0.0, 1 - (a[1] - fs) / (0.12 * h)), blur_m=0.015, y=fs + 0.004)
    parts = []                                   # (kind, depth, fn)
    shared = {}

    def leg(s):
        hp, kn, an = P(J["hip_" + s]), P(J["kn_" + s]), P(J["ank_" + s])
        k = hp[3]
        path = union(capsule(hp[:2], 0.048 * h * k, kn[:2], 0.040 * h * k), capsule(kn[:2], 0.040 * h * k, an[:2], 0.030 * h * k))
        shoe, sole = shoe_paths(cam, J["ank_" + s], J["fdir_footf_" + s], h, J["fdir_footu_" + s])

        bare = L.get("bottom", "pants") != "pants"

        def fn():
            fr.part(path, L["skin"] if bare else L["pants"], ld, width=0.09 * h * k, line=lw)
            if L.get("bottom") == "shorts":                  # the leg of the shorts: down to above the knee
                fr.part(capsule(hp[:2], 0.05 * h * k, (hp[0] + (kn[0] - hp[0]) * 0.72, hp[1] + (kn[1] - hp[1]) * 0.72), 0.047 * h * k), L["pants"], ld, width=0.09 * h * k, line=lw)
            _pattern(L, c, path, hp[:2], k, 1 if s == "R" else 2, lw, L["pants"])
            fr.part(shoe, L["shoes"], ld, width=0.07 * h * k, line=lw, lit=0.3)
            light_shoe = sum(hexrgb(L["shoes"])) > 1.5
            c.drawPath(sole, paint(shade(L["shoes"], -0.35 if light_shoe else 0.45)))
            c.drawPath(shoe, paint(shade(L["shoes"], -0.72), stroke=lw))
        z = (hp[2] + kn[2] + an[2]) / 3
        parts.append(("leg", z, fn))
        out["foot_" + s] = an[:2]
        out["ankle_" + s] = J["ank_" + s]

    def arm(s):
        sh, el, wr, hd = P(J["sh_" + s]), P(J["el_" + s]), P(J["wr_" + s]), P(J["hand_" + s])
        k = sh[3]
        path = union(capsule(sh[:2], 0.040 * h * k, el[:2], 0.035 * h * k), capsule(el[:2], 0.035 * h * k, wr[:2], 0.031 * h * k))
        fd = J["fdir_" + s]

        def fn():
            # hand first (a mitten along the forearm with a thumb); the sleeve end overlaps it as a cuff
            ax = math.atan2(hd[1] - wr[1], hd[0] - wr[0])
            hand = skia.Path()
            r1 = 0.039 * h * k * (1 + 0.1 * p["fist"])
            hand.addOval(skia.Rect(-r1 * 1.15, -r1 * 0.95, r1 * 1.15, r1 * 0.95))
            thumb = skia.Path()
            thumb.addOval(skia.Rect(-r1 * 0.2, -r1 * 1.25, r1 * 0.75, -r1 * 0.35))
            m = skia.Matrix()
            m.setRotate(math.degrees(ax))
            m.postTranslate(hd[0], hd[1])
            hp = union(hand, thumb)
            hp.transform(m)
            if "torso" in shared and (p.get("arm_near") or {}).get(s, z <= shared["zt"]):   # near arm: soft cast shadow onto the body
                sp = union(path, hp)
                sp.offset(ld[0] * 0.025 * h * k, ld[1] * 0.025 * h * k)
                fr.soft(sp, "#05060c", 0.30, 0.02 * h * k, clip=shared["torso"])
            hf = held.get(s) if held else None
            under = getattr(hf, "under", False)                 # gripped props (shears) go under the fist
            if hf and under:
                hf(fr, cam, J, s, hd, fd, k)
            if not p.get("hide_hand_" + s):                     # a custom hand is drawn over it instead
                fr.part(hp, L["skin"], ld, width=r1 * 2.2, line=lw)
            fr.part(path, L["top"], ld, width=0.08 * h * k, line=lw)
            _pattern(L, c, path, sh[:2], k, 3 if s == "R" else 4, lw, L["top"])
            if hf and not under:
                hf(fr, cam, J, s, hd, fd, k)
        z = (sh[2] + el[2] + wr[2]) / 3
        fn.side = s
        parts.append(("arm", z, fn))
        out["hand_" + s] = hd[:2]
        out["hand_r"] = 0.04 * h * k

    def torso():
        rings_t = [(-0.07 * h, 0.104, 0.074), (0.05 * h, 0.098, 0.068), (0.17 * h, 0.112, 0.078),
                   (0.245 * h, 0.124, 0.074), (0.275 * h, 0.118, 0.068), (0.292 * h, 0.088, 0.056),
                   (0.300 * h, 0.046, 0.040)]          # square shoulders, flat top: no hump at the neck
        br = 1 + 0.012 * p["breath"]
        tf = J["tf"]                                    # a long-legged body has a shorter torso: the rings above the hips move with it
        rings = [(u * tf if u > 0 else u, wa * h * L["build"] * (br if 0.1 * h < u < 0.27 * h else 1), db * h * br, 0, 0) for u, wa, db in rings_t]
        path, zt = lathe(cam, J["pelvis"], Bc, rings)
        shared["torso"], shared["zt"] = path, zt
        rings_p =[(0.0, 0.098 * h * L["build"], 0.068 * h, 0, 0), (-0.06 * h, 0.104 * h * L["build"], 0.07 * h, 0, 0),
                   (-0.10 * h, 0.094 * h * L["build"], 0.064 * h, 0, 0)]
        pel, _ = lathe(cam, J["pelvis"], Bb, rings_p)
        nk = P(J["neck"])
        hd = P(J["head"])
        k = nk[3]

        def fn():
            if L.get("bottom") not in ("skirt", "dress"):       # (under a skirt or a dress the hips are the cloth's)
                fr.part(pel, L["pants"], ld, width=0.2 * h * k, line=lw)
            _pattern(L, c, pel, P(J["pelvis"])[:2], k, 5, lw, L["pants"])

            def occl(cv):
                # shade under the chin and inside the hood
                cv.drawOval(skia.Rect(hd[0] - 0.09 * h * k, nk[1] - 0.03 * h * k, hd[0] + 0.09 * h * k, nk[1] + 0.07 * h * k),
                            paint("#05060c", a=0.42, blur=0.035 * h * k))
                fold = skia.Path()
                pc = P(Bc.w(J["pelvis"], 0, 0.06 * h, 0.07 * h))
                fold.moveTo(pc[0] - 0.06 * h * k, pc[1] - 0.02 * h * k)
                fold.quadTo(pc[0], pc[1] + 0.02 * h * k, pc[0] + 0.07 * h * k, pc[1] - 0.03 * h * k)
                cv.drawPath(fold, paint("#05060c", a=0.22, blur=0.01 * h * k, stroke=0.012 * h * k))
            fr.part(path, L["top"], ld, width=0.24 * h * k, line=lw, occl=occl)
            _pattern(L, c, path, P(J["pelvis"])[:2], k, 6, lw, L["top"])
            # neck opening (shaded hollow on the torso), then a slim neck rising out of it: no hood volume
            nb = P(add(J["neck"], mul(Bc.u, -0.012 * h)))
            cl = skia.Path()
            cl.addOval(skia.Rect(nb[0] - 0.036 * h * k, nb[1] - 0.012 * h * k, nb[0] + 0.036 * h * k, nb[1] + 0.014 * h * k))
            c.save()
            c.clipPath(path, skia.ClipOp.kIntersect, True)
            c.drawPath(cl, paint(shade(L["top"], -0.35), a=0.9, blur=0.004 * h * k))
            c.restore()
            neck = capsule(nb[:2], 0.030 * h * k, P(add(J["neck"], mul(Bc.u, 0.04 * h)))[:2], 0.028 * h * k)
            fr.part(neck, shade(L["skin"], L.get("neck_shade", -0.18)), ld, width=0.06 * h * k, line=lw)
        parts.append(("torso", zt, fn))

    def head():
        hc = P(J["head"])
        R = J["R"]
        Hd = Head(cam, J["head"], J["Bh"], R, L.get("head_shape"))
        rings = head_rings(R, L.get("head_shape"))
        path, zh = lathe(cam, J["head"], J["Bh"], rings)
        k = hc[3]
        ex = p

        def fn():
            for side, lam in ((-1, -1.55), (1, 1.55)):                         # ears first: half hidden
                if -0.25 < Hd.facing(lam, 0.0) <= 0.42 or (Hd.facing(lam, 0.0) > 0.42 and (L.get("blank") or L.get("sil") or L.get("face", "normal") != "normal")):
                    c.save()
                    c.concat(Hd.decal(lam, -0.05, 1.0))
                    ear = skia.Path()
                    ear.addOval(skia.Rect(-0.085 * R, -0.16 * R, 0.085 * R, 0.14 * R))
                    fr.part(ear, L["skin"], (0, 1), width=0.3 * R, line=0.02 * R)   # decal units: metres
                    c.restore()
            fr.part(path, L["skin"], ld, width=2 * R * k, line=lw, outline=False, lit=0.14, dark=0.34)
            c.save()
            c.clipPath(path, skia.ClipOp.kIntersect, True)
            # underside of the jaw and a soft forehead highlight
            c.drawPath(path, paint(shader=lin((hc[0], hc[1] + 0.2 * R * k), (hc[0], hc[1] + 1.05 * R * k),
                                              [argb("#000000", 0), argb("#1a0d14", 0.30)])))
            if glow:
                fr.glow(*P(glow[0])[:2], glow[1] * k, glow[2], a=glow[3])
            if Hd.facing(-0.5, 0.45) > 0.2 and not L.get("sil"):
                c.save()
                c.concat(Hd.decal(-0.45 * (1 if ld[0] > 0 else -1), 0.5))
                c.drawOval(skia.Rect(-0.22 * R, -0.12 * R, 0.22 * R, 0.12 * R), paint("#ffffff", a=0.20, blur=0.08 * R))
                c.restore()
            if L.get("blank"):                                # featureless: the real head shape, no face, no hair
                c.restore()                                   # (a hood extra covers the back of the head)
                c.drawPath(path, paint(shade(L["skin"], -0.68), stroke=lw))
                return
            # fringe shadow on the forehead
            hp = hair_path(Hd, cam, L, p.get("hair_lift", 0.0), p.get("t", 0.0))
            sh = skia.Path(hp)
            sh.offset(0.0, 0.07 * R * k)
            c.drawPath(sh, paint("#1a0d14", a=0.35, blur=0.05 * R * k))
            if L.get("sil"):                                  # no features; maybe a faint grin in the dark
                if p.get("grin", 0) > 0 and Hd.facing(0.0, -0.5) > 0.1:
                    c.save()
                    c.concat(Hd.decal(0.0, -0.48))
                    g = skia.Path()
                    g.moveTo(-0.42 * R, -0.12 * R)
                    g.quadTo(0, 0.26 * R, 0.42 * R, -0.12 * R)
                    c.drawPath(g, paint("#d8d4cc", a=0.55 * p["grin"], stroke=0.05 * R))
                    c.restore()
                c.restore()
                c.drawPath(path, paint(shade(L["skin"], -0.68), stroke=lw))
                fr.part(hp, L["hair"], (ld[0] * 0.5, 1.0), width=2 * R * k, line=lw, lit=0.10, dark=0.3)
                return
            if L.get("killer"):                               # the carved smile, drawn on the head surface
                for sg in (-1, 1):
                    pts = [(sg * 0.17, -0.53), (sg * 0.38, -0.46), (sg * 0.58, -0.36), (sg * 0.74, -0.24)]
                    if min(Hd.facing(a, b) for a, b in pts) < 0.05:
                        continue
                    q = [cam.proj(Hd.surf(a, b, 1.005))[:2] for a, b in pts]
                    cut = smooth(q, closed=False)
                    c.drawPath(cut, paint("#3a0508", stroke=0.12 * R * k, a=0.9))
                    c.drawPath(cut, paint("#c0141f", stroke=0.06 * R * k))
                    for a, b in pts[1:3]:                     # stitch-like nicks across the cut
                        m0 = cam.proj(Hd.surf(a, b + 0.05, 1.005))[:2]
                        m1 = cam.proj(Hd.surf(a, b - 0.05, 1.005))[:2]
                        c.drawLine(*m0, *m1, paint("#3a0508", stroke=0.02 * R * k))
            face = L.get("face", "normal")                    # look "face": blank = no features at all; grin = dots and a smile that is too wide
            for side, lam in ((-1, -1.55), (1, 1.55)):        # an ear that faces the lens (a profile, a head turned away): on the head, with the line of its fold. A turned head is then a head, not a bare oval
                if Hd.facing(lam, 0.0) > 0.42 and face == "normal":
                    c.save()
                    c.concat(Hd.decal(lam, -0.12, 1.0))
                    ear = skia.Path()
                    ear.addOval(skia.Rect(-0.115 * R, -0.19 * R, 0.115 * R, 0.17 * R))
                    c.drawPath(ear, paint(shade(L["skin"], -0.07)))
                    c.drawPath(ear, paint(shade(L["skin"], -0.55), stroke=0.022 * R))
                    fold = skia.Path()
                    fold.moveTo(0.035 * R * side, -0.09 * R)
                    fold.quadTo(-0.06 * R * side, -0.01 * R, 0.02 * R * side, 0.08 * R)
                    c.drawPath(fold, paint(shade(L["skin"], -0.4), stroke=0.02 * R))
                    c.restore()
            if face == "grin":
                _grin(c, cam, Hd, k, ex, L)
            for side, lam in ((-1, -0.40), (1, 0.40)):
                f = Hd.facing(lam, 0.02)
                if f > 0.12 and face == "normal":
                    if not p.get("noeyes"):                         # a look extra draws its own eyes
                        c.save()
                        c.concat(Hd.decal(lam, 0.02))
                        draw_eye(c, R, side, ex if ("lid_R" if side > 0 else "lid_L") not in ex else dict(ex, lid=ex["lid_R" if side > 0 else "lid_L"]), L, ld)      # (lid_R, lid_L: one eye's own lid, e.g. one eye opening)
                        c.restore()
            if Hd.facing(0.0, -0.16) > 0.05 and face == "normal":               # nose
                c.save()
                c.concat(Hd.decal(0.0, -0.17, 1.03))
                nose = skia.Path()
                nose.addOval(skia.Rect(-0.11 * R, -0.08 * R, 0.11 * R, 0.09 * R))
                c.drawPath(nose, paint(shade(L["skin"], -0.25), a=0.55, blur=0.02 * R))
                c.drawOval(skia.Rect(-0.05 * R, -0.07 * R, 0.03 * R, -0.01 * R), paint("#ffffff", a=0.35, blur=0.01 * R))
                if not L.get("no_nose_arc"):                  # (reads as a second mouth over a drawn-on one)
                    arc = skia.Path()
                    arc.moveTo(-0.07 * R, 0.07 * R)
                    arc.quadTo(0, 0.12 * R, 0.07 * R, 0.07 * R)
                    c.drawPath(arc, paint(shade(L["skin"], -0.6), stroke=0.025 * R, a=0.8))
                c.restore()
            if Hd.facing(0.0, -0.50) > 0.08 and not p.get("nomouth") and face == "normal":
                c.save()
                c.concat(Hd.decal(0.0, -0.50))
                draw_mouth(c, R, ex, L)
                c.restore()
            c.restore()
            c.drawPath(path, paint(shade(L["skin"], -0.68), stroke=lw))
            wrap = p.get("wrap", 0.0)
            if wrap > 0:                                       # hair shows only where the gauze is already off
                c.save()
                c.clipRect(skia.Rect(-1e5, -1e5, 1e5, wrap_top(cam, Hd, wrap)))
            fr.part(hp, L["hair"], (ld[0] * 0.5, 1.0), width=2 * R * k, line=lw, lit=0.16, dark=0.45, rim=0.12)
            if face == "normal" and not (L.get("sil") or L.get("blank")):
                for side, lam in ((-1, -0.40), (1, 0.40)):
                    if Hd.facing(lam * 1.08, L.get("brow_mu", BROW_MU)) > 0.12:      # drawn over the hair: a fringe never hides the brows
                        c.save()
                        c.concat(Hd.decal(lam * 1.08, L.get("brow_mu", BROW_MU)))
                        bk = "brow_R" if side > 0 else "brow_L"      # (brow_R, brow_L: one brow on its own, a raised eyebrow)
                        draw_brow(c, R, side, ex if bk not in ex else dict(ex, brow=ex[bk]), L)
                        c.restore()
            if wrap > 0:
                c.restore()
                bandage(fr, cam, Hd, path, wrap, ld, lw, k, out)
        parts.append(("head", zh, fn))
        out["head"] = hc[:2]
        out["head_r"] = R * k
        rear = p["rear_view"] if "rear_view" in p else dot(Bc.f, norm(sub(cam.pos, J["pelvis"]))) < -0.1
        if (L.get("long") or L.get("style") == "long") and not (L.get("sil") or L.get("blank") or L.get("back")) and not J.get("headless"):      # (a head that is off the body: no locks run from it to the shoulders)
            _long_hair(parts, fr, cam, J, Hd, L, ld, lw, rear, zh)
        if J.get("headless") and shadow:                     # it lies or flies on its own: its own small shadow on the ground under it
            fr.ground_ellipse(cam, J["head"][0], J["head"][2], 0.9 * R, 0.5 * R, "#000000", 0.4 * max(0.0, 1.0 - (J["head"][1] - R - p["floor"]) / (6 * R)), blur_m=0.03, y=p["floor"] + 0.004)
        if L.get("wear", "none") != "none":
            _wear(parts, fr, cam, J, Hd, L, p, ld, lw, rear)
        if L.get("animal", "none") != "none":
            _animal(parts, fr, cam, J, Hd, L, p, ld, lw, rear)
        if L.get("back"):                                    # long hair hanging behind the head and neck
            def back_fn():
                q = [Hd.surf(-1.35, 0.35, 1.06), J["Bh"].w(J["head"], 1.08 * R, -1.35 * R, -0.25 * R),
                     J["Bh"].w(J["head"], 0.55 * R, -1.75 * R, -0.55 * R), J["Bh"].w(J["head"], -0.55 * R, -1.75 * R, -0.55 * R),
                     J["Bh"].w(J["head"], -1.08 * R, -1.35 * R, -0.25 * R), Hd.surf(1.35, 0.35, 1.06), Hd.surf(math.pi, 0.7, 1.06)]
                bp = smooth([cam.proj(w)[:2] for w in q], k=0.8)
                fr.part(bp, shade(L["hair"], -0.12), (ld[0] * 0.5, 1.0), width=2 * R * k, line=lw, lit=0.10, dark=0.45)
            front = dot(J["Bh"].f, norm(sub(cam.pos, J["head"]))) > 0
            parts.append(("hairback_front" if front else "hairback_rear", zh, back_fn))

    for s in ("R", "L"):
        leg(s)
        arm(s)
    torso()
    head()
    if L.get("bottom") in ("skirt", "dress"):
        _bottom(parts, fr, cam, J, L, ld, lw)
    # costume layers from the look (coat hem, mask, cap, backpack...): fn(parts, fr, cam, J, p, ld, lw, out)
    # appends parts of kind under / coat / overtorso / face / top
    for ex in L.get("extras", ()):
        ex(parts, fr, cam, J, p, ld, lw, out)
    # fixed layering: legs under the hem, the far arm behind the torso, the head over the torso and neck,
    # the near arm on top; depth only decides which arm (and leg) is the near one
    zt = next(z for k, z, _ in parts if k == "torso")
    by = lambda kind: sorted([q for q in parts if q[0] == kind], key=lambda q: -q[1])      # noqa: E731
    arms = by("arm")
    # pose["arm_near"] = {"R": bool, "L": bool} fixes an arm's layer from outside: a caller that plans poses for you decides it
    # once per shot, because an arm hanging at torso depth otherwise flips in front of and behind the body by itself
    fixed = p.get("arm_near") or {}
    is_near = lambda a: fixed.get(getattr(a[2], "side", None), a[1] <= zt)      # noqa: E731
    near = [a for a in arms if is_near(a)]
    # long hair over the back: seen from behind, a side arm sits at torso depth and flipped near/far over the hair
    # sheet mid-turn (Kuchisake R2); empty hands go under the hair, prop hands stay on top (umbrella canopy)
    tuck, fade = [], []
    back = dot(J["Bh"].f, norm(sub(cam.pos, J["head"])))
    if L.get("arms_under_hair") and back < 0:
        tuck = [a for a in near if not (held and held.get(a[2].side))]
        near = [a for a in near if a not in tuck]
        al = int(255 * max(0.0, min(1.0, (back + 0.6) / 0.6)))      # dead behind: under; toward side-on: fades over
        if al:
            def faded(f):
                def g():
                    fr.c.saveLayerAlpha(None, al)
                    f()
                    fr.c.restore()
                return g
            fade = [(a[0], a[1], faded(a[2])) for a in tuck]
    order = (by("under") + by("hairback_front") + by("leg") + [a for a in arms if not is_near(a)] + by("coat") + by("torso")
             + by("overtorso") + by("head") + by("hairback_rear") + tuck + by("face") + fade + near + by("top"))
    for _, _, fn in order:
        fn()
    out["J"] = J
    out["depth"] = P(J["pelvis"])[2]
    return out


def wrap_top(cam, Hd, wrap):
    return cam.proj(Hd.B.w(Hd.c, 0, Hd.R * (1.25 - 2.45 * (1 - wrap)), 0))[1]


def bandage(fr, cam, Hd, head_path, wrap, ld, lw, k, out):
    """Gauze wrapped round the whole head. wrap 1 = fully wrapped (eye slits), falling to 0 as it is unwound
    from the crown down; out["wrap_pt"] = screen point where the loose strip leaves the head."""
    c, R = fr.c, Hd.R
    region = head_path
    top = wrap_top(cam, Hd, wrap)
    b = region.getBounds()
    c.save()
    c.clipRect(skia.Rect(b.left() - 4, top, b.right() + 4, b.bottom() + 4))
    if wrap > 0.97:                                       # eye slits while fully wrapped
        for lam in (-0.40, 0.40):
            if Hd.facing(lam, 0.02) > 0.15:
                hole = skia.Path()
                hole.addOval(skia.Rect(-0.30 * R, -0.22 * R, 0.30 * R, 0.24 * R))
                hole.transform(Hd.decal(lam, 0.02, 1.02))
                c.clipPath(hole, skia.ClipOp.kDifference, True)
    big = skia.Path(region)
    sm = skia.Matrix()
    sm.setScale(1.10, 1.08, b.centerX(), b.centerY())
    big.transform(sm)
    fr.part(big, "#e9e3d6", ld, width=2 * R * k, line=lw, lit=0.12, dark=0.32)
    c.save()
    c.clipPath(big, skia.ClipOp.kIntersect, True)
    for i in range(-8, 9):                                # overlapping wraps: slanted soft folds
        y = b.centerY() + i * 0.17 * R * k
        c.drawLine(b.left() - 10, y + 0.12 * R * k, b.right() + 10, y - 0.12 * R * k,
                   paint("#a89f8e", a=0.55, stroke=0.018 * R * k))
    c.restore()
    c.restore()
    out["wrap_pt"] = (b.right() - 0.15 * R * k, max(top, b.top()) + 0.12 * R * k)


def replant(t, start, steps, h):
    """Feet that step to new spots one at a time. start = {"R": ankle, "L": ankle}; steps = [(side, t0, dur,
    target ankle)], in time order. The moving foot lifts on an arc; returns ankle_R, ankle_L, plant."""
    cur = dict(start)
    plant = "both"
    for side, t0, dur, tgt in steps:
        a = cur[side]
        u = max(0.0, min(1.0, (t - t0) / dur))
        if u <= 0:
            break
        e = 0.5 - 0.5 * math.cos(math.pi * u)
        lift = 0.035 * h * math.sin(math.pi * u)
        cur[side] = (a[0] + (tgt[0] - a[0]) * e, a[1] + (tgt[1] - a[1]) * e + lift, a[2] + (tgt[2] - a[2]) * e)
        if u < 1:
            plant = "L" if side == "R" else "R"
            break
        cur[side] = tgt
    return {"ankle_R": cur["R"], "ankle_L": cur["L"], "plant": plant}


# ---- props held in a hand ------------------------------------------------------------------------------
def phone(on=True, case="#3a3f4d"):
    """A slim phone in the hand (about 7.5 x 15.5 cm). on: the screen side lit; off: the back, a soft case colour
    with an edge highlight and the camera, so a phone held to the ear still reads as a phone."""
    def fn(fr, cam, J, s, hd, fd, k):
        h = J["h"]
        ax = math.degrees(math.atan2(*reversed(_screen_dir(cam, J["wr_" + s], fd))))
        m = skia.Matrix()
        m.setRotate(ax + 90)
        m.postTranslate(hd[0], hd[1])
        hw, top, bot = 0.024 * h * k, -0.072 * h * k, 0.02 * h * k
        body = skia.Path()
        body.addRoundRect(skia.Rect(-hw, top, hw, bot), 0.012 * h * k, 0.012 * h * k)
        body.transform(m)
        bb = body.getBounds()
        if on:
            fr.c.drawPath(body, paint("#14161d"))
            scr = skia.Path()
            scr.addRoundRect(skia.Rect(-hw * 0.84, top + 0.005 * h * k, hw * 0.84, bot - 0.005 * h * k), 0.008 * h * k, 0.008 * h * k)
            scr.transform(m)
            b = scr.getBounds()
            fr.c.drawPath(scr, paint(shader=lin((b.left(), b.top()), (b.right(), b.bottom()), [argb("#9fd0ff"), argb("#3f7fe0")])))
            fr.glow(b.centerX(), b.centerY(), 0.14 * h * k, "#3a78ff", a=0.3)
        else:
            fr.c.drawPath(body, paint(shader=lin((bb.left(), bb.top()), (bb.right(), bb.bottom()), [argb(shade(case, 0.25)), argb(case), argb(shade(case, -0.35))], [0, 0.5, 1])))
            lens = skia.Path()
            lens.addRoundRect(skia.Rect(-hw * 0.7, top + 0.008 * h * k, -hw * 0.05, top + 0.03 * h * k), 0.006 * h * k, 0.006 * h * k)
            lens.transform(m)
            fr.c.drawPath(lens, paint(shade(case, -0.55)))
            lb = lens.getBounds()
            fr.c.drawCircle(lb.centerX(), lb.centerY(), 0.004 * h * k, paint("#0b0c10"))
            fr.c.drawPath(body, paint("#ffffff", a=0.18, stroke=max(1.0, 0.003 * h * k)))
        fr.c.drawPath(body, paint("#05060a", stroke=max(1.2, 0.004 * h * k)))
    return fn


def knife(out_k=1.0):
    """Blade along the forearm direction, emerging from the fist; out_k 0..1 = how far it is drawn."""
    def fn(fr, cam, J, s, hd, fd, k):
        h = J["h"]
        d = _screen_dir(cam, J["wr_" + s], fd)
        n = (-d[1], d[0])
        L = 0.15 * h * k * out_k
        base = (hd[0] + d[0] * 0.02 * h * k, hd[1] + d[1] * 0.02 * h * k)
        tip = (base[0] + d[0] * L, base[1] + d[1] * L)
        wb = 0.016 * h * k
        blade = skia.Path()
        blade.moveTo(base[0] + n[0] * wb, base[1] + n[1] * wb)
        blade.lineTo(tip[0], tip[1])
        blade.lineTo(base[0] - n[0] * wb * 0.6, base[1] - n[1] * wb * 0.6)
        blade.close()
        fr.c.drawPath(blade, paint(shader=lin(base, (base[0] + n[0] * wb, base[1] + n[1] * wb), [argb("#8a93a6"), argb("#eef2fa")])))
        fr.c.drawPath(blade, paint("#20242e", stroke=max(1.2, 0.0035 * h * k)))
        hb = (hd[0] - d[0] * 0.03 * h * k, hd[1] - d[1] * 0.03 * h * k)
        fr.c.drawLine(hb[0], hb[1], base[0], base[1], paint("#2a1c16", stroke=0.022 * h * k))
    return fn


def bottle(tilt=0.0):
    """Glass bottle gripped round its middle, axis across the fist; tilt (deg) turns the mouth downward to pour.
    J["prop_tip"] = screen point of the bottle mouth."""
    def fn(fr, cam, J, s, hd, fd, k):
        h = J["h"]
        d = _screen_dir(cam, J["wr_" + s], fd)
        a = math.atan2(d[1], d[0]) - math.pi / 2 + math.radians(tilt) * (1 if d[0] >= 0 else -1)
        ax = (math.cos(a), math.sin(a))
        L0, L1, r = 0.09 * h * k, 0.06 * h * k, 0.022 * h * k
        base = (hd[0] + ax[0] * L0, hd[1] + ax[1] * L0)
        sh = (hd[0] - ax[0] * L1, hd[1] - ax[1] * L1)
        tip = (sh[0] - ax[0] * 0.05 * h * k, sh[1] - ax[1] * 0.05 * h * k)
        body = union(capsule(base, r, sh, r * 0.95), capsule(sh, r * 0.45, tip, r * 0.38))
        fr.part(body, "#3d6b4a", (0.3, 1.0), width=2 * r, line=max(1.2, 0.004 * h * k), lit=0.4, dark=0.4)
        lab = capsule((hd[0] + ax[0] * 0.02 * h * k, hd[1] + ax[1] * 0.02 * h * k), r * 0.98,
                      (hd[0] + ax[0] * 0.065 * h * k, hd[1] + ax[1] * 0.065 * h * k), r * 0.98)
        fr.c.drawPath(lab, paint("#e8e2cf", a=0.9))
        J["prop_tip"] = tip
        J["prop_dir"] = (-ax[0], -ax[1])
    return fn


def match(lit=0.0, t=0.0):
    """A match pinched in the fist, pointing up along the thumb; lit 0..1 grows the flame."""
    def fn(fr, cam, J, s, hd, fd, k):
        h = J["h"]
        d = _screen_dir(cam, J["wr_" + s], fd)
        up = (d[1], -d[0]) if -d[0] < 0 else (-d[1], d[0])          # the perpendicular that points up on screen
        base = (hd[0] + d[0] * 0.012 * h * k, hd[1] + d[1] * 0.012 * h * k)
        tip = (base[0] + up[0] * 0.045 * h * k, base[1] + up[1] * 0.045 * h * k)
        fr.c.drawLine(*base, *tip, paint("#c9a36a", stroke=0.006 * h * k))
        fr.c.drawCircle(*tip, 0.0055 * h * k, paint("#7a1a12"))
        if lit > 0:
            fl = lit * (1 + 0.12 * math.sin(t * 47) + 0.08 * math.sin(t * 83))
            r = 0.012 * h * k * fl
            flame = skia.Path()
            flame.moveTo(tip[0] - r, tip[1])
            flame.quadTo(tip[0] - r * 0.9, tip[1] - r * 2.2, tip[0] + up[0] * r * 3.2, tip[1] + up[1] * r * 3.2)
            flame.quadTo(tip[0] + r * 0.9, tip[1] - r * 2.2, tip[0] + r, tip[1])
            flame.close()
            fr.glow(tip[0], tip[1] - r, 0.25 * h * k * lit, "#ff8a2a", a=0.55)
            fr.c.drawPath(flame, paint("#ffb347"))
            fr.c.drawCircle(tip[0], tip[1] - r * 0.5, r * 0.55, paint("#fff4c8"))
        J["prop_tip"] = tip
    return fn


def matchbox():
    def fn(fr, cam, J, s, hd, fd, k):
        h = J["h"]
        d = _screen_dir(cam, J["wr_" + s], fd)
        m = skia.Matrix()
        m.setRotate(math.degrees(math.atan2(d[1], d[0])))
        m.postTranslate(hd[0] + d[0] * 0.015 * h * k, hd[1] + d[1] * 0.015 * h * k)
        bx = skia.Path()
        bx.addRect(skia.Rect(-0.018 * h * k, -0.03 * h * k, 0.018 * h * k, 0.03 * h * k))
        bx.transform(m)
        fr.part(bx, "#c23a2a", (0.3, 1.0), width=0.05 * h * k, line=max(1.2, 0.003 * h * k), lit=0.3)
        st = skia.Path()
        st.addRect(skia.Rect(0.012 * h * k, -0.028 * h * k, 0.018 * h * k, 0.028 * h * k))
        st.transform(m)
        fr.c.drawPath(st, paint("#4a2a1a"))
    return fn


def hand_mirror(face=None):
    """Round hand mirror. Seen from behind the holder (over the shoulder) the glass faces the camera, so
    `face` draws the holder's reflection: pale skin, dark hair, eyes and a smile."""
    def fn(fr, cam, J, s, hd, fd, k):
        h = J["h"]
        up = (0.0, -1.0)
        top = (hd[0] + up[0] * 0.07 * h * k, hd[1] + up[1] * 0.07 * h * k)
        fr.c.drawLine(hd[0], hd[1], *top, paint("#3b2618", stroke=0.016 * h * k))
        o = skia.Path()
        r = 0.065 * h * k
        rect = skia.Rect(top[0] - r * 0.85, top[1] - 2 * r, top[0] + r * 0.85, top[1])
        o.addOval(rect)
        fr.part(o, "#5a3a24", (0.3, 1.0), width=2 * r, line=max(1.2, 0.004 * h * k), lit=0.25)
        if face:
            cx, cy = top[0], top[1] - r
            g = skia.Path()
            g.addOval(skia.Rect(cx - r * 0.7, cy - r * 0.85, cx + r * 0.7, cy + r * 0.85))
            fr.c.drawPath(g, paint("#9fb0c4"))
            fr.c.save()
            fr.c.clipPath(g, doAntiAlias=True)
            fr.c.drawOval(skia.Rect(cx - r * 0.5, cy - r * 0.5, cx + r * 0.5, cy + r * 0.8), paint(face))
            fr.c.drawOval(skia.Rect(cx - r * 0.56, cy - r * 0.75, cx + r * 0.56, cy - r * 0.1), paint("#141418"))
            for ex in (-0.2, 0.2):
                fr.c.drawCircle(cx + ex * r, cy + 0.08 * r, 0.07 * r, paint("#141418"))
            sm = skia.Path()
            sm.moveTo(cx - 0.25 * r, cy + 0.38 * r)
            sm.quadTo(cx, cy + 0.6 * r, cx + 0.25 * r, cy + 0.38 * r)
            fr.c.drawPath(sm, paint("#3a1a1a", stroke=0.05 * r))
            fr.c.drawLine(cx - 0.45 * r, cy - 0.6 * r, cx - 0.1 * r, cy - 0.75 * r, paint("#ffffff", a=0.5, stroke=0.06 * r))
            fr.c.restore()
        J["prop_tip"] = (top[0], top[1] - r)
    return fn


def _screen_dir(cam, w0, d):
    a = cam.proj(w0)
    b = cam.proj(add(w0, mul(d, 0.1)))
    v = (b[0] - a[0], b[1] - a[1])
    n = math.hypot(*v) or 1.0
    return (v[0] / n, v[1] / n)


# ---- walking with planted feet -------------------------------------------------------------------------
def gait(t, start, yaw, step, rate, n=None, t0=0.0, sep=0.065, lift=0.07, h=1.7):
    """Walk along the facing direction from `start` (pelvis ground point at t0). One foot is planted at a
    time and never moves; the pelvis travels exactly one step per step period (speed = step x rate). With
    n steps the walk ends: the last step decelerates and lands with both feet planted under the pelvis.
    Returns dict(x, z, ankle_R, ankle_L, swing (+1 = right leg forward .. -1), moving, plant)."""
    B = Basis.yaw(yaw)
    f = B.f
    st = (t - t0) * rate
    moving = True
    if n is not None and st >= n:
        st, moving = float(n), False
    k = math.floor(st)
    ph = st - k
    if n is not None and k == n - 1:
        prog = (n - 1) + (ph + ph * ph - ph ** 3)
    elif not moving:
        prog = float(n)
    else:
        prog = st
    pos = add(start, mul(f, prog * step))

    def land(i, side):
        sg = 1 if side == "R" else -1
        return add(start, mul(f, (i + 0.5) * step), mul(B.r, sg * sep * h / 1.0), (0, 0.035 * h, 0))
    side_of = lambda i: "R" if i % 2 == 0 else "L"      # noqa: E731
    res = {"x": pos[0], "z": pos[2], "moving": moving}
    if not moving:
        res["ankle_" + side_of(n - 1)] = land(n - 1, side_of(n - 1))
        res["ankle_" + side_of(n)] = land(n, side_of(n))
        res["plant"] = "both"
        res["swing"] = 0.0
        return res
    stance, swing = side_of(k), side_of(k + 1)
    res["ankle_" + stance] = land(k, stance)
    a0, a1 = land(k - 1, swing), land(k + 1, swing)
    e = ph * ph * (3 - 2 * ph)
    sw = add(mul(a0, 1 - e), mul(a1, e))
    res["ankle_" + swing] = add(sw, (0, lift * h / 1.7 * math.sin(math.pi * ph), 0))
    res["plant"] = stance
    fwd = -math.cos(math.pi * ph)                      # swing leg passes from behind (-1) to front (+1), eased ends
    if n is not None and k == n - 1:
        fwd = e - 1                                   # last step lands beside the stance foot: arms settle to 0
    res["swing"] = fwd if swing == "R" else -fwd
    res["bob"] = -0.012 * math.cos(2 * math.pi * ph)
    return res
