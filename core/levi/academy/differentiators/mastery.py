"""Corroboration-gated mastery — one lucky pass never graduates.

A skill counts as learned only after the learner demonstrates it in
``REQUIRED_CONTEXTS`` distinct contexts (e.g. "lab-sim", "written",
"live-fire"), each passed. Growth-loop lineage: learnings corroborate
rather than repeat. A repeat demonstration in the same context
overwrites the earlier one — the latest evidence wins.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.academy.differentiators import _seal

REQUIRED_CONTEXTS = 3


def _mastery_dir(learner_id: str, home: Optional[Path] = None) -> Path:
    d = _seal.pkg_dir(home) / "mastery" / learner_id
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


def _path(learner_id: str, skill_id: str, home: Optional[Path] = None) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in skill_id)
    return _mastery_dir(learner_id, home) / f"{safe}.json"


def record_demonstration(
    learner_id: str,
    skill_id: str,
    context_id: str,
    passed: bool,
    home: Optional[Path] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Record one demonstration of a skill in a context."""
    for field, value in (("learner_id", learner_id), ("skill_id", skill_id),
                         ("context_id", context_id)):
        if not value or not value.strip():
            raise ValueError(f"{field} must be non-empty")
    p = _path(learner_id, skill_id, home)
    record = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {
        "learner_id": learner_id, "skill_id": skill_id, "contexts": {}}
    record["contexts"][context_id] = {"passed": bool(passed), "ts": _utcnow(now)}
    _write_json(p, record)
    return mastery_status(learner_id, skill_id, home)


def mastery_status(learner_id: str, skill_id: str,
                   home: Optional[Path] = None) -> Dict[str, Any]:
    """Mastery verdict: 3 distinct passed contexts, or not yet."""
    p = _path(learner_id, skill_id, home)
    contexts = json.loads(p.read_text(encoding="utf-8"))["contexts"] if p.exists() else {}
    passed_contexts = sorted(c for c, r in contexts.items() if r["passed"])
    mastered = len(passed_contexts) >= REQUIRED_CONTEXTS
    return {
        "learner_id": learner_id,
        "skill_id": skill_id,
        "mastered": mastered,
        "distinct_passed_contexts": len(passed_contexts),
        "required_contexts": REQUIRED_CONTEXTS,
        "passed_contexts": passed_contexts,
        "all_contexts": {c: r["passed"] for c, r in sorted(contexts.items())},
    }
