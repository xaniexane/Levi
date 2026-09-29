# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: 2026-09-25.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""DDD daily-income daemon skill pack: draft-only runners as skills.

Each skill runs one daemon's ``run_daily()`` and returns the receipt.
INFO risk, zero permissions — the daemons write local draft files only.

Wired into ``SkillRegistry`` via lazy import (same pattern as the other
packs): ``from levi.ddd.daemons.skills import DAEMON_SKILLS``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from levi.skill.registry import Skill, SkillRisk

__all__ = ["DAEMON_SKILLS", "run_daemon_skill"]


def run_daemon_skill(daemon_id: str, args: Optional[Dict[str, Any]] = None) -> str:
    """Run one daemon's daily pass; return the receipt as plain text."""
    from levi.ddd.daemons.audit_daemon import AuditDaemon
    from levi.ddd.daemons.leads_daemon import LeadsDaemon
    from levi.ddd.daemons.listing_daemon import ListingDaemon

    daemons = {
        "audit-daemon": AuditDaemon,
        "listing-daemon": ListingDaemon,
        "leads-daemon": LeadsDaemon,
    }
    cls = daemons.get(daemon_id)
    if cls is None:
        return f"Unknown daemon {daemon_id!r} — nothing ran."
    receipt = cls().run_daily()
    status = receipt.get("status", "?")
    note = receipt.get("note", "")
    drafts = receipt.get("drafts_written") or []
    lines = [
        f"[{daemon_id}] status={status}",
        f"rows_seen={receipt.get('rows_seen', 0)}",
        f"drafts_written={len(drafts)}",
    ]
    lines.extend(f"  - {d}" for d in drafts)
    lines.append(note)
    return "\n".join(lines)


def _make_skill(daemon_id: str, name: str, description: str) -> Skill:
    def _handler(args: Optional[Dict[str, Any]] = None, _did: str = daemon_id) -> str:
        return run_daemon_skill(_did, args)

    return Skill(
        id=f"ddd.daily-{daemon_id.split('-')[0]}",
        name=name,
        description=description,
        category="ddd",
        risk_level=SkillRisk.INFO,
        permissions=[],
        requires_confirmation=False,
        handler=_handler,
        tags=["ddd", "daily-daemon", "draft-only"],
        version="1.0.0",
    )


DAEMON_SKILLS: List[Skill] = [
    _make_skill(
        "audit-daemon",
        "DDD daily audit daemon",
        "Runs the audit daemon's daily pass: up to 3 info-only site audits "
        "from Chauncey's prospect queue → $49 AuditNow drafts + outreach "
        "drafts in the DDD inbox. Draft only — nothing sent or charged.",
    ),
    _make_skill(
        "listing-daemon",
        "DDD daily listing daemon",
        "Runs the listing daemon's daily pass: resale inventory rows → "
        "marketplace listing drafts + pricing guidance in the DDD inbox. "
        "Draft only — nothing posted.",
    ),
    _make_skill(
        "leads-daemon",
        "DDD daily leads daemon",
        "Runs the leads daemon's daily pass: lead queue rows → "
        "DRAFT-labeled review-reply drafts (never posted — hard rule) + "
        "lead-gen pitch drafts in the DDD inbox. Contacts nobody.",
    ),
]
