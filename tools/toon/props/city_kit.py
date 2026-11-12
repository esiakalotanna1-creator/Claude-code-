"""City kit for the toon street (built 2026-11-08 for the Mara reel's city act): simple world-space props drawn with
boxes and soft blobs, plus a flat toon cat. Everything takes (fr, cam, ...) in street metres (y up).

    metal_bin(fr, cam, pos, lid=1.0, tilt=(0, 0), dent=0.0)      round dustbin, lid 0 = off .. 1 = on
    wheelie_bin(fr, cam, pos, yaw, lid=0.0, roll=0.0)             wheeled bin, lid angle 0..1 open, roll = tilt back
    car(fr, cam, pos, yaw, colr)                                  parked hatchback (box + cabin + wheels)
    bicycle(fr, cam, pos, yaw)                                    two wheels and a frame
    trolley(fr, cam, pos, yaw) / cart(fr, cam, pos, yaw)          shopping trolley / a food cart with an awning
    mannequin(fr, cam, pos, yaw, headless=False) / rail(fr, cam, pos, yaw, n)  shop dummies and a clothes rail
    ac_unit / chimney / dish / crate / cardboard / washing_line   rooftop and alley clutter
    cat(fr, cam, pos, yaw, pose, pattern)                         pose: sit | arch | jump | slip; pattern: ginger | calico | black | tabby
    glass_shards(fr, cam, pts) / rubbish(fr, cam, pts)            loose bits (positions animated by the scene)
"""
import math
import os
import sys

import skia

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from rig import Basis, add, mul  # noqa: E402
from toon import paint, shade  # noqa: E402


def _box_local(fr, cam, o, B, x, y, z, colr, line=1.0):
    """Axis box in basis B at origin o: x, y, z = (lo, hi) along r, u, f."""
    def P(a, b, c):
        return B.w(o, a, b, c)
    (x0, x1), (y0, y1), (z0, z1) = x, y, z
    quads = [(B.f, [P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1)]),
             (mul(B.f, -1), [P(x1, y0, z0), P(x0, y0, z0), P(x0, y1, z0), P(x1, y1, z0)]),
             (B.r, [P(x1, y0, z1), P(x1, y0, z0), P(x1, y1, z0), P(x1, y1, z1)]),
             (mul(B.r, -1), [P(x0, y0, z0), P(x0, y0, z1), P(x0, y1, z1), P(x0, y1, z0)]),
             (B.u, [P(x0, y1, z1), P(x1, y1, z1), P(x1, y1, z0), P(x0, y1, z0)])]
    m = B.w(o, (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    faces = []
    for nrm, pts in quads:
        d = cam.pos[0] - m[0], cam.pos[1] - m[1], cam.pos[2] - m[2]
        if nrm[0] * d[0] + nrm[1] * d[1] + nrm[2] * d[2] <= 0:
            continue
        lit = 0.5 + 0.5 * (0.3 * nrm[0] + 0.8 * nrm[1] - 0.2 * nrm[2])
        faces.append((cam.view(add(*[mul(q, 0.25) for q in pts]))[2], pts, shade(colr, -0.45 + 0.5 * lit)))
    for _, pts, c in sorted(faces, key=lambda q: -q[0]):
        fr.poly(cam, pts, colr=c, outline=shade(colr, -0.7), line=line)


def _cyl(fr, cam, pos, r, h, colr, n=12, top=True, line=1.0, taper=1.0):
    """A vertical cylinder (dustbin, chimney pot): side quads then the lid."""
    x, y, z = pos
    faces = []
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        pts = [(x + r * math.cos(a0), y, z + r * math.sin(a0)), (x + r * math.cos(a1), y, z + r * math.sin(a1)),
               (x + r * taper * math.cos(a1), y + h, z + r * taper * math.sin(a1)), (x + r * taper * math.cos(a0), y + h, z + r * taper * math.sin(a0))]
        nx, nz = math.cos((a0 + a1) / 2), math.sin((a0 + a1) / 2)
        m = (x + r * nx, y + h / 2, z + r * nz)
        if nx * (cam.pos[0] - m[0]) + nz * (cam.pos[2] - m[2]) <= 0:
            continue
        lit = 0.5 + 0.5 * (0.6 * nx - 0.3 * nz)
        faces.append((cam.view(m)[2], pts, shade(colr, -0.4 + 0.45 * lit)))
    for _, pts, c in sorted(faces, key=lambda q: -q[0]):
        fr.poly(cam, pts, colr=c, outline=shade(colr, -0.7), line=line)
    if top and cam.pos[1] > y + h:
        fr.poly(cam, [(x + r * taper * math.cos(2 * math.pi * i / n), y + h, z + r * taper * math.sin(2 * math.pi * i / n)) for i in range(n)],
                colr=shade(colr, 0.1), outline=shade(colr, -0.7), line=line)


# ---- bins ---------------------------------------------------------------------------------------------------------
def metal_bin(fr, cam, pos, lid=1.0, tilt=(0.0, 0.0), dent=0.0, colr="#7d8795"):
    """Galvanised dustbin, 0.5 m across, 0.75 tall. lid 1 = on, 0 = gone. tilt = (deg about x, deg about z)."""
    x, y, z = pos
    r, h = 0.25 * (1 - 0.15 * dent), 0.75
    if tilt != (0.0, 0.0):                                  # knocked over: draw it as a leaning box of quads
        B = Basis((1, 0, 0), (0, 1, 0), (0, 0, 1))
        from rig import rot
        u = rot(rot(B.u, (1, 0, 0), tilt[0]), (0, 0, 1), tilt[1])
        rr = rot(rot(B.r, (1, 0, 0), tilt[0]), (0, 0, 1), tilt[1])
        ff = rot(rot(B.f, (1, 0, 0), tilt[0]), (0, 0, 1), tilt[1])
        Bt = Basis(rr, u, ff)
        _box_local(fr, cam, (x, y, z), Bt, (-r, r), (0.0, h), (-r, r), colr, line=1.1)
        return
    _cyl(fr, cam, (x, y, z), r, h, colr, n=10, top=lid < 0.5, taper=1.08)
    for k in (0.25, 0.5):                                   # ribs
        yy = y + h * k
        pts = [(x + r * 1.04 * math.cos(2 * math.pi * i / 10), yy, z + r * 1.04 * math.sin(2 * math.pi * i / 10)) for i in range(11)]
        q = [cam.proj(p) for p in pts]
        if min(v[2] for v in q) > 0.3:
            path = skia.Path()
            path.moveTo(q[0][0], q[0][1])
            for v in q[1:]:
                path.lineTo(v[0], v[1])
            fr.c.drawPath(path, paint(shade(colr, -0.5), stroke=max(1.0, 0.006 * q[0][3]), a=0.6))
    if lid >= 0.5:
        _cyl(fr, cam, (x, y + h, z), r * 1.12, 0.07, shade(colr, 0.08), n=10, taper=0.8)
        _cyl(fr, cam, (x, y + h + 0.07, z), 0.05, 0.05, shade(colr, -0.1), n=8)     # handle knob


def bin_lid(fr, cam, pos, B, colr="#8a94a2"):
    """A loose dustbin lid (spinning on the ground / flying): a flat disc in basis B at pos."""
    pts = [B.w(pos, 0.28 * math.cos(2 * math.pi * i / 12), 0.0, 0.28 * math.sin(2 * math.pi * i / 12)) for i in range(12)]
    fr.poly(cam, pts, colr=shade(colr, 0.05), outline=shade(colr, -0.7), line=1.1)
    _box_local(fr, cam, pos, B, (-0.05, 0.05), (0.0, 0.06), (-0.05, 0.05), shade(colr, -0.1))


def wheelie_bin(fr, cam, pos, yaw, lid=0.0, roll=0.0, colr="#2f6b3a"):
    """Wheeled bin, axis-aligned (the alley runs along x): body 0.62 (x) by 0.6 (z) by 1.05 tall on two wheels at the
    -x side; lid 0 = shut flat on top .. 1 = open, standing up at the back. Drawn with the engine's own box so it
    never loses faces when the camera is close (bins looked partly invisible otherwise)."""
    x, y, z = pos
    fr.box(cam, (x - 0.31, x + 0.31), (y + 0.12, y + 1.05), (z - 0.3, z + 0.3), colr, line=1.2)
    for g in (-1, 1):                                        # wheels
        q = cam.proj((x - 0.3, y + 0.1, z + g * 0.24))
        if q[2] > 0.3:
            fr.c.drawCircle(q[0], q[1], max(1.5, 0.1 * q[3]), paint("#15161c"))
    if lid < 0.5:                                            # shut: a flat slab on top
        fr.box(cam, (x - 0.33, x + 0.33), (y + 1.05, y + 1.1), (z - 0.32, z + 0.32), shade(colr, 0.1), line=1.2)
    else:                                                    # open: standing up along the back edge
        fr.box(cam, (x - 0.36, x - 0.3), (y + 1.05, y + 1.7), (z - 0.32, z + 0.32), shade(colr, 0.1), line=1.2)


# ---- street things ------------------------------------------------------------------------------------------------
def car(fr, cam, pos, yaw, colr="#8c2f33"):
    """A parked hatchback, 4 m long, nose along +f."""
    B = Basis.yaw(yaw)
    _box_local(fr, cam, pos, B, (-0.85, 0.85), (0.25, 0.75), (-2.0, 2.0), colr, line=1.1)           # body
    _box_local(fr, cam, pos, B, (-0.78, 0.78), (0.75, 1.35), (-1.3, 0.9), shade(colr, -0.05), line=1.1)   # cabin
    for gz in (-1.25, 0.95):                                 # glass bands
        pts = [B.w(pos, -0.74, 0.8, gz), B.w(pos, 0.74, 0.8, gz), B.w(pos, 0.74, 1.3, gz), B.w(pos, -0.74, 1.3, gz)]
        fr.poly(cam, pts, colr="#1a2436", outline="#0b0f18", line=1.0)
    for gx in (-1, 1):
        pts = [B.w(pos, gx * 0.79, 0.8, -1.2), B.w(pos, gx * 0.79, 0.8, 0.8), B.w(pos, gx * 0.79, 1.3, 0.6), B.w(pos, gx * 0.79, 1.3, -1.0)]
        fr.poly(cam, pts, colr="#1a2436", outline="#0b0f18", line=1.0)
    for gx in (-1, 1):
        for gz in (-1.3, 1.3):
            c = B.w(pos, gx * 0.82, 0.3, gz)
            q = cam.proj(c)
            if q[2] > 0.3:
                fr.c.drawCircle(q[0], q[1], max(2.0, 0.3 * q[3]), paint("#101118"))
                fr.c.drawCircle(q[0], q[1], max(1.0, 0.15 * q[3]), paint("#5a5e68"))
    for g in (-1, 1):                                        # tail lights
        q = cam.proj(B.w(pos, g * 0.6, 0.6, -2.01))
        if q[2] > 0.3:
            fr.c.drawRect(skia.Rect(q[0] - 0.12 * q[3], q[1] - 0.05 * q[3], q[0] + 0.12 * q[3], q[1] + 0.05 * q[3]), paint("#c8303a"))


def bonnet_open(fr, cam, pos, yaw, colr="#8c2f33"):
    """The car's bonnet lifted (the mechanic ducks behind it)."""
    B = Basis.yaw(yaw)
    from rig import rot
    hinge = B.w(pos, 0.0, 0.75, 0.9)
    Bh = Basis(B.r, rot(B.u, B.r, 55.0), rot(B.f, B.r, 55.0))
    _box_local(fr, cam, hinge, Bh, (-0.8, 0.8), (0.0, 0.04), (0.0, 1.1), colr, line=1.1)


def bicycle(fr, cam, pos, yaw, lean=0.0):
    """A bike standing on the road: two wheels, a frame triangle, bars and a saddle."""
    B = Basis.yaw(yaw)
    from rig import rot
    if lean:
        B = Basis(rot(B.r, B.f, lean), rot(B.u, B.f, lean), B.f)
    for gz in (-0.55, 0.55):
        c = B.w(pos, 0.0, 0.33, gz)
        q = cam.proj(c)
        if q[2] > 0.3:
            fr.c.drawCircle(q[0], q[1], max(2.0, 0.33 * q[3]), paint("#15161c", stroke=max(1.0, 0.02 * q[3])))
            fr.c.drawCircle(q[0], q[1], max(1.0, 0.04 * q[3]), paint("#8a8e98"))
    frame = [(0.0, 0.33, -0.55), (0.0, 0.85, -0.1), (0.0, 0.95, 0.45), (0.0, 0.33, 0.55), (0.0, 0.55, 0.0), (0.0, 0.33, -0.55)]
    q = [cam.proj(B.w(pos, *v)) for v in frame]
    if min(v[2] for v in q) > 0.3:
        path = skia.Path()
        path.moveTo(q[0][0], q[0][1])
        for v in q[1:]:
            path.lineTo(v[0], v[1])
        path.moveTo(q[1][0], q[1][1])
        path.lineTo(q[4][0], q[4][1])
        fr.c.drawPath(path, paint("#c9622a", stroke=max(1.2, 0.03 * q[0][3])))
    bars = [cam.proj(B.w(pos, g * 0.25, 1.0, 0.45)) for g in (-1, 1)]
    if min(v[2] for v in bars) > 0.3:
        fr.c.drawLine(bars[0][0], bars[0][1], bars[1][0], bars[1][1], paint("#15161c", stroke=max(1.2, 0.025 * bars[0][3])))
    _box_local(fr, cam, pos, B, (-0.06, 0.06), (0.88, 0.94), (-0.22, 0.0), "#1a1b22")


def trolley(fr, cam, pos, yaw, colr="#2a3fa8"):
    """A two-wheeled shopping trolley (the elderly woman's), 1 m tall, bag on a frame."""
    B = Basis.yaw(yaw)
    _box_local(fr, cam, pos, B, (-0.18, 0.18), (0.12, 0.72), (-0.14, 0.14), colr, line=1.0)
    q0, q1 = cam.proj(B.w(pos, 0.0, 0.72, -0.1)), cam.proj(B.w(pos, 0.0, 1.0, -0.22))
    if min(q0[2], q1[2]) > 0.3:
        fr.c.drawLine(q0[0], q0[1], q1[0], q1[1], paint("#2a2b33", stroke=max(1.0, 0.02 * q0[3])))
    for g in (-1, 1):
        q = cam.proj(B.w(pos, g * 0.17, 0.08, -0.1))
        if q[2] > 0.3:
            fr.c.drawCircle(q[0], q[1], max(1.5, 0.08 * q[3]), paint("#15161c"))


def cart(fr, cam, pos, yaw):
    """A food cart with a striped awning and a hot plate glow."""
    B = Basis.yaw(yaw)
    _box_local(fr, cam, pos, B, (-0.7, 0.7), (0.3, 1.0), (-0.45, 0.45), "#c8c2b2", line=1.1)
    for g in (-1, 1):
        q = cam.proj(B.w(pos, g * 0.6, 0.25, 0.0))
        if q[2] > 0.3:
            fr.c.drawCircle(q[0], q[1], max(2.0, 0.25 * q[3]), paint("#15161c"))
    for g in (-1, 1):
        a, b = cam.proj(B.w(pos, g * 0.65, 1.0, 0.0)), cam.proj(B.w(pos, g * 0.65, 2.0, 0.0))
        if min(a[2], b[2]) > 0.3:
            fr.c.drawLine(a[0], a[1], b[0], b[1], paint("#3a3b44", stroke=max(1.0, 0.02 * a[3])))
    for i in range(6):                                       # the awning stripes
        x0, x1 = -0.9 + 0.3 * i, -0.6 + 0.3 * i
        pts = [B.w(pos, x0, 2.0, -0.6), B.w(pos, x1, 2.0, -0.6), B.w(pos, x1, 2.1, 0.6), B.w(pos, x0, 2.1, 0.6)]
        fr.poly(cam, pts, colr="#d8343a" if i % 2 else "#eeeae0", outline="#3a2a2a", line=1.0)
    q = cam.proj(B.w(pos, 0.2, 1.02, 0.0))
    if q[2] > 0.3:
        fr.glow(q[0], q[1], 0.5 * q[3], "#ffb060", a=0.35)


def umbrella(fr, cam, pos, yaw, inside_out=0.0, colr="#2b2f4a"):
    """Hand-held umbrella; inside_out 1 = blown inside out (canopy flips up)."""
    B = Basis.yaw(yaw)
    top = add(pos, (0.0, 0.9, 0.0))
    q0, q1 = cam.proj(pos), cam.proj(top)
    if min(q0[2], q1[2]) > 0.3:
        fr.c.drawLine(q0[0], q0[1], q1[0], q1[1], paint("#1a1b22", stroke=max(1.0, 0.015 * q0[3])))
    pts = []
    for i in range(12):
        a = 2 * math.pi * i / 12
        dy = -0.18 * (1 - inside_out) + 0.35 * inside_out
        pts.append(add(top, (0.5 * math.cos(a), dy, 0.5 * math.sin(a))))
    if cam.pos[1] > top[1] or inside_out > 0.5:
        fr.poly(cam, pts, colr=colr, outline=shade(colr, -0.6), line=1.1)
    else:
        for i in range(12):
            fr.poly(cam, [top, pts[i], pts[(i + 1) % 12]], colr=shade(colr, -0.1 + 0.1 * (i % 2)), outline=shade(colr, -0.6), line=0.8)


def coffee(fr, cam, pos):
    _cyl(fr, cam, pos, 0.04, 0.12, "#eeeae0", n=8, taper=1.15)


def sketchbook(fr, cam, pos, B):
    _box_local(fr, cam, pos, B, (-0.15, 0.15), (0.0, 0.02), (-0.2, 0.2), "#3a4a6a")


def box_stack(fr, cam, pos, yaw, n=3, fall=0.0):
    """Cardboard boxes in a stack; fall 0..1 topples them sideways."""
    B = Basis.yaw(yaw)
    for i in range(n):
        o = B.w(pos, 0.4 * fall * i, 0.42 * i * (1 - 0.6 * fall), 0.0)
        _box_local(fr, cam, o, B, (-0.25, 0.25), (0.0, 0.4), (-0.22, 0.22), "#a7773f", line=1.1)


def takeaway_bag(fr, cam, pos, B):
    _box_local(fr, cam, pos, B, (-0.12, 0.12), (0.0, 0.26), (-0.09, 0.09), "#d9c6a0", line=1.0)


def camera_prop(fr, cam, pos, B):
    _box_local(fr, cam, pos, B, (-0.08, 0.08), (0.0, 0.1), (-0.04, 0.06), "#15161c", line=1.0)


def dog(fr, cam, pos, yaw, colr="#8a6a44"):
    """A small dog on a lead: body, head, four legs, tail."""
    B = Basis.yaw(yaw)
    from sets.mara_room import soft
    soft(fr, cam, B.w(pos, 0.0, 0.32, 0.0), (0.12, 0.12, 0.26), colr, e=0.35)
    soft(fr, cam, B.w(pos, 0.0, 0.44, 0.3), (0.1, 0.09, 0.11), colr, e=0.35)
    for g in (-1, 1):
        for gz in (-0.17, 0.17):
            _box_local(fr, cam, B.w(pos, g * 0.07, 0.0, gz), B, (-0.025, 0.025), (0.0, 0.22), (-0.025, 0.025), shade(colr, -0.2))
    a, b = cam.proj(B.w(pos, 0.0, 0.4, -0.25)), cam.proj(B.w(pos, 0.0, 0.58, -0.4))
    if min(a[2], b[2]) > 0.3:
        fr.c.drawLine(a[0], a[1], b[0], b[1], paint(shade(colr, -0.2), stroke=max(1.0, 0.025 * a[3])))


def lead(fr, cam, a, b):
    qa, qb = cam.proj(a), cam.proj(b)
    if min(qa[2], qb[2]) > 0.3:
        fr.c.drawLine(qa[0], qa[1], qb[0], qb[1], paint("#c93a3a", stroke=max(1.0, 0.008 * qa[3])))


# ---- shop ---------------------------------------------------------------------------------------------------------
def mannequin(fr, cam, pos, yaw, headless=False, colr="#e8e4dc", top="#5a7fa8"):
    """A shop dummy on a stand: 1.75 m, plain white, a shirt over the torso."""
    B = Basis.yaw(yaw)
    from sets.mara_room import soft
    _cyl(fr, cam, pos, 0.22, 0.03, "#2a2b33", n=10)
    _box_local(fr, cam, pos, B, (-0.02, 0.02), (0.03, 0.75), (-0.02, 0.02), "#3a3b44")
    for g in (-1, 1):                                        # legs
        _box_local(fr, cam, B.w(pos, g * 0.09, 0.0, 0.0), B, (-0.07, 0.07), (0.1, 0.85), (-0.08, 0.08), colr, line=1.0)
    _box_local(fr, cam, pos, B, (-0.22, 0.22), (0.85, 1.45), (-0.12, 0.12), top, line=1.1)     # torso in a shirt
    for g in (-1, 1):
        _box_local(fr, cam, B.w(pos, g * 0.29, 0.0, 0.0), B, (-0.06, 0.06), (0.9, 1.42), (-0.07, 0.07), colr, line=1.0)
    _box_local(fr, cam, pos, B, (-0.05, 0.05), (1.45, 1.53), (-0.05, 0.05), colr)
    if not headless:
        soft(fr, cam, add(pos, (0.0, 1.66, 0.0)), (0.11, 0.13, 0.11), colr, e=0.3)


def mannequin_head(fr, cam, pos):
    from sets.mara_room import soft
    soft(fr, cam, pos, (0.11, 0.13, 0.11), "#e8e4dc", e=0.3)


def rail(fr, cam, pos, yaw, n=7, colours=("#b23a3a", "#2a4a7a", "#e8e4dc", "#3a7a4a", "#6a3a7a", "#d9a23a", "#333640")):
    """A clothes rail 1.6 m long with n hanging shirts."""
    B = Basis.yaw(yaw)
    for g in (-1, 1):
        _box_local(fr, cam, B.w(pos, g * 0.78, 0.0, 0.0), B, (-0.03, 0.03), (0.0, 1.55), (-0.03, 0.03), "#3a3b44")
    a, b = cam.proj(B.w(pos, -0.8, 1.55, 0.0)), cam.proj(B.w(pos, 0.8, 1.55, 0.0))
    if min(a[2], b[2]) > 0.3:
        fr.c.drawLine(a[0], a[1], b[0], b[1], paint("#8a8e98", stroke=max(1.2, 0.02 * a[3])))
    for i in range(n):
        x = -0.65 + 1.3 * i / max(1, n - 1)
        c = colours[i % len(colours)]
        _box_local(fr, cam, B.w(pos, x, 0.0, 0.0), B, (-0.17, 0.17), (0.75, 1.5), (-0.04, 0.04), c, line=1.0)


def shelf_wall(fr, cam, x, z0, z1, y0, y1, colr="#3a3328", folded=True):
    """A back wall of shelves (x = wall plane, facing -x), folded shirts in colour stacks."""
    fr.poly(cam, [(x, y0, z0), (x, y0, z1), (x, y1, z1), (x, y1, z0)], colr=colr, outline=shade(colr, -0.5), line=1.1)
    cols = ("#b23a3a", "#2a4a7a", "#e8e4dc", "#3a7a4a", "#d9a23a", "#6a3a7a")
    k = 0
    for y in (0.5, 1.0, 1.5, 2.0):
        fr.poly(cam, [(x - 0.35, y, z0), (x, y, z0), (x, y, z1), (x - 0.35, y, z1)], colr=shade(colr, 0.15), outline=shade(colr, -0.5), line=1.0)
        if folded:
            z = z0 + 0.25
            while z < z1 - 0.3:
                _box_local(fr, cam, (x - 0.18, y, z), Basis.yaw(0), (-0.15, 0.15), (0.0, 0.28), (-0.17, 0.17), cols[k % 6], line=0.9)
                k += 1
                z += 0.55


def price_sign(fr, cam, pos, B, text_col="#d8343a"):
    _box_local(fr, cam, pos, B, (-0.18, 0.18), (0.0, 0.12), (-0.005, 0.005), "#f2eee4", line=1.0)
    q = cam.proj(B.w(pos, 0.0, 0.06, 0.006))
    if q[2] > 0.3:
        fr.c.drawRect(skia.Rect(q[0] - 0.1 * q[3], q[1] - 0.025 * q[3], q[0] + 0.1 * q[3], q[1] + 0.025 * q[3]), paint(text_col))


def glass_pane(fr, cam, x, y0, y1, z0, z1, a=0.22, broken=0.0):
    """A shop window pane in the plane x; broken 0..1 removes it and leaves jagged edge triangles."""
    if broken <= 0.0:
        fr.poly(cam, [(x, y0, z0), (x, y0, z1), (x, y1, z1), (x, y1, z0)], colr="#8ab0d8", a=a, outline="#0b0f18", line=1.4)
        return
    zm, ym = (z0 + z1) / 2, (y0 + y1) / 2
    for i in range(10):                                      # the leftover shards round the frame
        a0 = 2 * math.pi * i / 10
        a1 = a0 + 0.35
        r0 = 0.35 * (0.6 + 0.4 * ((i * 0.37) % 1.0)) * (1 - 0.5 * broken)
        p0 = (x, ym + (y1 - y0) / 2 * math.sin(a0), zm + (z1 - z0) / 2 * math.cos(a0))
        p1 = (x, ym + (y1 - y0) / 2 * math.sin(a1), zm + (z1 - z0) / 2 * math.cos(a1))
        p2 = (x, ym + (y1 - y0) / 2 * r0 * 2.2 * math.sin((a0 + a1) / 2), zm + (z1 - z0) / 2 * r0 * 2.2 * math.cos((a0 + a1) / 2))
        fr.poly(cam, [p0, p1, p2], colr="#8ab0d8", a=a * 1.6, outline="#dfe8ff", line=1.0)


def glass_shards(fr, cam, pts):
    for p, s in pts:
        pts3 = [add(p, (0.0, 0.0, -s)), add(p, (s * 0.6, s * 0.3, s * 0.4)), add(p, (-s * 0.5, -s * 0.2, s * 0.5))]
        fr.poly(cam, pts3, colr="#dfe8ff", a=0.7, outline="#ffffff", line=0.8)


def rubbish(fr, cam, pts):
    """Loose rubbish bits (paper, peel, a can): (pos, size, colour)."""
    for p, s, c in pts:
        pts3 = [add(p, (-s, 0.0, -s * 0.6)), add(p, (s * 0.8, 0.0, -s * 0.4)), add(p, (s * 0.5, 0.0, s * 0.7)), add(p, (-s * 0.6, 0.0, s * 0.5))]
        fr.poly(cam, pts3, colr=c, outline=shade(c, -0.5), line=0.8)


# ---- rooftops and the alley ---------------------------------------------------------------------------------------
def ac_unit(fr, cam, pos, yaw, colr="#9aa0ac"):
    B = Basis.yaw(yaw)
    _box_local(fr, cam, pos, B, (-0.45, 0.45), (0.0, 0.7), (-0.4, 0.4), colr, line=1.1)
    q = cam.proj(B.w(pos, 0.0, 0.35, 0.41))
    if q[2] > 0.3:
        fr.c.drawCircle(q[0], q[1], max(2.0, 0.25 * q[3]), paint("#2a2b33", stroke=max(1.0, 0.03 * q[3])))


def chimney(fr, cam, pos, colr="#6a4a3a"):
    _box_local(fr, cam, pos, Basis.yaw(0), (-0.35, 0.35), (0.0, 1.1), (-0.3, 0.3), colr, line=1.1)
    for g in (-0.17, 0.17):
        _cyl(fr, cam, add(pos, (g, 1.1, 0.0)), 0.1, 0.35, "#b0583c", n=8)


def dish(fr, cam, pos, yaw):
    B = Basis.yaw(yaw)
    _box_local(fr, cam, pos, B, (-0.03, 0.03), (0.0, 0.8), (-0.03, 0.03), "#3a3b44")
    c = B.w(pos, 0.0, 0.85, 0.0)
    pts = [B.w(c, 0.38 * math.cos(2 * math.pi * i / 12), 0.38 * math.sin(2 * math.pi * i / 12), 0.0) for i in range(12)]
    fr.poly(cam, pts, colr="#c9ccd4", outline="#3a3b44", line=1.1)


def crate(fr, cam, pos, yaw, colr="#8a6a3a"):
    _box_local(fr, cam, pos, Basis.yaw(yaw), (-0.3, 0.3), (0.0, 0.5), (-0.3, 0.3), colr, line=1.1)


def cardboard(fr, cam, pos, yaw, colr="#a7773f"):
    _box_local(fr, cam, pos, Basis.yaw(yaw), (-0.45, 0.45), (0.0, 0.06), (-0.35, 0.35), colr, line=1.0)


def drainpipe(fr, cam, x, z, y0, y1, colr="#2a2b33"):
    _box_local(fr, cam, (x, y0, z), Basis.yaw(0), (-0.06, 0.06), (0.0, y1 - y0), (-0.06, 0.06), colr, line=1.0)


def washing_line(fr, cam, a, b, items=()):
    """A line between a and b with hung sheets: items = (u along the line, width, colour, flutter)."""
    qa, qb = cam.proj(a), cam.proj(b)
    if min(qa[2], qb[2]) > 0.3:
        fr.c.drawLine(qa[0], qa[1], qb[0], qb[1], paint("#8a8e98", stroke=max(1.0, 0.006 * qa[3])))
    for u, w, c, fl in items:
        p = add(a, mul((b[0] - a[0], b[1] - a[1], b[2] - a[2]), u))
        d = mul((b[0] - a[0], 0.0, b[2] - a[2]), 1.0 / max(1e-6, math.hypot(b[0] - a[0], b[2] - a[2])))
        pts = [add(p, mul(d, -w / 2)), add(p, mul(d, w / 2)), add(add(p, mul(d, w / 2 + 0.1 * fl)), (0.0, -0.9, 0.15 * fl)),
               add(add(p, mul(d, -w / 2 + 0.1 * fl)), (0.0, -0.95, 0.2 * fl))]
        fr.poly(cam, pts, colr=c, outline=shade(c, -0.5), line=1.0)


def sheet_wrap(fr, cam, head, R, colr="#e9d9c7", flap=0.0):
    """A floral bedsheet wrapped round a head: a soft blob over it with a tail flapping behind."""
    from sets.mara_room import soft
    soft(fr, cam, head, (R * 1.35, R * 1.3, R * 1.35), colr, e=0.3)
    tail = [add(head, (0.0, R * 0.6, -R * 1.1)), add(head, (R * 0.9, R * 0.2 + 0.1 * flap, -R * 2.6)), add(head, (-R * 0.7, -R * 0.5, -R * 2.9 - 0.15 * flap)),
            add(head, (0.0, -R * 0.9, -R * 1.2))]
    fr.poly(cam, tail, colr=colr, outline=shade(colr, -0.5), line=1.0)
    for dx, dz in ((0.3, -1.6), (-0.4, -2.0), (0.1, -2.5)):   # the flowers
        q = cam.proj(add(head, (dx * R, 0.0, dz * R)))
        if q[2] > 0.3:
            fr.c.drawCircle(q[0], q[1], max(1.0, 0.03 * R * 10 * q[3]), paint("#c96a8a"))


# ---- cats ---------------------------------------------------------------------------------------------------------
CAT = dict(ginger=("#d8863a", "#e8a86a"), calico=("#e8e4dc", "#d8863a"), black=("#15161c", "#15161c"), tabby=("#8a8e98", "#5a5e68"))


def cat(fr, cam, pos, yaw, pose="sit", pattern="ginger", t=0.0):
    """A toon cat, 0.4 m long: body, head with ears, tail; poses sit | arch | jump | slip (flat, under a car)."""
    from sets.mara_room import soft
    c0, c1 = CAT[pattern]
    B = Basis.yaw(yaw)
    if pose == "sit":
        soft(fr, cam, B.w(pos, 0.0, 0.17, -0.02), (0.1, 0.17, 0.14), c0, e=0.3)
        head = B.w(pos, 0.0, 0.36, 0.08)
    elif pose == "arch":
        soft(fr, cam, B.w(pos, 0.0, 0.26, 0.0), (0.09, 0.14, 0.2), c0, e=0.25)
        for g in (-1, 1):
            for gz in (-0.14, 0.14):
                _box_local(fr, cam, B.w(pos, g * 0.05, 0.0, gz), B, (-0.02, 0.02), (0.0, 0.16), (-0.02, 0.02), c0)
        head = B.w(pos, 0.0, 0.3, 0.26)
    elif pose == "jump":
        soft(fr, cam, B.w(pos, 0.0, 0.22, 0.0), (0.09, 0.1, 0.22), c0, e=0.3)
        for g in (-1, 1):
            _box_local(fr, cam, B.w(pos, g * 0.05, 0.0, 0.14), B, (-0.02, 0.02), (0.12, 0.28), (-0.02, 0.02), c0)
            _box_local(fr, cam, B.w(pos, g * 0.05, 0.0, -0.18), B, (-0.02, 0.02), (0.0, 0.14), (-0.02, 0.02), c0)
        head = B.w(pos, 0.0, 0.34, 0.26)
    else:                                                    # slip: flat and long, belly to the ground
        soft(fr, cam, B.w(pos, 0.0, 0.09, 0.0), (0.1, 0.08, 0.24), c0, e=0.3)
        head = B.w(pos, 0.0, 0.12, 0.26)
    soft(fr, cam, head, (0.085, 0.08, 0.085), c0, e=0.3)
    for g in (-1, 1):                                        # ears
        tri = [B.w(head, g * 0.03, 0.05, 0.0), B.w(head, g * 0.085, 0.04, 0.0), B.w(head, g * 0.06, 0.13, 0.0)]
        fr.poly(cam, tri, colr=c1, outline=shade(c0, -0.6), line=0.9)
    q = cam.proj(B.w(head, 0.0, 0.0, 0.09))
    if q[2] > 0.3:                                           # eyes: two green slits
        for g in (-1, 1):
            fr.c.drawOval(skia.Rect(q[0] + g * 0.035 * q[3] - 0.012 * q[3], q[1] - 0.012 * q[3], q[0] + g * 0.035 * q[3] + 0.012 * q[3], q[1] + 0.012 * q[3]),
                          paint("#b8ff6a"))
    tl = [B.w(pos, 0.0, 0.2 if pose != "slip" else 0.1, -0.16), B.w(pos, 0.06 * math.sin(t * 3.0), 0.38 if pose != "slip" else 0.14, -0.3),
          B.w(pos, 0.1 * math.sin(t * 3.0 + 1.0), 0.5 if pose != "slip" else 0.12, -0.36)]
    q = [cam.proj(v) for v in tl]
    if min(v[2] for v in q) > 0.3:
        path = skia.Path()
        path.moveTo(q[0][0], q[0][1])
        path.quadTo(q[1][0], q[1][1], q[2][0], q[2][1])
        fr.c.drawPath(path, paint(c0, stroke=max(1.5, 0.03 * q[0][3])))
