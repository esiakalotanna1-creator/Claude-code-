"""The cast of this episode. Each look is a dict in rig.LOOK (see the skill's engine reference for every key).

Model sheet before animating (from tools/toon):  python -m cast.sheet ../../episodes/starter/toon/looks.py nora
"""
import rig

rig.LOOK["nora"] = dict(h=1.64, skin="#eec4a2", hair="#3f2a20", style="neat", top="#c8663e", pants="#2f3550",
                        shoes="#23222a", iris="#4d6a52", build=0.92, brow=0.85, back=True)
