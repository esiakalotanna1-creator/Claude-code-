"""Voice-clarity rule: for every line, narration must be >= 10 dB above
music + sfx in the speech band (300-4000 Hz).

Usage (from the repo root): python tools/mix_check.py episodes/<name>/toon
"""
import json
import os
import sys

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt


def band(x, sr):
    sos = butter(4, [300, 4000], btype="band", fs=sr, output="sos")
    return sosfilt(sos, x)


def rms_db(x):
    r = np.sqrt(np.mean(x ** 2))
    return 20 * np.log10(max(r, 1e-9))


def main(ep):
    tl = json.load(open(os.path.join(ep, "timeline.json"), encoding="utf-8"))
    adir = os.path.join(ep, "video", "audio")
    for n in ("narration", "music", "sfx"):
        if not os.path.exists(os.path.join(adir, n + ".wav")):
            raise SystemExit(f"missing {n}.wav in {adir}: run build_tl.py (narration) and tools/sound.py first")
    nar, sr = sf.read(os.path.join(adir, "narration.wav"), dtype="float32")
    mus, _ = sf.read(os.path.join(adir, "music.wav"), dtype="float32")
    fx, _ = sf.read(os.path.join(adir, "sfx.wav"), dtype="float32")
    amb_p = os.path.join(adir, "ambience.wav")
    amb = sf.read(amb_p, dtype="float32")[0] if os.path.exists(amb_p) else np.zeros(len(fx), np.float32)
    for a in (nar, mus, fx, amb):
        assert a.ndim == 1
    n = min(len(nar), len(mus), len(fx), len(amb))
    bed = band(mus[:n] + fx[:n] + amb[:n], sr)
    voice = band(nar[:n], sr)

    fails = 0
    print(f"{'t0':>6}  {'voice':>7} {'bed':>7} {'margin':>7}  line")
    for L in tl["lines"]:
        i0, i1 = int(L["t0"] * sr), min(int(L["t1"] * sr), n)
        v, b = rms_db(voice[i0:i1]), rms_db(bed[i0:i1])
        margin = v - b
        flag = "" if margin >= 10 else "  <-- FAIL"
        if margin < 10:
            fails += 1
        print(f"{L['t0']:>6.1f}  {v:>6.1f} {b:>6.1f} {margin:>6.1f}dB  {L['speaker']}: {L['text'][:40]}{flag}")
    print(f"\n{fails} line(s) under the 10 dB margin" if fails else "\nAll lines pass the 10 dB voice-clarity rule")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main(sys.argv[1])
