"""Course-platform query API — stdlib only.

The platform is the infrastructure that delivers the curriculum: one clean
query surface consumed by LEVI/agents, the CLI today, and a web UI later.
Editions and tracks are first-class concepts; the growth pipeline is the
platform's content engine; agent teams get scoped views plus a learning
loop that feeds validated field learnings back into the corpus.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.sidewinder.curriculum import growth
from levi.sidewinder.curriculum.corpus import Corpus, format_entry, load_corpus
from levi.sidewinder.curriculum.editions import (
    edition_corpus,
    format_edition,
    list_editions,
    load_manifests,
)
from levi.sidewinder.curriculum.progressions import (
    format_learning_path,
    format_progression,
    learning_path,
    progression,
    track_counts,
)
from levi.sidewinder.platform import loop as loop_mod
from levi.sidewinder.platform.teams import Team, TeamRegistry, format_teams, team_corpus


class CoursePlatform:
    """Queryable infrastructure over the course curriculum."""

    def __init__(
        self,
        corpus: Optional[Corpus] = None,
        manifests_dir: Optional[Path] = None,
        teams_path: Optional[Path] = None,
    ):
        self._corpus = corpus or load_corpus()
        self._manifests = load_manifests(manifests_dir, corpus=self._corpus)
        self._teams = TeamRegistry(teams_path, known_editions=set(self._manifests))
        self._learning_engine = None

    # ── views ──────────────────────────────────────────────────────
    def _view(self, edition: Optional[str] = None, team: Optional[str] = None) -> Corpus:
        if team is not None:
            return self.team_view(team)
        if edition is not None:
            return self.edition_view(edition)
        return self._corpus

    def edition_view(self, edition_id: str) -> Corpus:
        try:
            manifest = self._manifests[edition_id]
        except KeyError:
            raise KeyError(
                f"unknown edition {edition_id!r} (want one of {', '.join(self.edition_ids())})"
            ) from None
        return edition_corpus(self._corpus, manifest)

    def team_view(self, team_id: str) -> Corpus:
        return team_corpus(self._corpus, self._manifests, self._teams.get(team_id))

    # ── query ──────────────────────────────────────────────────────
    def search(
        self,
        query: str,
        domain: Optional[str] = None,
        track: Optional[str] = None,
        edition: Optional[str] = None,
        team: Optional[str] = None,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        return self._view(edition, team).search(query, domain=domain, track=track, limit=limit)

    def get(
        self,
        entry_id: str,
        edition: Optional[str] = None,
        team: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        return self._view(edition, team).get(entry_id)

    def manual(
        self,
        domain: Optional[str] = None,
        track: Optional[str] = None,
        edition: Optional[str] = None,
        team: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        entries = self._view(edition, team).entries
        if domain:
            entries = [e for e in entries if e["domain"] == domain]
        if track:
            entries = [e for e in entries if track in e["tracks"]]
        return sorted(entries, key=lambda e: e["id"])

    # ── curriculum ─────────────────────────────────────────────────
    def track_counts(
        self, edition: Optional[str] = None, team: Optional[str] = None
    ) -> Dict[str, int]:
        return track_counts(self._view(edition, team))

    def progression(
        self, track: str, edition: Optional[str] = None, team: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        return progression(self._view(edition, team), track)

    def learning_path(
        self, entry_id: str, edition: Optional[str] = None, team: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        return learning_path(self._view(edition, team), entry_id)

    # ── editions ──────────────────────────────────────────────────
    def edition_ids(self) -> List[str]:
        return list_editions(self._manifests)

    def edition_manifest(self, edition_id: str) -> Dict[str, Any]:
        try:
            return self._manifests[edition_id]
        except KeyError:
            raise KeyError(
                f"unknown edition {edition_id!r} (want one of {', '.join(self.edition_ids())})"
            ) from None

    # ── teams ──────────────────────────────────────────────────────
    def list_teams(self) -> List[Team]:
        return self._teams.list_teams()

    def team(self, team_id: str) -> Team:
        return self._teams.get(team_id)

    # ── content engine ─────────────────────────────────────────────
    def grow(self, **kwargs) -> Dict[str, Any]:
        """Run the batch growth pipeline (validate → dedup → append)."""
        return growth.grow(**kwargs)

    def emit_stubs(self, n: int, **kwargs) -> Dict[str, Any]:
        return growth.write_stubs(n, **kwargs)

    # ── team learning loop ─────────────────────────────────────────
    def harvest(
        self, team_id: str, entries: List[Dict[str, Any]], intake_dir: Optional[Path] = None
    ) -> Dict[str, Any]:
        self._teams.get(team_id)  # unknown teams cannot harvest
        return loop_mod.harvest(team_id, entries, intake_dir=intake_dir)

    def review_intake(
        self,
        team_id: str,
        intake_dir: Optional[Path] = None,
        corpus_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        self._teams.get(team_id)
        return loop_mod.review_intake(team_id, intake_dir=intake_dir, corpus_dir=corpus_dir)

    def promote_intake(
        self,
        team_id: str,
        intake_dir: Optional[Path] = None,
        corpus_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        self._teams.get(team_id)
        return loop_mod.promote_intake(
            team_id, intake_dir=intake_dir, corpus_dir=corpus_dir
        )

    # ── learning engine (canon: life coach is its sub-engine) ──────────
    @property
    def learning_engine(self):
        """The platform's learning layer as an explicit engine.

        Additive: the query API above is untouched. The engine wraps this
        platform and owns the life-coach sub-engine; personal-refinement
        work is delegated down through it.
        """
        if self._learning_engine is None:
            from levi.sidewinder.platform.learning_engine import LearningEngine

            self._learning_engine = LearningEngine(platform=self)
        return self._learning_engine

    def refine(self, *args, **kwargs) -> Dict[str, Any]:
        """Personal refinement — delegated to the learning engine's
        life-coach sub-engine. ``refine(entry_id=...)`` or
        ``refine(edition=...)``."""
        return self.learning_engine.refine(*args, **kwargs)

    # ── formatting (text surfaces) ─────────────────────────────────
    def format_entry(self, entry: Dict[str, Any]) -> str:
        return format_entry(entry)

    def format_progression(
        self, track: str, edition: Optional[str] = None, team: Optional[str] = None
    ) -> str:
        return format_progression(self._view(edition, team), track)

    def format_learning_path(
        self, entry_id: str, edition: Optional[str] = None, team: Optional[str] = None
    ) -> str:
        return format_learning_path(self._view(edition, team), entry_id)

    def format_edition(self, edition_id: str) -> str:
        return format_edition(self._corpus, self.edition_manifest(edition_id))

    def format_teams(self) -> str:
        return format_teams(self.list_teams())
