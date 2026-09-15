"""
Tech-giant-class capabilities with a LEVI-unique spin.

Inspired by scale/polish expectations users have of major platforms —
implemented as local-first, HITL, exportable, non-personhood SI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class GiantSpin:
    giant_echo: str
    levi_spin: str
    surface: str


SPINS: List[GiantSpin] = [
    GiantSpin(
        "Universal search",
        "Local corpus + transcript search; no ad graph",
        "levi brain --query",
    ),
    GiantSpin(
        "Assistant ecosystem",
        "230 personas + 14 LEVI registers under HITL",
        "levi chat / voice",
    ),
    GiantSpin(
        "Cloud sync", "Optional encrypted wing; CMK never server-owned", "levi cloud"
    ),
    GiantSpin(
        "App store / plugins",
        "Skills/plugins with approval path",
        "levi plugins / agent",
    ),
    GiantSpin(
        "Analytics dashboard",
        "Scorecard + stress + enterprise checklist",
        "levi scorecard / stress",
    ),
    GiantSpin(
        "Onboarding magic",
        "init + morning + 5-minute win; no dark urgency",
        "levi init / morning",
    ),
    GiantSpin(
        "Creative suite",
        "L.W.P. literary engine + quality rater",
        "levi story / stress",
    ),
    GiantSpin(
        "Identity platform", "Local profile + exportable life-pack", "levi export"
    ),
    GiantSpin(
        "Safety center",
        "Crisis floor + wit kill-switch + Care register",
        "offline companion / voice care",
    ),
    GiantSpin(
        "Design system", "Condensed glass console · modern density", "levi serve-ui"
    ),
    GiantSpin(
        "Knowledge graph",
        "MAX/×10 densified literacy units offline",
        "levi brain --seed-max/--seed-x10",
    ),
    GiantSpin(
        "Team workspace", "Phase C seats design; HITL multi-party", "enterprise map"
    ),
    GiantSpin(
        "CI / quality gates",
        "pytest + stress harness + story quality scores",
        "levi stress",
    ),
    GiantSpin(
        "Personalization", "Nervous system + monotropism routing", "persona matrix"
    ),
    GiantSpin(
        "Developer platform", "CLI-first parity; UI defers to kernel", "levi --help"
    ),
]


def format_spins() -> str:
    lines = [
        "══ Tech-giant class × LEVI spin ══",
        f"items={len(SPINS)}",
        "Polish and power without surveillance-default economics.",
        "",
    ]
    for i, s in enumerate(SPINS, 1):
        lines.append(f"{i:2}. {s.giant_echo}")
        lines.append(f"    → {s.levi_spin}")
        lines.append(f"    {s.surface}")
        lines.append("")
    return "\n".join(lines)
