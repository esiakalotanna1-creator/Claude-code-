# Mandatory checks: the gate before every master render

Run all of these, in order, before **every** master, including re-renders after fixes.

## 1. Constraint checks: `python reel.py --check`

The check lives in the episode's `reel.py` and runs over every frame. It writes `review/reel_checks.txt`.

**What the starter's check tests** (every hit is one `ANOMALY` line with the shot, the time span and the cause):

- an arm or leg more than 2 cm short of its IK target (`reach short`);
- an ankle below the floor (`foot sinks`);
- an elbow bent past 155 deg (`elbow over-bent`);
- an elbow or knee whose bend plane flips between two frames (`elbow flip`, `knee flip`);
- a pelvis that moves more than 12 cm in one frame (`jump`);
- a person in view but within 0.45 m of the lens, so not drawn (`culled`);
- a caption over a face or a hand (`caption over face`).

**What no shipped check tests.** People passing through furniture or each other, a prop that misses the hand,
gaze that misses its target, a wrong front/back draw order, planted feet that slide, a step so wide it reads as
the splits. You find those on the sheets (steps 2 and 3), or you add a test for them to `check()` when an episode
needs one: the full example adds people against set solids (`solids()`, with allowed contacts in `allow`) and
its story's own rules (nobody crosses the glass).

**The full example's report is laid out differently.** Joint and solid problems are `ANOMALY` lines; captions
over a face or hand are separate lines starting `caption`; planted-foot drift and the largest joint
acceleration are numbers on one line per person and shot. Read the **whole** file there, not only
`grep ^ANOMALY`. Joint-speed peaks are fine only at intended snaps (a punch, a grab), and each is named in the log.

## 2. Stills: `python reel.py --stills`

Look at the first, mid and last frame of every shot. Check for anything uncanny, broken, hidden or
unreadable, and that the lighting matches across cuts. (Round 1.)

## 3. Every-frame sheets: `python reel.py --sheet SHOT1 SHOT2 ...` (`--half` = every 2nd frame)

Put every frame of every contact shot, walk, turn, step, occlusion change and cut on gapped sheets (flush
tiles make characters look merged). Render a single frame bigger with `--frame T`. (Round 2.) Look for:

- stances wider than the hips (the splits), knees through each other;
- a limb or a head vanishing or popping for one frame;
- a body cut away by a clip zone or drawn over by set dressing;
- hands that miss what they hold; props that jump;
- faces lost to darkness, glare or captions.

## 4. Log: `review/LOG.md` (append only; read it before editing)

For each anomaly record the time, the shot, the cause, the fix and how it was verified (which sheet or
check). Keep a separate table of accepted flags with the reason. End with **what was not inspected**:
real-time feel, audio by ear, phone-size readability, frames checked only at half rate.

## 5. Re-render and re-check

Fix in the data (keys, positions, cameras), re-render the affected shots, and re-check with sheets, not
with code alone. **Never claim zero anomalies from code.**
