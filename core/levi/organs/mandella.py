"""Mandella — stake selection under domain pressure (kernel organ).

The one stakes/scenario-generation implementation in this tree; pairs with
organs/echo.py. A prior lineage's graph/mandella.py was correctly rejected
at merge time to avoid a competing implementation — do not reintroduce one;
extend this module instead."""
from __future__ import annotations

from typing import Dict, List
import hashlib


DOMAINS = {
    "crisis": "A critical path is failing and information is incomplete.",
    "resource": "Budget, time, or energy is scarcer than the plan assumed.",
    "trust": "A counterpart’s incentives are opaque; cooperation is valuable but risky.",
    "identity": "Two self-descriptions conflict; only one can drive the next commit.",
    "build": "A factory stage is blocked; several stacks could work.",
    "write": "The story or premise can branch into several modes.",
    "security": "A consequential action is proposed; blast radius is unclear.",
    "product": "Users ask for more surface; retention may prefer one loop.",
}

OPTIONS: Dict[str, List[tuple]] = {
    "crisis": [
        ("Act fast with incomplete data", "high", "Smallest containment now"),
        ("Gather one more signal", "medium", "Time-box the wait"),
        ("Contain and observe", "low", "Define exit criteria"),
    ],
    "resource": [
        ("Spend the reserve", "high", "Track burn vs milestone"),
        ("Cut scope", "low", "Thinner vertical ship"),
        ("Borrow from another organ", "medium", "Composite risk ceiling"),
    ],
    "security": [
        ("HITL gate hard", "low", "No silent approval"),
        ("Preview only", "medium", "Reversible sandbox"),
        ("Proceed under policy", "high", "Receipt + rollback plan"),
    ],
}


def run_mandella(domain: str = "build", seed: str = "") -> Dict:
    d = (domain or "build").lower()
    if d not in DOMAINS:
        d = "build"
    premise = DOMAINS[d]
    opts = OPTIONS.get(d) or OPTIONS["resource"]
    h = int(hashlib.sha256((seed + d).encode()).hexdigest()[:6], 16)
    # rotate emphasis
    ordered = opts[h % len(opts) :] + opts[: h % len(opts)]
    return {
        "organ": "mandella",
        "domain": d,
        "premise": premise,
        "options": [
            {"label": o[0], "risk": o[1], "note": o[2]} for o in ordered
        ],
        "recommended": ordered[0][0],
        "seed": seed,
    }


def format_mandella(result: Dict) -> str:
    lines = [
        f"=== Mandella [{result['domain']}] ===",
        f"Premise: {result['premise']}",
        "",
        "Stakes:",
    ]
    for i, o in enumerate(result["options"], 1):
        mark = "→" if i == 1 else "·"
        lines.append(f"  {mark} {o['label']}  risk={o['risk']}  ({o['note']})")
    lines.append("")
    lines.append(f"Recommended stake: {result['recommended']}")
    lines.append("Commit is yours — Mandella surfaces pressure, does not force.")
    return "\n".join(lines)
