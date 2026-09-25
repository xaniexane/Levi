"""STRIPS-style planning — operators, goal-stack planner, MACROPs, PLANEX.

Studied from: ai-si-software-internals-20260916-0005/report.md (sec 1.3)
— all three entries MERGED into one module.

The mechanism under study, in three fused parts:

1. **Operator semantics.** Every operator declares preconditions plus
   ADD and DELETE lists; the world obeys the STRIPS assumption —
   anything not stated is false, so an operator's effects fully describe
   the new world.
2. **Goal-stack planner that survives its own side effects.** A
   backward-chaining planner works down a stack of goals; apply-markers
   lazily re-achieve preconditions clobbered by earlier operators, and
   after the stack drains any top-level goal still missing (the classic
   trap) goes back on the stack for another round. Achiever choice
   refuses circular dependencies, so the stack cannot loop forever.
3. **MACROPs.** A found plan is generalized — constants replaced by
   variables preserving equality structure — and cached as a named
   macro-operator reusable in later planning.
4. **PLANEX split.** Planning and execution are separate: an execution
   supervisor walks the plan step by step, verifies each step actually
   achieved its add-list in the world, and replans from the live world
   when a step fails or the world moves.

Original, from-scratch implementation for LEVI. States are sets of
string facts; operators are data. The bundled demo domain is a small
blocks world (``on/ontable/clear/holding/handempty``).

Public surface:
- ``Operator(name, pre, add, delete)`` — grounded or schematic.
- ``Planner(operators)`` — ``plan(state, goals) -> Plan``; raises
  ``NoPlan`` honestly when no operator chain reaches a goal.
- ``Plan`` — ordered steps; ``macrop(name)`` generalizes to a
  ``MacroOp`` with ``instantiate(binding)``.
- ``Planex(planner)`` — ``execute(plan, world, goals, fault=None)``
  returns an execution log; replans on failure.

stdlib-only. No network. Deterministic (operator choice breaks ties by
precondition count, then name).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

ORIGIN = "levi-revival/strips"


class NoPlan(Exception):
    """Raised when the goal stack cannot be satisfied — an honest dead end."""


@dataclass(frozen=True)
class Operator:
    """One operator: preconditions, ADD list, DELETE list. Data, not code."""

    name: str
    pre: frozenset
    add: frozenset
    delete: frozenset

    def __init__(
        self,
        name: str,
        pre: Iterable[str] = (),
        add: Iterable[str] = (),
        delete: Iterable[str] = (),
    ) -> None:
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "pre", frozenset(pre))
        object.__setattr__(self, "add", frozenset(add))
        object.__setattr__(self, "delete", frozenset(delete))

    def applicable(self, state: Set[str]) -> bool:
        return self.pre <= state

    def apply(self, state: Set[str]) -> Set[str]:
        return (state - self.delete) | self.add

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Operator({self.name})"


@dataclass
class Plan:
    """An ordered list of grounded operator steps plus the goal it serves."""

    steps: List[Operator] = field(default_factory=list)
    goals: Tuple[str, ...] = ()

    def __len__(self) -> int:
        return len(self.steps)

    def names(self) -> List[str]:
        return [s.name for s in self.steps]

    def macrop(self, name: str) -> "MacroOp":
        """Generalize this plan's constants to variables — the MACROP step."""
        var_of: Dict[str, str] = {}
        counter = [0]

        def var(const: str) -> str:
            if const not in var_of:
                counter[0] += 1
                var_of[const] = f"?v{counter[0]}"
            return var_of[const]

        def lift(fact: str) -> str:
            # constants are the parenthesized arguments: on(A,B) -> on(?v1,?v2)
            head, _, tail = fact.partition("(")
            if not tail:
                return fact
            args = [a.strip() for a in tail.rstrip(")").split(",")]
            return f"{head}({','.join(var(a) for a in args)})"

        pre: Set[str] = set()
        add: Set[str] = set()
        delete: Set[str] = set()
        for step in self.steps:
            pre |= {lift(p) for p in step.pre}
            add |= {lift(a) for a in step.add}
            delete |= {lift(d) for d in step.delete}
        # net effects only: a macro's delete shouldn't erase its own add
        net_add = add - pre
        net_delete = delete - add
        net_pre = pre - add  # facts the plan needed but did not itself create
        return MacroOp(
            name=name,
            pre=frozenset(net_pre),
            add=frozenset(net_add),
            delete=frozenset(net_delete),
            variables=tuple(sorted(var_of.values())),
            from_plan=tuple(self.names()),
        )


@dataclass(frozen=True)
class MacroOp:
    """A cached, generalized plan — usable as one operator."""

    name: str
    pre: frozenset
    add: frozenset
    delete: frozenset
    variables: Tuple[str, ...] = ()
    from_plan: Tuple[str, ...] = ()

    def instantiate(self, binding: Dict[str, str]) -> Operator:
        def ground(fact: str) -> str:
            for v, c in binding.items():
                fact = fact.replace(v, c)
            return fact

        return Operator(
            f"{self.name}{sorted(binding.items())}",
            pre=[ground(p) for p in self.pre],
            add=[ground(a) for a in self.add],
            delete=[ground(d) for d in self.delete],
        )


class Planner:
    """Backward-chaining goal-stack planner with clobber re-achievement."""

    def __init__(
        self, operators: Sequence[Operator], macros: Optional[Dict[str, MacroOp]] = None
    ) -> None:
        self.operators = list(operators)
        self.macros: Dict[str, MacroOp] = dict(macros or {})

    def achievers(self, goal: str) -> List[Operator]:
        cands = [op for op in self.operators if goal in op.add]
        cands.sort(key=lambda o: (len(o.pre), o.name))
        return cands

    def plan(
        self, state: Iterable[str], goals: Sequence[str], _guard: int = 2000
    ) -> Plan:
        """Plan backward from ``goals``; survive the planner's own side effects.

        Runs in rounds: each round works the goal stack depth-first. An
        ("__apply__", operator) marker re-pushes any of its preconditions
        that are missing when it fires — so a precondition clobbered by
        an earlier operator gets re-achieved lazily, exactly where it is
        needed. After the stack drains, any top-level goal still missing
        (clobbered along the way — the classic trap) goes back on the
        stack for another round.

        Achiever choice refuses circular dependencies: an operator is
        skipped when one of its preconditions is an ancestor goal not
        yet true, which is what kept naive goal-stack planners looping
        forever (``clear(A)`` via ``putdown(A)`` via ``holding(A)`` via
        ``pickup(A)`` via ``clear(A)`` ...).
        """
        world: Set[str] = set(state)
        steps: List[Operator] = []
        pending = list(goals)
        for _round in range(10):
            # stack holds goals or ("__apply__", operator, goal) markers
            stack: List = list(reversed(pending))
            guard = 0
            while stack:
                guard += 1
                if guard > _guard:
                    raise NoPlan(f"planning exhausted; stack left: {stack!r}")
                item = stack.pop()
                if isinstance(item, tuple):  # ("__apply__", operator, goal)
                    _, op, _served = item
                    missing = [p for p in sorted(op.pre) if p not in world]
                    if missing:
                        stack.append(item)
                        stack.extend(reversed(missing))
                        continue
                    world = op.apply(world)
                    steps.append(op)
                    continue
                goal = item
                if goal in world:
                    continue
                op = self._choose_achiever(goal, stack, world)
                stack.append(("__apply__", op, goal))
                stack.extend(reversed(sorted(op.pre)))
            pending = [g for g in goals if g not in world]
            if not pending:
                break
        if pending:
            raise NoPlan(f"could not achieve {pending} after replanning rounds")
        return Plan(steps=steps, goals=tuple(goals))

    def _choose_achiever(self, goal: str, stack: List, world: Set[str]) -> Operator:
        """Pick an achiever that can actually make progress.

        Two guards keep the stack honest:

        * **No circularity.** A candidate is skipped when one of its
          preconditions is a goal already in progress (an ancestor goal,
          the goal itself, or the goal served by a marker still on the
          stack) and not yet true — pursuing it would chase the stack's
          own tail (``ontable(A)`` via ``putdown(A)`` needs
          ``holding(A)``, which is what we were achieving).
        * **Applicable first.** Among the survivors, prefer an operator
          whose preconditions already hold — no new subgoals, no
          pointless detours (like picking up B and putting it straight
          back down just to free the hand).
        """
        cands = self.achievers(goal)
        if not cands:
            raise NoPlan(f"no operator achieves {goal!r}")
        in_progress = {goal}
        in_progress.update(s for s in stack if isinstance(s, str))
        in_progress.update(m[2] for m in stack if isinstance(m, tuple))
        blocked = {g for g in in_progress if g not in world}
        usable = [op for op in cands if not (set(op.pre) & blocked)]
        if not usable:
            raise NoPlan(f"achieving {goal!r} here would be circular")
        for op in usable:
            if op.applicable(world):
                return op
        return usable[0]

    def learn_macro(self, name: str, plan: Plan) -> MacroOp:
        macro = plan.macrop(name)
        self.macros[name] = macro
        return macro


# ----------------------------------------------------------------------
# PLANEX — the execution supervisor, separate from the planner
# ----------------------------------------------------------------------
@dataclass
class ExecEvent:
    step: int
    op: str
    kind: str  # ok | pre-fail | add-fail | replanned | done
    detail: str = ""


class Planex:
    """Supervised execution: verify every step's add-list, replan on failure."""

    def __init__(self, planner: Planner) -> None:
        self.planner = planner

    def execute(
        self,
        plan: Plan,
        world: Iterable[str],
        goals: Sequence[str],
        fault: Optional[Callable[[int, Set[str]], Set[str]]] = None,
    ) -> Tuple[Set[str], List[ExecEvent]]:
        """Walk the plan; ``fault(i, world)`` may perturb the world after
        step ``i`` (simulated trouble). Returns final world + event log."""
        world = set(world)
        events: List[ExecEvent] = []
        steps = list(plan.steps)
        i = 0
        replans = 0
        while i < len(steps):
            op = steps[i]
            if not op.applicable(world):
                events.append(
                    ExecEvent(
                        i, op.name, "pre-fail", "preconditions not met in live world"
                    )
                )
                steps, i, replans = self._replan(world, goals, events, replans, i)
                continue
            world = op.apply(world)
            if fault is not None:
                world = fault(i, world)
            missing = [a for a in op.add if a not in world]
            if missing:
                events.append(
                    ExecEvent(
                        i, op.name, "add-fail", f"add-list not achieved: {missing}"
                    )
                )
                steps, i, replans = self._replan(world, goals, events, replans, i)
                continue
            events.append(ExecEvent(i, op.name, "ok", "add-list verified"))
            i += 1
        events.append(
            ExecEvent(
                len(steps),
                "-",
                "done",
                f"goals {list(goals)} "
                f"{'met' if all(g in world for g in goals) else 'NOT met'}",
            )
        )
        return world, events

    def _replan(
        self,
        world: Set[str],
        goals: Sequence[str],
        events: List[ExecEvent],
        replans: int,
        i: int,
    ):
        replans += 1
        if replans > 5:
            raise NoPlan("too many replans — the world won't cooperate")
        new_plan = self.planner.plan(world, goals)
        events.append(ExecEvent(i, "-", "replanned", f"new plan: {new_plan.names()}"))
        return new_plan.steps, 0, replans


# ----------------------------------------------------------------------
# demo domain: a small blocks world in STRIPS facts
# ----------------------------------------------------------------------
def blocks_operators() -> List[Operator]:
    B = ["A", "B", "C"]
    ops: List[Operator] = []
    for x in B:
        ops.append(
            Operator(
                f"pickup({x})",
                pre={f"ontable({x})", f"clear({x})", "handempty"},
                add={f"holding({x})"},
                delete={f"ontable({x})", "handempty"},
            )
        )
        ops.append(
            Operator(
                f"putdown({x})",
                pre={f"holding({x})"},
                add={f"ontable({x})", "handempty", f"clear({x})"},
                delete={f"holding({x})"},
            )
        )
        for y in B:
            if x == y:
                continue
            ops.append(
                Operator(
                    f"stack({x},{y})",
                    pre={f"holding({x})", f"clear({y})"},
                    add={f"on({x},{y})", "handempty", f"clear({x})"},
                    delete={f"holding({x})", f"clear({y})"},
                )
            )
            ops.append(
                Operator(
                    f"unstack({x},{y})",
                    pre={f"on({x},{y})", f"clear({x})", "handempty"},
                    add={f"holding({x})", f"clear({y})"},
                    delete={f"on({x},{y})", "handempty"},
                )
            )
    return ops


def sussman_start() -> Set[str]:
    """The classic clobbering trap: on(C,A), goals on(A,B) + on(B,C)."""
    return {"on(C,A)", "ontable(A)", "ontable(B)", "clear(B)", "clear(C)", "handempty"}
