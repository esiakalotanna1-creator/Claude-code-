"""Reusable character kit for the toon rig (built for the Mara reel, kept as a kit).

Each module registers its looks in rig.LOOK on import and documents its pose keys. Shared costume layers live in
hair.py (gravity strands) and faces.py (creepy face styles). Model sheets: python -m cast.sheet <module> <look> (from tools/toon)
write assets/kit/cast/<look>.png.

    import cast.mara        # "mara": the Scandinavian nightmare spirit (pose: breeze, curl_R/L, creep)
"""
