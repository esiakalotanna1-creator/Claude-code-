"""Sound for THE LIGHT AT SEA. From the repo root:  python tools/sound.py episodes/lighthouse/toon
-> video/audio/music.wav, sfx.wav, ambience.wav (the narration stem comes from build_tl.py).

Everything is synthesised so the chain runs with no samples: fine for the drone, the sea-light shimmer and the
lamp's glow; replace the lever clunks and the sea bed with real recordings before you publish.
Event times are the same lists as scenes.py (LAMP, SEA): keep them in step.
"""
import numpy as np

LAMP = [1.7, 2.3, 2.9, 11.9, 12.4, 14.6, 38.0, 38.6, 39.2]
PRESS = LAMP[:6]                                   # pulled by hand: a clunk. The last three: nobody pulled them.
SEA = [5.6, 6.2, 6.8, 8.6, 9.2, 9.8, 12.95, 13.45, 15.15, 16.6, 18.0, 19.4, 22.0, 24.2, 26.4, 28.9, 31.6,
       35.0, 35.6, 36.2]
PAGE_OPEN = 21.2


def build(ctx):
    G, put, total = ctx["gen"], ctx["put"], ctx["total"]
    t = G["t_axis"](total)
    rng = np.random.default_rng(23)
    sr = int(round(len(t) / total))

    def tone(f, dur, decay, partials=((1.0, 1.0), (2.01, 0.4), (3.02, 0.2))):
        tt = np.arange(int(dur * sr)) / sr
        x = sum(a * np.sin(2 * np.pi * f * k * tt) for k, a in partials)
        return (x * np.exp(-tt * decay) * np.minimum(1.0, tt / 0.004)).astype("float32")

    for i, s in enumerate(LAMP):
        if s in PRESS:
            put(f"lever_{i}", s - 0.07, G["light_clack"](), 0.55)           # the lever going down
            put(f"latch_{i}", s - 0.02, G["padlock_click"](), 0.35)
        else:
            put(f"ghost_{i}", s - 0.02, G["deep_boom"](1.6), 0.45)         # nobody touched it
        put(f"lamp_{i}", s, tone(196.0, 0.5, 5.0, ((1.0, 1.0), (1.5, 0.5), (2.0, 0.3))), 0.22 if s in PRESS else 0.38)
    for i, s in enumerate(SEA):                                             # the answer: cold, glassy, a little late
        put(f"sea_{i}", s, tone(1318.5, 0.9, 4.5, ((1.0, 1.0), (1.498, 0.55), (2.51, 0.25))), 0.16)
    put("page", PAGE_OPEN, G["fabric_whoosh"](0.6), 0.5)
    put("last_hit", 39.9, G["bass_impact"](1.6), 0.9)                       # "Three times."
    put("riser_hand", 33.9, G["riser"](3.8), 0.35)

    # ambience: the sea and a thin wind round the glass, always there; the lamp room is otherwise quiet
    sea = G["lp"](rng.standard_normal(len(t)), 420) * (0.55 + 0.45 * np.sin(2 * np.pi * t / 7.3 + 0.4) ** 2)
    wind = G["bp"](rng.standard_normal(len(t)), 500, 1400) * (0.25 + 0.2 * np.sin(2 * np.pi * t / 11.0))
    amb = sea + 0.35 * wind
    amb *= np.clip(1.0 - np.clip((t - (total - 0.6)) / 0.6, 0, 1), 0, 1)

    # music: one low drone that enters with the first answer, tightens as the light closes in, thins to nothing
    # on the last line so the final flashes are heard alone
    drone = (np.sin(2 * np.pi * 55.0 * t) + 0.5 * np.sin(2 * np.pi * 82.6 * t + 0.7) + 0.25 * np.sin(2 * np.pi * 110.7 * t)) \
        * (0.75 + 0.25 * np.sin(2 * np.pi * t / 6.1))
    drone *= np.clip((t - 4.8) / 3.0, 0, 1) * (0.55 + 0.45 * np.clip((t - 17.0) / 12.0, 0, 1))
    drone *= 1.0 - 0.85 * np.clip((t - 39.6) / 1.5, 0, 1)
    thin = np.sin(2 * np.pi * 1760.0 * t) * 0.05 * np.clip((t - 28.0) / 6.0, 0, 1) * (1.0 - np.clip((t - 39.6) / 0.8, 0, 1))
    music = (drone + thin) * G["env_ar"](len(t), 0.05, 0.6)
    return dict(music=music.astype("float32"), music_level=0.15, duck_down=0.5,
                ambience=amb.astype("float32"), ambience_level=0.06, sfx_level=0.7)
