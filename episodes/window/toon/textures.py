"""Procedural tiling textures (cached PNGs in tex/) and an exact plane mapper.

A camera pinhole maps any world plane to the screen by a homography, so a tile drawn through skia's
setPolyToPoly (fitted on 4 points of the plane that are in front of the lens) lands exactly in perspective.
"""
import math
import os

import numpy as np
import skia
from PIL import Image, ImageFilter

from toon import clip_near, W, H

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, "tex")
_cache = {}


def _rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32)


def _save(name, a):
    os.makedirs(TEX, exist_ok=True)
    Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).save(os.path.join(TEX, name + ".png"))


def make_brick(ppm=320):
    """0.9 m x 0.6 m tile: 4 stretchers x 8 courses, running bond, 10 mm mortar; sunlit from the upper left."""
    w, h = int(0.9 * ppm), int(0.6 * ppm)
    rng = np.random.default_rng(4)
    a = np.zeros((h, w, 3), np.float32)
    a[:] = _rgb("#b8aa94")
    bw, bh, m = 0.225 * ppm, 0.075 * ppm, 0.010 * ppm
    yy, xx = np.mgrid[0:h, 0:w]
    base = [_rgb(c) for c in ("#9c4a33", "#a6553a", "#8e422e", "#b0603f", "#87402f", "#9a5038", "#7c3a2a")]
    for row in range(8):
        off = (bw / 2) * (row % 2)
        for col in range(-1, 5):
            x0 = col * bw + off + m / 2
            y0 = row * bh + m / 2
            col_ = base[rng.integers(len(base))] * rng.uniform(0.9, 1.08)
            sel = (xx >= x0) & (xx < x0 + bw - m) & (yy >= y0) & (yy < y0 + bh - m)
            sel |= (xx + w >= x0) & (xx + w < x0 + bw - m) & (yy >= y0) & (yy < y0 + bh - m)
            sel |= (xx - w >= x0) & (xx - w < x0 + bw - m) & (yy >= y0) & (yy < y0 + bh - m)
            a[sel] = col_
            ty = (yy - y0) / max(1.0, bh - m)
            a[sel & (ty < 0.16)] *= 1.12                                  # lit top edge
            a[sel & (ty > 0.84)] *= 0.80                                  # shadowed lower edge
    a *= (1 + 0.10 * (rng.random((h, w, 1)) - 0.5))
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))
    a = np.asarray(img, np.float32)
    spots = rng.random((h, w)) > 0.992
    a[spots] *= 0.7
    _save("brick", a)


def make_lawn(ppm=160):
    s = int(2.0 * ppm)
    rng = np.random.default_rng(9)
    a = np.zeros((s, s, 3), np.float32)
    a[:] = _rgb("#7a9a3e")
    n = rng.random((s // 8, s // 8))
    big = np.asarray(Image.fromarray((n * 255).astype(np.uint8)).resize((s, s), Image.BICUBIC), np.float32) / 255
    a *= (0.88 + 0.22 * big[..., None])
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    for _ in range(9000):                                                  # grass blades
        x, y = rng.uniform(0, s), rng.uniform(0, s)
        L = rng.uniform(4, 10)
        ang = rng.uniform(-0.5, 0.5)
        c = tuple(int(v) for v in (_rgb(rng.choice(["#94b44e", "#5f7f2e", "#a8c060", "#6c8c34", "#4f6e28"])) * rng.uniform(0.9, 1.1)).clip(0, 255))
        d.line([(x, y), (x + L * math.sin(ang), y - L * math.cos(ang))], fill=c, width=1)
    _save("lawn", np.asarray(img, np.float32))


def make_soil(ppm=220):
    s = int(1.0 * ppm)
    rng = np.random.default_rng(5)
    a = np.zeros((s, s, 3), np.float32)
    a[:] = _rgb("#4a3324")
    a *= (0.8 + 0.35 * rng.random((s, s, 1)))
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    for _ in range(700):                                                   # bark mulch chips and small stones
        x, y = rng.uniform(0, s), rng.uniform(0, s)
        r = rng.uniform(1.5, 4.5)
        c = tuple(int(v) for v in _rgb(rng.choice(["#6b4a30", "#3a281c", "#7a5a3c", "#5a4638", "#8a7a68"])))
        d.ellipse([x - r, y - r * 0.6, x + r, y + r * 0.6], fill=c)
    _save("soil", np.asarray(img, np.float32))


def make_hedge(ppm=260):
    s = int(1.0 * ppm)
    rng = np.random.default_rng(12)
    img = Image.new("RGB", (s, s), tuple(int(v) for v in _rgb("#2c4a22")))
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    for _ in range(5200):
        x, y = rng.uniform(-6, s + 6), rng.uniform(-6, s + 6)
        r = rng.uniform(2.0, 4.6)
        c = tuple(int(v) for v in (_rgb(rng.choice(["#3f6a2c", "#4f7c34", "#2f5426", "#5c8a3c", "#36602a", "#6f9a44"])) * rng.uniform(0.85, 1.12)).clip(0, 255))
        ang = rng.uniform(0, math.pi)
        dx, dy = math.cos(ang) * r, math.sin(ang) * r * 0.55
        d.ellipse([x - abs(dx) - 1, y - abs(dy) - 1, x + abs(dx) + 1, y + abs(dy) + 1], fill=c)
        for ox in (-s, s):
            d.ellipse([x + ox - abs(dx) - 1, y - abs(dy) - 1, x + ox + abs(dx) + 1, y + abs(dy) + 1], fill=c)
    a = np.asarray(img, np.float32)
    a *= (0.85 + 0.25 * rng.random((s, s, 1)))
    _save("hedge", a)


def make_wood(ppm=200):
    """Dark oak floorboards, 0.14 m boards, for the bedroom and landing (the living room uses the Room kit)."""
    w, h = int(1.4 * ppm), int(2.0 * ppm)
    rng = np.random.default_rng(3)
    a = np.zeros((h, w, 3), np.float32)
    for i in range(10):
        c = _rgb("#6a4a32") * rng.uniform(0.85, 1.1)
        x0, x1 = int(i * 0.14 * ppm), int((i + 1) * 0.14 * ppm)
        a[:, x0:x1] = c
        a[:, x0:x0 + 1] *= 0.55
        yy = np.arange(h)[:, None, None]
        a[:, x0:x1] *= (1 + 0.06 * np.sin(yy / rng.uniform(5, 12) + rng.uniform(0, 6)))
        cut = int(rng.uniform(0, h))
        a[cut:cut + 1, x0:x1] *= 0.6
    _save("wood", a)


def make_wallpaper(ppm=300):
    """0.54 m repeat for the nursery bedroom: soft sage stripes with a small cream flower sprig, half-drop."""
    from PIL import ImageDraw
    w, h = int(0.54 * ppm), int(0.54 * ppm)
    rng = np.random.default_rng(6)
    a = np.zeros((h, w, 3), np.float32)
    a[:] = _rgb("#6c7c68")
    for k in range(3):                                                     # paired pinstripes every 0.18 m
        x0 = int((k * 0.18 + 0.02) * ppm)
        a[:, x0:x0 + int(0.05 * ppm)] = _rgb("#74866f")
        a[:, x0 + int(0.055 * ppm):x0 + int(0.06 * ppm)] = _rgb("#8a9a80")
    a *= (0.96 + 0.06 * rng.random((h, w, 1)))
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    for k in range(3):
        for j in range(2):
            cx = (k * 0.18 + 0.135) * ppm
            cy = (j * 0.27 + (0.135 if k % 2 else 0.0)) * ppm
            for ox, oy in ((0, 0), (0, h), (0, -h)):
                x, y = cx + ox, cy + oy
                d.line([(x, y + 9), (x, y - 2)], fill=(92, 112, 82), width=2)
                for ang in range(0, 360, 72):
                    px, py = x + 4.5 * math.cos(math.radians(ang)), y - 4 + 4.5 * math.sin(math.radians(ang))
                    d.ellipse([px - 2.6, py - 2.6, px + 2.6, py + 2.6], fill=(214, 200, 160))
                d.ellipse([x - 1.6, y - 5.6, x + 1.6, y - 2.4], fill=(196, 150, 96))
    _save("wallpaper", np.asarray(img, np.float32))


def make_rug(ppm=150):
    """One whole 2.2 m x 1.6 m rug (no repeat): navy field, cream and rust borders, a diamond medallion."""
    from PIL import ImageDraw
    w, h = int(2.2 * ppm), int(1.6 * ppm)
    img = Image.new("RGB", (w, h), (42, 52, 82))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w - 1, h - 1], outline=(212, 196, 160), width=int(0.10 * ppm))
    m = int(0.14 * ppm)
    d.rectangle([m, m, w - 1 - m, h - 1 - m], outline=(150, 64, 44), width=int(0.05 * ppm))
    m2 = int(0.22 * ppm)
    for x in range(m2, w - m2, int(0.12 * ppm)):                           # a row of small diamonds inside the border
        for y in (m2, h - 1 - m2):
            d.polygon([(x, y - 6), (x + 6, y), (x, y + 6), (x - 6, y)], fill=(212, 196, 160))
    cx, cy = w / 2, h / 2
    for r_, col in ((0.55, (150, 64, 44)), (0.42, (212, 196, 160)), (0.30, (42, 52, 82)), (0.16, (190, 140, 70))):
        rr = r_ * ppm
        d.polygon([(cx, cy - rr * 0.75), (cx + rr, cy), (cx, cy + rr * 0.75), (cx - rr, cy)], fill=col)
    a = np.asarray(img, np.float32)
    a *= (0.92 + 0.10 * np.random.default_rng(2).random((h, w, 1)))
    _save("rug", a)


MAKERS = dict(brick=make_brick, lawn=make_lawn, soil=make_soil, hedge=make_hedge, wood=make_wood, wallpaper=make_wallpaper, rug=make_rug)
PPM = dict(brick=320, lawn=160, soil=220, hedge=260, wood=200, wallpaper=300, rug=150)


def image(name):
    if name not in _cache:
        p = os.path.join(TEX, name + ".png")
        if not os.path.exists(p):
            MAKERS[name]()
        a = np.asarray(Image.open(p).convert("RGBA"))
        _cache[name] = skia.Image.fromarray(np.ascontiguousarray(a), colorType=skia.kRGBA_8888_ColorType).withDefaultMipmaps()   # mip levels: no brick moire in the wides
    return _cache[name]


def plane(fr, cam, name, pts, to_uv, alpha=1.0, tint=None):
    """Draw texture `name` on a planar world polygon `pts`. to_uv(world point) -> (u, v) metres in the plane."""
    V = clip_near([cam.view(p) for p in pts], 0.06)
    if len(V) < 3:
        return None
    path = skia.Path()
    scr = []
    for i, (x, y, z) in enumerate(V):
        s = cam.f / z
        q = (W / 2 + x * s, H * cam.horizon - y * s)
        scr.append(q)
        (path.moveTo if i == 0 else path.lineTo)(*q)
    path.close()
    # back to world for the uv path; the fit uses 4 points of the plane around the visible centroid, all well in
    # front of the lens (any 4 such points give the exact homography; clipped corners can be near-collinear)
    wpts = [tuple(cam.pos[j] + x * cam.right[j] + y * (0.0, 1.0, 0.0)[j] + z * cam.fwd[j] for j in range(3)) for x, y, z in V]
    ppm = PPM[name]
    cw = [sum(p[j] for p in wpts) / len(wpts) for j in range(3)]
    zc = sum(v[2] for v in V) / len(V)
    e1 = [pts[1][j] - pts[0][j] for j in range(3)]
    e2 = [pts[-1][j] - pts[0][j] for j in range(3)]
    n1, n2 = math.sqrt(sum(c * c for c in e1)) or 1.0, math.sqrt(sum(c * c for c in e2)) or 1.0
    sc = 0.3 * zc / 1.42
    fit = [tuple(cw[j] + sc * (a * e1[j] / n1 + b * e2[j] / n2) for j in range(3)) for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    src, dst = [], []
    for p in fit:
        x, y, z = cam.view(p)
        s_ = cam.f / z
        dst.append(skia.Point(W / 2 + x * s_, H * cam.horizon - y * s_))
        src.append(skia.Point(*(c * ppm for c in to_uv(p))))
    m = skia.Matrix()
    if not m.setPolyToPoly(src, dst):
        return path
    inv = skia.Matrix()
    if not m.invert(inv):
        return path
    c = fr.c
    c.save()
    c.clipPath(path, skia.ClipOp.kIntersect, True)
    c.concat(m)
    sh = image(name).makeShader(skia.TileMode.kRepeat, skia.TileMode.kRepeat, skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kLinear))
    p = skia.Paint(Shader=sh, AntiAlias=True)
    p.setAlphaf(alpha)
    uvpath = skia.Path()
    for i, wp in enumerate(wpts):
        u, v = to_uv(wp)
        (uvpath.moveTo if i == 0 else uvpath.lineTo)(u * ppm, v * ppm)
    uvpath.close()
    c.drawPath(uvpath, p)
    c.restore()
    if tint is not None:
        colr, a = tint
        from toon import paint
        c.drawPath(path, paint(colr, a=a))
    return path


def _spread4(scr):
    """Indices of 4 points spanning the polygon (no three collinear in practice)."""
    n = len(scr)
    if n == 4:
        return [0, 1, 2, 3]
    best, bi = -1, None
    import itertools
    for comb in itertools.combinations(range(n), 4):
        q = [scr[i] for i in comb]
        a = 0.0
        for i in range(4):
            x0, y0 = q[i]
            x1, y1 = q[(i + 1) % 4]
            a += x0 * y1 - x1 * y0
        tri = min(abs((q[(i + 1) % 4][0] - q[i][0]) * (q[(i + 2) % 4][1] - q[i][1]) - (q[(i + 2) % 4][0] - q[i][0]) * (q[(i + 1) % 4][1] - q[i][1])) for i in range(4))
        sc = abs(a) + tri
        if tri > 1.0 and sc > best:
            best, bi = sc, list(comb)
    return bi or [0, 1, 2, min(3, n - 1)]
