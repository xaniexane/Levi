"""Legion service-operator personas — the public identities.

Wren (dev-lift) and Sidewinder (goal-line), picked by Chauncey
2026-09-22. The population meets the help, not the bloodline:
public identities only — no dynasty names, no mechanics.
"""

from .persona import (
    CORROBORATION_RULE,
    SHARED_SOUL,
    ServicePersona,
    ServicePersonaCard,
    build_system_prompt,
)
from .registry import (
    SERVICE_CARDS,
    SERVICE_SEATS,
    SERVICE_TWINS_CONFIG,
    make_persona,
    register_service_personas,
    service_persona_names,
)

__all__ = [
    "CORROBORATION_RULE",
    "SHARED_SOUL",
    "SERVICE_CARDS",
    "SERVICE_SEATS",
    "SERVICE_TWINS_CONFIG",
    "ServicePersona",
    "ServicePersonaCard",
    "build_system_prompt",
    "make_persona",
    "register_service_personas",
    "service_persona_names",
]
