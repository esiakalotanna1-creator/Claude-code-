"""A tall games console (generic, no logos): a tall black core between two white side plates that flare out toward
the top, a blue light strip along the core, and power + HDMI cables trailing from the back with dangling plugs.
Real size: 0.39 m tall, 0.10 m wide, 0.26 m deep. Origin = centre of the bottom; B.u = up, B.f = front.

    draw(fr, cam, o, B, t=0.0, light=(0, 2.4, 1.5), cables=1.0, swing=0.0)
    carry(cpose, s=1.0) -> (pose additions, held fn) for cast.creature: hunched, both hands clutching the plates
    python -m props.console  (from tools/toon) -> assets/kit/props/console.png
"""
import math
import os
import sys

import skia

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import rig  # noqa: E402
from rig import Basis, add, cross, dot, mul, norm, sub  # noqa: E402
from toon import paint, shade  # noqa: E402

WHITE, CORE, GLOW, CABLE = "#e9ebf0", "#17181e", "#4f8dff", "#141418"
H, W, D = 0.39, 0.10, 0.26
# side plate profile in (b = front/back, u = up): narrow waist low down, flaring wider at the top, rounded crown
PLATE = [(-0.115, 0.0), (0.115, 0.0), (0.125, 0.12), (0.142, 0.30), (0.14, 0.375), (0.11, 0.395),
         (-0.12, 0.395), (-0.148, 0.37), (-0.146, 0.28), (-0.124, 0.10)]


def _slab(cam, o, B, prof, x0, x1, colr, key, faces):
    """Extrude a (b, u) profile along B.r from x0 to x1; append visible shaded faces (depth, pts, colr)."""
    caps = [[B.w(o, x, u, b) for b, u in prof] for x in (x0, x1)]
    n = len(prof)
    cand = [(mul(B.r, -1), caps[0][::-1]), (B.r, caps[1])]
    for i in range(n):
        a0, a1 = caps[0][i], caps[0][(i + 1) % n]
        b0, b1 = caps[1][i], caps[1][(i + 1) % n]
        e = sub(a1, a0)
        nrm = norm(cross(e, B.r))
        cand.append((nrm, [a0, a1, b1, b0]))
    cen = add(*[mul(q, 1.0 / n) for q in caps[0]])
    cen = add(mul(cen, 0.5), mul(add(*[mul(q, 1.0 / n) for q in caps[1]]), 0.5))
    for nrm, pts in cand:
        m = add(*[mul(q, 1.0 / len(pts)) for q in pts])
        if dot(sub(m, cen), nrm) < 0:                       # keep normals pointing outward
            nrm = mul(nrm, -1)
        if dot(nrm, sub(cam.pos, m)) <= 0:
            continue
        lit = 0.5 + 0.5 * dot(nrm, key)
        faces.append((cam.view(m)[2], pts, shade(colr, -0.45 + 0.55 * lit)))


def draw(fr, cam, o, B, t=0.0, light=(0.0, 2.4, 1.5), cables=1.0, swing=0.0, line=None, floor=0.0, _only=None):
    c = fr.c
    k = cam.proj(add(o, mul(B.u, H / 2)))[3]
    if k <= 0:
        return
    if _only is None and cables > 0 and dot(B.f, sub(cam.pos, o)) > 0:     # seen from the front: cables go behind
        kw = dict(t=t, light=light, cables=cables, swing=swing, line=line, floor=floor)
        draw(fr, cam, o, B, _only="cables", **kw)
        draw(fr, cam, o, B, _only="body", **kw)
        return
    lw = line or max(1.0, 0.0055 * k)
    key = norm(sub(light, add(o, mul(B.u, H / 2))))
    faces = []
    _slab(cam, o, B, [(b * 0.92, max(0.01, u * 0.98)) for b, u in PLATE], -0.03, 0.03, CORE, key, faces)   # core
    for sg in (1, -1):
        x0, x1 = (0.03, 0.05) if sg > 0 else (-0.05, -0.03)
        _slab(cam, o, B, PLATE, x0, x1, WHITE, key, faces)
    for _, pts, colr in sorted(faces, key=lambda f: -f[0]) if _only != "cables" else ():
        fr.poly(cam, pts, colr, outline=shade(colr, -0.7) if colr != CORE else "#050506", line=lw)
    # blue light strip down the front edge of the core and a power button glint
    for sg in (1, -1) if _only != "cables" else ():
        a = cam.proj(B.w(o, sg * 0.031, 0.04, 0.112))
        b = cam.proj(B.w(o, sg * 0.031, 0.36, 0.13))
        if a[2] > 0.05 and b[2] > 0.05 and dot(B.f, sub(cam.pos, o)) > 0:
            c.drawLine(a[0], a[1], b[0], b[1], paint(GLOW, stroke=max(1.0, 0.006 * k), blur=0.004 * k))
            fr.glow((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, 0.08 * k, GLOW, a=0.25, sy=2.5)
    # cables out of the back: drooping, swinging, plugs dangling at the ends
    if cables > 0 and _only != "body":
        for i, (xo, ln, colr) in enumerate(((-0.012, 0.42, CABLE), (0.014, 0.34, "#22232a"))):
            p0 = B.w(o, xo, 0.05 + 0.03 * i, -0.13)
            pts = []
            for j in range(13):
                u = j / 12
                sw = swing * math.sin(t * 5.0 + i + u * 2.5) * 0.06 * u
                q = add(p0, mul(B.f, -0.08 * u - 0.02 * math.sin(u * 3)), mul(B.r, sw + 0.03 * i * u),
                        (0.0, -ln * cables * u * u * 0.9 - 0.04 * u, 0.0))
                if q[1] < floor + 0.006:                     # the slack drags along the floor
                    q = (q[0] - B.f[0] * (floor + 0.006 - q[1]), floor + 0.006, q[2] - B.f[2] * (floor + 0.006 - q[1]))
                pts.append(q)
            sp = [cam.proj(q) for q in pts]
            if min(q[2] for q in sp) < 0.05:
                continue
            path = rig.smooth([q[:2] for q in sp], closed=False)
            c.drawPath(path, paint("#000000", stroke=0.011 * k + lw))
            c.drawPath(path, paint(colr, stroke=0.008 * k))
            e, d = sp[-1], sp[-2]                           # the plug
            ang = math.degrees(math.atan2(e[1] - d[1], e[0] - d[0]))
            c.save()
            c.translate(e[0], e[1])
            c.rotate(ang)
            c.drawRect(skia.Rect(0, -0.009 * k, 0.03 * k, 0.009 * k), paint("#2b2c33"))
            c.drawRect(skia.Rect(0, -0.009 * k, 0.03 * k, 0.009 * k), paint("#000000", stroke=lw))
            c.drawRect(skia.Rect(0.03 * k, -0.005 * k, 0.042 * k, 0.005 * k), paint("#a9adb6" if i else "#c8cbd2"))
            c.restore()


def carry(cpose, s=1.0, t=0.0, wobble=1.0):
    """Hunched sneak hugging the console upright to its belly, a white side plate facing out (the shape people know),
    a hand clamped on each flared edge: returns the pose to merge into a creature pose and the held drawable for
    creature.draw(held=). It rocks as it shuffles; the cables hang slack off one side to the floor."""
    Bb = Basis.yaw(cpose.get("yaw", 0.0))
    root = (cpose.get("x", 0.0), cpose.get("floor", 0.0), cpose.get("z", 0.0))
    tip = 6 * wobble * math.sin(t * 6.0)                    # rocks side to side
    up_ax = rig.rot(Bb.u, Bb.f, tip)
    side_ax = rig.rot(Bb.r, Bb.f, tip)
    Bt = Bb.turn(28)                                         # turned a little so the black core and light strip show
    B = Basis(Bt.f, up_ax, mul(rig.rot(Bt.r, Bb.f, tip), -1))   # plate face out, its front edge to its left
    o = Bb.w(root, 0, 0.05 * s, 0.13 * s)                   # standing between its knees, hugged to the belly
    ctr = add(o, mul(up_ax, H * 0.55))
    pose = dict(crouch=0.12, lean=6, head_pitch=-4)        # taller than the lying-flat carry: its face clears the top
    for k, g in (("R", 1), ("L", -1)):
        end = add(ctr, mul(side_ax, g * 0.13))
        pose["ik_" + k] = add(end, mul(Bb.f, -0.01 * s))
        pose["pole_" + k] = norm(Bb.d(g * 1.0, 0.2, -0.6))   # elbows out and back, straining
        pose["palm_" + k] = mul(side_ax, -g)
        pose["curl_" + k] = 0.8
    draw_fn = lambda fr, cam, light=(0.0, 2.4, 1.5): draw(fr, cam, o, B, t=t, light=light, swing=0.6 * wobble, floor=root[1])   # noqa: E731
    return pose, (ctr, draw_fn)


if __name__ == "__main__":
    from PIL import Image
    from toon import Camera, Frame
    tiles = []
    for yaw, pit in ((20, 0), (-35, 0), (150, 0), (60, -70)):
        fr = Frame(0.35, bg="#161b2c")
        cam = Camera((0, 0.35, 0.0), 0, f=3600, horizon=0.55)
        B = Basis.yaw(yaw).pitch(pit)
        draw(fr, cam, (0, 0.05 if pit == 0 else 0.25, 1.4), B, cables=1.0)
        tiles.append(Image.fromarray(fr.array()))
    w, h = tiles[0].size
    img = Image.new("RGB", (w * 4 + 24, h), (255, 0, 255))
    for i, tl in enumerate(tiles):
        img.paste(tl, (i * (w + 8), 0))
    out = os.path.abspath(os.path.join(HERE, "..", "..", "assets", "kit", "props", "console.png"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out)
    print(out)
