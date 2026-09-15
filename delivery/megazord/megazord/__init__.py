"""
MEGAZORD — LEVI × L.W.P. megazord.

A single import surface for the combined Levi + L.W.P. organism.

Quick start:
    from megazord import MegaZord, CYBRUS, ECHO, ALPHA, OMEGA, RUNTIME

    mz = MegaZord(persona="alpha")
    result = mz.handle("Build me a hitl job tracker")
"""

from .personas import (
    CYBRUS,
    ECHO,
    ALPHA,
    OMEGA,
    RUNTIME,
    Persona,
    PersonaRegistry,
    DEFAULT_REGISTRY,
)
from .flows import (
    Flow,
    FlowEngine,
    FlowRegistry,
    LeviThinkFlow,
    LeviDecideFlow,
    LeviActFlow,
)
from .bridges.levi_bridge import LeviBridge
from .megazord_core import MegaZord

__all__ = [
    "CYBRUS",
    "ECHO",
    "ALPHA",
    "OMEGA",
    "RUNTIME",
    "Persona",
    "PersonaRegistry",
    "DEFAULT_REGISTRY",
    "Flow",
    "FlowEngine",
    "FlowRegistry",
    "LeviThinkFlow",
    "LeviDecideFlow",
    "LeviActFlow",
    "LeviBridge",
    "MegaZord",
]
