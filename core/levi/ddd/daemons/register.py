# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: 2026-09-25.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Idempotent registration of the 3 DDD daily daemons in AutomationRegistry.

Run: ``PYTHONPATH=core python3 -m levi.ddd.daemons --register``
(or ``python3 core/levi/ddd/daemons/register.py``).

Stable ids (``ddd-daily-audit``, ``ddd-daily-listing``, ``ddd-daily-leads``): re-running never
duplicates — existing records are left untouched. The registry lives at
``~/.levi/automations/automations.json`` (runtime data, not git).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "core"))

from levi.daemon.automation import (  # noqa: E402
    Automation,
    AutomationAction,
    AutomationRegistry,
    AutomationStatus,
    TriggerKind,
)

__all__ = ["AUTOMATION_SPECS", "register_all", "main"]

#: The three daemon automation specs. Draft-only by construction.
AUTOMATION_SPECS = [
    {
        "id": "ddd-daily-audit",
        "name": "DDD daily audit daemon (provisional)",
        "description": (
            "3x daily (08:00/13:00/18:00 America/Chicago): up to 3 info-only site audits from Chauncey's "
            "prospect queue → $49 AuditNow audit drafts + outreach drafts in "
            "~/workspace/ddd-inbox/. Draft only — nothing sent, published, "
            "or charged."
        ),
        "trigger": TriggerKind.SCHEDULE,
        "trigger_config": {
            "cron_job_id": "ddd-daily-audit",
            "schedule": "3x daily 08:00/13:00/18:00 America/Chicago",
        },
        "actions": [
            AutomationAction(skill_id="ddd.daily-audit", args={}, risk_level=0)
        ],
        "status": AutomationStatus.ACTIVE,
        "risk_ceiling": 0,
        "tags": ["ddd", "daily-daemon", "draft-only"],
    },
    {
        "id": "ddd-daily-listing",
        "name": "DDD daily listing daemon (provisional)",
        "description": (
            "3x daily (08:00/13:00/18:00 America/Chicago): resale inventory rows → marketplace listing "
            "drafts + pricing guidance in ~/workspace/ddd-inbox/. Draft "
            "only — nothing posted."
        ),
        "trigger": TriggerKind.SCHEDULE,
        "trigger_config": {
            "cron_job_id": "ddd-daily-listing",
            "schedule": "3x daily 08:00/13:00/18:00 America/Chicago",
        },
        "actions": [
            AutomationAction(skill_id="ddd.daily-listing", args={}, risk_level=0)
        ],
        "status": AutomationStatus.ACTIVE,
        "risk_ceiling": 0,
        "tags": ["ddd", "daily-daemon", "draft-only"],
    },
    {
        "id": "ddd-daily-leads",
        "name": "DDD daily leads daemon (provisional)",
        "description": (
            "3x daily (08:00/13:00/18:00 America/Chicago): lead queue rows → DRAFT-labeled review-reply "
            "drafts (never posted — hard rule) + lead-gen pitch drafts in "
            "~/workspace/ddd-inbox/. Contacts nobody."
        ),
        "trigger": TriggerKind.SCHEDULE,
        "trigger_config": {
            "cron_job_id": "ddd-daily-leads",
            "schedule": "3x daily 08:00/13:00/18:00 America/Chicago",
        },
        "actions": [
            AutomationAction(skill_id="ddd.daily-leads", args={}, risk_level=0)
        ],
        "status": AutomationStatus.ACTIVE,
        "risk_ceiling": 0,
        "tags": ["ddd", "daily-daemon", "draft-only"],
    },
]


def register_all(data_dir: Path | None = None) -> list[str]:
    """Register missing daemon automations. Returns ids newly created."""
    reg = AutomationRegistry(data_dir=data_dir) if data_dir else AutomationRegistry()
    created: list[str] = []
    for spec in AUTOMATION_SPECS:
        if spec["id"] in reg._autos:
            continue
        reg._autos[spec["id"]] = Automation(
            id=spec["id"],
            name=spec["name"],
            description=spec["description"],
            trigger=spec["trigger"],
            trigger_config=spec["trigger_config"],
            actions=spec["actions"],
            status=spec["status"],
            risk_ceiling=spec["risk_ceiling"],
            tags=spec["tags"],
        )
        created.append(spec["id"])
    reg._persist()
    return created


def main() -> int:
    created = register_all()
    if created:
        print("registered: " + ", ".join(created))
    else:
        print("already registered — nothing new")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
