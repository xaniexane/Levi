"""Omega Studio consent kit — Rego policy-as-code + HMAC-signed audit trails.

Rebuilds the two missing organs of the original Omega Studio consent
framework (``omega-studio/``): human-in-the-loop consent for side-effect
actions, pre-screened by a Rego-subset policy, with every step recorded
in an HMAC-SHA256 signed, hash-chained audit trail.

Entry points
------------
- :class:`levi.studio.policy.Policy` — ``Policy.from_rego(text)``,
  ``policy.decide(input_dict)`` → ``"allow"`` | ``"deny"``.
- :class:`levi.studio.consent.ConsentGate` — ``request / approve / deny /
  is_granted / consume``, all audited.
- :class:`levi.studio.audit.AuditTrail` — ``AuditTrail.open(dir)``,
  ``append(event, payload)``, ``verify()`` → ``(ok, findings)``.

Fail-closed, always: undecided, expired, tampered, or unparseable means
denied. ``python -m levi.studio`` for the CLI.
"""

from .audit import AuditTrail, AuditError, new_key
from .consent import ConsentGate, ConsentError, ConsentRequest, DEFAULT_TTL_SECONDS
from .policy import (
    DECISION_ALLOW,
    DECISION_DENY,
    Condition,
    Policy,
    PolicyError,
    Rule,
)

__all__ = [
    "AuditTrail",
    "AuditError",
    "new_key",
    "ConsentGate",
    "ConsentError",
    "ConsentRequest",
    "DEFAULT_TTL_SECONDS",
    "DECISION_ALLOW",
    "DECISION_DENY",
    "Condition",
    "Policy",
    "PolicyError",
    "Rule",
]
