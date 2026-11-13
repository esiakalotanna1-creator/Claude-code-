"""ONE LOOK: a 'you have $1,000,000 and 100 days' survival reel (our own take on the eye-contact-virus format).
Beats as in episodes/callback (tts.py -> audio/lines, build_tl.py -> timeline.json). extra: day / budget = the HUD from
this beat on; item = what the money is spent on (a label card)."""

TITLE = "ONE LOOK"
LABEL = "100 DAYS · PART 1"
VOICES = dict(NAR=("af_heart", 1.02, "en-us"), MAYA=("af_bella", 0.95, "en-us"))

BEATS = [
    ("hook", "NAR", "There's a virus you don't catch by breathing. You catch it with your eyes.",
     ["There's a virus", "you don't catch", "by breathing.", "You catch it", "with your [eyes]."], 0.3, {}),
    ("second", "NAR", "One second of eye contact, and your mind is gone.", ["One second", "of [eye contact],", "and your mind", "is [gone]."], 0.2, {}),
    ("smile", "NAR", "You don't feel sick. You just smile... and look for the next person.",
     ["You don't", "feel sick.", "You just [smile]...", "and look for", "the [next person]."], 0.3, {}),
    ("alaska", "NAR", "It starts in a tiny fishing town in Alaska. Doctors call it low risk.",
     ["It starts", "in a tiny", "fishing town", "in [Alaska].", "Doctors call it", "[low risk]."], 0.5, {}),
    ("numbers", "NAR", "Then they run the numbers. Every country on Earth. Inside one hundred days.",
     ["Then they run", "the [numbers].", "Every country", "on Earth.", "Inside", "[100 days]."], 0.3, {}),
    ("deal", "NAR", "So here's the deal. You get one million dollars, and one hundred days to survive it.",
     ["So here's", "the deal.", "You get", "[$1,000,000],", "and 100 days", "to [survive] it."], 0.5, {"day": 100, "budget": 1000000}),
    ("house", "NAR", "A house deep in the woods. Three hundred and fifty grand.", ["A house", "deep in the [woods].", "$350,000."], 0.4,
     {"day": 95, "budget": 650000, "item": "CABIN IN THE WOODS  -$350,000"}),
    ("shutters", "NAR", "Steel shutters on every window.", ["Steel [shutters]", "on every window."], 0.3,
     {"day": 83, "budget": 600000, "item": "STEEL SHUTTERS  -$50,000"}),
    ("bunker", "NAR", "A bunker under the floor, with a blast door.", ["A [bunker]", "under the floor,", "with a blast door."], 0.3,
     {"day": 72, "budget": 400000, "item": "BUNKER + BLAST DOOR  -$200,000"}),
    ("cameras", "NAR", "Thermal cameras on the tree line. Because you can't check someone's eyes... without looking at them.",
     ["[Thermal] cameras", "on the tree line.", "Because you can't", "check someone's eyes...", "without [looking]", "at them."], 0.3,
     {"day": 60, "budget": 270000, "item": "THERMAL CAMERAS  -$130,000"}),
    ("food", "NAR", "A year of food, a wall of batteries, and a dog. Dogs don't care about eye contact.",
     ["A year of food,", "a wall of batteries,", "and a [dog].", "Dogs don't care", "about [eye contact]."], 0.3,
     {"day": 42, "budget": 25000, "item": "FOOD + POWER + DOG  -$245,000"}),
    ("helmet", "NAR", "And the last twenty-five thousand, on one helmet. The visor is solid black.",
     ["And the last", "$25,000,", "on one [helmet].", "The visor", "is solid [black]."], 0.3,
     {"day": 18, "budget": 0, "item": "BLACKOUT HELMET  -$25,000"}),
    ("zero", "NAR", "Zero dollars left.", ["[Zero] dollars left."], 0.3, {"day": 12, "budget": 0, "hold": 0.4}),
    ("city", "NAR", "Day one hundred. It reaches the city.", ["Day [100].", "It reaches", "the [city]."], 0.6, {"day": 0}),
    ("streets", "NAR", "Within hours, the streets are full of people. Smiling. Looking.",
     ["Within hours,", "the streets", "are full of people.", "[Smiling].", "[Looking]."], 0.3, {}),
    ("blind", "NAR", "Everyone left ties something over their eyes. The ones who don't... join the smile.",
     ["Everyone left", "ties something", "over their [eyes].", "The ones who don't...", "join the [smile]."], 0.3, {}),
    ("dark", "NAR", "Day one hundred and three. The TV goes dark.", ["Day 103.", "The TV", "goes [dark]."], 0.6, {"day": -3}),
    ("gate", "NAR", "Then the gate camera picks up movement.", ["Then the", "gate camera", "picks up [movement]."], 0.4, {}),
    ("woman", "NAR", "A woman. Blindfolded. Alone.", ["A [woman].", "Blindfolded.", "Alone."], 0.3, {}),
    ("please", "MAYA", "Please. I haven't looked at anyone. Please, let me in.",
     ["[Please].", "I haven't looked", "at anyone.", "Please,", "let me [in]."], 0.4, {"hold": 0.3}),
    ("heat", "NAR", "Your camera only sees heat. And you can't check her eyes... without opening the door.",
     ["Your camera", "only sees [heat].", "And you can't", "check her eyes...", "without opening", "the [door]."], 0.3, {}),
    ("trees", "NAR", "Behind her, between the trees, something is smiling.", ["Behind her,", "between the trees,", "something", "is [smiling]."], 0.4, {"hold": 0.5}),
    ("thirty", "NAR", "You have thirty seconds.", ["You have", "[30 seconds]."], 0.3, {}),
    ("choice", "NAR", "Open the gate. Or keep it closed. What do you do?",
     ["Open the gate.", "Or keep", "it [closed].", "What do", "[you] do?"], 0.3, {"hold": 2.5}),
]
