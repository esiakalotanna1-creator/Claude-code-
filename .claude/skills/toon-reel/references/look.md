# Look: the toon style

**Execution quality is the bar.** Clear silhouettes, consistent proportions, balanced expressive faces,
smooth readable action, clean matte materials, soft shading, contact shadows and composed shots. Design
every new character, creature and set from the current script: its own anatomy, face, silhouette,
personality, architecture and palette. Never reuse another reel's designs. Recurring characters stay
on-model.

- Rounded simple shapes, slightly oversized heads, big expressive eyes. Noses, mouths, ears and hands are
  simplified the same way across the cast. Head size, eye spacing, shoulders and limbs stay fixed in
  every shot.
- Symmetrical base model: the eyes sit on one plane with the pupils on one target, and the mouth is under
  the nose. In three-quarter view the far eye is smaller. No drifting features.
- Matte materials: clean skin with soft shading (no pores, veins or realistic contours), clothes with a
  few purposeful folds, and hair as sculpted clumps rather than strands. Never pair a cartoon face with
  realistic hands.
- Ordinary people get round heads. Creepy humans stay subtle: the uncanny lives in the smile, the stillness
  and the eyes, not in gore.
- Performance comes through the eyes, brows, mouth and head angle, with anticipation and follow-through.
- Hats: a planar tilted rim and no fake visors. Check a cap from 18 angles before using it.
- Gate before animating: front, three-quarter and side views of each new character, the expressions the reel
  uses, and one representative set frame. Get an OK on both. From `tools/toon`:
  `python -m cast.sheet ../../episodes/<name>/toon/looks.py <look>` makes the turnaround; the full example's
  `turn_sheet.py` shows how to add an expression row for each character.

## Sets

- Dense, deliberate dressing with real textures (procedural tiles in `textures.py`, cached in `tex/`).
  No flat, empty boxes. Secondary sets (an insert of another room) get full dressing too.
- Fixed geography: landmarks, props and consequences stay consistent between angles. Doorways lead to
  built rooms. A window shows a built outside.
- Hedges, bushes and curtains never draw over a person by accident. Check the draw order on sheets.
