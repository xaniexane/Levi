"""LEVI job organ — ENGINE 3 / APPLY. Drafts and prefills; the human submits.

The binding law, enforced in code:

* The organ DRAFTS application packets and PREFILLS fields from the
  profile. It NEVER auto-submits anything, anywhere.
* Every submission intent passes an APPROVAL (or EDIT_APPROVE) gate.
* The Application Log only gains a row after the human CONFIRMS they
  actually submitted — ``log_submission`` refuses to write on a dry run
  or a denied gate.
* Dry-run is the default for every function here. Live execution is an
  explicit, per-call choice and still gates.

A "submission" in this organ means: the human pressed the button on the
board's site (or a browser agent did, under the human's eye). The organ
hands them the packet and records the receipt — it is never the hand on
the button.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from levi.automation.hitl import (
    Gate,
    GateKind,
    GateRequest,
    auto_approve,
)

from . import prep as prep_engine
from .profiles import Profile
from .store import Warehouse

Responder = Callable[[GateRequest], Dict[str, Any]]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _minion(
    minion_id: str,
    kind: GateKind,
    prompt: str,
    context: Optional[Dict[str, Any]] = None,
) -> GateRequest:
    return GateRequest(
        minion_id=minion_id,
        kind=kind,
        prompt=prompt,
        context=context or {},
    )


def build_packet(
    warehouse: Warehouse,
    profile: Profile,
    queue_id: int,
    with_cover_letter: bool = True,
    dry_run: bool = True,
    responder: Responder = auto_approve,
) -> Dict[str, Any]:
    """Assemble the submission packet for a queued job: resume version
    pick, cover-letter draft, prefilled contact fields. Records a
    NOTIFICATION gate (the human is told a packet is ready)."""
    row = warehouse.get_row("apply_queue", queue_id)
    listing = {
        "job_title": row.get("job_title"),
        "company": row.get("company"),
        "url": row.get("url"),
    }
    resume = prep_engine.pick_resume_version(warehouse, str(row.get("job_title") or ""))
    cover = None
    if with_cover_letter:
        template = prep_engine.pick_template(warehouse, str(row.get("job_title") or ""))
        if template is not None:
            cover = prep_engine.compose_cover_letter(profile, listing, template)

    packet = {
        "queue_id": queue_id,
        "job_title": row.get("job_title"),
        "company": row.get("company"),
        "url": row.get("url"),
        "apply_method": row.get("apply_method") or "human-browser",
        "resume_version": (resume or {}).get("version_name", ""),
        "cover_letter_draft": cover,
        "prefill": {
            "full_name": profile.get("full_name") or "",
            "email": profile.get("email") or "",
            "phone": profile.get("phone") or "",
        },
        "built_at": _utcnow(),
        "dry_run": dry_run,
    }

    gate = Gate(
        _minion(
            "jobs.apply.build-packet",
            GateKind.NOTIFICATION,
            f"Application packet ready: {row.get('job_title')} @ {row.get('company')}",
            {"queue_id": queue_id, "dry_run": dry_run},
        )
    )
    packet["gate"] = gate.resolve(responder).to_dict()

    if not dry_run:
        warehouse.update_row(
            "apply_queue",
            queue_id,
            {
                "resume_version": packet["resume_version"],
                "cover_letter": "Y" if cover else "N",
                "status": "packet-ready",
                "notes": (str(row.get("notes") or "") + " | packet built").strip(" |"),
            },
        )
        warehouse.log_automation(
            "build-packet",
            "Success",
            tool_used="jobs.apply",
            target_platform=str(row.get("source_board") or ""),
            job_title_processed=str(row.get("job_title") or ""),
            notes=f"queue_id={queue_id}",
        )
    return packet


def authorize_submission(
    warehouse: Warehouse,
    queue_id: int,
    responder: Responder,
    dry_run: bool = True,
    allow_edit: bool = True,
) -> Dict[str, Any]:
    """Ask the human to authorize this submission (APPROVAL, or
    EDIT_APPROVE when a cover-letter draft exists and edits are allowed).

    On approval the queue row is marked ``authorized`` — this is NOT a
    submission record. It is permission for the human to go submit, and
    the packet to take with them. Denial stops everything (GateDenied).
    """
    row = warehouse.get_row("apply_queue", queue_id)
    kind = (
        GateKind.EDIT_APPROVE
        if (allow_edit and row.get("cover_letter") == "Y")
        else GateKind.APPROVAL
    )
    gate = Gate(
        _minion(
            "jobs.apply.authorize",
            kind,
            f"Authorize submitting: {row.get('job_title')} @ {row.get('company')}?",
            {"queue_id": queue_id, "url": row.get("url"), "dry_run": dry_run},
        )
    )
    result = gate.require(responder)  # raises GateDenied on denial
    outcome = {
        "queue_id": queue_id,
        "authorized": True,
        "decision": result.decision,
        "edited": result.decision == "edited",
        "dry_run": dry_run,
        "gate": result.to_dict(),
    }
    if not dry_run:
        warehouse.update_row(
            "apply_queue",
            queue_id,
            {
                "status": "authorized",
                "notes": (
                    str(row.get("notes") or "")
                    + f" | authorized {result.decision} @ {_utcnow()[:16]}"
                ).strip(" |"),
            },
        )
        warehouse.log_automation(
            "authorize-submission",
            "Success",
            tool_used="jobs.apply",
            job_title_processed=str(row.get("job_title") or ""),
            notes=f"queue_id={queue_id} decision={result.decision}",
        )
    return outcome


def log_submission(
    warehouse: Warehouse,
    queue_id: int,
    responder: Responder,
    dry_run: bool = True,
    confirmation: bool = False,
) -> Dict[str, Any]:
    """Record an ACTUAL submission in the Application Log. The human must
    CONFIRM they pressed the button (``confirmation=True`` from their own
    answer, or a CONFIRM gate resolved by their responder). On dry-run,
    or without confirmation, nothing is written — the log never invents
    submissions."""
    row = warehouse.get_row("apply_queue", queue_id)
    gate = Gate(
        _minion(
            "jobs.apply.log-submission",
            GateKind.CONFIRM,
            f"Did you submit the application for {row.get('job_title')} @ {row.get('company')}?",
            {"queue_id": queue_id, "dry_run": dry_run},
        )
    )
    result = gate.require(responder)
    confirmed = confirmation or result.decision == "approved"
    outcome: Dict[str, Any] = {
        "queue_id": queue_id,
        "logged": False,
        "confirmed": confirmed,
        "dry_run": dry_run,
        "gate": result.to_dict(),
    }
    if dry_run or not confirmed:
        outcome["reason"] = "dry-run" if dry_run else "not confirmed by human"
        return outcome

    log_row = warehouse.add_row(
        "application_log",
        {
            "date_applied": _utcnow()[:10],
            "job_title": row.get("job_title"),
            "company": row.get("company"),
            "source": row.get("source_board") or "apply-queue",
            "url": row.get("url"),
            "resume_version": row.get("resume_version"),
            "cover_letter_used": row.get("cover_letter"),
            "apply_method": row.get("apply_method") or "human-browser",
            "confirmation_received": "N",
            "current_status": "submitted",
            "notes": "logged after human-confirmed submission",
        },
    )
    warehouse.update_row(
        "apply_queue",
        queue_id,
        {
            "status": "submitted",
            "completed": "Y",
            "notes": (str(row.get("notes") or "") + " | submitted, logged").strip(" |"),
        },
    )
    warehouse.log_automation(
        "log-submission",
        "Success",
        tool_used="jobs.apply",
        job_title_processed=str(row.get("job_title") or ""),
        notes=f"queue_id={queue_id} app row id={log_row['id']}",
    )
    outcome["logged"] = True
    outcome["application_log_id"] = log_row["id"]
    return outcome


def record_response(
    warehouse: Warehouse,
    log_id: int,
    response_type: str,
    current_status: str = "",
    notes: str = "",
) -> Dict[str, Any]:
    """Record an employer response on an Application Log row
    (interview invite, rejection, offer...)."""
    if response_type not in ("interview", "rejection", "offer", "screening", "other"):
        raise ValueError(f"unknown response_type {response_type!r}")
    return warehouse.update_row(
        "application_log",
        log_id,
        {
            "response_received": "Y",
            "response_type": response_type,
            "current_status": current_status or response_type,
            "notes": notes,
        },
    )
