"""LEVI's viable diagnostic: five functions, one audit channel, recursion.

Studied from: catalog (§19) and forgotten-methods-wave3-20260916-0015/report.md
(§23) — merged (functional description only; no historical claims).

The lesson, reborn as LEVI's own: a living organization needs five
functions, recursively, at every level:

1. **operations** — the units that do the actual work;
2. **coordination** — the anti-oscillation glue between operations
   (schedules, standards, shared protocols);
3. **control** — day-to-day management and resource bargaining;
4. **intelligence** — looking outward and forward (the world, the future);
5. **policy** — identity and direction: what we are for.

Plus an **audit channel** that bypasses the hierarchy entirely — control
checking the real state of operations without asking management's
permission. And the recursion: every operations unit is itself a viable
system, five functions deep, all the way down.

``diagnose(org)`` walks the tree and names what's missing, and where.

Honesty: LOAD-BEARING, with one stated limit. This is a structural
diagnostic, not a performance review — it tells you a function is absent
or unnamed, not whether the people doing it are any good. Presence here
means "someone owns it", nothing more.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

ORIGIN = "levi-revival/viable"

# The five functions, in S1..S5 order.
FUNCTIONS = (
    "operations",  # S1: the units doing the work
    "coordination",  # S2: anti-oscillation between operations
    "control",  # S3: day-to-day management, resource bargaining
    "intelligence",  # S4: outward/forward — environment and future
    "policy",  # S5: identity, purpose, direction
)


@dataclass
class Unit:
    """One viable unit: five named functions, an audit channel, and child
    units (each itself viable — the recursion). A function maps to a short
    note naming who/what owns it; ``None`` means absent."""

    name: str
    functions: Dict[str, Optional[str]] = field(default_factory=dict)
    audit: Optional[str] = None  # the S3* channel: who audits ops directly
    children: List["Unit"] = field(default_factory=list)

    def set(self, function: str, owner: str) -> "Unit":
        if function not in FUNCTIONS:
            raise ValueError(f"viable: unknown function {function!r}")
        self.functions[function] = owner
        return self

    def add(self, child: "Unit") -> "Unit":
        self.children.append(child)
        return self


@dataclass
class Gap:
    path: str  # e.g. "levi-lab/vision-team"
    function: str  # one of FUNCTIONS, or "audit"
    note: str

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return f"{self.path}: missing {self.function} — {self.note}"


def diagnose(unit: Unit, path: str = "") -> List[Gap]:
    """Walk the unit and every child recursively; report every missing
    function and every missing audit channel."""
    here = f"{path}/{unit.name}" if path else unit.name
    gaps: List[Gap] = []

    for fn in FUNCTIONS:
        if not unit.functions.get(fn):
            gaps.append(Gap(here, fn, _ADVICE[fn]))

    if not unit.audit:
        gaps.append(Gap(here, "audit", _ADVICE["audit"]))

    # recursion: operations units must themselves be viable
    for child in unit.children:
        gaps.extend(diagnose(child, here))
    return gaps


_ADVICE = {
    "operations": "nothing does the work — the unit is a meeting with no output",
    "coordination": "operations will oscillate and collide with no shared protocol",
    "control": "no day-to-day grip — resources bargained by rumor",
    "intelligence": "flying blind — nobody watches the world or the future",
    "policy": "no identity — the unit cannot say what it is for",
    "audit": "control trusts reports it never verifies — add a channel that "
    "bypasses the hierarchy",
}


def is_viable(unit: Unit) -> bool:
    """True iff diagnose finds nothing missing at any level."""
    return not diagnose(unit)


def report(unit: Unit) -> str:
    gaps = diagnose(unit)
    if not gaps:
        return f"{unit.name}: viable at every level."
    lines = [f"{unit.name}: {len(gaps)} gap(s) found:"]
    lines += [f"  - {g}" for g in gaps]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Demo — a healthy lab and a lab missing its coordination
# ---------------------------------------------------------------------------


def demo_healthy() -> Unit:
    vision = (
        Unit("vision-team")
        .set("operations", "perception engineers shipping detectors")
        .set("coordination", "weekly interface contract review")
        .set("control", "team lead, sprint bargaining")
        .set("intelligence", "paper watch + benchmark tracking")
        .set("policy", "eyes the organism can trust")
    )
    vision.audit = "lead spot-checks detector outputs directly"
    lab = (
        Unit("levi-lab")
        .set("operations", "research teams")
        .set("coordination", "shared roadmap + API standards")
        .set("control", "lab director, compute budget bargaining")
        .set("intelligence", "field scans, future-tech radar")
        .set("policy", "local-first synthetic intelligence")
        .add(vision)
    )
    lab.audit = "director sits in on team demos unannounced"
    return lab


def demo_broken() -> Unit:
    lab = demo_healthy()
    lab.functions["coordination"] = None  # the glue dissolved
    lab.audit = None  # and nobody checks anymore
    return lab


def demo() -> str:
    return report(demo_healthy()) + "\n\n" + report(demo_broken())


if __name__ == "__main__":  # pragma: no cover - demo
    print(demo())
