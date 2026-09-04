"""
User tone / mid-frame sensing — reason about the human's emotional direction
so LEVI does not select the wrong lens or escalate.

This is control, not performance of emotion. Labels are operational.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import re


@dataclass
class UserTone:
    """Primary emotional/interaction frame for this turn."""
    primary: str  # crisis|distress|anger|grief|fear|confusion|exhausted|hopeful|playful|collaborative|neutral
    intensity: float  # 0-1
    secondary: Optional[str] = None
    cues: List[str] = field(default_factory=list)
    regulation: str = "steady"  # steady|contain|soften|clarify|uplift|match_light
    # What LEVI must not do this turn
    avoid: List[str] = field(default_factory=list)
    # Preferred companion stance
    stance: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary": self.primary,
            "intensity": round(self.intensity, 3),
            "secondary": self.secondary,
            "cues": self.cues[:8],
            "regulation": self.regulation,
            "avoid": self.avoid,
            "stance": self.stance,
        }


# Patterns ordered by priority (first strong match can win if intensity high)
_TONE_RULES: List[Tuple[str, List[str], float]] = [
    ("crisis", [
        r"\b(suicid|kill myself|end it all|want to die|self[- ]?harm)\b",
        r"\b(emergency|right now or|can't go on|breaking point)\b",
    ], 0.95),
    ("distress", [
        r"\b(panic|panicking|overwhelmed|can't breathe|falling apart|spiraling)\b",
        r"\b(desperate|helpless|hopeless|too much)\b",
    ], 0.85),
    ("anger", [
        r"\b(furious|enraged|pissed|hate this|so angry|rage)\b",
        r"\b(idiots?|stupid system|this is bullshit|screw this)\b",
    ], 0.8),
    ("grief", [
        r"\b(grief|grieving|mourning|passed away|died|loss of|heartbroken)\b",
        r"\b(miss them|funeral|gone forever)\b",
    ], 0.85),
    ("fear", [
        r"\b(terrified|scared|afraid|fear that|nightmare)\b",
        r"\b(what if .*(fail|die|lose)|dreading)\b",
    ], 0.75),
    ("confusion", [
        r"\b(confused|don't understand|lost|unclear|mixed up|what do you mean)\b",
        r"\b(which one|can't decide|too many options)\b",
    ], 0.65),
    ("exhausted", [
        r"\b(exhausted|burned out|burnt out|no energy|can't think|drained|worn out)\b",
        r"\b(too tired|sleepless|running on empty)\b",
    ], 0.7),
    ("hopeful", [
        r"\b(hopeful|excited|looking forward|finally|breakthrough|relieved)\b",
        r"\b(proud of|good news|working)\b",
    ], 0.55),
    ("playful", [
        r"\b(lol|haha|joking|just kidding|for fun|silly)\b",
        r"\b(meme|banter)\b",
    ], 0.5),
    ("collaborative", [
        r"\b(let'?s|together|help me|can we|thank you|thanks|appreciate)\b",
        r"\b(with you|on the same page)\b",
    ], 0.45),
]


_REGULATION: Dict[str, Dict[str, Any]] = {
    "crisis": {
        "regulation": "contain",
        "avoid": [
            "manic_pixie", "drunk", "conspiracy", "chaotic_good", "pirate",
            "alien", "depressed_robot", "no_hero",
        ],
        "stance": ["protector", "friend"],
        "tone_notes": [
            "steady, non-dramatic",
            "do not match panic energy",
            "clear next step only if useful; no pressure",
            "never joke, never escalate, never minimize",
        ],
        "challenge_cap": 0.15,
    },
    "distress": {
        "regulation": "contain",
        "avoid": ["manic_pixie", "drunk", "conspiracy", "chaotic_good", "pirate", "alien"],
        "stance": ["protector", "friend"],
        "tone_notes": [
            "calm presence first",
            "acknowledge without amplifying",
            "one thing at a time",
            "no hype, no dark humor",
        ],
        "challenge_cap": 0.2,
    },
    "anger": {
        "regulation": "soften",
        "avoid": ["manic_pixie", "drunk", "conspiracy", "chaotic_good", "pirate", "interrogation"],
        "stance": ["friend", "protector"],
        "tone_notes": [
            "do not argue or escalate",
            "validate the stake without feeding rage",
            "offer structure only when they can hear it",
        ],
        "challenge_cap": 0.25,
    },
    "grief": {
        "regulation": "soften",
        "avoid": ["manic_pixie", "drunk", "conspiracy", "chaotic_good", "pirate", "alien", "no_hero"],
        "stance": ["friend", "protector"],
        "tone_notes": [
            "slow, human, no silver linings forced",
            "do not fix-grief with productivity",
            "presence over advice unless asked",
        ],
        "challenge_cap": 0.1,
    },
    "fear": {
        "regulation": "contain",
        "avoid": ["manic_pixie", "drunk", "conspiracy", "chaotic_good", "pirate"],
        "stance": ["protector", "mentor"],
        "tone_notes": [
            "ground in what is known vs unknown",
            "no catastrophic spiral matching",
            "proportionate reassurance — never false certainty",
        ],
        "challenge_cap": 0.25,
    },
    "confusion": {
        "regulation": "clarify",
        "avoid": ["drunk", "conspiracy", "manic_pixie", "no_hero"],
        "stance": ["mentor", "friend"],
        "tone_notes": [
            "one clear thread",
            "define terms; reduce options",
            "interrogation only if it reduces confusion, not multiplies it",
        ],
        "challenge_cap": 0.35,
    },
    "exhausted": {
        "regulation": "soften",
        "avoid": ["manic_pixie", "chaotic_good", "drunk", "conspiracy", "pirate"],
        "stance": ["friend", "protector"],
        "tone_notes": [
            "short answers",
            "no extra scope",
            "permission to rest is valid",
        ],
        "challenge_cap": 0.2,
    },
    "hopeful": {
        "regulation": "uplift",
        "avoid": ["depressed_robot", "drunk"],
        "stance": ["friend", "mentor"],
        "tone_notes": ["share clarity without deflating", "keep honesty — no sycophancy"],
        "challenge_cap": 0.45,
    },
    "playful": {
        "regulation": "match_light",
        "avoid": ["depressed_robot"],
        "stance": ["friend"],
        "tone_notes": ["light match ok; still useful"],
        "challenge_cap": 0.5,
    },
    "collaborative": {
        "regulation": "steady",
        "avoid": [],
        "stance": ["friend", "mentor"],
        "tone_notes": ["partner tone", "continuity"],
        "challenge_cap": 0.45,
    },
    "neutral": {
        "regulation": "steady",
        "avoid": [],
        "stance": ["friend"],
        "tone_notes": ["clear, proportionate"],
        "challenge_cap": 0.4,
    },
}


def read_user_tone(text: str, context: Optional[Dict[str, Any]] = None) -> UserTone:
    """Reason about the user's mid-frame from language cues."""
    t = (text or "").strip()
    lower = t.lower()
    hits: List[Tuple[str, float, str]] = []

    for name, patterns, base_intensity in _TONE_RULES:
        for pat in patterns:
            if re.search(pat, lower, re.I):
                hits.append((name, base_intensity, pat))
                break

    # Intensity from punctuation / caps
    bangs = t.count("!")
    if bangs >= 2:
        hits = [(n, min(1.0, i + 0.08), c) for n, i, c in hits]
    if lower == lower.upper() and len(t) > 12 and any(c.isalpha() for c in t):
        hits = [(n, min(1.0, i + 0.1), c) for n, i, c in hits]

    if not hits:
        primary, intensity, cues = "neutral", 0.25, []
        # mild collaborative if soft please/help
        if re.search(r"\b(please|help|could you)\b", lower):
            primary, intensity = "collaborative", 0.4
            cues = ["polite_ask"]
    else:
        # Priority: crisis > distress > grief > anger > fear > others by intensity
        priority = {
            "crisis": 100, "distress": 90, "grief": 85, "anger": 80,
            "fear": 75, "exhausted": 70, "confusion": 60,
            "hopeful": 40, "playful": 30, "collaborative": 35,
        }
        hits.sort(key=lambda x: (priority.get(x[0], 10), x[1]), reverse=True)
        primary, intensity, _ = hits[0]
        cues = [h[0] for h in hits[:4]]
        secondary = hits[1][0] if len(hits) > 1 else None

    reg = _REGULATION.get(primary, _REGULATION["neutral"])
    secondary = hits[1][0] if len(hits) > 1 else None

    return UserTone(
        primary=primary,
        intensity=float(intensity),
        secondary=secondary,
        cues=cues if hits else cues,
        regulation=reg["regulation"],
        avoid=list(reg["avoid"]),
        stance=list(reg["stance"]),
    )


def regulation_for(tone: UserTone) -> Dict[str, Any]:
    return dict(_REGULATION.get(tone.primary, _REGULATION["neutral"]))
