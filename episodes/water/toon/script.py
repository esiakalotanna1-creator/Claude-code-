"""WHAT IF WATER DISAPPEARED FOR 5 SECONDS: the beats (same format as episodes/callback: tts.py + build_tl.py)."""
TITLE = "5 SECONDS WITHOUT WATER"
LABEL = "WHAT IF"
VOICES = dict(NAR=("af_heart", 1.0, "en-us"))

BEATS = [
    ("hook", "NAR", "What if every drop of water on Earth disappeared... for just five seconds?",
     ["What if", "every drop", "of [water]", "on Earth", "[disappeared]...", "for just", "[five seconds]?"], 0.3, {"hold": 0.4}),
    ("s1", "NAR", "Second one.", ["Second [one]."], 0.2, {}),
    ("gone", "NAR", "Every ocean. Every river. Every cloud. Gone.", ["Every [ocean].", "Every river.", "Every cloud.", "[Gone]."], 0.2, {}),
    ("you", "NAR", "And so is the water inside you.", ["And so is", "the water", "[inside you]."], 0.3, {}),
    ("sixty", "NAR", "You're sixty percent water. In one blink, you lose more than half your body weight.",
     ["You're", "[sixty percent]", "water.", "In one blink,", "you lose", "more than [half]", "your body weight."], 0.2, {}),
    ("diet", "NAR", "Great for your diet. Terrible for being alive.", ["Great for", "your [diet].", "Terrible for", "being [alive]."], 0.3, {"hold": 0.4}),
    ("s2", "NAR", "Second two.", ["Second [two]."], 0.3, {}),
    ("plants", "NAR", "Every plant on Earth crumbles to dust. Trees. Grass. Your mom's houseplants.",
     ["Every [plant]", "on Earth", "crumbles to [dust].", "Trees.", "Grass.", "Your mom's", "[houseplants]."], 0.2, {}),
    ("s3", "NAR", "Second three.", ["Second [three]."], 0.3, {}),
    ("concrete", "NAR", "Concrete is held together by water. Without it, skyscrapers crumble like cookies.",
     ["Concrete", "is held together", "by [water].", "Without it,", "skyscrapers", "crumble like [cookies]."], 0.2, {}),
    ("ships", "NAR", "At sea, every ship drops into a hole up to eleven kilometers deep.",
     ["At sea,", "every [ship]", "drops into a hole", "up to [eleven kilometers]", "deep."], 0.3, {}),
    ("fall", "NAR", "In five seconds, they fall a hundred and twenty meters. A forty story building.",
     ["In five seconds,", "they fall", "[120 meters].", "A forty story", "[building]."], 0.2, {}),
    ("s4", "NAR", "Second four.", ["Second [four]."], 0.3, {}),
    ("sky", "NAR", "The sky turns perfectly clear. No clouds. No rain. Just silence.",
     ["The sky turns", "perfectly [clear].", "No clouds.", "No rain.", "Just [silence]."], 0.2, {"hold": 0.6}),
    ("s5", "NAR", "Second five.", ["Second [five]."], 0.3, {}),
    ("back", "NAR", "The water comes back. All of it. At once.", ["The water", "comes [back].", "All of it.", "At [once]."], 0.2, {"hold": 0.5}),
    ("after", "NAR", "Ships are a hundred meters underwater. Cities are rubble. And you... are a little pile of dust in your clothes.",
     ["Ships are", "a hundred meters", "[underwater].", "Cities are", "[rubble].", "And you...", "are a little", "pile of [dust]", "in your clothes."], 0.3, {"hold": 0.5}),
    ("but", "NAR", "But not everything died.", ["But not", "everything [died]."], 0.4, {"hold": 0.4}),
    ("tardi", "NAR", "Tardigrades survive being dried out completely. They'll shake off the dust...",
     ["[Tardigrades]", "survive being", "dried out", "completely.", "They'll shake", "off the [dust]..."], 0.2, {}),
    ("planet", "NAR", "...and finally have the planet to themselves.", ["...and finally", "have the [planet]", "to themselves."], 0.2, {"hold": 2.2}),
]
