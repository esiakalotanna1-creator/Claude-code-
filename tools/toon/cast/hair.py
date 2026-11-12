"""Long gravity hair as separate strands (from the Lynn reel's lank_hair, made generic for the kit).

strands(...) returns a LOOK extra: a curtain down the back plus strands framing the face, rooted outside the eyes and
mouth so they never cover the features. Strands fall along world -y (a lying head's hair pools on the floor).
Pose keys: t (seconds, drives the sway), breeze (0..1 extra sideways drift, e.g. an aircon draught; breeze_dir world
vector), no_frame_hair (drop the face strands).
"""
import math

import rig
from rig import Head, smooth
from toon import paint, shade


def strands(n_back=26, length=0.50, frame=((0.95, 0.36), (1.02, 0.46), (1.10, 0.40), (1.18, 0.52)), width=0.016,
            tangle=0.0, fly=0):
    """tangle 0..1 kinks each strand and splits its tip; fly = number of loose flyaway hairs off the crown."""

    def extra(parts, fr, cam, J, p, ld, lw, out):
        R, Bh = J["R"], J["Bh"]
        Hd = Head(cam, J["head"], Bh, R)
        hair = rig.LOOK[J["look"]]["hair"]
        t = p.get("t", 0.0)
        bz = p.get("breeze", 0.0)
        bd = p.get("breeze_dir", (1.0, 0.0, 0.0))
        to_cam = rig.norm(rig.sub(cam.pos, J["head"]))
        kh = cam.proj(J["head"])[3]

        def strand(lam, mu, ln, w0, i):
            # hugs the head from the crown down to where the surface stops facing down-and-out, then falls straight
            pts = [Hd.surf(lam, m, 1.04) for m in (0.85, mu + 0.2, mu)]
            while pts[-1][1] > J["head"][1] - 0.6 * R and len(pts) < 8:
                mu -= 0.25
                nx = Hd.surf(lam, mu, 1.04)
                if nx[1] >= pts[-1][1]:
                    break
                pts.append(nx)
            last = pts[-1]
            outw = rig.norm((last[0] - J["head"][0], 0.0, last[2] - J["head"][2]))
            n = 11
            for j in range(1, n + 1):
                u = j / n
                sway = 0.012 * math.sin(t * 1.1 + i * 1.7) * u + 0.01 * math.sin(i * 2.3 + u * 5)
                drift = bz * u * u * (0.05 + 0.025 * math.sin(t * 2.3 + i * 0.9))          # the draught lifts the tips most
                kink = tangle * 0.018 * math.sin(i * 3.1 + u * 17.0) * u                     # tangled: wavy, not combed
                q = rig.add(last, rig.mul(outw, 0.012 * u + abs(kink)), (sway + kink, -ln * u, 0.5 * sway - kink),
                            rig.mul(bd, drift))
                if q[1] < 0.008:
                    q = (q[0] + outw[0] * (0.008 - q[1]) * 0.6, 0.008, q[2] + outw[2] * (0.008 - q[1]) * 0.6)
                pts.append(q)
            sp = [cam.proj(q) for q in pts]
            if min(s[2] for s in sp) < 0.2:
                return []
            left, right = [], []
            for j, s in enumerate(sp):
                a, b = sp[max(0, j - 1)], sp[min(len(sp) - 1, j + 1)]
                dx, dy = b[0] - a[0], b[1] - a[1]
                L = math.hypot(dx, dy) or 1.0
                v = j / (len(sp) - 1)
                w = w0 * s[3] * min(1.0, 0.3 + 3 * v) * (1 - 0.75 * v)
                left.append((s[0] - dy / L * w, s[1] + dx / L * w))
                right.append((s[0] + dy / L * w, s[1] - dx / L * w))
            out_paths = [smooth(left + right[::-1], k=0.4)]
            if tangle > 0 and i % 3 == 0:                       # a split, frayed tip
                s = sp[-3]
                e = cam.proj(rig.add(pts[-1], (0.02 * math.sin(i), -0.03, 0.02 * math.cos(i))))
                out_paths.append(("line", s[:2], e[:2], max(0.6, w0 * s[3] * 0.35)))
            return out_paths

        def draw(items):
            for it in items:
                for pth in it:
                    if isinstance(pth, tuple):
                        _, a, b, sw = pth
                        fr.c.drawLine(a[0], a[1], b[0], b[1], paint(hair, stroke=sw))
                        continue
                    fr.c.drawPath(pth, paint(hair))
                    fr.c.drawPath(pth, paint(shade(hair, 0.5), stroke=max(0.8, 0.004 * R * kh), a=0.35))

        back, front = [], []
        for i in range(n_back):
            lam = 1.15 + (2 * math.pi - 2.3) * i / max(1, n_back - 1)
            mu = 0.30 + 0.12 * math.sin(i * 1.3)
            back.append(strand(lam, mu, length + 0.14 * math.sin(i * 2.1), width, i))
        for sg in (-1, 1):
            for j, (lam, ln) in enumerate(frame):
                if (Bh.u[1] < 0.5 and Hd.surf(sg * lam, 0.40)[1] > J["head"][1]) or p.get("no_frame_hair"):
                    continue
                q = strand(sg * lam, 0.40, ln * length / 0.5, width * 0.82, 40 + j + (4 if sg > 0 else 0))
                (front if Hd.facing(sg * lam, 0.40) > 0.05 else back).append(q)
        flyaways = []
        for i in range(fly):                                    # loose hairs standing off the crown
            lam = -1.2 + 2.4 * i / max(1, fly - 1)
            a = Hd.surf(lam, 0.95, 1.05)
            b = rig.add(Hd.surf(lam, 1.15, 1.25), (0.03 * math.sin(t * 1.7 + i) * (0.4 + bz), 0.0, 0.0))
            pa, pb = cam.proj(a), cam.proj(b)
            if Hd.facing(lam, 0.95) > -0.3 and min(pa[2], pb[2]) > 0.2:
                flyaways.append([("line", pa[:2], pb[:2], max(0.6, 0.004 * R * kh))])
        facing = rig.dot(Bh.f, to_cam) > 0
        parts.append(("under" if facing else "top", J["head"][2] + 0.01, lambda: draw(back)))
        parts.append(("face", J["head"][2] - 2e-4, lambda: draw(front + flyaways)))

    return extra
