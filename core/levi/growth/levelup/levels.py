"""Levels: threshold math + level-up events into the growth journal (L3, L4, L9).

Level is a pure function of cumulative EXP — never stored, always
recomputed from the receipt ledger:

    threshold(L) = 50 * L * (L + 1)

    L1 = 100, L2 = 300, L3 = 600, L4 = 1000, L5 = 1500, L10 = 5500.

When a new award pushes an entity across a threshold, exactly one
journal entry (kind="level-up") is recorded. The journal is the only
place level events are asserted (L4); the sentience rail screens every
blurb (L9).
"""

from __future__ import annotations

from .receipts import check_entity, entity_total

JOURNAL_KIND = "level-up"


def threshold(level: int) -> int:
    """Cumulative EXP required to reach `level`."""
    if not isinstance(level, int) or isinstance(level, bool) or level < 1:
        raise ValueError("threshold: level must be a positive int, got %r" % (level,))
    return 50 * level * (level + 1)


def level_for(total_exp: int) -> int:
    """Level reached at `total_exp` (pure function, L3)."""
    if not isinstance(total_exp, int) or isinstance(total_exp, bool):
        raise ValueError("level_for: total_exp must be an int")
    if total_exp < 0:
        raise ValueError("level_for: total_exp must be >= 0")
    level = 0
    while total_exp >= threshold(level + 1):
        level += 1
    return level


def exp_to_next(total_exp: int) -> tuple[int, int]:
    """(current_level, exp_needed_to_reach_next_level)."""
    lvl = level_for(total_exp)
    return lvl, threshold(lvl + 1) - total_exp


def _last_recorded_level(entity: str) -> int:
    """Highest level already asserted for this entity in the journal."""
    from levi.growth import journal as _journal

    check_entity(entity)
    best = 0
    for entry in _journal.read_entries(limit=500):
        if entry.get("kind") == JOURNAL_KIND and entry.get("entity") == entity:
            try:
                lvl = int(entry.get("level", 0))
            except (TypeError, ValueError):
                continue
            best = max(best, lvl)
    return best


def _blurb(entity: str, level: int, total: int) -> str:
    """Level-up blurb — engagement copy only, rail-checked (L9)."""
    from levi.growth.guards import check_no_sentience_claim

    text = (
        "%s reached level %d (%d total EXP). "
        "Training record updated; keep the questions coming."
        % (entity, level, total)
    )
    hits = check_no_sentience_claim(text)
    if hits:
        raise ValueError("level-up blurb tripped the sentience rail: %s" % hits)
    return text


def maybe_level_up(entity: str) -> dict | None:
    """Record a level-up if the entity crossed a threshold.

    Returns the journal entry, or None when no new crossing happened.
    Idempotent: repeated calls without new EXP return None (L4).
    """
    from levi.growth import journal as _journal

    check_entity(entity)
    total = entity_total(entity)
    now_level = level_for(total)
    recorded = _last_recorded_level(entity)
    if now_level <= recorded:
        return None
    # Record the highest newly-crossed level (catches multi-level jumps).
    entry = _journal.append_entry(
        {
            "kind": JOURNAL_KIND,
            "entity": entity,
            "level": now_level,
            "total_exp": total,
            "blurb": _blurb(entity, now_level, total),
        }
    )
    return entry
