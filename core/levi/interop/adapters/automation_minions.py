"""Adapter: agent intent <-> automation minion catalog.

Bridges the agent runtime's automation specialist (selected for intents
like "automate", "schedule", "every", "workflow") to the LEVI-native
automation engine (:mod:`levi.automation`): the HITL-gated minion catalog,
the dry-run rail, and the routine recorder.

Contract::

    minions_for_intent(intent_text, limit=5) -> [Minion]
        Ranked catalog matches for an intent. Blank intent -> [].
        Never raises on a missing automation package: returns [] so the
        caller can say so honestly.

    preview_intent_runs(intent_text, payload=None, limit=3) -> [Receipt]
        Dry-run receipts for the top catalog matches. Nothing executes;
        every receipt records the rail it walked (Plan -> Preview ->
        Permission -> Execute -> Verify -> Receipt) with the gate outcome.

    record_session_routine(session_id, name=None) -> Routine
        "Watch me once": distill a user-owned routine from one
        growth-harvested chat session via
        :func:`levi.automation.routines.record_from_session`.

The adapter never drives a browser or device and never executes live:
previews are dry-run only, and playback stays permission-gated inside
the automation package.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _lazy():
    """Import the automation package lazily; None when unavailable."""
    try:
        from levi.automation import minions as _minions
        from levi.automation import engine as _engine
        from levi.automation import routines as _routines

        return _minions, _engine, _routines
    except ImportError:
        return None


def minions_for_intent(intent_text: str, limit: int = 5) -> List[Any]:
    """Ranked catalog minions for an intent. Blank/unavailable -> []."""
    if not isinstance(intent_text, str) or not intent_text.strip():
        return []
    lazy = _lazy()
    if lazy is None:
        return []
    _, _, routines = lazy
    return routines.match_minions_for_text(intent_text)[: max(0, int(limit))]


def preview_intent_runs(
    intent_text: str,
    payload: Optional[Dict[str, Any]] = None,
    limit: int = 3,
) -> List[Any]:
    """Dry-run receipts for the top catalog matches of an intent.

    Never executes. A receipt with ``ok=False`` means the run would stop
    at the gate or on a failed condition — the preview says so plainly.
    """
    if not isinstance(intent_text, str) or not intent_text.strip():
        return []
    lazy = _lazy()
    if lazy is None:
        return []
    _, engine, _ = lazy  # catalog minions come via minions_for_intent
    out = []
    for minion in minions_for_intent(intent_text, limit=limit):
        event = engine.TriggerEvent(
            kind="intent-preview",
            summary=intent_text.strip()[:200],
            payload=dict(payload) if isinstance(payload, dict) else {},
        )
        out.append(engine.run_minion(minion, event, dry_run=True))
    return out


def record_session_routine(
    session_id: str,
    name: Optional[str] = None,
    sessions_dir: Any = None,
) -> Any:
    """Distill a user-owned routine from one harvested session.

    Raises ValueError when the session has no harvestable records or
    produces no steps; ImportError propagates only if the automation
    package itself is missing (callers should treat that as "unavailable").
    """
    lazy = _lazy()
    if lazy is None:
        raise ImportError("levi.automation is unavailable")
    _, _, routines = lazy
    return routines.record_from_session(
        session_id, name=name, sessions_dir=sessions_dir
    )
