"""Memory consolidation: sleep-and-reflect, on a schedule, never inline.

Studied from: ai-si-software-internals-20260916-0005/report.md (§2.7)

Functional description: every turn is appended to an episodic log as it
happens (cheap). Consolidation runs only when ``consolidate_if_due`` says
the log has passed a token threshold since the last run — never inline in
the hot path. When it runs, the oldest turns are summarized into semantic
facts by an extractive summarizer (top sentences by term centrality — no
generation, no invention), then compacted hierarchically: turns → episode
summaries → facts. A decay weight favors recent episodes over stale ones,
so old trivia fades while durable facts persist.

Pure Python, stdlib only. No provider branding. Not artificial — synthetic.
"""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

ORIGIN = "levi-revival/memsleep"

_WORD = re.compile(r"[a-z0-9']+")


def _words(text: str) -> List[str]:
    return _WORD.findall(text.lower())


def approx_tokens(text: str) -> int:
    """Cheap token estimate: ~4 chars per token. Honest approximation."""
    return max(1, len(text) // 4)


@dataclass
class LoggedTurn:
    text: str
    ts: float
    tokens: int = 0

    def __post_init__(self) -> None:
        self.tokens = approx_tokens(self.text)


@dataclass
class SemanticFact:
    text: str
    source_turns: int
    weight: float  # decay-weighted importance
    created_ts: float = field(default_factory=time.time)


class Consolidator:
    """Append cheaply; consolidate on schedule; compact hierarchically."""

    def __init__(
        self,
        threshold_tokens: int = 2000,
        keep_recent: int = 5,
        decay_half_life_turns: float = 50.0,
    ) -> None:
        self.threshold_tokens = threshold_tokens
        self.keep_recent = keep_recent  # newest turns never compacted
        self.decay_half_life = decay_half_life_turns
        self.episodic: List[LoggedTurn] = []
        self.facts: List[SemanticFact] = []
        self.episode_summaries: List[str] = []  # hierarchical middle layer
        self._tokens_since_consolidation = 0
        self.runs = 0
        self.last_run_ts: Optional[float] = None

    # -- hot path: append only ------------------------------------------
    def log_turn(self, text: str) -> None:
        turn = LoggedTurn(text=text, ts=time.time())
        self.episodic.append(turn)
        self._tokens_since_consolidation += turn.tokens

    def consolidate_if_due(self) -> bool:
        """Returns True when the schedule fired and consolidation ran."""
        if self._tokens_since_consolidation < self.threshold_tokens:
            return False
        if len(self.episodic) <= self.keep_recent:
            return False
        self._consolidate()
        return True

    # -- extractive summarizer ------------------------------------------
    def _extractive_summary(
        self, turns: List[LoggedTurn], max_sentences: int = 3
    ) -> str:
        sentences: List[str] = []
        for t in turns:
            sentences.extend(s for s in re.split(r"(?<=[.!?])\s+", t.text) if s.strip())
        if not sentences:
            return ""
        # term centrality: score sentences by summed log-frequency of words
        freq: Dict[str, int] = {}
        for s in sentences:
            for w in set(_words(s)):
                freq[w] = freq.get(w, 0) + 1
        scored = []
        for i, s in enumerate(sentences):
            ws = _words(s)
            score = sum(math.log(1 + freq[w]) for w in set(ws))
            score /= math.sqrt(len(ws)) if ws else 1.0  # length norm
            scored.append((score, i, s))
        scored.sort(key=lambda p: (-p[0], p[1]))
        # take the top sentences back in their original order
        top_idx = sorted(i for _, i, _s in scored[:max_sentences])
        return " ".join(sentences[i] for i in top_idx)

    def _decay(self, age_turns: float) -> float:
        return 0.5 ** (age_turns / self.decay_half_life)

    # -- the scheduled run -----------------------------------------------
    def _consolidate(self) -> None:
        compactable = self.episodic[: -self.keep_recent]
        if not compactable:
            return
        summary = self._extractive_summary(compactable)
        if summary:
            self.episode_summaries.append(summary)
            # hierarchical: episode summary → semantic fact with decay weight
            age = float(len(self.episodic))
            self.facts.append(
                SemanticFact(
                    text=summary,
                    source_turns=len(compactable),
                    weight=self._decay(age) * len(compactable),
                )
            )
        # compact: drop the raw turns that were summarized
        self.episodic = self.episodic[-self.keep_recent :]
        self._tokens_since_consolidation = sum(t.tokens for t in self.episodic)
        self.runs += 1
        self.last_run_ts = time.time()

    # -- recall -----------------------------------------------------------
    def recall_facts(self, query: str = "", limit: int = 5) -> List[SemanticFact]:
        facts = sorted(self.facts, key=lambda f: -f.weight)
        if query:
            q = set(_words(query))
            facts = sorted(
                facts,
                key=lambda f: (
                    -len(q & set(_words(f.text))),
                    -f.weight,
                ),
            )
        return facts[:limit]

    def status(self) -> Dict[str, object]:
        return {
            "episodic_turns": len(self.episodic),
            "pending_tokens": self._tokens_since_consolidation,
            "threshold_tokens": self.threshold_tokens,
            "consolidation_runs": self.runs,
            "facts": len(self.facts),
            "episode_summaries": len(self.episode_summaries),
            "last_run_ts": self.last_run_ts,
        }
