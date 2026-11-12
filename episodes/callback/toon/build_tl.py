"""script.py -> timeline.json (total, marks, lines with caption chunks) + audio/narration.wav.

With a narration take (script.SOURCE) and a source span on every phrase, the phrases are cut out of the take and
placed on the reel. Without one, each phrase's length is estimated from its word count and narration.wav is
silent, so the picture, captions and sound beds can be built first.    python build_tl.py
"""
import json
import os

import numpy as np
import soundfile as sf

import script as S

HERE = os.path.dirname(os.path.abspath(__file__))
SR = 48000
total = S.MARKS["end"]
take = os.path.join(HERE, S.SOURCE)
have_take = os.path.exists(take) and all(p[3] for p in S.PHRASES)
if have_take:
    src, sr = sf.read(take, dtype="float32")
    assert sr == SR and src.ndim == 1, f"{S.SOURCE} must be {SR} Hz mono"

out = np.zeros(int(total * SR), dtype=np.float32)
lines, prev_end = [], -1.0
for t, text, chunks, span in S.PHRASES:
    if have_take:
        a, b = span
        seg = src[int((a - 0.06) * SR):int((b + 0.12) * SR)].copy()
        f = int(0.012 * SR)
        seg[:f] *= np.linspace(0, 1, f)
        seg[-f:] *= np.linspace(1, 0, f)
        i0 = int((t - 0.06) * SR)
        out[i0:i0 + len(seg)] += seg[:len(out) - i0]
        dur = b - a
    else:
        dur = 0.30 + 0.34 * len(text.split())             # an unhurried narrator; replaced by the real take later
    assert t > prev_end + 0.15, f"'{text}' starts before the previous phrase has ended"
    assert t + dur <= total, f"'{text}' runs past the end of the reel"
    prev_end = t + dur
    n = [len(c.replace("[", "").replace("]", "")) for c in chunks]      # caption time split by letters
    ct, ch = t, []
    for c, k in zip(chunks, n):
        d = dur * k / sum(n)
        ch.append(dict(text=c, t0=round(ct, 3), t1=round(ct + d, 3)))
        ct += d
    lines.append(dict(speaker="NAR", text=text, t0=round(t, 3), t1=round(t + dur, 3), chunks=ch))

peak = np.abs(out).max()
if peak > 0:
    out *= 10 ** (-1.0 / 20) / peak                    # -1 dBFS peak; the mix sets the level
for d in ("audio", os.path.join("video", "audio")):
    os.makedirs(os.path.join(HERE, d), exist_ok=True)
    sf.write(os.path.join(HERE, d, "narration.wav"), out, SR)
json.dump(dict(title=S.TITLE, label=S.LABEL, total=total, marks=S.MARKS, lines=lines),
          open(os.path.join(HERE, "timeline.json"), "w", encoding="utf-8"), indent=1)
print("timeline.json:", len(lines), "lines,", "from the take" if have_take else "estimated timings (no take yet), silent narration.wav")
