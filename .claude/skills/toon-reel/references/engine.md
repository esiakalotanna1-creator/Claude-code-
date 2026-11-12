# Engine reference (tools/toon)

World units are metres, `y` is up. Output is 1080x1920; `Frame(scale)` draws the same framing at any scale
(0.2-0.3 for sheets, 0.5 for previews, 1.0 for the full-res preview, 2.0 then downsampled for the HQ master).

## toon.py: the renderer

```python
from toon import Camera, Frame, W, H, paint, shade, mix, argb, lin, rad, Rain, typeface
cam = Camera(pos=(0, 1.4, -3.0), yaw=0, f=1300, horizon=0.46)
fr = Frame(scale=0.5, bg="#05070f")
fr.box(cam, (x0, x1), (y0, y1), (z0, z1), "#334", light=(0, 2.4, 6))   # shaded box (top lighter, sides darker)
fr.poly(cam, [(x, y, z), ...], colr="#556", a=1.0, blur=0, outline=None)  # any world polygon (clipped at the lens)
fr.ground_ellipse(cam, cx, cz, rx, rz, "#000", 0.35, blur_m=0.08)         # contact shadows; add=True for light pools
fr.part(path, "#e8e8f0", light=(0.35, 1.0))   # a screen-space skia.Path, toon-shaded: fill, 3-stop gradient, inner edge, outline
fr.glow(x, y, r, "#ffd9a0", a=0.6)            # additive glow at a SCREEN point (project it first); keep it small
rgb = fr.array()                               # HxWx3 uint8
```

- **Camera** is yaw-only: `fwd = (sin yaw, 0, cos yaw)`, `right = (cos yaw, 0, -sin yaw)`, so `yaw=0` looks toward
  +z with +x on screen right. It cannot tilt. `horizon` is where the eye-level line sits, as a fraction of the
  frame height from the top: 0.46 is just above the middle; **a smaller value moves the eye line up, which reads as
  looking down** (the full example's top-down crib shot uses 0.02); a larger value reads as looking up.
  `cam.view(P)` gives camera space `(right, up, depth)`; `cam.proj(P)` gives `(screen x, screen y, depth, px per metre)`.
- `shade(c, k)` lightens toward white (k > 0) or darkens toward a cool near-black (k < 0), so shadows go blue,
  not grey. `mix(a, b, t)` blends two colours, and `paint(c, a, blur, stroke, blend, shader)` builds a skia Paint.
- `lin(p0, p1, cols, pos)` and `rad(c, r, cols, pos)` are gradient shaders: sky, light pools, face keys.
  `fr.poly(..., shader=fn)` takes a function `fn(path) -> shader`.
- `Rain(n, box, speed, seed, shelter)`: world-space streaks. Pass `shelter` by keyword. `.draw(fr, cam, t,
  light=lamp_pos)` lights the drops near a lamp.
- `clip_near(P, zn)` clips a polygon of camera-space points (`cam.view` output) at the lens; it can return fewer
  points, or none. `fr.poly` and `fr.ground_ellipse` already do it. **Never take a glow radius or stroke width
  from `cam.proj` of a point behind the camera** (check `depth > 0.3` first): it explodes and fills the frame.
- `toon.HQ["on"] = True` switches on smoother shading for the master (set the key; do not replace the dict).
- `typeface(bold=False)` and `font_path(bold=False)` find the caption font: `TOON_FONT` / `TOON_FONT_BOLD` if
  set (a missing file is an error), otherwise Arial Black / Arial Bold, otherwise DejaVu Sans Bold.

## rig.py: characters

```python
import rig
rig.LOOK["nora"] = dict(h=1.64, skin="#eec4a2", hair="#3f2a20", style="neat", top="#c8663e", pants="#2f3550",
                        shoes="#23222a", iris="#4d6a52", build=0.92, brow=0.85, back=True)
pose = dict(rig.REST, x=0.3, z=1.2, yaw=20, head_yaw=-10, lean=6, smile=0.3, gx=0.2)
J = rig.solve("nora", pose)          # world joints: head, neck, pelvis, sh_/el_/wr_/hand_/hip_/kn_/ank_R|L, Bc (chest basis), err
o = rig.draw(fr, cam, "nora", pose, light=(0, 2.4, 6.2), held={"R": rig.phone()}, shadow=True)
o["head"], o["head_r"], o["hand_R"], o["J"]     # screen head centre and radius, screen hand, the solved joints
```

- **Look keys** (`LOOK[name]`): `h` (standing height), `build`, `legs`, `arms`, `head` (proportions,
  1.0 = standard), `skin hair style top pants shoes iris brow`, `bottom` (`pants shorts skirt dress`),
  `wear` (`cap brim_hat glasses backpack scarf cape tie wings horns crown`), `animal`
  (`cat dog rabbit mouse bear` ears and snout), `head_shape`, `hair_mesh`, `long` (long hair), `pattern`,
  `sil` (silhouette only), `back` (hair drawn for views from behind: set it on anyone the camera gets behind),
  `killer` (a carved grin), `extras` (your own costume layers, below).
- **Pose keys** (`rig.REST` plus extras): placement `x z yaw floor`; body `crouch lean side twist bob breath
  shrug stance`; head `head_yaw head_pitch head_roll`; FK arms `aR aL = (shoulder pitch forward, roll out, elbow
  bend)` in degrees; IK `ik_R ik_L` (world wrist targets), `pole_R pole_L` (world elbow directions), `ankle_R
  ankle_L` (planted ankles), `kpole_R/L`, `toe_R/L`, `point_toes`; face `lid lid_lo brow brow_in gx gy mouth smile
  mouth_w grin fist`; `arms_k` (lengthen the arms a little for a reach), `hide_hand_R/L`, `rear_view`,
  `head_spin`, `hair_lift`, `t` (seconds, for flicker and sway).
- **`lie`** turns the whole upright skeleton as one rigid body, for lying and carried bodies:
  `lie=([(axis, degrees), ...], pelvis_point_or_None)`, for example `lie=([((1, 0, 0), 90)], (0.2, 0.3, 1.5))`.
- **Yaw for characters** (`rig.Basis.yaw`): `yaw=0` faces -z, toward a camera that looks along +z; positive yaw
  turns them toward screen right (`yaw=90` is a profile facing +x). Their own right is -x at yaw 0.
  `cam.rel_yaw(yaw, at)` tells you how a camera sees them (0 = facing the camera, +90 = profile to the right).
  `B.d(sgn * x, y, z)` gives a body-relative direction (sgn +1 = their right).
- **Brows**: + is angry, - is worried. A head dipped more than 12 deg bends the brows into an angry V.
- **Feet**: with no `ankle_R/L` the feet stand under the body and follow it. `rig.replant(t, start, steps, h)`
  steps one foot at a time to new world ankles on an arc; `rig.gait(t, start, yaw, step, rate, n)` is a walk with
  one foot always planted. Both return `ankle_R`, `ankle_L` and `plant`.
- **Held props**: `held={"R": rig.phone()}` (keys `"R"` and `"L"`). The rig has `phone() knife() bottle() match()
  matchbox() hand_mirror()`; the kit has more in `props/` (`tv`, `console`, `city_kit`).
- **Costume layers**: `extras=(fn, ...)` in the look. Each is `fn(parts, fr, cam, J, p, ld, lw, out)` and appends
  `(kind, depth, draw_fn)` to `parts`; `kind` is one of `under coat overtorso face top` and decides the layer
  (`episodes/smilingman/toon/looks.py` has a backpack and shorts written this way).
- **Fixed layering**: legs -> far arm -> torso -> head -> near arm. A person is one depth-sorted item.
- **Culling**: `rig.draw` does not draw anyone whose pelvis, head or an ankle is within 0.45 m of the lens, and
  returns `culled=True`.

## anim.py: timing

```python
from anim import Track, HOLD, EASE, move, blink, lerp
TIM = Track([(0.0, dict(head_yaw=0, smile=0)),
             (1.2, dict(head_yaw=HOLD)),                 # this channel starts moving here
             (1.5, dict(head_yaw=-30), "out"),           # the ease INTO this key: io in out snap back lin
             (2.0, dict(smile=0.6), "io")])
pose.update(TIM(T))
lid = blink(T, [2.9, 6.4], 0.16)                          # multiply the pose's lid by this
pos = move(T, 3.0, 6.0, a, b, ramp=0.3)                   # trapezoid camera move, no restarts
```

Channels only interpolate between the keys that name them, so offsets are free: key the eyes at t, the head at
t + 0.08 and the shoulders at t + 0.15.

## Kit modules (tools/toon)

- `cast/mara.py` (look `mara`) and `cast/powerup.py` (look `kid_powerup`) register looks in `rig.LOOK`.
  `cast/creature.py` and `cast/widemouth.py` are creatures with their own skeleton and their own `solve`/`draw`;
  `hair.py` and `faces.py` are shared layers.
- Model sheets, run from `tools/toon`: `python -m cast.sheet <module> <look> [out.png]`, where `<module>` is
  `mara` or `powerup`, or the path of an episode's `looks.py`. Default output: `assets/kit/cast/<look>.png` at the
  project root. The creatures draw their own: `python -m cast.creature`, `python -m cast.widemouth`.
- `sets/`: `city_street.py`, `gamer_room.py`, `mara_room.py`: modular rooms and a street with lights
  (`python -m sets.gamer_room --sheet out.png` for a contact sheet).
- `props/`: `tv.py`, `console.py`, `city_kit.py`.

## The episode pattern

**Starter (`episodes/starter/toon`), the one to copy.**
- `scenes.py` has one world class. `draw(fr, cam, T)` draws the shell, then the furniture and the people sorted
  far to near, grades each person, and returns `{pid: rig.draw result}`. `cast(T)` returns `[(pid, look, pose)]`.
  Acting is a `Track` evaluated at `T`; nothing is stored between frames.
- `reel.py` holds `SHOTS = [(name, t0, t1, camera_fn, opts)]`. The camera function is `track(a, b, ease)` with
  keys `(position, target, focal px, horizon)` and eases `lin io out smooth`, or any `f(T, t0, t1) -> Camera`.
  The only option is `cap=(y, size)`: where the caption sits in that shot.
- `render(T, scale)` returns `(shot name, HxWx3 array)`. Frames are independent, which `--master-par N` relies on.

**Full example (`episodes/window/toon`), for technique.** Its `reel.py` draws the world in pieces, so its
world classes have more methods: `bg(fr, cam, T)`, `items(cam, T)` -> `[(depth, draw_fn, id)]`, `cast(T)` ->
`[(pid, look, pose, held, glow, after)]`, `nearest_light(point)`, `grade(fr, cam, T, pid, o)`, `overlay(...)`,
`post(...)`, and for its checks `solids()` and `allow`. Its `SHOTS` rows are `(name, t0, t1, world, camera_fn,
opts)` with options `blur` (background defocus in px), `keep` (ids kept sharp), `cap` and `xfade`.
