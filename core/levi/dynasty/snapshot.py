# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Day-0 snapshot — the dynasty's sealed starting line.

Captures the state of the repo and its docs at dynasty day 0 using the
REAL stage-snapshot engine (:mod:`levi.snapshots.stages`): content-
addressed, hash-chained, sealed at rest with the keeper key. Later
phases diff against this snapshot to prove what changed.

The payload carries the git head (or ``"unknown"`` when git is
unavailable — it must never crash), the branch, and SHA-256 digests
of every ``.md`` doc under the given docs directory. The snapshot
helper is the ONLY snapshot path the Dynasty Builder may use.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Union

from levi.snapshots.stages import StageSnapshot, StageStore

STAGE_NAME = "dynasty-day0"


def _git_head(repo_root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "log", "-1", "--format=%H"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    head = (proc.stdout or "").strip()
    return head if head and proc.returncode == 0 else "unknown"


def _docs_hashes(docs_dir: Path) -> Dict[str, str]:
    hashes: Dict[str, str] = {}
    if not docs_dir.is_dir():
        return hashes
    for md in sorted(docs_dir.rglob("*.md")):
        if not md.is_file():
            continue
        rel = md.relative_to(docs_dir).as_posix()
        hashes[rel] = hashlib.sha256(md.read_bytes()).hexdigest()
    return hashes


def capture_dynasty_day0(
    docs_dir: Path,
    repo_root: Path,
    home: Optional[Union[str, Path]] = None,
) -> StageSnapshot:
    """Capture the dynasty day-0 stage snapshot.

    ``home`` resolves the stage-snapshot store location (honors the
    ``LEVI_HOME`` env var when None — pass a tmp home in tests).
    Returns the sealed :class:`StageSnapshot`.
    """
    payload: Dict[str, Any] = {
        "phase": "dynasty-day0",
        "repo": {"head": _git_head(repo_root), "branch": "main"},
        "docs": _docs_hashes(docs_dir),
    }
    store = StageStore(home=home)
    return store.capture_stage(
        STAGE_NAME,
        payload,
        stage_label=STAGE_NAME,
        note="Dynasty day 0 — sealed starting line for the Phase 0 playbook.",
    )
