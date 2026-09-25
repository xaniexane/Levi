"""The open creator ladder: democratic front pages, earned reputation.

Studied from: victims-of-giants-20260916-0017/report.md (Resurrection shortlist #14)

The mechanism:

* **Works** are posted by creators and carry *cross-domain badges*
  (e.g. "story", "code", "visual") so reputation is not siloed.
* **Votes** are simple signed ballots: each voter may vote once per work,
  and may change or retract the ballot. Vote counts are public.
* **The ladder** is a transparent promotion track: works cross *rungs*
  (fixed score thresholds) in the open, and the top rung feeds a
  **democratic front page** — slots filled by score order with
  deterministic tie-breaking, no hidden ranking.

Honest limit: scores are plain sums of ballots with an explicit,
configurable per-voter weight cap. There is no anti-fraud engine, no
identity verification, and no recommendation model — the ledger is
transparent instead of clever.

stdlib-only. No network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple


ORIGIN = "levi-revival/creator-ladder"


@dataclass
class Work:
    """A creator's posted work, eligible for votes and the ladder."""

    work_id: str
    creator: str
    title: str
    badges: List[str] = field(default_factory=list)
    posted_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class Ladder:
    """Transparent promotion track, vote ledger, and democratic front page."""

    rungs: List[Tuple[str, int]] = field(default_factory=list)  # (name, min score)
    works: Dict[str, Work] = field(default_factory=dict)
    ballots: Dict[str, Dict[str, int]] = field(
        default_factory=dict
    )  # work_id -> voter -> +1/-1

    def __post_init__(self) -> None:
        if not self.rungs:
            self.rungs = [("noticed", 3), ("rising", 10), ("front-page", 25)]

    # -- works -----------------------------------------------------------
    def post(
        self, work_id: str, creator: str, title: str, badges: Optional[List[str]] = None
    ) -> Work:
        work_id = (work_id or "").strip()
        if not work_id:
            raise ValueError("work_id must be non-empty")
        if work_id in self.works:
            raise ValueError(f"work already posted: {work_id!r}")
        if not creator or not creator.strip():
            raise ValueError("creator must be non-empty")
        work = Work(
            work_id=work_id,
            creator=creator.strip(),
            title=title,
            badges=list(badges or []),
        )
        self.works[work_id] = work
        self.ballots[work_id] = {}
        return work

    # -- voting ------------------------------------------------------------
    def vote(self, work_id: str, voter: str, value: int) -> int:
        """Cast or change a ballot (+1 or -1). Returns the new score."""
        self._work(work_id)
        voter = (voter or "").strip()
        if not voter:
            raise ValueError("voter must be non-empty")
        if value not in (1, -1):
            raise ValueError("ballot must be +1 or -1")
        if self.works[work_id].creator == voter:
            raise ValueError("creators cannot vote on their own work")
        self.ballots[work_id][voter] = value
        return self.score(work_id)

    def retract(self, work_id: str, voter: str) -> int:
        """Withdraw a ballot. Returns the new score."""
        self._work(work_id)
        if voter not in self.ballots[work_id]:
            raise KeyError(f"no ballot from {voter!r}")
        del self.ballots[work_id][voter]
        return self.score(work_id)

    def score(self, work_id: str) -> int:
        return sum(self.ballots[self._work(work_id).work_id].values())

    # -- the ladder --------------------------------------------------------
    def rung_of(self, work_id: str) -> Optional[str]:
        """Highest rung whose threshold the work's score meets, or None."""
        self._work(work_id)
        score = self.score(work_id)
        reached: Optional[str] = None
        for name, minimum in sorted(self.rungs, key=lambda r: r[1]):
            if score >= minimum:
                reached = name
        return reached

    def front_page(self, slots: int = 5) -> List[Work]:
        """Democratic front page: highest scores first, ties broken by
        earliest posting, then by work_id — fully deterministic."""
        ranked = sorted(
            self.works.values(),
            key=lambda w: (-self.score(w.work_id), w.posted_at, w.work_id),
        )
        top_rung = self.rungs[-1][0] if self.rungs else None
        eligible = [
            w for w in ranked if top_rung is None or self.rung_of(w.work_id) == top_rung
        ]
        return eligible[: max(0, slots)]

    # -- reputation ----------------------------------------------------------
    def reputation(self, creator: str) -> Dict:
        """Cross-domain reputation: total score and per-badge breakdown."""
        total = 0
        by_badge: Dict[str, int] = {}
        works = 0
        for work in self.works.values():
            if work.creator != creator:
                continue
            works += 1
            s = self.score(work.work_id)
            total += s
            for badge in work.badges:
                by_badge[badge] = by_badge.get(badge, 0) + s
        return {
            "creator": creator,
            "works": works,
            "total_score": total,
            "by_badge": by_badge,
        }

    def _work(self, work_id: str) -> Work:
        if work_id not in self.works:
            raise KeyError(f"no such work: {work_id!r}")
        return self.works[work_id]


def open_ladder(rungs: Optional[List[Tuple[str, int]]] = None) -> Ladder:
    """Open a new creator ladder with explicit rung thresholds."""
    return Ladder(rungs=list(rungs) if rungs else [])
