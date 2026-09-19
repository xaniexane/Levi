"""Workload router — supervised work for graduated trainees only.

Rules, enforced in code:
  * only trainees with status ``graduated`` receive work;
  * only registered task templates run — anything else is refused with
    an explicit reason (money, apply, shell, network are named);
  * every result is verified before acceptance;
  * a failed verification composts back into the trainee's journal and
    training loop; 3 consecutive failures demote the trainee to
    ``training`` — it must re-pass the exam to graduate again.
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from typing import Any

from levi.growth import journal as _journal

from levi.nursery import tasks as _tasks
from levi.nursery.trainee import get_trainee, nursery_home, update_trainee
from levi.nursery.training import trainee_env

MAX_CONSECUTIVE_FAILURES = 3


class Refusal(Exception):
    """The router refused the assignment — with the reason, not a traceback."""


class VerificationFailure(Exception):
    """The task ran but verification failed — composted, not accepted."""


def _ledger_path() -> Path:
    return nursery_home() / "ledger.jsonl"


def _append_ledger(record: dict[str, Any]) -> dict[str, Any]:
    record = dict(record)
    record.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    with open(_ledger_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def read_ledger(trainee_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    try:
        lines = _ledger_path().read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict) and (trainee_id is None or rec.get("trainee_id") == trainee_id):
            out.append(rec)
    return out[-limit:]


def _journal_work(trainee_id: str, entry: dict[str, Any]) -> None:
    with trainee_env(trainee_id):
        _journal.append_entry(dict(entry, kind="nursery-work", trainee_id=trainee_id))


def execute_task(task_kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Run a template and verify the result. Returns the verified result.

    Raises Refusal for unknown/forbidden kinds, VerificationFailure when
    the verifier rejects the output.
    """
    reason = _tasks.refusal_reason(task_kind)
    if reason is not None:
        raise Refusal(reason)
    name, _desc, executor, verifier = _tasks.TASKS[task_kind]
    if not isinstance(payload, dict):
        raise Refusal("task payload must be a dict")
    with tempfile.TemporaryDirectory(prefix="nursery-task-") as workdir:
        # Templates are pure functions of the payload; the workdir exists
        # so future templates have a sandbox to write in.
        try:
            result = executor(dict(payload))
        except Exception as exc:
            raise VerificationFailure("executor raised: %s" % exc) from exc
        ok, detail = verifier(result, payload)
        if not ok:
            raise VerificationFailure("verifier rejected: %s" % detail)
    return {"task_kind": name, "result": result, "verified": True, "detail": detail}


def assign(trainee_id: str, task_kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Assign supervised work to a graduated trainee. Returns a receipt.

    Refusals and verification failures are receipts, not silent drops:
    failures compost into the trainee's journal, and repeated failures
    demote the trainee back to training.
    """
    trainee = get_trainee(trainee_id)
    if trainee.status != "graduated":
        raise Refusal(
            "trainee %r is %r — only graduated trainees receive workload"
            % (trainee_id, trainee.status)
        )
    try:
        executed = execute_task(task_kind, payload)
    except (Refusal, VerificationFailure) as exc:
        trainee.consecutive_failures += 1
        demoted = trainee.consecutive_failures >= MAX_CONSECUTIVE_FAILURES
        if demoted:
            trainee.status = "training"
            trainee.consecutive_failures = 0
        update_trainee(trainee)
        _journal_work(
            trainee_id,
            {
                "event": "task_failed",
                "task_kind": task_kind,
                "error": "%s: %s" % (type(exc).__name__, exc),
                "demoted": demoted,
                "note": "composted back into training — failure is material, not shame",
            },
        )
        receipt = _append_ledger(
            {
                "trainee_id": trainee_id,
                "task_kind": task_kind,
                "accepted": False,
                "error": "%s: %s" % (type(exc).__name__, exc),
                "demoted": demoted,
            }
        )
        if demoted:
            raise VerificationFailure(
                "trainee %r demoted to training after %d consecutive failures: %s"
                % (trainee_id, MAX_CONSECUTIVE_FAILURES, exc)
            ) from exc
        raise
    trainee.consecutive_failures = 0
    update_trainee(trainee)
    _journal_work(
        trainee_id,
        {
            "event": "task_accepted",
            "task_kind": task_kind,
            "detail": executed["detail"],
        },
    )
    receipt = _append_ledger(
        {
            "trainee_id": trainee_id,
            "task_kind": task_kind,
            "accepted": True,
            "detail": executed["detail"],
        }
    )
    receipt["verified_result"] = executed["result"]
    return receipt
