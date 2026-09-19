"""llm_cache — exact + semantic caching so tokens are never bought twice.

Studied from: hybrid-cost-cutting-combos-20260916-0006/report.md [§4].

Shape studied: a cache hit on an inference response (or an embedding)
is a token never purchased — dial-up-era frugality applied to AI
pipelines.

Mechanism (stdlib only, heuristic where labeled):
* LLMCache: exact-match cache keyed on a normalized SHA-256 of the
  prompt, with LRU eviction and TTL expiry. Tracks hits, misses,
  evictions, and tokens never re-purchased.
* SemanticCache: extends the exact cache with a fingerprint-similarity
  lookup. Fingerprints are deterministic hashing-trick word vectors
  (labeled heuristic — a cheap stand-in for embeddings, not embeddings);
  cosine similarity above a threshold counts as a hit.
* normalize() strips the cosmetic differences that cause needless
  misses: case, whitespace runs, surrounding punctuation.

Honest limits: the semantic layer is a rough lexical fingerprint, not a
real embedding model — near-paraphrases may miss and unrelated prompts
with shared vocabulary may collide. Thresholds are tunable for that.

This is an original, from-scratch implementation for LEVI.
Not artificial. Synthetic.
"""

from __future__ import annotations

import hashlib
import math
import re
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

ORIGIN = "levi-revival/llm_cache"

_FINGERPRINT_DIMS = 64


def normalize(text: str) -> str:
    """Canonicalize a prompt so cosmetic differences don't cause misses."""
    text = text.strip().lower()
    text = re.sub(r"[^\w\s]", "", text)  # drop punctuation, inside and out
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def exact_key(text: str) -> str:
    """Stable cache key for a prompt."""
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def fingerprint(text: str, dims: int = _FINGERPRINT_DIMS) -> List[float]:
    """Deterministic hashing-trick word vector (heuristic, not an embedding)."""
    vec = [0.0] * dims
    for word in normalize(text).split():
        h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
        idx = h % dims
        sign = 1.0 if (h >> 7) & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]


def cosine(a: List[float], b: List[float]) -> float:
    """Cosine similarity of two same-length vectors."""
    return sum(x * y for x, y in zip(a, b, strict=True))


@dataclass
class CacheEntry:
    response: str
    tokens: int  # tokens this response would have cost to regenerate
    stored_at: float
    hits: int = 0


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    semantic_hits: int = 0
    tokens_saved: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


class LLMCache:
    """Exact-match LRU cache with TTL for inference responses."""

    def __init__(self, capacity: int = 512, ttl_seconds: float = 3600.0):
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.capacity = capacity
        self.ttl_seconds = ttl_seconds
        self._store: "OrderedDict[str, CacheEntry]" = OrderedDict()
        self.stats = CacheStats()

    def _expired(self, entry: CacheEntry, now: float) -> bool:
        return now - entry.stored_at > self.ttl_seconds

    def get(self, prompt: str, now: Optional[float] = None) -> Optional[str]:
        now = time.time() if now is None else now
        key = exact_key(prompt)
        entry = self._store.get(key)
        if entry is None or self._expired(entry, now):
            if entry is not None:
                del self._store[key]
            self.stats.misses += 1
            return None
        self._store.move_to_end(key)
        entry.hits += 1
        self.stats.hits += 1
        self.stats.tokens_saved += entry.tokens
        return entry.response

    def put(
        self,
        prompt: str,
        response: str,
        tokens: int,
        now: Optional[float] = None,
    ) -> None:
        now = time.time() if now is None else now
        if tokens < 0:
            raise ValueError("tokens must be >= 0")
        key = exact_key(prompt)
        self._store[key] = CacheEntry(response=response, tokens=tokens, stored_at=now)
        self._store.move_to_end(key)
        while len(self._store) > self.capacity:
            self._store.popitem(last=False)
            self.stats.evictions += 1

    def purge_expired(self, now: Optional[float] = None) -> int:
        now = time.time() if now is None else now
        expired = [k for k, e in self._store.items() if self._expired(e, now)]
        for key in expired:
            del self._store[key]
        return len(expired)

    def __len__(self) -> int:
        return len(self._store)


class SemanticCache(LLMCache):
    """Exact cache plus fingerprint-similarity lookup (heuristic)."""

    def __init__(
        self,
        capacity: int = 512,
        ttl_seconds: float = 3600.0,
        similarity_threshold: float = 0.92,
    ):
        super().__init__(capacity=capacity, ttl_seconds=ttl_seconds)
        if not 0.0 < similarity_threshold <= 1.0:
            raise ValueError("similarity_threshold must be within (0, 1]")
        self.similarity_threshold = similarity_threshold
        self._fingerprints: Dict[str, List[float]] = {}

    def put(self, prompt, response, tokens, now=None):
        now = time.time() if now is None else now
        super().put(prompt, response, tokens, now=now)
        key = exact_key(prompt)
        self._fingerprints[key] = fingerprint(prompt)
        # Keep fingerprint index in sync with LRU evictions.
        for dead in [k for k in self._fingerprints if k not in self._store]:
            del self._fingerprints[dead]

    def get_similar(
        self, prompt: str, now: Optional[float] = None
    ) -> Optional[Tuple[str, float]]:
        """Best cached response whose fingerprint clears the threshold.

        Returns ``(response, similarity)`` or ``None``. Exact hits are
        served by :meth:`get` first, so the prompt's own entry is skipped
        here — this is the fuzzy fallback only.
        """
        now = time.time() if now is None else now
        own_key = exact_key(prompt)
        target = fingerprint(prompt)
        best_key: Optional[str] = None
        best_score = 0.0
        for key, vec in self._fingerprints.items():
            if key == own_key:
                continue
            entry = self._store.get(key)
            if entry is None or self._expired(entry, now):
                continue
            score = cosine(target, vec)
            if score >= self.similarity_threshold and score > best_score:
                best_key, best_score = key, score
        if best_key is None:
            return None
        entry = self._store[best_key]
        entry.hits += 1
        self.stats.semantic_hits += 1
        self.stats.tokens_saved += entry.tokens
        return entry.response, best_score
