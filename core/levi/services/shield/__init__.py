"""Shield: authorized security assessment + hardening as a service.

Defensive blue-team only. This package plans, records, hardens, and
verifies — it performs no automated intrusion, ships no offensive
capability, and runs nothing without written client authorization.

Pipeline: intake -> authorize -> assess (plan + findings) -> harden
-> verify -> sealed report, offered through the legion service
standard (analyze -> quote -> deliver -> paid -> showcase).
"""

from __future__ import annotations

from levi.services.shield import assess, authorization, harden, report, service

__all__ = ["assess", "authorization", "harden", "report", "service"]
