"""afford — smart terrain: objects advertise, agents follow the gradient.

Studied from: revival-50-more-20260916-0009/report-part2.md (Section 36).

Load-bearing idea: objects broadcast *affordance signals* for agent
needs; agents follow the gradient to the best object. New objects work
with ZERO agent foreknowledge — agents read only advertised affordances,
never object identities or types.

LEVI's take: ``Terrain`` holds objects and agents on a 2-D field.
``TerrainObject`` publishes a need->strength affordance map; ``Agent``
publishes a need->intensity map. Each ``step()``, every agent
``scan()``s the field (affordance vectors only — no peeking at what
the object *is*), scores candidates by need x affordance, moves one
stride toward the winner, and drinks from it on arrival. Drop a brand-new
object onto the field and agents reroute to it with no code changes —
the foreknowledge-free property is the whole point.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional


ORIGIN = "levi-revival/afford"


@dataclass
class AffordanceObject:
    """A thing on the field. All it may say is what it affords."""

    name: str
    x: float
    y: float
    affordances: Dict[str, float]  # need -> provision strength per visit
    capacity: float = math.inf  # total provision before depletion

    def advertise(self) -> Dict[str, float]:
        """The affordance signal. Agents may read this and nothing else."""
        if self.capacity <= 0:
            return {}
        return dict(self.affordances)

    def draw(self, need: str, amount: float) -> float:
        """Take up to ``amount`` of provision for ``need``. Returns taken."""
        offered = self.advertise().get(need, 0.0)
        taken = min(offered, amount, self.capacity)
        self.capacity -= taken
        return taken


@dataclass
class Agent:
    """A needy wanderer. Knows its needs, reads signals, knows nothing else."""

    name: str
    x: float
    y: float
    needs: Dict[str, float]  # need -> intensity (0 = sated)
    stride: float = 1.0
    target: Optional[str] = None  # object name, recomputed every scan

    def hungriest(self) -> Optional[str]:
        """The need pressing hardest right now."""
        open_needs = {k: v for k, v in self.needs.items() if v > 0}
        if not open_needs:
            return None
        return max(open_needs, key=lambda k: open_needs[k])


@dataclass
class StepEvent:
    agent: str
    kind: str  # "move" | "arrive" | "drink" | "idle"
    detail: str


class Terrain:
    """The smart field. Objects advertise; agents gradient-follow."""

    def __init__(self) -> None:
        self.objects: Dict[str, AffordanceObject] = {}
        self.agents: Dict[str, Agent] = {}
        self.events: List[StepEvent] = []

    # -- population ----------------------------------------------------

    def place(self, obj: AffordanceObject) -> None:
        self.objects[obj.name] = obj

    def spawn(self, agent: Agent) -> None:
        self.agents[agent.name] = agent

    # -- the loop -------------------------------------------------------

    def scan(self, agent: Agent) -> Dict[str, Dict[str, float]]:
        """What the agent may perceive: name -> advertised affordances.

        Zero foreknowledge enforced by construction — the agent never
        sees object internals, only the broadcast signal.
        """
        return {name: obj.advertise() for name, obj in self.objects.items()}

    def _score(
        self, agent: Agent, signals: Dict[str, Dict[str, float]]
    ) -> Optional[str]:
        best: Optional[str] = None
        best_score = 0.0
        for name, aff in signals.items():
            score = sum(
                agent.needs.get(need, 0.0) * strength for need, strength in aff.items()
            )
            if score > best_score:
                best_score = score
                best = name
        return best

    def step(self) -> List[StepEvent]:
        """One tick: scan, pick the gradient winner, move, drink."""
        tick: List[StepEvent] = []
        for agent in self.agents.values():
            need = agent.hungriest()
            if need is None:
                tick.append(StepEvent(agent.name, "idle", "sated; no open needs"))
                continue
            signals = self.scan(agent)
            target_name = self._score(agent, signals)
            agent.target = target_name
            if target_name is None:
                tick.append(StepEvent(agent.name, "idle", f"no affordance for {need}"))
                continue
            obj = self.objects[target_name]
            dist = math.hypot(obj.x - agent.x, obj.y - agent.y)
            if dist <= agent.stride:
                agent.x, agent.y = obj.x, obj.y
                taken = obj.draw(need, agent.needs[need])
                agent.needs[need] = max(0.0, agent.needs[need] - taken)
                tick.append(
                    StepEvent(
                        agent.name, "drink", f"took {taken:.2f} of {need} at {obj.name}"
                    )
                )
            else:
                dx, dy = (obj.x - agent.x) / dist, (obj.y - agent.y) / dist
                agent.x += dx * agent.stride
                agent.y += dy * agent.stride
                tick.append(
                    StepEvent(
                        agent.name,
                        "move",
                        f"toward {obj.name} ({dist - agent.stride:.2f} left)",
                    )
                )
        self.events.extend(tick)
        return tick

    def run(self, ticks: int) -> List[StepEvent]:
        """Run several ticks; returns the full event log."""
        out: List[StepEvent] = []
        for _ in range(ticks):
            out.extend(self.step())
        return out
