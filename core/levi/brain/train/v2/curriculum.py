"""v2 curriculum builder: order teaching material simple -> complex.

Approved sources (consumed as corpus manifests that already passed the news
policy gate): course corpora, knowledge packs, growth-journal learnings.
Ordering heuristic per doc:

    difficulty = 0.5 * norm_len + 0.5 * mean_word_rarity

where ``norm_len`` is the doc's word count scaled to [0, 1] across the batch
and ``mean_word_rarity`` is the average ``1 - freq(word)/max_freq`` over the
doc's words. Short, common-vocabulary docs come first; long, rare-vocabulary
docs come last. Ties break deterministically by doc id.

Output is a :class:`CurriculumManifest` (JSON) with the ordered doc ids,
per-doc difficulty scores, and stage assignments (contiguous chunks). The
TEACH worker consumes the manifest; training stages advance through the
order as loss plateaus.

This is a heuristic, not pedagogy theory. It is honest about that: the
manifest records exactly how each doc was scored.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from levi.brain.train.v2.corpus_manager import Doc

_WORD_RE = re.compile(r"[a-z0-9']+")


def tokenize_words(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def corpus_word_counts(docs: Iterable[Doc]) -> Counter:
    """Word frequencies over a doc batch (drives the rarity heuristic)."""
    counts: Counter = Counter()
    for doc in docs:
        counts.update(tokenize_words(doc.text))
    return counts


def difficulty_scores(
    docs: list[Doc], word_counts: Counter | None = None
) -> dict[str, float]:
    """Map doc id -> difficulty in [0, 1] (higher = harder)."""
    docs = list(docs)
    if not docs:
        return {}
    if word_counts is None:
        word_counts = corpus_word_counts(docs)
    max_freq = max(word_counts.values()) if word_counts else 1
    lengths = [len(tokenize_words(d.text)) for d in docs]
    max_len = max(lengths) if lengths else 1

    scores: dict[str, float] = {}
    for doc, n_words in zip(docs, lengths, strict=True):
        words = tokenize_words(doc.text)
        if words:
            rarity = sum(
                max(0.0, 1.0 - word_counts[w] / max_freq) for w in words
            ) / len(words)
        else:
            rarity = 0.0
        norm_len = (n_words / max_len) if max_len else 0.0
        scores[doc.id] = 0.5 * norm_len + 0.5 * rarity
    return scores


@dataclass
class CurriculumManifest:
    name: str
    source_manifests: list[
        str
    ]  # corpus manifest names+versions, e.g. "courses@2026-09-15"
    n_stages: int
    order: list[str]  # doc ids, simple -> complex
    stage_of: dict[str, int]
    difficulty: dict[str, float]
    seed: int
    method: str = "len+rarity/2"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )


def build_curriculum(
    docs: list[Doc],
    *,
    name: str,
    source_manifests: Iterable[str] = (),
    n_stages: int = 4,
    seed: int = 1337,  # reserved: ordering is fully deterministic already
    word_counts: Counter | None = None,
) -> CurriculumManifest:
    """Order docs simple -> complex and assign contiguous stages.

    Deterministic: identical input always yields identical output.
    """
    if n_stages < 1:
        raise ValueError(f"n_stages must be >= 1, got {n_stages}")
    docs = list(docs)
    scores = difficulty_scores(docs, word_counts)
    ordered = sorted(docs, key=lambda d: (scores[d.id], d.id))
    order = [d.id for d in ordered]

    n = len(order)
    stage_of: dict[str, int] = {}
    for i, doc_id in enumerate(order):
        # Contiguous chunks; the last stage absorbs any remainder.
        stage = min(n_stages - 1, (i * n_stages) // max(n, 1))
        stage_of[doc_id] = stage

    return CurriculumManifest(
        name=name,
        source_manifests=list(source_manifests),
        n_stages=n_stages,
        order=order,
        stage_of=stage_of,
        difficulty={d.id: scores[d.id] for d in ordered},
        seed=seed,
    )


def stage_docs(manifest: CurriculumManifest, stage: int) -> list[str]:
    """Doc ids belonging to a stage, in curriculum order."""
    return [d for d in manifest.order if manifest.stage_of[d] == stage]


def save_curriculum(manifest: CurriculumManifest, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    d = asdict(manifest)
    d["difficulty"] = {k: round(v, 6) for k, v in d["difficulty"].items()}
    path.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_curriculum(path: str | Path) -> CurriculumManifest:
    path = Path(path)
    d = json.loads(path.read_text(encoding="utf-8"))
    return CurriculumManifest(
        name=d["name"],
        source_manifests=list(d.get("source_manifests", [])),
        n_stages=d["n_stages"],
        order=list(d["order"]),
        stage_of={k: int(v) for k, v in d["stage_of"].items()},
        difficulty={k: float(v) for k, v in d["difficulty"].items()},
        seed=d.get("seed", 0),
        method=d.get("method", "len+rarity/2"),
        created_at=d.get("created_at", ""),
    )


def describe_stages(manifest: CurriculumManifest) -> list[dict]:
    """Human-readable per-stage summary for logs and the TEACH worker."""
    out = []
    for s in range(manifest.n_stages):
        ids = stage_docs(manifest, s)
        diffs = [manifest.difficulty[d] for d in ids]
        out.append(
            {
                "stage": s,
                "n_docs": len(ids),
                "difficulty_min": round(min(diffs), 4) if diffs else None,
                "difficulty_max": round(max(diffs), 4) if diffs else None,
            }
        )
    return out
