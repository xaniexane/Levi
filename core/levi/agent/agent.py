"""Agents — the living runtime entities. Minions are the frozen records.

Naming law: going forward they are AGENTS. ``Minion`` stays strictly the
frozen intake-record dataclass in :mod:`levi.automation.minions`
(schema-fidelity law — its 471 constructor calls are never churned).
Every catalog row is actually an agent, classed AI / SI / XI, realized
as a twin pair: left brain + right brain, two bodies, two minds.

The twin pair reuses the twin machinery (:mod:`levi.twins.twin`):
``kind="agent"``, ``subject=<agent_id>``, sides fg/bg, where the Agent
layer declares fg = left brain (sequence/logic/execution) and bg = right
brain (pattern/variation/intuition). Pair links are bidirectional —
both records share one ``pair_id`` and each names the other as
counterpart via :func:`levi.twins.twin.counterpart_side`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from levi.agent.hemisphere import (
    HEMISPHERES,
    LEFT,
    RIGHT,
    Hemisphere,
    make_hemisphere,
)
from levi.automation.minions import MINIONS, Minion
from levi.ci import mapping as ci_mapping
from levi.operator.contract import (
    NATIVE,
    Operator,
    OperatorCapabilities,
    OperatorHealth,
    OperatorMessage,
    OperatorResult,
    validate_operator,
)
from levi.twins.twin import Twin, counterpart_side, twin_id_for

__all__ = [
    "AGENT_VERSION",
    "FG_HEMISPHERE",
    "BG_HEMISPHERE",
    "Agent",
    "AgentOperator",
    "build_agent",
    "build_agents",
    "find_minion",
]

#: Agent layer version (provenance on every twin record).
AGENT_VERSION = "1.0.0"

#: Hemisphere <-> twin-side mapping (declared, never silent).
#: fg = left brain, bg = right brain.
FG_HEMISPHERE = LEFT
BG_HEMISPHERE = RIGHT
_SIDE_FOR = {LEFT: "fg", RIGHT: "bg"}


def find_minion(minion_id: str) -> Minion:
    for m in MINIONS:
        if m.id == minion_id:
            return m
    raise KeyError(f"unknown minion id: {minion_id}")


def _twin_record(
    agent_id: str, hemisphere: str, hemi_obj: Hemisphere, minion: Minion
) -> Twin:
    """One body+mind of the pair, as a twin record.

    Reuses :class:`levi.twins.twin.Twin` directly — the pair link is the
    shared ``pair_id``; direction is recovered via ``counterpart_side``.
    """
    side = _SIDE_FOR[hemisphere]
    return Twin(
        twin_id=twin_id_for("agent", agent_id, side),
        kind="agent",
        subject=agent_id,
        side=side,
        pair_id=f"agentpair:{agent_id}",
        state={
            "hemisphere": hemisphere,
            "role": hemi_obj.role,
            "character": hemi_obj.character,
            "class": hemi_obj.class_tag,
            "minion_id": minion.id,
            "status": "standing-by",
        },
        notes=(
            f"{hemisphere} brain of agent {agent_id} "
            f"({hemi_obj.mind_descriptor}); twin side {side}; "
            f"counterpart {counterpart_side(side)}; "
            f"provenance levi.agent v{AGENT_VERSION}"
        ),
    )


@dataclass
class Agent:
    """One living agent: a catalog row realized as a twin pair.

    Two bodies, two minds — left (sequence/logic/execution) and right
    (pattern/variation/intuition) — that must converge to one action
    (see :mod:`levi.agent.merge`).
    """

    agent_id: str
    minion_id: str
    class_tag: str
    counsel_name: str
    grade: str
    left: Hemisphere
    right: Hemisphere
    twins: List[Twin]
    pair_id: str
    provenance: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.twins) != 2:
            raise ValueError("an agent is exactly one twin pair: two bodies")
        sides = sorted(t.side for t in self.twins)
        if sides != ["bg", "fg"]:
            raise ValueError(f"twin pair must be fg+bg, got {sides}")
        pair_ids = {t.pair_id for t in self.twins}
        if len(pair_ids) != 1 or self.pair_id not in pair_ids:
            raise ValueError("twin pair must share one pair_id")
        # Bidirectional: each twin's counterpart resolves to the other.
        by_side = {t.side: t for t in self.twins}
        for t in self.twins:
            other = by_side[counterpart_side(t.side)]
            if other.twin_id != twin_id_for("agent", self.agent_id, counterpart_side(t.side)):
                raise ValueError(f"broken pair link on {t.twin_id}")

    def hemisphere(self, name: str) -> Hemisphere:
        return self.left if name == LEFT else self.right

    def to_dict(self) -> Dict[str, Any]:
        from dataclasses import asdict

        return {
            "agent_id": self.agent_id,
            "minion_id": self.minion_id,
            "class_tag": self.class_tag,
            "counsel_name": self.counsel_name,
            "grade": self.grade,
            "pair_id": self.pair_id,
            "left": asdict(self.left),
            "right": asdict(self.right),
            "twins": [t.to_dict() for t in self.twins],
            "provenance": self.provenance,
        }


class AgentOperator(Operator):
    """The universal Operator contract worn by one agent.

    LEVI-native (``kind=NATIVE``), mirroring the enterprise grading
    wrapper: the tool columns ride along as plain data references —
    never identity, never branding.
    """

    def __init__(self, agent: Agent, minion: Minion):
        self.agent = agent
        self.minion = minion
        self.name = agent.agent_id
        self.kind = NATIVE
        self.lineage = "levi-native:agent-catalog"
        self.version = AGENT_VERSION
        self.is_foreign = False

    @property
    def identity_label(self) -> str:
        return (
            f"agent:{self.name}[{self.agent.class_tag}]"
            f"(left+right:{self.agent.pair_id})"
        )

    def capabilities(self) -> OperatorCapabilities:
        tools = tuple(
            t
            for t in (
                self.minion.android_tool,
                self.minion.windows_tool,
                self.minion.mac_tool,
                self.minion.chrome_extension,
            )
            if t and t.strip()
        )
        return OperatorCapabilities(
            tools=tools,
            streaming=False,
            memory_access=False,
            context_window=1024,
            tool_use_loop=False,
            max_tool_calls_per_step=8,
            notes=(
                f"agent {self.name}: {self.minion.subcategory} "
                f"[{self.agent.class_tag}] twin pair "
                f"left={self.agent.left.role} right={self.agent.right.role}"
            ),
        )

    def step(
        self,
        messages: List[OperatorMessage],
        tools: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> OperatorResult:
        t0 = time.perf_counter()
        return OperatorResult(
            text=(
                f"[{self.identity_label}] standing by — twin pair, "
                f"left ({self.agent.left.role}) + right ({self.agent.right.role}). "
                "Seat me to serve; I do not fake work."
            ),
            operator=self.name,
            kind=self.kind,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            finish_reason="stop",
            note="agent stub: awaiting seat assignment",
        )

    def health(self) -> OperatorHealth:
        return OperatorHealth(ok=True, note="agent twin pair; standing by")


def build_agent(minion: Minion, grade: str = "ungraded") -> Agent:
    """Realize one catalog row as a twin-pair agent.

    The ``Minion`` record is read, never modified — schema-fidelity law.
    """
    agent_id = minion.id
    class_tag = ci_mapping.class_for_minion(minion)
    counsel_name = ci_mapping.counsel_for_class(class_tag)
    left_twin_id = twin_id_for("agent", agent_id, "fg")
    right_twin_id = twin_id_for("agent", agent_id, "bg")
    left = make_hemisphere(LEFT, agent_id, class_tag, left_twin_id)
    right = make_hemisphere(RIGHT, agent_id, class_tag, right_twin_id)
    pair_id = f"agentpair:{agent_id}"
    twins = [
        _twin_record(agent_id, LEFT, left, minion),
        _twin_record(agent_id, RIGHT, right, minion),
    ]
    provenance = {
        "source": "core/levi/automation/minions.py (untouched; read, never edited)",
        "derived_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "derivation": (
            "one twin-pair agent per catalog row; fg=left brain "
            "(sequence/logic/execution), bg=right brain "
            "(pattern/variation/intuition)"
        ),
        "counsel_rule": "ci.mapping.class_for_minion",
        "agent_layer": f"levi.agent v{AGENT_VERSION}",
    }
    agent = Agent(
        agent_id=agent_id,
        minion_id=minion.id,
        class_tag=class_tag,
        counsel_name=counsel_name,
        grade=grade,
        left=left,
        right=right,
        twins=twins,
        pair_id=pair_id,
        provenance=provenance,
    )
    # Contract gate: an agent that fails validation is never banked.
    AgentOperator(agent, minion).validate()
    return agent


def build_agents(grades: Optional[Dict[str, str]] = None) -> List[Agent]:
    """Build all 471 agents — one twin pair per catalog row."""
    grades = grades or {}
    agents = []
    for m in MINIONS:
        agent = build_agent(m, grade=grades.get(m.id, "ungraded"))
        agents.append(agent)
    return agents
