"""Ability unlock registry (L13).

Penalties need something concrete to revoke, so abilities live here:
a minimal registry — ability id, level required, super tokens granted
on unlock. Unlocks are earned through the level path only; attempts
to unlock outside the scoring path are blocked fail-closed and (when
found in the record) revoked by the anti-cheat.

An unlock grants super tokens into the EARNED pool (they stack per
the token canon). Base weekly tokens are a separate concern and are
never minted or confiscated here.
"""

from __future__ import annotations

from .adjudication import (
    active_abilities,
    append_adj,
    earned_tokens,
)

# ability id, required level, name, super tokens granted on unlock.
# Kept minimal on purpose: penalties need concrete unlockables to
# revoke, not a full skill tree. Chauncey names the abilities; these
# provisional ids stand until he rules.
ABILITIES: tuple[dict, ...] = (
    {
        "id": "keen-ears",
        "level_required": 2,
        "name": "Keen Ears",
        "tokens": 10,
        "blurb": "Holds the thread of a conversation across sessions.",
    },
    {
        "id": "second-wind",
        "level_required": 3,
        "name": "Second Wind",
        "tokens": 15,
        "blurb": "Keeps training momentum through hard question sets.",
    },
    {
        "id": "deep-diver",
        "level_required": 4,
        "name": "Deep Diver",
        "tokens": 20,
        "blurb": "Tackles multi-step chains without losing the plot.",
    },
    {
        "id": "legion-chorus",
        "level_required": 5,
        "name": "Legion Chorus",
        "tokens": 25,
        "blurb": "Coordinates across Legion personas in one reply.",
    },
)

_BY_ID = {a["id"]: a for a in ABILITIES}


def get_ability(ability_id: str) -> dict:
    if ability_id not in _BY_ID:
        raise ValueError("unknown ability %r" % (ability_id,))
    return _BY_ID[ability_id]


def maybe_unlock(entity: str, effective_exp: int) -> list[dict]:
    """Unlock every ability whose level requirement is now met.

    Returns the unlock receipts written (empty when nothing new).
    Called after legitimate awards; the anti-cheat never calls this —
    it only revokes. Grants super tokens into the earned pool.
    """
    from .levels import level_for

    current = set(active_abilities(entity))
    level = level_for(effective_exp)
    granted: list[dict] = []
    for a in ABILITIES:
        if a["id"] in current:
            continue
        if level < a["level_required"]:
            continue
        receipt = append_adj(
            "unlock",
            entity,
            {
                "ability_id": a["id"],
                "level_required": a["level_required"],
                "level_at_unlock": level,
                "effective_exp": effective_exp,
            },
        )
        granted.append(receipt)
        append_adj(
            "token-grant",
            entity,
            {
                "tokens": a["tokens"],
                "reason": "unlock:%s" % a["id"],
            },
        )
    return granted


def ability_status(entity: str) -> dict:
    """Provisional-until-Chauncey-rules status snapshot."""
    return {
        "entity": entity,
        "active": active_abilities(entity),
        "earned_super_tokens": earned_tokens(entity),
        "registry": [
            {
                "id": a["id"],
                "level_required": a["level_required"],
                "active": a["id"] in active_abilities(entity),
            }
            for a in ABILITIES
        ],
    }
