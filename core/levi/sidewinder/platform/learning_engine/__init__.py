"""The LEARNING ENGINE — the platform's learning layer as an explicit engine.

Chauncey's canon: "life coach was sub engine of learning engine."

The learning engine is the platform's learning layer: curriculum delivery,
the team learning loop, and the growth pipeline — the engine that trains
agents and teams. It wraps the CoursePlatform query API (additive; nothing
in the existing API changes) and owns exactly one sub-engine:

* ``life_coach`` — personal refinement tooling. Nested module boundary:
  ``levi.sidewinder.platform.learning_engine.life_coach`` — not standalone,
  not a sibling of the engine. It consumes the career packs' team/skill
  outputs and turns them into personal refinement plans, drills, and
  checklists. The learning engine delegates all personal-refinement work
  to it; nothing else in the platform reaches past the engine to the coach.

Stdlib only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.sidewinder.platform.learning_engine.life_coach import LifeCoach


class LearningEngine:
    """The engine that trains agents and teams.

    Wraps a ``CoursePlatform`` (built when not supplied) and exposes the
    learning layer as one surface: delivery (search/get/manual,
    progressions, learning paths, edition and team views), the team
    learning loop (harvest -> review -> promote), the growth pipeline
    (content engine), and personal refinement — delegated to the
    life-coach sub-engine at ``self.life_coach``.
    """

    def __init__(self, platform=None, identity=None):
        # Imported lazily: api.py reaches back here through a property, so
        # the engine must never import the platform API at module top.
        if platform is None:
            from levi.sidewinder.platform.api import CoursePlatform

            platform = CoursePlatform()
        self.platform = platform
        # Identity record (dict, as stored by levi.cybrus.identity) of the
        # caller. Drives founder-gating in the life-coach sub-engine:
        # absent/None (the default) means restricted — the deep
        # DemandPulse-derived sensing stays off unless the record wears
        # the founder tier. Callers holding an IdentityStore pass
        # store.get(name).
        self.identity_record = identity
        self.life_coach = LifeCoach(self)

    # ── curriculum delivery (delegated to the platform) ──────────────
    def search(self, *args, **kwargs) -> List[Dict[str, Any]]:
        return self.platform.search(*args, **kwargs)

    def get(self, *args, **kwargs) -> Optional[Dict[str, Any]]:
        return self.platform.get(*args, **kwargs)

    def manual(self, *args, **kwargs) -> List[Dict[str, Any]]:
        return self.platform.manual(*args, **kwargs)

    def track_counts(self, *args, **kwargs) -> Dict[str, int]:
        return self.platform.track_counts(*args, **kwargs)

    def progression(self, *args, **kwargs) -> List[Dict[str, Any]]:
        return self.platform.progression(*args, **kwargs)

    def learning_path(self, *args, **kwargs) -> List[Dict[str, Any]]:
        return self.platform.learning_path(*args, **kwargs)

    def edition_ids(self) -> List[str]:
        return self.platform.edition_ids()

    def edition_manifest(self, *args, **kwargs) -> Dict[str, Any]:
        return self.platform.edition_manifest(*args, **kwargs)

    def edition_view(self, *args, **kwargs):
        return self.platform.edition_view(*args, **kwargs)

    def team_view(self, *args, **kwargs):
        return self.platform.team_view(*args, **kwargs)

    def list_teams(self, *args, **kwargs):
        return self.platform.list_teams(*args, **kwargs)

    def team(self, *args, **kwargs):
        return self.platform.team(*args, **kwargs)

    # ── team learning loop ──────────────────────────────────────────
    def harvest(self, *args, **kwargs) -> Dict[str, Any]:
        return self.platform.harvest(*args, **kwargs)

    def review_intake(self, *args, **kwargs) -> Dict[str, Any]:
        return self.platform.review_intake(*args, **kwargs)

    def promote_intake(self, *args, **kwargs) -> Dict[str, Any]:
        return self.platform.promote_intake(*args, **kwargs)

    # ── growth pipeline (content engine) ────────────────────────────
    def grow(self, *args, **kwargs) -> Dict[str, Any]:
        return self.platform.grow(*args, **kwargs)

    def emit_stubs(self, *args, **kwargs) -> Dict[str, Any]:
        return self.platform.emit_stubs(*args, **kwargs)

    # ── personal refinement: delegated to the sub-engine ────────────
    def refine(
        self,
        entry_id: Optional[str] = None,
        edition: Optional[str] = None,
        team: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Personal refinement, via the life-coach sub-engine.

        ``entry_id`` refines one entry into a practice plan;
        ``edition`` refines a whole career pack into a refinement program.
        """
        if entry_id is not None:
            return self.life_coach.refine_plan(entry_id, team=team)
        if edition is not None:
            return self.life_coach.career_refinement(edition, team=team, limit=limit)
        raise ValueError("refine() needs entry_id or edition")

    def format_plan(self, plan: Dict[str, Any]) -> str:
        return self.life_coach.format_plan(plan)

    def opportunities(
        self,
        edition: Optional[str] = None,
        team: Optional[str] = None,
        limit: int = 10,
        user_signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """DemandPulse pattern, life-coach persona: scan -> score -> surface.

        Delegates to the life-coach sub-engine. See
        ``LifeCoach.opportunities`` for the signal sources and the
        ``user_signals`` seam.
        """
        return self.life_coach.opportunities(
            edition=edition, team=team, limit=limit, user_signals=user_signals
        )

    def format_opportunities(self, result: Dict[str, Any]) -> str:
        return self.life_coach.format_opportunities(result)


__all__ = ["LearningEngine", "LifeCoach"]
