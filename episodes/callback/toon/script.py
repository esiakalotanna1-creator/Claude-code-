"""LEAVE A MESSAGE: the beats, in order.

BEATS = (id, speaker, text, captions, gap_before, extra)
    speaker: NAR, FRANK, THEO, MAYA (a voiced line, rendered by tts.py into audio/lines/<id>.wav) or SCREEN
             (a silent beat: something happens on a phone screen; extra["dur"] is how long it holds).
    captions: 1-4 word chunks, [word] is the red keyword; [] for none.
    gap_before: seconds of picture before this beat starts (after the previous one ends).
    extra: tts = the text sent to the voice (numbers spelled out), speed, hold (seconds kept after the line).
build_tl.py lays the beats end to end from the real take lengths and writes timeline.json.
"""

TITLE = "LEAVE A MESSAGE"
LABEL = "A SHORT STORY"

VOICES = dict(NAR=("af_heart", 0.94, "en-us"), FRANK=("am_michael", 0.92, "en-us"), THEO=("am_puck", 0.98, "en-us"),
              MAYA=("af_bella", 0.95, "en-us"))

BEATS = [
    ("open", "NAR", "For eleven months, Maya called her father every night at eleven.",
     ["For eleven months,", "Maya called", "her [father]", "every night", "at eleven."], 0.5, {}),
    ("dead", "NAR", "He had been dead for all of them.", ["He had been", "[dead]", "for all of them."], 0.35, {}),
    ("greet", "FRANK", "Hey, it's Frank. Leave a message, kiddo. I'll call you back.",
     ["Hey, it's Frank.", "Leave a message,", "[kiddo].", "I'll call you back."], 0.9, {}),
    ("never", "NAR", "She never left one. She just listened to him say it. Then she hung up.",
     ["She never", "left one.", "She just [listened]", "to him say it.", "Then she hung up."], 0.5, {}),
    ("twice", "NAR", "Tonight, it rang twice.", ["Tonight,", "it rang [twice]."], 0.8, {"hold": 0.6}),
    ("hello", "THEO", "...Hello?", ["...[Hello]?"], 0.4, {"tts": "Hello?", "hold": 0.4}),
    ("drop", "NAR", "She hung up so fast she dropped the phone.", ["She hung up", "so fast", "she [dropped]", "the phone."], 0.25, {}),
    ("across", "NAR", "Across town, Theo stared at his screen.", ["Across town,", "[Theo] stared", "at his screen."], 0.9, {}),
    ("missed", "NAR", "Twenty-one missed calls. Same number. Always eleven o'clock. Never a message.",
     ["Twenty-one", "[missed] calls.", "Same number.", "Always", "eleven o'clock.", "Never a message."], 0.3, {}),
    ("weeks", "NAR", "He'd only had the number for three weeks.", ["He'd only had", "the number", "for three [weeks]."], 0.3, {}),
    ("who", "SCREEN", "who is this?", [], 0.3, {"dur": 2.6}),
    ("typed", "NAR", "Maya typed for a long time.", ["Maya [typed]", "for a long time."], 0.4, {"hold": 0.8}),
    ("msg", "MAYA", "This was my dad's number. He died last winter. I call to hear his voicemail. I'm sorry. I'll stop.",
     ["This was", "my dad's number.", "He died", "last [winter].", "I call to hear", "his voicemail.", "I'm sorry.", "I'll stop."], 0.3, {"hold": 0.5}),
    ("dots", "NAR", "The dots appeared. Disappeared. Appeared again.", ["The dots", "appeared.", "Disappeared.", "Appeared [again]."], 0.5, {}),
    ("dont", "SCREEN", "you don't have to stop", [], 0.2, {"dur": 2.8}),
    ("next", "NAR", "The next night, at eleven, her phone buzzed first.", ["The next night,", "at eleven,", "her phone", "buzzed [first]."], 0.9, {}),
    ("ok", "SCREEN", "it's 11. you ok?", [], 0.2, {"dur": 2.2}),
    ("wasnt", "NAR", "She wasn't. So she called. And he picked up.", ["She [wasn't].", "So she called.", "And he", "picked up."], 0.3, {}),
    ("loud", "NAR", "His mom worked nights at the hospital. The house was loud when it was empty. So was her apartment.",
     ["His mom", "worked nights", "at the hospital.", "The house", "was [loud]", "when it was empty.", "So was", "her apartment."], 0.8, {}),
    ("homework", "NAR", "So every night at eleven: chemistry homework. Terrible jokes. Long silences that didn't feel lonely.",
     ["So every night", "at eleven:", "chemistry homework.", "Terrible [jokes].", "Long silences", "that didn't", "feel [lonely]."], 0.8, {}),
    ("laughed", "NAR", "One night, she laughed. Out loud. For the first time in a year.",
     ["One night,", "she [laughed].", "Out loud.", "For the first time", "in a year."], 0.6, {"hold": 0.8}),
    ("told", "NAR", "She told him how every call with her dad ended the same way.",
     ["She told him", "how every call", "with her dad", "ended the [same] way."], 0.6, {}),
    ("callback", "MAYA", "I'll call you back. He always did. Until he didn't.",
     ["\"I'll call", "you back.\"", "He [always] did.", "Until he didn't."], 0.4, {"hold": 0.7}),
    ("sound", "THEO", "What did he sound like?", ["What did he", "[sound] like?"], 0.5, {"hold": 0.5}),
    ("smiling", "MAYA", "Like he was smiling.", ["Like he was", "[smiling]."], 0.6, {"hold": 1.2}),
    ("thursday", "NAR", "The anniversary came on a Thursday.", ["The [anniversary]", "came on", "a Thursday."], 1.2, {}),
    ("goodbye", "NAR", "At eleven, Maya decided it was time to say goodbye. To the number. To all of it.",
     ["At eleven,", "Maya decided", "it was time", "to say [goodbye].", "To the number.", "To all of it."], 0.4, {}),
    ("rang", "NAR", "She called. It rang. And rang. Theo didn't pick up.",
     ["She called.", "It rang.", "And rang.", "Theo didn't", "[pick up]."], 0.5, {"hold": 0.8}),
    ("voice", "NAR", "Then, a voice she didn't expect.", ["Then, a voice", "she didn't [expect]."], 0.6, {"hold": 0.3}),
    ("newgreet", "THEO", "Hey. This isn't Frank. But this number still works. Leave a message, kiddo. Someone will call you back.",
     ["Hey.", "This isn't Frank.", "But this number", "still [works].", "Leave a message,", "kiddo.", "Someone will", "call you [back]."], 0.4, {"hold": 0.6}),
    ("beep", "NAR", "And for the first time in a year, Maya spoke after the beep.",
     ["And for the", "first time", "in a year,", "Maya [spoke]", "after the beep."], 0.6, {"hold": 0.8}),
    ("okay", "MAYA", "Hi, Dad. ...I'm okay.", ["Hi, [Dad].", "...I'm okay."], 0.5, {"tts": "Hi, Dad. ... I'm okay.", "hold": 1.0}),
    ("hungup", "NAR", "She hung up. The screen lit up before she could put it down.",
     ["She hung up.", "The screen", "[lit up]", "before she could", "put it down."], 0.6, {}),
    ("incoming", "SCREEN", "Incoming call: DAD", [], 0.2, {"dur": 3.0}),
    ("last", "NAR", "For the first time in a year, someone called her back.",
     ["For the first time", "in a year,", "someone called", "her [back]."], 0.4, {"hold": 3.0}),
]
