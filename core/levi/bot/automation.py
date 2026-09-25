"""Automation runner for LEVI bot services.

:func:`run_service` executes a service from the registry (on demand or from
a cron job), dispatches to its handler, and appends a run record to the
JSONL run log. Agentic steps inside handlers route through the existing
agent runtime with HITL gating for consequential acts — the runner itself
never invents results.

Every run is narrated in the spark voice by :func:`narrate`: the report
first, flavor second, honest about failures.

The bot implements no scheduler of its own. Recurrence comes from the
existing cron/daemon mechanism, e.g.::

    0 7 * * * cd ~/workspace/levi && python -m levi.bot service run morning-briefing

When no scheduler is attached, ``service run`` works on demand and the
narration says so plainly.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from levi.bot.services import (
    ServiceDefinition,
    ServiceError,
    ServiceRegistry,
    ServiceResult,
    get_handler_for,
)


def _state_dir() -> str:
    override = os.environ.get("LEVI_BOT_HOME")
    if override:
        return os.path.join(override, "bot")
    return os.path.join(os.path.expanduser("~"), ".levi", "bot")


def _run_log_path() -> str:
    return os.path.join(_state_dir(), "runs.jsonl")


@dataclass
class RunRecord:
    """One executed (or rejected) service run.

    The ``planned`` / ``approved`` / ``executed`` / ``verified`` fields
    carry the Plan → Permission → Execute → Verify → Receipt rail in
    structured form: what was intended, on what authority it ran, what
    actually happened, and how the outcome was checked.
    """

    service: str
    ok: bool
    summary: str
    report: str = ""
    files: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    error: str = ""
    planned: str = ""
    approved: str = ""
    executed: str = ""
    verified: str = ""
    ts: str = ""

    def __post_init__(self) -> None:
        if not self.ts:
            self.ts = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "service": self.service,
            "ok": self.ok,
            "summary": self.summary,
            "report": self.report,
            "files": self.files,
            "notes": self.notes,
            "error": self.error,
            "planned": self.planned,
            "approved": self.approved,
            "executed": self.executed,
            "verified": self.verified,
        }


def _append_run_log(record: RunRecord) -> None:
    """Append one run record to the JSONL run log (best-effort)."""
    try:
        path = _run_log_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
    except OSError:
        pass


def log_receipt(
    service: str,
    *,
    ok: bool,
    summary: str,
    report: str = "",
    files: List[str] | None = None,
    notes: List[str] | None = None,
    error: str = "",
    planned: str = "",
    approved: str = "",
    executed: str = "",
    verified: str = "",
) -> RunRecord:
    """Build a :class:`RunRecord` and append it to the run log.

    This is the single choke point for receipts: every dispatch — success,
    handler failure, or rejected-before-dispatch — goes through here, so
    no consequential act ends without a receipt entry. Never raises.
    """
    record = RunRecord(
        service=service,
        ok=ok,
        summary=summary,
        report=report,
        files=list(files or ()),
        notes=list(notes or ()),
        error=error,
        planned=planned,
        approved=approved,
        executed=executed,
        verified=verified,
    )
    _append_run_log(record)
    return record


def read_run_log(limit: int = 20) -> List[Dict[str, Any]]:
    """Read recent run-log records (newest last). Tolerates corruption."""
    path = _run_log_path()
    if not os.path.exists(path):
        return []
    records: List[Dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if isinstance(rec, dict):
                    records.append(rec)
    except OSError:
        return []
    return records[-limit:]


def run_service(
    name: str,
    params_override: Optional[Dict[str, Any]] = None,
    registry: Optional[ServiceRegistry] = None,
    *,
    scheduled: bool = False,
) -> RunRecord:
    """Execute the named service and log the run.

    Every path writes a receipt via :func:`log_receipt` — including
    rejected requests (unknown/disabled service, bad params), so an
    exception path never ends without a structured error *and* a receipt
    entry. Returns a :class:`RunRecord` for service-level outcomes;
    raises :class:`ServiceError` only for invalid *requests* (e.g. unknown
    service name).

    ``scheduled=True`` records that the authority for this run was a
    cron/daemon schedule rather than an on-demand user request.
    """
    from levi.bot.services import validate_name

    approval = "scheduled run (cron/daemon)" if scheduled else "on-demand user request"
    base_planned = "execute service %r" % (name,)

    def _reject(reason: str, exc: BaseException):
        log_receipt(
            name if isinstance(name, str) else "?",
            ok=False,
            summary="rejected: %s" % reason,
            error="%s: %s" % (type(exc).__name__, exc),
            planned=base_planned,
            approved=approval,
            executed="rejected before handler dispatch",
            verified="n/a — nothing executed",
        )
        raise exc

    try:
        validate_name(name)
        reg = registry or ServiceRegistry()
        definition: Optional[ServiceDefinition] = reg.get(name)
        if definition is None:
            raise ServiceError("run: unknown service %r — see `service list`" % (name,))
        if not definition.enabled:
            raise ServiceError(
                "run: service %r is disabled — `service enable %s` to re-arm it"
                % (name, name)
            )
        merged: Dict[str, Any] = dict(definition.params)
        if params_override:
            if not isinstance(params_override, dict):
                raise ServiceError("run: params_override must be a dict")
            merged.update(params_override)
    except Exception as exc:  # noqa: BLE001 - invalid requests are receipted, then raised
        _reject(str(exc), exc)

    planned = "execute service '%s' (type=%s, schedule=%s) with params %s" % (
        name,
        definition.service_type,
        definition.schedule,
        json.dumps(merged, sort_keys=True, ensure_ascii=False)[:500],
    )
    handler = get_handler_for(definition)
    handler_label = getattr(handler, "__name__", type(handler).__name__)
    try:
        result: ServiceResult = handler(merged)
    except ServiceError as exc:
        record = log_receipt(
            name,
            ok=False,
            summary="rejected: %s" % exc,
            error=str(exc),
            planned=planned,
            approved=approval,
            executed="handler %s refused before acting" % handler_label,
            verified="n/a — refused, no side effects",
        )
    except Exception as exc:  # noqa: BLE001 - handlers must never crash the runner
        record = log_receipt(
            name,
            ok=False,
            summary="crashed: %s: %s" % (type(exc).__name__, exc),
            error="%s: %s" % (type(exc).__name__, exc),
            planned=planned,
            approved=approval,
            executed="handler %s raised %s" % (handler_label, type(exc).__name__),
            verified="n/a — crashed, outcome unknown; nothing claimed",
        )
    else:
        if result.ok:
            verified = (
                "; ".join(result.notes)
                if result.notes
                else "handler reported success; report produced"
            )
            executed = "handler %s completed" % handler_label
        else:
            verified = "handler reported failure; no success claimed"
            executed = "handler %s completed with a failure report" % handler_label
        record = log_receipt(
            name,
            ok=result.ok,
            summary=result.summary(),
            report=result.report,
            files=list(result.files),
            notes=list(result.notes),
            planned=planned,
            approved=approval,
            executed=executed,
            verified=verified,
        )
    return record


# ---------------------------------------------------------------------------
# Spark-voiced narration
# ---------------------------------------------------------------------------

_OK_OPENERS = (
    "Done and done. Here's what I found:",
    "Handled. Report time:",
    "All yours — fresh off the assembly line:",
)

_FAIL_OPENERS = (
    "Okay, that one blew up in a very boring way. Here's the damage:",
    "So. That did not go as planned. Honest report:",
)


def narrate(record: RunRecord, *, scheduled: bool = False) -> str:
    """Render a run record as a spark-voiced reply.

    Report first, flavor second; failures are stated plainly. ``scheduled``
    notes when the run came from a cron job rather than a chat request.
    """
    if record.ok:
        opener = _OK_OPENERS[hash(record.service) % len(_OK_OPENERS)]
        text = "%s\n\n%s" % (opener, record.report)
    else:
        opener = _FAIL_OPENERS[hash(record.service) % len(_FAIL_OPENERS)]
        detail = record.error or record.summary
        text = "%s\n\n%s failed: %s" % (opener, record.service, detail)
        if record.notes:
            text += "\nNotes: " + "; ".join(record.notes)
    if record.files:
        text += "\n\nSaved: " + ", ".join(record.files)
    if scheduled:
        text += "\n\n_(ran on schedule; ping me if you want the cadence changed)_"
    else:
        text += (
            "\n\n_(on demand — want this on a schedule? say 'set up a daily "
            "bounty watch' or similar and I'll give you the cron line)_"
        )
    return text
