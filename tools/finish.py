"""Final export for Instagram Reels / TikTok / YouTube Shorts.

    python tools/finish.py <master.mp4> <out.mp4>

- Audio: limiter + two-pass loudnorm to -14 LUFS integrated, <= -2 dBTP, AAC 192k / 48 kHz.
- Video: re-encoded to H.264 High@4.1, 1080x1920, 30 fps CFR, yuv420p, BT.709 tagged, CRF 16
  (about 10-20 Mbit/s for these shorts), 1 s GOP, +faststart. Platforms re-encode every upload; a clean,
  properly tagged, standard-GOP source survives that re-encode with the least softening.
"""
import json
import re
import shutil
import subprocess
import sys

FF = shutil.which("ffmpeg") or "ffmpeg"
LIM = "alimiter=limit=0.5:attack=2:release=60:level=false,"


def measure(path, pre=""):
    r = subprocess.run([FF, "-hide_banner", "-i", path, "-af", pre + "loudnorm=I=-14:TP=-2:LRA=11:print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return json.loads(re.findall(r"\{[^{}]*\}", r.stderr)[-1])


def main(src, dst):
    m = measure(src, LIM)
    af = (LIM + f"loudnorm=I=-14:TP=-2.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,"
          "aresample=48000")
    vf = "scale=1080:1920:flags=neighbor,setsar=1,format=yuv420p"
    subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", "-i", src,
                    "-vf", vf, "-r", "30", "-fps_mode", "cfr",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-profile:v", "high", "-level:v", "4.1",
                    "-g", "30", "-keyint_min", "30", "-sc_threshold", "0", "-bf", "2",
                    "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
                    "-af", af, "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                    "-movflags", "+faststart", dst], check=True, stdin=subprocess.DEVNULL)
    k = measure(dst)
    print("final", dst, "I", k["input_i"], "LUFS  TP", k["input_tp"], "dBTP")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
