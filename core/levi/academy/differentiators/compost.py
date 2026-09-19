"""Failure compost — flunked exercises become remediation drills.

REIM lineage: failure is material, not shame. When an exercise fails
rubric checks, :func:`compost_failure` generates a targeted
remediation drill from exactly the checks that were missed — one
drill item per missed check, deterministically templated from the
check name and hint. The learner works the drill; :func:`complete_drill`
records the outcome.

Honest limit: drill prompts are template-generated from the rubric,
not AI-crafted pedagogy. The targeting is exact; the prose is plain.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.academy.differentiators import _seal


def _compost_dir(learner_id: str, home: Optional[Path] = None) -> Path:
    d = _seal.pkg_dir(home) / "compost" / learner_id
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    return d


def _write_json(path: Path, record: Dict[str, Any]) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _utcnow(now: Optional[float] = None) -> str:
    ts = now if now is not None else time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def _drill_prompt(check_name: str, hint: str) -> str:
    return (
        f"Targeted remediation for '{check_name}'. {hint} "
        "Re-demonstrate the skill with a fresh example, then state the "
        "underlying rule in your own words. The drill passes when the "
        "same check would pass on new material."
    )


def compost_failure(
    learner_id: str,
    module_id: str,
    exercise_id: str,
    failed_checks: List[Dict[str, str]],
    home: Optional[Path] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Compost a failed exercise into a remediation drill.

    ``failed_checks``: [{"name": str, "hint": str}, ...] — must be non-empty.
    """
    for field, value in (("learner_id", learner_id), ("module_id", module_id),
                         ("exercise_id", exercise_id)):
        if not value or not value.strip():
            raise ValueError(f"{field} must be non-empty")
    if not failed_checks or not isinstance(failed_checks, list):
        raise ValueError("failed_checks must be a non-empty list")
    items = []
    for i, fc in enumerate(failed_checks):
        if not isinstance(fc, dict) or "name" not in fc:
            raise ValueError(f"failed_checks[{i}] needs a 'name'")
        name = str(fc["name"])
        hint = str(fc.get("hint", "Review the lesson material for this check."))
        items.append({
            "check": name,
            "focus": hint,
            "prompt": _drill_prompt(name, hint),
            "status": "open",
        })
    drill_id = uuid.uuid4().hex[:12]
    drill = {
        "drill_id": drill_id,
        "learner_id": learner_id,
        "module_id": module_id,
        "exercise_id": exercise_id,
        "status": "assigned",
        "items": items,
        "composted_at": _utcnow(now),
        "completed_at": "",
    }
    _write_json(_compost_dir(learner_id, home) / f"{drill_id}.json", drill)
    return {"drill_id": drill_id, "learner_id": learner_id, "status": "assigned",
            "targets": [i["check"] for i in items]}


def _load(learner_id: str, drill_id: str, home: Optional[Path] = None) -> Dict[str, Any]:
    path = _compost_dir(learner_id, home) / f"{drill_id}.json"
    if not path.exists():
        raise KeyError(f"unknown drill {drill_id!r} for learner {learner_id!r}")
    return json.loads(path.read_text(encoding="utf-8"))


def complete_drill(
    learner_id: str,
    drill_id: str,
    results: Dict[str, bool],
    home: Optional[Path] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Record drill outcomes. ``results`` maps check name -> passed."""
    drill = _load(learner_id, drill_id, home)
    if drill["status"] not in ("assigned", "partial"):
        raise ValueError(f"drill {drill_id!r} is {drill['status']!r}, not completable")
    passed = 0
    for item in drill["items"]:
        if item["check"] in results:
            ok = bool(results[item["check"]])
            item["status"] = "passed" if ok else "open"
        if item["status"] == "passed":
            passed += 1
    total = len(drill["items"])
    drill["status"] = "completed" if passed == total else "partial"
    if drill["status"] == "completed":
        drill["completed_at"] = _utcnow(now)
    _write_json(_compost_dir(learner_id, home) / f"{drill_id}.json", drill)
    return {"drill_id": drill_id, "status": drill["status"],
            "passed": passed, "total": total}


def list_drills(learner_id: str, home: Optional[Path] = None,
                status: Optional[str] = None) -> List[Dict[str, Any]]:
    out = []
    for path in sorted(_compost_dir(learner_id, home).glob("*.json")):
        drill = json.loads(path.read_text(encoding="utf-8"))
        if status is None or drill["status"] == status:
            out.append(drill)
    return out
