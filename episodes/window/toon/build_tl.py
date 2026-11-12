"""Cut the narration phrases out of the take (script.SOURCE) and place them on the reel:
audio/narration.wav (48 kHz) + timeline.json (total, marks, lines with caption chunks)."""
import json
import os

import numpy as np
import soundfile as sf

import script as S

HERE = os.path.dirname(os.path.abspath(__file__))
SR = 48000
_take = os.path.join(HERE, S.SOURCE)
if not os.path.exists(_take):
    raise SystemExit(f"no narration take at {_take}: record or generate one (48 kHz mono wav), or keep the shipped timeline.json")
src, sr = sf.read(_take, dtype="float32")
assert sr == SR, f"{S.SOURCE} must be {SR} Hz, it is {sr} Hz"
total = S.MARKS["end"]
out = np.zeros(int(total * SR) + SR, dtype=np.float32)
lines = []
prev_end = -1.0
for a, b, t, text, chunks in S.PHRASES:
    seg = src[int((a - 0.06) * SR):int((b + 0.12) * SR)].copy()
    f = int(0.012 * SR)
    seg[:f] *= np.linspace(0, 1, f)
    seg[-f:] *= np.linspace(1, 0, f)
    i0 = int((t - 0.06) * SR)
    assert t > prev_end + 0.15, f"overlap at {text}"
    out[i0:i0 + len(seg)] += seg
    prev_end = t + (b - a)
    # caption chunks: time split by letters (short phrases, close enough to the words)
    n = [len(c.replace("[", "").replace("]", "")) for c in chunks]
    dur, ct, ch = b - a, t, []
    for c, k in zip(chunks, n):
        d = dur * k / sum(n)
        ch.append(dict(text=c, t0=round(ct, 3), t1=round(ct + d, 3)))
        ct += d
    lines.append(dict(speaker="NAR", text=text, t0=round(t, 3), t1=round(t + dur, 3), chunks=ch))
out = out[:int(total * SR)]
peak = np.abs(out).max()
out *= 10 ** (-1.0 / 20) / peak                    # -1 dBFS peak; the mix sets the level
sf.write(os.path.join(HERE, "audio", "narration.wav"), out, SR)
os.makedirs(os.path.join(HERE, "video", "audio"), exist_ok=True)
sf.write(os.path.join(HERE, "video", "audio", "narration.wav"), out, SR)
json.dump(dict(total=total, marks=S.MARKS, lines=lines), open(os.path.join(HERE, "timeline.json"), "w", encoding="utf-8"), indent=1)
for L in lines:
    print(f"{L['t0']:6.2f}-{L['t1']:6.2f}  {L['text']}")
print("total", total)
