"""Demand numbers — a deterministic 0-100 score on every demand signal.

Every signal in the DemandPulse store gets a NUMBER: a transparent,
auditable demand score computed only from the signal's own properties.
The full rubric lives in docs/DEMAND_NUMBERS.md; this module is the
machine that applies it.

LAWS (plain words):
  N1 auditable — every factor carries a ``basis`` string saying exactly
     what evidence produced its value. A number without bases is refused.
  N2 deterministic — the same signal + the same ``now`` always yields the
     same number. No randomness, no hidden state, no network.
  N3 measured, not invented — factors read only signal properties
     (need text, seen_count, created_at, source, segment, kind). Nothing
     is invented about markets, people, or money.
  N4 tier preserved — scoring never changes a signal's kind
     (HYPOTHESIS / INFERENCE / OBSERVED).
  N5 honest about ignorance — a low number means "thin evidence", never
     "no opportunity". Signals with nothing to work with score low.
  N6 calibrated by observed reliability — the five-factor composite is
     multiplied by 0.75 + 0.5*reliability, where reliability is the
     source channel's measured extraction yield (0.5 = unmeasured).
     The multiplier is stated on every number, never hidden.

The opportunities view clusters scored signals into ranked opportunity
rows (one line each: score, what, why, underlying signals, tier) and
reads straight from the store — no shadow system.

Stdlib only. Advisory: a number describes sensed demand; it executes
nothing and touches no money.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# rubric constants (mirrored in docs/DEMAND_NUMBERS.md — change both)

# Canonical factor order — also the tie-break-safe iteration order.
SIGNAL_FACTORS: Tuple[str, ...] = (
    "expression_strength",
    "frequency",
    "recency",
    "source_diversity",
    "domain_match",
)

# Weights must sum to 1.0.
SIGNAL_WEIGHTS: Dict[str, float] = {
    "expression_strength": 0.30,
    "frequency": 0.20,
    "recency": 0.15,
    "source_diversity": 0.15,
    "domain_match": 0.20,
}

_WEIGHT_EPS = 1e-9

# Jaccard threshold for clustering signals into one opportunity row.
CLUSTER_JACCARD = 0.35

# Kind precedence for opportunity-row tiering (strongest wins).
_KIND_RANK = {"OBSERVED": 3, "INFERENCE": 2, "HYPOTHESIS": 1}


# ---------------------------------------------------------------------------
# expression strength — demand markers in the need text (word-boundary match)

# (phrase, points). Matched case-insensitively on word boundaries.
_EXPRESSION_MARKERS: Tuple[Tuple[str, float], ...] = (
    # purchase intent — strongest
    ("willing to pay", 25.0),
    ("would pay", 25.0),
    ("take my money", 25.0),
    ("shut up and take", 25.0),
    ("how much", 20.0),
    ("pricing", 12.0),
    ("price", 12.0),
    ("paid", 12.0),
    ("budget", 12.0),
    ("cost", 8.0),
    # active seeking
    ("looking for", 15.0),
    ("seeking", 15.0),
    ("searching for", 15.0),
    ("in search of", 15.0),
    ("desperate", 15.0),
    ("need", 15.0),
    ("needs", 15.0),
    ("needed", 12.0),
    ("require", 12.0),
    ("requires", 12.0),
    ("want", 12.0),
    ("wants", 12.0),
    # pain
    ("struggling", 12.0),
    ("frustrated", 12.0),
    ("frustrating", 12.0),
    ("painful", 12.0),
    ("broken", 12.0),
    ("doesn't work", 12.0),
    ("does not work", 12.0),
    ("problem", 12.0),
    ("problems", 12.0),
    ("pain", 10.0),
    ("hate", 10.0),
    ("wish", 10.0),
    ("if only", 10.0),
    ("annoying", 8.0),
    # request
    ("help", 10.0),
    ("recommend", 10.0),
    ("recommendation", 10.0),
    ("suggest", 10.0),
    ("suggestion", 10.0),
    ("advice", 10.0),
    ("anyone know", 10.0),
    ("alternatives", 10.0),
    ("alternative", 8.0),
    ("ideas", 8.0),
    ("tips", 6.0),
    # urgency
    ("urgent", 10.0),
    ("asap", 10.0),
    ("immediately", 10.0),
    ("deadline", 10.0),
    ("right now", 8.0),
    ("today", 6.0),
    ("now", 5.0),
)

_EXPRESSION_BASE = 10.0
_EXPRESSION_QUESTION_BONUS = 5.0
_EXPRESSION_LENGTH_CAP = 10.0  # +1 per 10 chars, capped


def _phrase_re(phrase: str) -> "re.Pattern[str]":
    return re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE)


def _factor_expression(text: str) -> Tuple[float, str]:
    """0-100: how strongly the need is phrased."""
    t = str(text or "")
    matched: List[str] = []
    total = _EXPRESSION_BASE
    for phrase, points in _EXPRESSION_MARKERS:
        if _phrase_re(phrase).search(t):
            matched.append(phrase)
            total += points
    if t.rstrip().endswith("?"):
        total += _EXPRESSION_QUESTION_BONUS
        matched.append("(question form)")
    length_bonus = min(_EXPRESSION_LENGTH_CAP, len(t) // 10)
    total += length_bonus
    value = round(min(100.0, total), 2)
    if matched:
        basis = (
            f"base {_EXPRESSION_BASE:.0f} + markers "
            f"[{', '.join(matched)}] + length bonus {length_bonus}"
        )
    else:
        basis = (
            f"base {_EXPRESSION_BASE:.0f} + length bonus {length_bonus}; "
            "no demand markers matched"
        )
    return value, basis


# ---------------------------------------------------------------------------
# frequency — occurrence metadata (repeats are metadata, not new evidence)

def _factor_frequency(distinct_items: int,
                      legacy: bool = False) -> Tuple[float, str]:
    """0-100: log-scaled DISTINCT observed source items.

    ``distinct_items`` is the count of different source items the need was
    mined from (dedup merges origins) — real corroboration. The old code
    counted ``seen_count``, which the RSS double-mining + re-poll loop had
    inflated into a tick counter (avg 12 on the live store). Signals that
    predate item provenance (``legacy=True``) fall back to seen_count and
    the basis says so honestly.
    seen=1 -> 20, seen=12 -> ~74, seen=81+ -> 100.
    """
    n = distinct_items if isinstance(distinct_items, int) and distinct_items >= 1 else 1
    value = round(min(100.0, 20.0 * math.log2(1 + n)), 2)
    basis = f"{n} distinct observed item(s); 20*log2(1+n) capped at 100"
    if legacy:
        basis += " (legacy: no item provenance — seen_count used instead)"
    return value, basis


# ---------------------------------------------------------------------------
# recency — freshness with a 30-day half-life

def _parse_ts(raw: Any) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(str(raw))
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _factor_recency(created_at: Any, now: datetime) -> Tuple[float, str]:
    """0-100: 100 * 2^(-days/30). Fresh today -> 100, 30 days -> 50."""
    dt = _parse_ts(created_at)
    if dt is None:
        return 100.0, "unparseable timestamp — treated as fresh (honest default)"
    days = max(0.0, (now - dt).total_seconds() / 86400.0)
    value = round(100.0 * (2.0 ** (-days / 30.0)), 2)
    return value, f"first seen {days:.1f} day(s) ago; 100*2^(-days/30)"


# ---------------------------------------------------------------------------
# source diversity — corroboration across channels

def _factor_source_diversity(distinct_sources: int) -> Tuple[float, str]:
    """0-100: corroboration across channels.

    50 neutral for a single channel, +25 per extra channel, cap 100.
    Callers pass the count of distinct channels in the signal's
    near-dupe cluster across the store — the same need surfacing in
    rss AND hn is real corroboration. A lone single-channel signal
    stays at the neutral 50.
    """
    n = distinct_sources if isinstance(distinct_sources, int) and distinct_sources >= 1 else 1
    value = round(min(100.0, 50.0 + 25.0 * (n - 1)), 2)
    if n == 1:
        basis = "single channel (no corroborating channels) — neutral 50"
    else:
        basis = f"{n} distinct channels; 50 + 25 per extra channel, capped at 100"
    return value, basis


# ---------------------------------------------------------------------------
# domain match — fit to his known domains (label-level only, never eyes-only)

# NOTE: the "dynasty" domain is matched on its public label only. Dynasty/IP
# material is eyes-only and is NEVER read for matching terms (standing orders).
_DOMAINS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    (
        "levi",
        (
            "levi", "local-first", "offline-first", "on-device", "agent",
            "agents", "automation", "assistant", "productivity", "sidekick",
            "copilot",
        ),
    ),
    (
        "demandpulse",
        (
            "demand", "demandpulse", "opportunity", "opportunities",
            "customers", "market", "sales", "leads", "business idea",
            "startup",
        ),
    ),
    ("dynasty", ("dynasty",)),
    (
        "content",
        (
            "content", "video", "youtube", "tiktok", "post", "posts",
            "newsletter", "audience", "followers", "creator", "stream",
            "podcast",
        ),
    ),
)


def _factor_domain(text: str, segment: str) -> Tuple[float, str]:
    """0-100: 34 points per distinct matched domain term, cap 100."""
    t = str(text or "")
    hits: List[Tuple[str, str]] = []  # (domain, term)
    seen_terms = set()
    for domain, terms in _DOMAINS:
        for term in terms:
            if term in seen_terms:
                continue
            if _phrase_re(term).search(t):
                seen_terms.add(term)
                hits.append((domain, term))
    seg = str(segment or "").strip().lower()
    if seg and seg != "general":
        hits.append(("segment", seg))
    value = round(min(100.0, 34.0 * len(hits)), 2)
    if hits:
        by_domain: Dict[str, List[str]] = {}
        for domain, term in hits:
            by_domain.setdefault(domain, []).append(term)
        parts = [f"{d}: {', '.join(ts)}" for d, ts in by_domain.items()]
        basis = f"{len(hits)} distinct term(s) matched — " + "; ".join(parts)
    else:
        basis = "no domain terms matched (levi/demandpulse/dynasty/content)"
    return value, basis


# ---------------------------------------------------------------------------
# the number

@dataclass(frozen=True)
class FactorNumber:
    """One scored factor: 0-100 value plus the required basis note."""

    name: str
    value: float
    basis: str

    def __post_init__(self) -> None:
        if self.name not in SIGNAL_FACTORS:
            raise ValueError(f"unknown factor {self.name!r}")
        if (
            isinstance(self.value, bool)
            or not isinstance(self.value, (int, float))
            or not math.isfinite(self.value)
            or not 0.0 <= self.value <= 100.0
        ):
            raise ValueError(
                f"factor {self.name!r}: value must be a number in 0-100, "
                f"got {self.value!r}"
            )
        if not str(self.basis).strip():
            raise ValueError(
                f"factor {self.name!r}: basis is required — "
                "a number without a stated reason is rejected"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "value": float(self.value), "basis": self.basis}


@dataclass(frozen=True)
class SignalNumber:
    """The auditable number for one signal."""

    signal_id: str
    composite: float
    factors: Tuple[FactorNumber, ...]
    tier: str  # the signal's kind, preserved untouched (N4)
    scored_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    # Source-reliability calibration (quality build 2026-09-24): the
    # composite is the five-factor weighted sum, then multiplied by
    # 0.75 + 0.5*reliability (0.75x at 0.0, 1.0x neutral at 0.5, 1.25x
    # at 1.0). Reliability is the channel's observed extraction yield;
    # 0.5 is the stated neutral prior when unmeasured.
    reliability: float = 0.5
    reliability_multiplier: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.signal_id, str) or not self.signal_id.strip():
            raise ValueError("signal_id must be a non-empty string")
        if (
            isinstance(self.composite, bool)
            or not isinstance(self.composite, (int, float))
            or not math.isfinite(self.composite)
            or not 0.0 <= self.composite <= 100.0
        ):
            raise ValueError(
                f"composite must be a number in 0-100, got {self.composite!r}"
            )
        names = [f.name for f in self.factors]
        if set(names) != set(SIGNAL_FACTORS):
            raise ValueError(
                f"factors must cover exactly {SIGNAL_FACTORS}; got {sorted(names)}"
            )
        if self.tier not in _KIND_RANK:
            raise ValueError(f"tier must be a signal kind, got {self.tier!r}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "composite": float(self.composite),
            "tier": self.tier,
            "scored_at": self.scored_at,
            "reliability": float(self.reliability),
            "reliability_multiplier": float(self.reliability_multiplier),
            "factors": [f.to_dict() for f in self.factors],
        }

    def explain(self) -> str:
        lines = [f"[{self.signal_id}] number={self.composite:.2f}  tier={self.tier}"]
        for f in self.factors:
            w = SIGNAL_WEIGHTS[f.name]
            lines.append(
                f"  {f.name:20s} value={f.value:6.2f}  weight={w:.2f}  "
                f"contrib={f.value * w:6.2f}"
            )
            lines.append(f"    basis: {f.basis}")
        lines.append(
            f"  reliability      value={self.reliability:6.2f}  "
            f"multiplier={self.reliability_multiplier:.3f}  "
            f"(channel extraction yield; 0.5 = unmeasured)"
        )
        return "\n".join(lines)


def validate_signal_weights(weights: Optional[Dict[str, float]]) -> Dict[str, float]:
    """Return a validated copy of ``weights`` (defaults when None)."""
    if weights is None:
        w = dict(SIGNAL_WEIGHTS)
    elif not isinstance(weights, dict):
        raise ValueError(f"weights must be a dict over {SIGNAL_FACTORS}")
    else:
        w = dict(weights)
    if set(w) != set(SIGNAL_FACTORS):
        raise ValueError(
            f"weights must cover exactly {SIGNAL_FACTORS}; got {sorted(w)}"
        )
    for name, val in w.items():
        if (
            isinstance(val, bool)
            or not isinstance(val, (int, float))
            or not math.isfinite(val)
            or not 0.0 <= val <= 1.0
        ):
            raise ValueError(f"weight {name!r} must be a number in [0, 1]")
    total = sum(w.values())
    if abs(total - 1.0) > _WEIGHT_EPS:
        raise ValueError(f"weights must sum to 1.0, got {total:.6f}")
    return {k: float(v) for k, v in w.items()}


def score_signal(
    signal: Any,
    now: Optional[datetime] = None,
    weights: Optional[Dict[str, float]] = None,
    distinct_sources: int = 1,
    distinct_items: Optional[int] = None,
    legacy_items: bool = False,
    source_reliability: float = 0.5,
) -> SignalNumber:
    """Score one signal. Pure and deterministic.

    ``signal`` needs attributes: id, need, segment, kind, seen_count,
    created_at, source. ``now`` defaults to utcnow (pass it for tests).

    - ``distinct_items``: count of DISTINCT source items the need was
      mined from (dedup-merged origins). None -> falls back to
      seen_count with ``legacy_items=True`` noted in the basis.
    - ``distinct_sources``: distinct channels in the signal's near-dupe
      cluster (cross-channel corroboration).
    - ``source_reliability``: the channel's observed extraction yield,
      0..1 (0.5 = unmeasured neutral). Calibrates the composite by
      0.75 + 0.5*reliability — stated on the number, never hidden.
    """
    w = validate_signal_weights(weights)
    moment = now if now is not None else datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    if (
        isinstance(source_reliability, bool)
        or not isinstance(source_reliability, (int, float))
        or not math.isfinite(source_reliability)
        or not 0.0 <= source_reliability <= 1.0
    ):
        raise ValueError(
            "source_reliability must be a number in [0, 1], "
            f"got {source_reliability!r}"
        )

    need = getattr(signal, "need", "")
    kind = str(getattr(signal, "kind", "HYPOTHESIS"))
    if kind not in _KIND_RANK:
        raise ValueError(f"signal kind must be a known tier, got {kind!r}")

    if distinct_items is None:
        distinct_items = getattr(signal, "seen_count", 1)
        legacy_items = True
    vals = {
        "expression_strength": _factor_expression(need),
        "frequency": _factor_frequency(distinct_items, legacy=legacy_items),
        "recency": _factor_recency(getattr(signal, "created_at", None), moment),
        "source_diversity": _factor_source_diversity(distinct_sources),
        "domain_match": _factor_domain(need, getattr(signal, "segment", "general")),
    }
    factors = tuple(
        FactorNumber(name=n, value=vals[n][0], basis=vals[n][1])
        for n in SIGNAL_FACTORS
    )
    raw = sum(f.value * w[f.name] for f in factors)
    multiplier = round(0.75 + 0.5 * float(source_reliability), 3)
    composite = round(min(100.0, raw * multiplier), 2)
    return SignalNumber(
        signal_id=str(getattr(signal, "id", "?")),
        composite=composite,
        factors=factors,
        tier=kind,
        reliability=round(float(source_reliability), 3),
        reliability_multiplier=multiplier,
    )


# ---------------------------------------------------------------------------
# clustering — signals into opportunity rows

_STOPWORDS = frozenset(
    (
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "to",
        "of", "and", "or", "for", "in", "on", "at", "by", "with", "from",
        "as", "it", "its", "this", "that", "these", "those", "i", "me",
        "my", "we", "our", "you", "your", "he", "she", "they", "them",
        "his", "her", "their", "so", "but", "if", "then", "than", "too",
        "very", "just", "can", "could", "would", "should", "will", "do",
        "does", "did", "have", "has", "had", "not", "no", "yes", "how",
        "what", "when", "where", "why", "which", "who", "am", "im",
        "ive", "dont", "doesnt", "wanna", "gonna", "like", "get", "got",
        "go", "going", "come", "make", "take", "please", "thanks",
        "thank", "hi", "hey", "hello", "all", "any", "some", "more",
        "most", "other", "such", "only", "own", "same", "also", "well",
        "much", "many", "few", "every", "each", "both", "either",
        "neither", "into", "out", "over", "under", "again", "once",
        "here", "there", "about", "up", "down",
    )
)


def _keywords(text: str) -> frozenset:
    toks = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", str(text or "").lower())
    return frozenset(t for t in toks if len(t) >= 3 and t not in _STOPWORDS)


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def cluster_signals(signals: List[Any]) -> List[List[Any]]:
    """Greedy union-find over keyword Jaccard >= CLUSTER_JACCARD.

    Deterministic: signals are processed in id order, so the same store
    always yields the same clusters.
    """
    ordered = sorted(signals, key=lambda s: str(getattr(s, "id", "")))
    kw = [_keywords(getattr(s, "need", "")) for s in ordered]
    parent = list(range(len(ordered)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            # keep the smaller root canonical (deterministic)
            parent[max(ri, rj)] = min(ri, rj)

    for i in range(len(ordered)):
        for j in range(i + 1, len(ordered)):
            if _jaccard(kw[i], kw[j]) >= CLUSTER_JACCARD:
                union(i, j)

    groups: Dict[int, List[Any]] = {}
    for i, s in enumerate(ordered):
        groups.setdefault(find(i), []).append(s)
    # deterministic order: by the smallest member id in each cluster
    return sorted(groups.values(), key=lambda g: str(getattr(g[0], "id", "")))


# ---------------------------------------------------------------------------
# opportunity rows

@dataclass(frozen=True)
class OpportunityRow:
    """One ranked opportunity: an aggregate of scored signals."""

    id: str
    title: str
    score: float
    tier: str
    why: str
    signals: Tuple[Dict[str, Any], ...]
    member_count: int
    total_sightings: int
    distinct_sources: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "score": float(self.score),
            "tier": self.tier,
            "why": self.why,
            "member_count": self.member_count,
            "total_sightings": self.total_sightings,
            "distinct_sources": self.distinct_sources,
            "signals": [dict(s) for s in self.signals],
        }


def _signal_number(sig: Any, now: Optional[datetime]) -> float:
    n = getattr(sig, "number", None)
    if isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n):
        # not yet scored in the store — score on the fly (deterministic)
        return score_signal(sig, now=now).composite
    return round(float(n), 2)


def opportunity_rows(
    signals: List[Any], now: Optional[datetime] = None
) -> List[OpportunityRow]:
    """Aggregate scored signals into ranked opportunity rows.

    Row score = mean of member signal numbers. Rank: score desc, id asc.
    Tier = strongest member kind (OBSERVED > INFERENCE > HYPOTHESIS).
    """
    rows: List[OpportunityRow] = []
    for members in cluster_signals(signals):
        nums = [_signal_number(s, now) for s in members]
        score = round(sum(nums) / len(nums), 2)
        tier = max(
            (str(getattr(s, "kind", "HYPOTHESIS")) for s in members),
            key=lambda k: _KIND_RANK.get(k, 0),
        )
        rep_idx = max(
            range(len(members)), key=lambda i: (nums[i], str(getattr(members[i], "id", "")))
        )
        rep = members[rep_idx]
        rep_num = score_signal(rep, now=now)
        member_ids = sorted(str(getattr(s, "id", "")) for s in members)
        row_id = "opp-" + hashlib.sha256("|".join(member_ids).encode()).hexdigest()[:8]
        total_sightings = sum(
            getattr(s, "seen_count", 1)
            if isinstance(getattr(s, "seen_count", 1), int)
            else 1
            for s in members
        )
        sources = sorted({str(getattr(s, "source", "?")) for s in members})
        factor_bits = " ".join(
            f"{f.name.split('_')[0][:4]}={f.value:.1f}" for f in rep_num.factors
        )
        why = (
            f"representative [{getattr(rep, 'id', '?')}] {factor_bits} | "
            f"{len(members)} signal(s), {total_sightings} sightings, "
            f"{len(sources)} channel(s): {', '.join(sources)}"
        )
        sig_rows = tuple(
            {
                "id": str(getattr(s, "id", "")),
                "number": nums[i],
                "kind": str(getattr(s, "kind", "HYPOTHESIS")),
                "source": str(getattr(s, "source", "?")),
                "seen_count": getattr(s, "seen_count", 1),
                "need": str(getattr(s, "need", ""))[:120],
            }
            for i, s in enumerate(members)
        )
        rows.append(
            OpportunityRow(
                id=row_id,
                title=str(getattr(rep, "need", ""))[:120],
                score=score,
                tier=tier,
                why=why,
                signals=sig_rows,
                member_count=len(members),
                total_sightings=total_sightings,
                distinct_sources=len(sources),
            )
        )
    return sorted(rows, key=lambda r: (-r.score, r.id))


def render_rows(rows: List[OpportunityRow], signal_total: int, rescored: int) -> str:
    """One ranked line per opportunity, plus the why-line."""
    lines = [
        f"=== DemandPulse opportunities: {len(rows)} from {signal_total} signals "
        f"({rescored} scored this run) ===",
        "",
    ]
    if not rows:
        lines.append("(no signals in the store — ingest some with watcher/eyes/scan first)")
        return "\n".join(lines)
    for i, r in enumerate(rows, 1):
        lines.append(f"#{i:<3d} {r.score:6.2f}  [{r.tier}] {r.title}")
        lines.append(f"       why: {r.why}")
        lines.append(f"       id: {r.id}")
    lines.append("")
    lines.append("Numbers are sensed-demand scores (HYPOTHESIS/INFERENCE/OBSERVED) —")
    lines.append("advisory only. Rubric: docs/DEMAND_NUMBERS.md")
    return "\n".join(lines)
