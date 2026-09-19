"""Live-fire finals — the final module is supervised real work.

No multiple choice. The learner is assigned a real task from the
nursery workload router's verified templates
(:mod:`levi.nursery.router` — the same templates graduated trainees
run in production). The task executes, the verifier judges, and only
a verified result passes the final. A pass mints a sealed skill
receipt (module ``live-fire-final``); a failure is recorded with the
verifier's reason — compost material, not a silent drop.

Nursery boundaries hold: only registered templates run; money,
applications, shell, and network kinds are refused by the router.
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
from levi.academy.differentiators import receipts as _receipts

LIVE_FIRE_TASK = "sort_lines"
MODULE_ID = "live-fire-final"


def _finals_dir(learner_id: str, home: Optional[Path] = None) -> Path:
    d = _seal.pkg_dir(home) / "livefire" / learner_id
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


def assign_live_fire(learner_id: str, home: Optional[Path] = None,
                     now: Optional[float] = None) -> Dict[str, Any]:
    """Assign the live-fire final: a supervised nursery-router task."""
    if not learner_id or not learner_id.strip():
        raise ValueError("learner_id must be non-empty")
    final_id = uuid.uuid4().hex[:12]
    record = {
        "final_id": final_id,
        "learner_id": learner_id,
        "task_kind": LIVE_FIRE_TASK,
        "status": "assigned",
        "payload_shape": "{'lines': ['...', ...]} — a list of strings to sort",
        "assigned_at": _utcnow(now),
        "ran_at": "",
        "error": "",
        "receipt_id": "",
    }
    _write_json(_finals_dir(learner_id, home) / f"{final_id}.json", record)
    return {"final_id": final_id, "learner_id": learner_id,
            "task_kind": LIVE_FIRE_TASK, "status": "assigned",
            "payload_shape": record["payload_shape"]}


def _load(learner_id: str, final_id: str, home: Optional[Path] = None) -> Dict[str, Any]:
    path = _finals_dir(learner_id, home) / f"{final_id}.json"
    if not path.exists():
        raise KeyError(f"unknown final {final_id!r} for learner {learner_id!r}")
    return json.loads(path.read_text(encoding="utf-8"))


def run_live_fire(learner_id: str, final_id: str, payload: Dict[str, Any],
                  home: Optional[Path] = None,
                  now: Optional[float] = None) -> Dict[str, Any]:
    """Run the final through the nursery workload router, supervised.

    Returns the final record — never raises on task failure. A verified
    result passes and mints a sealed receipt; a refusal or verification
    failure is recorded with the reason.
    """
    from levi.nursery.router import Refusal, VerificationFailure, execute_task

    record = _load(learner_id, final_id, home)
    if record["status"] != "assigned":
        raise ValueError(f"final {final_id!r} is {record['status']!r}, not runnable")
    try:
        executed = execute_task(record["task_kind"], payload)
    except (Refusal, VerificationFailure) as exc:
        record["status"] = "failed"
        record["ran_at"] = _utcnow(now)
        record["error"] = f"{type(exc).__name__}: {exc}"
        _write_json(_finals_dir(learner_id, home) / f"{final_id}.json", record)
        return {"final_id": final_id, "learner_id": learner_id,
                "status": "failed", "error": record["error"]}
    record["status"] = "passed"
    record["ran_at"] = _utcnow(now)
    record["detail"] = executed.get("detail", "")
    receipt = _receipts.mint_receipt(
        learner_id, MODULE_ID, 1.0,
        [{"name": f"verified {record['task_kind']}", "passed": True}],
        home=home, now=now)
    record["receipt_id"] = receipt["receipt_id"]
    _write_json(_finals_dir(learner_id, home) / f"{final_id}.json", record)
    return {"final_id": final_id, "learner_id": learner_id, "status": "passed",
            "detail": record["detail"], "receipt_id": receipt["receipt_id"]}
