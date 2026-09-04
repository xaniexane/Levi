"""
MEGAZORD Personas
Each persona is a distinct "voice" of Levi — a preset soul profile + behavior set.

Personas:
    CYBRUS   — Security, gatekeeping, threat assessment
    ECHO     — Blueprint designer, builder, creator
    ALPHA    — No-code AI compiler, executor, operator
    OMEGA    — OS brain, orchestrator, long-game strategist
    KAI      — Logic runtime, memory, cross-orchestration brain
"""

from .persona_core import Persona, PersonaRegistry

# Pre-built personas
from .cybrus_persona import CYBRUS
from .echo_persona   import ECHO
from .alpha_persona  import ALPHA
from .omega_persona  import OMEGA
from .kai_persona    import KAI

__all__ = [
    "Persona", "PersonaRegistry",
    "CYBRUS", "ECHO", "ALPHA", "OMEGA", "KAI",
]
