"""Timing: keyed tracks evaluated from elapsed time, with per-key easing, and camera moves.

Pick the ease per key to match the action: "io" for slow gestures, "out" for sudden reactions (fast start,
soft stop), "snap" for impacts, "back" for a settle with a small overshoot, "lin" for constant motion.

    tr = Track([(0.0, dict(head_yaw=0)), (0.4, dict(head_yaw=30), "out")])
    tr(t) -> dict
"""
import math


def clamp(t):
    return max(0.0, min(1.0, t))


EASE = {
    "lin": clamp,
    "io": lambda t: 0.5 - 0.5 * math.cos(math.pi * clamp(t)),
    "in": lambda t: clamp(t) ** 2,
    "out": lambda t: 1 - (1 - clamp(t)) ** 3,
    "snap": lambda t: 1 - (1 - clamp(t)) ** 5,
    "back": lambda t: 1 + 2.2 * (clamp(t) - 1) ** 3 + 1.2 * (clamp(t) - 1) ** 2,
}


def lerp(a, b, t):
    if isinstance(a, tuple):
        return tuple(x + (y - x) * t for x, y in zip(a, b))
    return a + (b - a) * t


HOLD = object()      # in a key: "this channel starts moving here" (keeps its previous value until now)


class Track:
    """keys: [(t, {channel: value}, ease_into_this_key="io")]. Every channel interpolates only between the
    keys that name it, so actions on different channels overlap freely (offset timing). Use HOLD to mark
    where a channel's next move starts."""

    def __init__(self, keys):
        self.ch = {}
        for k in sorted(keys, key=lambda k: k[0]):
            t, v, e = (tuple(k) + ("io",))[:3]
            for n, val in v.items():
                ks = self.ch.setdefault(n, [])
                ks.append((t, ks[-1][1] if val is HOLD else val, e))

    def __call__(self, t):
        out = {}
        for n, ks in self.ch.items():
            if t <= ks[0][0]:
                out[n] = ks[0][1]
                continue
            out[n] = ks[-1][1]
            for (ta, va, _), (tb, vb, eb) in zip(ks, ks[1:]):
                if t <= tb:
                    out[n] = lerp(va, vb, EASE[eb]((t - ta) / max(1e-6, tb - ta)))
                    break
        return out


def move(t, t0, t1, a, b, ramp=0.3):
    """Camera move from a to b over [t0, t1] with a trapezoid velocity profile: it accelerates over the first
    `ramp` fraction, glides at constant speed, and decelerates over the last `ramp` fraction (no restarts)."""
    u = clamp((t - t0) / max(1e-6, t1 - t0))
    r = max(1e-3, min(0.5, ramp))
    vmax = 1 / (1 - r)                     # area under the trapezoid = 1
    if u < r:
        s = 0.5 * vmax * u * u / r
    elif u > 1 - r:
        s = 1 - 0.5 * vmax * (1 - u) ** 2 / r
    else:
        s = 0.5 * vmax * r + vmax * (u - r)
    return lerp(a, b, s)


def blink(t, times, dur=0.16):
    """Lid multiplier for blinks starting at `times` (closes fast, opens a little slower)."""
    m = 1.0
    for b in times:
        u = (t - b) / dur
        if 0 <= u < 1:
            m = min(m, 1 - u / 0.4 if u < 0.4 else (u - 0.4) / 0.6)
    return m
