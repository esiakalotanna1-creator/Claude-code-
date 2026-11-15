"""THREE SECONDS LATE, part 1: "IT MOVED FIRST". Beats as in episodes/onelook (tts.py -> audio/lines, build_tl.py ->
timeline.json). House rule: fast audio, so gaps are tiny and there are no "..." pauses. Text: [word] = caption accent.
Chunks are made automatically (2-3 words)."""
import re

TITLE = "THREE SECONDS LATE"
LABEL = "PART 1"
# speaker: (voice, speed, lang, pitch in semitones; pitch raises the tempo by the same ratio)
VOICES = dict(KAI=("am_puck", 1.08, "en-us", 2.0), ANCHOR=("af_sarah", 1.18, "en-us", 0.0),
              GMA=("bf_isabella", 1.16, "en-gb", -1.5), REMI=("af_sky", 1.06, "en-us", 3.5))

G = 0.06
_B = [
    ("hook", "KAI", "At [3:07] a.m. on a Tuesday, every reflection on Earth fell [three seconds] behind.",
     {"tts": "At three oh seven A M on a Tuesday, every reflection on Earth fell three seconds behind."}),
    ("friday", "KAI", "By Friday, they'd stopped trying to [catch up].", {}),
    ("mirrors", "KAI", "[Mirrors].", {}),
    ("windows", "KAI", "[Windows].", {}),
    ("puddles", "KAI", "[Puddles].", {}),
    ("phone", "KAI", "Your phone, when the screen goes [black].", {}),
    ("face", "KAI", "If it shows your face, it isn't on your [side] anymore.", {}),
    ("dad", "KAI", "My dad said it was [fake]. Then he shaved without a mirror.", {}),
    ("blender", "KAI", "Now he looks like he lost a fight with a [blender]. And he believes everything.", {}),
    ("anchor1", "ANCHOR", "The delay is [growing]. Three seconds. Then five. Then [ten].", {}),
    ("anchor2", "ANCHOR", "And if your reflection ever moves [before] you do, do not look away.", {}),
    ("normal", "KAI", "Cool. Normal [Tuesday].", {}),
    ("cover", "KAI", "So we covered [every] mirror in the house.", {}),
    ("gma1", "GMA", "I've survived two husbands, a recession, and your mother's [cooking]. I am not scared of my own face.", {}),
    ("remi", "REMI", "What if your face is scared of [you]?", {}),
    ("gma2", "GMA", "Then she's got good [sense].", {}),
    ("vanity", "KAI", "She kept her big mirror [uncovered].", {}),
    ("night", "KAI", "Two a.m. My phone went black, and my reflection put it down a whole [second] after me.",
     {"tts": "Two A M. My phone went black, and my reflection put it down a whole second after me."}),
    ("laugh", "KAI", "Then I heard Grandma [laughing]. Talking to someone.", {}),
    ("pretty", "GMA", "Oh, you were always the [pretty] one.", {}),
    ("which", "KAI", "Grandma? Which one of you is [talking]?", {}),
    ("card", "SCREEN", "", {"dur": 2.2}),
]


def chunks(text):
    words, out, cur = text.split(), [], []
    for w in words:
        cur.append(w)
        if len(cur) == 3 or re.search(r"[.,?!]\]?$", w):
            out.append(" ".join(cur))
            cur = []
    if cur:
        out.append(" ".join(cur))
    return out


BEATS = [(bid, spk, re.sub(r"[\[\]]", "", txt), chunks(txt) if txt else [], 0.0 if i == 0 else G, ex)
         for i, (bid, spk, txt, ex) in enumerate(_B)]
