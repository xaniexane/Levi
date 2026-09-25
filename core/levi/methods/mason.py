"""The Mason's Word and masons' marks: operative lodge authentication.

Origin: medieval operative lodges combined practical marks with secret
recognition. Banker marks identified which mason dressed each stone for
piece-rate pay; assembly marks were installation instructions. In
16th-century Scotland, lodges added the "Mason Word" — a secret word and
grip — and the 1598 Schaw Statutes required every admitted mason to enter
his name and mark in a register.

What it is in LEVI: two-tier signaling, enforced as two separate calls.
MembershipAuth issues membership tokens (the Word): a token authenticates
identity — it proves the bearer is a member — and certifies nothing about
skill. Skill is proven only by a separate practical demonstration ("hew
the stone on the spot"), recorded per member per skill. Work marks
attribute each finished piece to a member, so piece-rate pay can be
computed from the ledger. Verifying a token never certifies competence.

Honesty label: LOAD-BEARING — separating authentication-of-identity from
proof-of-skill is a concrete, transferable mechanism.

Deny-closed inputs: empty names or marks, duplicate names or marks,
unknown member ids, unknown token words, and competence claims with no
recorded demonstration are all rejected with ValueError.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

__all__ = [
    "Member",
    "MembershipToken",
    "Demonstration",
    "Piece",
    "MembershipAuth",
]


def _require_text(value: object, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{what} must be a non-empty string")
    return value.strip()


@dataclass
class Member:
    """A lodge member: name and personal mark, entered in the register."""

    id: str
    name: str
    mark: str


@dataclass
class MembershipToken:
    """The Word: proves membership (identity), not skill."""

    word: str
    member_id: str


@dataclass
class Demonstration:
    """A practical demonstration: skill proven on the spot, separately."""

    member_id: str
    skill: str


@dataclass
class Piece:
    """A finished work-piece attributed to a member for piece-rate pay."""

    id: str
    member_id: str
    description: str


class MembershipAuth:
    """Two-tier lodge signaling: membership tokens, skill proofs, work marks.

    Tier one (``issue_word``/``authenticate``) answers "is this person a
    member?" Tier two (``demonstrate``/``competent``) answers "can this
    person do the work?" — and only a recorded demonstration answers yes.
    """

    def __init__(self) -> None:
        self._members: dict[str, Member] = {}
        self._words: dict[str, str] = {}  # word -> member id
        self._demonstrations: dict[str, set[str]] = {}  # member id -> skills
        self._pieces: dict[str, Piece] = {}

    # -- the register ------------------------------------------------------
    def register(self, name: str, mark: str) -> Member:
        """Enter a name and mark in the register (Schaw Statutes, 1598)."""
        name = _require_text(name, "member name")
        mark = _require_text(mark, "member mark")
        if any(m.name.lower() == name.lower() for m in self._members.values()):
            raise ValueError(f"duplicate member name: {name!r}")
        if any(m.mark == mark for m in self._members.values()):
            raise ValueError(f"duplicate member mark: {mark!r}")
        member = Member(id=uuid.uuid4().hex[:12], name=name, mark=mark)
        self._members[member.id] = member
        self._demonstrations[member.id] = set()
        return member

    def member(self, member_id: str) -> Member:
        member = self._members.get(member_id)
        if member is None:
            raise ValueError(f"unknown member: {member_id!r}")
        return member

    # -- tier one: the Word (membership, not skill) -------------------------
    def issue_word(self, member_id: str) -> MembershipToken:
        """Give a member their secret word: it proves membership only."""
        self.member(member_id)  # deny-closed on unknown members
        word = "MASON-" + uuid.uuid4().hex[:8].upper()
        self._words[word] = member_id
        return MembershipToken(word=word, member_id=member_id)

    def authenticate(self, word: str) -> Member:
        """The Word admits a member — and says nothing about their skill."""
        member_id = self._words.get(word)
        if member_id is None:
            raise ValueError("unknown word: no such member (a cowan, perhaps)")
        return self._members[member_id]

    # -- tier two: hew the stone on the spot --------------------------------
    def demonstrate(self, member_id: str, skill: str) -> Demonstration:
        """Record a practical demonstration of a skill, witnessed now."""
        self.member(member_id)
        skill = _require_text(skill, "skill")
        self._demonstrations[member_id].add(skill.lower())
        return Demonstration(member_id=member_id, skill=skill)

    def competent(self, member_id: str, skill: str) -> bool:
        """Skill is proven only by a recorded demonstration — never by the Word."""
        self.member(member_id)
        skill = _require_text(skill, "skill")
        return skill.lower() in self._demonstrations[member_id]

    # -- banker marks: piece-rate pay ---------------------------------------
    def attribute_piece(self, piece_id: str, member_id: str, description: str) -> Piece:
        """Mark a finished piece with its maker's mark, for piece-rate pay."""
        piece_id = _require_text(piece_id, "piece id")
        description = _require_text(description, "piece description")
        self.member(member_id)
        if piece_id in self._pieces:
            raise ValueError(f"duplicate piece id: {piece_id!r}")
        piece = Piece(id=piece_id, member_id=member_id, description=description)
        self._pieces[piece_id] = piece
        return piece

    def pieces_of(self, member_id: str) -> list[Piece]:
        """Every piece carrying this member's mark."""
        self.member(member_id)
        return [p for p in self._pieces.values() if p.member_id == member_id]

    def pay_ledger(self) -> dict[str, int]:
        """Piece-rate pay: member name -> count of attributed pieces."""
        ledger: dict[str, int] = {}
        for piece in self._pieces.values():
            name = self._members[piece.member_id].name
            ledger[name] = ledger.get(name, 0) + 1
        return ledger

    def summary(self) -> dict:
        return {
            "members": len(self._members),
            "words_issued": len(self._words),
            "pieces": len(self._pieces),
        }
