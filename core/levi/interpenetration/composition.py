"""Composition law: interpenetrate organs, inherit the strictest ceiling.

``interpenetrate(*organs)`` fuses organs into a :class:`Composite` that
inherits the strictest risk ceiling of its members and emits a verifiable
:class:`~levi.interpenetration.signature.Signature`.

Risk-ceiling dialect (binding, repo-wide): a higher number is a higher
*clearance* to handle risk. ``levi.graph.interpenetration`` documents
"Composites inherit the strictest risk ceiling" and implements it as
``max`` of the parts; ``levi.agent.runtime`` sets
``run.risk_ceiling = max(s.risk_ceiling for s in selected)`` and caps any
risk above the ceiling fail-closed. This module follows that law exactly:
the composite is cleared up to the highest clearance any organ holds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple, Union

from .signature import Signature, compute_signature


@dataclass(frozen=True)
class Organ:
    """One interpenetrable organ: name, risk clearance, role."""

    name: str
    risk_ceiling: int
    role: str = ""


# Kernel organs with declared clearances. Echo only explores (no execution
# path of its own): clearance 1. Mandella recommends stakes under pressure:
# clearance 2. Both stay far below the protector/security band (4).
ORGAN_RISK: Dict[str, Organ] = {
    "echo": Organ(
        name="echo",
        risk_ceiling=1,
        role="expands the possibility space: taken / not-taken / wild branches",
    ),
    "mandella": Organ(
        name="mandella",
        risk_ceiling=2,
        role="stakes selection under domain pressure; recommends, never forces",
    ),
}

#: Control personas that are orthogonal (⊥) and may never be collapsed
#: into a single composition. Mirrors the special-persona handling in
#: ``levi.persona.composition``: interrogation/no_hero/reframe stay primary
#: alone — a composition fusing interrogation INTO no_hero (or vice versa)
#: would erase the distinction the organism relies on.
CONTROL_PERSONAS = frozenset({"interrogation", "no_hero"})


class InvariantViolation(ValueError):
    """A composition would collapse something the law keeps orthogonal."""


def check_control_persona_invariant(organs: Sequence[Organ]) -> None:
    """Enforce interrogation ⊥ no_hero: never collapsed, never fused.

    Raises :class:`InvariantViolation` when a composition contains both
    control personas — that is the collapse the law forbids.
    """
    names = {o.name.strip().lower() for o in organs}
    if CONTROL_PERSONAS <= names:
        raise InvariantViolation(
            "interrogation ⊥ no_hero: control personas are orthogonal and "
            "may never be collapsed into one composition"
        )


@dataclass(frozen=True)
class Composite:
    """A verified interpenetration of organs."""

    id: str
    name: str
    organs: Tuple[str, ...]
    risk_ceiling: int
    created_at: str
    signature: Signature = field(compare=False)


def _resolve(organs: Sequence[Union[str, Organ]]) -> List[Organ]:
    resolved: List[Organ] = []
    for o in organs:
        if isinstance(o, Organ):
            resolved.append(o)
            continue
        if isinstance(o, str):
            key = o.strip().lower()
            if key not in ORGAN_RISK:
                raise ValueError(f"unknown organ: {o!r}")
            resolved.append(ORGAN_RISK[key])
            continue
        raise ValueError(f"organ must be a name or Organ, got {type(o).__name__}")
    return resolved


def interpenetrate(
    *organs: Union[str, Organ],
    name: str = "",
    content: bytes = b"",
) -> Composite:
    """Fuse organs into a composite under the composition law.

    - The control-persona invariant is checked first: interrogation ⊥
      no_hero is never collapsed (:class:`InvariantViolation` otherwise).
    - ``risk_ceiling`` = max of the organs' clearances (strictest ceiling
      per LEVI's dialect — the composite is cleared up to the highest
      clearance any organ holds).
    - A :class:`Signature` is computed over ``content`` and attached; the
      composite id derives from it, so the composition is verifiable.
    """
    resolved = _resolve(organs)
    if len(resolved) < 2:
        raise ValueError("interpenetration needs at least 2 organs")
    check_control_persona_invariant(resolved)

    ceiling = max(o.risk_ceiling for o in resolved)
    organ_names = [o.name for o in resolved]
    sig = compute_signature(content, organ_names, ceiling)
    return Composite(
        id=f"composite-{sig.signature_id}",
        name=name or " × ".join(organ_names),
        organs=tuple(organ_names),
        risk_ceiling=ceiling,
        created_at=sig.timestamp,
        signature=sig,
    )
