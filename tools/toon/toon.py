"""Smooth cartoon renderer (2026-11-05, replaces the pixel engine for story reels).

Everything is drawn with antialiased Skia paths at the output resolution; positions are floats evaluated
from elapsed time. The world is a simple 3D space (metres, y up, z away from the camera) seen through a
perspective camera, so parallax, perspective and attached light/shadow come for free.

    cam = Camera(pos=(0, 1.4, 1.0), yaw=0, f=1300)
    fr = Frame(scale=1.0)                     # 1080x1920 (scale 0.5 = 540x960 preview, same framing)
    fr.box(cam, (x0, x1), (y0, y1), (z0, z1), "#334", light=LIGHT)
    fr.part(path, "#e8e8f0", light=(0.3, 1.0))   # shaded shape: fill, inner gradient, soft rim, outline
    rgb = fr.array()
"""
import math
import os

import numpy as np
import skia

W, H = 1080, 1920

# Caption / title fonts: set TOON_FONT (heavy) and TOON_FONT_BOLD to override; otherwise the first one found.
_DEJAVU = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",
           "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"]     # Debian, Fedora, Arch
_HEAVY = ["C:/Windows/Fonts/ariblk.ttf", "/System/Library/Fonts/Supplemental/Arial Black.ttf", "/Library/Fonts/Arial Black.ttf",
          "/usr/share/fonts/truetype/msttcorefonts/Arial_Black.ttf"] + _DEJAVU
_BOLD = ["C:/Windows/Fonts/arialbd.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf",
         "/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf"] + _DEJAVU


def font_path(bold=False):
    var = "TOON_FONT_BOLD" if bold else "TOON_FONT"
    env = os.environ.get(var)
    if env and not os.path.exists(env):
        raise FileNotFoundError(f"{var} points to a file that does not exist: {env}")
    for p in ([env] if env else []) + (_BOLD if bold else _HEAVY):
        if os.path.exists(p):
            return p
    raise FileNotFoundError("no caption font found: set TOON_FONT to a .ttf (Arial Black or any heavy sans)")


def typeface(bold=False):
    return skia.Typeface.MakeFromFile(font_path(bold))
# HQ shading (2026-11-06, opt-in per reel): smoother falloff, a soft key sheen, a faint bounce light in the shadow
HQ = {"on": False, "sheen": 0.06, "bounce": 0.0}   # bounce > 0 ghosts zigzag hairlines


# ---- colour ----------------------------------------------------------------------------------------
def hexrgb(c):
    if isinstance(c, str):
        c = c.lstrip("#")
        if len(c) == 3:
            c = "".join(ch * 2 for ch in c)
        return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return tuple(c)


def mix(a, b, t):
    a, b = hexrgb(a), hexrgb(b)
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def shade(c, k):
    """k > 0 lightens toward white, k < 0 darkens toward a cool near-black (shadows go blue, not grey)."""
    return mix(c, (1, 1, 1), k) if k >= 0 else mix(c, (0.03, 0.04, 0.10), -k)


def argb(c, a=1.0):
    r, g, b = hexrgb(c)
    return skia.ColorSetARGB(int(max(0, min(1, a)) * 255), int(r * 255), int(g * 255), int(b * 255))


def paint(c=None, a=1.0, blur=0.0, stroke=0.0, blend=None, shader=None, cap="round"):
    p = skia.Paint()
    p.setAntiAlias(True)
    if c is not None:
        p.setColor(argb(c, a))
    if shader is not None:
        p.setShader(shader)
        p.setAlphaf(a)
    if blur > 0.05:
        p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    if stroke:
        p.setStyle(skia.Paint.kStroke_Style)
        p.setStrokeWidth(stroke)
        p.setStrokeCap(skia.Paint.kRound_Cap if cap == "round" else skia.Paint.kButt_Cap)
        p.setStrokeJoin(skia.Paint.kRound_Join)
    if blend:
        p.setBlendMode({"add": skia.BlendMode.kPlus, "screen": skia.BlendMode.kScreen,
                        "mul": skia.BlendMode.kMultiply}[blend])
    return p


def lin(p0, p1, cols, pos=None):
    """cols: skia colour ints (use argb())."""
    return skia.GradientShader.MakeLinear([skia.Point(*p0), skia.Point(*p1)], cols, pos)


def rad(c, r, cols, pos=None, sx=1.0, sy=1.0):
    m = skia.Matrix()
    m.setScale(sx, sy, c[0], c[1])
    return skia.GradientShader.MakeRadial(skia.Point(*c), max(r, 0.01), cols, pos, skia.TileMode.kClamp, 0, m)


# ---- camera ----------------------------------------------------------------------------------------
class Camera:
    """Pinhole camera with yaw only (verticals stay vertical); horizon = principal point height."""

    def __init__(self, pos, yaw=0.0, f=1300.0, horizon=0.46):
        self.pos, self.yaw, self.f, self.horizon = tuple(pos), math.radians(yaw), f, horizon
        self.fwd = (math.sin(self.yaw), 0.0, math.cos(self.yaw))
        self.right = (math.cos(self.yaw), 0.0, -math.sin(self.yaw))

    def view(self, P):
        d = (P[0] - self.pos[0], P[1] - self.pos[1], P[2] - self.pos[2])
        return (d[0] * self.right[0] + d[2] * self.right[2], d[1], d[0] * self.fwd[0] + d[2] * self.fwd[2])

    def proj(self, P):
        """World point -> (screen x, screen y, depth, px per metre) in 1080x1920 output pixels."""
        x, y, z = self.view(P)
        z = max(z, 1e-3)
        s = self.f / z
        return (W / 2 + x * s, H * self.horizon - y * s, z, s)

    def rel_yaw(self, yaw_deg, at):
        """How a character facing yaw_deg (world) at point `at` is seen: 0 = facing the camera,
        +90 = profile facing screen right."""
        y = math.radians(yaw_deg)
        f = (math.sin(y), 0.0, -math.cos(y))
        to = (self.pos[0] - at[0], 0.0, self.pos[2] - at[2])
        n = math.hypot(to[0], to[2]) or 1.0
        to = (to[0] / n, 0, to[2] / n)
        rx, rz = -to[2], to[0]                    # screen-right axis as seen from the character position
        return math.degrees(math.atan2(f[0] * rx + f[2] * rz, f[0] * to[0] + f[2] * to[2]))


# ---- frame -----------------------------------------------------------------------------------------
class Frame:
    def __init__(self, scale=1.0, bg="#05070f"):
        self.k = scale
        self.surf = skia.Surface(int(W * scale), int(H * scale))
        self.c = self.surf.getCanvas()
        self.c.scale(scale, scale)
        self.c.clear(argb(bg))

    def array(self):
        a = self.surf.makeImageSnapshot().toarray(colorType=skia.ColorType.kRGBA_8888_ColorType)
        return np.ascontiguousarray(a[:, :, :3])

    # -- shaded part: the core of the look -----------------------------------------------------------
    def part(self, path, base, light=(0.35, 1.0), width=None, line=2.4, lit=0.16, dark=0.38, rim=0.0,
             outline=True, occl=None):
        """Fill `path` with `base`, then (clipped to it) a soft gradient from the lit side to the shadow
        side, a blurred inner shadow along the far edge and an optional rim highlight; outline in a dark
        shade of the base colour. light = screen direction the light travels (down-right = (0.35, 1))."""
        c = self.c
        dark *= HQ.get("dark_k", 1.0)                    # an episode can deepen every shadow side at once
        b = path.getBounds()
        w = width or max(b.width(), b.height(), 1.0)
        lx, ly = light
        n = math.hypot(lx, ly) or 1.0
        lx, ly = lx / n, ly / n
        cx, cy = b.centerX(), b.centerY()
        ext = 0.5 * (abs(lx) * b.width() + abs(ly) * b.height()) + 1
        c.drawPath(path, paint(base))
        c.save()
        c.clipPath(path, skia.ClipOp.kIntersect, True)
        p0, p1 = (cx - lx * ext, cy - ly * ext), (cx + lx * ext, cy + ly * ext)
        if HQ["on"]:                                     # smoothstep-like falloff: no visible gradient edges
            cols = [shade(base, lit), shade(base, lit * 0.55), base, shade(base, -dark * 0.4), shade(base, -dark * 0.85),
                    shade(base, -dark)]
            c.drawRect(b.makeOutset(4, 4), paint(shader=lin(p0, p1, [argb(x) for x in cols], [0.0, 0.2, 0.45, 0.68, 0.88, 1.0])))
        else:
            c.drawRect(b.makeOutset(4, 4), paint(shader=lin(p0, p1, [argb(shade(base, lit)), argb(base), argb(shade(base, -dark))],
                                                           [0.0, 0.45, 1.0])))
        # inner soft shadow hugging the edge: reads as a rounded volume
        c.drawPath(path, paint(shade(base, -dark * 0.9), a=0.45, blur=w * 0.09, stroke=w * 0.14))
        if HQ["on"] and w > 6:
            # faint bounce light just inside the shadow-side edge, then a soft sheen toward the key light
            if HQ["bounce"] > 0:
                r = skia.Path(path)
                r.offset(-lx * w * 0.07, -ly * w * 0.07)
                c.save()
                c.clipPath(r, skia.ClipOp.kDifference, True)
                c.drawPath(path, paint(shade(base, 0.35), a=HQ["bounce"], blur=w * 0.035))
                c.restore()
            hx, hy, hr = cx - lx * ext * 0.5, cy - ly * ext * 0.5, w * 0.34
            c.drawCircle(hx, hy, hr, paint(blend="screen", shader=rad((hx, hy), hr, [argb((1, 0.97, 0.92), HQ["sheen"]),
                                                                               argb((1, 0.97, 0.92), 0)], [0, 1])))
        if rim:
            r = skia.Path(path)
            r.offset(lx * w * 0.12, ly * w * 0.12)
            c.save()
            c.clipPath(r, skia.ClipOp.kDifference, True)
            c.drawPath(path, paint((0.75, 0.85, 1.0), a=rim, blur=w * 0.03))
            c.restore()
        if occl:
            occl(c)
        c.restore()
        if outline:
            c.drawPath(path, paint(shade(base, -0.72), stroke=line))

    def soft(self, path, colr, a, blur, clip=None):
        if clip is not None:
            self.c.save()
            self.c.clipPath(clip, skia.ClipOp.kIntersect, True)
        self.c.drawPath(path, paint(colr, a=a, blur=blur))
        if clip is not None:
            self.c.restore()

    def glow(self, x, y, r, colr, a=1.0, sx=1.0, sy=1.0):
        self.c.drawCircle(x, y, r * max(sx, sy), paint(blend="add", shader=rad(
            (x, y), r, [argb(colr, a), argb(colr, a * 0.35), argb(colr, 0)], [0, 0.35, 1], sx, sy)))

    # -- world primitives -------------------------------------------------------------------------------
    def poly(self, cam, pts, colr=None, shader=None, a=1.0, blur=0.0, outline=None, line=2.0):
        P = clip_near([cam.view(p) for p in pts])
        if len(P) < 3:
            return None
        path = skia.Path()
        for i, (x, y, z) in enumerate(P):
            s = cam.f / z
            sx, sy = W / 2 + x * s, H * cam.horizon - y * s
            (path.moveTo if i == 0 else path.lineTo)(sx, sy)
        path.close()
        self.c.drawPath(path, paint(colr, a=a, blur=blur, shader=shader(path) if shader else None))
        if outline:
            self.c.drawPath(path, paint(outline, stroke=line))
        return path

    def box(self, cam, xs, ys, zs, colr, light=None, line=2.0, top_k=0.14, side_k=-0.22, a=1.0):
        """Axis-aligned box; visible faces shaded by orientation and the distance to the light."""
        (x0, x1), (y0, y1), (z0, z1) = xs, ys, zs
        faces = [((0, 0, -1), [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], 0.0),
                 ((0, 1, 0), [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], top_k),
                 ((0, -1, 0), [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], -0.45),
                 ((-1, 0, 0), [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)], side_k),
                 ((1, 0, 0), [(x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)], side_k),
                 ((0, 0, 1), [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], -0.3)]
        C = cam.pos
        for n, pts, k in faces:
            fc = [sum(p[i] for p in pts) / 4 for i in range(3)]
            if n[0] * (C[0] - fc[0]) + n[1] * (C[1] - fc[1]) + n[2] * (C[2] - fc[2]) <= 0:
                continue
            kk = k
            if light is not None:
                d = math.dist(fc, light)
                kk += 0.35 * max(0.0, 1.0 - d / 3.5) - 0.12
            self.poly(cam, pts, colr=shade(colr, kk), a=a, outline=shade(colr, -0.75), line=line)

    def ground_ellipse(self, cam, cx, cz, rx, rz, colr, a, blur_m=0.0, y=0.0, add=False, n=40):
        pts = [(cx + rx * math.cos(2 * math.pi * i / n), y, cz + rz * math.sin(2 * math.pi * i / n)) for i in range(n)]
        P = clip_near([cam.view(p) for p in pts])
        if len(P) < 3:
            return
        path = skia.Path()
        for i, (x, yy, z) in enumerate(P):
            s = cam.f / z
            (path.moveTo if i == 0 else path.lineTo)(W / 2 + x * s, H * cam.horizon - yy * s)
        path.close()
        s = cam.proj((cx, y, cz))[3]
        self.c.drawPath(path, paint(colr, a=a, blur=blur_m * s, blend="add" if add else None))


def clip_near(P, zn=0.05):
    out = []
    for i in range(len(P)):
        a, b = P[i], P[(i + 1) % len(P)]
        if a[2] >= zn:
            out.append(a)
        if (a[2] >= zn) != (b[2] >= zn):
            t = (zn - a[2]) / (b[2] - a[2])
            out.append(tuple(a[j] + (b[j] - a[j]) * t for j in range(3)))
    return out


# ---- rain: world-space streaks, fixed seed, evaluated from time --------------------------------------
class Rain:
    def __init__(self, n=2600, box=((-7, 10), (0, 4.2), (1.5, 16)), speed=7.5, seed=3, shelter=None):
        r = np.random.default_rng(seed)
        self.p = np.stack([r.uniform(*box[0], n), r.uniform(*box[1], n), r.uniform(*box[2], n)], 1)
        self.y0, self.y1 = box[1]
        self.v = speed * r.uniform(0.85, 1.15, n)
        self.shelter = shelter          # (x0, x1, z0, z1, roof_y): no rain under the roof

    def draw(self, fr, cam, t, light=None, colr=(0.72, 0.8, 0.95), amax=0.55, zmin=0.4, wmax=99.0):
        """amax / zmin / wmax cap the streak alpha, skip drops nearer than zmin and cap the stroke width
        (the city street keeps near drops thin so they never sit over faces)."""
        span = self.y1 - self.y0
        y = self.y0 + (self.p[:, 1] - self.y0 - self.v * t) % span
        for (x, _, z), yy, v in zip(self.p, y, self.v):
            if self.shelter:
                x0, x1, z0, z1, ry = self.shelter
                if x0 < x < x1 and z0 < z < z1 and yy < ry:
                    continue
            a = cam.proj((x, yy, z))
            if a[2] < zmin or not (-20 < a[0] < W + 20 and -40 < a[1] < H + 40):
                continue
            b = cam.proj((x - 0.02, yy + v / 30 * 0.9, z))       # one frame of motion = the streak
            alpha = min(amax, 0.9 / a[2] + 0.06)
            if light is not None:
                alpha += 0.5 * max(0.0, 1 - math.dist((x, yy, z), light) / 2.8)
            fr.c.drawLine(a[0], a[1], b[0], b[1], paint(colr, a=min(alpha, 0.85, amax * 1.6),
                                                        stroke=min(wmax, max(0.8, 2.2 / a[2] ** 0.5))))
