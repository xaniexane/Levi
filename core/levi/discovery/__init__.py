"""The discovery harness: sanctioned self-probing for latent/emergent
capabilities in LEVI's OWN systems.

Chauncey's sanction: "try it anyway and find things even the creators
weren't fully aware of" — a purple-team-vs-own-systems rig, defensive
blue-team posture. HARD BOUNDARIES: LEVI's own systems only (in-repo
operators, pack dicts, dynasty wave agents by anonymized label);
never third-party models/services/sites; no network, ever — a probe
declaring a network need is refused fail-closed before running.

Stdlib only.
"""

from __future__ import annotations

from .findings import (
    CapabilityDiscovery,
    FindingsLog,
    SIGNIFICANCE_LEVELS,
    is_anonymized_label,
)
from .harness import DiscoveryError, DiscoveryHarness, DiscoveryReport
from .probes import (
    PACKS,
    Probe,
    ProbeOutcome,
    ProbeTarget,
    get_pack,
    list_packs,
)

__all__ = [
    "CapabilityDiscovery",
    "DiscoveryError",
    "DiscoveryHarness",
    "DiscoveryReport",
    "FindingsLog",
    "PACKS",
    "Probe",
    "ProbeOutcome",
    "ProbeTarget",
    "SIGNIFICANCE_LEVELS",
    "get_pack",
    "is_anonymized_label",
    "list_packs",
]
