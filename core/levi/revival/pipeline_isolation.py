"""Generic staged-pipeline isolation contracts for agent and growth loops.

Studied from: pre-digital-computation-20260916/report.md [Cross-entry pattern 3]
(Staged pipelines with isolation)

The studied shape (kept generic per the care note): the same pattern
recurs — Bletchley stage contracts, the census ETL, the Harvard
reduction line, the Ford Mark 1 predict-observe-correct cycle. Each is
a staged pipeline where isolation is a first-class contract: a stage
declares what it needs and what it produces, it receives a private
scratch space, the shared context is passed by copy so no stage can
mutate its neighbors' data, and every handoff is audited. The pattern
applies to LEVI's growth loop and agent loops; the mechanism itself
stays generic.

LEVI-native re-expression: a **StageContract** declares name, needs,
produces, and an optional tool allow-list; the **IsolatedPipeline**
runner enforces the contract — needs are extracted by copy from the
shared context, each stage gets a private scratch dict, outputs are
validated against the contract, and the context is never mutated
in-place by stages; **check_isolation** audits the run for contract
violations. Predict-observe-correct is included as one three-stage
contract example, built generically from caller-supplied functions.

Operations:

* ``StageContract(name, needs, produces, run, tools=())``
* ``IsolatedPipeline(contracts)`` / ``execute(context)`` -> (final_context, HandoffLog)
* ``check_isolation(log)`` -> list of violation strings (empty when clean)
* ``predict_observe_correct(predict, observe, correct)`` — three-contract example

Honest limits: isolation is copy-based, not process-based — trusted
code only. The tool allow-list is recorded and reported, not
sandbox-enforced.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Tuple


ORIGIN = "levi-revival/pipeline-isolation"

ContractFn = Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]


@dataclass(frozen=True)
class StageContract:
    """A stage's isolation contract: needs, produces, allowed tools, and its function.

    ``run`` receives (inputs, scratch) and returns the produced fields.
    """

    name: str
    needs: Tuple[str, ...]
    produces: Tuple[str, ...]
    run: ContractFn
    tools: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.needs:
            raise ValueError(f"contract {self.name!r}: needs must be non-empty")
        if not self.produces:
            raise ValueError(f"contract {self.name!r}: produces must be non-empty")


@dataclass(frozen=True)
class HandoffRecord:
    """One audited handoff: stage, fields seen, fields produced, tools declared."""

    stage: str
    fields_seen: Tuple[str, ...]
    fields_produced: Tuple[str, ...]
    tools_declared: Tuple[str, ...]


class IsolationError(RuntimeError):
    """Raised when a stage violates its contract."""


class IsolatedPipeline:
    """Runs stage contracts with copy-based isolation and a full audit log."""

    def __init__(self, contracts: List[StageContract]) -> None:
        if not contracts:
            raise ValueError("pipeline needs at least one contract")
        names = [c.name for c in contracts]
        if len(set(names)) != len(names):
            raise ValueError("stage names must be unique")
        self.contracts = contracts

    def execute(
        self, context: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[HandoffRecord]]:
        shared = copy.deepcopy(context)
        log: List[HandoffRecord] = []
        for contract in self.contracts:
            missing = [k for k in contract.needs if k not in shared]
            if missing:
                raise IsolationError(
                    f"stage {contract.name!r} missing required inputs: {missing}"
                )
            # Isolation: deep-copied inputs; a private scratch dict; shared is never
            # handed to the stage directly.
            inputs = copy.deepcopy({k: shared[k] for k in contract.needs})
            scratch: Dict[str, Any] = {}
            produced = contract.run(inputs, scratch)
            if not isinstance(produced, dict):
                raise IsolationError(f"stage {contract.name!r}: run must return a dict")
            missing_out = [k for k in contract.produces if k not in produced]
            if missing_out:
                raise IsolationError(
                    f"stage {contract.name!r} missing declared outputs: {missing_out}"
                )
            for k in contract.produces:
                shared[k] = copy.deepcopy(produced[k])
            log.append(
                HandoffRecord(
                    stage=contract.name,
                    fields_seen=tuple(contract.needs),
                    fields_produced=tuple(contract.produces),
                    tools_declared=tuple(contract.tools),
                )
            )
        return shared, log


def check_isolation(log: List[HandoffRecord]) -> List[str]:
    """Audit a handoff log; returns violation descriptions (empty when clean)."""
    violations: List[str] = []
    seen_produced: Dict[str, str] = {}
    for record in log:
        if not record.fields_seen:
            violations.append(f"{record.stage}: saw no inputs")
        if not record.fields_produced:
            violations.append(f"{record.stage}: produced no outputs")
        for f in record.fields_produced:
            if f in seen_produced:
                violations.append(
                    f"{record.stage}: re-produces {f!r} already produced by {seen_produced[f]!r}"
                )
            seen_produced[f] = record.stage
    return violations


def predict_observe_correct(
    predict: ContractFn,
    observe: ContractFn,
    correct: ContractFn,
) -> List[StageContract]:
    """The predict-observe-correct cycle as three isolated contracts."""
    return [
        StageContract("predict", ("state",), ("prediction",), predict),
        StageContract("observe", ("prediction", "sensor"), ("observation",), observe),
        StageContract("correct", ("prediction", "observation"), ("state",), correct),
    ]
