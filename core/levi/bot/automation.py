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
    """One executed service run."""

    service: str
    ok: bool
    summary: str
    report: str = ""
    files: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    error: str = ""
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
) -> RunRecord:
    """Execute the named service and log the run.

    Returns a :class:`RunRecord` (never raises for service-level failures;
    raises :class:`ServiceError` only for invalid *requests*, e.g. unknown
    service name).
    """
    from levi.bot.services import validate_name

    validate_name(name)
    reg = registry or ServiceRegistry()
    definition: Optional[ServiceDefinition] = reg.get(name)
    if definition is None:
        raise ServiceError("run: unknown service %r — see `service list`" % (name,))
    if not definition.enabled:
        raise ServiceError("run: service %r is disabled" % (name,))
    merged: Dict[str, Any] = dict(definition.params)
    if params_override:
        if not isinstance(params_override, dict):
            raise ServiceError("run: params_override must be a dict")
        merged.update(params_override)

    handler = get_handler_for(definition)
    try:
        result: ServiceResult = handler(merged)
    except ServiceError as exc:
        record = RunRecord(
            service=name, ok=False, summary="rejected: %s" % exc, error=str(exc)
        )
    except Exception as exc:  # noqa: BLE001 - handlers must never crash the runner
        record = RunRecord(
            service=name,
            ok=False,
            summary="crashed: %s: %s" % (type(exc).__name__, exc),
            error="%s: %s" % (type(exc).__name__, exc),
        )
    else:
        record = RunRecord(
            service=name,
            ok=result.ok,
            summary=result.summary(),
            report=result.report,
            files=list(result.files),
            notes=list(result.notes),
        )
    _append_run_log(record)
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
