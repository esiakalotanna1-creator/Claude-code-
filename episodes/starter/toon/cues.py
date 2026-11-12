"""Sound for THE LAMP. From the repo root:  python tools/sound.py episodes/starter/toon
-> video/audio/music.wav, sfx.wav, ambience.wav (the narration stem comes from build_tl.py).

Everything here is synthesised, so the whole chain runs with no samples. That is right for the drone and wrong
for the rest: replace the lamp tick, the knocks and the room tone with real recordings before you publish
(load a sample the way episodes/window/toon/cues.py does). Keep the event times in step with scenes.py.

tools/sound.py calls build(ctx): ctx["put"](name, time, samples, gain) places one sound on the sfx stem;
ctx["gen"] holds the generators and filters from tools/sound.py; ctx["marks"], ctx["lines"], ctx["total"].
"""
import numpy as np

FLICKS = [2.35, 5.25, 5.62]                    # = scenes.Room.flicks
KNOCKS = [7.9, 8.3, 11.0, 11.35]               # = scenes.Room.knocks


def build(ctx):
    G, put, total = ctx["gen"], ctx["put"], ctx["total"]
    t = G["t_axis"](total)
    rng = np.random.default_rng(11)
    for i, f in enumerate(FLICKS):                                 # the lamp ticks as it dips
        put(f"lamp_tick_{i}", f, G["light_clack"](), 0.35)
    for i, k in enumerate(KNOCKS):                                 # knuckles on the far side of a door
        put(f"knock_{i}", k, G["thud"](0.35), 0.9 if i < 2 else 1.0)
    # ambience: a quiet room at night (filtered noise), a touch louder once she listens
    amb = G["lp"](rng.standard_normal(len(t)), 260) * (0.8 + 0.2 * np.clip((t - KNOCKS[0]) / 1.5, 0, 1))
    # music: one low drone that arrives with the second flicker and swells to the last knocks
    drone = (np.sin(2 * np.pi * 55.0 * t) + 0.5 * np.sin(2 * np.pi * 82.6 * t + 0.7)) * (0.75 + 0.25 * np.sin(2 * np.pi * t / 5.1))
    drone *= np.clip((t - FLICKS[1]) / 2.5, 0, 1) * (0.6 + 0.4 * np.clip((t - KNOCKS[0]) / 3.0, 0, 1))
    drone *= G["env_ar"](len(t), 0.05, 0.4)
    return dict(music=drone.astype("float32"), music_level=0.14, duck_down=0.5,
                ambience=amb.astype("float32"), ambience_level=0.05, sfx_level=0.7)
