# Lighting: three layers, every location

1. **Cool environment light**: a blue-purple night (or a cool evening) that keeps detail in the shadows.
   Shadows shade toward a cool near-black (`toon.shade(c, -k)`), never grey or pure black.
2. **A soft face key**: from above and slightly in front, motivated by something in the scene (a lamp, a
   window, a phone, a streetlight). The starter's `Room.grade()` is the shortest version (its key warms and cools
   with the lamp). In the full example, `scenes.grade()` paints a radial `rad()` key over each
   head after the night tint, with its own colour per world:
   ```python
   tint, key, ka = "#929fbc", "#ffdcaa", 0.26   # rain-cold garden, the window's warm spill on his face
   ```
3. **Warm practicals** at several distances (lanterns, floor and table lamps, lit windows, a street lamp).
   Each one lights the surfaces near it: a `ground_ellipse` pool on the floor, a tint on the nearest wall,
   a warm edge on the side of a face turned toward it, and lit rain streaks around it (`Rain.draw(light=...)`).

## Rules

- **Faces are the clearest thing in frame.** The background is a little darker and lower in contrast
  around faces. Signature shapes stay readable at phone size.
- Window or screen glow never washes out a face. Hats, umbrellas and glass never black out an expression
  (use bounce light).
- **Contact shadows** go under feet, under chins and where hands touch things. No flat models, no black
  patches.
- Wet ground gets soft reflections under the real lights, never a mirror.
- Depth: a darker foreground edge, readable characters in the mid-ground, warm lights further back,
  softer distant buildings (`vignette()` and `wash()` in `episodes/jeff/toon/scenes.py`).
- **One setup per location.** Direction, colour and exposure hold across cuts. A per-world `tint/key`
  pair is how the example keeps them matched.
- Restraint: no bloom halos, glowing outlines, crushed shadows, blown highlights or heavy fog. `fr.glow`
  is for the bulb itself, small.
- Weather: rain or snow by default for night horror, animated in the quiet moments. Use the script's
  weather when it names one.
- For the master, switch on `toon.HQ["on"] = True` for smoother falloff and a soft key sheen.

## Lighting sheet (before the master)

Put a wide shot, both character close-ups and the main action shot side by side. Check that the
expressions read, the characters separate from the background, warm light falls on nearby objects, feet
and props are grounded, and brightness and colour match across the cuts.
