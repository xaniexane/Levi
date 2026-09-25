"""Alpha-as-critic for the media refinement loops.

``alpha_critique(task, context)`` runs Chauncey's Alpha deliberation
(propose -> critique -> verdict on the rules engine, brain-voice labeled
when usable) over a media artifact — a video analysis pack's heuristic
notes, an upgrade plan, a curation round — and returns the verdict with
its substrate label. When Alpha is unavailable the result says so
honestly instead of inventing a judgment.
"""

from __future__ import annotations

from typing import Any, Dict


def alpha_critique(task: str, context: str = "") -> Dict[str, Any]:
    """Ask Alpha to critique ``task`` (with optional ``context``).

    Returns {"status": "ok", "answer", "substrate", "limits", "verdict"}
    or {"status": "unavailable"|"error", "note": ...}. Never raises on
    Alpha-side problems — a critic that crashes is worse than none.
    """
    if not isinstance(task, str) or not task.strip():
        return {"status": "error", "note": "empty critique task — nothing to judge"}
    try:
        from levi.alpha import probe_alpha
    except Exception as exc:  # noqa: BLE001 - the failure IS the report
        return {
            "status": "unavailable",
            "note": f"levi.alpha could not be imported: {exc.__class__.__name__}: {exc}",
        }
    try:
        reasoner = probe_alpha()
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "unavailable",
            "note": f"Alpha reasoner could not be constructed: {exc.__class__.__name__}: {exc}",
        }
    if reasoner is None:
        return {"status": "unavailable", "note": "probe_alpha() returned None"}
    full_task = task if not context else task + "\n\nContext:\n" + context
    try:
        out = reasoner.reason(full_task)
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "note": f"Alpha deliberation failed: {exc.__class__.__name__}: {exc}",
        }
    return {
        "status": "ok",
        "answer": out.get("answer"),
        "substrate": out.get("substrate"),
        "limits": out.get("limits"),
        "verdict": out.get("verdict"),
    }
