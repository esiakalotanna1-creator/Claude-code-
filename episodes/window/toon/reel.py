"""THE MAN AT THE WINDOW v2: the toon reel, driven by timeline.json (script.py + build_tl.py). Shot list: SPEC.md.

    py reel.py --stills [shots]    first/mid/last frame of every shot -> review/shots.png
    py reel.py --sheet S1 S2 ...   every frame of the named shots on gapped sheets -> review/all_<shot>.png
    py reel.py --check             constraint + caption checks over every frame -> review/reel_checks.txt
    py reel.py --preview           540x960 silent preview -> review/reel_preview.mp4
    py reel.py                     HQ master 1080x1920 -> video/reel_silent.mp4 (mux with the mix separately)
"""
import json
import math
import os
import subprocess
import sys

import numpy as np
import skia
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from kit import B  # noqa: E402  (also puts tools/toon on the path)
import rig  # noqa: E402
from toon import Camera, Frame, W, H, paint  # noqa: E402
import toon as TN  # noqa: E402
import scenes as S  # noqa: E402

FPS = 30
OUT = os.path.join(HERE, "review")
VID = os.path.join(HERE, "video")
for _d in (OUT, VID):
    os.makedirs(_d, exist_ok=True)
TL = json.load(open(os.path.join(HERE, "timeline.json"), encoding="utf-8"))
TOTAL = round(TL["total"], 3)
M = TL["marks"]

G = S.House(M, TL["lines"])
BR = S.Bedroom(M)
EASE = {"io": lambda u: u * u * (3 - 2 * u), "lin": lambda u: u, "out": lambda u: 1 - (1 - u) ** 3,
        "smooth": lambda u: u ** 3 * (u * (6 * u - 15) + 10)}


def _lerp(x, y, u):
    return tuple(p + (q - p) * u for p, q in zip(x, y)) if isinstance(x, tuple) else x + (y - x) * u


def track(a, b, ease="smooth", d0=0.0, d1=1.0):
    """a, b = (pos, target, f, horizon). The camera aims (yaw) at the lerped target: one smooth move, no drift."""
    def f(T, t0, t1):
        u = min(1.0, max(0.0, ((T - t0) / max(1e-6, t1 - t0) - d0) / max(1e-6, d1 - d0)))
        u = EASE[ease](u)
        pos, tgt, fl, hz = (_lerp(a[i], b[i], u) for i in range(4))
        yaw = math.degrees(math.atan2(tgt[0] - pos[0], tgt[2] - pos[2]))
        return Camera(pos, yaw, fl, hz)
    return f


SX = S.SX
DEYE = (S.DX, 1.67, S.DZ + 0.06)                                                   # the father's eyes (truth POV)
G.force = "truth"
_WR = rig.solve("dad", G.dad_pose(M["shears"] + 1.0))["wr_R"]                       # the fist holding the shears (truth)
G.force = None
SH_A = ((_WR[0] + 0.62, _WR[1] - 0.18, _WR[2] + 0.22), (_WR[0], _WR[1] - 0.26, _WR[2]), 1150, 0.40)
SH_B = ((_WR[0] + 0.58, _WR[1] - 0.18, _WR[2] + 0.20), (_WR[0], _WR[1] - 0.26, _WR[2]), 1220, 0.40)


def BW(a):
    """A truth-world camera key turned into the belief world (inside the room, the stranger outside)."""
    return (S.rot(a[0]), S.rot(a[1]), a[2], a[3])


def _bez(p0, c, p1, u):
    return tuple((1 - u) ** 2 * a + 2 * u * (1 - u) * b + u * u * d for a, b, d in zip(p0, c, p1))


def _cam(pos, tgt, fl, hz):
    yaw = math.degrees(math.atan2(tgt[0] - pos[0], tgt[2] - pos[2]))
    return Camera(pos, yaw, fl, hz)


# The twist, in truth-world coordinates: an over-the-shoulder behind the father, a curve round his shoulder, the
# face filling the frame. Before T_SWAP the move is played turned (inside the room, pushing IN); after it the same
# curve runs backwards in the truth world (outside in the rain, pulling OUT), holds, then travels on to a 3/4 wide.
OTS = (-1.18, 1.85, -2.0)                                                       # over his left shoulder, the window beyond
OTS_T = (SX - 0.05, 1.62, 0.3)
CURVE = (-0.95, 1.76, -0.62)
FACE = (SX, 1.64, -0.45)
FACE_T = (SX, 1.63, 0.3)
WIDE = ((-3.0, 1.55, -4.3), (-0.25, 1.45, 0.0), 1000, 0.47)
T_ARRIVE, T_LEAVE, T_OTS, T_GO = M["pull"] + 3.5, G.T_SWAP + 0.15, G.T_SWAP + 2.05, G.T_SWAP + 2.85


def twist_world(T):
    """Truth-world camera of the twist at time T (twist() turns it for the belief world)."""
    if T < T_ARRIVE:                                                          # push in (played turned)
        u = EASE["io"](min(1.0, max(0.0, (T - M["pull"]) / (T_ARRIVE - M["pull"]))))
        return _cam(_bez(OTS, CURVE, FACE, u), _lerp(OTS_T, FACE_T, u), 900 + (2600 - 900) * u ** 1.8, 0.46 + 0.01 * u)
    if T < T_LEAVE:                                                           # the face fills the frame: a slow creep
        u = (T - T_ARRIVE) / (T_LEAVE - T_ARRIVE)
        return _cam((FACE[0], FACE[1], FACE[2] + 0.02 * u), FACE_T, 2600 + 60 * u, 0.47)
    if T < T_OTS:                                                             # pull back out round his shoulder
        u = EASE["io"]((T - T_LEAVE) / (T_OTS - T_LEAVE))
        f0 = (FACE[0], FACE[1], FACE[2] + 0.02)
        return _cam(_bez(f0, CURVE, OTS, u), _lerp(FACE_T, OTS_T, u), 2660 + (900 - 2660) * (1 - (1 - u) ** 1.8), 0.47 - 0.01 * u)
    o2 = (OTS[0] - 0.05, OTS[1] - 0.01, OTS[2] - 0.08)
    if T < T_GO:                                                              # hold on the reveal: "I was looking in."
        u = (T - T_OTS) / (T_GO - T_OTS)
        return _cam(_lerp(OTS, o2, u), OTS_T, 900 - 20 * u, 0.46)
    u = EASE["smooth"](min(1.0, (T - T_GO) / (M["inside"] - T_GO)))           # on through the garden to the 3/4 wide
    return _cam(_lerp(o2, WIDE[0], u), _lerp(OTS_T, WIDE[1], u), 880 + (WIDE[2] - 880) * u, 0.46 + 0.01 * u)


def twist(T, t0, t1):
    c = twist_world(T)
    if G.flip(T):
        tgt = (c.pos[0] + c.fwd[0], c.pos[1], c.pos[2] + c.fwd[2])
        return _cam(S.rot(c.pos), S.rot(tgt), c.f, c.horizon)
    return c


XFADE = (G.T_SWAP, 0.36)                                                     # the worlds swap inside the face

# name, start, end, scene, camera, opts (blur = background defocus px, keep = sharp pids, cap = (y, size))
# Shots 1-9 are the belief world: every camera is the truth camera turned through the glass with BW().
SHOTS = [
    # 1. ECU from inside: his forehead pressed on the outside of the rainy glass, eyes on us, the smile cropped
    ("H1", 0.0, M["widen"], G, track(BW(((SX, 1.75, -0.60), (SX, 1.71, 0.3), 2900, 0.36)), BW(((SX, 1.73, -0.57), (SX, 1.70, 0.3), 3050, 0.37)), "lin"), dict(cap=(600, 62))),
    # 2. the slow widen: the whole face, then the night garden round him and the frame of the window
    ("WD", M["widen"], M["dad"], G, track(BW(((SX, 1.73, -0.57), (SX, 1.70, 0.3), 3050, 0.37)), BW(((SX, 1.54, -0.70), (SX, 1.52, 0.3), 1080, 0.50)), "smooth"), dict(cap=lambda T: (600, 62) if T < 5.61 else (1450, 60))),
    # 3. the father's face from beside the window: the lamp-lit living room behind him, out of focus
    ("DF", M["dad"], M["stare"], G, track(BW(((-0.40, 1.67, -0.12), (0.80, 1.60, -2.6), 980, 0.40)), BW(((-0.40, 1.67, -0.15), (0.80, 1.60, -2.6), 1050, 0.40)), "lin"),
     dict(blur=14, keep={"dad"})),
    # 4. back to him from the father's eyes, a little closer
    ("ST", M["stare"], M["hand"], G, track(BW(((SX - 0.03, 1.57, -0.66), (SX, 1.57, 0.3), 1350, 0.50)), BW(((SX - 0.02, 1.57, -0.60), (SX, 1.57, 0.3), 1560, 0.50)), "lin"), {}),
    # 5. the hand comes up and presses flat on the outside of the glass
    ("HA", M["hand"], M["bed"], G, track(BW(((-0.10, 1.52, -0.70), (-0.14, 1.44, 0.3), 1120, 0.47)), BW(((-0.11, 1.51, -0.67), (-0.14, 1.43, 0.3), 1180, 0.47)), "lin"), dict(cap=(360, 58))),
    # 6. upstairs: she is asleep, the crib beside her, the nightlight, rain on the window
    ("BD", M["bed"], 22.95, BR, track(((-1.15, 1.40, 3.60), (-1.02, 0.72, 2.56), 1150, 0.06), ((-1.15, 1.37, 3.52), (-1.02, 0.72, 2.56), 1230, 0.06), "lin"), dict(cap=(1500, 60))),
    # 6b. the baby asleep in the crib under the turning mobile, from above the rail
    ("BC", 22.95, M["mouth"], BR, track(((-0.25, 1.80, 4.30), (0.29, 0.49, 3.565), 650, 0.02), ((-0.20, 1.78, 4.24), (0.29, 0.49, 3.565), 690, 0.02), "lin"), dict(cap=(1500, 60))),
    # 7. tight on his mouth and eyes: the lips part, nothing comes out
    ("DM", M["mouth"], M["slide"], G, track(BW(((S.DX + 0.02, 1.64, -0.26), (S.DX, 1.64, -2.2), 1900, 0.45)), BW(((S.DX + 0.02, 1.64, -0.27), (S.DX, 1.64, -2.2), 1980, 0.45)), "lin"),
     dict(blur=16, keep={"dad"}, cap=(250, 62))),
    # 8. the palm slides down the pane; the smile does not move
    ("SL", M["slide"], M["shears"], G, track(BW(((SX - 0.12, 1.58, -0.72), (SX - 0.14, 1.52, 0.3), 1150, 0.47)), BW(((SX - 0.12, 1.57, -0.69), (SX - 0.14, 1.51, 0.3), 1190, 0.47)), "lin"), {}),
    # 9. the gardening shears hanging from his hand, indoors; the grip tightens
    ("SH", M["shears"], M["pull"], G, track(BW(SH_A), BW(SH_B), "lin"),
     dict(blur=14, keep={"dad"})),
    # 10. THE TWIST (see twist_world)
    ("PU", M["pull"], M["inside"], G, twist, dict(cap=(330, 56), xfade=XFADE)),
    # 11. the father's view again, from the garden: the stranger at the pane, the room and the staircase behind him
    ("IN", M["inside"], M["smile"], G, track((DEYE, (SX - 0.35, 1.50, 2.0), 720, 0.47), ((DEYE[0], DEYE[1], DEYE[2] + 0.03), (SX - 0.35, 1.50, 2.0), 760, 0.47), "lin"),
     dict(cap=(1720, 54))),
    # 12. the smile, unchanged. Hold. Then black.
    ("SM", M["smile"], M["black"], G, track(((SX, 1.62, -0.60), (SX, 1.61, 0.3), 2700, 0.46), ((SX, 1.62, -0.59), (SX, 1.61, 0.3), 2740, 0.46), "lin"), {}),
    ("BL", M["black"], TOTAL, None, None, {}),
]


def shot_at(T):
    for s in SHOTS:
        if s[1] <= T < s[2]:
            return s
    return SHOTS[-1]


# ---- text ----------------------------------------------------------------------------------------------------
CHUNKS = sorted([c for L in TL["lines"] for c in L["chunks"]], key=lambda c: c["t0"])
CAP_Y = 1640
TF = TN.typeface()
SMALL = skia.Font(TF, 36)
LABEL = (0.3, 2.8)


def caption(T):
    cur = None
    for c in CHUNKS:
        if c["t0"] <= T + 1e-6:
            cur = c
    return cur["text"] if cur and T < cur["t1"] + 0.45 else None


def cap_of(name, T=0.0):
    for s in SHOTS:
        if s[0] == name:
            c = s[5].get("cap", (CAP_Y, 66))
            return c(T) if callable(c) else c
    return (CAP_Y, 66)


def caption_box(text, y=CAP_Y, size=66):
    w = skia.Font(TF, size).measureText(text.replace("[", "").replace("]", "")) + 16
    return ((W - w) / 2, y - size * 0.73, (W + w) / 2, y + size * 0.33)


def draw_caption(fr, text, y=CAP_Y, size=66):
    f = skia.Font(TF, size)
    parts = [(b.strip("[]"), b.startswith("[")) for b in text.replace("[", "|[").replace("]", "]|").split("|") if b]
    x = (W - sum(f.measureText(p) for p, _ in parts)) / 2
    for p, key in parts:
        blob = skia.TextBlob(p, f)
        fr.c.drawTextBlob(blob, x, y, paint("#000000", stroke=size * 0.18))
        fr.c.drawTextBlob(blob, x, y, paint("#FF4D4D" if key else "#F4F1EA"))
        x += f.measureText(p)


def centered(fr, text, font, y, colr, a=1.0, stroke=10):
    x = (W - font.measureText(text)) / 2
    blob = skia.TextBlob(text, font)
    fr.c.drawTextBlob(blob, x, y, paint("#000000", a=a, stroke=stroke))
    fr.c.drawTextBlob(blob, x, y, paint(colr, a=a))


def labels(fr, T):
    a0, a1 = LABEL
    if a0 <= T < a1:
        a = min(1.0, (T - a0) / 0.3, (a1 - T) / 0.3)
        centered(fr, "AN INTERNET HORROR STORY", SMALL, 300, "#E8E8E8", a=a, stroke=7)


# ---- frames ----------------------------------------------------------------------------------------------------
def render(T, scale=1.0, captions=True, log=None):
    name, t0, t1, sc, camf, opt = shot_at(T)
    xf = opt.get("xfade") if sc is not None else None
    if xf and abs(T - xf[0]) < xf[1] / 2 and log is None:
        sc.force = "belief"                                   # the same face in both worlds; only its surroundings change
        _, a = render_one(T, scale, captions, None)
        sc.force = "truth"
        _, b = render_one(T, scale, captions, None)
        sc.force = None
        u = (T - (xf[0] - xf[1] / 2)) / xf[1]
        u = u * u * (3 - 2 * u)
        return name, np.clip(a.astype(np.float32) * (1 - u) + b.astype(np.float32) * u + 0.5, 0, 255).astype(np.uint8)
    return render_one(T, scale, captions, log)


def render_one(T, scale=1.0, captions=True, log=None):
    name, t0, t1, sc, camf, opt = shot_at(T)
    if sc is None:
        return name, Frame(scale, bg="#000000").array()
    cam = camf(T, t0, t1)
    fr = Frame(scale)
    blur, keep = opt.get("blur", 0), opt.get("keep", set())
    if blur:                                     # shallow focus: everything behind the subject goes into a blurred layer
        fr.c.saveLayer(None, skia.Paint(ImageFilter=skia.ImageFilters.Blur(blur * scale, blur * scale)))
    sc.bg(fr, cam, T)
    items = sc.items(cam, T)
    outs = {}
    for pid, look, p, held, glow, after in sc.cast(T):
        J = rig.solve(look, p)
        light = sc.nearest_light(J["pelvis"])

        def fn(fr, pid=pid, look=look, p=p, held=held, glow=glow, after=after, light=light):
            graded = hasattr(sc, "grade")
            if graded:
                fr.c.saveLayer(None, None)
            o = rig.draw(fr, cam, look, p, light=light, glow=glow, held=held)
            outs[pid] = o
            if after and not o.get("culled"):
                after(fr, cam, o["J"])
            if graded:
                sc.grade(fr, cam, T, pid, o)
                fr.c.restore()
            if log is not None and not o.get("culled"):
                _log_person(log, o, name, T, pid, look, p, cam)
        items.append((cam.view(J["pelvis"])[2], fn, pid))
    order = sorted(items, key=lambda q: -q[0])
    open_ = bool(blur)
    for _, fn, nm in order:
        if open_ and nm in keep:
            fr.c.restore()
            open_ = False
        fn(fr)
    if open_:
        fr.c.restore()
    if log is not None:
        log.append(dict(kind="order", t=T, shot=name, order=[n for _, _, n in order], cam=cam, scene=sc))
    sc.overlay(fr, cam, T, outs)
    sc.post(fr, cam, T)
    labels(fr, T)
    if captions:
        c = caption(T)
        if c:
            y, size = cap_of(name, T)
            draw_caption(fr, c, y, size)
    return name, fr.array()


def _log_person(log, j, shot, T, pid, look, p, cam):
    J = j["J"]
    log.append(dict(kind="person", J=J, t=T, shot=shot, name=pid, look=look, plant=p.get("plant", "both"),
                    ank_R=J["ank_R"], ank_L=J["ank_L"], head=j["head"], head_r=j["head_r"],
                    hand_R=j.get("hand_R"), hand_L=j.get("hand_L"), err=J["err"],
                    floor={s: p.get("floor_" + s, p.get("floor", 0.0)) for s in "RL"},
                    joints={k: cam.proj(J[k])[:2] for k in ("head", "wr_R", "wr_L", "el_R", "el_L", "kn_R", "kn_L")}))


# ---- checks --------------------------------------------------------------------------------------------------
def frames_of(a, b):
    return [i / FPS for i in range(int(round(a * FPS)), int(round(b * FPS)))]


def _allowed(sc, a, pa, b, pb, pen):
    for x, px, y, py, tol in getattr(sc, "allow", []):
        if ((a.startswith(x) and pa.startswith(px) and b.startswith(y) and pb.startswith(py)) or
                (b.startswith(x) and pb.startswith(px) and a.startswith(y) and pa.startswith(py))) and pen <= tol:
            return True
    return False


def constraints(log):
    rep, hits = [], {}

    def hit(key, t, msg):
        a = hits.setdefault(key, [t, t, msg])
        a[0], a[1] = min(a[0], t), max(a[1], t)
        if len(msg) > len(a[2]):
            a[2] = msg
    people = [r for r in log if r["kind"] == "person"]
    scene_of = {r["shot"]: r["scene"] for r in log if r["kind"] == "order"}
    by, frames = {}, {}
    for r in people:
        by.setdefault((r["shot"], r["name"]), []).append(r)
        frames.setdefault((r["shot"], r["t"]), {})[r["name"]] = r
    for (shot, name), rs in by.items():
        sc = scene_of[shot]
        solids = sc.solids()
        prev = None
        for r in rs:
            J, t, h = r["J"], r["t"], r["J"]["h"]
            for s in ("R", "L"):
                up, fo = rig.sub(J["el_" + s], J["sh_" + s]), rig.sub(J["wr_" + s], J["el_" + s])
                if B._angle(up, fo) > 155:
                    hit((shot, name, "elbow over-bent", s), t, f"elbow_{s} {B._angle(up, fo):.0f} deg")
                thigh, shin = rig.sub(J["kn_" + s], J["hip_" + s]), rig.sub(J["ank_" + s], J["kn_" + s])
                kf = rig.dot(rig.sub(J["kn_" + s], rig.mul(rig.add(J["hip_" + s], J["ank_" + s]), 0.5)), J["Bb"].f)
                if kf < -0.005 and r["plant"] != "none":
                    hit((shot, name, "knee reversed", s), t, f"knee_{s} {kf * 1000:.0f} mm behind the leg line")
                if prev:
                    for lab, a1, b1, a0, b0 in (("elbow", up, fo, rig.sub(prev["el_" + s], prev["sh_" + s]), rig.sub(prev["wr_" + s], prev["el_" + s])),
                                                ("knee", thigh, shin, rig.sub(prev["kn_" + s], prev["hip_" + s]), rig.sub(prev["ank_" + s], prev["kn_" + s]))):
                        if B._angle(a1, b1) > 12 and B._angle(a0, b0) > 12 and rig.dot(rig.cross(a1, b1), rig.cross(a0, b0)) < 0:
                            hit((shot, name, f"{lab} flip", s), t, f"{lab}_{s} bend plane flipped between frames")
                ay = J["ank_" + s][1] - r["floor"][s] - 0.035 * h
                if r["plant"] != "none":
                    if ay < -0.003:
                        hit((shot, name, "foot sinks", s), t, f"ankle_{s} {ay * 1000:.0f} mm into the floor")
                    if r["plant"] in (s, "both") and abs(ay) > 0.003:
                        hit((shot, name, "planted foot floats", s), t, f"ankle_{s} {ay * 1000:.0f} mm off the floor")
                for k in ("arm_" + s, "leg_" + s):
                    if r["err"].get(k, 0) > 0.02:
                        hit((shot, name, "reach short", k), t, f"{k} target {r['err'][k] * 100:.0f} cm out of reach")
            for part, c, rad in B._spheres(J):
                for sn, box in solids.items():
                    pen = B._box_pen(c, rad, box)
                    if pen > 0.005 and not _allowed(sc, name, part, sn, "", pen):
                        hit((shot, name, "passes through", sn, part), t, f"{part} {pen * 1000:.0f} mm inside {sn}")
            prev = J
    orders = [r for r in log if r["kind"] == "order"]
    for (shot, name), rs in by.items():
        acc = (0.0, "")
        for p, q, r in zip(rs, rs[1:], rs[2:]):
            for k in p["joints"]:
                a2 = math.hypot(r["joints"][k][0] - 2 * q["joints"][k][0] + p["joints"][k][0],
                                r["joints"][k][1] - 2 * q["joints"][k][1] + p["joints"][k][1])
                if a2 > acc[0] and -200 < q["joints"][k][0] < W + 200 and -200 < q["joints"][k][1] < H + 200:
                    acc = (a2, f"{k} {q['t']:.2f}s")
        drift = 0.0
        for p, q in zip(rs, rs[1:]):
            for s in ("R", "L"):
                if p["plant"] in (s, "both") and q["plant"] in (s, "both"):
                    drift = max(drift, math.dist(p["ank_" + s], q["ank_" + s]))
        rep.append(f"{shot:4s} {name:8s} max joint accel {acc[0]:6.1f} px/f^2 at {acc[1]:12s} | planted-foot drift {drift * 1000:5.2f} mm")
    del orders
    # the glass geography: nobody changes sides, the hand never passes the inner face
    for r in people:
        if r["shot"] in ("BD", "BC"):
            continue
        sg = -1.0 if G.flip(r["t"]) else 1.0                       # belief: the two men are turned through the glass
        if r["name"] == "stranger" and sg * r["J"]["pelvis"][2] < 0.0:
            hit((r["shot"], "stranger", "wrong side"), r["t"], "the stranger's pelvis is on the wrong side of the glass")
        if r["name"] == "dad" and sg * r["J"]["pelvis"][2] > S.Z_OUT:
            hit((r["shot"], "dad", "wrong side"), r["t"], "the father is on the wrong side of the wall")
    for T in sorted({r["t"] for r in people}):
        hs = G.hand_state(T)
        if hs and LK.hand_min_z(*hs[:5]) < 0.004:
            hit(("hand", "stranger", "hand through glass"), T, f"hand {LK.hand_min_z(*hs[:5]) * 1000:.1f} mm from the pane")
    for (shot, *what), (ta, tb, msg) in sorted(hits.items(), key=lambda kv: kv[1][0]):
        rep.append(f"ANOMALY {shot} {ta:.2f}-{tb:.2f}s {what[0]}: {msg}")
    if not hits:
        rep.append("constraints: no joint, contact, collision or side anomaly in any logged frame")
    caps, cost = set(), {}
    for r in people:
        c = caption(r["t"])
        if not c:
            continue
        y0_, size = cap_of(r["shot"], r["t"])
        x0, y0, x1, y1 = caption_box(c, y0_, size)
        for what, pt, rr in (("face", r["head"], r["head_r"]), ("hand_R", r["hand_R"], 30), ("hand_L", r["hand_L"], 30)):
            if pt and x0 - rr < pt[0] < x1 + rr and y0 - rr < pt[1] < y1 + rr and -50 < pt[0] < W + 50:
                caps.add(f"caption {r['shot']} {r['t']:.2f}s {r['name']} {what} under '{c}'")
    rep += sorted(caps) or ["caption: no face or hand under the caption in any frame"]
    return rep


import looks as LK  # noqa: E402


def label(im, text):
    d = ImageDraw.Draw(im)
    d.rectangle((0, im.height - 22, im.width, im.height), fill=(0, 0, 0))
    d.text((6, im.height - 18), text, fill=(255, 255, 0))
    return im


def stills(only=None, scale=0.3):
    os.makedirs(OUT, exist_ok=True)
    tiles = []
    for name, a, b, _, _, _ in SHOTS:
        if only and name not in only:
            continue
        ts = frames_of(a, b)
        for lab, t in (("first", ts[0]), ("mid", ts[len(ts) // 2]), ("last", ts[-1])):
            tiles.append(label(Image.fromarray(render(t, scale)[1]), f"{name} {lab} {t:.2f}s"))
    B.sheet(tiles, os.path.join(OUT, "shots.png" if not only else f"shots_{'_'.join(only)}.png"), cols=6)
    print("stills", len(tiles))


def sheets(names, step=1):
    os.makedirs(OUT, exist_ok=True)
    known = [x[0] for x in SHOTS]
    for n in names:
        if n not in known:
            sys.exit(f"no shot named {n!r}: the shots are {', '.join(known)}")
    for name, a, b, _, _, _ in SHOTS:
        if name not in names:
            continue
        tiles = [label(Image.fromarray(render(t, 0.2)[1]), f"{t:.2f}") for t in frames_of(a, b)[::step]]
        B.sheet(tiles, os.path.join(OUT, f"all_{name}.png"), cols=10)
        print("sheet", name, len(tiles))


def check(only=None):
    log = []
    for name, a, b, sc, _, _ in SHOTS:
        if sc is None or (only and name not in only):
            continue
        for t in frames_of(a, b):
            render(t, 0.2, captions=False, log=log)
    rep = constraints(log)
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "reel_checks.txt"), "w").write("\n".join(rep) + "\n")
    print("\n".join(rep))
    print(sum(r.startswith("ANOMALY") for r in rep), "anomaly lines")


def downsample(a, rng=np.random.default_rng(7)):
    h, w = a.shape[0] // 2, a.shape[1] // 2
    f = a.astype(np.float32).reshape(h, 2, w, 2, 3).mean((1, 3))
    f += rng.random(f.shape, dtype=np.float32) - rng.random(f.shape, dtype=np.float32)
    return np.clip(np.rint(f), 0, 255).astype(np.uint8)


def encode(frames, path, size, crf="16", preset="medium"):
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", size, "-r", str(FPS),
                          "-i", "-", "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
                          "-c:v", "libx264", "-crf", crf, "-preset", preset, "-tune", "animation",
                          "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
                          path], stdin=subprocess.PIPE)
    for a in frames:
        p.stdin.write(np.ascontiguousarray(a).tobytes())
    p.stdin.close()
    p.wait()


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--stills" in a:
        stills([x for x in a if not x.startswith("--")] or None, scale=0.5 if "--big" in a else 0.3)
    elif "--sheet" in a:
        sheets([x for x in a if not x.startswith("--")], step=2 if "--half" in a else 1)
    elif "--check" in a:
        check([x for x in a if not x.startswith("--")] or None)
    elif "--frame" in a:
        if not [x for x in a if not x.startswith("--")]:
            sys.exit("usage: python reel.py --frame <seconds>")
        t = float([x for x in a if not x.startswith("--")][0])
        Image.fromarray(render(t, 0.5)[1]).save(os.path.join(OUT, f"_f{t:.2f}.png"))
    elif "--master-part" in a:                                   # one contiguous chunk of the master (see --master-par)
        k, n = (int(x) for x in a[a.index("--master-part") + 1:a.index("--master-part") + 3])
        fr = frames_of(0, TOTAL)
        L = -(-len(fr) // n)
        TN.HQ["on"] = True
        encode((downsample(render(t, 2.0)[1]) for t in fr[k * L:(k + 1) * L]), os.path.join(VID, f"_part{k:02d}.mp4"),
               f"{W}x{H}", crf="10", preset="slow")
    elif "--master-par" in a:                                    # the master on n processes; frames are order-independent
        n = int(a[a.index("--master-par") + 1])
        os.makedirs(VID, exist_ok=True)
        procs = [subprocess.Popen([sys.executable, os.path.abspath(__file__), "--master-part", str(k), str(n)]) for k in range(n)]
        if any([p.wait() for p in procs]):                       # wait for all of them, then fail
            sys.exit("a master part failed")
        lst = os.path.join(VID, "_parts.txt")
        open(lst, "w").write("".join(f"file '_part{k:02d}.mp4'\n" for k in range(n)))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy",
                        os.path.join(VID, "reel_silent.mp4")], check=True)
        for k in range(n):
            os.remove(os.path.join(VID, f"_part{k:02d}.mp4"))
        os.remove(lst)
        print("reel_silent.mp4")
    elif "--preview" in a:
        os.makedirs(OUT, exist_ok=True)
        encode((render(t, 1.0 if "--full" in a else 0.5)[1] for t in frames_of(0, TOTAL)), os.path.join(OUT, "reel_preview.mp4"),
               "1080x1920" if "--full" in a else "540x960")
    else:
        os.makedirs(VID, exist_ok=True)
        TN.HQ["on"] = True
        encode((downsample(render(t, 2.0)[1]) for t in frames_of(0, TOTAL)), os.path.join(VID, "reel_silent.mp4"),
               f"{W}x{H}", crf="10", preset="slow")
        print("reel_silent.mp4")
