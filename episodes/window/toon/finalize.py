"""Mix the four stems and mux them onto a silent render.

    py finalize.py preview     -> review/preview.mp4   (review/reel_preview.mp4 + mix)
    py finalize.py final       -> video/window_final.mp4 (video/reel_silent.mp4 + mix, through tools/finish.py)
"""
import os
import subprocess
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))


def rd(name):
    p = os.path.join(HERE, "video", "audio", name + ".wav")
    if not os.path.exists(p):
        p = os.path.join(HERE, "audio", name + ".wav")
    if not os.path.exists(p):
        raise SystemExit(f"missing stem {name}.wav: run build_tl.py (narration) and tools/sound.py (music, sfx, ambience) first")
    s, sr = sf.read(p, dtype="float32")
    return (s.mean(1) if s.ndim > 1 else s), sr


def mix():
    stems = [rd(n) for n in ("narration", "music", "sfx", "ambience")]
    sr = stems[0][1]
    n = max(len(s) for s, _ in stems)
    out = sum(np.pad(s, (0, n - len(s))) for s, _ in stems)
    peak = np.abs(out).max()
    if peak > 0.98:
        out = out * (0.98 / peak)
    wav = os.path.join(HERE, "video", "mix.wav")
    os.makedirs(os.path.dirname(wav), exist_ok=True)
    sf.write(wav, out.astype(np.float32), sr)
    return wav


def main(which):
    wav = mix()
    if which == "preview":
        silent, out = os.path.join(HERE, "review", "reel_preview.mp4"), os.path.join(HERE, "review", "preview.mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                        "-c:a", "aac", "-b:a", "160k", "-shortest", out], check=True)
    else:
        silent, muxed = os.path.join(HERE, "video", "reel_silent.mp4"), os.path.join(HERE, "video", "master.mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                        "-c:a", "aac", "-b:a", "192k", "-shortest", muxed], check=True)
        out = os.path.join(HERE, "video", "window_final.mp4")
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "finish.py"), muxed, out], check=True)
    print(out, os.path.getsize(out) // 1024, "KB")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "preview")
