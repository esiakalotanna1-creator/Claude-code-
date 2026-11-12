"""Find the spoken phrases in a narration take, so you can fill in the source spans in script.py.

    python tools/find_phrases.py take.wav [--gap 0.35] [--floor -38]

Prints one (start, end) per run of speech: a run ends when the level stays under the floor (dB below the take's
peak) for longer than the gap (seconds). Read them against your script: a pause inside a sentence splits it in
two (raise --gap), and two sentences read without a pause come out as one (lower --gap).
"""
import sys

import numpy as np
import soundfile as sf


def phrases(x, sr, gap=0.35, floor_db=-38.0):
    hop = sr // 100                                             # 10 ms frames
    n = len(x) // hop
    if n == 0:
        return []
    rms = np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1))
    loud = rms > rms.max() * 10 ** (floor_db / 20)
    out, start, quiet = [], None, 0
    for i, on in enumerate(loud):
        if on:
            start, quiet = (i if start is None else start), 0
        elif start is not None:
            quiet += 1
            if quiet * 0.01 > gap:
                out.append((start * 0.01, (i - quiet + 1) * 0.01))
                start, quiet = None, 0
    if start is not None:
        out.append((start * 0.01, (n - quiet) * 0.01))
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0].startswith("--"):
        sys.exit(__doc__)
    gap = float(a[a.index("--gap") + 1]) if "--gap" in a else 0.35
    floor = float(a[a.index("--floor") + 1]) if "--floor" in a else -38.0
    x, sr = sf.read(a[0], dtype="float32")
    if x.ndim > 1:
        x = x.mean(1)
    found = phrases(x, sr, gap, floor)
    for i, (s, e) in enumerate(found, 1):
        print(f"{i:3d}  ({s:.2f}, {e:.2f})   {e - s:.2f} s")
    print(f"{len(found)} phrases in {len(x) / sr:.1f} s at {sr} Hz" + ("" if sr == 48000 else "  (build_tl.py needs 48000 Hz mono: convert it first)"))
