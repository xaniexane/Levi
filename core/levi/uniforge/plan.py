"""BuildPlan data model: targets, steps, ordering, hermetic checks.

A :class:`BuildPlan` is pure data — no execution lives here. The native
SI core (:mod:`levi.uniforge.si`) assembles and runs plans; this module
only describes them. stdlib only.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Step:
    """One hermetic build step.

    ``tool`` is the executable that must exist on PATH; ``argv`` is the
    command (tool included) to run when live. ``artifacts`` lists paths
    relative to the step's workdir that must exist after execution for
    the verify stage to pass. ``consequential`` marks steps that act on
    the world beyond a build directory — these always pass a permission
    gate even inside a live run.
    """

    id: str
    label: str
    target: str
    tool: str
    argv: List[str]
    workdir: str = "."
    consequential: bool = False
    depends_on: List[str] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "target": self.target,
            "tool": self.tool,
            "argv": self.argv,
            "workdir": self.workdir,
            "consequential": self.consequential,
            "depends_on": list(self.depends_on),
            "artifacts": list(self.artifacts),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Step":
        return cls(
            id=d["id"],
            label=d["label"],
            target=d["target"],
            tool=d["tool"],
            argv=list(d["argv"]),
            workdir=d.get("workdir", "."),
            consequential=d.get("consequential", False),
            depends_on=list(d.get("depends_on", [])),
            artifacts=list(d.get("artifacts", [])),
        )


@dataclass
class BuildPlan:
    """One build plan across heterogeneous targets."""

    name: str
    targets: List[str]
    steps: List[Step] = field(default_factory=list)
    created_ts: str = ""

    def __post_init__(self) -> None:
        if not self.created_ts:
            self.created_ts = _utcnow()

    def step_ids(self) -> List[str]:
        return [s.id for s in self.steps]

    def ordered_steps(self) -> List[Step]:
        """Topological order honoring ``depends_on``.

        Raises ``ValueError`` on unknown dependencies or cycles — a plan
        that cannot be ordered is a plan that must not run.
        """
        by_id = {s.id: s for s in self.steps}
        for s in self.steps:
            for dep in s.depends_on:
                if dep not in by_id:
                    raise ValueError("step %r depends on unknown step %r" % (s.id, dep))
        ordered: List[Step] = []
        visiting: List[str] = []
        done: set = set()

        def visit(sid: str) -> None:
            if sid in done:
                return
            if sid in visiting:
                raise ValueError("dependency cycle: %s" % " -> ".join(visiting + [sid]))
            visiting.append(sid)
            for dep in by_id[sid].depends_on:
                visit(dep)
            visiting.pop()
            done.add(sid)
            ordered.append(by_id[sid])

        for s in self.steps:
            visit(s.id)
        return ordered

    def required_tools(self) -> List[str]:
        """Sorted unique tool names across all steps."""
        return sorted({s.tool for s in self.steps})

    def tool_status(self) -> Dict[str, Any]:
        """Hermetic tool check: which required tools exist on PATH.

        No network, no side effects — ``shutil.which`` only.
        """
        present, missing = [], []
        for tool in self.required_tools():
            (present if shutil.which(tool) else missing).append(tool)
        return {"present": present, "missing": missing}

    def hermetic_checks(self) -> Dict[str, Any]:
        """Plan-level checks that run with zero side effects."""
        tools = self.tool_status()
        try:
            self.ordered_steps()
            order_ok, order_error = True, ""
        except ValueError as exc:
            order_ok, order_error = False, str(exc)
        return {
            "targets_known": bool(self.targets),
            "steps_orderable": order_ok,
            "order_error": order_error,
            "tools_present": tools["present"],
            "tools_missing": tools["missing"],
            "no_network_used": True,
        }

    def preview(self) -> str:
        """Human-readable plan preview (the Preview stage)."""
        lines = [
            "BuildPlan: %s" % self.name,
            "targets: %s" % ", ".join(self.targets),
            "created: %s" % self.created_ts,
            "",
        ]
        for i, step in enumerate(self.ordered_steps(), 1):
            lines.append("  %d. [%s] %s" % (i, step.target, step.label))
            lines.append("     tool: %s" % step.tool)
            lines.append("     run:  %s" % " ".join(step.argv))
            if step.depends_on:
                lines.append("     after: %s" % ", ".join(step.depends_on))
            if step.consequential:
                lines.append("     consequential: yes (permission-gated)")
            if step.artifacts:
                lines.append("     artifacts: %s" % ", ".join(step.artifacts))
        tools = self.tool_status()
        lines.append("")
        lines.append("tools present: %s" % (", ".join(tools["present"]) or "(none)"))
        lines.append("tools missing: %s" % (", ".join(tools["missing"]) or "(none)"))
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "targets": list(self.targets),
            "steps": [s.to_dict() for s in self.steps],
            "created_ts": self.created_ts,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BuildPlan":
        return cls(
            name=d["name"],
            targets=list(d["targets"]),
            steps=[Step.from_dict(s) for s in d.get("steps", [])],
            created_ts=d.get("created_ts", ""),
        )
