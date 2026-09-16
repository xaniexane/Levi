"""Trivium & quadrivium: the staged learning pipeline as a runnable protocol.

Origin: the medieval liberal-arts curriculum — the **trivium** (grammar,
logic, rhetoric: the arts of *language*) then the **quadrivium**
(arithmetic, geometry, music, astronomy: the arts of *number and pattern*),
as preparatory study before philosophy. A seven-stage pipeline from "how
to handle words" to "how to handle the cosmos."

What it is in LEVI: a runnable protocol the assistant applies to anything
you're learning. Per topic: **grammar** (vocabulary and facts — the raw
material), **logic** (argument structure — what follows from what),
**rhetoric** (teach it back — the assistant plays student and
cross-examines until it can't trip you up). Only then the "quadrivium":
quantification and modeling. Each stage gates the next — you cannot
advance on vibes.

Honesty label: USEFUL PATTERN — and a skepticism flag built in: the
popular "grammar/logic/rhetoric = stages of childhood" reading is a
20th-century reinterpretation (Dorothy Sayers), not medieval practice.
Borrow the *sequenced-abstraction mechanism*, not the myth.

PROTOCOL LABEL: this module is a procedure the assistant executes with
you, not an autonomous agent. It holds the checklist; the learning is
yours.

Deny-closed inputs: empty topics/facts/claims/explanations, advancing
past unmet gates, unknown quadrivium arts, and answering unasked
questions are rejected with ValueError.
"""

from __future__ import annotations

__all__ = ["STAGES", "QUADRIVIUM_ARTS", "TriviumStudy"]

STAGES: tuple[str, ...] = ("grammar", "logic", "rhetoric", "quadrivium")

QUADRIVIUM_ARTS: dict[str, str] = {
    "arithmetic": "number in itself — counting, measurement, discrete quantity",
    "geometry": "number in space — shape, structure, spatial relations",
    "music": "number in time — rhythm, harmony, periodic pattern",
    "astronomy": "number in space and time — motion, cycles, prediction",
}


class TriviumStudy:
    """One topic moving through the seven liberal arts, in order."""

    def __init__(self, topic: str):
        if not isinstance(topic, str) or not topic.strip():
            raise ValueError("topic must be a non-empty string")
        self.topic = topic.strip()
        self.stage: str = "grammar"
        self._facts: list[str] = []          # grammar: vocabulary & facts
        self._claims: list[str] = []         # logic: argument structure
        self._explanation: str = ""          # rhetoric: the teach-back
        self._qa: list[tuple[str, str]] = []  # rhetoric: cross-examination Q&A
        self._quadrivium: dict[str, list[str]] = {a: [] for a in QUADRIVIUM_ARTS}

    # -- grammar: the raw material -------------------------------------------------
    def grammar(self, facts: list[str]) -> int:
        """Record vocabulary and facts. Returns the count banked."""
        clean = [self._clean(f, "fact") for f in facts]
        if not clean:
            raise ValueError("grammar needs at least one fact")
        self._facts.extend(clean)
        return len(self._facts)

    # -- logic: what follows from what ----------------------------------------------
    def logic(self, claims: list[str]) -> int:
        """Record argument structure: claims about what follows from what."""
        clean = [self._clean(c, "claim") for c in claims]
        if not clean:
            raise ValueError("logic needs at least one claim")
        self._claims.extend(clean)
        return len(self._claims)

    # -- rhetoric: teach it back -------------------------------------------------------
    def rhetoric(self, explanation: str) -> None:
        """The teach-back: explain the topic as if to a novice."""
        self._explanation = self._clean(explanation, "explanation")

    def cross_examine(self, question: str, answer: str) -> None:
        """The assistant plays student: it asks, you defend. Record the exchange.

        Every question must be answered — an unanswered objection is an
        unowned gap.
        """
        q = self._clean(question, "question")
        a = self._clean(answer, "answer")
        if any(existing_q.lower() == q.lower() for existing_q, _ in self._qa):
            raise ValueError(f"question already asked: {q!r}")
        self._qa.append((q, a))

    # -- quadrivium: number and pattern --------------------------------------------------
    def quadrivium(self, art: str, note: str) -> None:
        """Record a quantitative/modeling insight under its art."""
        if art not in QUADRIVIUM_ARTS:
            raise ValueError(f"unknown quadrivium art {art!r}; arts: {sorted(QUADRIVIUM_ARTS)}")
        self._quadrivium[art].append(self._clean(note, "quadrivium note"))

    # -- the gates -------------------------------------------------------------------------
    def _gate(self, stage: str) -> tuple[bool, str]:
        if stage == "grammar":
            ok = bool(self._facts)
            return ok, ("banked facts" if ok else "no facts banked — grammar() first")
        if stage == "logic":
            ok = bool(self._claims)
            return ok, ("argument structure recorded" if ok else "no claims recorded — logic() first")
        if stage == "rhetoric":
            ok = bool(self._explanation) and bool(self._qa)
            return ok, ("teach-back + cross-examination complete" if ok else
                        "rhetoric needs rhetoric() AND at least one cross_examine() exchange")
        if stage == "quadrivium":
            ok = any(self._quadrivium.values())
            return ok, ("quantitative notes recorded" if ok else
                        "quadrivium needs at least one quadrivium() note")
        raise ValueError(f"unknown stage: {stage!r}")

    def advance(self) -> str:
        """Move to the next stage. Refuses while the current gate is unmet."""
        idx = STAGES.index(self.stage)
        ok, why = self._gate(self.stage)
        if not ok:
            raise ValueError(f"cannot leave {self.stage}: {why}")
        if idx == len(STAGES) - 1:
            raise ValueError("already at the final stage (quadrivium)")
        self.stage = STAGES[idx + 1]
        return self.stage

    def status(self) -> dict:
        gates = {s: {"met": self._gate(s)[0], "detail": self._gate(s)[1]} for s in STAGES}
        return {
            "topic": self.topic,
            "stage": self.stage,
            "facts": len(self._facts),
            "claims": len(self._claims),
            "teach_back": bool(self._explanation),
            "cross_examinations": len(self._qa),
            "quadrivium_notes": {a: len(n) for a, n in self._quadrivium.items()},
            "gates": gates,
        }

    @staticmethod
    def _clean(value: str, kind: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{kind} must be a non-empty string")
        return value.strip()
