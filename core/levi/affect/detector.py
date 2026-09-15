"""Affect perception — lexicon/heuristic emotion detection from user text.

HARD HONESTY RULE (binding): this module does **pattern-based affect
modeling**, not felt emotion. It matches word patterns against small
hand-built lexicons and returns operational labels (valence, arousal,
emotion categories) that LEVI uses to *shape its conduct* — e.g. stay
calm when the user is angry, soften when they are distressed. It does
not feel anything, does not experience the user's emotions, and its
labels are probabilistic guesses about *text*, not knowledge of a
person's inner state. No sentience or subjective-experience claims may
be built on top of this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List

# Six basic emotion categories used across the engine.
EMOTIONS = ("joy", "sadness", "anger", "fear", "surprise", "disgust")


@dataclass
class EmotionReading:
    """One turn's affect read. All scores are heuristic, 0..1 unless noted."""

    valence: float = 0.0  # -1 (very negative) .. +1 (very positive)
    arousal: float = 0.0  # 0 (flat) .. 1 (highly activated)
    emotions: Dict[str, float] = field(default_factory=dict)
    dominant: str = "neutral"  # top emotion or "neutral"
    stress_signals: List[str] = field(default_factory=list)
    confidence: float = 0.0  # how much lexical evidence was found
    cues: List[str] = field(default_factory=list)  # matched cue words

    def to_dict(self) -> Dict:
        return {
            "valence": round(self.valence, 3),
            "arousal": round(self.arousal, 3),
            "emotions": {k: round(v, 3) for k, v in self.emotions.items()},
            "dominant": self.dominant,
            "stress_signals": self.stress_signals,
            "confidence": round(self.confidence, 3),
            "cues": self.cues[:10],
        }


# ---------------------------------------------------------------------------
# Lexicons — (word/phrase, weight). Weights are heuristic, tuned for
# precision over recall: better to under-read than to over-claim.
# ---------------------------------------------------------------------------

_LEXICON: Dict[str, List[tuple]] = {
    "joy": [
        ("happy", 0.7),
        ("joy", 0.8),
        ("delighted", 0.8),
        ("excited", 0.7),
        ("great", 0.5),
        ("awesome", 0.6),
        ("wonderful", 0.7),
        ("love", 0.6),
        ("glad", 0.6),
        ("thrilled", 0.8),
        ("fantastic", 0.6),
        ("amazing", 0.5),
        ("lol", 0.4),
        ("haha", 0.5),
        ("yay", 0.6),
        ("relieved", 0.5),
        ("proud", 0.5),
        ("grateful", 0.5),
        ("thank", 0.3),
        ("thanks", 0.3),
    ],
    "sadness": [
        ("sad", 0.7),
        ("depressed", 0.8),
        ("heartbroken", 0.85),
        ("grief", 0.8),
        ("grieving", 0.8),
        ("lonely", 0.7),
        ("cry", 0.6),
        ("crying", 0.65),
        ("tears", 0.6),
        ("miss", 0.4),
        ("lost", 0.45),
        ("hopeless", 0.75),
        ("empty", 0.5),
        ("down", 0.35),
        ("blue", 0.3),
    ],
    "anger": [
        ("angry", 0.7),
        ("furious", 0.85),
        ("enraged", 0.85),
        ("rage", 0.8),
        ("pissed", 0.75),
        ("hate", 0.65),
        ("annoyed", 0.5),
        ("frustrated", 0.55),
        ("frustrating", 0.55),
        ("irritated", 0.5),
        ("bullshit", 0.7),
        ("damn", 0.4),
        ("stupid", 0.55),
        ("idiot", 0.6),
        ("screw", 0.55),
        ("fed up", 0.6),
        ("sick of", 0.55),
    ],
    "fear": [
        ("afraid", 0.7),
        ("scared", 0.7),
        ("terrified", 0.85),
        ("fear", 0.7),
        ("anxious", 0.65),
        ("anxiety", 0.65),
        ("worried", 0.55),
        ("worry", 0.5),
        ("panic", 0.8),
        ("panicking", 0.8),
        ("dread", 0.7),
        ("nightmare", 0.6),
        ("unsafe", 0.6),
        ("threat", 0.55),
    ],
    "surprise": [
        ("surprised", 0.6),
        ("shocked", 0.7),
        ("wow", 0.5),
        ("unbelievable", 0.5),
        ("suddenly", 0.4),
        ("unexpected", 0.55),
        ("whoa", 0.5),
        ("can't believe", 0.55),
        ("astonished", 0.65),
    ],
    "disgust": [
        ("disgust", 0.7),
        ("disgusting", 0.75),
        ("gross", 0.6),
        ("revolting", 0.7),
        ("nasty", 0.55),
        ("sickening", 0.65),
        ("vile", 0.65),
    ],
}

# Phrases that signal acute stress / crisis regardless of emotion lexicon.
_STRESS_SIGNALS: List[tuple] = [
    (
        r"\b(kill myself|end it all|want to die|self[- ]?harm|suicid\w*)\b",
        "self-harm-ideation",
    ),
    (r"\b(can'?t (breathe|go on|take it|cope|sleep))\b", "overwhelm"),
    (r"\b(breaking point|falling apart|spiraling|spiral\w*)\b", "dysregulation"),
    (r"\b(burn\w* out|burnt out|no energy|running on empty|exhausted)\b", "exhaustion"),
    (r"\b(emergency|right now|asap|urgent\w*)\b", "urgency"),
]

_INTENSIFIERS = {
    "very": 1.3,
    "so": 1.35,
    "really": 1.3,
    "extremely": 1.6,
    "incredibly": 1.5,
    "super": 1.4,
    "utterly": 1.5,
    "completely": 1.3,
    "totally": 1.3,
    "absolutely": 1.4,
}

_NEGATIONS = {
    "not",
    "no",
    "never",
    "n't",
    "without",
    "hardly",
    "barely",
    "don",
    "doesn",
    "didn",
    "isn",
    "aren",
    "wasn",
    "weren",
    "won",
}

_VALENCE: Dict[str, float] = {
    "joy": 0.8,
    "surprise": 0.15,
    "sadness": -0.7,
    "anger": -0.6,
    "fear": -0.65,
    "disgust": -0.55,
}

_AROUSAL: Dict[str, float] = {
    "anger": 0.8,
    "fear": 0.75,
    "joy": 0.6,
    "surprise": 0.7,
    "disgust": 0.5,
    "sadness": 0.35,
}


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z']+", text.lower())


def detect(text: str) -> EmotionReading:
    """Run the heuristic detector over one user message.

    Deterministic, stdlib-only, no I/O. Returns neutral/low-confidence
    when there is no lexical evidence — never invents affect.
    """
    text = text or ""
    lowered = text.lower()
    tokens = _tokenize(text)

    emotions: Dict[str, float] = {e: 0.0 for e in EMOTIONS}
    cues: List[str] = []
    hits = 0
    clean_hits = 0  # hits not under negation — negated-only evidence is noise

    # Multi-word phrases first (joined token stream).
    joined = " ".join(tokens)
    for emo, pairs in _LEXICON.items():
        for phrase, weight in pairs:
            if " " in phrase:
                if phrase in joined:
                    emotions[emo] += weight
                    cues.append(phrase)
                    hits += 1

    # Single tokens with negation + intensifier handling (3-token window).
    for i, tok in enumerate(tokens):
        for emo, pairs in _LEXICON.items():
            for phrase, weight in pairs:
                if " " in phrase or phrase != tok:
                    continue
                w = weight
                window = tokens[max(0, i - 3) : i]
                negated = (
                    any(n in window for n in _NEGATIONS)
                    or tok.endswith("n't")
                    or any(t.endswith("n't") for t in window)
                )
                if negated:
                    # "not happy" -> damp, don't flip to sadness.
                    w *= 0.25
                for inten, mult in _INTENSIFIERS.items():
                    if inten in window:
                        w *= mult
                        break
                emotions[emo] += w
                cues.append(tok)
                hits += 1
                if not negated:
                    clean_hits += 1

    # Stress signals (regex over raw text — independent of lexicon).
    stress: List[str] = []
    for pattern, label in _STRESS_SIGNALS:
        if re.search(pattern, lowered):
            stress.append(label)
            if label == "self-harm-ideation":
                emotions["fear"] += 0.9
                emotions["sadness"] += 0.9
                hits += 2
                clean_hits += 2
            elif label in ("overwhelm", "dysregulation"):
                emotions["fear"] += 0.5
                emotions["sadness"] += 0.4
                hits += 1
                clean_hits += 1

    # Punctuation / caps arousal cues.
    arousal_boost = 0.0
    if re.search(r"!{2,}", text):
        arousal_boost += 0.25
    if re.search(r"\?{2,}", text):
        arousal_boost += 0.15
    words = re.findall(r"[A-Za-z]{2,}", text)
    if words and sum(1 for w in words if w.isupper()) / len(words) > 0.4:
        arousal_boost += 0.25

    total = sum(emotions.values())
    if total <= 0 or clean_hits == 0:
        # No evidence, or every hit was negated ("not happy") — refuse to
        # read affect into it. Neutral, zero confidence.
        return EmotionReading(
            valence=0.0,
            arousal=min(0.2, arousal_boost),
            emotions={e: 0.0 for e in EMOTIONS},
            dominant="neutral",
            stress_signals=stress,
            confidence=0.0,
            cues=cues,
        )

    # Normalize emotion scores.
    norm = {e: v / total for e, v in emotions.items()}
    dominant = max(norm, key=norm.get)

    valence = sum(norm[e] * _VALENCE[e] for e in EMOTIONS)
    arousal = sum(norm[e] * _AROUSAL[e] for e in EMOTIONS)
    arousal = min(1.0, arousal + arousal_boost * norm[dominant])
    # Stress always raises arousal.
    if stress:
        arousal = min(1.0, arousal + 0.15)

    # Confidence: more independent hits -> more confident, capped.
    confidence = min(1.0, 0.25 + 0.15 * hits)

    return EmotionReading(
        valence=max(-1.0, min(1.0, valence)),
        arousal=arousal,
        emotions={e: round(v, 4) for e, v in norm.items()},
        dominant=dominant if norm[dominant] >= 0.25 else "neutral",
        stress_signals=stress,
        confidence=confidence,
        cues=cues,
    )
