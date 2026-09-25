"""DemandPulse deep competitor intel — price/tactic/userbase/hiring extraction.

Hyper-aggressive SCAN, polite READS: this module widens *what* is extracted
from competitor pages (prices, feature launches, positioning shifts,
user-base signals, hiring) and *how often* pages are re-scanned — it never
widens how hard any single read hits a server (one request per page per
run, proper User-Agent, no retry loops, 1s between pages; see
competition.fetch_page).

LAWS:
  L1 Honest labels: every extracted fact carries label OBSERVED + the
     source URL + the snapshot's fetched date + a confidence. Nothing is
     invented — extraction can only surface text that was actually on the
     page. Anything uncertain is flagged, never presented as fact.
  L2 Advisory only: extraction reads the world and changes nothing. Move
     records feed HYPOTHESIS proposals and HYPOTHESIS signals; they never
     self-apply and never touch money.
  L3 Deterministic: same snapshot text in, same intel out. No randomness.
  L4 Graceful: bad input (empty text, malformed records) yields empty
     results, never an exception.

stdlib-only.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Price extraction
# ---------------------------------------------------------------------------

_CURRENCY = {"$": "USD", "\u20ac": "EUR", "\u00a3": "GBP"}

_AMOUNT = r"(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)"

_PRICE_MO = re.compile(
    r"([$€£])\s?" + _AMOUNT + r"\s*(?:/\s?|\s+per\s+)?(month|mo|monthly)\b",
    re.IGNORECASE,
)
_PRICE_YR = re.compile(
    r"([$€£])\s?"
    + _AMOUNT
    + r"\s*(?:/\s?|\s+per\s+)?(year|yr|yearly|annually|billed annually)\b",
    re.IGNORECASE,
)
_PRICE_FREE = re.compile(r"\b(free\s+(?:plan|tier|trial|forever)?)\b", re.IGNORECASE)
_PRICE_CUSTOM = re.compile(
    r"\b(contact sales|talk to sales|custom pricing|request(?:ing)? (?:a )?quote|"
    r"get a quote|enterprise pricing)\b",
    re.IGNORECASE,
)


def _parse_amount(raw: str) -> Optional[float]:
    try:
        return float(raw.replace(",", ""))
    except (ValueError, TypeError):
        return None


def _tier_context(text: str, match_start: int) -> str:
    """Best-effort tier name: the last few words before the price.

    Matching (see _norm_tier) keys on the final word only — tier names are
    usually one word ("Starter", "Pro") while the preceding copy shifts
    between snapshots.
    """
    window = text[max(0, match_start - 120) : match_start]
    words = re.findall(r"[A-Za-z0-9&+]+", window)
    return " ".join(words[-3:])[:60]


def _sentences(text: str) -> List[str]:
    """Split collapsed page text into sentences (extracted text has no
    newlines — whitespace is collapsed by competition._extract_text)."""
    parts = re.split(r"(?<=[.!?;])\s+", text or "")
    return [p.strip() for p in parts if p.strip()]


def extract_prices(text: str, max_facts: int = 12) -> List[Dict[str, Any]]:
    """Pull price points out of page text. Only what is on the page.

    Returns facts like {"tier", "price_monthly", "currency", "raw",
    "label": "OBSERVED", "confidence"}. Yearly prices are normalized to
    monthly (price_monthly = yearly / 12, noted in raw). "Free" and
    "contact sales" markers become price_monthly 0.0 / None respectively.
    Never invents a tier or a number.
    """
    if not isinstance(text, str) or not text:
        return []
    facts: List[Dict[str, Any]] = []
    seen = set()

    def _add(tier: str, monthly: Optional[float], currency: str, raw: str,
             confidence: str) -> None:
        key = (tier.lower(), monthly, currency)
        if key in seen:
            return
        seen.add(key)
        facts.append(
            {
                "tier": tier or "unspecified tier",
                "price_monthly": monthly,
                "currency": currency,
                "raw": raw[:80],
                "label": "OBSERVED",
                "confidence": confidence,
                "note": "scraped from public pricing text; "
                "verify on the live page before quoting",
            }
        )

    for rx, per in ((_PRICE_MO, "month"), (_PRICE_YR, "year")):
        for m in rx.finditer(text):
            if len(facts) >= max_facts:
                break
            sym, amount, _unit = m.group(1), m.group(2), m.group(3)
            value = _parse_amount(amount)
            if value is None:
                continue
            monthly = round(value / 12, 2) if per == "year" else value
            _add(
                _tier_context(text, m.start()),
                monthly,
                _CURRENCY.get(sym, sym),
                m.group(0).strip(),
                "high" if per == "month" else "medium",
            )
    for m in _PRICE_FREE.finditer(text):
        if len(facts) >= max_facts:
            break
        _add(_tier_context(text, m.start()), 0.0, "", m.group(0).strip(), "high")
    for m in _PRICE_CUSTOM.finditer(text):
        if len(facts) >= max_facts:
            break
        _add(
            _tier_context(text, m.start()),
            None,
            "",
            m.group(0).strip(),
            "high",
        )
    return facts[:max_facts]


def _norm_tier(tier: str) -> str:
    # Key on the final word: "for everyone Starter" and "for teams
    # Starter" are the same tier across snapshots.
    toks = re.findall(r"[a-z0-9]+", (tier or "").lower())
    return toks[-1] if toks else ""


def detect_price_changes(
    old: List[Dict[str, Any]], new: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Match tiers across two price lists; flag changed monthly prices.

    Pure + deterministic. Only flags when both sides have a numeric
    price_monthly for the same normalized tier. Returns move records.
    """
    moves: List[Dict[str, Any]] = []
    try:
        old_by_tier = {_norm_tier(p.get("tier", "")): p for p in old or []}
        new_by_tier = {_norm_tier(p.get("tier", "")): p for p in new or []}
    except Exception:
        return []
    for tier_key, np_ in sorted(new_by_tier.items()):
        op = old_by_tier.get(tier_key)
        if not op:
            continue  # new tier, not a change — surfaced as a launch instead
        o_val, n_val = op.get("price_monthly"), np_.get("price_monthly")
        if o_val is None or n_val is None:
            continue
        try:
            if abs(float(n_val) - float(o_val)) < 1e-9:
                continue
            pct = (
                round((float(n_val) - float(o_val)) / float(o_val) * 100, 1)
                if float(o_val)
                else None
            )
        except (TypeError, ValueError):
            continue
        moves.append(
            {
                "kind": "price_change",
                "tier": np_.get("tier") or op.get("tier"),
                "old_monthly": o_val,
                "new_monthly": n_val,
                "pct": pct,
                "currency": np_.get("currency") or op.get("currency"),
                "label": "OBSERVED",
            }
        )
    return moves


# ---------------------------------------------------------------------------
# Tactics: feature launches + positioning shifts
# ---------------------------------------------------------------------------

_LAUNCH_LINE = re.compile(
    r"\b(introducing|announcing|we'?ve launched|just launched|now live|"
    r"what'?s new|new feature|changelog|version \d+\.\d+|"
    r"launch(?:ed|ing)?)\b",
    re.IGNORECASE,
)


def extract_tactics(text: str, max_samples: int = 10) -> Dict[str, Any]:
    """Feature-launch markers + a positioning fingerprint from page text."""
    out: Dict[str, Any] = {
        "feature_launches": [],
        "positioning": "",
        "label": "OBSERVED",
    }
    if not isinstance(text, str) or not text:
        return out
    seen = set()
    for sent in _sentences(text):
        s = sent
        if len(s) > 220:
            continue
        if _LAUNCH_LINE.search(s):
            key = s.lower()
            if key not in seen:
                seen.add(key)
                out["feature_launches"].append(s[:200])
                if len(out["feature_launches"]) >= max_samples:
                    break
    # Positioning fingerprint: the page's opening sentences (usually the
    # H1 / hero copy) — diffed run-over-run to catch repositioning.
    out["positioning"] = " | ".join(_sentences(text)[:2])[:200]
    return out


def detect_positioning_shift(
    old_pos: str, new_pos: str
) -> Optional[Dict[str, Any]]:
    """Non-empty differing fingerprints -> a positioning-shift move."""
    if not old_pos or not new_pos:
        return None
    if old_pos.strip() == new_pos.strip():
        return None
    return {
        "kind": "positioning_shift",
        "old": old_pos[:200],
        "new": new_pos[:200],
        "label": "OBSERVED",
    }


# ---------------------------------------------------------------------------
# User-base signals (review counts, ratings, customer counts, followers)
# ---------------------------------------------------------------------------

_REVIEWS = re.compile(
    r"(\d[\d,]*(?:\.\d+)?)\s*\+?\s*reviews?\b", re.IGNORECASE
)
_RATING = re.compile(r"\b([0-4]\.\d|\d\.0)\s*(?:/\s*5|out of 5|\s*stars?)\b")
_CUSTOMERS = re.compile(
    r"(\d[\d,]*(?:\.\d+)?[kKmM]?)\+?\s*"
    r"(customers|users|companies|teams|businesses|marketers|brands)\b",
    re.IGNORECASE,
)
_TRUSTED_BY = re.compile(
    r"trusted by\s+(\d[\d,]*(?:\.\d+)?[kKmM]?)\+?", re.IGNORECASE
)
_FOLLOWERS = re.compile(
    r"(\d[\d,.]*(?:[kKmM])?)\s*(followers|subscribers)\b", re.IGNORECASE
)


def _to_number(raw: str) -> Optional[float]:
    try:
        s = raw.strip().replace(",", "")
        mult = 1.0
        if s[-1:] in ("k", "K"):
            mult, s = 1000.0, s[:-1]
        elif s[-1:] in ("m", "M"):
            mult, s = 1_000_000.0, s[:-1]
        value = float(s) * mult
        if not 0 < value < 1e12:
            return None
        return value
    except (ValueError, IndexError):
        return None


def extract_userbase(text: str, max_facts: int = 10) -> List[Dict[str, Any]]:
    """Scrape user-base proof points from page text. Observed only.

    Captures review counts, ratings, customer/user counts, "trusted by"
    figures, and follower counts. Every fact carries source context and a
    verify-before-quoting note. Never invents a number.
    """
    if not isinstance(text, str) or not text:
        return []
    facts: List[Dict[str, Any]] = []
    seen = set()

    def _add(metric: str, value: float, raw: str) -> None:
        key = (metric, value)
        if key in seen:
            return
        seen.add(key)
        facts.append(
            {
                "metric": metric,
                "value": value,
                "raw": raw[:80],
                "label": "OBSERVED",
                "confidence": "medium",
                "note": "scraped from public page text; "
                "verify on the live page before quoting",
            }
        )

    for m in _REVIEWS.finditer(text):
        v = _to_number(m.group(1))
        if v is not None:
            _add("review_count", v, m.group(0).strip())
    for m in _RATING.finditer(text):
        try:
            v = float(m.group(1))
        except ValueError:
            continue
        if 0 < v <= 5:
            _add("rating_out_of_5", v, m.group(0).strip())
    for m in _CUSTOMERS.finditer(text):
        v = _to_number(m.group(1))
        if v is not None:
            _add(f"{m.group(2).lower()}_count", v, m.group(0).strip())
    for m in _TRUSTED_BY.finditer(text):
        v = _to_number(m.group(1))
        if v is not None:
            _add("trusted_by_count", v, m.group(0).strip())
    for m in _FOLLOWERS.finditer(text):
        v = _to_number(m.group(1))
        if v is not None:
            _add(f"{m.group(2).lower()}_count", v, m.group(0).strip())
    return facts[:max_facts]


# ---------------------------------------------------------------------------
# Hiring signals — their job posts show where they are investing
# ---------------------------------------------------------------------------

_OPEN_ROLES = re.compile(
    r"(\d[\d,]*)\s*open\s+(roles|positions|jobs)\b", re.IGNORECASE
)
_DEPTS = (
    "engineering",
    "sales",
    "marketing",
    "product",
    "data",
    "design",
    "support",
    "operations",
)


def extract_hiring(text: str) -> Dict[str, Any]:
    """Hiring-investment signals from careers/job page text."""
    out: Dict[str, Any] = {
        "open_roles_mentions": [],
        "dept_hits": {},
        "label": "OBSERVED",
    }
    if not isinstance(text, str) or not text:
        return out
    for m in _OPEN_ROLES.finditer(text):
        try:
            out["open_roles_mentions"].append(int(m.group(1).replace(",", "")))
        except ValueError:
            continue
    low = text.lower()
    for dept in _DEPTS:
        n = len(re.findall(r"\b" + dept + r"\b", low))
        if n:
            out["dept_hits"][dept] = n
    return out


# ---------------------------------------------------------------------------
# Per-page intel + run-over-run diffing
# ---------------------------------------------------------------------------


def scan_page_intel(record: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the full intel surface from one page snapshot record."""
    text = (record or {}).get("text") or ""
    tactics = extract_tactics(text)
    return {
        "url": (record or {}).get("url", ""),
        "fetched_at": (record or {}).get("fetched_at"),
        "prices": extract_prices(text),
        "feature_launches": tactics["feature_launches"],
        "positioning": tactics["positioning"],
        "userbase": extract_userbase(text),
        "hiring": extract_hiring(text),
        "label": "OBSERVED",
    }


def _userbase_by_metric(facts: List[Dict[str, Any]]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for f in facts or []:
        try:
            out[str(f.get("metric"))] = float(f.get("value"))
        except (TypeError, ValueError):
            continue
    return out


def diff_intel(
    old: Dict[str, Any], new: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Diff two per-page intel dicts -> competitor move records.

    Pure + deterministic. Moves: price_change, feature_launch,
    positioning_shift, userbase_change, hiring_change. Every move is
    OBSERVED (it names a real before/after on a real page).
    """
    moves: List[Dict[str, Any]] = []
    try:
        url = new.get("url") or old.get("url") or ""
        to_ts = new.get("fetched_at")
        from_ts = old.get("fetched_at")

        def _stamp(move: Dict[str, Any]) -> Dict[str, Any]:
            move.update(
                {
                    "url": url,
                    "from": from_ts,
                    "to": to_ts,
                    "observed_at": to_ts,
                    "label": "OBSERVED",
                }
            )
            return move

        for pc in detect_price_changes(old.get("prices"), new.get("prices")):
            moves.append(_stamp(pc))

        shift = detect_positioning_shift(
            old.get("positioning") or "", new.get("positioning") or ""
        )
        if shift:
            moves.append(_stamp(shift))

        old_launches = {s.lower() for s in old.get("feature_launches") or []}
        for s in new.get("feature_launches") or []:
            if s.lower() not in old_launches:
                moves.append(
                    _stamp({"kind": "feature_launch", "text": s[:200]})
                )

        old_ub = _userbase_by_metric(old.get("userbase"))
        new_ub = _userbase_by_metric(new.get("userbase"))
        for metric, nval in sorted(new_ub.items()):
            oval = old_ub.get(metric)
            if oval is None or oval == nval:
                continue
            moves.append(
                _stamp(
                    {
                        "kind": "userbase_change",
                        "metric": metric,
                        "old": oval,
                        "new": nval,
                    }
                )
            )

        old_roles = (old.get("hiring") or {}).get("open_roles_mentions") or []
        new_roles = (new.get("hiring") or {}).get("open_roles_mentions") or []
        if old_roles != new_roles and (old_roles or new_roles):
            moves.append(
                _stamp(
                    {
                        "kind": "hiring_change",
                        "old": old_roles,
                        "new": new_roles,
                    }
                )
            )
    except Exception:
        return []
    return moves


# ---------------------------------------------------------------------------
# Impact scoring — observed moves -> advisory boost (INFERENCE)
# ---------------------------------------------------------------------------

_MOVE_POINTS = {
    "price_change": 8,
    "feature_launch": 5,
    "positioning_shift": 4,
    "userbase_change": 6,
    "hiring_change": 4,
}
_BOOST_CAP = 20


def score_competitor_impact(moves: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Turn observed competitor moves into a bounded advisory boost.

    Deterministic: same moves in, same boost out. The boost is INFERENCE
    (a judgment about urgency); the moves it cites are OBSERVED.
    Capped at 20 points so one noisy page can never dominate a score.
    """
    total = 0
    by_kind: Dict[str, int] = {}
    try:
        for m in moves or []:
            kind = (m or {}).get("kind")
            pts = _MOVE_POINTS.get(kind, 0)
            total += pts
            by_kind[kind] = by_kind.get(kind, 0) + 1
    except Exception:
        total, by_kind = 0, {}
    boost = min(_BOOST_CAP, total)
    reasons = [
        f"{count} observed {kind.replace('_', ' ')}(s) "
        f"(OBSERVED snapshots; +{min(_BOOST_CAP, count * _MOVE_POINTS.get(kind, 0))} urgency)"
        for kind, count in sorted(by_kind.items())
        if kind in _MOVE_POINTS
    ]
    return {
        "boost_points": boost,
        "cap": _BOOST_CAP,
        "moves_considered": len(moves or []),
        "reasons": reasons,
        "label": "INFERENCE",
        "note": "urgency judgment over observed moves; not a measurement",
    }


# ---------------------------------------------------------------------------
# Competitor news — funding / launch coverage via keyless news RSS
# ---------------------------------------------------------------------------


def competitor_news(name: str, max_items: int = 5) -> List[Dict[str, Any]]:
    """Funding/launch news for one competitor via Google News RSS.

    Keyless, one polite request. Returns [] on any failure. Items are
    OBSERVED (real headlines); their implications stay HYPOTHESIS.
    """
    try:
        from levi.demand import ingest as _ing
    except Exception:
        return []
    try:
        hits = _ing.fetch_google_news(f'"{name}" funding OR launch OR raises')
    except Exception:
        return []
    out: List[Dict[str, Any]] = []
    for h in (hits or [])[:max_items]:
        if not isinstance(h, dict) or not h.get("text"):
            continue
        out.append(
            {
                "headline": h["text"][:200],
                "url": h.get("url", ""),
                "published": (h.get("metadata") or {}).get("published", ""),
                "outlet": (h.get("metadata") or {}).get("outlet", ""),
                "label": "OBSERVED",
            }
        )
    return out


def move_text(move: Dict[str, Any], competitor: str) -> str:
    """Deterministic one-line signal text for a competitor move."""
    kind = move.get("kind", "change")
    if kind == "price_change":
        pct = move.get("pct")
        pct_s = f" ({pct:+.1f}%)" if isinstance(pct, (int, float)) else ""
        return (
            f"PRICE CHANGE: {competitor} {move.get('tier', '')} "
            f"${move.get('old_monthly')}/mo -> ${move.get('new_monthly')}/mo"
            f"{pct_s} [{move.get('url', '')}]"
        )
    if kind == "feature_launch":
        return f"FEATURE LAUNCH: {competitor}: {move.get('text', '')[:160]}"
    if kind == "positioning_shift":
        return (
            f"POSITIONING SHIFT: {competitor}: "
            f"'{move.get('old', '')[:80]}' -> '{move.get('new', '')[:80]}'"
        )
    if kind == "userbase_change":
        return (
            f"USERBASE CHANGE: {competitor} {move.get('metric')}: "
            f"{move.get('old')} -> {move.get('new')}"
        )
    if kind == "hiring_change":
        return (
            f"HIRING CHANGE: {competitor} open roles {move.get('old')} -> "
            f"{move.get('new')}"
        )
    return f"COMPETITOR MOVE: {competitor} {kind} [{move.get('url', '')}]"


def intel_generated_at() -> str:
    return datetime.now(timezone.utc).isoformat()
