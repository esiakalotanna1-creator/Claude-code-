# Acting and staging

## Acting

- **Chains with offsets**: eyes -> head -> shoulders -> body -> hands, each 0.05-0.15 s after the one
  before, as prep -> move -> settle. Use `HOLD` in a `Track` to mark where a channel starts moving.
- Use eases for intent: `out` / `snap` for reactions and impacts, `io` for slow gestures, `back` for a
  settle with a small overshoot.
- **Grabs reach before they close.** The hand travels to the target with the fingers open, then the
  fist closes. Held props follow the hand (`held=`); a placed prop is ray-cast onto its surface.
- **Feet are planted in world space** and step one at a time (`rig.replant`, `rig.gait`). No sliding,
  sinking or floating.
- Silhouette-readable actions: hold props at chest height so the action stays below the face. Use clasped
  hands at the chin instead of a hand over the mouth. Two-hand poses keep each hand on its own side, with
  `pole_R/L` pointing the elbows down and out, or the forearms cross in an X.
- **Stillness is a tool.** A threat that controls the scene is still and close; the moment it loses
  control, it gets restless.
- Blinks every 2-5 s (`anim.blink`), more on nerves, none during a stare.

## Staging lessons (each one is a glitch that already happened)

- **Never step more than ~0.2 m sideways in one step**: it reads as the splits, and no code check flags
  it. Break long sideways moves into shuffles, or turn the body toward the travel and take real forward
  steps.
- **A 1.2 m child cannot lean out over a 0.74 m sill.** The lean pivots at the pelvis and the chest hits
  the board. Check reach and lean limits against the set heights before you write the beat.
- **Two heads closer than ~0.24 m interpenetrate.** Re-block the stations; easing a lean back alone
  breaks the reach.
- **Clip zones** (a body seen through a gap in a hedge, a body behind a wall) must switch off once the body
  is clear of the occluder, or they cut the body away and leave a headless crouch.
- **IK pole changes are blended over ~0.2 s**, never switched in one frame, or the elbow flips its bend
  plane for a frame.
- After a release, carry the hand through a point in front of the body and blend the pole back to rest.
  Never let IK snap the arm straight.
- Curtains, posters and flat wall dressing sort as wall-flat items (push their sort depth ~0.6 m back), or
  they draw over people standing in front of them.
- A head dipped more than 12 deg bends the brows into an angry V. Compensate with `brow`.
- Beds: anchor them on their far side so a sitter draws on top. Someone standing beside a bed needs the
  near face of the bed (a skirt) to hide their feet.
- Shoes reach ~0.17 m past the ankle. Keep walk paths clear of furniture by that much.
- Doorways lead to built rooms. A window shows a built outside.
- Every narrated line is depicted: the picture matches what is said.
- When a staging keeps failing the checks, simplify it or pick a clearer angle. Never hide anatomy with
  blur, darkness, cuts or captions.
