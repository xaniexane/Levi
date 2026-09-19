"""Academy differentiators — measures no one else is using.

Six modules that make the boot camp prove itself instead of
asserting itself:

- ``receipts``  — sealed skill receipts: finish well = receipt.
- ``compost``   — failure compost: flunked exercises become targeted
  remediation drills (REIM lineage).
- ``stakes``    — stake-under-fog drills: learners stake reputation on
  answers before reveal; calibration scored, not just correctness.
- ``mastery``   — corroboration-gated mastery: a skill counts only
  after demonstration in 3 distinct contexts.
- ``decay``     — skill decay: unused skills rot on schedule and the
  academy re-tests. Never static, never outdated.
- ``livefire``  — live-fire finals: the final module is supervised
  real work through the nursery workload router, not multiple choice.

Stdlib only. State under ``<LEVI_HOME>/academy/differentiators/``,
owner-only permissions. No network, no randomness in scoring.
"""

from __future__ import annotations

from levi.academy.differentiators import compost, decay, livefire, mastery, receipts, stakes

__all__ = ["compost", "decay", "livefire", "mastery", "receipts", "stakes"]
