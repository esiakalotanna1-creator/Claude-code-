"""Render every voiced beat with Kokoro (local, free) -> audio/lines/<id>.wav, 48 kHz mono, trimmed.
The model files live in assets/tts/ at the project root (kokoro-v1.0.onnx, voices-v1.0.bin; not in git).
    python tts.py            renders missing lines
    python tts.py --force    re-renders all
"""
import os
import sys

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

import script as S

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(HERE, "audio", "lines")


def trim(a, sr, thr=0.012):
    idx = np.where(np.abs(a) > thr)[0]
    if len(idx) == 0:
        return a
    a0, a1 = max(0, idx[0] - int(0.03 * sr)), min(len(a), idx[-1] + int(0.08 * sr))
    return a[a0:a1]


def main(force=False):
    from kokoro_onnx import Kokoro
    k = Kokoro(os.path.join(ROOT, "assets", "tts", "kokoro-v1.0.onnx"), os.path.join(ROOT, "assets", "tts", "voices-v1.0.bin"))
    os.makedirs(OUT, exist_ok=True)
    for bid, spk, text, _, _, ex in S.BEATS:
        if spk == "SCREEN":
            continue
        path = os.path.join(OUT, bid + ".wav")
        if os.path.exists(path) and not force:
            continue
        voice, speed, lang = S.VOICES[spk]
        a, sr = k.create(ex.get("tts", text), voice=voice, speed=ex.get("speed", speed), lang=lang)
        a = resample_poly(np.asarray(a, dtype=np.float64), 2, 1).astype(np.float32)        # 24 kHz -> 48 kHz
        a = trim(a, 48000)
        a *= 10 ** (-3 / 20) / max(1e-6, np.abs(a).max())
        sf.write(path, a, 48000)
        print(f"{bid:10s} {spk:6s} {len(a) / 48000:5.2f}s  {text[:60]}")


if __name__ == "__main__":
    main("--force" in sys.argv)
