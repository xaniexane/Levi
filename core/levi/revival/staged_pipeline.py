"""A staged pipeline with hard isolation between stages.

Studied from: pre-digital-computation-20260916/report.md [Beat C #4]
(Bletchley Park pipeline, 1939-45)

The studied shape: intercept -> cribs -> Bombe menus -> checking ->
translation, where each stage sees only what it needs. Isolation is
the mechanism: no stage receives the full message, only its declared
inputs; outputs flow forward through handoff envelopes; an audit trail
records who saw what.

LEVI-native re-expression: a **Stage** declares its input fields and
output fields; the **Pipeline** builds each stage a redacted view
containing only its declared inputs — a stage physically cannot read
other keys because it never receives them; the **audit trail** logs
(stage, inputs_seen, outputs_produced) per handoff. Attempting to
declare outputs not produced, or reading undeclared fields, raises
immediately.

Operations:

* ``Stage(name, needs, produces, handler)`` — handler(view) -> dict of produced fields
* ``Pipeline(stages)`` / ``run(initial)`` — execute stages in order with redacted views
* ``audit_trail()`` — list of handoff records

Honest limits: isolation is enforced by redaction of the input view,
not by process boundaries — a hostile handler cannot be contained by
this. Handlers are trusted code; the mechanism models need-to-know
data flow, not sandboxing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List


ORIGIN = "levi-revival/staged-pipeline"

Handler = Callable[[Dict[str, Any]], Dict[str, Any]]


@dataclass(frozen=True)
class Stage:
    """One pipeline stage with a hard need-to-know contract."""

    name: str
    needs: tuple
    produces: tuple
    handler: Handler

    def __post_init__(self) -> None:
        if not self.needs:
            raise ValueError(
                f"stage {self.name!r}: must declare at least one input field"
            )
        if not self.produces:
            raise ValueError(
                f"stage {self.name!r}: must declare at least one output field"
            )


@dataclass(frozen=True)
class Handoff:
    """One audit record: what a stage was allowed to see and what it produced."""

    stage: str
    inputs_seen: tuple
    outputs_produced: tuple


class Pipeline:
    """Executes stages in order; each stage receives only its declared inputs."""

    def __init__(self, stages: List[Stage]) -> None:
        if not stages:
            raise ValueError("pipeline needs at least one stage")
        self.stages = stages
        self._audit: List[Handoff] = []

    def run(self, initial: Dict[str, Any]) -> Dict[str, Any]:
        self._audit = []
        satchel: Dict[str, Any] = dict(initial)
        for stage in self.stages:
            missing = [k for k in stage.needs if k not in satchel]
            if missing:
                raise KeyError(
                    f"stage {stage.name!r} missing required inputs: {missing}"
                )
            # Hard isolation: the handler only ever receives this redacted view.
            view = {k: satchel[k] for k in stage.needs}
            produced = stage.handler(view)
            if not isinstance(produced, dict):
                raise TypeError(f"stage {stage.name!r}: handler must return a dict")
            missing_out = [k for k in stage.produces if k not in produced]
            if missing_out:
                raise KeyError(
                    f"stage {stage.name!r} failed to produce declared outputs: {missing_out}"
                )
            for k in stage.produces:
                satchel[k] = produced[k]
            self._audit.append(
                Handoff(
                    stage=stage.name,
                    inputs_seen=tuple(stage.needs),
                    outputs_produced=tuple(stage.produces),
                )
            )
        return satchel

    def audit_trail(self) -> List[Handoff]:
        return list(self._audit)

    def visible_fields(self, stage_name: str) -> List[str]:
        """Which fields a named stage was permitted to see, from the audit trail."""
        for handoff in self._audit:
            if handoff.stage == stage_name:
                return list(handoff.inputs_seen)
        raise KeyError(f"no audited stage named {stage_name!r}")
