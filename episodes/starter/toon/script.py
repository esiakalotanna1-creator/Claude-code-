"""THE LAMP: a 12.5 s starter episode. Copy this folder to start your own reel.

PHRASES = (placed at, text, caption chunks, source span). Caption chunks are 1-4 words; [word] is the red keyword.
The source span is (start, end) of the phrase inside your narration take (SOURCE), or None before you have a take:
build_tl.py then estimates each phrase's length from its word count, so the picture can be blocked first.
MARKS are the story beats in seconds; reel.py and scenes.py read them from timeline.json.
"""

TITLE = "THE LAMP"
LABEL = "A SHORT STORY"                       # the small line shown over the first seconds
SOURCE = "audio/narration_take.wav"           # one take, 48 kHz mono (not shipped)

PHRASES = [
    (0.40, "Every night at nine, my lamp flickers once.", ["Every night", "at [nine],", "my lamp", "flickers [once]."], None),
    (4.00, "Tonight, it flickered twice.", ["Tonight,", "it flickered", "[twice]."], None),
    (7.20, "Then something answered from the hallway.", ["Then something", "[answered]", "from the hallway."], None),
    (10.30, "Two knocks.", ["[Two] knocks."], None),
]

MARKS = dict(wide=0.0, close=3.6, door=6.8, feet=9.8, end=12.5)
