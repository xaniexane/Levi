"""
Story quality rater — offline scoring of generated prose.

Dimensions: length, sensory, scar/continuity, specificity, anti-repetition, structure.
Score 0–10. Used in stress tests and `levi story --rate`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List
import re


@dataclass
class QualityReport:
    score: float
    grade: str
    notes: List[str]
    words: int

    def format(self) -> str:
        lines = [
            f"══ Story quality  {self.score:.1f}/10  ({self.grade}) ══",
            f"words={self.words}",
        ]
        for n in self.notes:
            lines.append(f"  · {n}")
        return "\n".join(lines)


def _unique_ratio(text: str) -> float:
    words = re.findall(r"[a-zA-Z']+", text.lower())
    if not words:
        return 0.0
    return len(set(words)) / max(1, len(words))


def rate_text(text: str) -> QualityReport:
    notes: List[str] = []
    words = text.split()
    n = len(words)
    scores: List[float] = []

    # Length
    if n >= 120:
        scores.append(10)
        notes.append("length: strong")
    elif n >= 80:
        scores.append(8)
        notes.append("length: good")
    elif n >= 40:
        scores.append(5)
        notes.append("length: thin")
    else:
        scores.append(2)
        notes.append("length: too short")

    # Sensory
    sensory_cues = [
        "sound", "cold", "light", "taste", "air", "weight", "room", "door",
        "metallic", "temperature", "breath", "wrist", "pressure",
    ]
    sc = sum(1 for c in sensory_cues if c in text.lower())
    scores.append(min(10, 4 + sc * 1.2))
    notes.append(f"sensory cues≈{sc}")

    # Scar / continuity law
    scar_cues = ["scar", "wound", "compromise", "cost", "still", "invoice", "cascade", "nothing reset"]
    sk = sum(1 for c in scar_cues if c in text.lower())
    scores.append(min(10, 3 + sk * 1.5))
    notes.append(f"continuity/scar cues≈{sk}")

    # Specificity (proper names / concrete nouns heuristic)
    caps = len(re.findall(r"\b[A-Z][a-z]+\b", text))
    scores.append(min(10, 4 + min(caps, 8) * 0.7))
    notes.append(f"proper/concrete markers≈{caps}")

    # Anti-repetition
    ur = _unique_ratio(text)
    if ur >= 0.55:
        scores.append(10)
        notes.append(f"lexical diversity {ur:.2f} strong")
    elif ur >= 0.4:
        scores.append(7)
        notes.append(f"lexical diversity {ur:.2f} ok")
    else:
        scores.append(3)
        notes.append(f"lexical diversity {ur:.2f} repetitive")

    # Formula penalty
    formula = 0
    for bad in ["Premise pressure remained", "Wound law:", "Sensory edge —", "the place-time of the beat"]:
        if bad in text:
            formula += 1
    if formula:
        scores.append(max(2, 8 - formula * 2))
        notes.append(f"formula markers={formula} (lower is better)")
    else:
        scores.append(9)
        notes.append("formula markers=0")

    # Structure (paragraphs / beats)
    parts = [p for p in re.split(r"\n\n+", text) if p.strip()]
    if len(parts) >= 3 or text.count(".") >= 5:
        scores.append(9)
        notes.append("structure: multi-sentence/beat")
    else:
        scores.append(5)
        notes.append("structure: flat")

    score = sum(scores) / len(scores)
    if score >= 9:
        grade = "A"
    elif score >= 8:
        grade = "B+"
    elif score >= 7:
        grade = "B"
    elif score >= 6:
        grade = "C+"
    else:
        grade = "C"
    return QualityReport(score=round(score, 2), grade=grade, notes=notes, words=n)


def rate_story_dict(d: dict) -> QualityReport:
    body = d.get("body") or d.get("manuscript") or d.get("text") or ""
    if not body and d.get("beats"):
        body = "\n\n".join(str(b) for b in d["beats"])
    return rate_text(str(body))
