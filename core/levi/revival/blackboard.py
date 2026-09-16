"""revival/blackboard.py — Hearsay-II style shared hypothesis surface.

Revival of: the Hearsay-II blackboard architecture (Erman, Hayes-Roth,
Lesser & Reddy, 1980).

Why it matters: instead of a fixed pipeline (stage 1 -> stage 2 -> stage 3),
independent knowledge sources (KSs) watch a shared blackboard, bid to act when
they see something they can contribute to, and post hypotheses back. Control is
opportunistic: the highest-bid KS runs next. This fits multi-stage agent work
where you don't know in advance which analysis will be useful — classification,
enrichment, summarization, verification all compete for attention on evidence.

LEVI adaptation:
- ``Blackboard.post_hypothesis(topic, content, confidence, source)`` posts a
  hypothesis; nothing is ever silently overwritten.
- ``register_ks(name, interests, action, bid=None)`` registers a knowledge
  source with interest patterns (exact topic, "*" wildcard, or a predicate).
- ``bid()`` / ``run_cycle()``: every KS bids on the current board; the
  highest bidder's action runs. ``run_until()`` loops until no KS wants to act.
- Conflict handling: competing hypotheses on the same topic COEXIST, each with
  its confidence; ``conflicts()`` surfaces the competing pairs and ``best()``
  picks the highest-confidence one. Overwrite-by-construction is a bug this
  module refuses to have.

Honest limits:
- Bidding is only as smart as the bid functions; the default bid is "I see new
  matching hypotheses". Cycles are bounded by ``run_until(max_cycles)``.
- This is in-process and synchronous: no distributed blackboard, no truth
  maintenance beyond supersede links. Confidence values are whatever the KSs
  claim — the board does not calibrate them.
"""

from __future__ import annotations

import itertools
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class Hypothesis:
    id: int
    topic: str
    content: Any
    confidence: float
    source: str
    at: float
    supersedes: Optional[int] = None

    def __post_init__(self) -> None:
        if not self.topic or not isinstance(self.topic, str):
            raise ValueError("topic must be a non-empty string")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")


@dataclass
class _KnowledgeSource:
    name: str
    interests: List[Any]
    action: Callable[["Blackboard"], None]
    bid_fn: Optional[Callable[["Blackboard", "_KnowledgeSource"], float]]
    seen_upto: int = 0  # highest hypothesis id observed


def _matches(pattern: Any, topic: str) -> bool:
    if pattern == "*":
        return True
    if callable(pattern):
        try:
            return bool(pattern(topic))
        except Exception:
            return False
    return pattern == topic


class Blackboard:
    """Shared hypothesis surface with opportunistic KS scheduling."""

    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self._ids = itertools.count(1)
        self._hyps: List[Hypothesis] = []
        self._ks: Dict[str, _KnowledgeSource] = {}
        self._run_log: List[str] = []  # KS names in execution order

    # ------------------------------------------------------------ hypotheses
    def post_hypothesis(
        self,
        topic: str,
        content: Any,
        confidence: float = 0.5,
        source: str = "anon",
        supersedes: Optional[int] = None,
    ) -> Hypothesis:
        """Post a hypothesis. Never overwrites: competing posts coexist."""
        hyp = Hypothesis(
            id=next(self._ids),
            topic=topic,
            content=content,
            confidence=confidence,
            source=source,
            at=self._clock(),
            supersedes=supersedes,
        )
        self._hyps.append(hyp)
        return hyp

    def hypotheses(self, topic: Optional[str] = None) -> List[Hypothesis]:
        if topic is None:
            return list(self._hyps)
        return [h for h in self._hyps if h.topic == topic]

    def best(self, topic: str) -> Optional[Hypothesis]:
        """Highest-confidence hypothesis on a topic (ties: earliest posted)."""
        cands = self.hypotheses(topic)
        if not cands:
            return None
        return max(cands, key=lambda h: (h.confidence, -h.id))

    def conflicts(self) -> List[Tuple[Hypothesis, Hypothesis]]:
        """Pairs of same-topic hypotheses with differing content.

        Competing hypotheses coexist; this surfaces them instead of hiding
        the disagreement.
        """
        out: List[Tuple[Hypothesis, Hypothesis]] = []
        by_topic: Dict[str, List[Hypothesis]] = {}
        for h in self._hyps:
            by_topic.setdefault(h.topic, []).append(h)
        for hyps in by_topic.values():
            for i in range(len(hyps)):
                for j in range(i + 1, len(hyps)):
                    a, b = hyps[i], hyps[j]
                    if a.content != b.content:
                        out.append((a, b))
        return out

    # ------------------------------------------------------------------- KSs
    def register_ks(
        self,
        name: str,
        interests: List[Any],
        action: Callable[["Blackboard"], None],
        bid: Optional[Callable[["Blackboard", _KnowledgeSource], float]] = None,
    ) -> None:
        """Register a knowledge source.

        ``interests``: topic strings, "*" wildcard, or ``callable(topic)->bool``.
        ``action(bb)``: performs the KS's contribution (usually posts hypotheses).
        ``bid(bb, ks)``: returns a bid in [0, 1]; default bids 1.0 when the KS
        sees new matching hypotheses, else 0.0.
        """
        if not name or not isinstance(name, str):
            raise ValueError("KS name must be a non-empty string")
        if name in self._ks:
            raise ValueError(f"KS {name!r} already registered")
        if not callable(action):
            raise ValueError("KS action must be callable")
        if bid is not None and not callable(bid):
            raise ValueError("KS bid must be callable or None")
        self._ks[name] = _KnowledgeSource(
            name=name, interests=list(interests), action=action, bid_fn=bid,
            seen_upto=self._latest_id(),
        )

    def _latest_id(self) -> int:
        return self._hyps[-1].id if self._hyps else 0

    def _new_matches(self, ks: _KnowledgeSource) -> List[Hypothesis]:
        return [
            h for h in self._hyps
            if h.id > ks.seen_upto and any(_matches(p, h.topic) for p in ks.interests)
        ]

    def _default_bid(self, ks: _KnowledgeSource) -> float:
        return 1.0 if self._new_matches(ks) else 0.0

    def bids(self) -> Dict[str, float]:
        """Current bid of every KS. Highest bid wins the next cycle."""
        out: Dict[str, float] = {}
        for name, ks in self._ks.items():
            fn = ks.bid_fn or (lambda bb, k: self._default_bid(k))
            try:
                b = float(fn(self, ks))
            except Exception:
                b = 0.0
            out[name] = max(0.0, min(1.0, b))
        return out

    # -------------------------------------------------------------- scheduler
    def run_cycle(self) -> Optional[str]:
        """Run one cycle: highest-bidding KS acts. Returns its name or None."""
        bids = self.bids()
        if not bids:
            return None
        # deterministic tie-break: highest bid, then registration order
        order = list(self._ks.keys())
        winner = max(order, key=lambda n: (bids[n], -order.index(n)))
        if bids[winner] <= 0.0:
            return None
        ks = self._ks[winner]
        ks.action(self)
        # Only the acting KS advances its watermark: every other KS still
        # "hasn't seen" the new hypotheses, so chains like
        # classify -> enrich -> summarize keep firing opportunistically.
        ks.seen_upto = self._latest_id()
        self._run_log.append(winner)
        return winner

    def run_until(self, max_cycles: int = 100) -> Dict[str, Any]:
        """Run cycles until no KS bids > 0 or max_cycles is reached."""
        cycles = 0
        while cycles < max_cycles:
            if self.run_cycle() is None:
                break
            cycles += 1
        return {
            "cycles": cycles,
            "run_order": list(self._run_log),
            "hypotheses": len(self._hyps),
            "exhausted": cycles < max_cycles,
        }

    @property
    def run_log(self) -> List[str]:
        return list(self._run_log)


# ------------------------------------------------------------------- demo
def demo_three_stage() -> Dict[str, Any]:
    """Worked demo: classify -> enrich -> summarize assembled opportunistically.

    The three KSs are registered in *reverse* pipeline order to prove the
    point: execution order comes from bidding on blackboard state, not from a
    hardcoded pipeline.
    """
    bb = Blackboard()

    def classifier(b: Blackboard) -> None:
        doc = b.best("doc:ingested")
        text = str(doc.content).lower()
        label = "incident" if any(w in text for w in ("outage", "down", "breach")) else "note"
        b.post_hypothesis("doc:class", {"label": label}, confidence=0.8,
                           source="classifier")

    def enricher(b: Blackboard) -> None:
        cls = b.best("doc:class")
        label = cls.content["label"]
        b.post_hypothesis("doc:enriched",
                           {"label": label, "tags": ["urgent"] if label == "incident" else []},
                           confidence=0.75, source="enricher")

    def summarizer(b: Blackboard) -> None:
        enr = b.best("doc:enriched")
        b.post_hypothesis("doc:summary",
                           f"summary: {enr.content['label']} {enr.content['tags']}",
                           confidence=0.9, source="summarizer")

    # deliberately shuffled registration order
    bb.register_ks("summarizer", ["doc:enriched"], summarizer)
    bb.register_ks("enricher", ["doc:class"], enricher)
    bb.register_ks("classifier", ["doc:ingested"], classifier)

    bb.post_hypothesis("doc:ingested", "The payment API is down in eu-west",
                       confidence=1.0, source="ingest")
    result = bb.run_until()
    result["summary"] = bb.best("doc:summary")
    return result


if __name__ == "__main__":  # pragma: no cover
    import json
    out = demo_three_stage()
    out["summary"] = out["summary"].__dict__
    print(json.dumps(out, indent=2, default=str))
