"""bridging_layer — disagreement-bridging legitimacy without a moderator.

Studied from: giant-patterns-hunt-20260916-0016 (report.md [Additions 2]).
Load-bearing idea: rank claims by how well they bridge disagreement —
approved across divided groups — so legitimacy comes from bridging
consensus, not from a central moderator.

LEVI's take: ``BridgingLayer`` collects ``Statement``s and ``Response``s
(agree / disagree / pass) from named groups (any partition the user
defines: cohorts, feeds, communities). A statement's *bridging score* is
the geometric mean of group approval rates, discounted by polarization —
so a claim loved by one side and loathed by the other scores low even if
its raw total is high. Imported feeds merge as labeled items with their
source attached, so provenance stays visible.

The scoring is an explicit heuristic (documented in ``explain``), not a
claim about truth — it surfaces what bridges, not what is correct.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional


ORIGIN = "levi-revival/bridging-layer"

AGREE = "agree"
DISAGREE = "disagree"
PASS = "pass"
VERDICTS = (AGREE, DISAGREE, PASS)


@dataclass
class Response:
    group: str
    verdict: str
    voter: str = ""


@dataclass
class Statement:
    id: str
    text: str
    author: str
    source: str = "local"  # provenance: local | <imported feed name>
    responses: List[Response] = field(default_factory=list)


@dataclass
class BridgingScore:
    statement_id: str
    score: float
    group_approvals: Dict[str, float]
    polarization: float
    n_responses: int

    def explain(self) -> str:
        lines = [
            f"bridging score {self.score:.3f} over {self.n_responses} responses",
            "group approvals:",
        ]
        for g, a in sorted(self.group_approvals.items()):
            lines.append(f"  {g}: {a:.2f}")
        lines.append(f"polarization discount: {self.polarization:.2f}")
        lines.append(
            "heuristic: geometric mean of group approvals × (1 − polarization);"
            " surfaces what bridges disagreement, not what is true."
        )
        return "\n".join(lines)


class BridgingLayer:
    """Statements ranked by cross-group bridging, not raw popularity."""

    def __init__(self) -> None:
        self.statements: Dict[str, Statement] = {}

    # -- authoring ------------------------------------------------------------

    def propose(self, text: str, author: str, source: str = "local") -> Statement:
        s = Statement(
            id=f"st-{uuid.uuid4().hex[:8]}",
            text=text,
            author=author,
            source=source,
        )
        self.statements[s.id] = s
        return s

    def import_feed(
        self, feed_name: str, items: List[Dict[str, str]]
    ) -> List[Statement]:
        """Merge an imported feed as labeled statements; source stays visible."""
        made = []
        for it in items:
            made.append(
                self.propose(
                    text=it.get("text", ""),
                    author=it.get("author", "unknown"),
                    source=feed_name,
                )
            )
        return made

    # -- responding -----------------------------------------------------------

    def respond(
        self, statement_id: str, group: str, verdict: str, voter: str = ""
    ) -> Response:
        if verdict not in VERDICTS:
            raise ValueError(f"verdict must be one of {VERDICTS}")
        s = self.statements[statement_id]
        r = Response(group=group, verdict=verdict, voter=voter)
        s.responses.append(r)
        return r

    # -- bridging -------------------------------------------------------------

    def score(self, statement_id: str) -> BridgingScore:
        s = self.statements[statement_id]
        by_group: Dict[str, List[str]] = {}
        for r in s.responses:
            by_group.setdefault(r.group, []).append(r.verdict)
        approvals: Dict[str, float] = {}
        for g, verdicts in by_group.items():
            decided = [v for v in verdicts if v != PASS]
            approvals[g] = (
                sum(1 for v in decided if v == AGREE) / len(decided) if decided else 0.0
            )
        if not approvals:
            return BridgingScore(statement_id, 0.0, {}, 0.0, 0)
        vals = list(approvals.values())
        geo = math.exp(sum(math.log(max(v, 1e-9)) for v in vals) / len(vals))
        polarization = (max(vals) - min(vals)) if len(vals) > 1 else 0.0
        final = geo * (1.0 - polarization)
        return BridgingScore(
            statement_id=statement_id,
            score=max(final, 0.0),
            group_approvals=approvals,
            polarization=polarization,
            n_responses=len(s.responses),
        )

    def consensus_feed(self, limit: Optional[int] = None) -> List[BridgingScore]:
        ranked = sorted(
            (self.score(sid) for sid in self.statements),
            key=lambda b: -b.score,
        )
        return ranked[:limit] if limit is not None else ranked

    def contested(self, threshold: float = 0.4) -> List[BridgingScore]:
        """Statements with high polarization: the live disagreements."""
        return [b for b in self.consensus_feed() if b.polarization >= threshold]

    # -- snapshots ------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            sid: {
                "id": s.id,
                "text": s.text,
                "author": s.author,
                "source": s.source,
                "responses": [asdict(r) for r in s.responses],
            }
            for sid, s in self.statements.items()
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BridgingLayer":
        layer = cls()
        for sid, s in d.items():
            layer.statements[sid] = Statement(
                id=s["id"],
                text=s["text"],
                author=s["author"],
                source=s.get("source", "local"),
                responses=[Response(**r) for r in s.get("responses", [])],
            )
        return layer
