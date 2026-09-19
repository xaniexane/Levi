"""Team learning loop — stdlib only.

Field work by a team feeds validated entries back into the corpus through
the same mechanical growth pipeline, so crews get smarter together:

* ``harvest(team_id, entries)`` — a team submits candidate field learnings
  (list of entry dicts). They are validated and appended to the team's
  intake queue. Nothing touches the corpus.
* ``review_intake(team_id)`` — dry-run report over the intake queue:
  valid / invalid / duplicates vs the live corpus. Nothing is written.
* ``promote_intake(team_id)`` — valid, deduped entries are appended to the
  corpus shards; invalid lines stay in the intake queue for fixing.

No unreviewed writes: only entries that pass schema validation (including
the crisis-domain law) are ever appended, and ``promote`` is an explicit
step — ``harvest`` and ``review`` never modify the corpus.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.sidewinder.curriculum import growth
from levi.sidewinder.curriculum.schema import validate_entry

MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_INTAKE_DIR = MODULE_DIR / "field_intake"


def _intake_path(team_id: str, intake_dir: Optional[Path] = None) -> Path:
    base = intake_dir or DEFAULT_INTAKE_DIR
    return base / f"{team_id}.jsonl"


def harvest(
    team_id: str, entries: List[Dict[str, Any]], intake_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """Validate candidate entries and queue them for the team. Returns
    ``{team, received, valid, invalid, errors}``. Corpus untouched."""
    path = _intake_path(team_id, intake_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    valid = 0
    errors: List[str] = []
    with path.open("a", encoding="utf-8") as fh:
        for entry in entries:
            problems = validate_entry(entry)
            if problems:
                title = entry.get("title") if isinstance(entry, dict) else "?"
                errors.append(f"invalid {title!r}: {'; '.join(problems)}")
            else:
                valid += 1
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return {
        "team": team_id,
        "received": len(entries),
        "valid": valid,
        "invalid": len(entries) - valid,
        "errors": errors,
        "intake": str(path),
    }


def review_intake(
    team_id: str,
    intake_dir: Optional[Path] = None,
    corpus_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Dry-run the team's intake queue against the live corpus. Read-only."""
    report = growth.grow(
        seeds_path=_intake_path(team_id, intake_dir),
        corpus_dir=corpus_dir,
        dry_run=True,
        consume=False,
    )
    report["team"] = team_id
    return report


def promote_intake(
    team_id: str,
    intake_dir: Optional[Path] = None,
    corpus_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Append the team's validated, deduped entries to the corpus.

    Entries are stamped with provenance (``{"team": ..., "promoted": date}``)
    before promotion; invalid lines stay in the intake queue for fixing.
    """
    path = _intake_path(team_id, intake_dir)
    if path.is_file():
        stamped: List[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                stamped.append(line)
                continue
            if isinstance(obj, dict):
                prov = obj.setdefault("provenance", {})
                if isinstance(prov, dict):
                    prov.setdefault("team", team_id)
                    prov.setdefault("promoted", datetime.now(timezone.utc).date().isoformat())
            stamped.append(json.dumps(obj, ensure_ascii=False))
        path.write_text("\n".join(stamped) + ("\n" if stamped else ""), encoding="utf-8")
    report = growth.grow(seeds_path=path, corpus_dir=corpus_dir, consume=True)
    report["team"] = team_id
    return report
