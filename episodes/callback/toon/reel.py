"""LEAVE A MESSAGE: the reel. Every shot is anchored to the beats in timeline.json (real voice-take lengths).

    python reel.py --frame T [scale]   one frame -> review/_f<T>.png
    python reel.py --stills            first/mid/last frame of every shot -> review/shots.png
    python reel.py --sheet S1 S2 ...   every frame of the named shots (--half: every 2nd) -> review/all_<shot>.png
    python reel.py --check             joint, reach and caption checks over every frame -> review/reel_checks.txt
    python reel.py --preview [--full]  silent preview -> review/reel_preview.mp4
    python reel.py --master-par N      HQ master on N processes -> video/reel_silent.mp4
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
import sets as S  # noqa: E402  (puts tools/toon on the path)
import acting as A  # noqa: E402
import ui  # noqa: E402
import rig  # noqa: E402
import toon as TN  # noqa: E402
from anim import HOLD, Track  # noqa: E402
from toon import Camera, Frame, W, H, argb, paint, rad  # noqa: E402

FPS = 30
OUT, VID = os.path.join(HERE, "review"), os.path.join(HERE, "video")
TL = A.TL
TOTAL = round(TL["total"], 3)
b0 = lambda k: A.bt(k, "t0")     # noqa: E731
b1 = lambda k: A.bt(k, "t1")     # noqa: E731
EASE = {"lin": lambda u: u, "io": lambda u: u * u * (3 - 2 * u), "out": lambda u: 1 - (1 - u) ** 3,
        "smooth": lambda u: u ** 3 * (u * (6 * u - 15) + 10)}

FLAT, ROOM, MEM = S.Flat(), S.Room(), S.Flat(day=True)


def track(a, b, ease="smooth"):
    """One camera move between keys (position, target, focal px, horizon)."""
    def f(T, t0, t1):
        u = EASE[ease](min(1.0, max(0.0, (T - t0) / max(1e-6, t1 - t0))))
        pos, tgt, fl, hz = (tuple(p + (q - p) * u for p, q in zip(x, y)) if isinstance(x, tuple) else x + (y - x) * u for x, y in zip(a, b))
        return Camera(pos, math.degrees(math.atan2(tgt[0] - pos[0], tgt[2] - pos[2])), fl, hz)
    return f


def K(pos, tgt, f, hz=0.44):
    return (pos, tgt, f, hz)


# ======================================================================================================== acting
# Maya on the window seat (all her seat scenes). ph: 0 ear, 1 phone up in front, 2 lap, 3 hand resting.
MS = Track([
    (0.0, dict(ph=0.0, lid=0.72, brow=-0.25, smile=0.0, mouth=0.0, gx=0.0, gy=-0.2, head_yaw=-10.0, head_pitch=6.0, head_roll=6.0, lean=4.0, tear=0.0)),
    (b0("greet") + 0.1, dict(lid=HOLD, smile=HOLD, head_roll=HOLD)),
    (b0("greet") + 0.5, dict(lid=0.0, head_roll=9.0), "io"),
    (b0("greet") + 2.2, dict(smile=0.18), "io"),
    (b1("greet"), dict(tear=0.35), "io"),
    (b0("never") + 0.2, dict(lid=HOLD, gy=HOLD, head_pitch=HOLD, ph=HOLD)),
    (b0("never") + 0.6, dict(lid=0.68, gy=-0.6), "io"),
    (b0("never") + 1.4, dict(ph=1.0, head_pitch=16.0, head_roll=3.0, smile=0.0), "io"),
    (b1("never") - 0.5, dict(ph=HOLD, head_pitch=HOLD, tear=HOLD)),
    (b1("never") + 0.3, dict(ph=2.0, head_pitch=10.0, tear=0.0), "io"),
    (b0("twice") - 0.2, dict(ph=HOLD, lid=HOLD, gy=HOLD, head_pitch=HOLD, head_yaw=HOLD)),
    (b0("twice") + 0.5, dict(ph=0.0, lid=0.75, gy=-0.25, head_pitch=6.0, head_yaw=-10.0), "io"),
    (b0("hello") + 0.05, dict(lid=HOLD, brow=HOLD, mouth=HOLD, lean=HOLD, head_pitch=HOLD, gy=HOLD)),
    (b0("hello") + 0.16, dict(lid=1.2, brow=0.55, gy=0.0), "snap"),
    (b0("hello") + 0.30, dict(mouth=0.22, lean=-6.0, head_pitch=-2.0), "out"),
    (b1("hello") + 0.10, dict(ph=HOLD)),
    (b1("hello") + 0.35, dict(ph=1.0), "snap"),
    (b0("drop") + 0.25, dict(ph=HOLD, head_yaw=HOLD, head_pitch=HOLD, gy=HOLD, gx=HOLD, mouth=HOLD)),
    (b0("drop") + 0.65, dict(ph=3.0, head_yaw=12.0, head_pitch=16.0, gy=-0.6, gx=0.4, mouth=0.12), "out"),
    (b1("drop") + 0.5, dict(brow=0.3, lid=1.05), "io"),
    # the calls: relaxed, then the split screen, the laugh
    (b0("across"), dict(ph=HOLD, lid=HOLD, brow=HOLD, smile=HOLD, mouth=HOLD, gx=HOLD, gy=HOLD, head_yaw=HOLD, head_pitch=HOLD, head_roll=HOLD, lean=HOLD, tear=HOLD)),
    (b0("loud") - 0.1, dict(ph=0.0, lid=0.85, brow=-0.1, smile=0.08, mouth=0.0, gx=0.0, gy=-0.15, head_yaw=-8.0, head_pitch=5.0,
                            head_roll=6.0, lean=3.0, tear=0.0)),
    (b0("laughed") + 0.3, dict(smile=HOLD, lid=HOLD, mouth=HOLD, head_pitch=HOLD, lean=HOLD, brow=HOLD)),
    (b0("laughed") + 0.7, dict(smile=0.95, lid=0.25, mouth=0.42, head_pitch=-10.0, lean=-7.0, brow=0.3), "out"),
    (b0("laughed") + 2.4, dict(mouth=HOLD, lid=HOLD, head_pitch=HOLD, lean=HOLD)),
    (b1("laughed") + 0.3, dict(mouth=0.08, lid=0.7, head_pitch=4.0, lean=2.0, smile=0.55), "io"),
    # telling him about her dad: she looks out at the rain, then back
    (b0("told") - 0.05, dict(head_yaw=HOLD, gx=HOLD, gy=HOLD, head_pitch=HOLD, smile=HOLD, brow=HOLD, lid=HOLD)),
    (b0("told") + 0.6, dict(head_yaw=-4.0, gx=0.0, gy=-0.55, head_pitch=12.0, smile=0.1, brow=-0.3, lid=0.75), "io"),
    (b0("callback") - 0.2, dict(head_yaw=HOLD, gx=HOLD, tear=HOLD)),
    (b0("callback") + 0.4, dict(head_yaw=-6.0, gx=0.0, tear=0.3), "io"),
    (b0("callback") + 1.0, dict(gy=HOLD, head_pitch=HOLD)),
    (b0("callback") + 1.6, dict(gy=-0.15, head_pitch=5.0), "io"),
    (b0("smiling") - 0.3, dict(smile=HOLD, tear=HOLD, lid=HOLD, brow=HOLD)),
    (b0("smiling") + 0.3, dict(smile=0.55, tear=0.75, lid=0.72, brow=-0.4), "io"),
    (b0("thursday") + 0.2, dict(ph=HOLD, smile=HOLD, tear=HOLD, lid=HOLD, brow=HOLD, gy=HOLD, gx=HOLD, head_pitch=HOLD, head_yaw=HOLD, head_roll=HOLD)),
    # the anniversary: phone in front, a glance at his photo, then the last call
    (b0("goodbye") - 0.1, dict(ph=1.0, smile=0.0, tear=0.0, lid=0.8, brow=-0.5, gy=-0.55, gx=0.0, head_pitch=14.0, head_yaw=-4.0, head_roll=3.0)),
    (b0("goodbye") + 1.6, dict(head_yaw=HOLD, gx=HOLD, gy=HOLD, head_pitch=HOLD)),
    (b0("goodbye") + 2.3, dict(head_yaw=48.0, gx=0.75, gy=-0.3, head_pitch=8.0), "io"),
    (b0("goodbye") + 3.9, dict(head_yaw=HOLD, gx=HOLD, gy=HOLD, head_pitch=HOLD)),
    (b0("goodbye") + 4.6, dict(head_yaw=-4.0, gx=0.0, gy=-0.55, head_pitch=14.0), "io"),
    (b0("rang") - 0.3, dict(ph=HOLD, head_pitch=HOLD, gy=HOLD)),
    (b0("rang") + 0.4, dict(ph=0.0, head_pitch=6.0, gy=-0.2), "io"),
    (b0("voice") + 0.5, dict(lid=HOLD, brow=HOLD, mouth=HOLD)),
    (b0("voice") + 0.8, dict(lid=1.1, brow=0.35, mouth=0.1), "out"),
    (b0("newgreet") + 1.5, dict(tear=HOLD, brow=HOLD, lid=HOLD, smile=HOLD, mouth=HOLD)),
    (b0("newgreet") + 3.0, dict(tear=0.6, brow=-0.55, lid=0.9, smile=0.2, mouth=0.0), "io"),
    (b0("okay") - 0.4, dict(lid=HOLD, smile=HOLD, tear=HOLD)),
    (b0("okay") + 0.1, dict(lid=0.0, smile=0.25, tear=0.85), "io"),
    (b1("okay") + 0.2, dict(lid=HOLD, smile=HOLD)),
    (b1("okay") + 0.9, dict(lid=0.7, smile=0.5), "io"),
    (b0("hungup") + 0.2, dict(ph=HOLD, gy=HOLD, head_pitch=HOLD)),
    (b0("hungup") + 1.0, dict(ph=1.0, gy=-0.55, head_pitch=14.0), "io"),
    (b0("incoming") + 0.05, dict(lid=HOLD, brow=HOLD, mouth=HOLD, smile=HOLD)),
    (b0("incoming") + 0.3, dict(lid=1.12, brow=0.45, mouth=0.16, smile=0.0), "out"),
    (b0("last") + 0.3, dict(ph=HOLD, smile=HOLD, lid=HOLD, brow=HOLD, mouth=HOLD, head_pitch=HOLD, gy=HOLD, head_roll=HOLD)),
    (b0("last") + 1.1, dict(ph=0.0, smile=0.6, lid=0.75, brow=-0.1, mouth=0.0, head_pitch=5.0, gy=-0.15, head_roll=8.0), "io"),
])
MS_BL = A.blinks(0, TOTAL, 3.4, 1)

# Maya on the sofa (typing her message) and in the kitchen
MSOFA = Track([
    (0.0, dict(ph2=0.0, lid=0.85, brow=-0.5, smile=0.0, gy=-0.6, gx=0.0, head_pitch=18.0, head_yaw=0.0, tear=0.0, mouth=0.0)),
    (b0("typed") + 0.2, dict(ph2=HOLD)),
    (b0("typed") + 0.4, dict(ph2=1.0), "io"),
    (b1("typed") - 0.2, dict(ph2=HOLD)),
    (b1("typed") + 0.2, dict(ph2=0.0), "io"),
    (b0("msg") + 2.8, dict(lid=HOLD, tear=HOLD, gy=HOLD, head_pitch=HOLD)),
    (b0("msg") + 3.6, dict(lid=0.7, tear=0.45, gy=-0.4, head_pitch=12.0), "io"),
    (b0("dont") + 0.8, dict(lid=HOLD, brow=HOLD, smile=HOLD, mouth=HOLD, tear=HOLD)),
    (b0("dont") + 1.6, dict(lid=1.0, brow=-0.15, smile=0.22, mouth=0.06, tear=0.3), "io"),
])
MKIT = Track([
    (0.0, dict(ph=3.0, lid=0.8, brow=-0.2, smile=0.0, gy=-0.3, gx=0.0, head_pitch=8.0, head_yaw=0.0, mouth=0.0)),
    (b0("next") + 1.4, dict(gx=HOLD, gy=HOLD, head_pitch=HOLD, head_yaw=HOLD, lid=HOLD)),
    (b0("next") + 1.6, dict(gx=-0.3, gy=-0.6, lid=1.0), "snap"),
    (b0("next") + 1.9, dict(head_pitch=16.0, head_yaw=-12.0), "out"),
    (b0("wasnt") - 0.1, dict(ph=HOLD)),
    (b0("wasnt") + 0.6, dict(ph=1.0), "io"),
    (b0("wasnt") + 1.2, dict(ph=HOLD, head_pitch=HOLD, smile=HOLD, gy=HOLD)),
    (b0("wasnt") + 1.9, dict(ph=0.0, head_pitch=4.0, smile=0.12, gy=-0.1), "io"),
])
MAYA_PH_ON = lambda T: (b0("hungup") + 1.3 <= T)      # noqa: E731   the screen lights up in her hand (DAD calling)

# Theo at the desk / on the bed
TD = Track([
    (0.0, dict(ph=1.0, ph2=0.0, lid=0.92, brow=-0.15, smile=0.0, mouth=0.0, gy=-0.55, gx=0.0, head_pitch=20.0, head_yaw=0.0, head_roll=0.0, lean=10.0)),
    (b0("weeks") - 0.2, dict(brow=HOLD, head_roll=HOLD)),
    (b0("weeks") + 0.4, dict(brow=-0.4, head_roll=-6.0), "io"),
    (b0("who") + 0.2, dict(ph2=HOLD)),
    (b0("who") + 0.4, dict(ph2=1.0), "io"),
    (b1("who") - 0.3, dict(ph2=HOLD)),
    (b1("who"), dict(ph2=0.0), "io"),
    (b0("dots") - 0.9, dict(brow=HOLD, lid=HOLD, mouth=HOLD, head_roll=HOLD)),
    (b0("dots") - 0.2, dict(brow=-0.55, lid=1.0, mouth=0.06, head_roll=0.0), "io"),
    # picks up her call
    (b0("wasnt") + 1.5, dict(ph=HOLD, head_pitch=HOLD, gy=HOLD, smile=HOLD, lean=HOLD)),
    (b0("wasnt") + 2.1, dict(ph=0.0, head_pitch=4.0, gy=-0.1, smile=0.15, lean=4.0), "io"),
    (b0("homework") - 0.2, dict(gx=HOLD, lid=HOLD)),
    (b0("homework") + 0.3, dict(gx=0.5, lid=0.9), "io"),
    (b0("homework") + 2.4, dict(smile=HOLD, brow=HOLD, head_roll=HOLD, gx=HOLD)),
    (b0("homework") + 2.8, dict(smile=0.85, brow=0.35, head_roll=-8.0, gx=0.0), "out"),
    (b0("homework") + 4.6, dict(smile=HOLD, brow=HOLD, head_roll=HOLD, lid=HOLD)),
    (b0("homework") + 5.2, dict(smile=0.12, brow=-0.05, head_roll=-2.0, lid=0.72), "io"),
    (b0("homework") + 6.5, dict(lid=HOLD, brow=HOLD, smile=HOLD, head_pitch=HOLD, gy=HOLD)),
    (b0("sound") - 0.6, dict(lid=0.85, brow=-0.25, smile=0.0, head_pitch=8.0, gy=-0.25)),
    # the recording (a flashback): phone up near his mouth, nervous half-smile
    (b0("thursday"), dict(ph=HOLD, smile=HOLD, lid=HOLD, brow=HOLD, gy=HOLD, head_pitch=HOLD, lean=HOLD)),
    (b0("newgreet") - 0.1, dict(ph=1.0, smile=0.25, lid=0.82, brow=-0.2, gy=-0.4, head_pitch=12.0, lean=8.0)),
])
TD_BL = A.blinks(0, TOTAL, 3.0, 2)
TB = Track([(0.0, dict(lid=0.92, brow=-0.45, smile=0.15, mouth=0.0, gy=-0.1, gx=0.0, head_pitch=8.0, head_yaw=0.0, lean=12.0)),
            (b1("rang") - 0.6, dict(smile=HOLD)), (b1("rang"), dict(smile=0.3), "io")])
FK = Track([(0.0, dict(smile=0.85, lid=0.55, brow=0.25, mouth=0.0, gy=-0.1, head_pitch=-6.0, head_roll=6.0, head_yaw=0.0))])
FPHOTO = Track([(0.0, dict(smile=0.95, lid=0.55, brow=0.25, mouth=0.18, gy=0.0, head_pitch=-2.0, head_roll=6.0))])


def frank_photo(T):
    p = dict(rig.REST, x=0.0, z=2.25, yaw=0.0, aR=(8.0, 8.0, 20.0), aL=(8.0, 8.0, 20.0), t=T)
    p.update(FPHOTO(T))
    return [("frank", "frank", p, None)]


def laugh_mouth(T, t0, t1):
    """A silent laugh/talk flap for montage beats without a voice line."""
    return 0.0 if not (t0 <= T < t1) else 0.12 + 0.12 * abs(math.sin((T - t0) * 9.0))


def theo_talk(T):
    cast = A.theo_desk(T, TD, TD_BL, side="R")
    p = cast[0][2]
    for a, b in ((b0("homework") + 0.4, b0("homework") + 2.2), (b0("homework") + 2.9, b0("homework") + 4.5)):
        p["mouth"] = max(p.get("mouth", 0.0), laugh_mouth(T, a, b))
    return cast


def frank_mem(T):
    cast = A.frank_kitch(T, FK, A.blinks(0, TOTAL, 3.0, 4))
    cast[0][2]["mouth"] = max(cast[0][2].get("mouth", 0.0), laugh_mouth(T, b0("callback") + 0.2, b1("callback")))
    return cast


HM = rig.solve("maya", A.maya_seat(5.0, MS, [])[0][2])["head"]
HK = rig.solve("maya", A.maya_kitch(53.0, MKIT, [])[0][2])["head"]
HT = rig.solve("theo", A.theo_desk(31.0, TD, [])[0][2])["head"]
HTB = rig.solve("theo", A.theo_bed(103.0, TB, [])[0][2])["head"]
HF = rig.solve("frank", A.frank_kitch(85.0, FK, [])[0][2])["head"]
HFP = rig.solve("frank", frank_photo(9.0)[0][2])["head"]


def seat_cast(T):
    on = (MAYA_PH_ON(T) and T < b0("last") + 0.9) if b0("hungup") <= T < b0("last") + 0.9 else None
    return A.maya_seat(T, MS, MS_BL, phone_on=on, held=not (b0("drop") + 0.25 <= T < b0("loud") - 0.5))


def drop_props(T):
    """Her phone falls out of her hand onto the cushion and lies there, still lit."""
    t0 = b0("drop") + 0.25
    if T < t0 or T > b0("loud") - 0.5:
        return []
    J = rig.solve("maya", A.maya_seat(t0, MS, [])[0][2])
    hx, hy, hz = J["wr_L"]
    u = min(1.0, (T - t0) / 0.32)
    land = (0.42, 0.495, 2.62)
    y = hy + (land[1] - hy) * u * u
    bounce = 0.02 * math.sin(min(1.0, max(0.0, (T - t0 - 0.32) / 0.25)) * math.pi)
    return [("phone", (hx + (land[0] - hx) * u, y + bounce, hz + (land[2] - hz) * u), 1.0)]


def counter_props(T):
    if T >= b0("wasnt") + 0.15:
        return []
    lit = 1.0 if T >= b0("next") + 1.5 else 0.0
    buzz = 0.006 * math.sin(T * 70) if b0("next") + 1.5 <= T < b0("next") + 3.0 else 0.0
    return [("phone", (1.62 + buzz, 0.925, 0.42), lit)]


def desk_phone_props(T):
    ring = b0("rang") <= T < b1("rang") + 0.8
    buzz = 0.005 * math.sin(T * 70) if ring and (T * 1.2) % 1.0 < 0.55 else 0.0
    return [("phone", (1.55 + buzz, 0.745, 1.35), 1.0 if ring else 0.0)]


# ======================================================================================================== shots
def world_shot(world, camf, castf, phone=0.0, props=None, laptop=1.0, post=None):
    def fn(fr, T, t0, t1):
        cam = camf(T, t0, t1)
        world.props = props(T) if props else []
        cast = castf(T) if castf else []
        kw = dict(phone=phone(T) if callable(phone) else phone)
        if world is ROOM:
            kw["laptop"] = laptop
        outs = world.draw(fr, cam, T, cast, **kw)
        if post:
            post(fr, T, t0, t1)
        return cam, cast, outs
    return fn


def ui_shot(base, draw_ui, dim=0.62):
    """A phone screen insert over a darkened view of the room it is in."""
    def fn(fr, T, t0, t1):
        cam, cast, outs = base(fr, T, t0, t1)
        fr.c.drawRect(skia.Rect(-10, -10, W + 10, H + 10), paint("#05070f", a=dim))
        draw_ui(fr, T, t0, t1)
        return cam, [], {}
    return fn


def split(top, bottom):
    """Two shots stacked: the top and bottom halves of the frame, each the centre band of its own render."""
    def fn(fr, T, t0, t1):
        a, b = Frame(fr.scale), Frame(fr.scale)
        top(a, T, t0, t1)
        bottom(b, T, t0, t1)
        A1, B1 = a.array(), b.array()
        h = A1.shape[0]
        out = np.concatenate([A1[h // 4: h // 4 + h // 2], B1[h // 4: h // 4 + h // 2]], axis=0)
        return out
    return fn


def memory_post(fr, T, t0, t1):
    """A warm, soft-edged memory: a low warm wash and a vignette."""
    fr.c.drawRect(skia.Rect(-10, -10, W + 10, H + 10), paint("#ffb36b", a=0.08, blend="add"))
    fr.c.drawRect(skia.Rect(-10, -10, W + 10, H + 10), paint(shader=rad((W / 2, H * 0.45), H * 0.62, [argb("#000000", 0), argb("#160903", 0.7)], [0.45, 1])))


def photo_post(fr, T, t0, t1):
    memory_post(fr, T, t0, t1)
    c = fr.c
    m = 70
    border = skia.Path()
    border.addRect(skia.Rect(-10, -10, W + 10, H + 10))
    border.addRect(skia.Rect(m, m + 180, W - m, H - m - 260))
    border.setFillType(skia.PathFillType.kEvenOdd)
    c.drawPath(border, paint("#f3ece0"))
    c.drawRect(skia.Rect(m, m + 180, W - m, H - m - 260), paint("#3a2a1e", stroke=3))


def recall_post(fr, T, t0, t1):
    """Theo recording, earlier: a cool desaturated look and soft edges, so it reads as a flashback."""
    q = paint("#8fa6c9", a=0.45)
    q.setBlendMode(skia.BlendMode.kColor)
    fr.c.drawRect(skia.Rect(-10, -10, W + 10, H + 10), q)
    fr.c.drawRect(skia.Rect(-10, -10, W + 10, H + 10), paint(shader=rad((W / 2, H * 0.45), H * 0.62, [argb("#000000", 0), argb("#05070f", 0.65)], [0.45, 1])))


NUMBER = "(555) 014-2290"
MSG = "This was my dad's number. He died last winter. I call to hear his voicemail. I'm sorry. I'll stop."


def typed(text, T, a, b):
    n = int(len(text) * min(1.0, max(0.0, (T - a) / max(1e-6, b - a))))
    return text[:n]


def ui_missed(fr, T, t0, t1):
    ui.missed_calls(fr, 21, NUMBER, "11:00 PM", scroll=max(0.0, (T - t0 - 0.8)) * 380)


def ui_who(fr, T, t0, t1):
    s = typed("who is this?", T, t0 + 0.2, t0 + 1.6)
    ui.thread(fr, NUMBER, [(s, True)] if s else [], t=T)


def ui_msg(fr, T, t0, t1):
    s = typed(MSG, T, b0("msg") - 0.2, b1("msg") - 0.3)
    ui.thread(fr, "Dad", [("who is this?", False)] + ([(s, True)] if s else []), t=T)


def ui_dots(fr, T, t0, t1):
    on = 1.0 if (T - b0("dots")) % 1.25 < 0.8 and T > b0("dots") + 0.2 else 0.0
    ui.thread(fr, "Dad", [("who is this?", False), (MSG, True)], typing=on, t=T)


def ui_dont(fr, T, t0, t1):
    ui.thread(fr, "Dad", [("who is this?", False), (MSG, True), ("you don't have to stop", False)], t=T)


def ui_ok(fr, T, t0, t1):
    u = min(1.0, max(0.0, (T - t0) / 0.35))
    ui.lock_screen(fr, "11:00", "Wednesday, March 6", ("Dad", "it's 11. you ok?", u), t=T, buzz=1.0 if T - t0 < 0.6 else 0.0)


def ui_call(name, sub, incoming=False):
    def f(fr, T, t0, t1):
        ui.call_screen(fr, name, sub, T, incoming=incoming, initial="D" if name.upper() == "DAD" else name[:1])
    return f


def ui_anniv(fr, T, t0, t1):
    ui.lock_screen(fr, "11:00", "Thursday, March 14", None, t=T)


def ui_rec(fr, T, t0, t1):
    ui.recording(fr, T, T - b0("newgreet") + 1.0)


flat = lambda camf, **kw: world_shot(FLAT, camf, seat_cast, **kw)                        # noqa: E731
room_desk = lambda camf, castf=None, **kw: world_shot(ROOM, camf, castf or (lambda T: A.theo_desk(T, TD, TD_BL, side="R")), **kw)  # noqa: E731
sofa = lambda camf: world_shot(FLAT, camf, lambda T: A.maya_sofa(T, MSOFA, MS_BL), phone=0.8)        # noqa: E731
kitch = lambda camf: world_shot(FLAT, camf, lambda T: A.maya_kitch(T, MKIT, MS_BL, held=T >= b0("wasnt") + 0.15, phone_on=T < b0("wasnt") + 1.0),
                                props=counter_props)                                                     # noqa: E731
OUTS = K((0.55, 1.35, 4.6), HM, 1500)

SHOTS = [
    # name, start, end, draw fn, opts (cap = (y, size))
    ("HOOK", 0.0, b0("dead") - 0.35, flat(track(K((0.7, 2.25, 1.1), (0.15, 2.25, 3.0), 1500, 0.50), K((0.8, 1.32, 1.62), HM, 2000, 0.44), "smooth")), dict(cap=(1800, 62))),
    ("CALLSCR", b0("dead") - 0.35, b0("greet") - 0.05, ui_shot(flat(track(K((0.9, 1.3, 1.6), HM, 1900), K((0.9, 1.3, 1.6), HM, 1950))), ui_call("Dad", "calling...")), dict(cap=(1830, 62))),
    ("LISTEN", b0("greet") - 0.05, b0("greet") + 1.8, flat(track(K((0.78, 1.33, 1.75), HM, 2300, 0.43), K((0.74, 1.33, 1.8), HM, 2550, 0.43), "lin")), {}),
    ("PHOTO", b0("greet") + 1.8, b0("never") - 0.1, world_shot(MEM, track(K((0.0, 1.6, 0.85), HFP, 1800, 0.40), K((0.0, 1.6, 0.92), HFP, 1900, 0.40), "lin"),
                                                                 frank_photo, post=photo_post), dict(cap=(1700, 62))),
    ("HANGUP", b0("never") - 0.1, b1("never") + 0.7, flat(track(K((1.0, 1.2, 1.05), (0.12, 0.95, 2.65), 1500, 0.46), K((0.92, 1.2, 1.15), (0.12, 0.95, 2.65), 1600, 0.46))), {}),
    ("NIGHT2", b1("never") + 0.7, b0("hello") - 0.45, flat(track(K((0.82, 1.3, 1.6), HM, 2000), K((0.8, 1.3, 1.64), HM, 2150), "lin")), {}),
    ("HELLO", b0("hello") - 0.45, b0("drop") - 0.05, flat(track(K((0.6, 1.28, 1.8), HM, 2500, 0.43), K((0.58, 1.28, 1.83), HM, 2650, 0.43), "lin")), dict(cap=(1800, 62))),
    ("DROP", b0("drop") - 0.05, b0("across") - 0.4, flat(track(K((0.42, 1.62, 1.3), (0.3, 0.62, 2.62), 1550, 0.30), K((0.4, 1.6, 1.36), (0.3, 0.62, 2.62), 1650, 0.30)), props=drop_props), {}),
    ("THEO_IN", b0("across") - 0.4, b0("missed") - 0.05, room_desk(track(K((-1.3, 1.3, -0.8), (1.1, 0.95, 2.0), 1200, 0.48), K((-0.95, 1.28, -0.35), (1.1, 0.95, 2.0), 1350, 0.48)), phone=1.0), {}),
    ("MISSED", b0("missed") - 0.05, b1("missed") + 0.1, ui_shot(room_desk(track(K((1.9, 1.32, 0.55), HT, 2000), K((1.9, 1.32, 0.55), HT, 2000))), ui_missed), dict(cap=(1830, 62))),
    ("THEO_CU", b1("missed") + 0.1, b0("who") - 0.05, room_desk(track(K((1.9, 1.32, 0.55), HT, 2000, 0.42), K((1.86, 1.32, 0.6), HT, 2250, 0.42), "lin"), phone=1.0), dict(cap=(1800, 60))),
    ("WHO_UI", b0("who") - 0.05, b0("typed") - 0.3, ui_shot(room_desk(track(K((1.9, 1.32, 0.55), HT, 2000), K((1.9, 1.32, 0.55), HT, 2000))), ui_who), dict(cap=(1830, 62))),
    ("SOFA", b0("typed") - 0.3, b0("msg") - 0.2, sofa(track(K((-0.55, 1.25, 1.55), (-1.55, 0.95, 0.8), 1700, 0.45), K((-0.6, 1.25, 1.45), (-1.55, 0.95, 0.8), 1850, 0.45))), {}),
    ("MSG_UI", b0("msg") - 0.2, b0("msg") + 3.2, ui_shot(sofa(track(K((-0.55, 1.25, 1.55), (-1.55, 0.95, 0.8), 1850), K((-0.55, 1.25, 1.55), (-1.55, 0.95, 0.8), 1850))), ui_msg), dict(cap=(1830, 62))),
    ("MSG_FACE", b0("msg") + 3.2, b0("msg") + 4.9, sofa(track(K((-0.75, 1.3, 1.35), (-1.6, 1.22, 0.8), 1900, 0.42), K((-0.77, 1.3, 1.32), (-1.6, 1.22, 0.8), 2050, 0.42), "lin")), {}),
    ("MSG_UI2", b0("msg") + 4.9, b1("msg") + 0.55, ui_shot(sofa(track(K((-0.55, 1.25, 1.55), (-1.55, 0.95, 0.8), 1850), K((-0.55, 1.25, 1.55), (-1.55, 0.95, 0.8), 1850))), ui_msg), dict(cap=(1830, 62))),
    ("THEO_READ", b1("msg") + 0.55, b0("dots") + 1.0, room_desk(track(K((1.86, 1.3, 0.7), HT, 2300, 0.42), K((1.84, 1.3, 0.74), HT, 2500, 0.42), "lin"), phone=1.0), {}),
    ("DOTS_UI", b0("dots") + 1.0, b0("dont") + 0.05, ui_shot(sofa(track(K((-0.55, 1.25, 1.55), (-1.55, 0.95, 0.8), 1850), K((-0.55, 1.25, 1.55), (-1.55, 0.95, 0.8), 1850))), ui_dots), dict(cap=(1830, 62))),
    ("DONT_UI", b0("dont") + 0.05, b0("dont") + 1.6, ui_shot(sofa(track(K((-0.55, 1.25, 1.55), (-1.55, 0.95, 0.8), 1850), K((-0.55, 1.25, 1.55), (-1.55, 0.95, 0.8), 1850))), ui_dont), {}),
    ("DONT_FACE", b0("dont") + 1.6, b0("next") - 0.5, sofa(track(K((-0.75, 1.3, 1.35), (-1.6, 1.22, 0.8), 1900, 0.42), K((-0.79, 1.3, 1.3), (-1.6, 1.22, 0.8), 2100, 0.42), "lin")), {}),
    ("KITCHEN", b0("next") - 0.5, b0("next") + 1.9, kitch(track(K((1.38, 1.45, -0.75), (1.1, 1.05, 0.55), 1350, 0.45), K((1.38, 1.43, -0.6), (1.1, 1.05, 0.55), 1450, 0.45))), {}),
    ("BUZZ", b0("next") + 1.9, b0("ok") - 0.05, kitch(track(K((1.3, 1.32, 0.05), (1.62, 0.93, 0.42), 2000, 0.22), K((1.32, 1.3, 0.1), (1.62, 0.93, 0.42), 2200, 0.22), "lin")), {}),
    ("OK_UI", b0("ok") - 0.05, b0("wasnt") + 0.1, ui_shot(kitch(track(K((1.38, 1.45, -0.6), (1.1, 1.05, 0.55), 1450), K((1.38, 1.45, -0.6), (1.1, 1.05, 0.55), 1450))), ui_ok), dict(cap=(1830, 62))),
    ("CALLS", b0("wasnt") + 0.1, b0("wasnt") + 1.5, kitch(track(K((1.38, 1.45, -0.35), HK, 1800, 0.43), K((1.38, 1.45, -0.28), HK, 1950, 0.43), "lin")), {}),
    ("PICKUP", b0("wasnt") + 1.5, b0("loud") - 0.2, room_desk(track(K((1.9, 1.32, 0.6), HT, 2000, 0.42), K((1.88, 1.32, 0.64), HT, 2150, 0.42), "lin"), phone=0.0), {}),
    ("THEO_WIDE", b0("loud") - 0.2, b0("loud") + 2.9, room_desk(track(K((0.0, 1.75, -1.4), (0.6, 0.9, 2.2), 1000, 0.40), K((0.05, 1.72, -1.2), (0.6, 0.9, 2.2), 1050, 0.40), "lin"), phone=0.0), {}),
    ("FLAT_WIDE", b0("loud") + 2.9, b0("homework") - 0.1, flat(track(K((-1.65, 1.75, -2.2), (0.1, 1.0, 2.7), 1050, 0.42), K((-1.5, 1.72, -1.9), (0.1, 1.0, 2.7), 1120, 0.42), "lin")), {}),
    ("HOMEWORK", b0("homework") - 0.1, b0("homework") + 2.5, room_desk(track(K((1.85, 1.25, 0.8), HT, 1800, 0.44), K((1.84, 1.25, 0.84), HT, 1900, 0.44), "lin"), castf=theo_talk), {}),
    ("JOKE", b0("homework") + 2.5, b0("homework") + 4.6, room_desk(track(K((1.78, 1.34, 0.9), HT, 2300, 0.42), K((1.77, 1.34, 0.93), HT, 2450, 0.42), "lin"), castf=theo_talk), {}),
    ("SPLIT", b0("homework") + 4.6, b0("laughed") - 0.1, split(flat(track(K((0.62, 1.3, 1.65), HM, 1900, 0.5), K((0.6, 1.3, 1.69), HM, 2000, 0.5), "lin")),
                                                              room_desk(track(K((1.9, 1.3, 0.6), HT, 1900, 0.5), K((1.88, 1.3, 0.64), HT, 2000, 0.5), "lin"))), dict(cap=(1000, 58))),
    ("LAUGH", b0("laughed") - 0.1, b0("told") - 0.3, flat(track(K((0.5, 1.25, 1.78), HM, 2100, 0.44), K((0.48, 1.25, 1.82), HM, 2300, 0.44), "lin")), {}),
    ("TOLD", b0("told") - 0.3, b0("callback") - 0.1, flat(track(K((0.6, 1.3, 1.72), HM, 2000, 0.44), K((0.58, 1.3, 1.78), HM, 2150, 0.44), "lin")), {}),
    ("MEMORY", b0("callback") - 0.1, b1("callback") + 0.6, world_shot(MEM, track(K((1.4, 1.55, -0.6), HF, 1500, 0.44), K((1.4, 1.55, -0.5), HF, 1600, 0.44), "lin"),
                                                                        frank_mem, post=memory_post), {}),
    ("SOUND", b1("callback") + 0.6, b0("smiling") - 0.2, room_desk(track(K((1.86, 1.3, 0.75), HT, 2400, 0.42), K((1.85, 1.3, 0.78), HT, 2550, 0.42), "lin"), phone=0.0), {}),
    ("SMILING", b0("smiling") - 0.2, b0("thursday") - 0.4, flat(track(K((0.62, 1.3, 1.75), HM, 2500, 0.43), K((0.6, 1.3, 1.8), HM, 2700, 0.43), "lin")), {}),
    ("ANNIV", b0("thursday") - 0.4, b0("goodbye") - 0.1, ui_shot(flat(track(K((-1.65, 1.75, -2.2), (0.1, 1.0, 2.7), 1050), K((-1.65, 1.75, -2.2), (0.1, 1.0, 2.7), 1050))), ui_anniv, dim=0.5), dict(cap=(1830, 62))),
    ("GOODBYE", b0("goodbye") - 0.1, b0("goodbye") + 4.4, flat(track(K((0.95, 1.35, 1.55), (0.25, 1.05, 2.7), 1650, 0.44), K((0.9, 1.35, 1.62), (0.25, 1.05, 2.7), 1800, 0.44)), phone=1.0), {}),
    ("CALL2", b0("goodbye") + 4.4, b0("rang") + 0.2, ui_shot(flat(track(K((0.9, 1.3, 1.6), HM, 1900), K((0.9, 1.3, 1.6), HM, 1900))), ui_call("Dad", "calling...")), dict(cap=(1830, 62))),
    ("RANG_T", b0("rang") + 0.2, b0("rang") + 2.4, world_shot(ROOM, track(K((0.75, 1.2, 0.2), HTB, 1500, 0.46), K((0.7, 1.2, 0.28), HTB, 1600, 0.46), "lin"),
                                                              lambda T: A.theo_bed(T, TB, TD_BL), props=desk_phone_props), {}),
    ("WAIT", b0("rang") + 2.4, b0("voice") - 0.1, flat(track(K((0.8, 1.3, 1.6), HM, 2200), K((0.78, 1.3, 1.64), HM, 2350), "lin")), {}),
    ("VOICE", b0("voice") - 0.1, b0("newgreet") + 0.4, flat(track(K((0.72, 1.28, 1.75), HM, 2400, 0.43), K((0.7, 1.28, 1.8), HM, 2850, 0.43))), {}),
    ("RECORD", b0("newgreet") + 0.4, b0("newgreet") + 2.6, room_desk(track(K((1.85, 1.28, 0.8), HT, 2200, 0.42), K((1.84, 1.28, 0.84), HT, 2350, 0.42), "lin"), phone=1.0, post=recall_post), dict(cap=(1800, 60))),
    ("REC_UI", b0("newgreet") + 2.6, b0("newgreet") + 3.7, ui_shot(room_desk(track(K((1.85, 1.28, 0.8), HT, 2200), K((1.85, 1.28, 0.8), HT, 2200)), post=recall_post), ui_rec), dict(cap=(1830, 62))),
    ("LISTEN2", b0("newgreet") + 3.7, b0("beep") - 0.2, flat(track(K((0.56, 1.3, 1.8), HM, 2400, 0.43), K((0.54, 1.3, 1.84), HM, 2600, 0.43), "lin")), {}),
    ("BEEP", b0("beep") - 0.2, b0("okay") - 0.3, flat(track(K((-0.3, 1.4, 4.5), HM, 1500, 0.45), K((-0.22, 1.37, 4.0), HM, 1750, 0.45))), {}),
    ("OKAY", b0("okay") - 0.3, b0("hungup") + 0.1, flat(track(K((0.7, 1.29, 1.8), HM, 2600, 0.43), K((0.68, 1.29, 1.84), HM, 2850, 0.43), "lin")), {}),
    ("HUNGUP2", b0("hungup") + 0.1, b0("incoming") - 0.05, flat(track(K((0.78, 1.15, 1.5), (0.12, 0.98, 2.65), 1700, 0.46), K((0.74, 1.15, 1.56), (0.12, 0.98, 2.65), 1850, 0.46), "lin"),
                                                               phone=lambda T: 1.0 if MAYA_PH_ON(T) else 0.0), {}),
    ("INCOMING", b0("incoming") - 0.05, b0("last") - 0.1, ui_shot(flat(track(K((0.78, 1.15, 1.5), (0.12, 0.98, 2.65), 1850), K((0.78, 1.15, 1.5), (0.12, 0.98, 2.65), 1850))),
                                                                  ui_call("DAD", "incoming call", incoming=True)), dict(cap=(1830, 62))),
    ("ANSWER", b0("last") - 0.1, b0("last") + 2.2, flat(track(K((0.62, 1.3, 1.78), HM, 2300, 0.43), K((0.6, 1.3, 1.82), HM, 2450, 0.43), "lin")), dict(cap=(1800, 60))),
    ("PULLOUT", b0("last") + 2.2, TOTAL, flat(track(K((0.35, 1.38, 4.1), HM, 1700, 0.45), K((0.4, 2.2, 10.0), HM, 1250, 0.45), "io")), {}),
]


def shot_at(T):
    for s in SHOTS:
        if s[1] <= T < s[2]:
            return s
    return SHOTS[-1]


# ---- text --------------------------------------------------------------------------------------------------------
CHUNKS = sorted([c for L in TL["lines"] for c in L["chunks"]], key=lambda c: c["t0"])
CAP_Y, CAP_SIZE = 1620, 64
TF = TN.typeface()


def caption(T):
    cur = None
    for c in CHUNKS:
        if c["t0"] <= T + 1e-6:
            cur = c
    return cur["text"] if cur and T < cur["t1"] + 0.35 else None


def caption_box(text, y, size):
    w = skia.Font(TF, size).measureText(text.replace("[", "").replace("]", "")) + 16
    return ((W - w) / 2, y - size * 0.73, (W + w) / 2, y + size * 0.33)


def draw_caption(fr, text, y, size):
    f = skia.Font(TF, size)
    parts = [(b.strip("[]"), b.startswith("[")) for b in text.replace("[", "|[").replace("]", "]|").split("|") if b]
    x = (W - sum(f.measureText(p) for p, _ in parts)) / 2
    for p, key in parts:
        blob = skia.TextBlob(p, f)
        fr.c.drawTextBlob(blob, x, y, paint("#000000", stroke=size * 0.18))
        fr.c.drawTextBlob(blob, x, y, paint("#FF4D4D" if key else "#F4F1EA"))
        x += f.measureText(p)


def draw_titles(fr, T):
    if 0.25 <= T < 3.2:                                                       # the label over the hook
        a = min(1.0, (T - 0.25) / 0.3, (3.2 - T) / 0.3)
        f = skia.Font(TF, 36)
        x = (W - f.measureText(TL["label"])) / 2
        fr.c.drawTextBlob(skia.TextBlob(TL["label"], f), x, 300, paint("#000000", a=a, stroke=7))
        fr.c.drawTextBlob(skia.TextBlob(TL["label"], f), x, 300, paint("#E8E8E8", a=a))
    t0 = b1("last") + 0.6                                                     # the title over the pull-out
    if T >= t0:
        a = min(1.0, (T - t0) / 0.8)
        f = skia.Font(TN.typeface(True), 76)
        x = (W - f.measureText(TL["title"])) / 2
        fr.c.drawTextBlob(skia.TextBlob(TL["title"], f), x, 900, paint("#000000", a=a * 0.6, stroke=10))
        fr.c.drawTextBlob(skia.TextBlob(TL["title"], f), x, 900, paint("#F4F1EA", a=a))


# ---- frames ------------------------------------------------------------------------------------------------------
def render(T, scale=1.0, captions=True, log=None):
    name, t0, t1, fn, opt = shot_at(T)
    fr = Frame(scale)
    fr.scale = scale
    res = fn(fr, T, t0, t1)
    if isinstance(res, np.ndarray):                                            # a composite (split screen): draw text on top of it
        fr = Frame(scale)
        fr.scale = scale
        img = skia.Image.fromarray(np.ascontiguousarray(np.dstack([res, np.full(res.shape[:2], 255, np.uint8)])), colorType=skia.kRGBA_8888_ColorType)
        fr.c.save()
        fr.c.resetMatrix()
        fr.c.drawImage(img, 0, 0)
        fr.c.restore()
        res = None
    if log is not None and res:
        cam, cast, outs = res
        for pid, look, pose, held in cast:
            log.append(dict(t=T, shot=name, pid=pid, pose=pose, o=outs.get(pid, {}), J=rig.solve(look, pose), cam=cam))
    draw_titles(fr, T)
    if captions:
        c = caption(T)
        if c:
            draw_caption(fr, c, *opt.get("cap", (CAP_Y, CAP_SIZE)))
    a = fr.array()
    k = min(1.0, max(0.0, (TOTAL - T) / 1.2), max(0.0, T / 0.25))              # fade in from black (a breath) and out at the end
    if k < 1.0:
        a = (a.astype(np.float32) * k).astype(np.uint8)
    return name, a


def frames_of(a, b):
    return [i / FPS for i in range(int(round(a * FPS)), int(round(b * FPS)))]


# ---- checks ------------------------------------------------------------------------------------------------------
def _angle(a, b):
    return math.degrees(math.acos(max(-1.0, min(1.0, rig.dot(rig.norm(a), rig.norm(b))))))


def check():
    log = []
    for name, a, b, _, _ in SHOTS:
        for t in frames_of(a, b):
            render(t, 0.25, log=log)
        print("checked", name, flush=True)
    hits = {}

    def hit(shot, pid, what, t, msg):
        h = hits.setdefault((shot, pid, what), [t, t, msg])
        h[0], h[1] = min(h[0], t), max(h[1], t)

    prev = {}
    for r in log:
        J, t, shot, pid, o = r["J"], r["t"], r["shot"], r["pid"], r["o"]
        if o.get("culled"):
            vx, _, vz = r["cam"].view(J["pelvis"])
            if vz > 0.05 and abs(vx) < 540 / r["cam"].f * vz + 0.3:
                hit(shot, pid, "culled", t, "closer than 0.45 m to the lens and in view, so not drawn")
            continue
        floor = r["pose"].get("floor", 0.0)
        for s in "RL":
            for k in ("arm_" + s, "leg_" + s):
                if J["err"].get(k, 0) > 0.02:
                    hit(shot, pid, "reach short " + k, t, f"{k} target {J['err'][k] * 100:.0f} cm out of reach")
            if r["pose"].get("plant", "both") != "none":
                ay = J["ank_" + s][1] - floor - 0.035 * J["h"]
                if ay < -0.003:
                    hit(shot, pid, "foot sinks " + s, t, f"ankle_{s} {ay * 1000:.0f} mm into the floor")
            up, fo = rig.sub(J["el_" + s], J["sh_" + s]), rig.sub(J["wr_" + s], J["el_" + s])
            if _angle(up, fo) > 155:
                hit(shot, pid, "elbow over-bent " + s, t, f"elbow_{s} {_angle(up, fo):.0f} deg")
            P = prev.get((shot, pid))
            if P is not None:
                for lab, a1, b1_, a0, b0_ in (("elbow", up, fo, rig.sub(P["el_" + s], P["sh_" + s]), rig.sub(P["wr_" + s], P["el_" + s])),
                                              ("knee", rig.sub(J["kn_" + s], J["hip_" + s]), rig.sub(J["ank_" + s], J["kn_" + s]),
                                               rig.sub(P["kn_" + s], P["hip_" + s]), rig.sub(P["ank_" + s], P["kn_" + s]))):
                    if _angle(a1, b1_) > 12 and _angle(a0, b0_) > 12 and rig.dot(rig.cross(a1, b1_), rig.cross(a0, b0_)) < 0:
                        hit(shot, pid, f"{lab} flip {s}", t, f"{lab}_{s} bend plane flipped between frames")
                step = math.dist(P["pelvis"], J["pelvis"])
                if step > 0.12:
                    hit(shot, pid, "jump", t, f"pelvis moved {step * 100:.0f} cm in one frame")
        prev[(shot, pid)] = J
        c = caption(t)
        if c:
            opt = shot_at(t)[4]
            x0, y0, x1, y1 = caption_box(c, *opt.get("cap", (CAP_Y, CAP_SIZE)))
            for what, pt, rr in (("face", o.get("head"), o.get("head_r", 0)), ("hand_R", o.get("hand_R"), 30), ("hand_L", o.get("hand_L"), 30)):
                if pt and x0 - rr < pt[0] < x1 + rr and y0 - rr < pt[1] < y1 + rr and -50 < pt[0] < W + 50:
                    hit(shot, pid, "caption over " + what, t, f"'{c}' covers the {what}")
    rep = [f"ANOMALY {shot} {ta:.2f}-{tb:.2f}s {pid}: {what}: {msg}" for (shot, pid, what), (ta, tb, msg) in sorted(hits.items(), key=lambda kv: kv[1][0])]
    rep.append(f"{len(hits)} anomalies in {len(log)} person-frames. This is code only: now look at --stills and --sheet.")
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "reel_checks.txt"), "w", encoding="utf-8").write("\n".join(rep) + "\n")
    print("\n".join(rep))


# ---- sheets ------------------------------------------------------------------------------------------------------
def label(im, text):
    d = ImageDraw.Draw(im)
    d.rectangle((0, im.height - 22, im.width, im.height), fill=(0, 0, 0))
    d.text((6, im.height - 18), text, fill=(255, 255, 0))
    return im


def sheet(tiles, path, cols=6, gap=8):
    w, h = tiles[0].size
    rows = (len(tiles) + cols - 1) // cols
    im = Image.new("RGB", (cols * (w + gap) + gap, rows * (h + gap) + gap), (24, 24, 28))
    for i, t in enumerate(tiles):
        im.paste(t, (gap + (i % cols) * (w + gap), gap + (i // cols) * (h + gap)))
    os.makedirs(OUT, exist_ok=True)
    im.save(path)
    print(path)


def stills(names=None, out="shots.png"):
    tiles = []
    for name, a, b, _, _ in SHOTS:
        if names and name not in names:
            continue
        ts = frames_of(a, b)
        tiles += [label(Image.fromarray(render(t, 0.25)[1]), f"{name} {lab} {t:.2f}s") for lab, t in (("first", ts[0]), ("mid", ts[len(ts) // 2]), ("last", ts[-1]))]
    sheet(tiles, os.path.join(OUT, out), cols=9)


def sheets(names, step=1):
    for name, a, b, _, _ in SHOTS:
        if name in names:
            sheet([label(Image.fromarray(render(t, 0.2)[1]), f"{t:.2f}") for t in frames_of(a, b)[::step]], os.path.join(OUT, f"all_{name}.png"), cols=10)


# ---- video -------------------------------------------------------------------------------------------------------
def downsample(a, rng=np.random.default_rng(7)):
    h, w = a.shape[0] // 2, a.shape[1] // 2
    f = a.astype(np.float32).reshape(h, 2, w, 2, 3).mean((1, 3))
    f += rng.random(f.shape, dtype=np.float32) - rng.random(f.shape, dtype=np.float32)
    return np.clip(np.rint(f), 0, 255).astype(np.uint8)


def encode(frames, path, size, crf="16", preset="medium"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", size, "-r", str(FPS),
                          "-i", "-", "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
                          "-c:v", "libx264", "-crf", crf, "-preset", preset, "-tune", "animation",
                          "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv", path],
                         stdin=subprocess.PIPE)
    for a in frames:
        p.stdin.write(np.ascontiguousarray(a).tobytes())
    p.stdin.close()
    if p.wait():
        sys.exit("ffmpeg failed")


if __name__ == "__main__":
    a = sys.argv[1:]
    pos = [x for x in a if not x.startswith("--")]
    if "--frame" in a:
        t = float(pos[0])
        os.makedirs(OUT, exist_ok=True)
        Image.fromarray(render(t, float(pos[1]) if len(pos) > 1 else 0.5)[1]).save(os.path.join(OUT, f"_f{t:.2f}.png"))
        print(os.path.join(OUT, f"_f{t:.2f}.png"))
    elif "--stills" in a:
        stills(pos or None, "shots.png" if not pos else "shots_sel.png")
    elif "--sheet" in a:
        sheets(pos, step=2 if "--half" in a else 1)
    elif "--check" in a:
        check()
    elif "--preview" in a:
        full = "--full" in a
        encode((render(t, 1.0 if full else 0.5)[1] for t in frames_of(0, TOTAL)), os.path.join(OUT, "reel_preview.mp4"), "1080x1920" if full else "540x960")
        print(os.path.join(OUT, "reel_preview.mp4"))
    elif "--master-part" in a:
        k, n = int(pos[0]), int(pos[1])
        fr = frames_of(0, TOTAL)
        L = -(-len(fr) // n)
        TN.HQ["on"] = True
        encode((downsample(render(t, 2.0)[1]) for t in fr[k * L:(k + 1) * L]), os.path.join(VID, f"_part{k:02d}.mp4"), f"{W}x{H}", crf="10", preset="slow")
    elif "--master-par" in a:
        n = int(a[a.index("--master-par") + 1])
        os.makedirs(VID, exist_ok=True)
        procs = [subprocess.Popen([sys.executable, os.path.abspath(__file__), "--master-part", str(k), str(n)]) for k in range(n)]
        if any([p.wait() for p in procs]):
            sys.exit("a master part failed")
        lst = os.path.join(VID, "_parts.txt")
        open(lst, "w").write("".join(f"file '_part{k:02d}.mp4'\n" for k in range(n)))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", os.path.join(VID, "reel_silent.mp4")], check=True)
        for k in range(n):
            os.remove(os.path.join(VID, f"_part{k:02d}.mp4"))
        os.remove(lst)
        print(os.path.join(VID, "reel_silent.mp4"))
    else:
        print(__doc__)
