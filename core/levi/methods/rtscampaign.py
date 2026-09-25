"""Single-player RTS campaigns: scenario scripting, tech trees, offline AI.

Origin: StarCraft, Age of Empires, Command and Conquer (1990s–2000s) —
authored narrative campaigns with scripted scenarios, asymmetric factions,
and offline skirmish versus AI. The campaign was the product; multiplayer
was the bonus.

What it is in LEVI: CampaignEngine — missions as ordered scripts of
triggers, each trigger a named (condition, event) pair evaluated against
an open fact table; ``advance`` merges new facts and fires each newly-met
trigger's event exactly once, in script order. A TechTree gates node
unlocks behind prerequisite nodes, so progression carries across missions.
AIOpponent is a deterministic, seeded policy for offline play: the same
seed and the same tick always produce the same decision.

Honesty label: USEFUL PATTERN — trigger/event scripting and prerequisite
gating are concrete mechanics; the AI is a scripted build-order policy,
not a real opponent.

Deny-closed inputs: duplicate trigger names, triggers added to a mission
that already started, non-callable conditions, unknown missions or tech
nodes, starting missions out of order, unlocking a tech whose
prerequisites aren't met or that's already unlocked, and advancing a
mission that isn't running are all rejected with ValueError.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable

__all__ = ["Trigger", "Mission", "CampaignEngine", "TechTree", "AIOpponent"]

Condition = Callable[[dict], bool]


def _require_name(value: object, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{what} must be a non-empty string")
    return value.strip()


@dataclass
class Trigger:
    """A scenario-script line: when ``condition`` holds, ``event`` fires."""

    name: str
    condition: Condition
    event: str
    once: bool = True
    fired: bool = False


@dataclass
class Mission:
    """One scripted scenario: an ordered trigger script over a fact table."""

    name: str
    triggers: list[Trigger] = field(default_factory=list)
    started: bool = False
    finished: bool = False
    facts: dict = field(default_factory=dict)


class CampaignEngine:
    """Trigger-based storytelling: missions run in order, events fire once."""

    def __init__(self) -> None:
        self._missions: dict[str, Mission] = {}
        self._order: list[str] = []
        self._log: list[tuple[str, str, str]] = []  # (mission, trigger, event)

    # -- authoring ---------------------------------------------------------
    def add_mission(self, name: str) -> Mission:
        name = _require_name(name, "mission name")
        if name in self._missions:
            raise ValueError(f"duplicate mission: {name!r}")
        mission = Mission(name=name)
        self._missions[name] = mission
        self._order.append(name)
        return mission

    def add_trigger(
        self,
        mission_name: str,
        trigger_name: str,
        condition: Condition,
        event: str,
        once: bool = True,
    ) -> Trigger:
        mission = self._mission(mission_name)
        if mission.started:
            raise ValueError(
                f"mission {mission_name!r} already started — its script is locked"
            )
        trigger_name = _require_name(trigger_name, "trigger name")
        event = _require_name(event, "event")
        if not callable(condition):
            raise ValueError("trigger condition must be callable")
        if any(t.name == trigger_name for t in mission.triggers):
            raise ValueError(
                f"duplicate trigger {trigger_name!r} in mission {mission_name!r}"
            )
        trigger = Trigger(
            name=trigger_name, condition=condition, event=event, once=once
        )
        mission.triggers.append(trigger)
        return trigger

    def _mission(self, name: str) -> Mission:
        mission = self._missions.get(name)
        if mission is None:
            raise ValueError(f"unknown mission: {name!r}; known={list(self._missions)}")
        return mission

    # -- running -----------------------------------------------------------
    def start_mission(self, name: str) -> Mission:
        mission = self._mission(name)
        if mission.started:
            raise ValueError(f"mission {name!r} already started")
        idx = self._order.index(name)
        for earlier in self._order[:idx]:
            if not self._missions[earlier].finished:
                raise ValueError(
                    f"mission {name!r} is out of order — finish {earlier!r} first"
                )
        mission.started = True
        return mission

    def advance(self, mission_name: str, facts: dict) -> list[str]:
        """Merge new facts, evaluate triggers in script order, return events fired."""
        mission = self._mission(mission_name)
        if not mission.started:
            raise ValueError(f"mission {mission_name!r} has not started")
        if mission.finished:
            raise ValueError(f"mission {mission_name!r} is already finished")
        if not isinstance(facts, dict):
            raise ValueError("facts must be a dict")
        mission.facts.update(facts)
        fired: list[str] = []
        for trigger in mission.triggers:
            if trigger.once and trigger.fired:
                continue
            try:
                met = bool(trigger.condition(dict(mission.facts)))
            except Exception as exc:
                raise ValueError(
                    f"trigger {trigger.name!r} condition failed: {exc}"
                ) from exc
            if met:
                trigger.fired = True
                self._log.append((mission.name, trigger.name, trigger.event))
                fired.append(trigger.event)
        return fired

    def finish_mission(self, name: str) -> Mission:
        mission = self._mission(name)
        if not mission.started:
            raise ValueError(f"mission {name!r} has not started")
        if mission.finished:
            raise ValueError(f"mission {name!r} is already finished")
        mission.finished = True
        return mission

    def event_log(self) -> list[tuple[str, str, str]]:
        return list(self._log)

    def pending_triggers(self, mission_name: str) -> list[str]:
        mission = self._mission(mission_name)
        return [t.name for t in mission.triggers if not t.fired]


class TechTree:
    """Progression across missions: nodes unlock only behind prerequisites."""

    def __init__(self) -> None:
        self._prereqs: dict[str, tuple[str, ...]] = {}
        self._unlocked: list[str] = []

    def add_node(self, node_id: str, prerequisites: tuple[str, ...] = ()) -> str:
        node_id = _require_name(node_id, "tech node id")
        if node_id in self._prereqs:
            raise ValueError(f"duplicate tech node: {node_id!r}")
        prereqs = tuple(_require_name(p, "prerequisite") for p in prerequisites)
        for pre in prereqs:
            if pre not in self._prereqs:
                raise ValueError(f"tech node {node_id!r} requires unknown node {pre!r}")
        self._prereqs[node_id] = prereqs
        return node_id

    def unlock(self, node_id: str) -> str:
        if node_id not in self._prereqs:
            raise ValueError(
                f"unknown tech node: {node_id!r}; known={list(self._prereqs)}"
            )
        if node_id in self._unlocked:
            raise ValueError(f"tech node {node_id!r} is already unlocked")
        missing = [p for p in self._prereqs[node_id] if p not in self._unlocked]
        if missing:
            raise ValueError(f"tech node {node_id!r} is gated behind {missing}")
        self._unlocked.append(node_id)
        return node_id

    def unlocked(self) -> list[str]:
        return list(self._unlocked)

    def available(self) -> list[str]:
        """Nodes whose prerequisites are met but that aren't unlocked yet."""
        return [
            node
            for node, prereqs in self._prereqs.items()
            if node not in self._unlocked and all(p in self._unlocked for p in prereqs)
        ]


class AIOpponent:
    """A deterministic, seeded offline opponent: scripted build order plus
    fixed reactive rules. Same seed, same tick, same facts -> same decision.
    """

    _LATE_GAME = ("scout", "expand", "harass", "fortify")

    def __init__(self, seed: int, build_order: tuple[str, ...] | list[str]):
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ValueError(f"seed must be an integer, got {seed!r}")
        if not build_order or not all(
            isinstance(step, str) and step.strip() for step in build_order
        ):
            raise ValueError("build_order must be a non-empty list of strings")
        self.seed = seed
        self.build_order = tuple(s.strip() for s in build_order)
        rng = random.Random(seed)
        late = list(self._LATE_GAME)
        rng.shuffle(late)
        self._late_game = tuple(late)

    def decide(self, tick: int, facts: dict | None = None) -> str:
        """The opponent's action for this tick. Pure function of inputs."""
        if isinstance(tick, bool) or not isinstance(tick, int) or tick < 0:
            raise ValueError(f"tick must be a non-negative integer, got {tick!r}")
        facts = facts or {}
        if facts.get("under_attack"):
            return "defend_base"
        if facts.get("enemy_weak"):
            return "attack"
        if tick < len(self.build_order):
            return f"build:{self.build_order[tick]}"
        return self._late_game[(tick - len(self.build_order)) % len(self._late_game)]

    def reset(self) -> None:
        """Re-seed the late-game rotation (identical decisions afterwards)."""
        rng = random.Random(self.seed)
        late = list(self._LATE_GAME)
        rng.shuffle(late)
        self._late_game = tuple(late)
