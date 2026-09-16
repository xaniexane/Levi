"""LEVI memory retrieval upgrade.

A ranker that works OVER the existing :class:`levi.memory.store.MemoryStore`
without changing it (entries are read through the store's public ``list()``).

Ladder implemented here (all stdlib-only, offline, deterministic):

1. **BM25** lexical scoring — tokenize (lowercase, stopwords, light stemming),
   field weights (tags count 3x content), k1=1.5 / b=0.75.
2. **Recency + importance** — exponential time-decay (configurable half-life)
   combined with entry importance and a corroboration-count boost from
   metadata (``metadata["corroboration"]`` when present).
3. **Sparse semantic vectors** — character n-gram hashing trick (hashlib) +
   cosine similarity. Catches paraphrase with no model.
4. **Hybrid fusion** — reciprocal rank fusion (k=60) over BM25 + sparse-vector
   rankings.
5. **Query expansion** — small synonym map + multi-query (split on " or " /
   commas), fused with RRF.

Public API: :func:`retrieve` — fail-closed, never raises on weird input.
"""

from __future__ import annotations

import hashlib
import math
import re
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Tokenization
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_STOPWORDS = frozenset(
    """
    a an the and or but if then else when while of at by for with about into
    through during before after above below to from up down in out on off over
    under again further once here there all any both each few more most other
    some such no nor not only own same so than too very can will just don
    should now is are was were be been being have has had having do does did
    doing would could ought i you he she it we they them his her its our their
    this that these those am me my mine your yours him us as s t d ll m re ve
    what which who whom whose why how where
    """.split()
)

# Tiny domain-neutral synonym map for query expansion. Deliberately small:
# expansion is a recall aid, not a thesaurus.
_SYNONYMS: Dict[str, Tuple[str, ...]] = {
    "buy": ("purchase", "acquire"),
    "purchase": ("buy", "acquire"),
    "sell": ("vend",),
    "fast": ("quick", "rapid"),
    "quick": ("fast", "rapid"),
    "slow": ("sluggish",),
    "help": ("assist", "aid"),
    "assist": ("help", "aid"),
    "car": ("auto", "vehicle"),
    "auto": ("car", "vehicle"),
    "dog": ("canine", "puppy"),
    "cat": ("feline", "kitten"),
    "laptop": ("computer", "notebook"),
    "computer": ("laptop", "pc"),
    "phone": ("mobile", "smartphone"),
    "email": ("mail", "message"),
    "password": ("passcode", "credentials"),
    "money": ("cash", "funds"),
    "house": ("home", "residence"),
    "home": ("house", "residence"),
    "big": ("large", "huge"),
    "small": ("tiny", "little"),
    "good": ("great", "excellent"),
    "bad": ("poor", "terrible"),
    "start": ("begin", "commence"),
    "begin": ("start", "commence"),
    "stop": ("halt", "cease"),
    "make": ("create", "build"),
    "create": ("make", "build"),
    "fix": ("repair", "mend"),
    "repair": ("fix", "mend"),
    "find": ("locate", "search"),
    "search": ("find", "lookup"),
}


def _stem(token: str) -> str:
    """Very light stemmer: strip a few common English suffixes."""
    if len(token) > 5:
        for suffix in ("ing", "tion", "ness", "ment"):
            if token.endswith(suffix):
                return token[: -len(suffix)]
    if len(token) > 4:
        for suffix in ("edly", "ly", "ed", "es"):
            if token.endswith(suffix):
                stemmed = token[: -len(suffix)]
                if len(stemmed) >= 3:
                    return stemmed
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def tokenize(text: str) -> List[str]:
    """Lowercase, split on non-alphanumerics, drop stopwords, light-stem."""
    if not isinstance(text, str):
        return []
    return [
        _stem(tok)
        for tok in _TOKEN_RE.findall(text.lower())
        if tok not in _STOPWORDS and len(tok) > 1
    ]


# ---------------------------------------------------------------------------
# BM25
# ---------------------------------------------------------------------------

_BM25_K1 = 1.5
_BM25_B = 0.75
_TAG_FIELD_WEIGHT = 3.0


def _field_term_freqs(entry) -> Dict[str, float]:
    """Weighted term frequencies: tags count 3x, content 1x."""
    freqs: Dict[str, float] = {}
    for tok in tokenize(entry.content or ""):
        freqs[tok] = freqs.get(tok, 0.0) + 1.0
    for tag in entry.tags or []:
        for tok in tokenize(tag):
            freqs[tok] = freqs.get(tok, 0.0) + _TAG_FIELD_WEIGHT
    return freqs


class BM25Index:
    """BM25 over a fixed set of memory entries (built per retrieve call)."""

    def __init__(self, entries: Sequence) -> None:
        self.entries = list(entries)
        self._tfs: List[Dict[str, float]] = []
        self._df: Dict[str, int] = {}
        total_len = 0.0
        for entry in self.entries:
            tf = _field_term_freqs(entry)
            self._tfs.append(tf)
            total_len += sum(tf.values())
            for term in tf:
                self._df[term] = self._df.get(term, 0) + 1
        self._n = len(self.entries)
        self._avgdl = total_len / self._n if self._n else 1.0

    def _idf(self, term: str) -> float:
        df = self._df.get(term, 0)
        return math.log((self._n - df + 0.5) / (df + 0.5) + 1.0)

    def score(self, query_terms: List[str], idx: int) -> float:
        tf = self._tfs[idx]
        dl = sum(tf.values())
        total = 0.0
        for term in query_terms:
            f = tf.get(term, 0.0)
            if f <= 0:
                continue
            idf = self._idf(term)
            denom = f + _BM25_K1 * (1 - _BM25_B + _BM25_B * dl / self._avgdl)
            total += idf * (f * (_BM25_K1 + 1)) / denom
        return total

    def rank(self, query_terms: List[str]) -> List[Tuple[int, float]]:
        scored = [
            (i, self.score(query_terms, i))
            for i in range(self._n)
            if any(t in self._tfs[i] for t in query_terms)
        ]
        # Deterministic tie-break on entry id.
        scored.sort(key=lambda p: (-p[1], self.entries[p[0]].id))
        return scored


# ---------------------------------------------------------------------------
# Sparse semantic vectors (hashing trick, no model)
# ---------------------------------------------------------------------------

_VECTOR_DIM = 512
_NGRAM_N = 4


def _char_ngrams(text: str, n: int = _NGRAM_N) -> List[str]:
    cleaned = re.sub(r"[^a-z0-9 ]", " ", (text or "").lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) < n:
        return [cleaned] if cleaned else []
    return [cleaned[i : i + n] for i in range(len(cleaned) - n + 1)]


def sparse_vector(text: str, dim: int = _VECTOR_DIM) -> List[float]:
    """Deterministic hashed character-n-gram vector, L2-normalized."""
    vec = [0.0] * dim
    for ng in _char_ngrams(text):
        h = hashlib.md5(ng.encode("utf-8")).digest()
        idx = int.from_bytes(h[:4], "big") % dim
        vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _entry_vector_text(entry) -> str:
    return (entry.content or "") + " " + " ".join(entry.tags or [])


# ---------------------------------------------------------------------------
# Recency + importance
# ---------------------------------------------------------------------------

_DEFAULT_HALFLIFE_HOURS = 24.0 * 7  # one week


def _parse_ts(value) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def recency_factor(entry, half_life_hours: float = _DEFAULT_HALFLIFE_HOURS,
                   now: Optional[datetime] = None) -> float:
    """Exponential decay: 1.0 for brand-new, 0.5 after one half-life."""
    if half_life_hours <= 0:
        return 1.0
    ts = _parse_ts(getattr(entry, "updated_at", None)) or _parse_ts(
        getattr(entry, "created_at", None)
    )
    if ts is None:
        return 0.5  # unknown age: neutral, never zero
    now = now or datetime.now(timezone.utc)
    age_hours = max(0.0, (now - ts).total_seconds() / 3600.0)
    return 0.5 ** (age_hours / half_life_hours)


def corroboration_boost(entry) -> float:
    """Small boost for entries corroborated multiple times (growth loop)."""
    try:
        count = int((entry.metadata or {}).get("corroboration", 0) or 0)
    except (TypeError, ValueError):
        count = 0
    return 1.0 + 0.1 * min(max(count, 0), 5)


def quality_factor(entry, half_life_hours: float = _DEFAULT_HALFLIFE_HOURS,
                   now: Optional[datetime] = None) -> Tuple[float, str]:
    """Combined recency × importance × corroboration multiplier."""
    try:
        importance = float(getattr(entry, "importance", 0.5) or 0.0)
    except (TypeError, ValueError):
        importance = 0.0
    importance = max(0.0, min(1.0, importance))
    rec = recency_factor(entry, half_life_hours, now)
    cor = corroboration_boost(entry)
    # importance/recency modulate but never zero out a lexical/semantic hit
    factor = (0.5 + 0.5 * importance) * (0.5 + 0.5 * rec) * cor
    expl = "importance=%.2f recency=%.2f corroboration×%.2f" % (
        importance, rec, cor)
    return factor, expl


# ---------------------------------------------------------------------------
# Reciprocal rank fusion
# ---------------------------------------------------------------------------

_RRF_K = 60


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[Tuple[str, float]]], k: int = _RRF_K
) -> List[Tuple[str, float]]:
    """Fuse ranked lists of (entry_id, score) → [(entry_id, rrf_score)]."""
    fused: Dict[str, float] = {}
    for ranking in rankings:
        for rank, (eid, _score) in enumerate(ranking):
            fused[eid] = fused.get(eid, 0.0) + 1.0 / (k + rank + 1)
    return sorted(fused.items(), key=lambda p: (-p[1], p[0]))


# ---------------------------------------------------------------------------
# Query expansion
# ---------------------------------------------------------------------------

_MULTI_SPLIT_RE = re.compile(r"\s+or\s+|,|;|\s+and\s+", re.IGNORECASE)


def expand_query(query: str) -> List[str]:
    """Return sub-queries: split multi-queries, expand each with synonyms."""
    parts = [p.strip() for p in _MULTI_SPLIT_RE.split(query) if p.strip()]
    if not parts:
        return []
    expanded = []
    for part in parts:
        raw_terms = [t for t in _TOKEN_RE.findall(part.lower())
                     if t not in _STOPWORDS and len(t) > 1]
        extra: List[str] = []
        for tok in raw_terms:
            for syn in _SYNONYMS.get(tok, ()):
                if syn not in extra:
                    extra.append(syn)
        sub = part + (" " + " ".join(extra) if extra else "")
        expanded.append(sub)
    # De-duplicate while preserving order.
    seen, unique = set(), []
    for sub in expanded:
        if sub not in seen:
            seen.add(sub)
            unique.append(sub)
    return unique


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# Fail-closed diagnostics: last reason retrieve() returned [].
LAST_ERROR: str = ""

_VALID_METHODS = ("bm25", "vector", "hybrid", "recency")


def _retrieve_single(query: str, entries: Sequence, index: BM25Index,
                     vectors: List[List[float]], query_vec: List[float],
                     method: str, half_life_hours: float,
                     now: Optional[datetime]) -> List[Tuple[str, float, str]]:
    """Run one sub-query; return [(entry_id, score, explanation)]."""
    q_terms = tokenize(query)
    if not q_terms and method in ("bm25", "hybrid"):
        return []

    by_id = {e.id: e for e in entries}
    out: List[Tuple[str, float, str]] = []

    if method == "bm25":
        for idx, bm25_score in index.rank(q_terms):
            entry = index.entries[idx]
            qf, qexpl = quality_factor(entry, half_life_hours, now)
            out.append((entry.id, bm25_score * qf,
                        "bm25=%.3f %s" % (bm25_score, qexpl)))
    elif method == "vector":
        scored = []
        for i, entry in enumerate(entries):
            sim = _cosine(query_vec, vectors[i])
            if sim > 0:
                scored.append((entry.id, sim))
        scored.sort(key=lambda p: (-p[1], p[0]))
        for eid, sim in scored:
            qf, qexpl = quality_factor(by_id[eid], half_life_hours, now)
            out.append((eid, sim * qf, "vector=%.3f %s" % (sim, qexpl)))
    elif method == "recency":
        scored = []
        for entry in entries:
            rec = recency_factor(entry, half_life_hours, now)
            try:
                imp = float(getattr(entry, "importance", 0.5) or 0.0)
            except (TypeError, ValueError):
                imp = 0.0
            scored.append((entry.id, rec * (0.5 + 0.5 * max(0.0, min(1.0, imp)))))
        scored.sort(key=lambda p: (-p[1], p[0]))
        for eid, s in scored:
            entry = by_id[eid]
            out.append((eid, s, "recency=%.3f importance=%.2f"
                        % (recency_factor(entry, half_life_hours, now),
                           getattr(entry, "importance", 0.5))))
    else:  # hybrid
        bm25_ranked = [(index.entries[i].id, s)
                       for i, s in index.rank(q_terms)] if q_terms else []
        vec_ranked = []
        for i, entry in enumerate(entries):
            sim = _cosine(query_vec, vectors[i])
            if sim > 0:
                vec_ranked.append((entry.id, sim))
        vec_ranked.sort(key=lambda p: (-p[1], p[0]))
        fused = reciprocal_rank_fusion([bm25_ranked, vec_ranked])
        # Keep per-signal ranks/sims for the explanation.
        bm25_pos = {eid: r for r, (eid, _s) in enumerate(bm25_ranked)}
        vec_pos = {eid: r for r, (eid, _s) in enumerate(vec_ranked)}
        vec_sim = {eid: s for eid, s in vec_ranked}
        for eid, rrf in fused:
            entry = by_id[eid]
            qf, qexpl = quality_factor(entry, half_life_hours, now)
            bpos = bm25_pos.get(eid)
            vpos = vec_pos.get(eid)
            out.append((eid, rrf * qf,
                        "rrf=%.4f bm25_rank=%s vec_rank=%s vec_sim=%.3f %s"
                        % (rrf, bpos, vpos, vec_sim.get(eid, 0.0), qexpl)))
    out.sort(key=lambda p: (-p[1], p[0]))
    return out


def retrieve(query, store, limit: int = 10, method: str = "hybrid",
             half_life_hours: float = _DEFAULT_HALFLIFE_HOURS,
             now: Optional[datetime] = None):
    """Retrieve memory entries for *query*.

    Returns a list of ``(entry, score, explanation)`` tuples, best first.
    *method* is one of ``bm25`` / ``vector`` / ``hybrid`` / ``recency``.

    Fail-closed: never raises. On bad input or internal error returns []
    and records the reason in :data:`LAST_ERROR`. Blank queries return [].
    Deterministic: identical inputs give identical outputs.
    """
    global LAST_ERROR
    LAST_ERROR = ""
    try:
        if not isinstance(query, str) or not query.strip():
            LAST_ERROR = "blank query"
            return []
        if method not in _VALID_METHODS:
            LAST_ERROR = "unknown method %r" % (method,)
            return []
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            LAST_ERROR = "bad limit %r" % (limit,)
            return []
        if limit < 1:
            LAST_ERROR = "non-positive limit"
            return []
        if store is None or not hasattr(store, "list"):
            LAST_ERROR = "store has no list()"
            return []

        entries = list(store.list(limit=100000) or [])
        if not entries:
            LAST_ERROR = "store is empty"
            return []

        index = BM25Index(entries)
        vectors = [sparse_vector(_entry_vector_text(e)) for e in entries]
        by_id = {e.id: e for e in entries}

        sub_queries = expand_query(query)
        if not sub_queries:
            LAST_ERROR = "query has no usable terms"
            return []

        if len(sub_queries) == 1:
            qvec = sparse_vector(sub_queries[0])
            ranked = _retrieve_single(sub_queries[0], entries, index, vectors,
                                      qvec, method, half_life_hours, now)
        else:
            # Multi-query: run each sub-query, fuse with RRF.
            per_q = []
            for sub in sub_queries:
                qvec = sparse_vector(sub)
                ranked_sq = _retrieve_single(sub, entries, index, vectors,
                                             qvec, method, half_life_hours, now)
                per_q.append([(eid, s) for eid, s, _x in ranked_sq])
            fused = reciprocal_rank_fusion(per_q)
            # Rebuild explanations from the first sub-query's run for
            # determinism, then re-score by fused order.
            first = {eid: (s, x) for eid, s, x in _retrieve_single(
                sub_queries[0], entries, index, vectors,
                sparse_vector(sub_queries[0]), method, half_life_hours, now)}
            ranked = []
            for eid, rrf in fused:
                s, x = first.get(eid, (0.0, "multi-query fused"))
                ranked.append((eid, rrf, "multi-query rrf=%.4f | %s" % (rrf, x)))

        results = []
        for eid, score, expl in ranked[:limit]:
            entry = by_id.get(eid)
            if entry is not None:
                results.append((entry, score, expl))
        return results
    except Exception as exc:  # fail closed — never raise to callers
        LAST_ERROR = "%s: %s" % (type(exc).__name__, exc)
        print("retrieval: %s" % LAST_ERROR, file=sys.stderr)
        return []
