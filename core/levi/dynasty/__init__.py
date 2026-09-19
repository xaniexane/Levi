# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Dynasty namespace — Phase 0 of the dynasty playbook.

This package is the code embodiment of Phase 0: the dynasty's day-zero
foundation. Eleven builds are coming; before any of them land, the
dynasty needs its maker, its law, its receipts, and its IP posture:

- :mod:`levi.dynasty.builder` — the Dynasty Builder agent spec. A
  trainee-class agent that serves and never graduates. It writes the
  first prototypes under strict tool scopes.
- :mod:`levi.dynasty.registry` — Builder registration in the dynasty's
  own registry, mirroring nursery workload laws (seeded facts, earned
  judgment, verification before acceptance). It is NOT enrolled in the
  nursery router, whose law admits only graduated trainees.
- :mod:`levi.dynasty.receipts` — sealed, hash-chained task receipts.
  Every task runs plan→execute→verify→receipt; no receipt, no advance.
- :mod:`levi.dynasty.snapshot` — day-0 snapshot helper over the real
  stage-snapshot engine (:mod:`levi.snapshots.stages`).
- :mod:`levi.dynasty.roster` — the 11-agent wave roster plus the
  two-agent corroboration gate. Solo ships: never.
- :mod:`levi.dynasty.shell` — the Builder's first task output: a
  CLI-first LEVI Shell prototype skeleton (sessions, command runner,
  automation hooks).

No network. No money rails. Phase 0 is law, not product.
"""

from levi.dynasty import builder, receipts, registry, roster, snapshot

__all__ = ["builder", "receipts", "registry", "roster", "snapshot"]
