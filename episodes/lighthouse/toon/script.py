"""THE LIGHT AT SEA: a 45 s reel. One keeper, one lantern room, one answering light.

PHRASES = (placed at, text, caption chunks, source span). [word] is the red keyword. Source span is None until a
narration take exists (build_tl.py then estimates lengths from word counts).
"""

TITLE = "THE LIGHT AT SEA"
LABEL = "A SHORT STORY"
SOURCE = "audio/narration_take.wav"

PHRASES = [
    (0.40, "Every night at dusk, the keeper flashes his lamp three times.",
     ["Every night", "at dusk,", "the keeper", "flashes his lamp", "[three] times."], None),
    (4.90, "Tonight, something out at sea flashed back.",
     ["Tonight,", "something", "out at sea", "[flashed back]."], None),
    (8.00, "Same rhythm. Same count. Where no ship sails.",
     ["Same rhythm.", "Same count.", "Where no [ship] sails."], None),
    (11.50, "He flashed twice. It answered twice.",
     ["He flashed [twice].", "It answered [twice]."], None),
    (14.30, "He flashed once. It came closer.",
     ["He flashed [once].", "It came [closer]."], None),
    (17.10, "Closer, every time, until it hung outside the glass.",
     ["Closer,", "every time,", "until it hung", "outside the [glass]."], None),
    (21.00, "He opened the logbook. Thirty years of entries.",
     ["He opened", "the [logbook].", "Thirty years", "of entries."], None),
    (24.50, "Every night, the same line: Light seen. Answered.",
     ["Every night,", "the same line:", "Light seen.", "[Answered]."], None),
    (28.40, "The light wasn't copying him.",
     ["The light", "wasn't", "[copying] him."], None),
    (31.00, "He had always been copying it.",
     ["He had", "always been", "[copying] it."], None),
    (34.20, "Tonight, he kept his hand still.",
     ["Tonight,", "he kept", "his hand [still]."], None),
    (37.00, "The lamp flashed anyway.",
     ["The lamp", "flashed [anyway]."], None),
    (39.90, "Three times.",
     ["[Three] times."], None),
]

MARKS = dict(wide=0.0, face=3.4, window=5.2, react=8.0, lever=10.0, window2=12.6, lever2=14.2, window3=15.0, react2=17.0,
             window4=18.8,
             book=20.6, page=24.4, dread=28.2, realise=31.0, hand=34.0, lamp=37.0, final=40.0, end=45.0)
