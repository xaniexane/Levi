"""Goal-oriented planning over LEVI's own tool surface.

Inspired by Goal-Oriented Action Planning (Jeff Orkin, 2003 — built for
F.E.A.R., Monolith; Jeff Orkin's thesis work, with STRIPS (Stanford,
1971) as the ancestor). The ahead-of-its-time mechanism: instead of a
finite state machine hand-authored for every situation, the agent keeps a
world state, a set of *actions* (each with preconditions, effects, and a
cost), and *plans backward from a goal* with A* — then replans at runtime
when the world changes. Games-aside, it is the honest substrate for an
assistant that must assemble multi-step tool sequences toward a goal
rather than follow a script.

Remix delta: game-AI GOAP reimagined as the planning substrate for LEVI's
*own assistant loop* — not an FPS AI clone. Actions are LEVI tool
operations declared with preconditions/effects/costs over world-state
dicts; the Planner replans at runtime when the world moves and reports
*what changed*; ``NoPlan`` is honest data (the agent says the goal is
unreachable from these actions instead of hallucinating a plan).
Deterministic (ties break by action name). No steering, no anim graphs;
this module plans over symbolic facts only — a planner, not a
simulator.

This is an original, from-scratch reimplementation for LEVI — no GOAP
game code is used. ``plan(world, goal, actions)`` runs A* over
dictionaries of facts; action costs steer the planner toward cheaper
sequences; a plan is a list of grounded action names. ``Planner`` adds
runtime replanning: feed it state updates, and when an action's
preconditions break it replans and reports what changed — the honest
"the world moved, so the plan moved" behavior. A ``Replanner`` executor
wraps all of it: execute an action, observe the new world, replan on
failure.

Preconditions/effects may be plain dicts or callables taking the world
dict (for state-dependent checks); effects may be dicts or callables
returning an updated world. Everything is deterministic: ties in the A*
frontier break by action name, so the same inputs always yield the same
plan.

Honesty: USEFUL PATTERN — goal-state planning as an architectural
pattern for LEVI's own tool-use loops. What is NOT revived: real-time
FPS steering/anim graphs; this module plans over *symbolic* facts only.
It is a planner, not a simulator — preconditions describe, they don't
guarantee, the real world.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Union


State = dict[str, Any]
PreCond = Union[State, Callable[[State], bool]]
Effect = Union[State, Callable[[State], State]]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class PlanError(Exception):
    """Base class for planning failures."""


class NoPlan(PlanError):
    """No action sequence reaches the goal from the current world state."""


class UnknownAction(PlanError):
    """The named action is not registered."""


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------


@dataclass
class Action:
    """One GOAP action: when ``pre(world)`` holds, apply ``effects`` to get
    a new world. ``cost`` steers A* toward cheaper sequences."""

    name: str
    preconditions: PreCond = field(default_factory=dict)
    effects: Effect = field(default_factory=dict)
    cost: float = 1.0

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("action name must be non-empty")
        if self.cost < 0:
            raise ValueError("action cost must be non-negative")

    def applicable(self, world: State) -> bool:
        pre = self.preconditions
        if callable(pre):
            return bool(pre(dict(world)))
        return all(world.get(k) == v for k, v in pre.items())

    def apply(self, world: State) -> State:
        eff = self.effects
        if callable(eff):
            new = eff(dict(world))
            if not isinstance(new, dict):
                raise PlanError(f"effect callable of {self.name!r} must return a dict")
            return new
        new = dict(world)
        new.update(eff)
        return new


def goal_satisfied(world: State, goal: State) -> bool:
    """Every goal fact holds in the world (goal is a partial state)."""
    return all(world.get(k) == v for k, v in goal.items())


# ---------------------------------------------------------------------------
# A* planner
# ---------------------------------------------------------------------------


def _state_key(world: State) -> tuple:
    def freeze(v: Any) -> Any:
        if isinstance(v, dict):
            return tuple(sorted((k, freeze(x)) for k, x in v.items()))
        if isinstance(v, (list, tuple)):
            return tuple(freeze(x) for x in v)
        if isinstance(v, (set, frozenset)):
            return tuple(sorted(freeze(x) for x in v))
        return v

    return tuple(sorted((k, freeze(v)) for k, v in world.items()))


def plan(
    world: State, goal: State, actions: list[Action], max_expansions: int = 10000
) -> list[str]:
    """A* from ``world`` to a state satisfying ``goal``.

    Returns the action-name sequence (cheapest first on ties, ties broken
    by action name — deterministic). Raises :class:`NoPlan` when
    unreachable, which is honest data: the goal cannot be assembled from
    these actions, so the agent must say so, not hallucinate a plan.
    """
    if not isinstance(world, dict) or not isinstance(goal, dict):
        raise ValueError("world and goal must be dicts")
    if goal_satisfied(world, goal):
        return []
    actions = sorted(actions, key=lambda a: a.name)  # deterministic order
    # frontier entries: (f, insertion-counter, g, state, plan-so-far)
    start_key = _state_key(world)
    frontier: list[tuple] = [(0.0, 0, 0.0, world, [])]
    counter = 1
    best_g: dict[tuple, float] = {start_key: 0.0}
    expansions = 0
    while frontier:
        _, _, g, state, seq = heapq.heappop(frontier)
        if goal_satisfied(state, goal):
            return seq
        expansions += 1
        if expansions > max_expansions:
            break
        for action in actions:
            if not action.applicable(state):
                continue
            nxt = action.apply(state)
            ng = g + action.cost
            key = _state_key(nxt)
            if key in best_g and best_g[key] <= ng:
                continue
            best_g[key] = ng
            # Admissible heuristic: 0 (Dijkstra) — always safe, may be slow.
            heapq.heappush(frontier, (ng, counter, ng, nxt, seq + [action.name]))
            counter += 1
    raise NoPlan(
        f"no plan from current world state to goal {sorted(goal)} "
        f"using {[a.name for a in actions]}"
    )


# ---------------------------------------------------------------------------
# Planner — planning + runtime replanning
# ---------------------------------------------------------------------------


class Planner:
    """Holds a goal and action set; plans, then replans when the world
    moves. ``on_replan`` callbacks receive ``(old_plan, new_plan, reason)``."""

    def __init__(
        self,
        actions: list[Action],
        goal: State,
        on_replan: Optional[Callable[[list[str], list[str], str], None]] = None,
    ):
        self.actions: dict[str, Action] = {}
        for a in actions:
            if a.name in self.actions:
                raise ValueError(f"duplicate action name {a.name!r}")
            self.actions[a.name] = a
        self.goal = dict(goal)
        self.on_replan = on_replan
        self.world: State = {}
        self.current_plan: list[str] = []
        self.replans = 0

    def set_world(self, world: State) -> None:
        self.world = dict(world)

    def update_world(self, updates: State) -> None:
        self.world.update(updates)

    def make_plan(self) -> list[str]:
        self.current_plan = plan(self.world, self.goal, list(self.actions.values()))
        return list(self.current_plan)

    def next_action(self) -> Optional[str]:
        """Peek at the next action, replanning first if the head of the
        plan no longer applies to the current world."""
        if not self.current_plan:
            self.make_plan()
        if not self.current_plan:
            return None
        head = self.actions[self.current_plan[0]]
        if not head.applicable(self.world):
            old = list(self.current_plan)
            self.replans += 1
            self.make_plan()
            if self.on_replan:
                self.on_replan(
                    old,
                    list(self.current_plan),
                    f"precondition of {head.name!r} no longer holds",
                )
        return self.current_plan[0] if self.current_plan else None

    def mark_done(
        self, action_name: str, observed_world: Optional[State] = None
    ) -> None:
        """Record that ``action_name`` executed; optionally fold in the
        observed post-state (what the world *actually* looks like now —
        effects describe, they don't guarantee)."""
        if action_name in self.current_plan:
            self.current_plan.remove(action_name)
        if observed_world is not None:
            self.world = dict(observed_world)

    def add_action(self, action: Action) -> None:
        if action.name in self.actions:
            raise ValueError(f"duplicate action name {action.name!r}")
        self.actions[action.name] = action


__all__ = [
    "PlanError",
    "NoPlan",
    "UnknownAction",
    "Action",
    "goal_satisfied",
    "plan",
    "Planner",
]
