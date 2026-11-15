"""Kokoro (local, free) -> audio/lines/<id>.wav, 48 kHz mono, trimmed tight (house rule: fast audio).
A voice's pitch (semitones) is applied by resampling, which also speeds it up by the same ratio.
    python tts.py [--force]"""
import os
import sys

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

import script as S

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(HERE, "audio", "lines")


def trim(a, sr, thr=0.015):
    idx = np.where(np.abs(a) > thr)[0]
    if len(idx) == 0:
        return a
    return a[max(0, idx[0] - int(0.01 * sr)):min(len(a), idx[-1] + int(0.04 * sr))]


def squeeze(a, sr, max_gap=0.12, thr=0.01):
    """Cut every internal pause down to max_gap s: no breathers."""
    hop = int(0.01 * sr)
    n = len(a) // hop
    loud = np.sqrt(np.mean(a[:n * hop].reshape(n, hop) ** 2, axis=1)) > thr
    keep, run = [], 0
    for i in range(n):
        run = 0 if loud[i] else run + 1
        if run * 0.01 <= max_gap:
            keep.append(a[i * hop:(i + 1) * hop])
    return np.concatenate(keep + [a[n * hop:]])


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
        voice, speed, lang, pitch = S.VOICES[spk]
        a, sr = k.create(ex.get("tts", text), voice=voice, speed=ex.get("speed", speed), lang=lang)
        a = np.asarray(a, dtype=np.float64)
        r = 2 ** (pitch / 12)                              # play r times faster -> pitch up by `pitch` semitones
        up, down = 2 * 1000, int(round(1000 * r))           # 24 kHz -> 48 kHz, then / r
        a = resample_poly(a, up, down).astype(np.float32)
        a = squeeze(trim(a, 48000), 48000)
        a *= 10 ** (-3 / 20) / max(1e-6, np.abs(a).max())
        sf.write(path, a, 48000)
        print(f"{bid:8s} {spk:6s} {len(a) / 48000:5.2f}s  {text[:60]}")


if __name__ == "__main__":
    main("--force" in sys.argv)
