"""Acting for LEAVE A MESSAGE: the poses of each setup, the phone hand, and mouths driven by the voice takes.

Setups (stations):
    maya_seat   Maya on the window seat, facing into the room (yaw 0). Phone hand: left.
    maya_sofa   Maya on the sofa along the left wall, facing +x. Phone in both hands.
    maya_kitch  Maya standing at the kitchen counter, facing +x.
    theo_desk   Theo on his desk chair, facing the desk (yaw 75).
    theo_bed    Theo on the edge of his bed, facing +x.
    frank_kitch Frank (memory) at a kitchen counter, facing +x.

Phone positions are blended with a channel "ph": 0 = at the ear, 1 = held up in front (reading/typing), 2 = in the lap /
lowered, 3 = empty hand resting (the phone is elsewhere). Face channels are the rig's (lid, brow, smile, mouth, gx,
gy, head_yaw, head_pitch, head_roll, lean, twist) plus "tear" (0..1, a wet line under the eyes).
"""
import json
import math
import os

import numpy as np
import soundfile as sf

import rig
from anim import Track, blink
import sets as S

HERE = os.path.dirname(os.path.abspath(__file__))
TL = json.load(open(os.path.join(HERE, "timeline.json"), encoding="utf-8"))
B = TL["beats"]


def bt(bid, k="t0"):
    return B[bid][k]


# ---- mouths from the takes ------------------------------------------------------------------------------------
_ENV = {}


def _env(bid):
    if bid not in _ENV:
        p = os.path.join(HERE, "audio", "lines", bid + ".wav")
        if not os.path.exists(p):
            _ENV[bid] = None
        else:
            a, sr = sf.read(p, dtype="float32")
            hop = sr // 60
            n = len(a) // hop
            e = np.sqrt(np.mean(a[:n * hop].reshape(n, hop) ** 2, axis=1))
            e = e / max(1e-6, np.percentile(e, 95))
            _ENV[bid] = np.clip(e, 0, 1.2)
    return _ENV[bid]


def mouth(T, speaker, scale=0.34):
    """Mouth opening for a character at time T: follows the loudness of whichever of their lines is playing."""
    for bid, b in B.items():
        if b["speaker"] == speaker and b["t0"] <= T < b["t1"]:
            e = _env(bid)
            if e is None:
                return 0.15 + 0.12 * abs(math.sin((T - b["t0"]) * 11))
            i = int((T - b["t0"]) * 60)
            v = float(np.mean(e[max(0, i - 2):i + 3])) if i < len(e) else 0.0
            return scale * min(1.0, v) ** 0.8
    return 0.0


# ---- the phone hand -----------------------------------------------------------------------------------------------
def _lerp(a, b, u):
    return tuple(x + (y - x) * u for x, y in zip(a, b))


def phone_hand(p, look, ph, side, targets):
    """Blend the phone hand between ear / front / lap / rest. targets: dict of extra world targets by index."""
    J = rig.solve(look, dict(p))
    R, Bh, hd, Bb = J["R"], J["Bh"], J["head"], rig.Basis.yaw(p["yaw"])
    sg = 1 if side == "R" else -1                                       # +1 = their right
    ear = Bh.w(hd, sg * R * 0.98, -0.20 * R, 0.02 * R)
    pts = [ear, targets[1], targets[2], targets[3]]
    poles = [Bb.d(sg * 0.6, -0.15, 1.0), Bb.d(sg * 0.55, -1.0, -0.1), Bb.d(sg * 0.5, -1.0, -0.2), Bb.d(sg * 0.4, -1.0, 0.1)]
    i = max(0, min(2, int(ph)))
    u = max(0.0, min(1.0, ph - i))
    u = u * u * (3 - 2 * u)
    p["ik_" + side] = _lerp(pts[i], pts[i + 1], u)
    p["pole_" + side] = _lerp(poles[i], poles[i + 1], u)
    return p


def face(p, T, tr, speaker, blinks):
    v = tr(T)
    p.update({k: v[k] for k in v if k not in ("ph", "ph2")})
    if "gy" in p:
        p["gy"] = -p["gy"]                      # tracks use gy + = up; the rig's eye y grows downward
    m = mouth(T, speaker)
    if m > 0:
        p["mouth"] = max(p.get("mouth", 0.0), m)
    p["lid"] = p.get("lid", 1.0) * blink(T, blinks)
    p["t"] = T
    return p


def blinks(t0, t1, every=3.1, seed=0):
    r = np.random.default_rng(seed)
    out, t = [], t0 + r.uniform(0.4, 1.4)
    while t < t1:
        out.append(round(t, 2))
        t += every * r.uniform(0.6, 1.4)
    return out


# ---- stations ------------------------------------------------------------------------------------------------------
SEAT = (0.12, 2.70, 0.0)
SOFA = (-1.62, 0.80, 90.0)
KITCH = (1.02, 0.55, 90.0)
DESK = (0.92, 1.75, 75.0)
BED = (-1.10, 1.62, 90.0)


def maya_seat(T, tr, bl, phone_on=None, held=True):
    x, z, yaw = SEAT
    v = tr(T)
    p = S.seated("maya", x, z, yaw, 0.48, 0.36, breath=0.5 + 0.5 * math.sin(T * 1.7), aR=(28.0, 6.0, 64.0))
    p = face(p, T, tr, "MAYA", bl)
    Bb = rig.Basis.yaw(yaw)
    o = (x, 0, z)
    tg = {1: Bb.w(o, -0.03, 0.90, 0.34), 2: Bb.w(o, -0.06, 0.66, 0.24), 3: Bb.w(o, -0.10, 0.60, 0.20)}
    p = phone_hand(p, "maya", v.get("ph", 0.0), "L", tg)
    if v.get("ph", 0.0) >= 0.95 and v.get("ph", 0.0) <= 1.6:            # reading: the other hand comes up to hold it too
        p["ik_R"] = Bb.w(o, 0.04, 0.88, 0.35)
        p["pole_R"] = Bb.d(0.55, -1.0, -0.1)
    on = phone_on if phone_on is not None else v.get("ph", 0.0) > 0.5
    h = {"L": rig.phone(on=on)} if held else None
    return [("maya", "maya", p, h)]


def maya_sofa(T, tr, bl, phone_on=True):
    x, z, yaw = SOFA
    p = S.seated("maya", x, z, yaw, 0.52, 0.36, breath=0.5 + 0.5 * math.sin(T * 1.7))
    p = face(p, T, tr, "MAYA", bl)
    Bb = rig.Basis.yaw(yaw)
    o = (x, 0, z)
    typing = tr(T).get("ph2", 0.0)
    tap = 0.008 * typing * math.sin(T * 23)
    p["ik_L"] = Bb.w(o, -0.04, 0.90 + tap, 0.34)
    p["ik_R"] = Bb.w(o, 0.04, 0.90 - tap, 0.34)
    p["pole_L"], p["pole_R"] = Bb.d(-0.55, -1.0, -0.1), Bb.d(0.55, -1.0, -0.1)
    return [("maya", "maya", p, {"L": rig.phone(on=phone_on)})]


def maya_kitch(T, tr, bl, phone_on=False, held=False):
    x, z, yaw = KITCH
    v = tr(T)
    p = dict(rig.REST, x=x, z=z, yaw=yaw, aR=(10.0, 8.0, 30.0), aL=(10.0, 8.0, 30.0), breath=0.5 + 0.5 * math.sin(T * 1.7))
    p = face(p, T, tr, "MAYA", bl)
    Bb = rig.Basis.yaw(yaw)
    o = (x, 0, z)
    # 3 = both hands round the mug on the counter; 1 = phone up in front; 0 = at the ear
    tg = {1: Bb.w(o, -0.05, 1.18, 0.30), 2: Bb.w(o, -0.05, 1.18, 0.30), 3: Bb.w(o, -0.10, 0.97, 0.36)}
    ph = v.get("ph", 3.0)
    tg[3] = Bb.w(o, 0.10, 0.97, 0.36)
    p = phone_hand(p, "maya", ph, "R", tg)
    p["ik_L"] = Bb.w(o, -0.08, 0.97, 0.38)
    p["pole_L"] = Bb.d(-0.5, -1.0, 0.0)
    return [("maya", "maya", p, {"R": rig.phone(on=phone_on and ph > 0.5)} if held else None)]


def theo_desk(T, tr, bl, phone_on=True, side="R"):
    x, z, yaw = DESK
    v = tr(T)
    p = S.seated("theo", x, z, yaw, 0.5, 0.36, breath=0.5 + 0.5 * math.sin(T * 1.9))
    p = face(p, T, tr, "THEO", bl)
    Bb = rig.Basis.yaw(yaw)
    o = (x, 0, z)
    ph = v.get("ph", 1.0)
    typing = v.get("ph2", 0.0)
    tap = 0.008 * typing * math.sin(T * 25)
    tg = {1: Bb.w(o, 0.0, 0.88 + tap, 0.38), 2: Bb.w(o, 0.04, 0.66, 0.26), 3: Bb.w(o, 0.12, 0.76, 0.40)}
    p = phone_hand(p, "theo", ph, side, tg)
    other = "L" if side == "R" else "R"
    sg = 1 if other == "R" else -1
    if ph >= 0.95 and ph <= 1.5:
        p["ik_" + other] = Bb.w(o, sg * 0.05, 0.88 - tap, 0.38)
        p["pole_" + other] = Bb.d(sg * 0.55, -1.0, -0.1)
    else:
        p["ik_" + other] = Bb.w(o, sg * 0.14, 0.77, 0.42)                    # resting on the desk edge
        p["pole_" + other] = Bb.d(sg * 0.5, -1.0, 0.0)
    return [("theo", "theo", p, {side: rig.phone(on=phone_on and ph > 0.5)})]


def theo_bed(T, tr, bl):
    x, z, yaw = BED
    p = S.seated("theo", x, z, yaw, 0.56, 0.34, breath=0.5 + 0.5 * math.sin(T * 2.3))
    p = face(p, T, tr, "THEO", bl)
    Bb = rig.Basis.yaw(yaw)
    o = (x, 0, z)
    p["ik_R"] = Bb.w(o, 0.03, 0.82, 0.30)                                     # hands clasped between his knees
    p["ik_L"] = Bb.w(o, -0.03, 0.82, 0.30)
    p["pole_R"], p["pole_L"] = Bb.d(0.6, -1.0, 0.0), Bb.d(-0.6, -1.0, 0.0)
    return [("theo", "theo", p, None)]


def frank_kitch(T, tr, bl):
    x, z, yaw = KITCH
    p = dict(rig.REST, x=x, z=z, yaw=yaw, aR=(10.0, 8.0, 30.0), breath=0.5 + 0.5 * math.sin(T * 1.5))
    p = face(p, T, tr, "FRANK", bl)
    Bb = rig.Basis.yaw(yaw)
    o = (x, 0, z)
    p = phone_hand(p, "frank", 0.0, "L", {1: Bb.w(o, 0, 1.2, 0.3), 2: Bb.w(o, 0, 1.2, 0.3), 3: Bb.w(o, 0, 1.0, 0.3)})
    p["ik_R"] = Bb.w(o, 0.10, 0.98, 0.40)
    p["pole_R"] = Bb.d(0.5, -1.0, 0.0)
    return [("frank", "frank", p, {"L": rig.phone(on=False)})]
