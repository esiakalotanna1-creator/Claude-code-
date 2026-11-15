"""Sound for THREE SECONDS LATE part 1: a cold drone, scrubbing for the hook (the reflection keeps scrubbing), whooshes
on cuts, tape, band-aid pops, a blender zap, a news sting, rain at night, a door creak and the final sting."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import script as S  # noqa: E402,F401

SR = 48000


def build(ctx):
    G, put, total, M = ctx["gen"], ctx["put"], ctx["total"], ctx["marks"]
    t = G["t_axis"](total)
    rng = np.random.default_rng(4)

    def noise(d):
        return rng.standard_normal(int(d * SR))

    def tone(fs, d, decay=6.0):
        tt = np.arange(int(d * SR)) / SR
        return (sum(np.sin(2 * np.pi * f * tt) for f in fs) / len(fs) * np.exp(-tt * decay)).astype("float32")

    def whoosh(d=0.35):
        n = noise(d)
        return (G["bp"](n, 500, 4000) * np.sin(np.linspace(0, np.pi, len(n))) ** 2 * 0.6).astype("float32")

    def scrub(d, rate):
        tt = np.arange(int(d * SR)) / SR
        return (G["bp"](noise(d), 2500, 9000) * (0.5 + 0.5 * np.sin(2 * np.pi * rate * tt)) ** 2 * 0.5).astype("float32")

    put("scrub", 0.05, scrub(1.3, 7.0), 0.5)
    put("scrub_ref", 1.35, scrub(1.8, 4.5) * np.linspace(1, 0.3, int(1.8 * SR)), 0.35)
    put("title", 0.0, G["bass_impact"](1.4), 0.6)
    put("stop", 1.35, G["sting"](1.0), 0.25)
    cuts = ["friday", "mirrors", "windows", "puddles", "phone", "face", "dad", "anchor1", "normal", "cover", "gma1", "remi",
            "vanity", "night", "laugh", "pretty", "which"]
    for k in cuts:
        put("wh_" + k, M[k] - 0.12, whoosh(), 0.35)
    put("boom_globe", M["friday"], G["deep_boom"](1.6), 0.5)
    for i in range(10):
        put(f"blip{i}", M["friday"] + 0.1 + i * 0.16, tone([1760], 0.08, 30), 0.12)
    put("tape", M["mirrors"] + 0.12, (G["bp"](noise(0.25), 1500, 7000) * np.linspace(1, 0.2, int(0.25 * SR))).astype("float32"), 0.5)
    put("drip", M["puddles"] + 0.15, tone([1400, 900], 0.25, 18), 0.4)
    put("click", M["phone"] + 0.4, G["light_clack"](), 0.5)
    for i in range(7):
        put(f"pop{i}", M["dad"] + 1.15 + i * 0.12, tone([700 + 90 * i], 0.08, 40), 0.25)
    bl = M["blender"] + 1.25
    tt = np.arange(int(0.6 * SR)) / SR
    put("blender", bl, (np.sign(np.sin(2 * np.pi * 190 * tt)) * 0.25 * G["env_ar"](len(tt), 0.02, 0.15)).astype("float32"), 0.35)
    put("news", M["anchor1"] - 0.05, tone([523, 659, 784], 0.6, 4.0), 0.3)
    put("pen", M["normal"], (G["bp"](noise(0.5), 3000, 8000) * 0.3).astype("float32"), 0.2)
    put("blanket", M["cover"] + 0.2, G["fabric_whoosh"](0.6), 0.5)
    put("glint", M["vanity"] + 0.6, tone([2637, 3520], 0.6, 5), 0.18)
    put("off", M["night"] + 1.0, G["light_clack"](), 0.4)
    put("creak", M["pretty"] + 0.55, G["door_creak"](1.4), 0.5)
    put("sting", M["card"] - 1.4, G["sting"](1.4), 0.5)
    put("boom_end", M["card"], G["bass_impact"](1.8), 0.7)
    drone = 0.5 * np.sin(2 * np.pi * 55 * t) + 0.3 * np.sin(2 * np.pi * 82.4 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * t / 5))
    pulse = np.sin(2 * np.pi * 2.0 * t) ** 8 * np.sin(2 * np.pi * 110 * t) * 0.4
    music = (drone + pulse) * G["env_ar"](len(t), 0.3, 0.8)
    rain = G["lp"](noise(total), 2500) * 0.6
    env = np.clip((t - M["night"]) / 0.4, 0, 1) * np.clip((M["pretty"] + 1.5 - t) / 1.0, 0.25, 1)
    return dict(music=music.astype("float32"), music_level=0.12, duck_down=0.45, ambience=(rain * env).astype("float32"),
                ambience_level=0.05, sfx_level=0.65)
