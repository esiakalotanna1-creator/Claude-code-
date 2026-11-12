"""Sound for LEAVE A MESSAGE. From the repo root:  python tools/sound.py episodes/callback/toon
-> video/audio/music.wav, sfx.wav, ambience.wav (the voices are on narration.wav from build_tl.py).

All synthesised so the chain runs with no samples: rain bed, phone ring / buzz / message pop / voicemail beep,
a soft piano score. Replace the rain and the phone sounds with real recordings before publishing if you can.
"""
import numpy as np

SR = 48000


def build(ctx):
    G, put, total, M = ctx["gen"], ctx["put"], ctx["total"], ctx["marks"]
    t = G["t_axis"](total)
    rng = np.random.default_rng(5)

    def tone(freqs, dur, a=0.004, decay=3.0):
        tt = np.arange(int(dur * SR)) / SR
        x = sum(np.sin(2 * np.pi * f * tt) for f in freqs) / len(freqs)
        return (x * np.minimum(1, tt / a) * np.exp(-tt * decay)).astype("float32")

    def ring():                                       # a classic two-tone ring, 1.6 s on
        tt = np.arange(int(1.6 * SR)) / SR
        x = 0.5 * (np.sin(2 * np.pi * 440 * tt) + np.sin(2 * np.pi * 480 * tt))
        x *= (np.sin(2 * np.pi * 20 * tt) > -0.2) * np.minimum(1, tt / 0.01) * np.minimum(1, (1.6 - tt) / 0.02)
        return G["lp"](x, 2600).astype("float32")

    def buzz(dur=1.1):
        tt = np.arange(int(dur * SR)) / SR
        x = np.sign(np.sin(2 * np.pi * 150 * tt)) * (0.6 + 0.4 * np.sin(2 * np.pi * 9 * tt)) * ((tt % 0.55) < 0.38)
        return G["lp"](x, 900).astype("float32") * 0.6

    def pop():
        return tone([880, 1320], 0.18, decay=22)

    def tap():
        n = rng.standard_normal(int(0.03 * SR))
        return (G["bp"](n, 2000, 6000) * np.exp(-np.arange(len(n)) / SR * 120)).astype("float32")

    b, e = lambda k: M[k], None
    beats = ctx.get("beats")
    # --- events -------------------------------------------------------------------------------------------------
    put("dial", b("dead") - 0.3, tone([350, 440], 1.2, decay=0.6) * 0.5, 0.25)
    put("click_greet", b("greet") - 0.25, tone([1800], 0.05, decay=60), 0.4)
    put("hangup1", b("never") + 3.5, tone([600], 0.08, decay=40), 0.35)
    put("ring1", b("twice") + 0.2, ring()[: int(1.0 * SR)], 0.07)
    put("ring2", b("twice") + 1.5, ring()[: int(0.7 * SR)], 0.16)
    put("click_hello", b("hello") - 0.3, tone([1800], 0.05, decay=60), 0.4)
    put("drop", b("drop") + 0.57, G["thud"](0.3), 0.5)
    for i in range(10):
        put(f"tap_who_{i}", b("who") + 0.25 + i * 0.13, tap(), 0.25)
    put("send_who", b("who") + 1.75, pop(), 0.3)
    for i in range(24):
        put(f"tap_typed_{i}", b("typed") + 0.3 + i * 0.11 + 0.03 * (i % 3), tap(), 0.2)
    put("recv_who", b("msg") - 0.3, pop(), 0.25)
    put("send_msg", b("msg") + 6.2, pop(), 0.3)
    put("recv_dont", b("dont") + 0.1, pop(), 0.35)
    put("buzz_ok", b("next") + 1.5, buzz(1.5), 0.45)
    put("ring_call", b("wasnt") + 0.9, ring()[: int(0.8 * SR)], 0.15)
    for k in range(3):
        put(f"ring_anniv_{k}", b("rang") + 0.2 + k * 1.9, ring(), 0.08)
    put("vm_click", b("voice") + 0.7, tone([1800], 0.05, decay=60), 0.4)
    put("beep", b("okay") - 0.95, tone([1000], 0.45, a=0.002, decay=0.3), 0.35)
    put("hangup2", b("hungup") + 0.2, tone([600], 0.08, decay=40), 0.35)
    for k in range(2):
        put(f"ring_dad_{k}", b("incoming") - 0.1 + k * 1.8, ring(), 0.24)
    put("answer", b("last") + 0.95, tone([1800], 0.05, decay=60), 0.35)

    # --- ambience: rain against glass, always; a little louder in Maya's flat -----------------------------------
    rain = G["bp"](rng.standard_normal(len(t)), 900, 6000) * 0.5 + G["lp"](rng.standard_normal(len(t)), 400) * 0.8
    patter = (rng.random(len(t)) < 0.0009) * rng.uniform(0.3, 1.0, len(t))
    rain = rain + G["hp"](np.convolve(patter, np.exp(-np.arange(200) / 30.0), "same"), 2000) * 2.0
    amb = rain * (0.85 + 0.15 * np.sin(2 * np.pi * t / 9.0))

    # --- music: a soft piano; sparse, then warm in the montage, gone for the beep, full at the end ---------------
    def piano(f, dur):
        tt = np.arange(int(dur * SR)) / SR
        x = sum(a * np.sin(2 * np.pi * f * k * tt) * np.exp(-tt * (1.4 + 0.9 * k)) for k, a in ((1, 1.0), (2, 0.42), (3, 0.18), (4, 0.08)))
        return x * np.minimum(1, tt / 0.006)

    music = np.zeros(len(t), np.float32)

    def note(at, midi, dur=3.0, vel=0.5):
        f = 440 * 2 ** ((midi - 69) / 12)
        x = piano(f, dur) * vel
        i = int(at * SR)
        j = min(len(music), i + len(x))
        if i < len(music):
            music[i:j] += x[: j - i]

    # chords (A minor): Am, F, C, G ; then Fmaj7, C/E, Dm7, G
    prog = [(57, 60, 64), (53, 57, 60), (48, 52, 55), (55, 59, 62), (53, 57, 64), (52, 55, 60), (50, 53, 57), (55, 59, 62)]

    def phrase(t0, t1, beat, vel, arp=True, bass=True, start=0):
        k, tt = start, t0
        while tt < t1 - 0.5:
            ch = prog[k % len(prog)]
            if bass:
                note(tt, ch[0] - 12, 4.5, vel * 0.8)
            if arp:
                for j, m in enumerate((ch[0], ch[1], ch[2], ch[1] + 12, ch[2])):
                    note(tt + j * beat / 4, m + 12, 2.5, vel * (0.55 if j else 0.7))
            else:
                for m in ch:
                    note(tt, m + 12, 4.0, vel * 0.45)
            tt += beat * 2
            k += 1

    phrase(0.2, b("across") - 0.4, 2.2, 0.16, arp=False)                     # the ritual: a few held chords
    phrase(b("typed"), b("next") - 0.3, 2.0, 0.13, arp=False, start=2)
    phrase(b("loud"), b("thursday") - 0.6, 1.6, 0.20, arp=True, start=0)      # the calls: the piano moves
    phrase(b("thursday"), b("voice") - 0.5, 2.4, 0.09, arp=False, bass=True, start=4)
    phrase(b("newgreet") + 0.5, b("beep") - 0.3, 2.0, 0.12, arp=True, start=0)
    phrase(b("incoming") - 0.2, total, 1.7, 0.24, arp=True, start=4)          # he called back
    note(total - 4.2, 45, 6.0, 0.3)
    note(total - 4.2, 57, 6.0, 0.25)
    note(total - 4.2, 64, 6.0, 0.2)
    music *= G["env_ar"](len(t), 0.5, 1.2)
    return dict(music=music.astype("float32"), music_level=0.17, duck_down=0.35,
                ambience=amb.astype("float32"), ambience_level=0.035, sfx_level=0.6)
