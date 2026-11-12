# Camera direction

## Shot design

- **One purpose per shot**: one action, one expression or one reveal. Cut every 2-3 s; let the reveal hold.
- **The hook (0-3 s)** is the most beautiful moving shot of the reel, with camera and character moving
  from frame 1. Never open on a static face.
- **Coverage**: show both characters together first, then matching close-ups at the same height and
  screen position. Alternate close emotion with wide clarity.
- **Eyelines**: close-ups stay within ~35 deg of the eyeline. Matching close-ups mirror each other.
- **Foreground framing**: a curtain edge, a window frame or a chair back adds depth and frames faces.
  It must never fill the frame (no back-of-head or door-slab shots).
- **Readable at phone size**: a face is at least ~1/4 of the frame width in a close-up.
- **Reveals**: a slow push-in, a lateral reveal past a foreground object, or a match cut through a
  full-frame close-up (the example swaps the whole world while a face fills the frame: `twist_world()`
  in `episodes/window/toon/reel.py`).

## Code

```python
# a = (pos, target, focal px, horizon); the camera yaws to aim at the lerped target
("ST", M["stare"], M["hand"], G, track(((x, 1.57, -0.66), (x, 1.57, 0.3), 1350, 0.50),
                                       ((x, 1.57, -0.60), (x, 1.57, 0.3), 1560, 0.50), "lin"), {}),
```

- Eases for camera moves: `"lin"` for slow creeps, `"smooth"` (quintic) for a proper move, `"io"` for a
  gentle push. `anim.move()` gives a trapezoid move with no restart.
- The camera turns to face the target but cannot tilt, so **the target's height does nothing**. Frame up or down
  with the camera's own height and `horizon`: 0.46 is level; a smaller value moves the eye line up the frame and
  reads as looking down (0.02-0.10 for a top-down insert); a larger value reads as looking up.
- Focal length in px at 1080 wide: about 700-1000 for wides, 1100-1600 for mediums, 1900-3000 for
  close-ups and extreme close-ups. A longer lens from further back flattens the shot and keeps the lens
  out of the 0.45 m cull.
- Background defocus (full example only): `dict(blur=14, keep={"dad"})` blurs everything except the named people.
  The starter's only shot option is `cap=(y, size)`.
- Write each camera key from its **target first**: where the eyes or hands will be at that time
  (`rig.solve(look, pose_at(T))["head"]`), then place the camera relative to it.

## Staging traps the camera causes

- A camera inside a set piece sees through it: put it at least 0.2 m from walls, hedges and furniture.
- A camera low behind a sill or a table loses the face behind the edge. Raise it, move it out over the edge,
  or shoot from the other side with a long lens.
- Two people on one eyeline block each other in a reverse shot. Shoot it from the eyeline and hide the near
  person in that shot only (give `render()` a per-shot `hide` set that filters the cast), or move the camera
  off-axis.
- A camera behind someone holding a mirror sees the glass and the reflection.
- Captions take the zone the shot leaves empty (`cap=(y, size)` per shot); the check flags one over a face.
