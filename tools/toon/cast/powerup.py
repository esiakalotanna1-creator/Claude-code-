"""Timmy's power-up (built for the Mara reel, kept for the kit): Timmy's look "kid" with gold 3D spiked hair that
grows in with the power-up, teal eyes, and a flickering gold aura with blue-white sparks. The beanie comes off as a
separate prop (beanie(): drawn in any basis, so it can fly off and tumble).

    import cast.powerup      # registers "kid_powerup" (needs episodes/smilingman/toon/looks.py for "kid")
    pose keys: power (0 = Timmy's own buzz cut .. 1 = full spikes, gold), aura (0..1), t (seconds: flicker)
    python -m cast.powerup   (from tools/toon) -> assets/kit/cast/kid_powerup.png
"""
import math
import os
import sys

import skia

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import importlib.util  # noqa: E402

_sp = importlib.util.spec_from_file_location("timmy_looks", os.path.join(ROOT, "episodes", "smilingman", "toon", "looks.py"))
looks = importlib.util.module_from_spec(_sp)      # by path: inside an episode, "looks" is that episode's own module
_sp.loader.exec_module(looks)                     # registers "kid"
import rig  # noqa: E402
from rig import Basis, Head, add, cross, dot, lathe, mul, norm, smooth, sub  # noqa: E402
from toon import mix, paint, shade  # noqa: E402

GOLD, GOLD_HI, AURA, SPARK, TEAL = "#f6c840", "#fff1a8", "#ffcf3a", "#bfe9ff", "#2fd0c2"
BEANIE = "#d9a43a"                                         # Timmy's mustard knit beanie (looks.kid_cap)

# spikes: (lam, mu, length in R, base width in R, sweep back) - a crown of big upswept spikes plus two fringe locks
SPIKES = [(0.0, 1.05, 1.55, 0.36, 0.25), (0.75, 0.95, 1.35, 0.34, 0.35), (-0.75, 0.95, 1.35, 0.34, 0.35),
          (1.45, 0.75, 1.15, 0.32, 0.5), (-1.45, 0.75, 1.15, 0.32, 0.5), (2.2, 0.75, 1.25, 0.34, 0.65),
          (-2.2, 0.75, 1.25, 0.34, 0.65), (math.pi, 0.8, 1.3, 0.36, 0.75), (0.4, 1.35, 1.6, 0.3, 0.45),
          (-0.4, 1.35, 1.6, 0.3, 0.45), (2.6, 1.2, 1.2, 0.3, 0.7), (-2.6, 1.2, 1.2, 0.3, 0.7),
          (1.1, 0.35, 0.9, 0.28, 0.6), (-1.1, 0.35, 0.9, 0.28, 0.6)]
FRINGE = [(0.28, 0.62, 0.62, 0.17), (-0.18, 0.66, 0.5, 0.15)]       # (lam, mu, length, width): over the forehead


def _cone(cam, base, d, w, ln, up):
    """Screen hull of a cone (base circle radius w perpendicular to d, tip at base + d*ln) -> (path, depth)."""
    a = norm(cross(d, up if abs(dot(d, up)) < 0.95 else (1.0, 0.0, 0.0)))
    b = cross(d, a)
    pts = [cam.proj(add(base, mul(a, w * math.cos(t)), mul(b, w * math.sin(t))))
           for t in (2 * math.pi * i / 12 for i in range(12))]
    tip = cam.proj(add(base, mul(d, ln)))
    if min(q[2] for q in pts + [tip]) < 0.1:
        return None, 0
    return smooth(rig._hull([q[:2] for q in pts] + [tip[:2]]), k=0.25), cam.view(add(base, mul(d, ln * 0.4)))[2]


def power_hair(parts, fr, cam, J, p, ld, lw, out):
    pw = p.get("power", 1.0)
    # the buzz cut under the spikes turns gold with the power (the rig's head reads the colour when it draws, later)
    rig.LOOK[J["look"]]["hair"] = mix(rig.LOOK["kid"]["hair"], GOLD, min(1.0, pw * 1.4))
    rig.LOOK[J["look"]]["iris"] = mix(rig.LOOK["kid"]["iris"], TEAL, min(1.0, pw * 1.4))
    if pw <= 0.01:
        return
    R, Bh = J["R"], J["Bh"]
    Hd = Head(cam, J["head"], Bh, R)
    k = cam.proj(J["head"])[3]
    t = p.get("t", 0.0)
    col = mix(rig.LOOK["kid"]["hair"], GOLD, min(1.0, pw * 1.4))
    to_cam = norm(sub(cam.pos, J["head"]))
    back, front = [], []
    for i, (lam, mu, ln, w, sw) in enumerate(SPIKES):
        base = Hd.surf(lam, mu, 0.96)
        nrm = norm(sub(base, J["head"]))
        d = norm(add(mul(nrm, 0.65), mul(Bh.u, 0.95), mul(Bh.f, -sw), mul(Bh.r, 0.05 * math.sin(t * 9 + i) * pw)))
        path, z = _cone(cam, base, d, w * R, ln * R * (0.25 + 0.75 * pw) * (1 + 0.03 * math.sin(t * 7 + i * 1.7)), Bh.u)
        if path is not None:
            (front if dot(nrm, to_cam) > 0.15 else back).append((z, path))
    for lam, mu, ln, w in FRINGE:
        base = Hd.surf(lam, mu, 1.0)
        d = norm(add(mul(Bh.u, -0.75), mul(Bh.f, 0.45), mul(Bh.r, -0.3 * lam)))
        path, z = _cone(cam, base, d, w * R, ln * R * pw, Bh.u)
        if path is not None:
            front.append((z - 1.0, path))

    def draw(items):
        def f():
            for _, path in sorted(items, key=lambda q: -q[0]):
                fr.part(path, col, (ld[0] * 0.4, 1.0), width=0.5 * R * k, line=lw, lit=0.25, dark=0.35)
                if pw > 0.5:
                    fr.c.save()
                    fr.c.clipPath(path, skia.ClipOp.kIntersect, True)
                    b = path.getBounds()
                    fr.c.drawLine(b.centerX(), b.bottom(), b.centerX() + 0.05 * R * k, b.top(),
                                  paint(GOLD_HI, stroke=0.06 * R * k, a=0.5 * pw, blur=0.03 * R * k))
                    fr.c.restore()
        return f
    parts.append(("under", J["head"][2], draw(back)))
    parts.append(("face", J["head"][2] - 1e-3, draw(front)))
    if pw > 0.3:                                           # the hair glows
        def glow():
            x, y = cam.proj(add(J["head"], mul(Bh.u, 1.1 * R)))[:2]
            fr.glow(x, y, 2.4 * R * k, AURA, a=0.22 * pw, sy=1.2)
        parts.append(("under", J["head"][2] + 1e-3, glow))  # behind the head: the face stays readable


def _resample(poly, n):
    """n points evenly spaced along a closed polygon's perimeter."""
    segs = [(poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly))]
    lens = [math.dist(a, b) for a, b in segs]
    tot = sum(lens) or 1.0
    out, acc, j = [], 0.0, 0
    for i in range(n):
        d = tot * i / n
        while acc + lens[j] < d and j < len(segs) - 1:
            acc += lens[j]
            j += 1
        u = (d - acc) / (lens[j] or 1.0)
        (a, b) = segs[j]
        out.append((a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u))
    return out


def aura(parts, fr, cam, J, p, ld, lw, out):
    a = p.get("aura", 0.0)
    if a <= 0.01:
        return
    t, h = p.get("t", 0.0), J["h"]
    keys = ["head", "neck", "pelvis"] + [j + s for s in ("_R", "_L") for j in ("sh", "el", "wr", "hand", "hip", "kn", "ank")]
    pts = [cam.proj(J[q]) for q in keys if q in J]
    pts.append(cam.proj(add(J["head"], mul(J["Bh"].u, 2.6 * J["R"] * p.get("power", 1.0)))))      # the spikes
    k = cam.proj(J["pelvis"])[3]
    cx = sum(q[0] for q in pts) / len(pts)
    cy = sum(q[1] for q in pts) / len(pts)
    hull = rig._hull([q[:2] for q in pts])

    def grown(pad, lift):
        out_ = []
        for x, y in hull:
            dx, dy = x - cx, y - cy
            n = math.hypot(dx, dy) or 1.0
            out_.append((x + dx / n * pad * k, y + dy / n * pad * k - lift * k * max(0.0, -dy / n)))
        return out_

    def back():
        c = fr.c
        fl = 1 + 0.12 * math.sin(t * 23) + 0.08 * math.sin(t * 37)
        c.drawPath(smooth(grown(0.20 * h * fl, 0.25 * h), k=0.6), paint(AURA, a=0.18 * a, blur=0.09 * h * k, blend="add"))
        c.drawPath(smooth(grown(0.09 * h, 0.12 * h), k=0.6), paint(AURA, a=0.30 * a, blur=0.04 * h * k, blend="add"))
        ring = _resample(grown(0.05 * h, 0.0), 30)          # evenly spaced, not stacked on the hull corners
        for i in range(30):                                 # flame tongues licking upward off the outline
            x, y = ring[i]
            ph = t * 9 + i * 1.9
            ht = (0.12 + 0.10 * (0.5 + 0.5 * math.sin(ph))) * h * k * (1.2 if y < cy else 0.7)
            wd = 0.05 * h * k
            sway = 0.02 * h * k * math.sin(ph * 1.7)
            tongue = skia.Path()
            tongue.moveTo(x - wd, y)
            tongue.quadTo(x - wd * 0.6 + sway, y - ht * 0.6, x + sway * 2, y - ht)
            tongue.quadTo(x + wd * 0.6 + sway, y - ht * 0.6, x + wd, y)
            tongue.close()
            c.drawPath(tongue, paint(AURA, a=0.22 * a, blur=0.018 * h * k, blend="add"))
    parts.append(("under", 99.0, back))

    def front():
        c = fr.c
        c.drawPath(smooth(grown(0.03 * h, 0.0), k=0.6), paint(AURA, a=0.10 * a, blur=0.03 * h * k, blend="add"))
        seed = int(t * 12)                                  # sparks: new zigzags a few times a second
        for j in range(3):
            r = math.sin(seed * 12.9898 + j * 78.233) * 43758.5453
            r -= math.floor(r)
            if r < 0.45:
                continue
            x, y = hull[int(r * 997) % len(hull)]
            ang = r * 6.28
            q = [(x, y)]
            for m in range(5):
                ang += (0.9 if m % 2 else -0.9)
                x += math.cos(ang) * 0.035 * h * k
                y += math.sin(ang) * 0.035 * h * k
                q.append((x, y))
            pth = skia.Path()
            pth.moveTo(*q[0])
            for v in q[1:]:
                pth.lineTo(*v)
            c.drawPath(pth, paint(SPARK, stroke=0.006 * h * k, a=0.9 * a, blend="add"))
            c.drawPath(pth, paint(SPARK, stroke=0.016 * h * k, a=0.3 * a, blur=0.008 * h * k, blend="add"))
    parts.append(("top", 0.0, front))


def beanie(fr, cam, o, B, ld=(0.3, 1.0), line=None, R=None):
    """The knit beanie on its own (o = centre of the opening, B.u = out of the crown), for it flying off the head."""
    R = R or 0.104 * rig.LOOK["kid"]["h"] * 1.06
    rings = [(0.0, 0.98, 0.98, 0, 0), (0.12, 1.0, 1.0, 0, 0), (0.45, 0.94, 0.94, 0, 0), (0.75, 0.74, 0.74, 0, 0),
             (0.95, 0.42, 0.42, 0, 0), (1.03, 0.05, 0.05, 0, 0)]
    path, _ = lathe(cam, o, B, [(u * R, wa * R, db * R, 0, 0) for u, wa, db, _, _ in rings])
    k = cam.proj(o)[3]
    lw = line or max(1.2, 0.0055 * k)
    fr.part(path, BEANIE, ld, width=2 * R * k, line=lw, lit=0.18, dark=0.4)
    cuff, _ = lathe(cam, o, B, [(u * R, 1.02 * R, 1.02 * R, 0, 0) for u in (0.0, 0.3)])
    fr.part(cuff, shade(BEANIE, -0.12), ld, width=0.5 * R * k, line=lw, lit=0.1, dark=0.3)
    # the opening, when it shows: the dark inside of the hat
    if dot(mul(B.u, -1), norm(sub(cam.pos, o))) > 0.1:
        rim = [cam.proj(B.w(o, R * math.cos(a), 0, R * math.sin(a)))[:2] for a in (2 * math.pi * i / 24 for i in range(24))]
        fr.c.drawPath(smooth(rim, k=0.5), paint("#3a2a12"))


rig.LOOK["kid_powerup"] = dict(rig.LOOK["kid"], hair=GOLD, iris=TEAL, hair_mesh=True,
                           extras=(aura, looks.kid_legs, looks.kid_pack, power_hair))


if __name__ == "__main__":
    from PIL import Image
    from toon import Camera, Frame
    kh = rig.LOOK["kid"]["h"]
    tiles = []

    def tile(cam, pose, extra=None):
        fr = Frame(0.35, bg="#161b2c")
        rig.draw(fr, cam, "kid_powerup", dict(dict(x=0, z=3.2, nopack=True), **pose), light=(0.6, 2.4, 2.0))
        if extra:
            extra(fr, cam)
        tiles.append(Image.fromarray(fr.array()))
    wide = Camera((0, kh * 0.6, 0.0), 0, f=2500, horizon=0.55)
    stance = dict(aR=(10, 22, 40), aL=(10, 22, 40), fist=1.0, brow_in=0.9, brow=0.3, stance=0.05)
    for i, yaw in enumerate((0, 35, 90, 150, 180)):        # full power turnaround
        tile(wide, dict(stance, yaw=yaw, power=1.0, aura=1.0, t=i * 0.37))
    for i, pw in enumerate((0.0, 0.35, 0.7)):              # the power-up: beanie lifting off, spikes growing in
        pose = dict(stance, x=0, z=3.2, yaw=10, power=pw, aura=pw, t=1.0 + i * 0.3)
        Jh = rig.solve("kid_powerup", pose)

        def hat(fr, cam, pw=pw, Jh=Jh):                     # sits on the crown, then the hair pushes it up and off
            Bh = Jh["Bh"].roll(-35 * pw).pitch(-25 * pw)
            o = add(Jh["head"], mul(Jh["Bh"].u, Jh["R"] * (0.32 + 4.0 * pw)), mul(Jh["Bh"].r, -0.3 * Jh["R"] * pw))
            beanie(fr, cam, o, Bh)
        tile(wide, pose, hat)
    close = Camera((0, kh * 0.95, 1.9), 0, f=3600, horizon=0.5)
    tile(close, dict(stance, yaw=12, power=1.0, aura=1.0, t=2.2))
    w, h = tiles[0].size
    img = Image.new("RGB", (w * len(tiles) + 8 * (len(tiles) - 1), h), (255, 0, 255))
    for i, tl in enumerate(tiles):
        img.paste(tl, (i * (w + 8), 0))
    outp = os.path.join(ROOT, "assets", "kit", "cast", "kid_powerup.png")
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    img.save(outp)
    print(outp, img.size)
