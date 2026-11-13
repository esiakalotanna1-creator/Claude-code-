"""Sound for 5 SECONDS WITHOUT WATER: a tense pulse, a tick on every second, whooshes on cuts, glitch, crumble,
the sea roaring back, and a small squeak for the water bear. All synthesised."""
import numpy as np

SR = 48000


def build(ctx):
    G, put, total, M = ctx["gen"], ctx["put"], ctx["total"], ctx["marks"]
    t = G["t_axis"](total)
    rng = np.random.default_rng(3)

    def noise(d):
        return rng.standard_normal(int(d * SR))

    def env(n, a, r):
        x = np.ones(n)
        ia, ir = int(a * SR), int(r * SR)
        x[:ia] = np.linspace(0, 1, ia)
        x[-ir:] *= np.linspace(1, 0, ir)
        return x

    def whoosh(d=0.5):
        n = noise(d)
        return (G["bp"](n, 300, 3000) * np.sin(np.linspace(0, np.pi, len(n))) ** 2).astype("float32")

    def tick():
        tt = np.arange(int(0.12 * SR)) / SR
        return (np.sin(2 * np.pi * 1800 * tt) * np.exp(-tt * 60)).astype("float32")

    def rumble(d):
        n = noise(d)
        return (G["lp"](n, 120) * 3 * env(len(n), 0.2, 0.8)).astype("float32")

    def roar(d):
        n = noise(d)
        return (G["lp"](n, 900) * env(len(n), 0.25, 1.2)).astype("float32")

    put("glitch", M["hook"] + 2.9, (np.sign(noise(0.35)) * 0.3).astype("float32"), 0.25)
    for i, k in enumerate(["s1", "s2", "s3", "s4", "s5"]):
        put(f"tick{i}", M[k], tick(), 0.6)
        put(f"whoosh{i}", M[k] - 0.15, whoosh(), 0.35)
    put("drain", M["gone"], roar(2.5)[::-1].copy(), 0.25)
    put("dust", M["sixty"] + 2.6, (G["hp"](noise(1.5), 3000) * env(int(1.5 * SR), 0.1, 1.0)).astype("float32"), 0.2)
    put("trees", M["plants"] + 0.6, rumble(2.5), 0.4)
    put("city", M["concrete"] + 1.2, rumble(3.5), 0.6)
    put("shipfall", M["ships"] + 1.2, whoosh(4.0), 0.15)
    put("sea_back", M["back"] + 0.3, roar(3.0), 0.7)
    put("boom", M["back"] + 0.9, G["bass_impact"](1.6), 0.8)
    tt = np.arange(int(0.25 * SR)) / SR
    put("squeak", M["tardi"] + 2.9, (np.sin(2 * np.pi * (900 + 900 * tt / 0.25) * tt) * np.exp(-tt * 10)).astype("float32"), 0.3)
    # music: a low pulse that tightens through the five seconds, drops out for the silent sky, swells at the return
    pulse = np.sin(2 * np.pi * 55 * t) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * (1.2 + 0.25 * np.clip((t - M["s1"]) / 30, 0, 1)) * t)))
    pad = 0.4 * (np.sin(2 * np.pi * 110 * t) + np.sin(2 * np.pi * 164.8 * t)) * (0.6 + 0.4 * np.sin(2 * np.pi * t / 7))
    music = (pulse + pad) * np.clip(t / 1.5, 0, 1)
    music *= 1 - 0.85 * ((t > M["sky"] + 0.5) & (t < M["s5"]))
    music *= np.where(t > M["tardi"], 0.5, 1.0)
    music *= G["env_ar"](len(t), 0.1, 1.0)
    amb = G["lp"](rng.standard_normal(len(t)), 500) * np.where(t < M["s1"], 1.0, 0.2)
    return dict(music=music.astype("float32"), music_level=0.12, duck_down=0.4, ambience=amb.astype("float32"), ambience_level=0.04, sfx_level=0.6)
