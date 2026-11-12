"""The cast: Ned, the keeper of the light. Thin grey hair, a weathered face, a worn mustard oilskin and a red scarf.

Model sheet before animating (from tools/toon):  python -m cast.sheet ../../episodes/lighthouse/toon/looks.py ned
"""
import rig

rig.LOOK["ned"] = dict(h=1.74, skin="#d9a98a", hair="#a9a8b3", style="lank", top="#b98a2e", pants="#33384a",
                       shoes="#1f1e24", iris="#4f6b86", build=1.02, brow=1.0, wear="scarf", back=True)
