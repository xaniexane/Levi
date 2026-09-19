"""Recursive delegation with tight protocols — one master, many monitors.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #28).

The mechanism under study: a single master teaches a cadre of
**monitors**, each of whom drills a small group in turn. Every node both
learns from above and teaches below — and teaching is the learning
accelerator. The protocols are tight: a monitor may not teach what it
has not itself passed (own-drill first), drills are standardized
prompt/response pairs, and pass/fail propagates upward — the master's
report names every weak branch.

This is an original, from-scratch implementation for LEVI. A lesson is
a set of drill items (prompt + expected answer). The master drills the
monitors; each monitor drills its group. A monitor's group drill is
refused until the monitor passes its own drill. After the cascade, the
master's report shows per-group pass rates, flags branches below the
mastery threshold, and orders re-drill where the cascade frayed.

Public surface:
- ``Lesson``: prompt/answer drill items.
- ``MonitorialSchool``: ``add_monitor``, ``add_pupil``,
  ``drill_monitor``, ``drill_group``, ``cascade_report``.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

ORIGIN = "levi-revival/monitorial"


class MonitorialError(Exception):
    """A protocol violation: unknown node, unpassed monitor, bad drill."""


@dataclass
class DrillItem:
    prompt: str
    answer: str


@dataclass
class Lesson:
    name: str
    items: List[DrillItem] = field(default_factory=list)

    def add(self, prompt: str, answer: str) -> None:
        if not prompt.strip() or not answer.strip():
            raise MonitorialError("drill items need a prompt and an answer")
        self.items.append(DrillItem(prompt.strip(), answer.strip()))

    def check(self, response: str, item_index: int) -> bool:
        """Fuzzy match: the response passes if it contains the answer's core words."""
        answer = self.items[item_index].answer.lower()
        response = response.lower()
        core = [tok for tok in answer.split() if len(tok) > 2]
        if not core:
            return response.strip() == answer.strip()
        return all(tok in response for tok in core)


@dataclass
class Node:
    name: str
    role: str  # "master" | "monitor" | "pupil"
    lesson: str = ""
    own_drill_passed: bool = False
    score: float = 0.0


class MonitorialSchool:
    """One master -> monitors -> groups, drills cascading down, failures up."""

    PASS_THRESHOLD = 0.6  # fraction of items to pass a drill
    MASTERY_THRESHOLD = 0.8  # group pass-rate below this flags a re-drill

    def __init__(self, master_name: str) -> None:
        self.nodes: Dict[str, Node] = {master_name: Node(master_name, "master")}
        self.master = master_name
        self.monitors: Dict[str, List[str]] = {}  # monitor -> pupil names
        self.lessons: Dict[str, Lesson] = {}
        self.drill_log: List[Dict[str, object]] = []

    # -- structure ----------------------------------------------------
    def add_monitor(self, name: str) -> None:
        if name in self.nodes:
            raise MonitorialError(f"node '{name}' already exists")
        self.nodes[name] = Node(name, "monitor")
        self.monitors[name] = []

    def add_pupil(self, monitor: str, name: str) -> None:
        if monitor not in self.monitors:
            raise MonitorialError(f"'{monitor}' is not a monitor")
        if name in self.nodes:
            raise MonitorialError(f"node '{name}' already exists")
        self.nodes[name] = Node(name, "pupil")
        self.monitors[monitor].append(name)

    def set_lesson(self, lesson: Lesson, target: str) -> None:
        if target not in self.nodes:
            raise MonitorialError(f"unknown node '{target}'")
        if not lesson.items:
            raise MonitorialError("a lesson needs drill items")
        self.lessons[target] = lesson
        self.nodes[target].lesson = lesson.name

    # -- drills --------------------------------------------------------
    def drill(self, name: str, responses: List[str]) -> Tuple[bool, float]:
        """Run the standardized drill on one node against its lesson."""
        if name not in self.nodes:
            raise MonitorialError(f"unknown node '{name}'")
        lesson = self.lessons.get(name)
        if lesson is None:
            raise MonitorialError(f"no lesson set for '{name}'")
        if len(responses) != len(lesson.items):
            raise MonitorialError(
                f"drill expects {len(lesson.items)} responses, got {len(responses)}"
            )
        hits = sum(1 for i, r in enumerate(responses) if lesson.check(r, i))
        score = hits / len(lesson.items)
        passed = score >= self.PASS_THRESHOLD
        node = self.nodes[name]
        node.score = round(score, 3)
        node.own_drill_passed = passed
        self.drill_log.append(
            {
                "node": name,
                "role": node.role,
                "lesson": lesson.name,
                "score": node.score,
                "passed": passed,
            }
        )
        return passed, node.score

    def drill_group(
        self, monitor: str, pupil_responses: Dict[str, List[str]]
    ) -> Dict[str, Tuple[bool, float]]:
        """A monitor drills its group. Protocol: the monitor drills itself FIRST.

        Refused if the monitor has not passed its own drill — you cannot
        teach what you have not passed.
        """
        if monitor not in self.monitors:
            raise MonitorialError(f"'{monitor}' is not a monitor")
        if not self.nodes[monitor].own_drill_passed:
            raise MonitorialError(
                f"protocol violation: monitor '{monitor}' may not teach "
                "before passing its own drill"
            )
        results: Dict[str, Tuple[bool, float]] = {}
        for pupil in self.monitors[monitor]:
            responses = pupil_responses.get(pupil, [])
            results[pupil] = self.drill(pupil, responses)
        return results

    # -- propagation ----------------------------------------------------
    def cascade_report(self) -> Dict[str, object]:
        """The master's report: pass/fail propagated upward, weak branches named."""
        branches = []
        for monitor, pupils in self.monitors.items():
            monitor_node = self.nodes[monitor]
            tested = [
                self.nodes[p]
                for p in pupils
                if any(e["node"] == p for e in self.drill_log)
            ]
            pass_count = sum(1 for n in tested if n.own_drill_passed)
            rate = pass_count / len(tested) if tested else 0.0
            branches.append(
                {
                    "monitor": monitor,
                    "monitor_passed": monitor_node.own_drill_passed,
                    "monitor_score": monitor_node.score,
                    "pupils_tested": len(tested),
                    "pupils_passed": pass_count,
                    "pass_rate": round(rate, 3),
                    "re_drill": rate < self.MASTERY_THRESHOLD,
                }
            )
        return {
            "master": self.master,
            "monitors": len(self.monitors),
            "pupils": sum(len(p) for p in self.monitors.values()),
            "branches": branches,
            "weak_branches": [b["monitor"] for b in branches if b["re_drill"]],
        }
