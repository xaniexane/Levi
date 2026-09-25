"""Moore School human computers -> ENIAC programmers: role transfer.

Origin: 1940-45, University of Pennsylvania's Moore School — ~100 women
recruited as Army human "computers" solving ballistics equations for firing
tables; six of them (Jean Bartik, Betty Holberton, Kathleen Antonelli,
Marlyn Meltzer, Frances Spence, Ruth Teitelbaum) became ENIAC's first
programmers in 1945. The Ballistic Research Laboratory ran a hybrid
pipeline before the word existed: differential analyzers solved differential
equations mechanically, human teams did the rest. The ahead-of-its-time
move was *role transfer*: the six learned ENIAC from blueprints alone
(barred from the machine room for secrecy) and understood application and
hardware so deeply they could diagnose faults to the individual vacuum
tube — the first hardware/software co-designers. Adele Goldstine's training
program was effectively the first programming manual.

What it is in LEVI: procedure porting with transfer/rewrite classification.
Describe a new substrate as a blueprint (named ops with wiring notes), then
port each operator procedure step-by-step: every step is either transferred
onto a substrate op or explicitly marked for rewrite with a reason.
``finalize()`` refuses to complete until every step is accounted for, and
the porting report tells you exactly which procedures the old crew could
carry over and which need new code.

Honesty label: LOAD-BEARING — step-by-step porting with explicit
transfer/rewrite classification is a concrete, transferable mechanism.

Deny-closed inputs: empty op/procedure/reason names, duplicate ops or
procedures, unknown procedures or ops, out-of-range or non-integer step
indices, mapping an already-accounted step, finalizing with unmapped steps,
finalizing twice, and reading a report before finalization are all rejected
with ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["BlueprintAdoption", "PortingReport"]


def _clean(value: str, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{what} must be a non-empty string")
    return value.strip()


@dataclass
class PortingReport:
    procedure: str
    transferred: dict = field(default_factory=dict)  # step index -> op name
    rewrites: dict = field(default_factory=dict)  # step index -> reason

    @property
    def transfer_ratio(self) -> float:
        # MONEY LAW: porting metric — the share of operator-procedure steps
        # transferred to the new substrate. A float about ENIAC, not funds.
        total = len(self.transferred) + len(self.rewrites)
        return len(self.transferred) / total if total else 0.0

    def summary(self) -> dict:
        return {
            "procedure": self.procedure,
            "steps": len(self.transferred) + len(self.rewrites),
            "transferred": len(self.transferred),
            "rewrites": len(self.rewrites),
            "transfer_ratio": round(self.transfer_ratio, 4),
        }


class BlueprintAdoption:
    """Adopt a new substrate from its blueprints: port every procedure,
    step by step, into transferred ops and honest rewrites."""

    def __init__(self) -> None:
        self._ops: dict[str, str] = {}  # op name -> wiring notes
        self._procedures: dict[str, list[str]] = {}  # name -> steps
        self._mapped: dict[str, dict[int, str]] = {}  # name -> step -> op
        self._rewrites: dict[str, dict[int, str]] = {}  # name -> step -> reason
        self._finalized: dict[str, PortingReport] = {}

    # -- the blueprint -----------------------------------------------------
    def register_op(self, name: str, wiring: str = "") -> str:
        """Describe one substrate operation from its blueprint."""
        name = _clean(name, "op name")
        if name in self._ops:
            raise ValueError(f"duplicate op: {name!r}")
        self._ops[name] = wiring or ""
        return name

    def ops(self) -> list[str]:
        return sorted(self._ops)

    # -- operator procedures -------------------------------------------------
    def define_procedure(self, name: str, steps: list[str]) -> list[str]:
        """Record an operator procedure as an ordered list of steps."""
        name = _clean(name, "procedure name")
        if name in self._procedures:
            raise ValueError(f"duplicate procedure: {name!r}")
        if not isinstance(steps, list) or not steps:
            raise ValueError("steps must be a non-empty list of strings")
        cleaned = [_clean(s, f"step {i}") for i, s in enumerate(steps)]
        self._procedures[name] = cleaned
        self._mapped[name] = {}
        self._rewrites[name] = {}
        return list(cleaned)

    # -- porting ---------------------------------------------------------------
    def map_step(self, procedure: str, index: int, op: str) -> None:
        """Transfer one step onto a substrate op — the step survives the
        move to the new machine."""
        steps = self._require_open(procedure)
        index = self._require_step(procedure, steps, index)
        op = _clean(op, "op name")
        if op not in self._ops:
            raise ValueError(f"unknown op: {op!r}")
        self._mapped[procedure][index] = op

    def mark_rewrite(self, procedure: str, index: int, reason: str) -> None:
        """Admit a step cannot transfer and must be rewritten, with a reason."""
        steps = self._require_open(procedure)
        index = self._require_step(procedure, steps, index)
        reason = _clean(reason, "rewrite reason")
        self._rewrites[procedure][index] = reason

    def finalize(self, procedure: str) -> PortingReport:
        """Complete the port. Refuses until every step is transferred or
        explicitly marked for rewrite — no silent drops."""
        steps = self._require_open(procedure)
        unmapped = [
            i
            for i in range(len(steps))
            if i not in self._mapped[procedure] and i not in self._rewrites[procedure]
        ]
        if unmapped:
            raise ValueError(
                f"procedure {procedure!r} has unmapped steps: {unmapped} — "
                "transfer or mark_rewrite every step before finalizing"
            )
        report = PortingReport(
            procedure=procedure,
            transferred=dict(sorted(self._mapped[procedure].items())),
            rewrites=dict(sorted(self._rewrites[procedure].items())),
        )
        self._finalized[procedure] = report
        return report

    def report(self, procedure: str) -> PortingReport:
        """The porting report: what transferred, what needs rewrite."""
        if procedure not in self._procedures:
            raise ValueError(f"unknown procedure: {procedure!r}")
        report = self._finalized.get(procedure)
        if report is None:
            raise ValueError(
                f"procedure {procedure!r} is not finalized yet — "
                "finalize() before reading the report"
            )
        return report

    # -- internals -------------------------------------------------------------
    def _require_open(self, procedure: str) -> list[str]:
        steps = self._procedures.get(procedure)
        if steps is None:
            raise ValueError(f"unknown procedure: {procedure!r}")
        if procedure in self._finalized:
            raise ValueError(
                f"procedure {procedure!r} is already finalized — "
                "ports are frozen once complete"
            )
        return steps

    def _require_step(self, procedure: str, steps: list[str], index: int) -> int:
        if not isinstance(index, int) or isinstance(index, bool):
            raise ValueError(f"step index must be an integer, got {index!r}")
        if not 0 <= index < len(steps):
            raise ValueError(
                f"step index {index} out of range for procedure "
                f"{procedure!r} ({len(steps)} steps)"
            )
        if index in self._mapped[procedure] or index in self._rewrites[procedure]:
            raise ValueError(f"step {index} of {procedure!r} is already accounted for")
        return index
