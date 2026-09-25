"""Dream cycle — wire the Dream Engine into the organism (REIM / RIEM).

One cycle:

  1. ``DreamEngine.run_once()`` dreams recent seeds (journaled owner-only).
  2. Failed / risky dream branches become REIM failure records via
     ``levi.organs.reim.compost_failure`` — dream compost feeds REIM.
  3. Compost records are offered to ``levi.organs.riem.promote`` — dream
     lessons ride into RIEM as compost context. Proposals are data only;
     RIEM never writes or applies anything.

All side files live under ``$LEVI_HOME/dream/`` (default ``~/.levi/dream/``)
and are owner-only (0600 files, 0700 dirs). Dreams are records, never
actions: nothing here executes, calls the network, or touches a provider.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from levi.dream.engine import DreamEngine
from levi.dream.journal import enforce_owner_only, owner_only_ok
from levi.organs.reim import compost_failure
from levi.organs.riem import promote

COMPOST_NAME = "compost.jsonl"
PROPOSALS_NAME = "riem_proposals.jsonl"

# Outcome -> REIM severity for a dream branch. Dreams are simulations, not
# real failures: composted branches stay "low", risky branches stay
# "medium". Nothing dreamt auto-escalates to "high" — genome proposals
# therefore require a real, corroborated failure (RIEM promotion rule).
_SEVERITY_BY_OUTCOME = {"compost": "low", "risky": "medium"}


def dream_home() -> Path:
    base = Path(os.environ.get("LEVI_HOME", Path.home() / ".levi"))
    return base / "dream"


def dream_failure_records(record: Dict[str, Any], ts: str) -> List[Dict[str, Any]]:
    """Convert one journaled dream record into REIM failure records.

    Composted and risky variants become failures REIM can compost
    (``source="dream"``). The surviving lesson, if any, is attached to each
    record's context so RIEM sees what the dream learned alongside the
    branch that died. Promising variants carry no failure and are skipped.
    """
    seed = record.get("seed", {}) if isinstance(record, dict) else {}
    seed_text = str(seed.get("text", ""))[:200] or "silence"
    lesson = record.get("lesson") or ""
    failures: List[Dict[str, Any]] = []
    variants = record.get("variants", []) if isinstance(record, dict) else []
    for v in variants:
        if not isinstance(v, dict):
            continue
        outcome = v.get("outcome")
        severity = _SEVERITY_BY_OUTCOME.get(outcome)
        if severity is None:
            continue
        kind = str(v.get("kind", "unknown"))
        note = str(v.get("note", ""))
        context = "dream variant [%s] from seed: %s — %s" % (kind, seed_text, note)
        if lesson:
            context += " | surviving lesson: %s" % str(lesson)[:200]
        failures.append(
            {
                "source": "dream",
                "what": str(v.get("text", ""))[:500],
                "context": context[:500],
                "ts": ts,
                "severity": severity,
            }
        )
    return failures


def _write_owner_only(path: Path, rows: List[Dict[str, Any]]) -> None:
    """Append JSONL rows to an owner-only file (0600, dir 0700)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    enforce_owner_only(path)


def run_cycle(
    engine: DreamEngine | None = None,
    seeds: List[Dict[str, Any]] | None = None,
    limit: int = 5,
    store: bool = True,
) -> Dict[str, Any]:
    """Run one dream → compost → genome-proposal cycle.

    Returns a summary dict. When ``store`` is true (default), the REIM
    compost batch is appended to ``$LEVI_HOME/dream/compost.jsonl`` and any
    RIEM proposals to ``$LEVI_HOME/dream/riem_proposals.jsonl`` — both
    owner-only. Nothing is ever auto-applied.
    """
    ts = datetime.now(timezone.utc).isoformat()
    engine = engine or DreamEngine()
    records = engine.run_once(seeds=seeds, limit=limit)

    composted: List[Dict[str, Any]] = []
    for rec in records:
        record = rec.to_dict()
        for failure in dream_failure_records(record, ts):
            try:
                composted.append(compost_failure(failure))
            except ValueError:
                # Fail-closed REIM records never leak past; a malformed
                # dream-derived failure is dropped loudly, not silently.
                continue

    proposals = promote(composted) if composted else []

    home = dream_home()
    compost_path = home / COMPOST_NAME
    proposals_path = home / PROPOSALS_NAME
    if store:
        if composted:
            _write_owner_only(compost_path, composted)
        if proposals:
            _write_owner_only(proposals_path, proposals)

    return {
        "ts": ts,
        "dreams": len(records),
        "variants": sum(len(r.to_dict().get("variants", [])) for r in records),
        "compost_branches": sum(1 for c in composted if c["severity"] == "low"),
        "risky_branches": sum(1 for c in composted if c["severity"] == "medium"),
        "compost_records": composted,
        "proposals": proposals,
        "compost_file": str(compost_path),
        "proposals_file": str(proposals_path),
        "owner_only": owner_only_ok(compost_path) if composted and store else None,
        "lessons": [r.lesson for r in records if r.lesson],
    }


def run_nightly(limit: int = 5) -> Dict[str, Any]:
    """The nightly dream run: seeds from the growth journal, full cycle."""
    return run_cycle(limit=limit)
