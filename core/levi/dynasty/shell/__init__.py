# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Shell — CLI-first prototype skeleton of the clean-room terminal.

Phase 0 target, stated plainly: a terminal session that survives
process death. This package is the CLI-first prototype skeleton —
sessions, a guarded command runner, and automation hooks — designed
to be lifted into the Android body later (foreground-service
anchoring, guided package setup) without changing this contract.

Submodules:
- :mod:`levi.dynasty.shell.sessions` — in-memory session registry with
  optional JSON persistence.
- :mod:`levi.dynasty.shell.runner` — subprocess runner with a hard
  deny-list for destructive commands.
- :mod:`levi.dynasty.shell.hooks` — named automation hooks over the
  runner.
- :mod:`levi.dynasty.shell.__main__` — the ``python -m levi.dynasty.shell``
  CLI, which prints JSON.
"""
