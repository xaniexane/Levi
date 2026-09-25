"""Additive emission hook: bloodstream turn → observability corpus.

:func:`emit_turn_trace` is the single call site the turn pipeline needs:
it builds a :class:`TurnTrace` from the finished ``TurnResult`` and
appends it to the :class:`TraceStore`. It never raises into the pipeline
and never changes what the turn does — observability is a side effect,
not a stage.

``base_dir`` override: the pipeline passes ``data_dir / "observability"``
when a TurnContext overrides the home directory (tests, hermetic runs);
otherwise the store defaults to ``~/.levi/observability``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from levi.observability.schema import TurnTrace, from_bloodstream
from levi.observability.store import TraceStore


def emit_turn_trace(
    result: Any,
    text: str = "",
    *,
    stage_timings: Optional[Dict[str, float]] = None,
    duration_ms: Optional[float] = None,
    composted: Any = None,
    base_dir: Optional[Path] = None,
) -> Optional[TurnTrace]:
    """Round-trip one finished turn into the observability corpus.

    Returns the emitted TurnTrace, or None if anything failed. Never
    raises — a broken observer must not break the organism it watches.
    """
    try:
        trace = from_bloodstream(
            result,
            text,
            stage_timings=stage_timings,
            duration_ms=duration_ms,
            composted=composted,
        )
        store = TraceStore(base_dir=base_dir)
        store.append(trace)
        return trace
    except Exception:
        return None
