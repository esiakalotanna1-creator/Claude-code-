"""THE LAMP: the reel. Shots are in SHOTS; everything else here is generic and can stay as it is in a new episode.

    python reel.py --frame T [scale]   one frame (default half size) -> review/_f<T>.png
    python reel.py --stills            first/mid/last frame of every shot -> review/shots.png
    python reel.py --sheet S1 S2 ...   every frame of the named shots on gapped sheets -> review/all_<shot>.png  (--half: every 2nd)
    python reel.py --check             constraint + caption checks over every frame -> review/reel_checks.txt
    python reel.py --preview [--full]  silent preview, 540x960 or 1080x1920 -> review/reel_preview.mp4
    python reel.py --master-par N      HQ master 1080x1920 on N processes -> video/reel_silent.mp4
"""
import json
import math
import os
import subprocess
import sys

import numpy as np
import skia
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scenes as S  # noqa: E402  (puts tools/toon on the path)
import rig  # noqa: E402
import toon as TN  # noqa: E402
from toon import Camera, Frame, W, H, paint  # noqa: E402

FPS = 30
OUT, VID = os.path.join(HERE, "review"), os.path.join(HERE, "video")
if not os.path.exists(os.path.join(HERE, "timeline.json")):
    sys.exit("no timeline.json yet: run  python build_tl.py  first")
TL = json.load(open(os.path.join(HERE, "timeline.json"), encoding="utf-8"))
TOTAL, M = round(TL["total"], 3), TL["marks"]
WORLD = S.Room(M)
EASE = {"lin": lambda u: u, "io": lambda u: u * u * (3 - 2 * u), "out": lambda u: 1 - (1 - u) ** 3,
        "smooth": lambda u: u ** 3 * (u * (6 * u - 15) + 10)}


def _lerp(x, y, u):
    return tuple(p + (q - p) * u for p, q in zip(x, y)) if isinstance(x, tuple) else x + (y - x) * u


def track(a, b, ease="smooth"):
    """One clean camera move. a, b = (position, target, focal length px, horizon). The camera turns (yaw) to face the
    target; it cannot tilt, so the target's height is ignored: frame up or down with the position and the horizon
    (a smaller horizon puts the eye line higher in the frame, which reads as looking down)."""
    def f(T, t0, t1):
        u = EASE[ease](min(1.0, max(0.0, (T - t0) / max(1e-6, t1 - t0))))
        pos, tgt, fl, hz = (_lerp(a[i], b[i], u) for i in range(4))
        return Camera(pos, math.degrees(math.atan2(tgt[0] - pos[0], tgt[2] - pos[2])), fl, hz)
    return f


HEAD = rig.solve("nora", WORLD.nora(4.0))["head"]              # write each camera from its target: where the face will be
DOOR_X = (S.DOOR[0][0] + S.DOOR[0][1]) / 2

# name, start, end, camera, opts (cap = (y, size): where the caption goes in this shot)
SHOTS = [
    # the hook: the whole room, already pushing in
    ("WIDE", M["wide"], M["close"], track(((0.2, 1.30, -2.4), (0.2, 1.1, 2.4), 1250, 0.44), ((0.2, 1.28, -2.0), (0.2, 1.1, 2.4), 1380, 0.44)), {}),
    # her face, within 35 degrees of her eyeline; the lamp is just off screen right
    ("CLOSE", M["close"], M["door"], track(((0.38, 1.52, 0.92), HEAD, 1950, 0.42), ((0.36, 1.52, 0.98), HEAD, 2120, 0.42), "lin"), {}),
    # over her shoulder to the door
    ("DOOR", M["door"], M["feet"], track(((-1.45, 1.55, 1.0), (DOOR_X - 0.15, 1.0, S.RZ), 1380, 0.44), ((-1.38, 1.55, 1.08), (DOOR_X - 0.15, 1.0, S.RZ), 1480, 0.44)),
     dict(cap=(1470, 66))),                                # the caption clears her hand
    # low, on the light under the door
    ("FEET", M["feet"], M["end"], track(((1.2, 0.42, 1.4), (DOOR_X, 0.1, S.RZ), 1750, 0.34), ((1.22, 0.40, 1.5), (DOOR_X, 0.1, S.RZ), 1900, 0.34), "lin"),
     dict(cap=(1500, 66))),
]


def shot_at(T):
    for s in SHOTS:
        if s[1] <= T < s[2]:
            return s
    return SHOTS[-1]


# ---- text ----------------------------------------------------------------------------------------------------
CHUNKS = sorted([c for L in TL["lines"] for c in L["chunks"]], key=lambda c: c["t0"])
CAP_Y, CAP_SIZE = 1640, 66
TF = TN.typeface()
LABEL_T = (0.3, 2.8)


def caption(T):
    cur = None
    for c in CHUNKS:
        if c["t0"] <= T + 1e-6:
            cur = c
    return cur["text"] if cur and T < cur["t1"] + 0.45 else None


def caption_box(text, y, size):
    w = skia.Font(TF, size).measureText(text.replace("[", "").replace("]", "")) + 16
    return ((W - w) / 2, y - size * 0.73, (W + w) / 2, y + size * 0.33)


def draw_caption(fr, text, y, size):
    f = skia.Font(TF, size)
    parts = [(b.strip("[]"), b.startswith("[")) for b in text.replace("[", "|[").replace("]", "]|").split("|") if b]
    x = (W - sum(f.measureText(p) for p, _ in parts)) / 2
    for p, key in parts:
        blob = skia.TextBlob(p, f)
        fr.c.drawTextBlob(blob, x, y, paint("#000000", stroke=size * 0.18))
        fr.c.drawTextBlob(blob, x, y, paint("#FF4D4D" if key else "#F4F1EA"))
        x += f.measureText(p)


def draw_label(fr, T):
    a0, a1 = LABEL_T
    if TL.get("label") and a0 <= T < a1:
        a = min(1.0, (T - a0) / 0.3, (a1 - T) / 0.3)
        f = skia.Font(TF, 36)
        blob = skia.TextBlob(TL["label"], f)
        x = (W - f.measureText(TL["label"])) / 2
        fr.c.drawTextBlob(blob, x, 300, paint("#000000", a=a, stroke=7))
        fr.c.drawTextBlob(blob, x, 300, paint("#E8E8E8", a=a))


# ---- frames --------------------------------------------------------------------------------------------------
def render(T, scale=1.0, captions=True, log=None):
    """-> (shot name, HxWx3 uint8). Frames depend only on T."""
    name, t0, t1, camf, opt = shot_at(T)
    cam = camf(T, t0, t1)
    fr = Frame(scale)
    outs = WORLD.draw(fr, cam, T)
    if log is not None:
        for (pid, look, pose) in WORLD.cast(T):
            log.append(dict(t=T, shot=name, pid=pid, pose=pose, o=outs.get(pid, {}), J=rig.solve(look, pose), cam=cam))
    draw_label(fr, T)
    if captions:
        c = caption(T)
        if c:
            draw_caption(fr, c, *opt.get("cap", (CAP_Y, CAP_SIZE)))
    return name, fr.array()


def frames_of(a, b):
    return [i / FPS for i in range(int(round(a * FPS)), int(round(b * FPS)))]


# ---- checks: every hit is an ANOMALY line ------------------------------------------------------------------
def _angle(a, b):
    return math.degrees(math.acos(max(-1.0, min(1.0, rig.dot(rig.norm(a), rig.norm(b))))))


def check():
    log = []
    for name, a, b, _, _ in SHOTS:
        for t in frames_of(a, b):
            render(t, 0.25, log=log)
        print("checked", name, flush=True)
    hits = {}

    def hit(shot, pid, what, t, msg):
        h = hits.setdefault((shot, pid, what), [t, t, msg])
        h[0], h[1] = min(h[0], t), max(h[1], t)

    prev = {}
    for r in log:
        J, t, shot, pid, o = r["J"], r["t"], r["shot"], r["pid"], r["o"]
        if o.get("culled"):                                       # rig.draw skips anyone within 0.45 m of the lens
            vx, _, vz = r["cam"].view(J["pelvis"])
            if vz > 0.05 and abs(vx) < 540 / r["cam"].f * vz + 0.3:          # only a problem if they would be in view
                hit(shot, pid, "culled", t, "closer than 0.45 m to the lens and in view, so not drawn: move the camera back")
            continue
        floor = r["pose"].get("floor", 0.0)
        for s in "RL":
            for k in ("arm_" + s, "leg_" + s):
                if J["err"].get(k, 0) > 0.02:
                    hit(shot, pid, "reach short " + k, t, f"{k} target {J['err'][k] * 100:.0f} cm out of reach")
            ay = J["ank_" + s][1] - floor - 0.035 * J["h"]
            if ay < -0.003:
                hit(shot, pid, "foot sinks " + s, t, f"ankle_{s} {ay * 1000:.0f} mm into the floor")
            up, fo = rig.sub(J["el_" + s], J["sh_" + s]), rig.sub(J["wr_" + s], J["el_" + s])
            if _angle(up, fo) > 155:
                hit(shot, pid, "elbow over-bent " + s, t, f"elbow_{s} {_angle(up, fo):.0f} deg")
            P = prev.get((shot, pid))
            if P is not None:
                for lab, a1, b1, a0, b0 in (("elbow", up, fo, rig.sub(P["el_" + s], P["sh_" + s]), rig.sub(P["wr_" + s], P["el_" + s])),
                                            ("knee", rig.sub(J["kn_" + s], J["hip_" + s]), rig.sub(J["ank_" + s], J["kn_" + s]),
                                             rig.sub(P["kn_" + s], P["hip_" + s]), rig.sub(P["ank_" + s], P["kn_" + s]))):
                    if _angle(a1, b1) > 12 and _angle(a0, b0) > 12 and rig.dot(rig.cross(a1, b1), rig.cross(a0, b0)) < 0:
                        hit(shot, pid, f"{lab} flip {s}", t, f"{lab}_{s} bend plane flipped between frames")
                step = math.dist(P["pelvis"], J["pelvis"])
                if step > 0.12:
                    hit(shot, pid, "jump", t, f"pelvis moved {step * 100:.0f} cm in one frame")
        prev[(shot, pid)] = J
        c = caption(t)
        if c:
            opt = shot_at(t)[4]
            x0, y0, x1, y1 = caption_box(c, *opt.get("cap", (CAP_Y, CAP_SIZE)))
            for what, pt, rr in (("face", o.get("head"), o.get("head_r", 0)), ("hand_R", o.get("hand_R"), 30), ("hand_L", o.get("hand_L"), 30)):
                if pt and x0 - rr < pt[0] < x1 + rr and y0 - rr < pt[1] < y1 + rr and -50 < pt[0] < W + 50:
                    hit(shot, pid, "caption over " + what, t, f"'{c}' covers the {what}: move the caption (cap=) or the camera")
    rep = [f"ANOMALY {shot} {ta:.2f}-{tb:.2f}s {pid}: {what}: {msg}" for (shot, pid, what), (ta, tb, msg) in sorted(hits.items(), key=lambda kv: kv[1][0])]
    rep.append(f"{len(hits)} anomalies in {len(log)} person-frames. This is code only: now look at --stills and --sheet.")
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "reel_checks.txt"), "w", encoding="utf-8").write("\n".join(rep) + "\n")
    print("\n".join(rep))


# ---- sheets --------------------------------------------------------------------------------------------------
def label(im, text):
    d = ImageDraw.Draw(im)
    d.rectangle((0, im.height - 22, im.width, im.height), fill=(0, 0, 0))
    d.text((6, im.height - 18), text, fill=(255, 255, 0))
    return im


def sheet(tiles, path, cols=6, gap=8):
    w, h = tiles[0].size
    rows = (len(tiles) + cols - 1) // cols
    im = Image.new("RGB", (cols * (w + gap) + gap, rows * (h + gap) + gap), (24, 24, 28))
    for i, t in enumerate(tiles):
        im.paste(t, (gap + (i % cols) * (w + gap), gap + (i // cols) * (h + gap)))
    os.makedirs(OUT, exist_ok=True)
    im.save(path)
    print(path)


def stills():
    tiles = []
    for name, a, b, _, _ in SHOTS:
        ts = frames_of(a, b)
        tiles += [label(Image.fromarray(render(t, 0.3)[1]), f"{name} {lab} {t:.2f}s") for lab, t in (("first", ts[0]), ("mid", ts[len(ts) // 2]), ("last", ts[-1]))]
    sheet(tiles, os.path.join(OUT, "shots.png"), cols=6)


def sheets(names, step=1):
    known = [s[0] for s in SHOTS]
    for n in names:
        if n not in known:
            sys.exit(f"no shot named {n!r}: the shots are {', '.join(known)}")
    for name, a, b, _, _ in SHOTS:
        if name in names:
            sheet([label(Image.fromarray(render(t, 0.2)[1]), f"{t:.2f}") for t in frames_of(a, b)[::step]], os.path.join(OUT, f"all_{name}.png"), cols=10)


# ---- video ---------------------------------------------------------------------------------------------------
def downsample(a, rng=np.random.default_rng(7)):
    h, w = a.shape[0] // 2, a.shape[1] // 2
    f = a.astype(np.float32).reshape(h, 2, w, 2, 3).mean((1, 3))
    f += rng.random(f.shape, dtype=np.float32) - rng.random(f.shape, dtype=np.float32)      # dither: no banding in the gradients
    return np.clip(np.rint(f), 0, 255).astype(np.uint8)


def encode(frames, path, size, crf="16", preset="medium"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", size, "-r", str(FPS),
                          "-i", "-", "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
                          "-c:v", "libx264", "-crf", crf, "-preset", preset, "-tune", "animation",
                          "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv", path],
                         stdin=subprocess.PIPE)
    for a in frames:
        p.stdin.write(np.ascontiguousarray(a).tobytes())
    p.stdin.close()
    if p.wait():
        sys.exit("ffmpeg failed")


if __name__ == "__main__":
    a = sys.argv[1:]
    pos = [x for x in a if not x.startswith("--")]
    if "--frame" in a:
        if not pos:
            sys.exit("usage: python reel.py --frame <seconds> [scale]")
        t = float(pos[0])
        os.makedirs(OUT, exist_ok=True)
        Image.fromarray(render(t, float(pos[1]) if len(pos) > 1 else 0.5)[1]).save(os.path.join(OUT, f"_f{t:.2f}.png"))
        print(os.path.join(OUT, f"_f{t:.2f}.png"))
    elif "--stills" in a:
        stills()
    elif "--sheet" in a:
        sheets(pos, step=2 if "--half" in a else 1)
    elif "--check" in a:
        check()
    elif "--preview" in a:
        full = "--full" in a
        encode((render(t, 1.0 if full else 0.5)[1] for t in frames_of(0, TOTAL)), os.path.join(OUT, "reel_preview.mp4"), "1080x1920" if full else "540x960")
        print(os.path.join(OUT, "reel_preview.mp4"))
    elif "--master-part" in a:                                   # one contiguous chunk of the master (see --master-par)
        k, n = int(pos[0]), int(pos[1])
        fr = frames_of(0, TOTAL)
        L = -(-len(fr) // n)
        TN.HQ["on"] = True
        encode((downsample(render(t, 2.0)[1]) for t in fr[k * L:(k + 1) * L]), os.path.join(VID, f"_part{k:02d}.mp4"), f"{W}x{H}", crf="10", preset="slow")
    elif "--master-par" in a:                                    # the master on n processes; frames are order-independent
        n = int(a[a.index("--master-par") + 1])
        os.makedirs(VID, exist_ok=True)
        procs = [subprocess.Popen([sys.executable, os.path.abspath(__file__), "--master-part", str(k), str(n)]) for k in range(n)]
        if any([p.wait() for p in procs]):                       # wait for all of them, then fail
            sys.exit("a master part failed")
        lst = os.path.join(VID, "_parts.txt")
        open(lst, "w").write("".join(f"file '_part{k:02d}.mp4'\n" for k in range(n)))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", os.path.join(VID, "reel_silent.mp4")], check=True)
        for k in range(n):
            os.remove(os.path.join(VID, f"_part{k:02d}.mp4"))
        os.remove(lst)
        print(os.path.join(VID, "reel_silent.mp4"))
    else:
        print(__doc__)
