# Starter: The Lamp

A 12.5 s reel in four shots: one room, one person, a lamp, a door. It is the template for a new episode. It
depends only on `tools/toon`, needs no audio and no samples, and every command below works on a fresh clone.

| file | what to change for your story |
|---|---|
| `script.py` | the lines, their caption chunks, where each is placed, and the marks (story beats) |
| `looks.py` | your cast |
| `scenes.py` | your set, its lights, who stands where, and the acting tracks |
| `reel.py` | only the `SHOTS` table (and the camera targets above it); the rest is generic |
| `cues.py` | the sound events |
| `build_tl.py`, `finalize.py` | nothing: they are generic |

## Picture

```bash
python build_tl.py                   # script.py -> timeline.json
python reel.py --stills              # review/shots.png
python reel.py --check               # review/reel_checks.txt: 0 anomalies as shipped
python reel.py --sheet CLOSE DOOR    # every frame of the acting shots
python reel.py --preview --full      # review/reel_preview.mp4 (1080x1920, silent)
python reel.py --master-par 8        # video/reel_silent.mp4 (HQ master)
```

## Voice

Until you have a narration take, `build_tl.py` estimates each phrase's length from its word count and writes a
silent `narration.wav`, so the picture can be blocked first. When you have one:

1. Save it as `audio/narration_take.wav` (one take, 48 kHz mono).
2. From the repo root: `python tools/find_phrases.py episodes/starter/toon/audio/narration_take.wav` prints each
   phrase's `(start, end)`. Put them in the last field of each row of `PHRASES` in `script.py`.
3. `python build_tl.py` again. Real phrases are longer or shorter than the estimates: re-check every shot.

## Sound and the final file

```bash
python ../../../tools/sound.py .          # music / sfx / ambience stems -> video/audio/
python ../../../tools/mix_check.py .      # voice >= 10 dB over the beds (every line fails until there is a voice)
python finalize.py preview                # review/preview.mp4 = the preview render + the mix
python finalize.py final                  # video/final.mp4 = the master + the mix, through tools/finish.py
```

The cues are synthesised placeholders (a tick, four thuds, a drone, room tone) so the chain runs with nothing
installed. Replace the tick, the knocks and the room tone with real recordings before publishing. With no voice
in the mix the final file comes out quieter than -14 LUFS (about -18 as shipped); `finish.py` prints what it
measured.
