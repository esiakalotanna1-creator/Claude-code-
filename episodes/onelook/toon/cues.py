"""Sound for ONE LOOK: a dark pulse, whooshes on cuts, a cash-register hit per purchase, static, an alarm, a heartbeat for
the last 30 seconds, and a low boom on the title. All synthesised."""
import numpy as np

import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import script as S  # noqa: E402

SR = 48000


def build(ctx):
    G, put, total, M = ctx["gen"], ctx["put"], ctx["total"], ctx["marks"]
    t = G["t_axis"](total)
    rng = np.random.default_rng(4)

    def tone(fs, d, decay=6.0):
        tt = np.arange(int(d * SR)) / SR
        return (sum(np.sin(2 * np.pi * f * tt) for f in fs) / len(fs) * np.exp(-tt * decay)).astype("float32")

    def whoosh(d=0.45):
        n = rng.standard_normal(int(d * SR))
        return (G["bp"](n, 400, 3500) * np.sin(np.linspace(0, np.pi, len(n))) ** 2).astype("float32")

    put("title_boom", 0.2, G["bass_impact"](1.6), 0.8)
    for k in ("second", "alaska", "numbers", "deal", "city", "dark", "gate", "woman", "heat", "trees", "thirty", "choice"):
        put("wh_" + k, M[k] - 0.2, whoosh(), 0.3)
    put("turn", M["second"] + 1.2, tone([220, 330, 440], 1.2, 2.0), 0.35)
    put("stamp", M["alaska"] + 3.6, G["thud"](0.4), 0.6)
    for bid, *_ , ex in S.BEATS:
        if "item" in ex:
            put("cash_" + bid, M[bid] + 0.05, tone([1318, 1760], 0.5, 7.0), 0.3)
    put("static", M["dark"], (rng.standard_normal(int(1.6 * SR)) * 0.5).astype("float32"), 0.15)
    for i in range(6):
        put(f"alarm{i}", M["gate"] + i * 0.7, tone([880, 660], 0.35, 3.0), 0.25)
    for i in range(int((total - M["thirty"]) / 0.8)):
        put(f"beat{i}", M["thirty"] + i * 0.8, G["thud"](0.25), 0.45)
    pulse = np.sin(2 * np.pi * 49 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.9 * t))
    pad = 0.35 * (np.sin(2 * np.pi * 98 * t) + np.sin(2 * np.pi * 116.5 * t)) * (0.5 + 0.5 * np.sin(2 * np.pi * t / 6.0))
    music = (pulse + pad) * G["env_ar"](len(t), 0.5, 1.0)
    amb = G["lp"](rng.standard_normal(len(t)), 600)
    return dict(music=music.astype("float32"), music_level=0.11, duck_down=0.4, ambience=amb.astype("float32"), ambience_level=0.03, sfx_level=0.6)
