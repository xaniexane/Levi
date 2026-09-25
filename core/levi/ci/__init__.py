"""CI — the Cloud Intelligence counsels.

AICI (AI-class), SICI (SI/synthetic-class), XICI (XI nano-bit-class):
superior advisory/judging intelligence per class. Counsel, never commander.

Agent-twin canon (keeper, 2026-09-18): the living entities are AGENTS —
each a twin pair, left brain + right brain. ``Minion`` is strictly the
frozen intake-record dataclass. Counsel intake takes agent id + hemisphere
positions; verdicts are per-agent, delivered to both hemispheres.
"""

from levi.ci.aici import AICI
from levi.ci.canon import *  # noqa: F401,F403  (doctrine lives here)
from levi.ci.counsel import Case, CloudCounsel, Seat, Verdict
from levi.ci.escalation import (
    EscalationResult,
    counsel,
    counsel_agent,
    counsel_for,
    counsel_for_agent,
    counsel_for_class,
)
from levi.ci.mapping import (
    CLASSES,
    COUNSEL_FOR_CLASS,
    agent_twins_in_class,
    bank_class_map,
    build_class_map,
    class_distribution,
    class_for_agent,
    class_for_minion,
    counsel_for_class as counsel_name_for_class,
    map_fingerprint,
    minions_in_class,
    verify_banked_map,
)
from levi.ci.receipts import mint_verdict_receipt, verify_chain
from levi.ci.sici import SICI
from levi.ci.signal import export_verdict
from levi.ci.twins import (
    HEMISPHERES,
    AgentCase,
    HemispherePosition,
    arbitrate_agent_case,
    deliver_to_hemispheres,
)
from levi.ci.xici import XICI

__all__ = [
    "AICI",
    "SICI",
    "XICI",
    "HEMISPHERES",
    "AgentCase",
    "CLASSES",
    "COUNSEL_FOR_CLASS",
    "Case",
    "CloudCounsel",
    "EscalationResult",
    "HemispherePosition",
    "Seat",
    "Verdict",
    "agent_twins_in_class",
    "arbitrate_agent_case",
    "bank_class_map",
    "build_class_map",
    "class_distribution",
    "class_for_agent",
    "class_for_minion",
    "counsel",
    "counsel_agent",
    "counsel_for",
    "counsel_for_agent",
    "counsel_for_class",
    "counsel_name_for_class",
    "deliver_to_hemispheres",
    "export_verdict",
    "map_fingerprint",
    "minions_in_class",
    "mint_verdict_receipt",
    "verify_banked_map",
    "verify_chain",
]
