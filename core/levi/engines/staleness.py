"""Staleness engine — score freshness, mark the old, delete nothing.

Knowledge rots on a schedule nobody reads. Staleness hangs an age against
every item and classifies it honestly: fresh (still within the fresh
window), stale (past fresh, past the point where you should re-check it),
expired (past the point where trusting it is a mistake). Classification
is marking, not pruning: nothing leaves the verdict.

An item is a dict with an ``id`` and a ``seen_at`` ISO-8601 stamp; a
policy is a named half-life pair (fresh boundary, stale boundary)::

    {"items": [{"id": "receipt-12", "seen_at": "2026-09-20T10:00:00+00:00"}],
     "policy": "day"}

Policies are named because numbers drift — a name is a promise kept in one
place:

    short:  fresh 1h,   stale 24h     (hot signals, alerts)
    day:    fresh 24h,  stale 7d      (daily reports)
    week:   fresh 7d,   stale 30d     (weekly summaries)
    long:   fresh 30d,  stale 180d    (canon material)

Custom policies are allowed as ``{"fresh_sec": 3600, "stale_sec": 86400}``
— same shape as a named policy's expansion, checked by the same laws.

The score decays linearly: 1.0 at age zero, 0.0 exactly at the stale
boundary, and flat 0.0 beyond it. Confidence is the mean score — a fresh
table speaks with one voice; a rotted table mumbles.

Laws (declared up front, proved by the test suite)
--------------------------------------------------
1. **Stamp law** — every item carries a parseable ISO-8601 ``seen_at``;
   an item without a real stamp is refused, never scored.
2. **Future law** — stamps after ``now`` are refused; freshness is earned
   by age, never granted to things that haven't happened.
3. **Determinism law** — same inputs → byte-identical verdict (sans
   ``ran_at``).
4. **Deny-closed law** — malformed items (missing id, bad stamp, unknown
   policy, duplicate ids) are refused with a named error, never coerced.
5. **Mark-never-delete law** — expired items are classified and kept; the
   verdict always contains every input item. Absence is evidence of a
   bug, not of a clean table.
6. **Evidence law** — every score carries the observed age, the boundary
   that classified it, and the policy that set it; a bare state is
   refused by design.
7. **Bound law** — runs are capped at ``max_items`` (default 4096); a
   bigger run is refused rather than half-run.

Pure computation — no actions, no side effects.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from levi.engines.base import Engine, EngineInputError, EngineResult, registry

_POLICIES: Dict[str, Dict[str, float]] = {
    "short": {"fresh_sec": 3600.0, "stale_sec": 86400.0},
    "day": {"fresh_sec": 86400.0, "stale_sec": 604800.0},
    "week": {"fresh_sec": 604800.0, "stale_sec": 2592000.0},
    "long": {"fresh_sec": 2592000.0, "stale_sec": 15552000.0},
}

_DEFAULT_MAX_ITEMS = 4096


def _parse_stamp(value: Any, item_id: Any) -> datetime:
    if not isinstance(value, str):
        raise EngineInputError(
            f"engine 'staleness': item {item_id!r} seen_at must be an "
            f"ISO-8601 string, got {type(value).__name__}"
        )
    text = value.strip()
    if not text:
        raise EngineInputError(f"engine 'staleness': item {item_id!r} seen_at is empty")
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        raise EngineInputError(
            f"engine 'staleness': item {item_id!r} seen_at is not a valid "
            f"ISO-8601 stamp: {text!r}"
        ) from None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp


def _resolve_policy(policy: Any) -> Dict[str, float]:
    if isinstance(policy, str):
        if policy not in _POLICIES:
            raise EngineInputError(
                f"engine 'staleness': unknown policy {policy!r}; known: "
                + ", ".join(sorted(_POLICIES))
            )
        return dict(_POLICIES[policy])
    if isinstance(policy, dict):
        missing = {"fresh_sec", "stale_sec"} - set(policy)
        if missing:
            raise EngineInputError(
                "engine 'staleness': custom policy missing keys: "
                + ", ".join(sorted(missing))
            )
        try:
            fresh = float(policy["fresh_sec"])
            stale = float(policy["stale_sec"])
        except (TypeError, ValueError):
            raise EngineInputError(
                "engine 'staleness': custom policy bounds must be numbers of seconds"
            ) from None
        if fresh <= 0 or stale <= 0 or fresh >= stale:
            raise EngineInputError(
                "engine 'staleness': custom policy needs 0 < fresh_sec < stale_sec"
            )
        return {"fresh_sec": fresh, "stale_sec": stale}
    raise EngineInputError(
        "engine 'staleness': policy must be a policy name or "
        "{fresh_sec, stale_sec}, got " + type(policy).__name__
    )


def _classify(age_sec: float, fresh_sec: float, stale_sec: float) -> str:
    if age_sec <= fresh_sec:
        return "fresh"
    if age_sec < stale_sec:
        return "stale"
    return "expired"


def _score(age_sec: float, stale_sec: float) -> float:
    if age_sec >= stale_sec:
        return 0.0
    return round(1.0 - (age_sec / stale_sec), 6)


def _staleness(inputs: Dict[str, Any]) -> EngineResult:
    items = inputs["items"]
    if not isinstance(items, list):
        raise EngineInputError(
            "engine 'staleness': items must be a list, got " + type(items).__name__
        )
    max_items = inputs.get("max_items", _DEFAULT_MAX_ITEMS)
    if not isinstance(max_items, int) or max_items < 1:
        raise EngineInputError("engine 'staleness': max_items must be a positive int")
    if len(items) > max_items:
        raise EngineInputError(
            f"engine 'staleness': {len(items)} items exceed max_items "
            f"{max_items} — refusing rather than half-running"
        )
    policy_name = inputs.get("policy", "day")
    bounds = _resolve_policy(policy_name)
    now = inputs.get("now")
    now_dt = (
        _parse_stamp(now, "<now>") if now is not None else datetime.now(timezone.utc)
    )

    seen_ids: Dict[Any, None] = {}
    scored: List[Dict[str, Any]] = []
    trace: List[str] = []
    for item in items:
        if not isinstance(item, dict):
            raise EngineInputError(
                "engine 'staleness': every item must be a dict, got "
                + type(item).__name__
            )
        item_id = item.get("id")
        if item_id is None or (isinstance(item_id, str) and not item_id.strip()):
            raise EngineInputError(
                "engine 'staleness': every item needs a non-empty id"
            )
        if item_id in seen_ids:
            raise EngineInputError(f"engine 'staleness': duplicate item id {item_id!r}")
        seen_ids[item_id] = None
        stamp = _parse_stamp(item.get("seen_at"), item_id)
        age_sec = (now_dt - stamp).total_seconds()
        if age_sec < 0:
            raise EngineInputError(
                f"engine 'staleness': item {item_id!r} is stamped in the "
                "future — refusing to score what hasn't happened"
            )
        state = _classify(age_sec, bounds["fresh_sec"], bounds["stale_sec"])
        scored.append(
            {
                "id": item_id,
                "state": state,
                "age_sec": round(age_sec, 3),
                "score": _score(age_sec, bounds["stale_sec"]),
                "seen_at": item.get("seen_at"),
                "fresh_sec": bounds["fresh_sec"],
                "stale_sec": bounds["stale_sec"],
                "policy": policy_name if isinstance(policy_name, str) else "custom",
            }
        )
        trace.append(
            f"{item_id}: {state} (age {age_sec:.0f}s "
            f"vs fresh {bounds['fresh_sec']:.0f}s / "
            f"stale {bounds['stale_sec']:.0f}s)"
        )

    counts = {"fresh": 0, "stale": 0, "expired": 0}
    for entry in scored:
        counts[entry["state"]] += 1
    confidence = (
        round(sum(e["score"] for e in scored) / len(scored), 6) if scored else 1.0
    )
    verdict = {
        "items": scored,
        "counts": counts,
        "total": len(scored),
        "policy": policy_name if isinstance(policy_name, str) else "custom",
        "now": now_dt.isoformat(),
        "nothing_pruned": len(scored) == len(items),
    }
    return EngineResult(
        engine_id="staleness",
        verdict=verdict,
        confidence=confidence,
        trace=trace,
    )


STALENESS_ENGINE = Engine(
    id="staleness",
    name="Staleness",
    description=(
        "Scores item freshness against a named or custom age policy; "
        "classifies fresh/stale/expired and marks — never deletes."
    ),
    version="1.0.0",
    required=("items",),
    schema={
        "items": "list of {id, seen_at}",
        "policy": "policy name or {fresh_sec, stale_sec}, default 'day'",
        "now": "ISO-8601 stamp, default wall clock",
        "max_items": "int >= 1, default 4096 (run guard)",
    },
    risk="info",
    handler=_staleness,
)

registry.register(STALENESS_ENGINE)


def _declare_to_interop() -> None:
    try:
        from levi.interop.registry import register
    except Exception:  # pragma: no cover - registry substrate mid-edit
        return
    try:
        register(
            "engines-staleness",
            provides=("engines.staleness.score",),
            requires=(),
        )
    except Exception:  # deny-closed: duplicate / malformed never half-runs
        pass


_declare_to_interop()
