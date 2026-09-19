"""LEVI's teachback checker: entailment meshes and the teachback test.

Studied from: retired-software-revival-research-20260916-0004/report.md (§20)
(functional description only; no historical claims).

The lesson, reborn as LEVI's own: knowledge is a mesh, not a list.
Topics are linked by *derivation edges* — "fractions" derives from
"division" and "sharing", so you don't understand fractions until you can
derive them from those roots. And *understanding* is proven by teaching:
to claim a topic, the learner must teach it back — produce a small
derivation of the topic from its foundations. This module checks that
teachback against the mesh and reports the gaps: unsupported leaps,
missing foundations, unknown topics, circular reasoning.

Honesty: LOAD-BEARING, with one stated limit. A teachback here is a
structured derivation (claims + "derives from" links), not natural
language — LEVI checks the *shape* of the reasoning against the mesh, it
does not grade prose. A well-shaped derivation can still be nonsense in
its details; shape is necessary, not sufficient.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set

ORIGIN = "levi-revival/teachback"


# ---------------------------------------------------------------------------
# The mesh — topics linked by derivation edges
# ---------------------------------------------------------------------------


@dataclass
class Topic:
    name: str
    note: str = ""


@dataclass
class Derivation:
    """Topic X is derived from premises P1..Pn: to understand X you must be
    able to get there from the Pi."""

    topic: str
    premises: List[str]
    note: str = ""


class Mesh:
    """An entailment mesh: topics plus the derivation edges between them."""

    def __init__(self) -> None:
        self.topics: Dict[str, Topic] = {}
        self.derivations: List[Derivation] = []

    def topic(self, name: str, note: str = "") -> "Mesh":
        self.topics[name] = Topic(name, note)
        return self

    def derives(self, topic: str, *premises: str, note: str = "") -> "Mesh":
        """Declare: `topic` is understood via derivation from `premises`."""
        self.derivations.append(Derivation(topic, list(premises), note))
        return self

    def foundations(self, topic: str) -> Set[str]:
        """All topics transitively required to understand `topic`."""
        found: Set[str] = set()
        stack = [topic]
        while stack:
            cur = stack.pop()
            for d in self.derivations:
                if d.topic == cur:
                    for p in d.premises:
                        if p not in found:
                            found.add(p)
                            stack.append(p)
        found.discard(topic)
        return found

    def edge_exists(self, topic: str, premises: Set[str]) -> bool:
        """Is there a declared derivation of `topic` from (a superset of)
        these premises?"""
        for d in self.derivations:
            if d.topic == topic and set(d.premises) <= premises:
                return True
        return False

    def has_derivations(self, topic: str) -> bool:
        """Does the mesh declare any derivation *of* this topic? Root
        topics (no derivations) are assertable without premises."""
        return any(d.topic == topic for d in self.derivations)


# ---------------------------------------------------------------------------
# Teachbacks — the learner teaches the topic back as a derivation
# ---------------------------------------------------------------------------


@dataclass
class Step:
    """One teachback step: `claim` derived from `premises`."""

    claim: str
    premises: List[str] = field(default_factory=list)


@dataclass
class Teachback:
    learner: str
    topic: str
    steps: List[Step] = field(default_factory=list)

    def claims(self) -> Set[str]:
        return {s.claim for s in self.steps}


@dataclass
class Gap:
    kind: str  # unknown-topic | unsupported-leap | missing-foundation | circular
    detail: str

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return f"[{self.kind}] {self.detail}"


@dataclass
class Report:
    topic: str
    learner: str
    understands: bool
    gaps: List[Gap] = field(default_factory=list)
    covered: Set[str] = field(default_factory=set)

    def summary(self) -> str:
        if self.understands:
            return f"{self.learner} understands {self.topic}: teachback complete."
        lines = [f"{self.learner} does not yet understand {self.topic}:"]
        lines += [f"  - {g}" for g in self.gaps]
        return "\n".join(lines)


def check(mesh: Mesh, tb: Teachback) -> Report:
    """Check a teachback against the mesh. Understands iff the topic is
    claimed, every required foundation is taught, and every step's
    derivation is licensed by a mesh edge."""
    gaps: List[Gap] = []
    claims = tb.claims()

    # 1. every claimed topic and premise must exist in the mesh
    for step in tb.steps:
        for name in [step.claim, *step.premises]:
            if name not in mesh.topics:
                gaps.append(
                    Gap(
                        "unknown-topic",
                        f"{tb.learner} mentions {name!r}, not in the mesh",
                    )
                )

    # 2. every step's derivation must be licensed by a mesh edge
    #    (root topics with no derivations are assertable outright)
    for step in tb.steps:
        if (
            step.claim in mesh.topics
            and mesh.has_derivations(step.claim)
            and not mesh.edge_exists(step.claim, set(step.premises))
        ):
            gaps.append(
                Gap(
                    "unsupported-leap",
                    f"{step.claim!r} from {step.premises} is not a licensed derivation",
                )
            )

    # 3. foundations of the topic must themselves be taught back
    for req in sorted(mesh.foundations(tb.topic)):
        if req not in claims:
            gaps.append(
                Gap(
                    "missing-foundation",
                    f"{req!r} is required for {tb.topic!r} but was never taught",
                )
            )

    # 4. the topic itself must be claimed
    if tb.topic not in claims:
        gaps.append(
            Gap(
                "missing-foundation",
                f"the topic {tb.topic!r} itself was never taught back",
            )
        )

    # 5. circularity: a claim that (transitively) derives from itself
    for step in tb.steps:
        if step.claim in mesh.foundations(step.claim):
            gaps.append(
                Gap("circular", f"{step.claim!r} derives from itself through the mesh")
            )
            break

    covered = claims & (mesh.foundations(tb.topic) | {tb.topic})
    return Report(
        topic=tb.topic,
        learner=tb.learner,
        understands=not gaps,
        gaps=gaps,
        covered=covered,
    )


# ---------------------------------------------------------------------------
# Demo — fractions taught back from division and sharing
# ---------------------------------------------------------------------------


def demo_mesh() -> Mesh:
    return (
        Mesh()
        .topic("sharing", "splitting things fairly")
        .topic("division", "how many times one number fits in another")
        .topic("fractions", "parts of a whole")
        .topic("ratios", "comparing two quantities")
        .derives("division", "sharing")
        .derives("fractions", "division", "sharing")
        .derives("ratios", "fractions", "division")
    )


def demo() -> Report:
    mesh = demo_mesh()
    tb = Teachback(
        learner="levi-learner",
        topic="fractions",
        steps=[
            Step("sharing"),
            Step("division", ["sharing"]),
            Step("fractions", ["division", "sharing"]),
        ],
    )
    return check(mesh, tb)


if __name__ == "__main__":  # pragma: no cover - demo
    print(demo().summary())
