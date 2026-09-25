"""Member mastery levels for the shared Legion skill pool.

Members hold skills at ranks; the pool resolves what a member can
execute. Member ids are Legion crew identifiers — this module plugs
into the EXISTING member representation in ``levi.legion.team`` and
invents no parallel member system:

- ``member_id_for(member)`` accepts a ``CrewMember`` (or anything with
  ``seat_key`` / ``role``, or a plain mapping), and resolves to the
  stable seat key, falling back to ``role:<role>``. A bare string is
  used as-is (it is expected to already be a seat key or role id).
- Mastery itself is a plain in-memory registry: member_id ->
  skill_id -> rank ("I"/"II"/"III").

LAW-GUARD-PROVE — invariants, proved by the test suite:

1. a mastery rank is always inside the skill's ladder — setting an
   out-of-ladder rank (or an unknown skill) fails LOUDLY;
2. ``executable_skills(member)`` returns only skills the member holds,
   each shaped to the member's own rank via ``pool.skill_at``.

PERSISTENCE PATH (documented, not built): the store is deliberately a
plain dict. ``dump()`` / ``load()`` serialize it to JSON-able data; a
durable store would call these around a file (e.g. a JSON document next
to the legion state) — no database, no implicit file I/O here.

NAMING: all names provisional, awaiting Chauncey's word — including the
``I / II / III`` rank names inherited from ``ranks.py``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from .pool import get_pool
from .ranks import RANKS

# member_id -> {skill_id: rank}
_MASTERY: Dict[str, Dict[str, str]] = {}


def member_id_for(member: Any) -> str:
    """Resolve a member to its stable id.

    Accepts a ``CrewMember`` from ``levi.legion.team`` (or any object /
    mapping carrying ``seat_key`` or ``role``), or a bare string which
    is used as-is. Seat key wins — it is the stable crew identity;
    ``role:<role>`` is the fallback when no seat key exists.
    """
    if isinstance(member, str):
        if not member.strip():
            raise ValueError("member id must be a non-empty string")
        return member.strip()
    seat_key = getattr(member, "seat_key", None)
    role = getattr(member, "role", None)
    if isinstance(member, Mapping):
        seat_key = seat_key or member.get("seat_key")
        role = role or member.get("role")
    if seat_key:
        return str(seat_key)
    if role:
        return f"role:{role}"
    raise ValueError(
        "cannot resolve a member id — expected a CrewMember "
        "(seat_key/role), a mapping, or a non-empty string"
    )


def set_mastery(member: Any, skill_id: str, rank: str) -> Dict[str, str]:
    """Record that a member holds a skill at a rank.

    Fails LOUDLY on unknown skills and on ranks outside the skill's
    ladder (invariant 1). Rank matching is case-insensitive; the stored
    value is the canonical ladder name. Returns a receipt dict.
    """
    member_id = member_id_for(member)
    pool = get_pool()
    skill = pool.get(skill_id)
    if skill is None:
        raise ValueError(f"unknown skill {skill_id!r} — cannot set mastery")
    rung = str(rank or "").upper().strip()
    if rung not in RANKS:
        raise ValueError(
            f"rank {rank!r} is outside the ladder {RANKS} "
            f"for skill {skill_id!r} — mastery refused"
        )
    _MASTERY.setdefault(member_id, {})[skill_id] = rung
    return {
        "member_id": member_id,
        "skill_id": skill_id,
        "rank": rung,
        "status": "set",
    }


def mastery_for(member: Any, skill_id: str) -> Optional[str]:
    """The rank a member holds a skill at; None when the member does
    not hold it (or the member is unknown)."""
    member_id = member_id_for(member)
    return _MASTERY.get(member_id, {}).get(skill_id)


def executable_skills(member: Any) -> List[Dict[str, Any]]:
    """What the member can execute: every held skill, shaped to the
    member's own rank (``active_rank`` + ``rank_description``), plus a
    ``mastery_rank`` field. Members with no recorded mastery get []."""
    member_id = member_id_for(member)
    pool = get_pool()
    held = _MASTERY.get(member_id, {})
    out = []
    for skill_id, rank in sorted(held.items()):
        shaped = pool.skill_at(skill_id, rank)
        shaped["mastery_rank"] = rank
        out.append(shaped)
    return out


def clear_mastery(member: Any, skill_id: Optional[str] = None) -> Dict[str, Any]:
    """Forget mastery: one skill, or the whole member record when
    ``skill_id`` is None. Returns what was cleared."""
    member_id = member_id_for(member)
    held = _MASTERY.get(member_id, {})
    if skill_id is None:
        cleared = sorted(held)
        _MASTERY.pop(member_id, None)
    else:
        cleared = [skill_id] if held.pop(skill_id, None) is not None else []
        if not held:
            _MASTERY.pop(member_id, None)
    return {"member_id": member_id, "cleared": cleared}


def dump() -> Dict[str, Dict[str, str]]:
    """Serialize the whole mastery registry to JSON-able data."""
    return {m: dict(skills) for m, skills in _MASTERY.items()}


def load(data: Mapping[str, Mapping[str, str]]) -> Dict[str, int]:
    """Restore mastery from ``dump()`` output. Every entry is
    re-validated through ``set_mastery`` — corrupt data fails loudly.
    Returns {"members": n, "entries": m}."""
    reset()
    members = entries = 0
    for member_id, skills in data.items():
        members += 1
        for skill_id, rank in skills.items():
            set_mastery(member_id, skill_id, rank)
            entries += 1
    return {"members": members, "entries": entries}


def reset() -> None:
    """Empty the registry. Test seam — not for production use."""
    _MASTERY.clear()
