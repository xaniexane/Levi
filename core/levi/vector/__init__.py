"""vector: sandbox; safe simulation before production (LEVI-native).

Canon role (ORGANISM_FORMS): "sandbox; safe simulation before production".

Canon evidence (founder corpus: copilot-sweep/ser13-18-21-master-conversation.md):
  - "Vector (Sandbox) — safe sim env (vector_sandbox.py)."
  - SER-18 (Lifecycle Engine) maps to OmniPulse, Eden, UniForge, Vector:
    "Eden + Vector host risky/experimental phases."

This is a LEVI-native recreation with LEVI's own twist — never a copy of
the original code. Vector is the form-facade over ``levi.sandbox`` (the
real implementation: bwrap/unshare/subprocess backends with an honest
isolation contract):

  - ``run_vector``: fail-closed argv validation, dry-run purity (a dry run
    NEVER executes — it returns the would-be receipt), hostile argv
    treated as data (non-string argv elements are rejected and named in
    the receipt, never executed).
  - ``capabilities``: honest report of which backends this host actually
    has — Vector never claims isolation the backend doesn't provide.
  - Every run returns a receipt: executed or dry-run, refused, or degraded.

Ready-for-review by the keeper. Never claims his review.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from levi.sandbox.backends import (
    describe_backends,
    isolation_report,
    select_backend,
)

FORM_NAME = "vector"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _receipt(
    status: str, reason: str, *, dry_run: bool = False, **extra: Any
) -> Dict[str, Any]:
    receipt = {
        "form": FORM_NAME,
        "status": status,
        "reason": reason,
        "dry_run": dry_run,
        "at": _utcnow(),
    }
    receipt.update(extra)
    return receipt


def capabilities() -> Dict[str, Any]:
    """Honest report: which sandbox backends this host actually has."""
    specs = describe_backends()
    return {
        "form": FORM_NAME,
        "backends": [
            {
                "name": s.name,
                "isolation": s.isolation_level,
                "available": s.available,
                "report": isolation_report(s),
            }
            for s in specs
        ],
        "selected": select_backend().name,
        "honest_limit": (
            "Vector's isolation is exactly what the selected backend "
            "provides. 'subprocess' means NO isolation and requires an "
            "explicit degraded acknowledgement."
        ),
    }


def run_vector(
    cmd: Any,
    *,
    dry_run: bool = False,
    backend: Optional[str] = None,
    net: bool = False,
    repo: Optional[Path] = None,
    allow_degraded: bool = False,
) -> Dict[str, Any]:
    """Run ``cmd`` inside the Vector sandbox (or dry-run it).

    Fail-closed: ``cmd`` must be a non-empty sequence of strings. Anything
    else — non-string elements, empty command, non-sequences — is rejected
    as hostile payload: treated as data, named in the receipt, NEVER
    executed.
    """
    if isinstance(cmd, (str, bytes)) or not isinstance(cmd, Sequence):
        return _receipt(
            "rejected",
            f"cmd must be a sequence of strings (argv), got "
            f"{type(cmd).__name__}: treated as data, not executed",
            dry_run=dry_run,
        )
    argv: List[str] = list(cmd)
    if not argv:
        return _receipt(
            "rejected", "empty command: nothing to simulate", dry_run=dry_run
        )
    bad = [a for a in argv if not isinstance(a, str)]
    if bad:
        return _receipt(
            "rejected",
            f"hostile argv elements rejected as data ({len(bad)} non-string): "
            f"{[repr(b)[:60] for b in bad]} — nothing executed",
            dry_run=dry_run,
        )
    if dry_run:
        return _receipt(
            "dry-run",
            f"would run {argv} via backend "
            f"{select_backend(backend).name} (net={net}); nothing executed",
            dry_run=True,
            argv=argv,
            backend=select_backend(backend).name,
            net=net,
        )
    from levi.sandbox.runner import run_command

    try:
        result = run_command(
            argv,
            backend=backend,
            net=net,
            repo=repo,
            allow_degraded=allow_degraded,
        )
    except PermissionError as exc:
        return _receipt(
            "refused",
            f"degraded sandbox requires acknowledgement: {exc}",
            argv=argv,
        )
    except Exception as exc:  # noqa: BLE001 - surfaced in receipt, not raised
        return _receipt("failed", f"sandbox run failed: {exc}", argv=argv)
    return _receipt(
        "executed",
        f"ran {argv} in backend {result.backend} "
        f"(isolation {result.isolation_level}), rc={result.returncode}",
        argv=argv,
        backend=result.backend,
        isolation=result.isolation_level,
        returncode=result.returncode,
        notes=list(result.notes),
    )
