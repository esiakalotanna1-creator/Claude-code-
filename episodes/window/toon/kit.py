"""Reuses the approved Jeff toon kit (Room, eases, washes) and the Smiling Man rig without copying them."""
import importlib.util
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
JEFF = os.path.join(ROOT, "episodes", "jeff", "toon")
SMILING = os.path.join(ROOT, "episodes", "smilingman", "toon")
sys.path.insert(0, os.path.join(ROOT, "tools", "toon"))
sys.path.append(JEFF)                       # jeff's scenes imports its own busstop module
sys.path.append(SMILING)                    # smiler.py imports the smilingman looks (Timmy cast)
_spec = importlib.util.spec_from_file_location("jeff_scenes", os.path.join(JEFF, "scenes.py"))
JS = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(JS)

B = JS.B
Room, lamp_item = JS.Room, JS.lamp_item
hold, win, lerp, vignette, wash = JS.hold, JS.win, JS.lerp, JS.vignette, JS.wash
