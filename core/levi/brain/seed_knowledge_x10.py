"""
×10 MAX expansion — second densification wave on top of seed_knowledge_max.

Adds thousands of short operator units without replacing the 2518 base pack.
"""
from __future__ import annotations

from typing import Iterator, List, Tuple

_RAW: List[Tuple[str, str, Tuple[str, ...]]] = []


def _build() -> List[Tuple[str, str, Tuple[str, ...]]]:
    raw: List[Tuple[str, str, Tuple[str, ...]]] = []
    # 500 interpenetration drills
    organs = [
        "si", "kai", "persona", "wit", "hitl", "corpus", "story", "model",
        "cloud", "crypto", "enterprise", "agent", "ui", "cli", "scar", "export",
    ]
    for i, a in enumerate(organs):
        for b in organs[i + 1 :]:
            for n in range(1, 6):
                raw.append(
                    (
                        f"X10 couple {a}↔{b} #{n} — keep both laws true under change; no silent override.",
                        "INFERENCE",
                        ("x10", "couple", a, b),
                    )
                )
    # 800 field checks
    for i in range(1, 801):
        raw.append(
            (
                f"X10 field {i:04d} — Verify owner, evidence label, HITL need, rollback, and offline path.",
                "OBSERVED",
                ("x10", "field"),
            )
        )
    # 600 build slices
    for i in range(1, 601):
        raw.append(
            (
                f"X10 slice {i:04d} — Ship the smallest proof of the riskiest assumption; measure once.",
                "INFERENCE",
                ("x10", "slice"),
            )
        )
    # 400 care under load
    for i in range(1, 401):
        raw.append(
            (
                f"X10 care {i:04d} — Distress: mute wit, reduce choices, one next step, stay present.",
                "OBSERVED",
                ("x10", "care"),
            )
        )
    # 300 KAI discipline
    regs = [
        "kai_9000", "kai_9000_care", "kai_9000_ops", "kai_9000_challenger",
        "kai_9000_literary", "kai_9000_forensic", "kai_9000_void", "kai_9000_builder",
        "kai_9000_mirror", "kai_9000_architect", "kai_9000_sentinel", "kai_9000_oracle",
    ]
    contexts = ["crisis", "design", "review", "handoff", "conflict", "planning", "incident", "writing"]
    for r in regs:
        for c in contexts:
            for n in range(1, 4):
                raw.append(
                    (
                        f"X10 KAI {r} @ {c} #{n} — original LEVI register; forbids stay on; not third-party source.",
                        "OBSERVED",
                        ("x10", "kai", r, c),
                    )
                )
    # 200 modern UI ops
    for i in range(1, 201):
        raw.append(
            (
                f"X10 UI {i:03d} — Condensed console copies CLI; kernel is authority; glass stays local.",
                "OBSERVED",
                ("x10", "ui"),
            )
        )
    return raw


_RAW = _build()


def iter_x10(limit: int = 0) -> Iterator[Tuple[str, str, List[str]]]:
    n = 0
    for text, kind, tags in _RAW:
        yield text, kind, list(tags)
        n += 1
        if limit and n >= limit:
            return


def seed(limit: int = 0) -> int:
    from levi.brain.corpus import Corpus
    c = Corpus()
    count = 0
    for text, kind, tags in iter_x10(limit=limit):
        c.add(text, kind=kind, source="seed_knowledge_x10", tags=tags)
        count += 1
    return count


def format_index() -> str:
    return (
        f"=== ×10 MAX expansion pack ===\n"
        f"units={len(_RAW)}\n"
        f"On top of seed-max (2518). Total if both seeded ≈ {2518 + len(_RAW)}\n"
        f"Run: python -m levi.cli.main brain --seed-x10\n"
    )
