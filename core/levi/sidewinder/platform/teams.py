"""Agent teams — team scoping over the curriculum, stdlib only.

A team is a named group of agents with assigned tracks and/or editions:

* a field crew assigned the First Responder edition,
* a build crew on the build/create tracks.

A team's view = the union of its editions' pack views (whole corpus when
no editions are assigned), narrowed to its assigned tracks (when any),
plus prerequisite closure so learning paths never dangle. Query and
curriculum calls accept a team context and run inside that view.

Teams are declared in ``teams.json`` (this directory); ``TeamRegistry``
loads them, validates tracks/editions, and supports register/save for
mechanical team management.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from levi.sidewinder import TRACKS
from levi.sidewinder.curriculum.corpus import Corpus
from levi.sidewinder.curriculum.editions import edition_ids
from levi.sidewinder.curriculum.scope import closure_ids

MODULE_DIR = Path(__file__).resolve().parent
TEAMS_FILE = MODULE_DIR / "teams.json"

_ID_RE = re.compile(r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z")


@dataclass
class Team:
    id: str
    name: str
    description: str = ""
    tracks: Tuple[str, ...] = ()
    editions: Tuple[str, ...] = ()
    members: Tuple[str, ...] = ()

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tracks": list(self.tracks),
            "editions": list(self.editions),
            "members": list(self.members),
        }

    @staticmethod
    def from_dict(raw: Dict) -> "Team":
        return Team(
            id=raw["id"],
            name=raw.get("name", raw["id"]),
            description=raw.get("description", ""),
            tracks=tuple(raw.get("tracks", ())),
            editions=tuple(raw.get("editions", ())),
            members=tuple(raw.get("members", ())),
        )


def validate_team(team: Team, known_editions: Optional[Set[str]] = None) -> List[str]:
    errors: List[str] = []
    if not isinstance(team.id, str) or not _ID_RE.match(team.id):
        errors.append(f"bad team id {team.id!r} (want lowercase slug)")
    if not isinstance(team.name, str) or not team.name.strip():
        errors.append("team name must be a non-empty string")
    bad_tracks = [t for t in team.tracks if t not in TRACKS]
    if bad_tracks:
        errors.append(f"unknown track(s): {', '.join(bad_tracks)}")
    if known_editions is not None:
        bad_ed = [e for e in team.editions if e not in known_editions]
        if bad_ed:
            errors.append(f"unknown edition(s): {', '.join(bad_ed)}")
    if not team.tracks and not team.editions:
        errors.append("a team must be assigned at least one track or edition")
    return errors


class TeamRegistry:
    """Teams loaded from ``teams.json``; register/save for management."""

    def __init__(self, path: Optional[Path] = None, known_editions: Optional[Set[str]] = None):
        self.path = path or TEAMS_FILE
        self.known_editions = known_editions
        self._teams: Dict[str, Team] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError(f"{self.path}: teams file must hold a JSON list")
        for item in raw:
            team = Team.from_dict(item)
            errors = validate_team(team, self.known_editions)
            if errors:
                raise ValueError(f"{self.path}: team {team.id}: " + "; ".join(errors))
            if team.id in self._teams:
                raise ValueError(f"{self.path}: duplicate team id {team.id!r}")
            self._teams[team.id] = team

    def list_teams(self) -> List[Team]:
        return [self._teams[k] for k in sorted(self._teams)]

    def get(self, team_id: str) -> Team:
        try:
            return self._teams[team_id]
        except KeyError:
            raise KeyError(
                f"unknown team {team_id!r} (want one of {', '.join(sorted(self._teams)) or 'none'})"
            ) from None

    def register(self, team: Team) -> None:
        errors = validate_team(team, self.known_editions)
        if errors:
            raise ValueError(f"team {team.id}: " + "; ".join(errors))
        self._teams[team.id] = team
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [t.to_dict() for t in self.list_teams()]
        self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _team_pool(corpus: Corpus, manifests: Dict[str, Dict], team: Team) -> List[Dict]:
    """Corpus entries plus the pack entries of the team's editions."""
    pool = list(corpus.entries)
    for eid in team.editions:
        pool.extend(manifests[eid].get("_entries", []))
    return pool


def team_entry_ids(
    corpus: Corpus, manifests: Dict[str, Dict], team: Team
) -> Set[str]:
    """Entry ids in a team's view: edition union (or whole corpus), narrowed
    to assigned tracks, plus prerequisite closure."""
    if team.editions:
        ids: Set[str] = set()
        for eid in team.editions:
            ids |= edition_ids(corpus, manifests[eid])
    else:
        ids = {e["id"] for e in corpus.entries}
    if team.tracks:
        tracks = set(team.tracks)
        by_id = {e["id"]: e for e in _team_pool(corpus, manifests, team)}
        ids = {eid for eid in ids if set(by_id[eid]["tracks"]) & tracks}
        ids = closure_ids(by_id, ids)
    return ids


def team_corpus(corpus: Corpus, manifests: Dict[str, Dict], team: Team) -> Corpus:
    """The team's scoped view as a Corpus (search/get/progressions work)."""
    ids = team_entry_ids(corpus, manifests, team)
    by_id = {e["id"]: e for e in _team_pool(corpus, manifests, team)}
    return Corpus([by_id[eid] for eid in ids if eid in by_id])


def format_teams(teams: List[Team]) -> str:
    lines = [f"{len(teams)} registered teams:"]
    for team in teams:
        scope = []
        if team.editions:
            scope.append("editions=" + ",".join(team.editions))
        if team.tracks:
            scope.append("tracks=" + ",".join(team.tracks))
        members = f" — members: {', '.join(team.members)}" if team.members else ""
        lines.append(f"  {team.id}  {team.name} ({'; '.join(scope) or 'unscoped'}){members}")
        if team.description:
            lines.append(f"    {team.description}")
    return "\n".join(lines)
