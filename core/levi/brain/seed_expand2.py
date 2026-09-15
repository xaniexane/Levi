"""Expansion pack II — interpenetration + condensed-ops literacy."""

from __future__ import annotations
from typing import List, Tuple

_RAW: List[Tuple[str, str, Tuple[str, ...]]] = [
    (
        "Interpenetration — UI copies CLI; kernel remains authority for chat, story, model.",
        "OBSERVED",
        ("expand2", "ui"),
    ),
    (
        "Interpenetration — KAI forbids couple to wit kill-switch under distress.",
        "OBSERVED",
        ("expand2", "kai"),
    ),
    (
        "Interpenetration — scar law in story_fabric couples to unique organs list.",
        "OBSERVED",
        ("expand2", "story"),
    ),
    (
        "Interpenetration — enterprise checklist couples export, crisis, HITL, provenance.",
        "OBSERVED",
        ("expand2", "enterprise"),
    ),
    (
        "Interpenetration — MAX corpus units feed companion literacy offline.",
        "OBSERVED",
        ("expand2", "corpus"),
    ),
    (
        "Interpenetration — Phase map couples cloud wings without CMK surrender.",
        "OBSERVED",
        ("expand2", "cloud"),
    ),
    (
        "Condensed UI — density over decoration; glass retained, chrome compressed.",
        "OBSERVED",
        ("expand2", "ui"),
    ),
    (
        "Condensed UI — tabs: chat, story, model, KAI, MAX, ops — one stage.",
        "OBSERVED",
        ("expand2", "ui"),
    ),
    (
        "Premium — features interpenetrate: export requires local-first; HITL requires agent gates.",
        "OBSERVED",
        ("expand2", "premium"),
    ),
    (
        "Modernization — DM Sans / Syne / Plex Mono; fewer shadows, tighter padding.",
        "OBSERVED",
        ("expand2", "ui"),
    ),
]

# densify coupling lines
_ORGANS = [
    "si",
    "kai",
    "persona",
    "wit",
    "hitl",
    "corpus",
    "story",
    "model",
    "cloud",
    "enterprise",
    "ui",
    "cli",
]
for a in _ORGANS:
    for b in _ORGANS:
        if a >= b:
            continue
        _RAW.append(
            (
                f"Couple {a}↔{b} — changes in one should remain coherent with the other's law.",
                "INFERENCE",
                ("expand2", "couple", a, b),
            )
        )


def seed(limit: int = 0) -> int:
    from levi.brain.corpus import Corpus

    c = Corpus()
    n = 0
    for text, kind, tags in _RAW:
        c.add(text, kind=kind, source="seed_expand2", tags=list(tags))
        n += 1
        if limit and n >= limit:
            break
    return n


def format_index() -> str:
    return f"=== Expansion pack II ===\nunits={len(_RAW)}\nRun: levi brain --seed-expand2\n"
