# Example: The Man at the Window

A 50 s straight-horror reel in 13 shots. Night and rain. A man stands smiling at a window, and the narrator is
the father inside. The twist: the camera pushes into the stranger's face until it fills the frame, both worlds
swap inside the close-up, and the pull-back shows the father was outside all along.

- `SPEC.md`: the shot-by-shot brief it was built from. `SCRIPT.md`: narration and shot table. `POST.md`: post copy.
- `scenes.py`: the house front, the lamp-lit living room and the upstairs bedroom, with three-layer lighting.
  The "belief" world is the "truth" world rotated 180 deg about the pane, which is what makes the swap exact.
- `looks.py`: the cast (the father, the stranger, the wife, the baby). `textures.py`: procedural brick,
  lawn, soil and hedge.
- `reel.py`: the `SHOTS` table, the twist camera (`twist_world`), captions and the checks.

## What `--check` reports here

`python reel.py --check` prints 7 `ANOMALY` lines, all in shot `PU` at 39.47 s (the stranger) and 40.63 s (the
father). They are the world swap itself: the two worlds are mirror images, so comparing one frame with the
next reads as elbow and knee bend planes flipping. Nothing shows on screen, because the swap happens behind
the full-frame face and the father is out of frame until about 40.8 s. Any other anomaly is a real one.

## It ships silent

The original narration was a paid TTS take and is not included. `timeline.json` keeps the line timings, so
the picture and captions render exactly as cut. To give it a voice:

1. Record or generate the narration as one take, at 48 kHz mono, and save it as `audio/narration_take.wav`
   (or change `SOURCE` in `script.py`).
2. Set each phrase's `(src start, src end)` in `script.py` `PHRASES` to where it sits in your take. Leave
   the `placed at` times alone, so the cut keeps its timing.
3. `python build_tl.py` -> `audio/narration.wav` + a fresh `timeline.json`.

## Sound

`cues.py` expects real recordings in `assets/sfx/pixabay/` at the repo root: `rain_window`, `rain_street`,
`thunder`, `wind_howl`, `aircon_hum` and `glass_tap` (mp3), plus `audio/sfx/squeak.mp3` (a palm on glass)
and `shears.mp3`. Any CC0 or licensed samples with those names will do.

From this folder (the tools also run from the repo root as `python tools/sound.py episodes/window/toon`):

```bash
python ../../../tools/sound.py .          # music / sfx / ambience stems -> video/audio/
python ../../../tools/mix_check.py .      # voice >= 10 dB over the beds on every line
python reel.py --preview --full && python finalize.py preview   # review/preview.mp4
python reel.py --master-par 12 && python finalize.py final      # video/window_final.mp4 at -14 LUFS
```
