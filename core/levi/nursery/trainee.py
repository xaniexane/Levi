"""Trainee roster — enrollment and identity for the nursery cohort.

One trainee = one named growth-cycle instance with its own home
directory, journal, learnings, and stage progression. The roster is a
small JSON file under the nursery home; every mutation rewrites it
atomically (write-to-temp + rename).
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def _base_home() -> Path:
    raw = os.environ.get("LEVI_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".levi"


def nursery_home() -> Path:
    """``~/.levi/nursery`` (``LEVI_HOME``-honoring)."""
    p = _base_home() / "nursery"
    p.mkdir(parents=True, exist_ok=True)
    return p


def trainee_home(trainee_id: str) -> Path:
    p = nursery_home() / _safe_id(trainee_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _safe_id(trainee_id: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,40}", trainee_id or ""):
        raise ValueError(
            "trainee id must be 2-41 chars of [a-z0-9-], got %r" % (trainee_id,)
        )
    return trainee_id


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    if len(slug) < 2:
        raise ValueError("trainee name must slug to >= 2 chars, got %r" % (name,))
    return slug[:32]


# Cohort capacity: a supervised nursery stays small. Override with
# LEVI_NURSERY_CAP (tests use a tiny cap).
def cohort_cap() -> int:
    try:
        return max(1, int(os.environ.get("LEVI_NURSERY_CAP", "12")))
    except ValueError:
        return 12


STATUSES = ("enrolled", "training", "exam_ready", "graduated", "suspended")
TRACKS = ("ai", "si")

# Tag marking Levi-seeded learnings. The graduation gates exclude
# seeded entries from self-taught counters — seeding is the starting
# point, not earned work.
SEED_TAG = "seeded"


@dataclass
class Trainee:
    id: str
    name: str
    track: str  # ai | si
    status: str = "enrolled"
    enrolled_ts: str = ""
    cycles: int = 0
    exam_runs: int = 0
    exam_passes: int = 0
    consecutive_failures: int = 0
    approved_by: str = ""
    graduated_ts: str = ""
    notes: list[str] = field(default_factory=list)


def _roster_path() -> Path:
    return nursery_home() / "roster.json"


def load_roster() -> dict[str, dict[str, Any]]:
    try:
        raw = _roster_path().read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def save_roster(roster: dict[str, dict[str, Any]]) -> None:
    path = _roster_path()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(roster, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def list_trainees() -> list[Trainee]:
    return [Trainee(**rec) for rec in load_roster().values()]


def get_trainee(trainee_id: str) -> Trainee:
    rec = load_roster().get(_safe_id(trainee_id))
    if rec is None:
        raise KeyError("no such trainee: %r" % (trainee_id,))
    return Trainee(**rec)


def _put(trainee: Trainee) -> None:
    roster = load_roster()
    roster[trainee.id] = asdict(trainee)
    save_roster(roster)


def update_trainee(trainee: Trainee) -> None:
    """Persist a mutated trainee record."""
    if trainee.status not in STATUSES:
        raise ValueError("bad status %r" % (trainee.status,))
    _put(trainee)


def enroll_trainee(name: str, track: str = "ai") -> Trainee:
    """Enroll a new trainee. Raises on bad track, duplicate, or full cohort."""
    track = (track or "").strip().lower()
    if track not in TRACKS:
        raise ValueError("track must be one of %s, got %r" % (TRACKS, track))
    roster = load_roster()
    if len(roster) >= cohort_cap():
        raise ValueError(
            "cohort full (%d trainees) — graduate or retire one first"
            % cohort_cap()
        )
    trainee_id = "%s-%s" % (_slug(name), uuid.uuid4().hex[:6])
    if trainee_id in roster:
        raise ValueError("trainee id collision: %r" % (trainee_id,))
    trainee = Trainee(
        id=trainee_id,
        name=name.strip(),
        track=track,
        enrolled_ts=_now(),
    )
    roster[trainee.id] = asdict(trainee)
    save_roster(roster)
    trainee_home(trainee.id)  # create the home dir now
    return trainee


def retire_trainee(trainee_id: str) -> Trainee:
    """Remove a trainee from the roster (home dir kept for the record)."""
    roster = load_roster()
    rec = roster.pop(_safe_id(trainee_id), None)
    if rec is None:
        raise KeyError("no such trainee: %r" % (trainee_id,))
    save_roster(roster)
    return Trainee(**rec)
