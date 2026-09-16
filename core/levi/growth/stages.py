"""Developmental stages with EXPLICIT criteria — no vibe-based growth.

A stage is a pure function of observable counters, nothing else:

  * ``learnings``       — self-taught growth learnings consolidated
                          (curriculum seed and distribution routing
                          slips don't count)
  * ``corroborations``  — sum of ``corroborated_count`` over those
                          learnings (evidence the loop's beliefs keep
                          checking out)
  * ``days_active``     — days since the first journaled cycle/study
                          (the loop has been *running*, not just run)
  * ``curriculum_units``— founder-taught seed lessons consolidated
  * ``cycles``          — growth cycles completed (informational)

``stage_for(stats)`` returns the highest stage whose criteria are all
met, plus the explicit requirements of the NEXT stage so
``levi growth status`` can show real numbers ("learnings 12/25").

This is engagement copy, not a cognitive claim: the stage labels how
much Levi has been taught, not how it *feels* about being taught.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

# Stage ladder: (name, blurb, {counter: threshold}). A stage is
# reached when EVERY criterion is met (missing counters count as 0).
STAGE_LADDER: tuple[tuple[str, str, dict[str, float]], ...] = (
    (
        "newborn",
        "just opened its eyes — no learnings consolidated yet",
        {},
    ),
    (
        "sprouting",
        "first learnings taking root",
        {"learnings": 1},
    ),
    (
        "curious",
        "asking questions of its own experience now",
        {"learnings": 5, "days_active": 1},
    ),
    (
        "growing",
        "a real memory of how things work around here",
        {"learnings": 25, "corroborations": 10, "days_active": 7},
    ),
    (
        "maturing",
        "seasoned — a long personal history to draw on",
        {
            "learnings": 100,
            "corroborations": 50,
            "days_active": 30,
            "curriculum_units": 20,
        },
    ),
)

_LEARNING_KINDS = ("fact", "preference", "procedural", "correction")


def _validate_stats(stats: Any) -> dict[str, float]:
    if not isinstance(stats, Mapping):
        raise ValueError(
            "stage_for: stats must be a mapping, got %s" % type(stats).__name__
        )
    clean: dict[str, float] = {}
    for key, value in stats.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(
                "stage_for: counter %r must be a number, got %r" % (key, value)
            )
        if value < 0:
            raise ValueError(
                "stage_for: counter %r must be non-negative, got %r" % (key, value)
            )
        clean[str(key)] = float(value)
    return clean


def _criteria_met(criteria: dict[str, float], stats: dict[str, float]) -> bool:
    return all(stats.get(name, 0.0) >= need for name, need in criteria.items())


def stage_for(stats: Mapping[str, Any]) -> dict[str, Any]:
    """Pure function: observable counters → stage + next requirements.

    Returns ``{"name", "blurb", "criteria", "next"}`` where ``next`` is
    ``None`` at the top stage, else ``{"name", "requirements"}`` with
    ``requirements`` mapping each counter → ``{"current", "threshold",
    "met"}``.

    Raises ValueError when ``stats`` is not a mapping of non-negative
    numbers.
    """
    counters = _validate_stats(stats)
    name, blurb, criteria = STAGE_LADDER[0]
    next_idx: int | None = 1
    for i, (sname, sblurb, scriteria) in enumerate(STAGE_LADDER):
        if _criteria_met(scriteria, counters):
            name, blurb, criteria = sname, sblurb, scriteria
            next_idx = i + 1 if i + 1 < len(STAGE_LADDER) else None
    nxt = None
    if next_idx is not None:
        nname, _nblurb, ncriteria = STAGE_LADDER[next_idx]
        nxt = {
            "name": nname,
            "requirements": {
                counter: {
                    "current": counters.get(counter, 0.0),
                    "threshold": need,
                    "met": counters.get(counter, 0.0) >= need,
                }
                for counter, need in ncriteria.items()
            },
        }
    return {
        "name": name,
        "blurb": blurb,
        "criteria": dict(criteria),
        "next": nxt,
    }


# ---------------------------------------------------------------------------
# Observable counters from the real world
# ---------------------------------------------------------------------------


def _parse_ts(ts: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def gather_stats(
    store: Any,
    state: Mapping[str, Any],
    journal_entries: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, float]:
    """Collect the observable counters stages are computed from.

    * self-taught learnings: growth-tagged memory entries that are
      neither distribution routing slips nor curriculum seed;
    * curriculum_units: growth+curriculum tagged entries;
    * corroborations: sum of ``corroborated_count`` on self-taught
      entries only (founder-seeded counts don't count — they weren't
      earned);
    * days_active: whole days from the earliest cycle/study journal
      entry to ``now``;
    * cycles: completed cycles from growth state.

    Pure given its inputs (``now`` injectable for tests). Raises
    ValueError on bad input shapes.
    """
    if store is not None and not hasattr(store, "list"):
        raise ValueError(
            "gather_stats: store must provide list(), got %s" % type(store).__name__
        )
    if not isinstance(state, Mapping):
        raise ValueError(
            "gather_stats: state must be a mapping, got %s" % type(state).__name__
        )
    if not isinstance(journal_entries, list):
        raise ValueError(
            "gather_stats: journal_entries must be a list, got %s"
            % type(journal_entries).__name__
        )
    now = now or datetime.now(timezone.utc)

    learnings = 0
    curriculum_units = 0
    corroborations = 0.0
    if store is not None:
        for entry in store.list(limit=5000):
            tags = set(getattr(entry, "tags", []) or [])
            if "growth" not in tags:
                continue
            if "curriculum" in tags:
                curriculum_units += 1
                continue
            if "distribution" in tags:
                continue  # routing slips are bookkeeping, not learnings
            if not any(k in tags for k in _LEARNING_KINDS):
                continue
            learnings += 1
            md = getattr(entry, "metadata", None) or {}
            try:
                corroborations += float(md.get("corroborated_count", 0) or 0)
            except (TypeError, ValueError):
                pass

    first: datetime | None = None
    for rec in journal_entries:
        if not isinstance(rec, dict):
            continue
        if rec.get("kind") not in ("cycle", "study"):
            continue
        dt = _parse_ts(rec.get("ts", ""))
        if dt is not None and (first is None or dt < first):
            first = dt
    days_active = 0.0
    if first is not None and now >= first:
        days_active = float((now - first).days)

    cycles = state.get("cycles", 0)
    try:
        cycles = int(cycles)
    except (TypeError, ValueError):
        cycles = 0
    return {
        "learnings": float(learnings),
        "corroborations": corroborations,
        "days_active": days_active,
        "curriculum_units": float(curriculum_units),
        "cycles": float(max(0, cycles)),
    }
