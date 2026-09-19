"""Team combination — catalogue agents join agent teams, combining with his force.

A ForceTeam is a named crew. Seats are either native members or
catalogue attachments (an outside provider's agent filling a role).
``from_record`` adapts any external team mapping (id/name/members) so
catalogue agents can attach to teams managed elsewhere — the catalogue
never rewrites those teams, it only records its own attachments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional


@dataclass
class TeamSeat:
    """One seat on a team: a native member or a catalogue attachment."""

    member_ref: str  # native agent id, or the catalogue entry id
    kind: str = "native"  # "native" | "catalogue"
    role: str = ""

    def __post_init__(self) -> None:
        if self.kind not in ("native", "catalogue"):
            raise ValueError(f"seat kind must be 'native' or 'catalogue', got {self.kind!r}")
        if not self.member_ref:
            raise ValueError("seat member_ref must be non-empty")

    def to_dict(self) -> Dict:
        return {"member_ref": self.member_ref, "kind": self.kind, "role": self.role}


class ForceTeam:
    """A named crew catalogue agents can attach to."""

    def __init__(self, team_id: str, name: str = "") -> None:
        if not team_id or not isinstance(team_id, str):
            raise ValueError("team_id must be a non-empty string")
        self.id = team_id
        self.name = name or team_id
        self._seats: List[TeamSeat] = []

    @staticmethod
    def from_record(raw: Mapping) -> "ForceTeam":
        """Adapt an external team record (any mapping with id/name/members)."""
        team = ForceTeam(team_id=str(raw["id"]), name=str(raw.get("name", raw["id"])))
        for m in raw.get("members", []) or []:
            team._seats.append(TeamSeat(member_ref=str(m), kind="native"))
        return team

    def attach_catalogue_agent(
        self, entry_id: str, role: str = "", known_entry_ids: Optional[set] = None
    ) -> TeamSeat:
        """Seat a catalogue agent on this team under a role."""
        if known_entry_ids is not None and entry_id not in known_entry_ids:
            raise KeyError(f"unknown catalogue entry {entry_id!r}")
        if any(s.kind == "catalogue" and s.member_ref == entry_id for s in self._seats):
            raise ValueError(f"entry {entry_id!r} is already attached to team {self.id!r}")
        seat = TeamSeat(member_ref=entry_id, kind="catalogue", role=role)
        self._seats.append(seat)
        return seat

    def detach(self, member_ref: str) -> bool:
        """Remove a seat. True when something was removed."""
        before = len(self._seats)
        self._seats = [s for s in self._seats if s.member_ref != member_ref]
        return len(self._seats) < before

    def seats(self) -> List[TeamSeat]:
        return list(self._seats)

    def catalogue_agents(self) -> List[TeamSeat]:
        return [s for s in self._seats if s.kind == "catalogue"]

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "seats": [s.to_dict() for s in self._seats],
        }

    @staticmethod
    def from_dict(raw: Dict) -> "ForceTeam":
        team = ForceTeam(team_id=raw["id"], name=raw.get("name", ""))
        for s in raw.get("seats", []) or []:
            team._seats.append(
                TeamSeat(
                    member_ref=s["member_ref"],
                    kind=s.get("kind", "native"),
                    role=s.get("role", ""),
                )
            )
        return team
