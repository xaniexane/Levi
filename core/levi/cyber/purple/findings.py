"""Findings pipeline: emulate -> detect -> harden, closed loop.

Every emulated technique produces >= 1 Finding. Each finding maps to a
real blue-team playbook id from the cyber manifest. Unknown playbook ids
fail closed (the run errors rather than emitting a dangling finding).
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


class UnknownPlaybook(Exception):
    """Raised when a finding references a playbook id not in the manifest."""


def _manifest_path() -> Path:
    here = Path(__file__).resolve()
    # core/levi/cyber/purple/findings.py -> core/levi/skill/playbooks/cyber/
    return here.parents[2] / "skill" / "playbooks" / "cyber" / "cyber_index.jsonl.gz"


@lru_cache(maxsize=1)
def load_playbook_index() -> dict[str, str]:
    """skill_id -> playbook name for the whole cyber manifest. Cached."""
    index: dict[str, str] = {}
    with gzip.open(_manifest_path(), "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if "skill_id" not in record:
                continue  # header line: {manifest, count, built_at}
            index[record["skill_id"]] = record["name"]
    return index


@lru_cache(maxsize=1)
def load_playbook_ids() -> frozenset[str]:
    """All skill_ids in the cyber playbook manifest. Cached per process."""
    return frozenset(load_playbook_index())


@dataclass(frozen=True)
class Finding:
    """One defensive finding from an emulated technique.

    detected: True when the expected defensive signal was present in the
        synthetic telemetry (the blue team's detection fired); False when
        the signal was missing (a miss — hardening is then urgent).
    playbook_id: the blue-team playbook that hardens against this
        technique. Guaranteed present in the manifest.
    recommendation: human-readable next step naming the playbook.
    """

    finding_id: str
    exercise_id: str
    technique_id: str
    phase: str
    detected: bool
    playbook_id: str
    recommendation: str


def build_finding(
    *,
    exercise_id: str,
    technique_id: str,
    phase: str,
    detected: bool,
    playbook_id: str,
    playbook_name: str,
    playbook_ids: frozenset[str] | None = None,
) -> Finding:
    """Build one finding, failing closed on unknown playbook ids."""
    known = playbook_ids if playbook_ids is not None else load_playbook_ids()
    if playbook_id not in known:
        raise UnknownPlaybook(f"playbook id not in manifest: {playbook_id!r}")
    state = "DETECTED" if detected else "MISSED"
    return Finding(
        finding_id=f"{exercise_id}:{technique_id}",
        exercise_id=exercise_id,
        technique_id=technique_id,
        phase=phase,
        detected=detected,
        playbook_id=playbook_id,
        recommendation=(
            f"[{state}] {technique_id} ({phase}): apply blue-team playbook "
            f"{playbook_id} ({playbook_name}) to harden."
        ),
    )


def build_findings(
    *,
    exercise_id: str,
    detections: list[tuple[str, str, bool, str, str]],
    playbook_ids: frozenset[str] | None = None,
) -> tuple[Finding, ...]:
    """Build findings for a run.

    detections: list of (technique_id, phase, detected, playbook_id,
    playbook_name). One finding per technique — the closed loop.
    """
    return tuple(
        build_finding(
            exercise_id=exercise_id,
            technique_id=technique_id,
            phase=phase,
            detected=detected,
            playbook_id=playbook_id,
            playbook_name=playbook_name,
            playbook_ids=playbook_ids,
        )
        for technique_id, phase, detected, playbook_id, playbook_name in detections
    )
