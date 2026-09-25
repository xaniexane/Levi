"""DreamEngine — synthesize dreams from recent history, variate, score, journal.

Offline-first. Rule-based synthesis always runs; pass ``generate`` (a
callable taking a prompt string and returning text) for model-assisted
dreams. The engine honestly reports which mode produced each dream.

Seed sources: explicit seed dicts, or the growth journal
(``~/.levi/growth/journal.jsonl``) when present. Seeds are never required —
a bare seed text also works.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from levi.dream.journal import DreamJournal
from levi.dream.vary import variate

_RISK_WORDS = {
    "delete",
    "destroy",
    "bypass",
    "disable",
    "override",
    "secret",
    "password",
    "exploit",
    "attack",
    "weapon",
}


def _wordset(t: str) -> set:
    import re

    return set(re.findall(r"[a-z0-9]+", t.lower()))


def _novelty(seed_text: str, variant_text: str) -> float:
    """Word-overlap inverse: 1.0 = wholly new vocabulary."""
    s, v = _wordset(seed_text), _wordset(variant_text)
    if not v:
        return 0.0
    return 1.0 - len(s & v) / len(v)


def _risk_flags(text: str) -> List[str]:
    low = text.lower()
    return sorted({w for w in _RISK_WORDS if w in low})


def score_variant(seed_text: str, variant: Dict[str, str]) -> Dict[str, Any]:
    """Rule-score a variant. Returns outcome: promising | risky | compost."""
    text = variant["text"]
    novelty = round(_novelty(seed_text, text), 3)
    risks = _risk_flags(text)
    if risks:
        outcome = "compost"
        note = f"flagged words: {', '.join(risks)} — compost, do not pursue"
    elif novelty < 0.35:
        outcome = "compost"
        note = "too close to the seed — no new information"
    elif novelty > 0.85:
        outcome = "risky"
        note = "high novelty — verify before trusting"
    else:
        outcome = "promising"
        note = "novel but grounded — candidate lesson"
    return {
        "kind": variant["kind"],
        "text": text,
        "novelty": novelty,
        "risks": risks,
        "outcome": outcome,
        "note": note,
    }


def extract_lesson(seed: Dict[str, Any], scored: List[Dict[str, Any]]) -> Optional[str]:
    """Compress the best surviving variant into a heritable one-liner (RIEM-style)."""
    survivors = [v for v in scored if v["outcome"] == "promising"]
    if not survivors:
        return None
    best = max(survivors, key=lambda v: v["novelty"])
    seed_text = str(seed.get("text", ""))[:80]
    return f"[{best['kind']}] from '{seed_text}': {best['text'][:140]}"


@dataclass
class DreamRecord:
    seed: Dict[str, Any]
    variants: List[Dict[str, Any]] = field(default_factory=list)
    lesson: Optional[str] = None
    compost_count: int = 0
    mode: str = "rules"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def synthesize_dream(
    seed: Dict[str, Any],
    kinds: List[str] | None = None,
    generate: Callable[[str], str] | None = None,
) -> DreamRecord:
    """Run one seed through variation, scoring, and lesson extraction."""
    seed_text = str(seed.get("text", "")).strip() or "silence"
    mode = "rules"
    variants = variate(seed_text, kinds)
    if generate is not None:
        # Model-assisted: one extra fusion dream, honestly labeled.
        try:
            fusion = generate(
                f"Fuse this into one creative insight (2 sentences max): {seed_text}"
            )
            if fusion and fusion.strip():
                variants.append({"kind": "fusion", "text": fusion.strip()[:500]})
                mode = "model-assisted"
        except Exception:
            pass
    scored = [score_variant(seed_text, v) for v in variants]
    lesson = extract_lesson(seed, scored)
    compost_count = sum(1 for v in scored if v["outcome"] == "compost")
    return DreamRecord(
        seed=seed,
        variants=scored,
        lesson=lesson,
        compost_count=compost_count,
        mode=mode,
    )


class DreamEngine:
    """Collect seeds, dream them, journal the results."""

    def __init__(
        self,
        journal: DreamJournal | None = None,
        generate: Callable[[str], str] | None = None,
        growth_journal: Path | None = None,
    ) -> None:
        self.journal = journal or DreamJournal()
        self.generate = generate
        base = Path(os.environ.get("LEVI_HOME", Path.home() / ".levi"))
        self.growth_journal = growth_journal or (base / "growth" / "journal.jsonl")

    def collect_seeds(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Pull recent seeds from the growth journal when present."""
        seeds: List[Dict[str, Any]] = []
        try:
            if self.growth_journal.exists():
                lines = self.growth_journal.read_text(encoding="utf-8").splitlines()
                for line in lines[-limit:]:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    text = row.get("text") or row.get("learning") or row.get("summary")
                    if text:
                        seeds.append(
                            {
                                "text": str(text),
                                "source": "growth-journal",
                                "ts": row.get("ts", ""),
                            }
                        )
        except OSError:
            pass
        return seeds

    def dream_seed(
        self, seed: Dict[str, Any], kinds: List[str] | None = None
    ) -> DreamRecord:
        record = synthesize_dream(seed, kinds=kinds, generate=self.generate)
        self.journal.append(record.to_dict())
        return record

    def run_once(
        self,
        seeds: List[Dict[str, Any]] | None = None,
        limit: int = 5,
        kinds: List[str] | None = None,
    ) -> List[DreamRecord]:
        seeds = seeds if seeds is not None else self.collect_seeds(limit)
        return [self.dream_seed(s, kinds=kinds) for s in seeds]
