"""hunt-archive-publish: the factory line end-to-end.

Chauncey's synthesis: the Megazord is an industrial complex — warehouses
(inventory) plus a FACTORY production line:
hunt intake -> archive processing -> manufacture -> warehouse stocking ->
galaxy distribution. This workflow IS that line, offline and bounded:

  intake      — take a bounded set of hunt findings (fixture-injected;
                the live hunt is network-bound, so findings are the
                offline input, never fabricated)
  process     — validate them into ArchiveRecords and write the hunt
                module's sanctioned archive ingest queue (pending files)
  stock       — stock the live archive shelves (ArchiveStore.add_many:
                skipped duplicates are counted, never overwritten)
  manufacture — queue buildable findings for the never-stops build engine
                via queue_for_build (standing auto-approval; load-bearing
                and useful-pattern ratings only; hard-route finds flagged).
                THE WAYMAKER LAW (top law): when a finding has NO existing
                build path — not queued by the standing machinery, or flagged
                by hard_route_review because every known way is cost-bearing
                — it is never a dead end. It is recorded as a waymaker job
                ({"kind": "waymaker", "finding": <id>, "note": ...}) on the
                result's waymaker_jobs list: "no existing way" is the trigger
                to manufacture one. The manufactured capability itself is NOT
                built here — the gap is named and queued, honestly.
  distribute  — publish the collection to the galaxy registry

Every step calls a real module API; failures are honest (ok=False with a
reason). If any step fails, the workflow stops there — partial runs leave
durable state only in the steps that actually completed, and the steps log
says exactly which ones.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from levi.archive.record import ArchiveRecord, make_id, slugify
from levi.archive.store import ArchiveStore
from levi.galaxy.registry import GalaxyRegistry
from levi.perpetual import hunt as _hunt

from ._common import (
    emit,
    finish_step,
    new_step,
    resolve_home,
    workflow_env,
    workflow_result,
)

NAME = "hunt-archive-publish"
SUMMARY = (
    "Factory line: intake (hunt findings) -> process (archive ingest queue) "
    "-> stock (archive shelves) -> manufacture (build queue + waymaker jobs "
    "for findings with no existing way) -> distribute (galaxy publish). "
    "Offline: pass findings=... instead of running a network hunt."
)
STEP_NAMES = ["intake", "process", "stock", "manufacture", "distribute"]


def _to_records(findings: List[Dict[str, Any]]) -> List[ArchiveRecord]:
    records = []
    for i, f in enumerate(findings):
        if not isinstance(f, dict):
            raise ValueError("finding #%d is not a dict" % i)
        data = dict(f)
        if not data.get("id"):
            data["id"] = make_id(
                data.get("kind", "software"),
                "workflow",
                data.get("title", "untitled"),
                data.get("era", ""),
                i,
            )
        records.append(ArchiveRecord(**data))
    return records


def _fail(
    steps: List[Dict[str, Any]],
    step: Dict[str, Any],
    exc: Exception,
    artifacts: Dict[str, Any],
) -> Dict[str, Any]:
    finish_step(step, False, reason="%s: %s" % (type(exc).__name__, exc))
    steps.append(step)
    emit("workflow.done", {"workflow": NAME, "ok": False})
    result = workflow_result(NAME, steps, artifacts)
    result["waymaker_jobs"] = []  # no manufacture happened on a failed run
    return result


def run(
    home=None,
    findings: Optional[List[Dict[str, Any]]] = None,
    wave_id: Optional[str] = None,
    author: str = "levi-workflows",
    **kwargs,
) -> Dict[str, Any]:
    levi_home = resolve_home(home)
    emit("workflow.start", {"workflow": NAME, "home": str(levi_home)})
    steps: List[Dict[str, Any]] = []
    artifacts: Dict[str, Any] = {}
    waymaker_jobs: List[Dict[str, Any]] = []

    # -- intake: bounded hunt findings, fixture-injected -------------------
    step = new_step("intake")
    try:
        if not findings:
            raise ValueError(
                "no findings supplied — the live hunt is network-bound; "
                "pass findings=[{...ArchiveRecord fields...}] to run offline"
            )
        records = _to_records(findings)
        wave = wave_id or (
            "wave-%s" % datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        )
        record_ids = [r.id for r in records]
        finish_step(
            step,
            True,
            {"records": len(records), "wave_id": wave, "record_ids": record_ids},
        )
        artifacts["wave_id"] = wave
        artifacts["record_ids"] = record_ids
    except Exception as exc:
        return _fail(steps, step, exc, artifacts)
    steps.append(step)

    # -- process: the hunt module's sanctioned archive ingest queue --------
    step = new_step("process")
    try:
        with workflow_env(levi_home):
            queue_path = _hunt.queue_for_archive(
                records, wave, home=str(levi_home.parent)
            )
        finish_step(step, True, {"queue": str(queue_path), "records": len(records)})
        artifacts["queue_path"] = str(queue_path)
    except Exception as exc:
        return _fail(steps, step, exc, artifacts)
    steps.append(step)

    # -- stock: shelve the records in the live archive ---------------------
    step = new_step("stock")
    try:
        with workflow_env(levi_home):
            store = ArchiveStore(home=levi_home.parent)
            counts = store.add_many(records)
        finish_step(
            step,
            True,
            {
                "added": counts.get("added", 0),
                "skipped_duplicates": counts.get("skipped", 0),
            },
        )
        artifacts["store_added"] = counts.get("added", 0)
    except Exception as exc:
        return _fail(steps, step, exc, artifacts)
    steps.append(step)

    # -- manufacture: queue buildable findings; name waymaker jobs --------
    step = new_step("manufacture")
    try:
        with workflow_env(levi_home):
            queued = _hunt.queue_for_build(records, wave, home=str(levi_home.parent))
            queued_items = _hunt.read_build_queue(home=str(levi_home.parent))
        queued_ids = {
            i.get("record_id") for i in queued_items if i.get("wave_id") == wave
        }
        hard = {f["record_id"]: f for f in _hunt.hard_route_review(records)}
        jobs: List[Dict[str, Any]] = []
        for rec in records:
            if rec.id not in queued_ids:
                # The standing machinery has no build order for this one —
                # no API, no tool, no path. Waymaker law: manufacture one.
                jobs.append(
                    {
                        "kind": "waymaker",
                        "finding": rec.id,
                        "title": rec.title,
                        "rating": rec.rating,
                        "note": "no existing way — queued to manufacture one",
                    }
                )
            elif rec.id in hard:
                # Every known way is cost-bearing; the hard-route law forbids
                # paying, so the way itself must be manufactured clean-room.
                jobs.append(
                    {
                        "kind": "waymaker",
                        "finding": rec.id,
                        "title": rec.title,
                        "rating": rec.rating,
                        "note": (
                            "no cost-bearing way allowed — manufacture a "
                            "clean-room, stdlib-only, local-first way "
                            "(hard-route)"
                        ),
                        "signals": hard[rec.id].get("signals", []),
                    }
                )
        waymaker_jobs = jobs
        finish_step(
            step,
            True,
            {
                "build_queued": queued,
                "waymaker_jobs": len(jobs),
            },
        )
        artifacts["build_queued"] = queued
        artifacts["waymaker_count"] = len(jobs)
    except Exception as exc:
        return _fail(steps, step, exc, artifacts)
    steps.append(step)

    # -- distribute: publish the collection to the galaxy registry ---------
    step = new_step("distribute")
    try:
        digest = hashlib.sha256(
            json.dumps(sorted(record_ids), sort_keys=True).encode("utf-8")
        ).hexdigest()
        pkg_id = "levi/workflows/hunt-%s" % slugify(wave, max_len=40)
        record = {
            "id": pkg_id,
            "version": "1.0.0",
            "kind": "archive-collection",
            "author": author,
            "source": "workflow:%s" % NAME,
            "description": "Hunt collection %s: %d archived finds"
            % (wave, len(record_ids)),
            "capabilities": ["archive", "search"],
            "root_sha256": digest,
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "granted": {"network": False, "fs": [], "subprocess": False},
        }
        registry = GalaxyRegistry(levi_home)
        registry.add(record)
        finish_step(step, True, {"package_id": pkg_id, "root_sha256": digest})
        artifacts["package_id"] = pkg_id
        artifacts["registry_record"] = registry.get(pkg_id)
    except Exception as exc:
        return _fail(steps, step, exc, artifacts)
    steps.append(step)

    emit(
        "workflow.done",
        {
            "workflow": NAME,
            "ok": True,
            "records": len(record_ids),
            "waymaker_jobs": len(waymaker_jobs),
        },
    )
    result = workflow_result(NAME, steps, artifacts)
    result["waymaker_jobs"] = waymaker_jobs
    return result
