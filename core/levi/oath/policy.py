"""Policy enforcement for LEVI Oath.

Enforcement order — every mission passes through all three gates, in
order, and a denial at any gate stops the mission:

1. **Trust gate.**  Mission creation requires ``VERIFIED`` or ``TRUSTED``
   mail.  This is a hard requirement: there is no override, no owner flag,
   no "just this once".  A contact may additionally raise their own floor
   to ``TRUSTED``; it can never be lowered below ``VERIFIED``.
2. **Permission check.**  Deny-closed: for each stage, the contact must
   hold an explicit grant covering the command's tier.  Anything not
   explicitly granted is denied.
3. **Risk-ceiling inheritance.**  A contact can never run a command tier
   above their personal ``tier_ceiling``.  ``dangerous``-tier commands
   additionally require the explicit ``d`` grant letter on that exact
   command — the ceiling alone is not enough.

Grant letters to tiers: ``r`` -> ``read``, ``w`` -> ``write``,
``x`` -> ``execute``.  ``d`` is the explicit dangerous grant.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from levi.oath.commands import CommandDefinition, CommandRegistry
from levi.oath.contacts import TIERS, TIER_LETTER, Contact
from levi.oath.trust import TRUST_ORDER, TRUSTED, VERIFIED

__all__ = [
    "PolicyDecision",
    "PolicyError",
    "trust_gate",
    "check_command",
    "check_pipeline",
    "trust_meets_floor",
]

#: The global hard floor: nothing below VERIFIED may create a mission.
HARD_FLOOR = VERIFIED


class PolicyError(Exception):
    """Raised (or recorded) when a policy gate denies an action."""


@dataclass(frozen=True)
class PolicyDecision:
    """One gate's verdict."""

    allowed: bool
    gate: str
    reason: str

    def __bool__(self) -> bool:  # pragma: no cover - convenience
        return self.allowed


def trust_meets_floor(trust: str, floor: str) -> bool:
    """Return True when ``trust`` is at or above ``floor`` on the ladder."""
    try:
        return TRUST_ORDER.index(trust) >= TRUST_ORDER.index(floor)
    except ValueError:
        return False


def trust_gate(contact: Contact, trust: str) -> PolicyDecision:
    """Gate 1: the trust gate.

    ``trust`` must reach ``HARD_FLOOR`` (``VERIFIED``) *and* the contact's
    own ``trust_floor``.  There is deliberately no override parameter.
    """
    if not trust_meets_floor(trust, HARD_FLOOR):
        return PolicyDecision(
            False,
            "trust",
            f"mission requires {HARD_FLOOR} or {TRUSTED}; got {trust} — denied",
        )
    if not trust_meets_floor(trust, contact.trust_floor):
        return PolicyDecision(
            False,
            "trust",
            f"contact {contact.name!r} requires {contact.trust_floor}; got {trust} — denied",
        )
    return PolicyDecision(True, "trust", f"trust {trust} meets floor {contact.trust_floor}")


def check_command(
    contact: Contact,
    definition: CommandDefinition,
) -> PolicyDecision:
    """Gates 2 + 3 for a single command: permission, then risk ceiling.

    Deny-closed: the contact must hold the exact grant letter the tier
    requires on *this* command.  Then the tier must sit at or below the
    contact's ``tier_ceiling``.
    """
    tier = definition.tier
    if tier not in TIERS:
        return PolicyDecision(False, "permission", f"unknown tier {tier!r} — denied")

    # Gate 2 — permission (deny-closed).
    needed = TIER_LETTER[tier]
    granted = set(contact.grants.get(definition.name, ()))
    if needed not in granted:
        return PolicyDecision(
            False,
            "permission",
            f"contact {contact.name!r} lacks {needed!r} grant for "
            f"{definition.name!r} (tier {tier}) — denied",
        )

    # Gate 3 — risk ceiling inheritance.
    if TIERS.index(tier) > TIERS.index(contact.tier_ceiling):
        return PolicyDecision(
            False,
            "risk-ceiling",
            f"tier {tier} exceeds {contact.name!r}'s ceiling {contact.tier_ceiling} — denied",
        )
    return PolicyDecision(
        True,
        "risk-ceiling",
        f"{definition.name!r} (tier {tier}) within grants and ceiling",
    )


def check_pipeline(
    contact: Contact,
    stages: list[dict],
    registry: Optional[CommandRegistry] = None,
) -> list[PolicyDecision]:
    """Run gates 2+3 for every stage of a parsed pipeline.

    ``stages`` are dicts as produced by :func:`levi.oath.pipeline.parse`
    (``{"kind": "cmd"|"ai"|"reply", "name": ..., "args": {...}}``).
    Returns one decision per stage; callers should stop at the first
    denial.
    """
    registry = registry or CommandRegistry()
    decisions: list[PolicyDecision] = []
    for stage in stages:
        name = stage.get("name", "")
        try:
            definition = registry.get(name)
        except Exception as exc:  # unknown command -> deny
            decisions.append(
                PolicyDecision(False, "permission", f"unknown command {name!r} — denied ({exc})")
            )
            continue
        # Validate arguments render *before* the stage runs: a stage whose
        # argv cannot be built is denied, not retried.
        try:
            definition.render(dict(stage.get("args", {})))
        except Exception as exc:
            decisions.append(
                PolicyDecision(False, "permission", f"{name!r}: invalid arguments — denied ({exc})")
            )
            continue
        decisions.append(check_command(contact, definition))
    return decisions
