"""The cast of THREE SECONDS LATE. House rule (CLAUDE.md): the main characters wear all black, with "Neat" across the
back of the shirt; boys in black trousers, women in a black skirt.

    kai     14, the narrator. Dry, funny. Short dark hair, brown skin, white sneakers. Right-handed (it matters).
    remi    7, his brother. Small, round face, messy hair.
    mom     practical, holding it together. Hair up in a bun.
    gma     Grandma Bea, 81. Silver bun, round glasses, fearless.
    *_copy  the reflection people: the same look, eyes a touch too bright (used when a copy steps out).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
import importlib.util  # noqa: E402

import rig  # noqa: E402

_spec = importlib.util.spec_from_file_location("callback_looks", os.path.join(HERE, "..", "..", "callback", "toon", "looks.py"))
_cb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_cb)                                     # callback's costume kit
hair_bun, round_glasses = _cb.hair_bun, _cb.round_glasses

BLACK, TROUS, NEAT = "#1a1a1f", "#141418", dict(back_text="Neat", back_text_col="#f1ede4")

rig.LOOK["kai"] = dict(h=1.62, skin="#9a6444", hair="#141010", style="short", top=BLACK, pants=TROUS, shoes="#ecebe6",
                       iris="#3a2416", build=0.88, brow=1.0, brow_col="#141010", head_shape=(0.97, 1.02, 0.0), **NEAT)
rig.LOOK["remi"] = dict(h=1.22, skin="#9a6444", hair="#141010", style="messy", top=BLACK, pants=TROUS, shoes="#d8483a",
                        iris="#3a2416", build=0.95, brow=0.85, brow_col="#141010", head=1.18, legs=0.92, head_shape=(1.04, 0.96, 0.0), **NEAT)
rig.LOOK["mom"] = dict(h=1.66, skin="#a46c4b", hair="#1a1210", style="short", top=BLACK, pants=TROUS, shoes="#2a2630", bottom="skirt",
                       iris="#3a2416", build=0.9, brow=0.85, brow_col="#1a1210", brow_mu=0.43, mu_front=0.66,
                       extras=(hair_bun("#1a1210", tie="#1a1a1f"),), **NEAT)
rig.LOOK["gma"] = dict(h=1.56, skin="#9a6a4e", hair="#d9d6d0", style="short", top=BLACK, pants=TROUS, shoes="#2a2630", bottom="skirt",
                       iris="#3b2a20", build=0.94, brow=0.8, brow_col="#bdb8b0", brow_mu=0.43, mu_front=0.62, head_shape=(1.0, 0.98, 0.06),
                       extras=(hair_bun("#d9d6d0", tie="#6b4a8a"), round_glasses("#3a2a22")), **NEAT)
rig.LOOK["anchor"] = dict(h=1.68, skin="#f0c9a8", hair="#c9a24a", style="short", top="#2f4f86", pants="#2a2f3a", shoes="#22252e",
                          iris="#3e5f7a", build=0.9, brow=0.8, brow_col="#8a6a2c", brow_mu=0.43, mu_front=0.62)
rig.LOOK["dad"] = dict(rig.LOOK["father"], skin="#94603f", hair="#141010")
for nm in ("kai", "gma"):
    rig.LOOK[nm + "_copy"] = dict(rig.LOOK[nm], glow="#cfe6ff")
