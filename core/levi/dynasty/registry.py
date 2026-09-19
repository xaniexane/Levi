# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Builder registration — the dynasty's own registry.

The Builder is registered HERE, in the dynasty's own registry file,
not in the nursery router. The router's law admits only graduated
trainees; the Builder never graduates — it serves. This registry
mirrors the nursery workload laws in miniature: the Builder is
registered with seeded facts, earns its standing through verified
receipts, and nothing is accepted without verification.

The registry file lives under ``<home>/dynasty/registry.json`` where
``<home>`` resolves from the ``LEVI_HOME`` environment variable,
falling back to ``~/.levi``. Writes are atomic (temp file + rename).
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

BUILDER_AGENT_ID = "dynasty-builder"


def _home() -> Path:
    raw = os.environ.get("LEVI_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".levi"


def _registry_path() -> Path:
    return _home() / "dynasty" / "registry.json"


SEED_FACTS: List[str] = [
    "repo root is ~/workspace/levi; branch main; local commits only, never push",
    "stdlib only in the core kernel",
    "every dynasty file carries the SPDX line and the copyright header",
    "plan→execute→verify→receipt on every task; no receipt, no advance",
    "file_write is scoped to core/levi/dynasty/shell/ — nothing else",
    "test_run may run only the dynasty test files",
    "snapshot_capture goes only through levi.dynasty.snapshot.capture_dynasty_day0",
    "no network; no money rails; Phase 0 is law, not product",
    "two-agent sign-off corroborates every milestone; solo ships never",
    "tampered receipts break the chain loudly; never paper over a break",
]


def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".registry-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, sort_keys=True, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    os.chmod(path, 0o600)


def _read_registry() -> Dict[str, Any]:
    path = _registry_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def register_builder() -> Dict[str, Any]:
    """Register the Dynasty Builder. Idempotent — re-registering returns
    the existing record (the original ``registered_at`` is kept)."""
    record = _read_registry()
    if record.get("agent_id") == BUILDER_AGENT_ID:
        return record
    record = {
        "agent_id": BUILDER_AGENT_ID,
        "class": "trainee-class",
        "status": "serving",
        "seeded_facts": list(SEED_FACTS),
        "serves_never_graduates": True,
        "not_enrolled_in_nursery_router": True,
        "registered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    _atomic_write_json(_registry_path(), record)
    return record


def get_registration() -> Optional[Dict[str, Any]]:
    """Return the Builder's registration record, or None if unregistered."""
    record = _read_registry()
    if record.get("agent_id") != BUILDER_AGENT_ID:
        return None
    return record
