"""Mix the stems and mux them onto a silent render.

    python finalize.py preview     review/reel_preview.mp4 + mix -> review/preview.mp4
    python finalize.py final       video/reel_silent.mp4 + mix -> video/final.mp4 (through tools/finish.py: -14 LUFS)
Add a stem (a bleep track, a second voice) by adding its name to STEMS.
"""
import os
import subprocess
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
STEMS = ("narration", "music", "sfx", "ambience")


def rd(name):
    p = os.path.join(HERE, "video", "audio", name + ".wav")
    if not os.path.exists(p):
        sys.exit(f"missing stem {name}.wav: run build_tl.py (narration) and tools/sound.py (music, sfx, ambience) first")
    s, sr = sf.read(p, dtype="float32")
    return (s.mean(1) if s.ndim > 1 else s), sr


def mix():
    stems = [rd(n) for n in STEMS]
    sr = stems[0][1]
    n = max(len(s) for s, _ in stems)
    out = sum(np.pad(s, (0, n - len(s))) for s, _ in stems)
    peak = np.abs(out).max()
    if peak > 0.98:
        out = out * (0.98 / peak)
    wav = os.path.join(HERE, "video", "mix.wav")
    sf.write(wav, out.astype(np.float32), sr)
    return wav


def main(which):
    silent = os.path.join(HERE, "review", "reel_preview.mp4") if which == "preview" else os.path.join(HERE, "video", "reel_silent.mp4")
    if not os.path.exists(silent):
        sys.exit(f"no picture at {silent}: run  python reel.py {'--preview --full' if which == 'preview' else '--master-par 8'}  first")
    wav = mix()
    out = os.path.join(HERE, "review", "preview.mp4") if which == "preview" else os.path.join(HERE, "video", "master.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", out], check=True)
    if which != "preview":
        muxed, out = out, os.path.join(HERE, "video", "final.mp4")
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "finish.py"), muxed, out], check=True)
    print(out, os.path.getsize(out) // 1024, "KB")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "preview")
