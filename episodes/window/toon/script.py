"""THE MAN AT THE WINDOW (the shot-by-shot brief is SPEC.md). Straight horror.

Narration: one take by one narrator (any TTS or a recording, 48 kHz mono), audio/narration_take.wav. Not shipped.
PHRASES = (start, end) of each spoken phrase in that take, and where it is placed on the reel (t). build_tl.py
cuts the phrases out, places them and writes audio/narration.wav + timeline.json (marks, lines, caption chunks).
"""

TITLE = "THE MAN AT THE WINDOW"
SOURCE = "audio/narration_take.wav"

# (src start, src end, placed at, text, caption chunks)
PHRASES = [
    (0.10, 1.28, 0.40, "When I looked up...", ["When I [looked up]..."]),
    (1.76, 3.90, 2.06, "there was a man pressed against my window.", ["there was a [man]", "pressed against", "my [window]."]),
    (4.52, 6.78, 4.82, "I had no idea how long he'd been there.", ["I had no idea", "how long", "he'd been there."]),
    (8.00, 9.18, 11.00, "He wasn't knocking.", ["He wasn't [knocking]."]),
    (9.86, 11.46, 12.80, "He wasn't asking for anything.", ["He wasn't asking", "for anything."]),
    (12.16, 15.16, 14.95, "He just stood there... smiling through the glass.", ["He just stood there...", "[smiling]", "through the glass."]),
    (16.34, 18.30, 20.60, "My wife was asleep upstairs.", ["My wife was asleep", "[upstairs]."]),
    (18.86, 20.44, 23.00, "Our little boy was in his crib.", ["Our little boy", "was in his [crib]."]),
    (21.02, 23.16, 25.20, "I wanted to shout... but couldn't.", ["I wanted to [shout]...", "but couldn't."]),
    (24.22, 25.38, 29.40, "I stood frozen.", ["I stood [frozen]."]),
    (26.48, 28.96, 32.00, "The gardening shears were still in my hand.", ["The gardening [shears]", "were still", "in my hand."]),
    (29.86, 32.20, 36.20, "Because I wasn't looking out of my house.", ["Because I wasn't", "looking [out]", "of my house."]),
    (32.86, 34.04, 41.00, "I was looking in.", ["I was looking [in]."]),
    (34.96, 36.16, 44.80, "He was inside.", ["He was [inside]."]),
    (36.72, 37.42, 46.60, "With them.", ["With them."]),
]

# shot boundaries (the spec's timings, nudged so each line lands on its picture)
MARKS = dict(hook=0.0, widen=3.0, dad=7.6, stare=10.6, hand=17.2, bed=20.4, mouth=24.8, slide=27.8, shears=31.6,
             pull=35.6, wide=40.4, inside=44.2, smile=48.0, black=50.2, end=50.8)
