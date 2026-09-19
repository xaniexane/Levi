# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Wave roster + corroboration gate — the 11-agent Phase 0 wave.

Each wave agent owns one build and owes one first milestone, taken
verbatim from the dynasty playbook. No agent ships its milestone
alone: :data:`CORROBORATION_GATE` requires two distinct agents to
sign off — the owner AND an independent verifier. Solo ships: never.
"""

from __future__ import annotations

from typing import Dict, List

WAVE_ROSTER: List[Dict[str, str]] = [
    {
        "agent_id": "shellwright",
        "owns": "LEVI Shell",
        "first_milestone": "CLI prototype → Android body",
    },
    {
        "agent_id": "forgehand",
        "owns": "LEVI Forge",
        "first_milestone": "editor core + embedded runtime",
    },
    {
        "agent_id": "vaultkeeper",
        "owns": "LEVI Vault",
        "first_milestone": "repo index + verified installs",
    },
    {
        "agent_id": "threadweaver",
        "owns": "Thread+Waves",
        "first_milestone": "agent threads + local media plugin",
    },
    {
        "agent_id": "veilwright",
        "owns": "overlays+VR",
        "first_milestone": "overlay launcher prototype",
    },
    {
        "agent_id": "starmaker",
        "owns": "creator suite",
        "first_milestone": "avatar/photo pipeline MVP",
    },
    {
        "agent_id": "gamemaster",
        "owns": "AI gaming",
        "first_milestone": "first automated game + ladder",
    },
    {
        "agent_id": "schoolmaster",
        "owns": "infinite learning",
        "first_milestone": "first course track + tutoring",
    },
    {
        "agent_id": "herald",
        "owns": "editions expansion",
        "first_milestone": "3 new sector editions",
    },
    {
        "agent_id": "keystone",
        "owns": "one-app shell",
        "first_milestone": "plugin host loading Shell+Forge",
    },
    {
        "agent_id": "quartermaster",
        "owns": "cross-cutting: money/snapshots/receipts",
        "first_milestone": "Cybrus wiring, 70/30, stage snapshots",
    },
]

CORROBORATION_GATE: Dict[str, object] = {
    "rule": "two-agent sign-off",
    "owner": "required",
    "independent_verifier": "required",
    "solo_ships": False,
}


def list_roster() -> List[Dict[str, str]]:
    """Return a copy of the wave roster."""
    return [dict(entry) for entry in WAVE_ROSTER]


def get_agent(agent_id: str) -> Dict[str, str] | None:
    """Return the roster entry for ``agent_id``, or None."""
    for entry in WAVE_ROSTER:
        if entry["agent_id"] == agent_id:
            return dict(entry)
    return None


def check_signoff(signoffs: List[str]) -> bool:
    """True iff at least two DISTINCT agent ids signed off.

    Duplicates don't count — ``["a", "a"]`` is one agent agreeing with
    itself, which is exactly what the gate exists to forbid.
    """
    return len(set(signoffs)) >= 2
