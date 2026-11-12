"""script.py BEATS -> timeline.json + audio/narration.wav (all voices on one stem).

Beats are laid end to end: start = previous end + gap_before; a voiced beat lasts its take (audio/lines/<id>.wav),
or an estimate when the take is missing; SCREEN beats last extra["dur"]. "hold" adds picture after a line.
    python build_tl.py
"""
import json
import os

import numpy as np
import soundfile as sf

import script as S

HERE = os.path.dirname(os.path.abspath(__file__))
SR = 48000
lines, beats, t = [], {}, 0.0
takes = {}
for bid, spk, text, chunks, gap, ex in S.BEATS:
    t += gap
    if spk == "SCREEN":
        dur, have = ex["dur"], True
    else:
        p = os.path.join(HERE, "audio", "lines", bid + ".wav")
        have = os.path.exists(p)
        if have:
            a, sr = sf.read(p, dtype="float32")
            assert sr == SR
            takes[bid] = (t, a)
            dur = len(a) / SR
        else:
            dur = 0.30 + 0.36 * len(text.split())
    t0, t1 = t, t + dur
    beats[bid] = dict(speaker=spk, t0=round(t0, 3), t1=round(t1, 3), text=text)
    if chunks:
        n = [len(c.replace("[", "").replace("]", "")) for c in chunks]
        ct, ch = t0, []
        for c, kk in zip(chunks, n):
            d = dur * kk / sum(n)
            ch.append(dict(text=c, t0=round(ct, 3), t1=round(ct + d, 3)))
            ct += d
        lines.append(dict(id=bid, speaker=spk, text=text, t0=round(t0, 3), t1=round(t1, 3), chunks=ch))
    t = t1 + ex.get("hold", 0.0)
total = round(t + 0.5, 3)
out = np.zeros(int(total * SR) + SR, dtype=np.float32)
for bid, (t0, a) in takes.items():
    i0 = int(t0 * SR)
    out[i0:i0 + len(a)] += a[:len(out) - i0]
out = out[:int(total * SR)]
peak = np.abs(out).max()
if peak > 0:
    out *= 10 ** (-1.0 / 20) / peak
for d in ("audio", os.path.join("video", "audio")):
    os.makedirs(os.path.join(HERE, d), exist_ok=True)
    sf.write(os.path.join(HERE, d, "narration.wav"), out, SR)
json.dump(dict(title=S.TITLE, label=S.LABEL, total=total, beats=beats, lines=lines, marks={k: v['t0'] for k, v in beats.items()}),
          open(os.path.join(HERE, "timeline.json"), "w", encoding="utf-8"), indent=1)
print(f"timeline.json: {len(beats)} beats, {len(takes)} takes, total {total:.1f}s")
