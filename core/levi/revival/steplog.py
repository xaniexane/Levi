"""steplog — typed agent step log and the sense→think→act loop.

Studied from: ai-si-software-internals-20260916-0005/report.md (§2.5).

The canonical agent scaffold, reduced to its load-bearing parts: memory
is a **typed step log**, not a bag of strings. Each iteration serializes
the log to messages, asks the policy what to do next, parses the action,
executes it through a tool registry, and logs the observation. The
types matter — a ``PlanningStep`` is addressable as a plan (it can be
revised, persisted outside the context window, re-read later), where a
plain string would just be more context to forget.

The "model" is an **injected callable** — never a real provider. The
loop doesn't care whether the policy is a stub, a script, a test
double, or (elsewhere, wired by the caller) a real synthetic-intelligence
model. That seam is the whole point: everything about the loop is
testable without any model at all.

Step types: ``SystemPromptStep``, ``TaskStep``, ``ActionStep``,
``PlanningStep``, ``ObservationStep``. ``StepLog.write_memory_to_messages``
is the serialization seam (mirrors the published ``write_memory_to_messages``
idea); ``Agent.run`` is the loop with step callbacks.

This is an original, from-scratch implementation for LEVI. Not
artificial. Synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union

ORIGIN = "levi-revival/steplog"


# ---------------------------------------------------------------------------
# Typed steps
# ---------------------------------------------------------------------------


@dataclass
class SystemPromptStep:
    content: str
    role: str = "system"


@dataclass
class TaskStep:
    content: str
    role: str = "user"


@dataclass
class ActionStep:
    tool: str
    args: Dict[str, Any] = field(default_factory=dict)
    thought: str = ""


@dataclass
class PlanningStep:
    plan: str
    facts: List[str] = field(default_factory=list)


@dataclass
class ObservationStep:
    tool: str
    result: Any
    error: Optional[str] = None


Step = Union[SystemPromptStep, TaskStep, ActionStep, PlanningStep, ObservationStep]


@dataclass
class StopStep:
    """Policy signal: the task is complete; carry the final answer."""

    answer: str


PolicyOutput = Union[ActionStep, PlanningStep, StopStep]


# ---------------------------------------------------------------------------
# The log
# ---------------------------------------------------------------------------


class StepLog:
    """The agent's memory: an append-only typed step log."""

    def __init__(self) -> None:
        self.steps: List[Step] = []

    def append(self, step: Step) -> None:
        self.steps.append(step)

    def of_type(self, cls: type) -> List[Step]:
        return [s for s in self.steps if isinstance(s, cls)]

    @property
    def plan(self) -> Optional[PlanningStep]:
        """The latest plan, if any — addressable, revisable, persistable."""
        plans = self.of_type(PlanningStep)
        return plans[-1] if plans else None  # type: ignore[return-value]

    def write_memory_to_messages(self) -> List[Dict[str, Any]]:
        """Serialize the typed log to chat messages for the policy."""
        messages: List[Dict[str, Any]] = []
        for step in self.steps:
            if isinstance(step, SystemPromptStep):
                messages.append({"role": "system", "content": step.content})
            elif isinstance(step, TaskStep):
                messages.append({"role": "user", "content": step.content})
            elif isinstance(step, PlanningStep):
                messages.append(
                    {"role": "assistant", "content": f"[PLAN]\n{step.plan}"}
                )
            elif isinstance(step, ActionStep):
                thought = f"Thought: {step.thought}\n" if step.thought else ""
                messages.append(
                    {
                        "role": "assistant",
                        "content": f"{thought}Action: {step.tool}({step.args})",
                    }
                )
            elif isinstance(step, ObservationStep):
                if step.error:
                    messages.append(
                        {
                            "role": "user",
                            "content": f"Observation error from {step.tool}: {step.error}",
                        }
                    )
                else:
                    messages.append(
                        {
                            "role": "user",
                            "content": f"Observation from {step.tool}: {step.result}",
                        }
                    )
        return messages


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------


class UnknownTool(Exception):
    pass


class ToolRegistry:
    """Name -> callable. The loop's only way to touch the world."""

    def __init__(self) -> None:
        self.tools: Dict[str, Callable[..., Any]] = {}

    def register(self, name: str, fn: Callable[..., Any]) -> None:
        self.tools[name] = fn

    def execute(self, step: ActionStep) -> ObservationStep:
        fn = self.tools.get(step.tool)
        if fn is None:
            return ObservationStep(
                tool=step.tool, result=None, error=f"unknown tool: {step.tool}"
            )
        try:
            return ObservationStep(tool=step.tool, result=fn(**step.args))
        except Exception as exc:  # noqa: BLE001 — surfaced as observation
            return ObservationStep(tool=step.tool, result=None, error=str(exc))


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------


class Agent:
    """Sense→think→act over a typed step log.

    ``policy``: callable(messages) -> ActionStep | PlanningStep | StopStep.
    Injected — never a real provider inside this module.
    ``on_step``: callbacks run after every logged step (logging, budgets).
    """

    def __init__(
        self,
        policy: Callable[[List[Dict[str, Any]]], PolicyOutput],
        tools: Optional[ToolRegistry] = None,
        max_steps: int = 25,
    ) -> None:
        self.policy = policy
        self.tools = tools or ToolRegistry()
        self.max_steps = max_steps
        self.log = StepLog()
        self.on_step: List[Callable[[Step], None]] = []

    def _record(self, step: Step) -> None:
        self.log.append(step)
        for cb in self.on_step:
            cb(step)

    def run(self, task: str, system_prompt: str = "") -> str:
        """Run the loop; return the policy's final answer."""
        if system_prompt:
            self._record(SystemPromptStep(content=system_prompt))
        self._record(TaskStep(content=task))
        for _ in range(self.max_steps):
            messages = self.log.write_memory_to_messages()
            decision = self.policy(messages)
            if isinstance(decision, StopStep):
                return decision.answer
            if isinstance(decision, PlanningStep):
                # Plan-and-execute: the plan lands in memory as a typed step.
                self._record(decision)
                continue
            if isinstance(decision, ActionStep):
                self._record(decision)
                self._record(self.tools.execute(decision))
                continue
            raise TypeError(f"policy returned unsupported type: {type(decision)}")
        return "(max steps reached without a stop decision)"


def scripted_policy(
    script: List[PolicyOutput],
) -> Callable[[List[Dict[str, Any]]], PolicyOutput]:
    """Build a deterministic stub policy from a script (for tests/demos)."""
    queue = list(script)

    def policy(_messages: List[Dict[str, Any]]) -> PolicyOutput:
        if not queue:
            return StopStep(answer="(script exhausted)")
        return queue.pop(0)

    return policy
