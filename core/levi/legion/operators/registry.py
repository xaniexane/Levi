"""Wren + Sidewinder registry: seats, twin verifiers, registration.

Chauncey picked these two (2026-09-22); the other four Wave 1
personas were reverted (see 7193ac74) and remain in history.

Seats (public service handles)::

    service.dev-lift   -> wren
    service.goal-line  -> sidewinder

Corroboration wiring: the twin config below plugs straight into
:func:`levi.operator.registry.resolve_twin` — primary does the work,
the named verifier is the second pair of eyes. The two verify each
other (cross-verification); defaults are overridable through the
normal twins config shape. Standing twin mode is ``"on_demand"``
(ratified 2026-09-18).

GAP (reported, not built): ``goal-line`` has no entry in the
service taxonomy (``core/levi/services/offering.py`` SERVICE_TYPES)
and no engine behind it — ``dev-lift`` has both (the Site Lift
machinery). The Sidewinder persona is real; the goal-line service
behind it is the next build.
"""

from __future__ import annotations

from typing import Dict

from levi.operator.registry import OperatorRegistry

from .persona import ServicePersona, ServicePersonaCard
from .sidewinder import CARD as SIDEWINDER_CARD
from .sidewinder import make_sidewinder
from .wren import CARD as WREN_CARD
from .wren import make_wren

__all__ = [
    "SERVICE_CARDS",
    "SERVICE_SEATS",
    "SERVICE_TWINS_CONFIG",
    "make_persona",
    "register_service_personas",
    "service_persona_names",
]

#: name -> card, in spec order.
SERVICE_CARDS: Dict[str, ServicePersonaCard] = {
    "wren": WREN_CARD,
    "sidewinder": SIDEWINDER_CARD,
}

_MAKERS = {
    "wren": make_wren,
    "sidewinder": make_sidewinder,
}

#: Seat -> persona name. Seats accept any operator by name/config, so
#: swapping a persona is a config change, never a code change.
SERVICE_SEATS: Dict[str, str] = {
    "service.dev-lift": "wren",
    "service.goal-line": "sidewinder",
}

#: Twin config for :func:`levi.operator.registry.resolve_twin` —
#: the corroboration rule, wired. Each seat's verifier is the
#: persona's default second pair of eyes.
SERVICE_TWINS_CONFIG: Dict[str, Dict] = {
    "twins": {
        "mode": "on_demand",
        "seats": {
            seat: {"primary": name, "verifier": SERVICE_CARDS[name].verifier}
            for seat, name in SERVICE_SEATS.items()
        },
    }
}


def service_persona_names() -> list[str]:
    """The built service persona names, in spec order."""
    return list(SERVICE_CARDS)


def make_persona(name: str, base_name: str = "levi-brain") -> ServicePersona:
    """Build one service persona operator (unbound)."""
    try:
        maker = _MAKERS[name]
    except KeyError:
        raise ValueError(
            f"unknown service persona {name!r}; must be one of "
            f"{service_persona_names()}"
        ) from None
    return maker(base_name=base_name)


def register_service_personas(
    registry: OperatorRegistry,
    base_name: str = "levi-brain",
) -> OperatorRegistry:
    """Bind the personas to ``registry`` and register them by name.

    Each persona delegates its turns to ``base_name`` (resolved from
    the same registry at step time) with its persona system prompt
    prepended. Registration validates every persona against the
    operator contract (no-mask law enforced); a violation raises
    :class:`levi.operator.contract.OperatorContractError`.
    """
    for name in service_persona_names():
        persona = make_persona(name, base_name=base_name).bind(registry)
        registry.register(name, persona, replace=True)
    return registry
