---
name: toon-reel
description: Make a vertical (9:16, 1080x1920, 30 fps) cartoon story reel for Reels / TikTok / Shorts with the toon-reel-engine - the script method, the episode files, the Skia toon look, three-layer lighting, camera direction, acting, the mandatory frame checks, sound, mix and the final export. Use whenever someone asks for a new reel, episode, short story video, legend retelling or animated short with this engine, or asks to light, stage, check, render or finish one.
---

# Toon reel

You are directing and building a short animated story with the toon-reel-engine. Everything is Python:
characters, sets, lights and cameras are code, and every frame is a pure function of time `T`. There is no
timeline editor and no keyframe UI. You write data (keys, shot tables) and then you **look at frames**.

Layout of the engine (keep it: the relative imports depend on it):

```
tools/toon/            the engine: toon.py (renderer), rig.py (characters), anim.py (timing), cast/ props/ sets/ (kit)
tools/                 sound.py (stems from cues), mix_check.py (voice clarity), finish.py (-14 LUFS export),
                       thumb.py (cover), find_phrases.py (phrase times in a narration take)
episodes/starter/toon  THE TEMPLATE: "The Lamp", 12.5 s, four shots, one room, one person. Copy this to begin.
episodes/window/toon   THE FULL EXAMPLE: "The Man at the Window", 50 s, 13 shots, two worlds and a twist.
episodes/jeff, episodes/smilingman   support modules the full example and the kit import (not runnable episodes)
```

**Commands.** `python` below means the interpreter that has `requirements.txt` installed (`py` on Windows).
An episode's own scripts (`reel.py`, `build_tl.py`, `finalize.py`) run from the episode folder
`episodes/<name>/toon`. The tools run from the project root: `python tools/sound.py episodes/<name>/toon`.

## First: find or set up the engine

Work in the person's own project folder, never inside the plugin's install folder (it is replaced on update).

1. If the working folder already has `tools/toon/toon.py`, use it.
2. Otherwise the engine ships with this skill. Its root is two folders above this skill's base directory
   (`<skill dir>/../..`: it holds `tools/`, `episodes/`, `requirements.txt` and `.gitignore`). Copy those four into
   the working folder, keeping the layout, and tell the person you did. If that folder has no `tools/` (the skill
   was copied on its own), clone `https://github.com/wlr2/toon-reel-engine` instead.
3. `pip install -r requirements.txt`, and check `ffmpeg -version` works (5.1 or later). Captions need Arial Black,
   or `TOON_FONT` set to a heavy sans `.ttf`.
4. Prove the setup before building anything, from `episodes/starter/toon`: `python build_tl.py`, then
   `python reel.py --frame 5.0` must write `review/_f5.00.png`.

## The order is fixed

**script -> timeline -> cast sheets + set frame -> blocking -> checks (2 rounds) -> preview -> master -> sound -> finish -> post.**

A master render never starts before the checks have passed and been logged. Show the person the character
sheet and one set frame before animating, and a labelled key-frame sheet before the full-res preview. Ask before
spending money on anything (paid TTS, paid SFX, cloud renders).

## 1. Script (references/script.md)

The ten-step method: open on the most specific contradiction, one main question, a chain of consequences, a change
every few seconds, written for speech and animation, a moving middle, an earned ending with the signature line
last, honest framing ("AN INTERNET HORROR STORY" for creepypasta), a timed shot table, then a retention edit.
If the person hands you a script or a beat sheet, **their words and their spec win** over any house rule here:
never rewrite their lines, suggest changes and quote what you would change.

Deliverable: `SCRIPT.md` (three hooks + the pick, full narration, timed shot table, word count) and `script.py`.

## 2. The timeline, then the voice

- `script.py` holds `PHRASES` (where each line is placed, its text, its caption chunks with `[word]` for the red
  keyword) and `MARKS` (the story beats in seconds, which become the shot boundaries).
- `python build_tl.py` writes `timeline.json` (`total`, `marks`, `lines`). **The reel reads only `timeline.json`.**
  In the starter it works before any audio exists: phrase lengths are estimated from word counts, so you can
  block the picture first.
- The voice is one take per speaker, 48 kHz mono, from any TTS or a microphone (this repo ships none; ElevenLabs
  is paid, Kokoro is free and local). Never speed a take up to fit: cut a beat instead. Spell numbers out as words
  in the text you send to a TTS.
- `python tools/find_phrases.py take.wav` prints each phrase's `(start, end)` in the take. Put them in
  `PHRASES` and re-run `build_tl.py`: it cuts the phrases out, places them and writes `audio/narration.wav`.
  Then re-check every shot: real phrase lengths differ from the estimates.
- The shipped `build_tl.py` files handle one narrator. For several speakers keep one take per speaker and add the
  speaker to each phrase (a small change to `build_tl.py`).
- Swears for TikTok: bleep them in a separate stem, and asterisk them in captions (`f***ing`).

## 3. The episode files (references/engine.md)

| file | job |
|---|---|
| `script.py` | lines, caption chunks, marks |
| `build_tl.py` | `timeline.json` (+ `audio/narration.wav`) |
| `looks.py` | the cast: each look is a dict in `rig.LOOK` |
| `scenes.py` | the world: set geometry, lights, who is where at time `T`, the acting tracks |
| `reel.py` | `SHOTS`, captions, `render(T)`, the checks, and the render commands |
| `cues.py` | sound events for `tools/sound.py` |
| `finalize.py` | mix the stems, mux onto the render, run `tools/finish.py` |

**Start a new episode by copying `episodes/starter/toon`** to `episodes/<name>/toon`. Its `reel.py`, `build_tl.py`
and `finalize.py` are generic and can stay as they are; you replace `script.py`, `looks.py`, `scenes.py`, the
`SHOTS` table and `cues.py`. Do not start from `episodes/window/toon`: its `reel.py`, `cues.py` and checks are
wired to that story (two mirrored worlds, named marks, a custom twist camera). Read it for technique: textures,
depth-of-field, a per-world face key, hands on glass, a cross-fade between worlds. Larger episodes move the
acting out of `scenes.py` into an `acting.py`.

A world needs two methods: `draw(fr, cam, T)`, which draws everything and returns `{pid: rig.draw result}`, and
`cast(T)`, which returns `[(pid, look, pose)]`. `pid` is a person's id in this episode ("nora"). One world and
one timeline per location; shots only choose cameras.

## 4. Look (references/look.md)

Rounded simple shapes, slightly big heads, big expressive eyes, matte materials with soft 3-stop shading and a
darker outline in the base colour. Each character gets their own silhouette, face and palette designed from the
script (never a reskin of another reel's character); recurring characters stay on-model. Make a model sheet before
animating, from `tools/toon`: `python -m cast.sheet ../../episodes/<name>/toon/looks.py <look>` (it writes
`assets/kit/cast/<look>.png` at the project root, or the path you give as a third argument).

## 5. Lighting (references/lighting.md)

Three layers in every location: a **cool environment** (blue-purple night keeps detail), a **soft key on every
face** (from above-front, motivated by a lamp or window), and **warm practicals** at several distances that light
what is near them. Faces are the clearest thing in frame; the background is a little darker and lower in
contrast around them. Contact shadows under feet, furniture and touching hands. One light setup per location: the
direction, colour and exposure hold across cuts. No bloom, no glowing outlines, no crushed blacks. Weather (rain,
snow, wind) animates in quiet moments when the story has weather.

## 6. Camera (references/camera.md)

- A cut every 2-3 s. Each shot serves one action, one expression or one reveal.
- The hook (0-3 s) is the most beautiful moving shot of the reel: camera and character move from frame 1.
- Two-shot first, then matching close-ups. Close-ups stay within ~35 deg of the eyeline.
- `track(a, b, ease)` makes one clean move between two keys `(position, target, focal px, horizon)`. The camera
  turns to face the target but cannot tilt: the target's height is ignored. Frame up or down with the camera
  height and `horizon` (a smaller value puts the eye line higher in the frame, which reads as looking down).
- Keep cameras >= 0.45 m from any person in view: `rig.draw` does not draw anyone closer than that.
- Captions (Arial Black 66 px, white, black stroke, keyword #FF4D4D) never sit on a face or a hand. Move them
  per shot with `cap=(y, size)`.

## 7. Acting and staging (references/acting-staging.md)

Every action is a chain with offsets: eyes -> head -> shoulders -> body -> hands, as prep -> move -> settle.
Reactions ease `out`/`snap`, settles `back`. Grabs reach before they close. A person who only turns the head and
shoulders can stand on the default feet; a person who walks or turns the body needs feet planted in world space
(`ankle_R`/`ankle_L` from `rig.replant` or `rig.gait`), stepping one at a time. Read the staging lessons before
blocking anything: each one is a glitch that has already happened.

## 8. Checks: the gate before every master (references/checks.md)

1. `python reel.py --check` -> read the whole `review/reel_checks.txt`. In the starter every problem is an
   `ANOMALY` line: reach, sinking feet, over-bent elbows, elbow and knee flips, jumps, people too close to the
   lens, captions over a face or hand.
2. `python reel.py --stills` -> first/mid/last frame of every shot (round 1).
3. `python reel.py --sheet <SHOTS>` -> **every frame** of contact shots, walks, turns and occlusion changes on
   gapped sheets (round 2). Look for splits, popping limbs, heads through things, things vanishing.
4. Fix in the data, re-run, and log each anomaly in `review/LOG.md` (append only): time, shot, cause, fix, how
   verified; plus accepted flags with the reason, and what you could not inspect.
5. Never claim "no anomalies" from code alone. The code checks joints, not pictures: it does not see people
   passing through furniture or each other, props missing a hand, a wrong draw order, or a 0.8 m sideways step
   that reads as the splits. Those you find on the sheets.

## 9. Render (from the episode folder)

- `python reel.py --preview --full` -> `review/reel_preview.mp4` (1080x1920, silent). `python finalize.py preview`
  adds the mix -> `review/preview.mp4`. Show it, get an OK.
- `python reel.py --master-par 12` -> `video/reel_silent.mp4`: the master on 12 processes (use your core count).

## 10. Sound, mix, finish, post (references/sound-finish.md)

- `cues.py`, then from the project root `python tools/sound.py episodes/<name>/toon` -> music, sfx and ambience
  stems. Real recordings for real things (bring CC0 or licensed samples into `assets/sfx/`); synthesis only for
  abstract drones, risers and booms. The starter's cues are all synthesised so the chain runs: replace them.
- `python tools/mix_check.py episodes/<name>/toon`: the voice must be >= 10 dB over the beds on every line
  (every line fails until there is a real narration take).
- `python finalize.py final` (episode folder) -> `tools/finish.py` -> -14 LUFS, <= -2 dBTP, H.264 High, +faststart.
- Cover, from the project root: `python tools/thumb.py frame.png cover.jpg --line "TITLE:#F2EFE6:120"`.
- `POST.md`: captions per platform, hashtags, and a reminder to switch on HD upload in the app.

## Words used here

- **mark**: a named story beat in seconds (`MARKS`), used as a shot boundary and to time actions.
- **station**: a spot where a character stands (x, z, facing) and the time they step to it.
- **planted foot**: an ankle fixed at a world position (`ankle_R`/`ankle_L`), so the foot cannot slide.
- **clip zone**: a screen-space clip that hides part of a body behind something (a hedge, a wall edge).
- **wall-flat item**: flat set dressing on a wall (curtain, poster); sort it as far back as its wall.
- **practical**: a light source that is visible in the set (a lamp, a lit window).

## Habits

- Look before you claim. Render the frame, read the sheet, then say what you saw.
- One change, one re-render of the affected shots, one re-check, with sheets.
- When a staging keeps failing, simplify it or pick a clearer angle. Never hide anatomy with blur, darkness,
  cuts or captions.
- Write every correction the person gives you into the episode's `review/LOG.md` and, if it is general, into a
  `STAGING_NOTES.md` at the project root (read it at the start of every episode). Never write into the plugin's
  own folder.
