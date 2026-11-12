"""Sound design for THE MAN AT THE WINDOW v3 (run from the repo root: python tools/sound.py episodes/window/toon). Night and rain: inside the room the rain is heard on the glass and muffled beyond it; the bedroom insert hears it
fainter under the room tone; at the swap (we are suddenly outside) the rain opens up full and close, a low distant
thunder rolls under the swap, then everything fades under the black. A faint low tone, a glass squeak. No end scare.

Stems: narration.wav (the narrator's take), music.wav (the low tone, synthesised: an abstract drone), sfx.wav, ambience.wav.
Real recordings (not shipped, bring your own): assets/sfx/pixabay at the repo root (rain_window, rain_street, thunder,
wind_howl, aircon_hum, glass_tap, all .mp3) and two episode sounds in audio/sfx (squeak = a palm on glass,
shears = the grip tightening on the shears).
"""
import os
import subprocess

import numpy as np
import soundfile as sf

SR = 48000
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SFX = os.path.join(ROOT, "assets", "sfx", "pixabay")
EP_SFX = os.path.join(HERE, "audio", "sfx")
CACHE = os.path.join(ROOT, "assets", "sfx", "cache")


def load(path):
    if not os.path.exists(path):
        raise SystemExit(f"missing sound sample: {path} (the episode README lists what to bring)")
    os.makedirs(CACHE, exist_ok=True)
    tag = "window_" if path.startswith(EP_SFX) else ""
    out = os.path.join(CACHE, tag + os.path.splitext(os.path.basename(path))[0] + ".wav")
    if not os.path.exists(out):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-ac", "1", "-ar", str(SR), out], check=True)
    s, _ = sf.read(out, dtype="float32")
    return s


def build(ctx):
    G = ctx["gen"]
    t_axis, lp, hp, env_ar = G["t_axis"], G["lp"], G["hp"], G["env_ar"]
    put, M, total = ctx["put"], ctx["marks"], ctx["total"]
    T_TOUCH, T_SLIDE, T_SLID = M["hand"] + 1.55, M["slide"] + 0.8, M["slide"] + 3.4     # = scenes.House
    BD0, BD1 = M["bed"], M["mouth"]                                                      # the upstairs insert

    def src(name):
        return os.path.join(EP_SFX, name + ".mp3") if name in ("squeak", "shears") else os.path.join(SFX, name + ".mp3")

    def smp(name, t0=0.0, dur=None, fade=(0.02, 0.05), norm=1.0):
        s = load(src(name))
        i0 = int(t0 * SR)
        s = s[i0:i0 + int(dur * SR)] if dur else s[i0:]
        s = s / (np.abs(s).max() + 1e-6) * norm
        return s * env_ar(len(s), fade[0], fade[1], 1.0)

    def loop(name, dur, t0=0.0):
        s = load(src(name))[int(t0 * SR):]
        s = s / (np.abs(s).max() + 1e-6)
        n = int(dur * SR)
        if len(s) >= n:
            return s[:n]
        x = SR
        out = np.zeros(n + len(s))
        pos = 0
        while pos < n:
            seg = s.copy()
            seg[:x] *= np.linspace(0, 1, x)
            seg[-x:] *= np.linspace(1, 0, x)
            out[pos:pos + len(s)] += seg
            pos += len(s) - x
        return out[:n]

    def slow(s, k):
        idx = np.arange(0, len(s) - 1, 1.0 / k)
        return np.interp(idx, np.arange(len(s)), s)

    t = t_axis(total)
    n = len(t)
    ramp = lambda x, d: np.clip((t - x) / d, 0, 1)            # noqa: E731
    inside = ramp(BD0 - 0.05, 0.1) * (1 - ramp(BD1 - 0.05, 0.1))   # 1 during the bedroom insert
    out_ = 1 - inside
    F0, F1 = next((L["t0"], L["t1"]) for L in ctx["lines"] if L["text"].startswith("I stood frozen"))
    hush = 1 - 0.55 * np.clip(np.minimum(t - (F0 - 0.3), (F1 + 0.3) - t) / 0.3, 0, 1)   # the world holds its breath

    # ---- ambience: rain. Before the swap we are indoors: drops on the pane, the downpour muffled beyond it, room
    # tone. The bedroom insert hears it fainter. After the swap we are outside in it: the full open rain. ----
    T_SWAP = M["pull"] + 3.85                                  # = scenes.House.T_SWAP
    pane = hp(loop("rain_window", total, t0=1.0), 250)
    street = loop("rain_street", total, t0=3.0)
    wind = lp(loop("wind_howl", total, t0=2.0), 900)
    room = lp(loop("aircon_hum", total, t0=10.0), 300)
    opened = ramp(T_SWAP - 0.15, 0.35)                         # the walls fall away with the cross-fade
    amb = out_ * (1 - opened) * (0.40 * pane + 0.45 * lp(street, 900) + 0.10 * room + 0.12 * wind)
    amb += out_ * opened * (0.75 * street + 0.18 * lp(wind, 700))
    amb += inside * (0.16 * lp(pane, 2500) + 0.22 * lp(street, 600) + 0.14 * room)
    amb *= 1 - ramp(M["black"], 0.08)                          # nothing under the black
    amb = hp(amb, 60)
    amb *= hush

    # ---- sfx (the stem is peak-normalised, so these gains are relative) ----
    # fingertips meet the glass: a soft dull contact, a tiny squeak as the palm flattens
    put("touch_tap", T_TOUCH - 0.03, lp(smp("glass_tap", 0.0, 0.35, norm=0.7, fade=(0.002, 0.2)), 1400), 0.30)
    put("touch_squeak", T_TOUCH + 0.12, hp(smp("squeak", 0.0, 0.5, norm=0.6, fade=(0.03, 0.25)), 400), 0.22)
    # the palm slides down the pane: the real squeak stretched over the whole slide, smile unmoved
    sq = hp(slow(smp("squeak", 0.0, None, norm=0.9, fade=(0.08, 0.5)), (T_SLID - T_SLIDE) / 2.0), 300)
    ts = T_SLIDE + np.arange(len(sq)) / SR
    sq = sq * (1 - 0.8 * np.clip(np.minimum(ts - (F0 - 0.15), (F1 + 0.1) - ts) / 0.15, 0, 1))   # dips under the words
    put("slide_squeak", T_SLIDE, sq, 0.16)
    # the grip tightens on the shears
    put("shears_grip", M["shears"] + 1.0, smp("shears", 0.0, None, norm=0.8, fade=(0.02, 0.4)), 0.45)
    # distant thunder: once far off as he first stares, then low and long under the swap
    put("thunder_far", M["stare"] + 1.2, lp(smp("thunder", 0.0, 6.0, norm=0.8, fade=(0.3, 2.0)), 500), 0.22)
    put("thunder_swap", T_SWAP - 0.25, lp(smp("thunder", 0.0, 7.0, norm=1.0, fade=(0.05, 2.5)), 700), 0.38)
    # the reveal line lands on one soft low swell, nothing sharp
    put("reveal_low", M["wide"] + 0.5, G["deep_boom"](3.2), 0.16)

    # ---- the faint low tone (music stem): two soft detuned lows and filtered air, swelling toward the slide ----
    rng = np.random.default_rng(7)
    lfo = 0.75 + 0.25 * np.sin(2 * np.pi * t / 7.3)
    tone = (np.sin(2 * np.pi * 49.0 * t) + 0.6 * np.sin(2 * np.pi * 73.6 * t + 1.0) + 0.25 * np.sin(2 * np.pi * 98.3 * t)) * lfo
    air = lp(rng.standard_normal(n), 220) * 6.0
    music = (tone + air).astype("float32")
    music *= 0.35 + 0.35 * ramp(M["dad"], 4.0)
    music *= 1 - 0.6 * inside                                  # the family insert stays quiet
    music *= 1 - ramp(M["pull"] + 0.4, 2.2)                    # gone as the camera pulls back
    music *= env_ar(n, 1.5, 0.05, 1.0)
    music *= hush
    return dict(music=music, music_mute=[(M["pull"] + 2.6, total)], music_level=0.16, duck_down=0.5,
                ambience=amb, ambience_level=0.14, sfx_level=0.8)
