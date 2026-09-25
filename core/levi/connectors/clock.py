"""Clock connector — pure tick math, no wall clock.

Given ``since`` (epoch seconds of the last tick boundary), ``now``
(epoch seconds), and ``period_seconds``, emits one event per tick that
fell due in ``(since, now]``::

    {"kind": "tick", "name": "<tick_name>", "at": <epoch seconds>,
     "tick_index": <int>}

The connector reads no wall clock itself — the caller passes ``now`` —
so ticks are deterministic and testable. ``state`` carries the last
tick boundary forward: ``{"last": <epoch>}``. A zero or negative period
is refused; ``since > now`` is refused; more than 10,000 due ticks is
refused rather than flooding the caller.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from levi.connectors.base import Connector, ConnectorError, registry

_MAX_TICKS = 10_000


def _epoch(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConnectorError(f"clock: '{name}' must be epoch seconds (a number)")
    return float(value)


def poll_clock(
    since: float,
    now: float,
    period_seconds: float,
    name: str = "tick",
    state: Dict[str, Any] | None = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    since_f = _epoch(since, "since")
    now_f = _epoch(now, "now")
    period = _epoch(period_seconds, "period_seconds")
    if period <= 0:
        raise ConnectorError("clock: 'period_seconds' must be positive")
    if since_f > now_f:
        raise ConnectorError("clock: 'since' is after 'now'")
    if not name or not isinstance(name, str):
        raise ConnectorError("clock: 'name' must be a non-empty string")

    start = (state or {}).get("last", since_f)
    start = _epoch(start, "state['last']") if start is not None else since_f

    events: List[Dict[str, Any]] = []
    # First tick boundary strictly after `start`.
    first_index = int(start // period) + 1
    tick_at = first_index * period
    index = first_index
    while tick_at <= now_f:
        events.append(
            {"kind": "tick", "name": name, "at": tick_at, "tick_index": index}
        )
        if len(events) > _MAX_TICKS:
            raise ConnectorError(
                f"clock: more than {_MAX_TICKS} ticks due — refused, "
                "narrow the window or widen the period"
            )
        index += 1
        tick_at = index * period

    new_state = {"last": events[-1]["at"] if events else start}
    return events, new_state


CLOCK_CONNECTOR = Connector(
    id="clock",
    name="Clock",
    description=(
        "Pure tick math: emits due ticks for (since, now] at a fixed "
        "period. Reads no wall clock — the caller passes 'now'."
    ),
    inputs=("since", "now", "period_seconds", "name", "state"),
    poll=poll_clock,
)

registry.register(CLOCK_CONNECTOR)
