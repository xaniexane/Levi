"""sparksense — ambient entity detection with described actions.

Studied from: retired-software-revival-research-20260916-0004/report.md (Section 30).

The load-bearing idea: the system *notices* actionable things inside
ordinary text — dates, durations, money, addresses — and quietly offers
what you could do with them. Ambient, background, zero ceremony.

LEVI's take: ``SparkSense`` runs original regex-based scanners over
any text and returns ``Detection``s. Every detection carries
``actions`` — *descriptors* of contextual actions ("schedule for this
date", "set a timer", "flag in budget"), never executed. LEVI looks,
never touches: no calendar writes, no timers armed, no side effects at
all. The caller decides what any action means in its own world.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

ORIGIN = "levi-revival/sparksense"


@dataclass
class Detection:
    """One noticed entity."""

    kind: str  # "date" | "duration" | "money" | "address"
    text: str  # the exact matched substring
    span: Tuple[int, int]  # (start, end) offsets into the source text
    value: str  # normalized-ish value for the caller to use
    actions: List[str] = field(default_factory=list)  # DESCRIBED, never executed


# Original patterns, written for LEVI — deliberately conservative so the
# sense stays quiet instead of hallucinating entities.
_MONTHS = (
    "jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    "jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|"
    "nov(?:ember)?|dec(?:ember)?"
)

_DATE_PATTERNS = [
    re.compile(
        rf"\b(?:{_MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?(?:\s*,?\s*\d{{4}})?", re.I
    ),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),  # 2026-09-16
    re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b"),  # 9/16 or 9/16/2026
    re.compile(
        r"\b(?:today|tomorrow|tonight|next\s+(?:week|month|monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b",
        re.I,
    ),
]

_DURATION_PATTERNS = [
    re.compile(
        r"\b\d+(?:\.\d+)?\s*(?:hours?|hrs?|minutes?|mins?|seconds?|secs?|days?|weeks?)\b",
        re.I,
    ),
]

_MONEY_PATTERNS = [
    re.compile(r"\$\s?\d[\d,]*(?:\.\d{2})?\b"),  # $12.50
    re.compile(r"\b(?:USD|EUR|GBP)\s?\d[\d,]*(?:\.\d{2})?\b", re.I),
]

_ADDRESS_PATTERNS = [
    re.compile(
        r"\b\d{1,5}\s+[A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*){0,3}\s+"
        r"(?:St(?:reet)?|Ave(?:nue)?|Rd|Road|Blvd|Ln|Lane|Dr|Drive|Ct|Way|Pl|Place)\b"
    ),
]

_ACTION_HINTS: Dict[str, List[str]] = {
    "date": [
        "schedule: create a calendar entry for this date",
        "remind: set a reminder tied to this date",
    ],
    "duration": [
        "timer: start a countdown for this duration",
        "log: record this duration against the current task",
    ],
    "money": [
        "budget: flag this amount for budget review",
        "split: propose splitting this amount",
    ],
    "address": [
        "map: look up this address on a map",
        "route: plan a route to this address",
    ],
}


def _scan(patterns: List[re.Pattern], kind: str, text: str) -> List[Detection]:
    found: List[Detection] = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            found.append(
                Detection(
                    kind=kind,
                    text=match.group(0),
                    span=(match.start(), match.end()),
                    value=match.group(0).strip(),
                    actions=list(_ACTION_HINTS[kind]),
                )
            )
    return found


class SparkSense:
    """Background scanners that notice actionable entities in text."""

    def sense(self, text: str) -> List[Detection]:
        """Scan ``text``; return detections ordered by position.

        Pure function: reads text, returns descriptions. No side effects.
        """
        detections: List[Detection] = []
        detections.extend(_scan(_DATE_PATTERNS, "date", text))
        detections.extend(_scan(_DURATION_PATTERNS, "duration", text))
        detections.extend(_scan(_MONEY_PATTERNS, "money", text))
        detections.extend(_scan(_ADDRESS_PATTERNS, "address", text))
        # de-dupe overlapping spans (first-listed kind wins on ties)
        detections.sort(key=lambda d: (d.span[0], d.span[1]))
        clean: List[Detection] = []
        for det in detections:
            if not any(
                det.span[0] < kept.span[1] and kept.span[0] < det.span[1]
                for kept in clean
            ):
                clean.append(det)
        return clean

    def kinds_present(self, text: str) -> List[str]:
        """Which entity kinds were noticed, in first-appearance order."""
        seen: List[str] = []
        for det in self.sense(text):
            if det.kind not in seen:
                seen.append(det.kind)
        return seen
