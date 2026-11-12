# Sound, mix, finish, posting

## Voices

- One take per speaker. Never speed a take up (not even slightly). If the reel is too long, cut a beat.
- This repo ships no voice tool. Any TTS or a microphone works (Kokoro is free and local, ElevenLabs is paid);
  save each take as a 48 kHz mono wav. Ask before spending credits, and never spend them on tests.
- `python tools/find_phrases.py take.wav` (project root) lists each phrase's `(start, end)` for `script.py`.
- To make a voice younger, raise the pitch with the formants shifted. The length stays the same, so it is
  not a speed-up (this filter needs an ffmpeg built with librubberband):
  `ffmpeg -i in.wav -af "rubberband=pitch=2^(2/12):formant=shifted" out.wav`
- Write numbers out as words in the TTS text.
- Swears: silence them in the narration, put a 1 kHz bleep in a stem of its own (`video/audio/beeps.wav`, about
  x0.12 of full scale), add `"beeps"` to `STEMS` in `finalize.py`, and asterisk them in the captions. No shipped
  script makes the bleep stem for you.

## Stems

`cues.py` lists the events. From the project root, `python tools/sound.py episodes/<name>/toon` renders them
into `video/audio/{music,sfx,ambience}.wav`; `narration.wav` comes from `build_tl.py`. `cues.py` must define
`build(ctx)`: `ctx["put"](name, time, samples, gain)` places a sound, `ctx["gen"]` holds the generators and
filters of `tools/sound.py`, and it returns the music and ambience arrays with their levels. The starter's cues
are synthesised placeholders; the full example's load real recordings (and cache the converted files in
`assets/sfx/cache`: delete the cached file if you replace a sample under the same name).

- **Real recordings for real things** (rain, doors, glass, footsteps, thumps, branches, cloth). Bring
  CC0 or licensed samples into `assets/sfx/<source>/`; the example's `cues.py` expects
  `assets/sfx/pixabay/{rain_window,rain_street,thunder,wind_howl,aircon_hum,glass_tap}.mp3`. Synthesis is
  only for abstract drones, risers, stings and booms.
- A full stack on every action beat: the impact, its body (a low thump), its tail (debris, leaves) and
  the room's answer.
- Never leave silence. A room tone or ambience bed runs under everything, including the black at the end.
- Twist and comedy beats: the music cuts out right before the line, and a deep bass hit plus the push-in
  lands the flip. Meme-style SFX go on the punch words.

## Mix

- From the project root, `python tools/mix_check.py episodes/<name>/toon`: the narration must sit at least 10 dB above music,
  sfx and ambience in the speech band (300-4000 Hz) on every line. Fix the levels in `cues.py`, then
  re-run.
- Listen to it. A measurement is not a mix.

## Finish

- From the episode folder: `python finalize.py preview` muxes the mix onto `review/reel_preview.mp4`
  (-> `review/preview.mp4`). `python finalize.py final` muxes onto `video/reel_silent.mp4`, then runs
  `tools/finish.py` (-> `video/final.mp4` in the starter).
- `tools/finish.py in.mp4 out.mp4` applies a limiter plus two-pass loudnorm to -14 LUFS integrated
  (<= -2 dBTP, AAC 192k / 48 kHz), and re-encodes to H.264 High@4.1, 1080x1920, 30 fps CFR, BT.709,
  CRF 16, a 1 s GOP and +faststart. Needs `ffmpeg` 5.1 or later on PATH.

## Cover and post

- From the project root: `python tools/thumb.py frame.png cover.jpg --line "THE MAN AT THE:#F2EFE6:110" --line "WINDOW:#FF5A3C:220"`.
  Use a clean frame with no captions. Text stays inside y 400-1520 (the band that survives the Shorts
  shelf and the Instagram grid crops), and the face sits above the title.
- `POST.md` holds the Instagram, TikTok and YouTube captions, a title, hashtags, and a reminder to switch
  on "Upload at highest quality" (Instagram) and "Upload HD" (TikTok).
- No engagement bait, polls or "comment if..." lines unless the person asks for them.
