"""Flat-screen TV (generic 25", no logos): a thin black panel on two splayed feet, a glossy dark screen with three
stuck pixels (the "dead pixels" joke), a red standby LED, the power cable out of the back.
Size: 0.56 m wide, 0.34 m panel on 0.03 m feet. Origin = centre of the bottom; B.u = up, B.f = out of the screen.

    draw(fr, cam, o, B, t=0.0, light=(0, 2.4, 1.5), cable=0.0)
    py -m props.tv           (from tools/toon) -> assets/kit/props/tv.png
"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from rig import Basis, add, cross, dot, mul, norm, sub  # noqa: E402
from toon import paint, shade  # noqa: E402

W, PH, D, FOOT = 0.56, 0.34, 0.045, 0.03
BODY, SCREEN, CABLE = "#16171d", "#0b0d16", "#141418"
DEAD = [(0.31, 0.38, "#e8f4ff"), (0.62, 0.55, "#ff5a5a"), (0.47, 0.7, "#7affb0")]   # (u across, v down, colour)


def _box(cam, o, B, x, y, z, colr, key, faces):
    """Axis box in B: x, y, z = (lo, hi) along r, u, f. Appends visible shaded faces (depth, pts, colr)."""
    def P(a, b, c):
        return B.w(o, a, b, c)
    (x0, x1), (y0, y1), (z0, z1) = x, y, z
    quads = [(B.f, [P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1)]),
             (mul(B.f, -1), [P(x1, y0, z0), P(x0, y0, z0), P(x0, y1, z0), P(x1, y1, z0)]),
             (B.r, [P(x1, y0, z1), P(x1, y0, z0), P(x1, y1, z0), P(x1, y1, z1)]),
             (mul(B.r, -1), [P(x0, y0, z0), P(x0, y0, z1), P(x0, y1, z1), P(x0, y1, z0)]),
             (B.u, [P(x0, y1, z1), P(x1, y1, z1), P(x1, y1, z0), P(x0, y1, z0)]),
             (mul(B.u, -1), [P(x0, y0, z0), P(x1, y0, z0), P(x1, y0, z1), P(x0, y0, z1)])]
    for nrm, pts in quads:
        m = add(*[mul(q, 0.25) for q in pts])
        if dot(nrm, sub(cam.pos, m)) <= 0:
            continue
        lit = 0.5 + 0.5 * dot(nrm, key)
        faces.append((cam.view(m)[2], pts, shade(colr, -0.4 + 0.5 * lit)))


def draw(fr, cam, o, B, t=0.0, light=(0.0, 2.4, 1.5), cable=0.0, line=None):
    mid = add(o, mul(B.u, FOOT + PH / 2))
    pc = cam.proj(mid)
    if pc[2] < 0.15:
        return
    k = pc[3]
    lw = line or max(1.0, 0.004 * k)
    key = norm(sub(light, mid))
    faces = []
    for sx in (-0.2, 0.2):                                      # the two feet
        _box(cam, o, B, (W * sx - 0.03, W * sx + 0.03), (0.0, FOOT + 0.01), (-0.06, 0.05), "#202128", key, faces)
    _box(cam, o, B, (-W / 2, W / 2), (FOOT, FOOT + PH), (-D / 2, D / 2), BODY, key, faces)
    _box(cam, o, B, (-0.1, 0.1), (FOOT + 0.06, FOOT + 0.24), (-D / 2 - 0.03, -D / 2), BODY, key, faces)   # back hump
    if cable > 0:                                               # power cable trailing from the back
        a = B.w(o, 0.08, FOOT + 0.1, -D / 2 - 0.03)
        b = B.w(o, 0.12 + 0.05 * cable, 0.02, -D / 2 - 0.2 * cable)
        c = B.w(o, 0.2 + 0.1 * cable, 0.0, -D / 2 - 0.45 * cable)
        faces.append((cam.view(a)[2] + 0.01, [a, b, c], None))
    for z, pts, colr in sorted(faces, key=lambda q: -q[0]):
        if colr is None:
            q = [cam.proj(v) for v in pts]
            if min(v[2] for v in q) > 0.15:
                fr.c.drawPath(_line(q), paint(CABLE, stroke=max(1.0, 0.008 * k)))
            continue
        fr.poly(cam, pts, colr=colr, outline="#3b3e4c", line=lw)   # a lit bezel edge: it reads in a dark room
    front = dot(B.f, sub(cam.pos, mid)) > 0
    if not front:
        return
    e = 0.012
    z1 = D / 2 + 0.001
    scr = [B.w(o, -W / 2 + e, FOOT + PH - e, z1), B.w(o, W / 2 - e, FOOT + PH - e, z1),
           B.w(o, W / 2 - e, FOOT + e + 0.012, z1), B.w(o, -W / 2 + e, FOOT + e + 0.012, z1)]
    fr.poly(cam, scr, colr=SCREEN)
    sh = [B.w(o, -W / 2 + 0.06, FOOT + PH - e, z1 + 1e-4), B.w(o, -W / 2 + 0.16, FOOT + PH - e, z1 + 1e-4),
          B.w(o, -W / 2 + 0.06, FOOT + e + 0.02, z1 + 1e-4), B.w(o, -W / 2 + 0.0 + e, FOOT + e + 0.02, z1 + 1e-4)]
    fr.poly(cam, sh, colr="#151a2a")                           # a soft reflection streak across the glass
    for u, v, col in DEAD:                                     # the stuck pixels
        p = cam.proj(B.w(o, -W / 2 + e + u * (W - 2 * e), FOOT + PH - e - v * (PH - 2 * e - 0.012), z1 + 2e-4))
        if p[2] > 0.15:
            r = max(1.2, 0.0045 * p[3])
            fr.c.drawRect(_rect(p[0] - r, p[1] - r, p[0] + r, p[1] + r), paint(col))
    led = cam.proj(B.w(o, W / 2 - 0.04, FOOT + 0.006, z1 + 2e-4))
    if led[2] > 0.15:
        fr.c.drawCircle(led[0], led[1], max(1.0, 0.004 * led[3]), paint("#ff2a2a"))


def _line(q):
    import skia
    pth = skia.Path()
    pth.moveTo(q[0][0], q[0][1])
    pth.quadTo(q[1][0], q[1][1], q[2][0], q[2][1])
    return pth


def _rect(a, b, c, d):
    import skia
    return skia.Rect(a, b, c, d)


if __name__ == "__main__":
    from PIL import Image

    from toon import Camera, Frame
    ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
    tiles = []
    for yaw in (0, 35, 90, 150):
        fr = Frame(0.3)
        fr.c.clear(0xff20222c)
        cam = Camera((0.0, 0.35, -1.1), 0.0, 1800)
        draw(fr, cam, (0.0, 0.0, 0.0), Basis.yaw(180 + yaw), cable=1.0)
        tiles.append(Image.fromarray(fr.array()))
    im = Image.new("RGB", (sum(t.width for t in tiles), tiles[0].height))
    x = 0
    for t in tiles:
        im.paste(t, (x, 0))
        x += t.width
    out = os.path.join(ROOT, "assets", "kit", "props", "tv.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    im.save(out)
    print(out)
