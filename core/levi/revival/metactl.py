"""MetaCtl — the system reasons about which reasoning to use.

Studied from: revival-50-more-20260916-0009/report-part1.md (sec 25).

The mechanism under study: explicit meta-level control. Object-level
rules do the work, grouped by kind; meta-level axioms *name* those
object-level expressions — rule groups, individual rules, strategies —
and manipulate them: enable this group for this problem, disable that
one, prefer this strategy over that. The system doesn't just reason; it
reasons about *how* to reason, per problem, out in the open where you
can read the decision.

Original, from-scratch implementation for LEVI. Problems are plain
dicts; object rules are condition → action pairs in named groups;
meta-rules are condition → control-effect pairs, and control effects
are data (``("enable", group)``, ``("disable", group)``,
``("disable_rule", (group, name))``, ``("strategy", name)``).
Strategies are pluggable firing disciplines. The trace records every
meta decision with the meta-rule that made it — control is inspectable,
never silent.

Public surface:
- ``MetaController`` — ``object_rule(group, name, condition, action)``,
  ``meta_rule(name, condition, *effects)``, ``strategy(name, runner)``,
  ``solve(problem, goal=None, max_steps=50)`` → ``(problem, trace)``.
- ``Trace`` — ordered human-readable lines; ``meta_decisions()``.

stdlib-only. No network. Deterministic (rules fire in registration
order unless a strategy reorders them).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

ORIGIN = "levi-revival/metactl"

# control-effect shapes
Enable = Tuple[str, str]  # ("enable", group)
Disable = Tuple[str, str]  # ("disable", group)
DisableRule = Tuple[str, Tuple[str, str]]  # ("disable_rule", (group, name))
UseStrategy = Tuple[str, str]  # ("strategy", name)
Effect = Tuple[str, Any]


@dataclass
class ObjectRule:
    group: str
    name: str
    condition: Callable[[Dict[str, Any]], bool]
    action: Callable[[Dict[str, Any]], Optional[str]]  # returns a note


@dataclass
class MetaRule:
    name: str
    condition: Callable[[Dict[str, Any], Dict[str, Any]], bool]
    effects: Tuple[Effect, ...]  # condition sees (problem, meta_state)

    def __init__(
        self,
        name: str,
        condition: Callable[[Dict[str, Any], Dict[str, Any]], bool],
        effects: Tuple[Effect, ...],
    ) -> None:
        self.name = name
        self.condition = condition
        self.effects = effects


@dataclass
class Trace:
    lines: List[str] = field(default_factory=list)

    def add(self, line: str) -> None:
        self.lines.append(line)

    def meta_decisions(self) -> List[str]:
        return [ln for ln in self.lines if ln.startswith("META")]

    def __str__(self) -> str:
        return "\n".join(self.lines)


class MetaController:
    """Two floors: the meta floor decides, the object floor works."""

    def __init__(self) -> None:
        self.object_rules: List[ObjectRule] = []
        self.meta_rules: List[MetaRule] = []
        self.strategies: Dict[str, Callable] = {
            "first_match": self._strat_first_match,
            "all_match": self._strat_all_match,
        }
        self.default_strategy = "first_match"

    # ------------------------------------------------------------------
    # declaration
    # ------------------------------------------------------------------
    def object_rule(
        self,
        group: str,
        name: str,
        condition: Callable[[Dict[str, Any]], bool],
        action: Callable[[Dict[str, Any]], Optional[str]],
    ) -> ObjectRule:
        rule = ObjectRule(group, name, condition, action)
        self.object_rules.append(rule)
        return rule

    def meta_rule(
        self,
        name: str,
        condition: Callable[[Dict[str, Any], Dict[str, Any]], bool],
        *effects: Effect,
    ) -> MetaRule:
        rule = MetaRule(name, condition, tuple(effects))
        self.meta_rules.append(rule)
        return rule

    def strategy(self, name: str, runner: Callable) -> None:
        """A strategy runner: (rules, problem, goal, trace) -> steps taken."""
        self.strategies[name] = runner

    # ------------------------------------------------------------------
    # meta floor — reasons about the object floor
    # ------------------------------------------------------------------
    def _meta_phase(self, problem: Dict[str, Any], trace: Trace) -> Dict[str, Any]:
        meta: Dict[str, Any] = {
            "enabled_groups": {r.group for r in self.object_rules},
            "disabled_rules": set(),  # {(group, name)}
            "strategy": self.default_strategy,
        }
        for mrule in self.meta_rules:
            if mrule.condition(problem, meta):
                for eff in mrule.effects:
                    kind, arg = eff
                    if kind == "enable":
                        meta["enabled_groups"].add(arg)
                        trace.add(f"META {mrule.name}: enabled group '{arg}'")
                    elif kind == "disable":
                        meta["enabled_groups"].discard(arg)
                        trace.add(f"META {mrule.name}: disabled group '{arg}'")
                    elif kind == "disable_rule":
                        meta["disabled_rules"].add(tuple(arg))
                        trace.add(
                            f"META {mrule.name}: disabled rule "
                            f"'{arg[1]}' in group '{arg[0]}'"
                        )
                    elif kind == "strategy":
                        meta["strategy"] = arg
                        trace.add(f"META {mrule.name}: strategy -> '{arg}'")
                    else:
                        trace.add(f"META {mrule.name}: unknown effect {eff!r}")
        trace.add(
            f"META settled: groups={sorted(meta['enabled_groups'])} "
            f"strategy={meta['strategy']}"
        )
        return meta

    def _active_rules(self, meta: Dict[str, Any]) -> List[ObjectRule]:
        return [
            r
            for r in self.object_rules
            if r.group in meta["enabled_groups"]
            and (r.group, r.name) not in meta["disabled_rules"]
        ]

    # ------------------------------------------------------------------
    # object floor — runs under the chosen strategy
    # ------------------------------------------------------------------
    def _strat_first_match(self, rules, problem, goal, trace) -> int:
        steps = 0
        while steps < 50:
            if goal is not None and goal(problem):
                break
            for rule in rules:
                if rule.condition(problem):
                    note = rule.action(problem) or ""
                    trace.add(f"OBJ [{rule.group}] {rule.name} {note}".rstrip())
                    steps += 1
                    break
            else:
                break
        return steps

    def _strat_all_match(self, rules, problem, goal, trace) -> int:
        steps = 0
        while steps < 50:
            if goal is not None and goal(problem):
                break
            fired = False
            for rule in rules:
                if rule.condition(problem):
                    note = rule.action(problem) or ""
                    trace.add(f"OBJ [{rule.group}] {rule.name} {note}".rstrip())
                    steps += 1
                    fired = True
            if not fired:
                break
        return steps

    # ------------------------------------------------------------------
    # the solve: meta first, then object, with a mid-run meta re-check
    # ------------------------------------------------------------------
    def solve(
        self,
        problem: Dict[str, Any],
        goal: Optional[Callable[[Dict[str, Any]], bool]] = None,
        max_steps: int = 50,
        recheck_every: int = 0,
    ) -> Tuple[Dict[str, Any], Trace]:
        """Meta decides the setup; the object floor works; optionally the
        meta floor re-checks mid-run (``recheck_every`` > 0)."""
        problem = dict(problem)
        trace = Trace()
        trace.add(f"problem: {problem}")
        meta = self._meta_phase(problem, trace)
        runner = self.strategies[meta["strategy"]]
        rules = self._active_rules(meta)
        steps = 0
        while steps < max_steps:
            if goal is not None and goal(problem):
                break
            before = steps
            steps += runner(rules, problem, goal, trace)
            if steps == before:
                break  # quiescent
            if recheck_every and steps % recheck_every == 0:
                trace.add("META re-check mid-run")
                meta = self._meta_phase(problem, trace)
                rules = self._active_rules(meta)
                runner = self.strategies[meta["strategy"]]
        done = goal(problem) if goal else True
        trace.add(f"done: {done} after {steps} object steps; problem={problem}")
        return problem, trace
