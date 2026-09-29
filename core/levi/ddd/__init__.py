# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: 2026-09-25.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""LEVI-native home for the DirectDepositDaemon (DDD) SI operators.

Advisory-only agents, one per DDD product. Draft-only, no outbound,
no payment — see ``levi.ddd.agents.base`` for the enforced laws.
"""

from levi.ddd import agents as agents  # noqa: F401  (convenience re-export)
