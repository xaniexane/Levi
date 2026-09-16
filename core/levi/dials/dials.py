"""Sovereign Attention Dials — the ranking engine.

Item schema: ``{id, author, timestamp, text, tags}``.

The weight vector is a plain dict of feature-name -> non-negative float.
Features are pure functions of (item, context) returning values in
[0, 1]:

- ``recency``     — exponential decay on item age (half-life configurable)
- ``affinity``    — 1.0 if the author is on the user's EXPLICIT opt-in
  affinity list (edited via CLI), else 0.0. Never inferred.
- ``diversity``   — 1.0 minus the fraction of already-ranked items sharing
  the item's dominant tag (computed greedily during ranking, so earlier
  picks push later same-tag items down)
- ``substance``   — length-based, saturating: longer-than-a-threshold text
  scores up to 1.0 (a documented heuristic, not a quality claim)
- ``tag_match``   — 1.0 if the item carries any of the user's pinned tags

Score = sum(w_f * f(item)) / sum(w). With all weights zero (or in
``chronological`` mode) the feed is strictly newest-first; weights are an
opt-in overlay, never a hidden default.

Every ranking decision is explainable: :func:`explain` returns the raw
per-feature values and their weighted contributions for an item.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _home() -> Path:
    """Resolved at call time so tests can redirect HOME."""
    override = os.environ.get("LEVI_HOME")
    if override:
        return Path(override)
    return Path.home() / ".levi"


def _state_path() -> Path:
    return _home() / "dials" / "dials.json"


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------


@dataclass
class Item:
    id: str
    author: str
    timestamp: str  # ISO-8601
    text: str
    tags: List[str] = field(default_factory=list)

    def age_seconds(self, now: Optional[datetime] = None) -> float:
        now = now or datetime.now(timezone.utc)
        ts = datetime.fromisoformat(self.timestamp)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return max(0.0, (now - ts).total_seconds())


def _new_id(author: str, text: str, timestamp: str) -> str:
    return hashlib.sha256(f"{author}|{text}|{timestamp}".encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Features
# ---------------------------------------------------------------------------

RECENCY_HALFLIFE_SECONDS = 6 * 3600.0  # 6h half-life; user-editable via CLI
SUBSTANCE_SATURATION_CHARS = 280.0


def feat_recency(item: Item, ctx: "RankContext") -> float:
    half = ctx.recency_halflife_s or RECENCY_HALFLIFE_SECONDS
    return 0.5 ** (item.age_seconds(ctx.now) / half)


def feat_affinity(item: Item, ctx: "RankContext") -> float:
    return 1.0 if item.author in ctx.affinity else 0.0


def feat_diversity(item: Item, ctx: "RankContext") -> float:
    """Penalize items whose dominant tag is already well represented in the
    ranked-so-far set. First items of a tag score 1.0."""
    if not item.tags:
        return 1.0
    dominant = item.tags[0]
    seen = ctx.tag_counts.get(dominant, 0)
    total = max(1, ctx.ranked_so_far)
    return 1.0 - (seen / total)


def feat_substance(item: Item, ctx: "RankContext") -> float:
    return min(1.0, len(item.text) / SUBSTANCE_SATURATION_CHARS)


def feat_tag_match(item: Item, ctx: "RankContext") -> float:
    if not ctx.pinned_tags:
        return 0.0
    return 1.0 if any(t in ctx.pinned_tags for t in item.tags) else 0.0


FEATURES: Dict[str, Any] = {
    "recency": feat_recency,
    "affinity": feat_affinity,
    "diversity": feat_diversity,
    "substance": feat_substance,
    "tag_match": feat_tag_match,
}

DEFAULT_WEIGHTS: Dict[str, float] = {
    "recency": 1.0,
    "affinity": 1.0,
    "diversity": 0.5,
    "substance": 0.25,
    "tag_match": 0.5,
}


@dataclass
class RankContext:
    now: datetime
    affinity: List[str]
    pinned_tags: List[str]
    recency_halflife_s: float = RECENCY_HALFLIFE_SECONDS
    tag_counts: Dict[str, int] = field(default_factory=dict)
    ranked_so_far: int = 0


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class DialError(ValueError):
    """Raised for invalid dial operations (bad weight names, negatives)."""


class AttentionDials:
    """Local-first ranking engine with a user-owned weight vector."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or _state_path()
        self.weights: Dict[str, float] = dict(DEFAULT_WEIGHTS)
        self.affinity: List[str] = []
        self.pinned_tags: List[str] = []
        self.recency_halflife_s: float = RECENCY_HALFLIFE_SECONDS
        self.mode: str = "chronological"  # sticky default; "weighted" is opt-in
        self.items: List[Item] = []
        self._load()

    # -- persistence ----------------------------------------------------
    def _load(self) -> None:
        try:
            raw = json.loads(self._path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return
        self.weights = {
            k: float(v) for k, v in raw.get("weights", {}).items() if k in FEATURES
        }
        for k in DEFAULT_WEIGHTS:
            self.weights.setdefault(k, DEFAULT_WEIGHTS[k])
        self.affinity = list(raw.get("affinity", []))
        self.pinned_tags = list(raw.get("pinned_tags", []))
        self.recency_halflife_s = float(
            raw.get("recency_halflife_s", RECENCY_HALFLIFE_SECONDS)
        )
        if raw.get("mode") in ("chronological", "weighted"):
            self.mode = raw["mode"]
        self.items = [Item(**it) for it in raw.get("items", [])]

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "weights": self.weights,
            "affinity": self.affinity,
            "pinned_tags": self.pinned_tags,
            "recency_halflife_s": self.recency_halflife_s,
            "mode": self.mode,
            "items": [asdict(i) for i in self.items],
        }
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True))
        tmp.replace(self._path)

    # -- items ----------------------------------------------------------
    def add_item(
        self,
        author: str,
        text: str,
        tags: Optional[List[str]] = None,
        timestamp: Optional[str] = None,
    ) -> Item:
        author, text = author.strip(), text.strip()
        if not author:
            raise DialError("author must be non-empty")
        if not text:
            raise DialError("text must be non-empty")
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        item = Item(
            id=_new_id(author, text, ts),
            author=author,
            timestamp=ts,
            text=text,
            tags=list(tags or []),
        )
        # idempotent: same content+author+timestamp re-add returns existing
        for existing in self.items:
            if existing.id == item.id:
                return existing
        self.items.append(item)
        self._save()
        return item

    # -- dials ----------------------------------------------------------
    def set_weight(self, name: str, value: float) -> None:
        if name not in FEATURES:
            raise DialError(f"unknown weight {name!r}; known: {sorted(FEATURES)}")
        if not math.isfinite(value) or value < 0:
            raise DialError(
                f"weight must be a finite non-negative number, got {value!r}"
            )
        self.weights[name] = float(value)
        self._save()

    def set_mode(self, mode: str) -> None:
        if mode not in ("chronological", "weighted"):
            raise DialError("mode must be 'chronological' or 'weighted'")
        self.mode = mode
        self._save()

    def add_affinity(self, author: str) -> None:
        author = author.strip()
        if not author:
            raise DialError("author must be non-empty")
        if author not in self.affinity:
            self.affinity.append(author)
            self._save()

    def remove_affinity(self, author: str) -> None:
        if author in self.affinity:
            self.affinity.remove(author)
            self._save()

    def pin_tag(self, tag: str) -> None:
        tag = tag.strip()
        if tag and tag not in self.pinned_tags:
            self.pinned_tags.append(tag)
            self._save()

    def _context(self, now: Optional[datetime] = None) -> RankContext:
        return RankContext(
            now=now or datetime.now(timezone.utc),
            affinity=list(self.affinity),
            pinned_tags=list(self.pinned_tags),
            recency_halflife_s=self.recency_halflife_s,
        )

    # -- ranking --------------------------------------------------------
    def _score(self, item: Item, ctx: RankContext) -> Tuple[float, Dict[str, float]]:
        total_w = sum(self.weights.values())
        if total_w <= 0:
            return 0.0, {k: 0.0 for k in FEATURES}
        contribs: Dict[str, float] = {}
        score = 0.0
        for name, fn in FEATURES.items():
            raw = max(0.0, min(1.0, fn(item, ctx)))
            c = self.weights[name] * raw / total_w
            contribs[name] = c
            score += c
        return score, contribs

    def explain(self, item_id: str, now: Optional[datetime] = None) -> Dict[str, Any]:
        """Full transparency: per-feature values and weighted contributions."""
        item = next((i for i in self.items if i.id == item_id), None)
        if item is None:
            raise DialError(f"unknown item id {item_id!r}")
        ctx = self._context(now)
        score, contribs = self._score(item, ctx)
        total_w = sum(self.weights.values())
        features = {n: max(0.0, min(1.0, fn(item, ctx))) for n, fn in FEATURES.items()}
        return {
            "id": item.id,
            "author": item.author,
            "mode": self.mode,
            "weights": dict(self.weights),
            "total_weight": total_w,
            "features": features,
            "contributions": contribs,
            "score": score,
        }

    def rank(
        self, now: Optional[datetime] = None, limit: Optional[int] = None
    ) -> List[Tuple[Item, float, Dict[str, float]]]:
        """Ranked feed. Chronological mode: strictly newest-first, weights
        shown as what-WOULD-apply. Weighted mode: greedy diversity-aware
        scoring (diversity sees previously ranked items)."""
        ctx = self._context(now)
        if self.mode == "chronological":
            ordered = sorted(self.items, key=lambda i: i.timestamp, reverse=True)
            out = []
            for it in ordered:
                score, contribs = self._score(it, ctx)
                out.append((it, score, contribs))
            return out[:limit] if limit else out
        # weighted: greedy so diversity is position-aware
        remaining = list(self.items)
        ranked: List[Tuple[Item, float, Dict[str, float]]] = []
        while remaining:
            best, best_score, best_c = None, -1.0, {}
            for it in remaining:
                s, c = self._score(it, ctx)
                if s > best_score or (
                    s == best_score and it.timestamp > (best.timestamp if best else "")
                ):
                    best, best_score, best_c = it, s, c
            assert best is not None
            ranked.append((best, best_score, best_c))
            remaining.remove(best)
            if best.tags:
                ctx.tag_counts[best.tags[0]] = ctx.tag_counts.get(best.tags[0], 0) + 1
            ctx.ranked_so_far += 1
        return ranked[:limit] if limit else ranked

    def feed(
        self, limit: Optional[int] = None, now: Optional[datetime] = None
    ) -> List[Item]:
        return [it for it, _, _ in self.rank(now=now, limit=limit)]

    # -- display --------------------------------------------------------
    def format_weights(self) -> str:
        lines = [
            "=== Attention Dials ===",
            f"mode: {self.mode}  (sticky default: chronological)",
            f"recency half-life: {self.recency_halflife_s / 3600:.1f}h",
            f"affinity (explicit opt-in): {', '.join(self.affinity) or '(none)'}",
            f"pinned tags: {', '.join(self.pinned_tags) or '(none)'}",
            "",
        ]
        total = sum(self.weights.values())
        for name in FEATURES:
            w = self.weights[name]
            pct = (w / total * 100) if total else 0.0
            lines.append(f"  {name:10s} weight={w:6.2f}  ({pct:5.1f}% of score)")
        lines += [
            "",
            "Giants hide these. Yours are editable: dials set-weight <name> <value>",
            "Affinity is explicit only — LEVI never infers who you like.",
        ]
        return "\n".join(lines)

    def format_feed(self, limit: int = 20, now: Optional[datetime] = None) -> str:
        ranked = self.rank(now=now, limit=limit)
        lines = [f"=== Feed ({self.mode}) — {len(ranked)} shown ==="]
        for it, score, contribs in ranked:
            top = max(contribs, key=lambda k: contribs[k]) if contribs else "-"
            tag_s = f" [{','.join(it.tags)}]" if it.tags else ""
            lines.append(f"  [{it.id[:8]}] {it.author}{tag_s}: {it.text[:70]}")
            lines.append(f"           score={score:.3f}  top-driver={top}")
        if not ranked:
            lines.append(
                "  (empty — add items with: dials add --author NAME --text TEXT)"
            )
        return "\n".join(lines)
