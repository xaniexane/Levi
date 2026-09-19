"""Interpenetration — the composition-law engine.

Where the graph engine (``levi.graph.interpenetration``) keeps the
capability graph, this package is the *law*: how organs interpenetrate,
what a composition inherits, what may never be collapsed, and the
verifiable signature every composition emits.

Standing laws enforced here:

- Strictest-risk-ceiling inheritance. In LEVI's risk-ceiling dialect a
  higher number is a *higher clearance* to handle risk (see
  ``levi.graph.interpenetration``: "Composites inherit the strictest risk
  ceiling" implemented as ``max`` of parts; ``levi.agent.runtime`` sets
  ``run.risk_ceiling = max(...)``). The composite inherits the highest
  clearance any organ holds; anything above it is capped fail-closed.
- interrogation ⊥ no_hero: the two control personas are orthogonal and
  are never collapsed into one composition. Attempting it raises
  :class:`InvariantViolation`.
"""

from __future__ import annotations

from .composition import (
    CONTROL_PERSONAS,
    ORGAN_RISK,
    Composite,
    InvariantViolation,
    Organ,
    check_control_persona_invariant,
    interpenetrate,
)
from .signature import Signature, compute_signature, verify_signature
from .fog import FOG_PROBES, FogVerdict, fog_sweep, phantom_run
from .catalog import (
    ECHO_MANDELLA_ORGANS,
    canonical_catalog_bytes,
    sign_automation_catalog,
    signature_for_rows,
    verify_signatures,
)

__all__ = [
    "CONTROL_PERSONAS",
    "ECHO_MANDELLA_ORGANS",
    "FOG_PROBES",
    "ORGAN_RISK",
    "Composite",
    "FogVerdict",
    "InvariantViolation",
    "Organ",
    "Signature",
    "canonical_catalog_bytes",
    "check_control_persona_invariant",
    "compute_signature",
    "fog_sweep",
    "interpenetrate",
    "phantom_run",
    "sign_automation_catalog",
    "signature_for_rows",
    "verify_signature",
    "verify_signatures",
]
