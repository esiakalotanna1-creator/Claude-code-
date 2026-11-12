"""Station 4: sound. Generate music bed + SFX from timeline.json marks.

Every sound is shaped noise / sine stacks (numpy+scipy). Ducking under
spoken lines is baked into both beds. Writes:
  video/audio/music.wav, video/audio/sfx.wav, sfx_times.json

Usage (from the repo root): python tools/sound.py episodes/<name>/toon
"""
import json
import os
import sys

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

SR = 48000
rng = np.random.default_rng(11)  # fixed seed: deterministic renders


def t_axis(dur):
    return np.arange(int(dur * SR)) / SR


def env_ar(n, a, r, hold=1.0):
    """attack/release envelope in seconds over n samples"""
    e = np.ones(n) * hold
    na, nr = int(a * SR), int(r * SR)
    if na:
        e[:na] = np.linspace(0, hold, na)
    if nr:
        e[-nr:] = np.linspace(hold, 0, nr)
    return e


def bp(x, lo, hi, order=4):
    sos = butter(order, [lo, hi], btype="band", fs=SR, output="sos")
    return sosfilt(sos, x)


def lp(x, f, order=4):
    sos = butter(order, f, btype="low", fs=SR, output="sos")
    return sosfilt(sos, x)


def hp(x, f, order=4):
    sos = butter(order, f, btype="high", fs=SR, output="sos")
    return sosfilt(sos, x)


# ---------------- SFX generators ----------------

def heartbeat(dur, bpm=55):
    """lub-dub pairs"""
    t = t_axis(dur)
    out = np.zeros_like(t)
    beat = 60.0 / bpm
    ti = 0.0
    while ti < dur - 0.4:
        for off, amp in ((0.0, 1.0), (0.16, 0.65)):
            i = int((ti + off) * SR)
            n = int(0.12 * SR)
            tt = t_axis(0.12)
            thump = np.sin(2 * np.pi * (52 - 18 * tt / 0.12) * tt) * np.exp(-tt * 28)
            out[i:i + n] += amp * thump[:len(out[i:i + n])]
        ti += beat
    return lp(out, 150) * 1.6


def bass_impact(dur=1.6):
    t = t_axis(dur)
    f = 64 * np.exp(-t * 2.2) + 36
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.6)
    click = hp(rng.standard_normal(len(t)) * np.exp(-t * 60), 1200) * 0.4
    return lp(body, 220) * 1.4 + click


def padlock_click():
    t = t_axis(0.22)
    n = rng.standard_normal(len(t))
    a = bp(n, 1800, 4800) * np.exp(-t * 55)
    b = bp(n, 700, 1400) * np.exp(-t * 30) * 0.6
    return (a + b) * 1.1


def door_creak(dur=1.8):
    t = t_axis(dur)
    f = 280 + 180 * np.sin(2 * np.pi * 0.7 * t) + 90 * np.sin(2 * np.pi * 2.3 * t + 1.2)
    tone = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR))  # square: woody
    grit = bp(rng.standard_normal(len(t)), 400, 2200) * 0.35
    x = (tone * 0.5 + grit) * env_ar(len(t), 0.15, 0.5, 0.8)
    return bp(x, 240, 2600) * 0.5


def stair_creak(dur=0.7):
    t = t_axis(dur)
    f = 520 - 260 * t / dur + 60 * np.sin(2 * np.pi * 9 * t)
    tone = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR))
    x = tone * env_ar(len(t), 0.02, 0.3, 0.9)
    return bp(x, 300, 3000) * 0.5


def fabric_whoosh(dur=0.5):
    t = t_axis(dur)
    n = rng.standard_normal(len(t))
    sweep = bp(n, 300, 1800) * np.sin(np.pi * t / dur) ** 2
    return sweep * 1.2


def cage_clang(dur=1.4):
    t = t_axis(dur)
    out = np.zeros_like(t)
    for f, a, d in ((211, 1.0, 6), (337, 0.7, 8), (489, 0.5, 10), (678, 0.35, 13)):
        out += a * np.sin(2 * np.pi * f * t) * np.exp(-t * d)
    strike = hp(rng.standard_normal(len(t)) * np.exp(-t * 80), 900) * 0.5
    return (out * 0.5 + strike) * 0.9


def light_clack():
    t = t_axis(0.09)
    return bp(rng.standard_normal(len(t)) * np.exp(-t * 90), 900, 5200) * 1.3


def fluoro_hum(dur):
    t = t_axis(dur)
    x = (np.sin(2 * np.pi * 120 * t) + 0.4 * np.sin(2 * np.pi * 240 * t)
         + 0.15 * np.sin(2 * np.pi * 360 * t))
    flicker = 1 + 0.08 * np.sin(2 * np.pi * 7.3 * t) * np.sin(2 * np.pi * 0.9 * t)
    return x * flicker * env_ar(len(t), 0.4, 0.8, 1.0) * 0.16


def deep_boom(dur=2.2):
    t = t_axis(dur)
    x = np.sin(2 * np.pi * (44 - 8 * t / dur) * t) * np.exp(-t * 1.8)
    return lp(x, 130) * 1.5


def sting(dur=1.2):
    t = t_axis(dur)
    out = np.zeros_like(t)
    for f in (660, 702, 991, 1320):
        out += np.sin(2 * np.pi * f * t)
    out *= np.exp(-t * 4) * 0.28
    return out + bass_impact(dur)[:len(out)] * 0.8


def riser(dur=2.0):
    t = t_axis(dur)
    n = bp(rng.standard_normal(len(t)), 300, 4000)
    return n * (t / dur) ** 2.5 * 0.9


def bubbles(dur=1.6, n=7):
    """small wet pops at fixed spacings"""
    out = np.zeros(int(dur * SR))
    for i in range(n):
        at = 0.08 + i * (dur - 0.3) / n + ((i * 37) % 7) * 0.012
        tt = t_axis(0.07)
        f = 380 + ((i * 53) % 5) * 90
        pop = np.sin(2 * np.pi * (f + 900 * tt) * tt) * np.exp(-tt * 70)
        j = int(at * SR)
        out[j:j + len(pop)] += pop[:len(out) - j] * (0.8 - 0.06 * i)
    return lp(out, 2500) * 0.9


def skin_shift(dur=2.4):
    """warping low tone + bony crackle bursts"""
    t = t_axis(dur)
    f = 70 + 50 * np.sin(2 * np.pi * 0.9 * t) * (t / dur)
    warp = np.sin(2 * np.pi * np.cumsum(f) / SR) * env_ar(len(t), 0.3, 0.4, 0.9)
    crack = np.zeros_like(t)
    for i in range(14):
        at = 0.2 + i * (dur - 0.5) / 14 + ((i * 29) % 5) * 0.02
        j = int(at * SR)
        tt = t_axis(0.04)
        burst = hp(rng.standard_normal(len(tt)), 1500) * np.exp(-tt * 120)
        crack[j:j + len(burst)] += burst[:len(crack) - j] * (0.5 + 0.04 * i)
    return lp(warp, 200) * 0.9 + bp(crack, 1200, 6000) * 0.6


def thud(dur=0.6):
    t = t_axis(dur)
    body = np.sin(2 * np.pi * (70 - 30 * t / dur) * t) * np.exp(-t * 9)
    grit = lp(rng.standard_normal(len(t)), 600) * np.exp(-t * 25) * 0.4
    return lp(body + grit, 300) * 1.3


# ---------------- music bed ----------------

def music_bed(total, marks, hum_from=None, hum_to=None):
    t = t_axis(total)
    # root drone: A1 55Hz, slow detune beat
    drone = (np.sin(2 * np.pi * 55 * t) + np.sin(2 * np.pi * 55.35 * t)
             + 0.5 * np.sin(2 * np.pi * 110 * t))
    drone *= 0.5 + 0.12 * np.sin(2 * np.pi * 0.07 * t)
    # minor pad: A2-C3-E3, very soft, breathing
    pad = (np.sin(2 * np.pi * 110 * t) + np.sin(2 * np.pi * 130.8 * t)
           + np.sin(2 * np.pi * 164.8 * t))
    pad = lp(pad, 900) * (0.10 + 0.05 * np.sin(2 * np.pi * 0.05 * t + 2))
    bed = lp(drone, 300) * 0.5 + pad
    # tension: slow semitone shimmer after the tale
    if "copycat_tale" in marks:
        i0 = int(marks["copycat_tale"] * SR)
        tt = t[i0:] - t[i0]
        shimmer = np.sin(2 * np.pi * 220 * tt) * np.sin(2 * np.pi * 233.1 * tt)
        bed[i0:] += lp(shimmer, 1200) * np.minimum(tt / 12, 1) * 0.12
    # fluorescent hum lives in the music bed (ambience)
    if hum_from is not None:
        i0 = int(hum_from * SR)
        dur = (hum_to or total) - hum_from
        h = fluoro_hum(dur)
        bed[i0:i0 + len(h)] += h
    return bed


def duck(x, lines, down, attack=0.06, release=0.18):
    """multiply bed by ducking envelope around spoken lines"""
    env = np.ones(len(x))
    for L in lines:
        i0 = max(0, int((L["t0"] - attack) * SR))
        i1 = min(len(x), int((L["t1"] + release) * SR))
        env[i0:i1] = np.minimum(env[i0:i1], down)
    # smooth the steps
    k = int(0.05 * SR)
    kernel = np.ones(k) / k
    env = np.convolve(env, kernel, mode="same")
    return x * env


def main(ep_dir):
    tl = json.load(open(os.path.join(ep_dir, "timeline.json"), encoding="utf-8"))
    total = tl["total"] + 0.5
    marks, lines = tl["marks"], tl["lines"]

    # ---- sfx track ----
    sfx = np.zeros(int(total * SR))
    events = []

    def put(name, when, samples, gain=1.0):
        i = int(when * SR)
        s = samples * gain
        end = min(len(sfx), i + len(s))
        if end > i:
            sfx[i:end] += s[:end - i]
            events.append(dict(name=name, t=round(when, 3)))

    cues_path = os.path.join(ep_dir, "cues.py")
    if os.path.exists(cues_path):
        # episode-specific sound design: cues.py defines build(ctx) and may
        # return a dict with 'music' (float array) and 'music_mute' spans
        import importlib.util
        spec = importlib.util.spec_from_file_location("episode_cues", cues_path)
        cues = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cues)
        ctx = dict(marks=marks, lines=lines, total=total, put=put, SR=SR, gen=globals())
        res = cues.build(ctx) or {}
        finish(ep_dir, sfx, events, lines, res.get("music"), res.get("music_mute", []),
               music_level=res.get("music_level", 0.32), duck_down=res.get("duck_down", 0.45),
               ambience=res.get("ambience"), ambience_level=res.get("ambience_level", 0.06), sfx_level=res.get("sfx_level", 0.75))
        return

    raise SystemExit(f"{ep_dir} has no cues.py: write one with build(ctx) (see episodes/window/toon/cues.py)")


def finish(ep_dir, sfx, events, lines, music, music_mute=(), music_level=0.32, duck_down=0.45, ambience=None,
           ambience_level=0.06, sfx_level=0.75):
    """duck, normalise and write both tracks. music_mute: [(t0, t1)] spans where
    the bed drops to silence and then fades back over 2 s."""
    sfx = duck(sfx, lines, down=duck_down)
    peak = np.abs(sfx).max()
    if peak > 0:
        sfx = sfx / peak * sfx_level  # docs: effects ~0.75

    music = duck(music, lines, down=duck_down)
    for t0, t1 in music_mute:
        i0 = int(t0 * SR)
        i1 = min(len(music), int(t1 * SR))
        i2 = min(len(music), i1 + int(2.0 * SR))
        music[i0:i1] *= 0.0
        music[i1:i2] *= np.linspace(0, 1, i2 - i1)
    peak = np.abs(music).max()
    if peak > 0:
        music = music / peak * music_level

    adir = os.path.join(ep_dir, "video", "audio")
    os.makedirs(adir, exist_ok=True)
    sf.write(os.path.join(adir, "music.wav"), music.astype(np.float32), SR)
    sf.write(os.path.join(adir, "sfx.wav"), sfx.astype(np.float32), SR)
    if ambience is not None:                  # optional 4th stem (rain / city bed), ducked lightly under the lines
        ambience = duck(ambience, lines, down=0.7)
        ambience = ambience / (np.abs(ambience).max() + 1e-9) * ambience_level
        sf.write(os.path.join(adir, "ambience.wav"), ambience.astype(np.float32), SR)
    with open(os.path.join(ep_dir, "sfx_times.json"), "w") as f:
        json.dump(events, f, indent=1)
    print(f"music.wav + sfx.wav written ({len(sfx) / SR:.1f}s), {len(events)} sfx events")
    for e in events:
        print(f"  {e['t']:>6.2f}  {e['name']}")


if __name__ == "__main__":
    main(sys.argv[1])
