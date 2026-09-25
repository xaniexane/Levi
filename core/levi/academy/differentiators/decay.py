"""Skill decay — unused skills rot on schedule; the academy re-tests.

Never static, never outdated, enforced in code. Every touched skill
carries a last-used timestamp; strength decays exponentially with a
30-day half-life. Skills below the retest threshold show up in
:func:`due_for_retest`. A passed retest restores full strength; a
failed retest zeroes the skill and flags it for remediation
(compost it — see :mod:`levi.academy.differentiators.compost`).
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.academy.differentiators import _seal

HALF_LIFE_DAYS = 30.0
_SECONDS_PER_DAY = 86400.0


def _decay_dir(learner_id: str, home: Optional[Path] = None) -> Path:
    d = _seal.pkg_dir(home) / "decay" / learner_id
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


def _now(now: Optional[float]) -> float:
    return now if now is not None else time.time()


def _path(learner_id: str, home: Optional[Path] = None) -> Path:
    return _decay_dir(learner_id, home) / "skills.json"


def _load(learner_id: str, home: Optional[Path] = None) -> Dict[str, Any]:
    p = _path(learner_id, home)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def touch_skill(learner_id: str, skill_id: str, home: Optional[Path] = None,
                now: Optional[float] = None) -> Dict[str, Any]:
    """Mark a skill used now — strength restored to full."""
    if not learner_id or not learner_id.strip():
        raise ValueError("learner_id must be non-empty")
    if not skill_id or not skill_id.strip():
        raise ValueError("skill_id must be non-empty")
    record = _load(learner_id, home)
    record[skill_id] = {"last_used": _now(now), "zeroed": False}
    _write_json(_path(learner_id, home), record)
    return {"learner_id": learner_id, "skill_id": skill_id, "strength": 1.0}


def skill_strength(learner_id: str, skill_id: str, home: Optional[Path] = None,
                   now: Optional[float] = None) -> float:
    """Current strength 0..1. Unknown skills score 0 — nothing to decay from."""
    record = _load(learner_id, home)
    entry = record.get(skill_id)
    if not entry or entry.get("zeroed") or entry.get("last_used") is None:
        return 0.0
    elapsed_days = (_now(now) - float(entry["last_used"])) / _SECONDS_PER_DAY
    if elapsed_days < 0:
        elapsed_days = 0.0
    return round(0.5 ** (elapsed_days / HALF_LIFE_DAYS), 3)


def due_for_retest(learner_id: str, threshold: float = 0.5,
                   home: Optional[Path] = None,
                   now: Optional[float] = None) -> List[Dict[str, Any]]:
    """Skills whose strength has decayed below threshold (or was zeroed)."""
    if not 0.0 < threshold <= 1.0:
        raise ValueError("threshold must be in (0, 1]")
    record = _load(learner_id, home)
    out = []
    for skill_id in sorted(record):
        strength = skill_strength(learner_id, skill_id, home, now)
        if strength < threshold:
            out.append({"skill_id": skill_id, "strength": strength,
                        "last_used": record[skill_id].get("last_used")})
    return out


def retest(learner_id: str, skill_id: str, passed: bool,
           home: Optional[Path] = None,
           now: Optional[float] = None) -> Dict[str, Any]:
    """Record a retest. Pass restores the skill; fail zeroes it for remediation."""
    record = _load(learner_id, home)
    if skill_id not in record:
        raise KeyError(f"unknown skill {skill_id!r} for learner {learner_id!r}")
    passed = bool(passed)
    if passed:
        record[skill_id] = {"last_used": _now(now), "zeroed": False}
        result = {"learner_id": learner_id, "skill_id": skill_id,
                  "passed": True, "strength": 1.0, "needs_remediation": False}
    else:
        record[skill_id] = {"last_used": None, "zeroed": True}
        result = {"learner_id": learner_id, "skill_id": skill_id,
                  "passed": False, "strength": 0.0, "needs_remediation": True}
    _write_json(_path(learner_id, home), record)
    return result
