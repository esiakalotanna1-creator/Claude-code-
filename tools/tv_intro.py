"""House rule 1 (see CLAUDE.md): every video opens on an old TV with static, under 1 second, blended into the first
shot. Draws a CRT set (bezel, knobs, curved glass) full of static, zooms into the screen and cross-fades into the
video, with a static crackle on the audio.

    python tools/tv_intro.py in.mp4 out.mp4 [--len 0.75] [--blend 0.3]
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

import numpy as np
import skia
import soundfile as sf

FPS = 30


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate",
                        "-of", "json", path], capture_output=True, text=True, check=True)
    s = json.loads(r.stdout)["streams"][0]
    n, d = s["r_frame_rate"].split("/")
    return s["width"], s["height"], float(n) / float(d)


def tv_frame(W, H, i, n, rng):
    u = i / max(1, n - 1)
    zoom = 1.0 + 1.6 * (u ** 2.2)                              # pushes into the screen at the end
    surf = skia.Surface(W, H)
    c = surf.getCanvas()
    c.clear(skia.Color(14, 11, 9))
    sw, sh = W * 0.78, W * 0.78 * 0.82                           # the 4:3-ish curved screen
    cx, cy = W / 2, H * 0.45
    c.translate(cx, cy)
    c.scale(zoom, zoom)
    c.translate(-cx, -cy)
    body = skia.Rect(cx - sw / 2 - 70, cy - sh / 2 - 70, cx + sw / 2 + 70, cy + sh / 2 + 260)
    p = skia.Paint(AntiAlias=True)
    p.setShader(skia.GradientShader.MakeLinear([skia.Point(0, body.top()), skia.Point(0, body.bottom())],
                                               [skia.Color(92, 70, 50), skia.Color(52, 38, 28)]))
    c.drawRRect(skia.RRect.MakeRectXY(body, 60, 60), p)
    c.drawRRect(skia.RRect.MakeRectXY(body, 60, 60), skia.Paint(AntiAlias=True, Color=skia.Color(20, 14, 10), Style=skia.Paint.kStroke_Style, StrokeWidth=6))
    scr = skia.Rect(cx - sw / 2, cy - sh / 2, cx + sw / 2, cy + sh / 2)
    c.drawRRect(skia.RRect.MakeRectXY(scr.makeOutset(22, 22), 70, 70), skia.Paint(AntiAlias=True, Color=skia.Color(24, 22, 20)))
    # static: blocky noise, a rolling bright band, scanlines
    nw, nh = int(sw / 4), int(sh / 4)
    g = rng.integers(0, 255, (nh, nw), dtype=np.uint8).astype(np.float32)
    band = (np.arange(nh) / nh - (i * 0.11) % 1.0)
    g += 90 * np.exp(-(band * 9) ** 2)[:, None]
    g[::2] *= 0.7
    g = np.clip(g, 0, 255).astype(np.uint8)
    img = skia.Image.fromarray(np.ascontiguousarray(np.dstack([g, g, g, np.full_like(g, 255)])), colorType=skia.kRGBA_8888_ColorType)
    path = skia.Path()
    path.addRRect(skia.RRect.MakeRectXY(scr, 64, 64))
    c.save()
    c.clipPath(path, skia.ClipOp.kIntersect, True)
    c.drawImageRect(img, scr, skia.SamplingOptions(skia.FilterMode.kNearest))
    vg = skia.Paint()
    vg.setShader(skia.GradientShader.MakeRadial(skia.Point(cx, cy), sw * 0.62, [skia.Color4f(0, 0, 0, 0), skia.Color4f(0, 0, 0, 0.75)], [0.55, 1.0]))
    c.drawRect(scr, vg)
    gl = skia.Paint(AntiAlias=True, Color=skia.Color4f(1, 1, 1, 0.10))
    c.drawOval(skia.Rect(scr.left() + sw * 0.08, scr.top() + sh * 0.05, scr.left() + sw * 0.55, scr.top() + sh * 0.3), gl)
    c.restore()
    for k, kx in enumerate((cx + sw / 2 - 90, cx + sw / 2 - 230)):   # knobs and the speaker grille
        ky = cy + sh / 2 + 150
        c.drawCircle(kx, ky, 46, skia.Paint(AntiAlias=True, Color=skia.Color(30, 24, 20)))
        c.drawCircle(kx, ky, 38, skia.Paint(AntiAlias=True, Color=skia.Color(70, 62, 54)))
        c.drawLine(kx, ky, kx + 30 * np.cos(i * 0.3 + k), ky + 30 * np.sin(i * 0.3 + k), skia.Paint(AntiAlias=True, Color=skia.Color(20, 16, 12), StrokeWidth=6))
    for j in range(7):
        y = cy + sh / 2 + 100 + j * 18
        c.drawLine(cx - sw / 2 + 40, y, cx - sw / 2 + 360, y, skia.Paint(AntiAlias=True, Color=skia.Color(30, 22, 16), StrokeWidth=7))
    a = surf.makeImageSnapshot().toarray(colorType=skia.ColorType.kRGBA_8888_ColorType)[:, :, :3]
    return np.ascontiguousarray(a)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--len", type=float, default=0.75)
    ap.add_argument("--blend", type=float, default=0.3)
    o = ap.parse_args()
    assert o.len < 1.0, "house rule: the intro stays under 1 second"
    W, H, fps = probe(o.src)
    n = int(round(o.len * fps))
    rng = np.random.default_rng(7)
    tmp = tempfile.mkdtemp()
    intro_v, intro_a = os.path.join(tmp, "intro.mp4"), os.path.join(tmp, "intro.wav")
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps),
                          "-i", "-", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", intro_v], stdin=subprocess.PIPE)
    for i in range(n):
        p.stdin.write(tv_frame(W, H, i, n, rng).tobytes())
    p.stdin.close()
    if p.wait():
        sys.exit("ffmpeg failed (intro)")
    sr = 48000
    m = int(o.len * sr)
    s = rng.standard_normal(m) * 0.25
    s *= 1 + 2.5 * (rng.random(m) > 0.9985)                       # crackle
    s *= np.minimum(1, np.arange(m) / (0.02 * sr))
    sf.write(intro_a, np.stack([s, s], 1).astype(np.float32), sr)
    off = o.len - o.blend
    fc = (f"[0:v]fps={fps},format=yuv420p,setsar=1[a];[1:v]fps={fps},format=yuv420p,setsar=1[b];"
          f"[a][b]xfade=transition=fade:duration={o.blend}:offset={off:.3f}[v];"
          f"[2:a]aformat=sample_rates=48000:channel_layouts=stereo[x];[1:a]aformat=sample_rates=48000:channel_layouts=stereo[y];"
          f"[x][y]acrossfade=d={o.blend}:c1=tri:c2=tri[au]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", intro_v, "-i", o.src, "-i", intro_a, "-filter_complex", fc,
                    "-map", "[v]", "-map", "[au]", "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", o.dst], check=True)
    print(o.dst)


if __name__ == "__main__":
    main()
