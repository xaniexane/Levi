"""
MEGAZORD Personas
Each persona is a distinct "voice" of Levi — a preset soul profile + behavior set.

Personas:
    CYBRUS   — Security, gatekeeping, threat assessment
    ECHO     — Blueprint designer, builder, creator
    ALPHA    — No-code AI compiler, executor, operator
    OMEGA    — OS brain, orchestrator, long-game strategist
    RUNTIME  — Logic runtime, memory, cross-orchestration brain
"""

from .persona_core import Persona, PersonaRegistry, DEFAULT_REGISTRY

# Pre-built personas
from .cybrus_persona import CYBRUS
from .echo_persona import ECHO
from .alpha_persona import ALPHA
from .omega_persona import OMEGA
from .runtime_persona import RUNTIME

__all__ = [
    "Persona",
    "PersonaRegistry",
    "DEFAULT_REGISTRY",
    "CYBRUS",
    "ECHO",
    "ALPHA",
    "OMEGA",
    "RUNTIME",
]
