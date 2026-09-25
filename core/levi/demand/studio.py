"""Wave Pulse (module: studio) — content intelligence machine.

DemandPulse detects demand; Wave Pulse determines content. It watches what
is performing right now on Reddit, X, Facebook/Instagram, and TikTok —
especially from monetized or monetization-adjacent creators — grades it on
one interpenetrated quality model, extracts the patterns, and emits an
agent brief for creating ORIGINAL text + video posts.

Honesty rules (inherited from DemandPulse):
- Every grade is a hypothesis/advisory, never a claim about real earnings.
- No pipeline guarantees income. This raises odds; it does not promise them.
- Briefs say REWRITE, never copy. Patterns are spirit, not text.

Unified Quality Grade (interpenetrated across the four platforms):
    grade = 0.35*Attention + 0.30*Propagation + 0.20*Conversation
            + 0.15*Originality, then x velocity multiplier (0.8-1.3).

Components are computed from whatever metrics are available and reweighted;
``coverage`` records how much of the expected input was present.
"""

from __future__ import annotations

import json
import math
import os
import re
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from levi.demand.engines import (
    engine_info as _engine_info,
    list_engines as _list_engines,
    load_engine_prompt as _load_engine_prompt,
)


def list_engines() -> List[str]:
    """Content engine keys available to brief generation, sorted."""
    return _list_engines()


def engine_info(name: str) -> Dict[str, str]:
    """Metadata for a content engine; raises KeyError on unknown names."""
    return _engine_info(name)


def load_engine_prompt(name: str) -> str:
    """Load a content engine's prompt spec verbatim."""
    return _load_engine_prompt(name)

# ---------------------------------------------------------------------------
# Platforms & formats
# ---------------------------------------------------------------------------

REDDIT = "reddit"
X = "x"
FACEBOOK = "facebook"
INSTAGRAM = "instagram"
TIKTOK = "tiktok"
PLATFORMS = (REDDIT, X, FACEBOOK, INSTAGRAM, TIKTOK)

SHORT_VIDEO = "short_video"  # <60s vertical
LONG_VIDEO = "long_video"  # 60s+ vertical
TEXT_THREAD = "text_thread"
CAROUSEL = "carousel"
IMAGE = "image"
FORMATS = (SHORT_VIDEO, LONG_VIDEO, TEXT_THREAD, CAROUSEL, IMAGE)

GRADE_THRESHOLD = 75.0  # patterns are extracted only from winners >= this

W_ATTENTION = 0.35
W_PROPAGATION = 0.30
W_CONVERSATION = 0.20
W_ORIGINALITY = 0.15


def _levi_home() -> Path:
    return Path(os.environ.get("LEVI_HOME", Path.home() / ".levi"))


def _store_dir() -> Path:
    d = _levi_home() / "demand" / "wavepulse"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# ContentSignal
# ---------------------------------------------------------------------------


@dataclass
class ContentSignal:
    """One observed post. Every metric optional; missing = unknown, not zero."""

    id: str
    platform: str
    text: str = ""
    format: str = TEXT_THREAD
    author: str = ""
    author_monetized: Optional[bool] = None  # None = unknown
    url: str = ""
    posted_at: str = ""  # ISO 8601
    hashtags: List[str] = field(default_factory=list)
    sound: str = ""
    metrics: Dict[str, float] = field(default_factory=dict)
    # Known metric keys: views, likes, shares, saves, comments, reposts,
    # quotes, bookmarks, upvotes, crossposts, awards, followers,
    # completion_rate (0-100), avg_watch_s, duration_s, rewatches,
    # dwell_s, dm_shares, copy_link_shares, author_replies (0/1)

    def age_hours(self) -> Optional[float]:
        if not self.posted_at:
            return None
        try:
            dt = datetime.fromisoformat(self.posted_at)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0)
        except ValueError:
            return None

    def m(self, key: str) -> Optional[float]:
        v = self.metrics.get(key)
        return None if v is None else float(v)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "platform": self.platform,
            "text": self.text,
            "format": self.format,
            "author": self.author,
            "author_monetized": self.author_monetized,
            "url": self.url,
            "posted_at": self.posted_at,
            "hashtags": self.hashtags,
            "sound": self.sound,
            "metrics": self.metrics,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ContentSignal":
        return cls(
            id=str(d.get("id", "")),
            platform=str(d.get("platform", "")),
            text=str(d.get("text", "")),
            format=str(d.get("format", TEXT_THREAD)),
            author=str(d.get("author", "")),
            author_monetized=d.get("author_monetized"),
            url=str(d.get("url", "")),
            posted_at=str(d.get("posted_at", "")),
            hashtags=list(d.get("hashtags") or []),
            sound=str(d.get("sound", "")),
            metrics={k: float(v) for k, v in (d.get("metrics") or {}).items()},
        )


# ---------------------------------------------------------------------------
# Adapters — how signals get in
# ---------------------------------------------------------------------------


class AdapterUnavailable(Exception):
    """Raised when an adapter needs credentials the user has not provided."""


class SignalAdapter:
    """Base: fetch(query, limit) -> list[ContentSignal]."""

    name = "base"

    def available(self) -> bool:
        return True

    def fetch(self, query: str, limit: int = 25) -> List[ContentSignal]:
        raise NotImplementedError


class LocalFileAdapter(SignalAdapter):
    """Works today: import signals from a JSONL file (one object per line)."""

    name = "local"

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def fetch(self, query: str = "", limit: int = 25) -> List[ContentSignal]:
        out: List[ContentSignal] = []
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(ContentSignal.from_dict(json.loads(line)))
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
                if len(out) >= limit:
                    break
        if query:
            q = query.lower()
            out = [s for s in out if q in s.text.lower()]
        return out


def parse_reddit_listing(payload: Dict[str, Any]) -> List[ContentSignal]:
    """Pure parser for a reddit /hot.json (or /top.json) listing payload."""
    out: List[ContentSignal] = []
    for child in (payload.get("data") or {}).get("children", []):
        d = child.get("data") or {}
        post_id = str(d.get("id", ""))
        if not post_id:
            continue
        title = str(d.get("title", ""))
        selftext = str(d.get("selftext", ""))
        text = (title + ("\n" + selftext if selftext else "")).strip()[:2000]
        try:
            posted = datetime.fromtimestamp(
                float(d.get("created_utc", 0)), tz=timezone.utc
            ).isoformat()
        except (TypeError, ValueError):
            posted = ""
        out.append(
            ContentSignal(
                id=f"reddit:{post_id}",
                platform=REDDIT,
                text=text,
                format=TEXT_THREAD,
                author=str(d.get("author", "")),
                url="https://www.reddit.com" + str(d.get("permalink", "")),
                posted_at=posted,
                metrics={
                    "upvotes": float(d.get("score", 0) or 0),
                    "comments": float(d.get("num_comments", 0) or 0),
                    "crossposts": float(d.get("num_crossposts", 0) or 0),
                    "awards": float(
                        sum(
                            a.get("count", 0)
                            for a in (d.get("all_awardings") or [])
                            if isinstance(a, dict)
                        )
                    ),
                },
            )
        )
    return out


class RedditPublicAdapter(SignalAdapter):
    """Works today, no key: reddit's public JSON listings (rate-limited)."""

    name = "reddit"

    def __init__(self, sort: str = "hot"):
        self.sort = sort

    def fetch(self, query: str, limit: int = 25) -> List[ContentSignal]:
        sub = query.strip().lstrip("r/") or "all"
        url = f"https://www.reddit.com/r/{sub}/{self.sort}.json?limit={min(limit, 100)}"
        req = urllib.request.Request(
            url, headers={"User-Agent": "levi-wavepulse/1.0 (content research)"}
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                payload = json.loads(resp.read().decode("utf-8", "replace"))
        except Exception as exc:  # network, rate limit, bad sub — all honest
            raise AdapterUnavailable(f"reddit fetch failed: {exc}") from exc
        return parse_reddit_listing(payload)[:limit]


class _KeyedAdapter(SignalAdapter):
    """Base for adapters that need a credential the user has not supplied."""

    env_var = ""
    howto = ""

    def available(self) -> bool:
        return bool(os.environ.get(self.env_var))

    def fetch(self, query: str, limit: int = 25) -> List[ContentSignal]:
        raise AdapterUnavailable(
            f"{self.name} needs {self.env_var}. {self.howto} "
            "Until then, use the local JSONL adapter."
        )


class TikTokAdapter(_KeyedAdapter):
    name = "tiktok"
    env_var = "TIKTOK_API_KEY"
    howto = "Get a key from the TikTok Creative Center / Research API."


class XAdapter(_KeyedAdapter):
    name = "x"
    env_var = "X_BEARER_TOKEN"
    howto = "Get a bearer token from the X developer portal (Basic tier+)."


class MetaAdapter(_KeyedAdapter):
    name = "meta"
    env_var = "META_ACCESS_TOKEN"
    howto = "Get a token via Meta Business Suite / Graph API for your Page."


ADAPTERS: Dict[str, type] = {
    "local": LocalFileAdapter,
    "reddit": RedditPublicAdapter,
    "tiktok": TikTokAdapter,
    "x": XAdapter,
    "meta": MetaAdapter,
}


# ---------------------------------------------------------------------------
# Scoring — the interpenetrated Quality Grade
# ---------------------------------------------------------------------------


def _mean(parts: List[float]) -> Optional[float]:
    return sum(parts) / len(parts) if parts else None


def _cap100(x: float) -> float:
    return max(0.0, min(100.0, x))


def attention_score(sig: ContentSignal) -> Tuple[Optional[float], str]:
    """How deeply people stay. Blends completion, watch/dwell, rewatches."""
    parts: List[float] = []
    notes: List[str] = []
    cr = sig.m("completion_rate")
    if cr is not None:
        parts.append(_cap100(cr))
        notes.append("completion_rate")
    aw, dur = sig.m("avg_watch_s"), sig.m("duration_s")
    if aw is not None and dur:
        parts.append(_cap100(100.0 * aw / dur))
        notes.append("watch/duration")
    rw, views = sig.m("rewatches"), sig.m("views")
    if rw is not None and views:
        parts.append(_cap100(100.0 * (rw / views) * 10.0))
        notes.append("rewatches")
    dwell = sig.m("dwell_s")
    if dwell is not None:
        parts.append(_cap100(dwell * 2.0))
        notes.append("dwell")
    if not parts:
        return None, "no attention inputs"
    return _cap100(_mean(parts) or 0.0), "+".join(notes)


def propagation_score(sig: ContentSignal) -> Tuple[Optional[float], str]:
    """How strongly people push it outward: shares, saves, DMs, crossposts."""
    views = sig.m("views") or sig.m("followers")
    shares = sig.m("shares") or 0.0
    saves = sig.m("saves") or 0.0
    dm = (sig.m("dm_shares") or 0.0) + (sig.m("copy_link_shares") or 0.0)
    cross = (sig.m("crossposts") or 0.0) + (sig.m("reposts") or 0.0)
    total = shares + saves * 1.5 + dm * 2.0 + cross * 3.0
    if views and views > 0:
        return _cap100(100.0 * total / views), "rate-vs-views"
    if total > 0:
        # No reach denominator: log scale on raw propagation actions.
        return _cap100(10.0 * math.log10(1.0 + total)), "log-raw"
    return None, "no propagation inputs"


def conversation_score(sig: ContentSignal) -> Tuple[Optional[float], str]:
    """Replies/comments depth, weighted; author re-engagement is gold."""
    views = sig.m("views") or sig.m("followers")
    comments = sig.m("comments") or 0.0
    quotes = sig.m("quotes") or 0.0
    parts: List[float] = []
    if views and views > 0 and (comments or quotes):
        parts.append(_cap100(100.0 * (comments + quotes * 2.0) / views * 5.0))
    elif comments or quotes:
        parts.append(_cap100(10.0 * math.log10(1.0 + comments + quotes * 2.0)))
    if not parts:
        return None, "no conversation inputs"
    score = _mean(parts) or 0.0
    if (sig.m("author_replies") or 0) > 0:
        score = _cap100(score + 10.0)  # author in the replies: strong signal
    return _cap100(score), "comments+quotes"


def _shingles(text: str, k: int = 5) -> set:
    words = re.findall(r"[a-z0-9]+", text.lower())
    if len(words) < k:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + k]) for i in range(len(words) - k + 1)}


def originality_score(sig: ContentSignal, corpus: Sequence[str]) -> Tuple[float, str]:
    """Semantic uniqueness vs recent corpus (stdlib shingle Jaccard).

    100 = nothing like it seen. Identical text -> ~0. No corpus -> 60
    neutral, flagged. Format novelty adds up to +5.
    """
    mine = _shingles(sig.text)
    if not mine:
        return 50.0, "empty text"
    best = 0.0
    for other in corpus:
        theirs = _shingles(other)
        if not theirs:
            continue
        inter = len(mine & theirs)
        union = len(mine | theirs)
        if union:
            best = max(best, inter / union)
    score = 100.0 * (1.0 - best)
    basis = f"max-jaccard={best:.2f}"
    if not corpus:
        score, basis = 60.0, "no-corpus-neutral"
    return _cap100(score), basis


def velocity_multiplier(sig: ContentSignal, baseline_per_hour: float = 100.0) -> float:
    """Early velocity 0.8x-1.3x. First 30-90 min decide the test pools."""
    likes = sig.m("likes") or 0.0
    comments = sig.m("comments") or 0.0
    shares = sig.m("shares") or 0.0
    upvotes = sig.m("upvotes") or 0.0
    actions = likes + comments + shares + upvotes
    age = sig.age_hours()
    if age is None or actions <= 0:
        return 1.0  # unknown age/actions: neutral, not punished
    velocity = actions / max(age, 0.25)
    ratio = velocity / max(baseline_per_hour, 1e-9)
    return max(0.8, min(1.3, 0.8 + 0.5 * min(ratio, 1.0)))


@dataclass
class GradeResult:
    signal_id: str
    grade: float
    attention: Optional[float]
    propagation: Optional[float]
    conversation: Optional[float]
    originality: float
    velocity_mult: float
    coverage: float  # 0-1: fraction of the 4 components with real inputs
    basis: str
    hypothesis: bool = True  # always: grades are advisory, never earnings claims


def quality_grade(
    sig: ContentSignal,
    corpus: Sequence[str] = (),
    baseline_per_hour: float = 100.0,
) -> GradeResult:
    """The interpenetrated grade. Missing components reweight; never zero-fill."""
    att, att_b = attention_score(sig)
    prop, prop_b = propagation_score(sig)
    conv, conv_b = conversation_score(sig)
    orig, orig_b = originality_score(sig, corpus)

    parts: List[Tuple[float, float]] = []  # (weight, score)
    if att is not None:
        parts.append((W_ATTENTION, att))
    if prop is not None:
        parts.append((W_PROPAGATION, prop))
    if conv is not None:
        parts.append((W_CONVERSATION, conv))
    parts.append((W_ORIGINALITY, orig))  # originality always computable

    total_w = sum(w for w, _ in parts)
    base = sum(w * s for w, s in parts) / total_w if total_w else 0.0
    mult = velocity_multiplier(sig, baseline_per_hour)
    coverage = (len(parts) - 1) / 3.0  # originality excluded: always present
    basis = (
        f"att={att_b} prop={prop_b} conv={conv_b} orig={orig_b} "
        f"velx={mult:.2f} coverage={coverage:.2f}"
    )
    return GradeResult(
        signal_id=sig.id,
        grade=_cap100(base * mult),
        attention=att,
        propagation=prop,
        conversation=conv,
        originality=orig,
        velocity_mult=mult,
        coverage=coverage,
        basis=basis,
    )


def rank_signals(
    signals: Sequence[ContentSignal],
    corpus: Sequence[str] = (),
    baseline_per_hour: float = 100.0,
) -> List[Tuple[ContentSignal, GradeResult]]:
    """Grade everything; corpus defaults to the batch's own texts."""
    texts = list(corpus) or [s.text for s in signals]
    graded = [
        (s, quality_grade(s, [t for t in texts if t != s.text], baseline_per_hour))
        for s in signals
    ]
    graded.sort(key=lambda pair: pair[1].grade, reverse=True)
    return graded


# ---------------------------------------------------------------------------
# Pattern extraction — only from winners (>= GRADE_THRESHOLD)
# ---------------------------------------------------------------------------

_CTA_PATTERNS = (
    "comment",
    "share",
    "follow",
    "link in bio",
    "duet",
    "stitch",
    "tag a",
    "save this",
)


def _hook_of(text: str) -> str:
    first = re.split(r"[.!?\n]", text.strip(), maxsplit=1)[0].strip()
    return first[:140]


@dataclass
class WavePatterns:
    winners: int
    scanned: int
    top_hooks: List[Tuple[str, int]]  # (hook, count)
    top_sounds: List[Tuple[str, int]]
    top_hashtags: List[Tuple[str, int]]
    top_formats: List[Tuple[str, float]]  # (format, avg grade)
    cta_rate: float  # fraction of winners with a CTA
    question_rate: float  # fraction opening/using a question
    monetized_share: float  # fraction of winners flagged monetized
    gaps: List[str]  # underserved angles, plain language


def extract_patterns(
    graded: Sequence[Tuple[ContentSignal, GradeResult]],
    min_grade: float = GRADE_THRESHOLD,
) -> WavePatterns:
    winners = [(s, g) for s, g in graded if g.grade >= min_grade]
    scanned = len(graded)
    hooks: Counter = Counter()
    sounds: Counter = Counter()
    tags: Counter = Counter()
    fmt_grades: Dict[str, List[float]] = {}
    cta = q = mon = mon_known = 0
    for s, g in winners:
        hook = _hook_of(s.text)
        if hook:
            hooks[hook] += 1
        if s.sound:
            sounds[s.sound] += 1
        for t in s.hashtags:
            tags[t.lower().lstrip("#")] += 1
        fmt_grades.setdefault(s.format, []).append(g.grade)
        low = s.text.lower()
        if any(p in low for p in _CTA_PATTERNS):
            cta += 1
        if "?" in s.text[:280]:
            q += 1
        if s.author_monetized is not None:
            mon_known += 1
            if s.author_monetized:
                mon += 1

    top_formats = sorted(
        ((f, sum(v) / len(v)) for f, v in fmt_grades.items()),
        key=lambda x: x[1],
        reverse=True,
    )
    gaps: List[str] = []
    for f in FORMATS:
        if f not in fmt_grades:
            gaps.append(f"No winners in format '{f}' — open lane.")
    for f, avg in top_formats:
        if avg >= 85 and len(fmt_grades[f]) <= 2:
            gaps.append(
                f"Format '{f}' averages {avg:.0f} but only "
                f"{len(fmt_grades[f])} winner(s) — thin competition."
            )
    if not winners:
        gaps.append("No winners cleared the grade bar — lower it or scan more.")

    n = max(len(winners), 1)
    return WavePatterns(
        winners=len(winners),
        scanned=scanned,
        top_hooks=hooks.most_common(8),
        top_sounds=sounds.most_common(8),
        top_hashtags=tags.most_common(8),
        top_formats=top_formats,
        cta_rate=cta / n,
        question_rate=q / n,
        monetized_share=(mon / mon_known) if mon_known else 0.0,
        gaps=gaps,
    )


# ---------------------------------------------------------------------------
# Briefs — what the creating agent gets
# ---------------------------------------------------------------------------


@dataclass
class ContentBrief:
    niche: str
    created: str
    target_platforms: List[str]
    proven_patterns: List[str]
    originality_gaps: List[str]
    text_format: str
    video_format: str
    hook_library: List[str]  # proven hooks, REWRITTEN — never copy verbatim
    levers: List[str]
    risk_flags: List[str]
    hypothesis: bool = True
    engine: Optional[str] = None  # engine key, e.g. "facebook-elite-viral"


def generate_brief(
    niche: str,
    graded: Sequence[Tuple[ContentSignal, GradeResult]],
    patterns: WavePatterns,
    engine: Optional[str] = None,
) -> ContentBrief:
    """Build the creating agent's brief.

    engine: optional engine key (see list_engines()). The brief then runs
    through that engine's verbatim prompt spec on top of the proven
    patterns. Raises KeyError on unknown engine names.
    """
    if engine is not None:
        _engine_info(engine)  # validates; raises KeyError on unknown
    plats = sorted({s.platform for s, g in graded if g.grade >= GRADE_THRESHOLD})
    proven: List[str] = []
    for s, g in sorted(graded, key=lambda p: p[1].grade, reverse=True)[:5]:
        proven.append(
            f"[{s.platform}/{s.format}] grade={g.grade:.0f} "
            f"hook='{_hook_of(s.text)[:80]}' why={g.basis}"
        )
    levers = [
        f"CTA in {patterns.cta_rate:.0%} of winners — close with one, not two.",
        f"Question-driven in {patterns.question_rate:.0%} of winners.",
        "First 1-3 seconds decide video test pools; state the payoff up front.",
        "Shares/saves outweigh likes — build the save trigger (list, numbers).",
        "Reply to early comments yourself; author re-engagement lifts grade.",
    ]
    risks = [
        "REWRITE every hook — verbatim reuse trips originality filters.",
        "No watermarks from other apps on Reels/TikTok.",
        "Punch at systems/industries, never private individuals.",
        "Grades are hypotheses, not earnings promises. Nothing is guaranteed.",
    ]
    if engine is not None:
        risks.append(
            "The engine's >=8.9 quality gate is a self-scored target, not a "
            "measured outcome. It raises the bar; it proves nothing."
        )
    return ContentBrief(
        niche=niche,
        created=datetime.now(timezone.utc).isoformat(),
        target_platforms=plats or ["tiktok", "instagram"],
        proven_patterns=proven,
        originality_gaps=list(patterns.gaps),
        text_format=(
            "Hook line + 3-5 tight value lines + one question. "
            "3-track voice: take, aside, inner voice in parens."
        ),
        video_format=(
            "15-45s vertical 9:16. 0-3s: hook as spoken first line + burned-in "
            "caption. Middle: one contradiction, one aside. End: single CTA."
        ),
        hook_library=[h for h, _ in patterns.top_hooks],
        levers=levers,
        risk_flags=risks,
        engine=engine,
    )


def render_brief(b: ContentBrief) -> str:
    lines = [
        f"WAVE PULSE BRIEF — {b.niche}",
        f"created {b.created} (HYPOTHESIS — advisory, not an earnings claim)",
        "",
        f"TARGET: {', '.join(b.target_platforms)}",
        "",
        "PROVEN PATTERNS (rewrite the spirit, never the text):",
    ]
    lines += [f"  - {p}" for p in b.proven_patterns] or ["  (none yet)"]
    lines += ["", "ORIGINALITY GAPS:"]
    lines += [f"  - {g}" for g in b.originality_gaps] or ["  (none yet)"]
    if b.engine is not None:
        info = _engine_info(b.engine)
        lines += [
            "",
            f"ENGINE: {info['label']} ({b.engine})",
            f"Fusion: {info['platforms']} — {info['kind']}",
            "Run the brief through this engine's spec below. Its quality gates "
            "are self-scored targets, not measured outcomes.",
            "",
            _load_engine_prompt(b.engine).rstrip(),
        ]
    lines += [
        "",
        f"TEXT FORMAT: {b.text_format}",
        "",
        f"VIDEO FORMAT: {b.video_format}",
        "",
    ]
    lines += ["HOOK LIBRARY (rewrite, don't copy):"]
    lines += [f"  - {h}" for h in b.hook_library] or ["  (none yet)"]
    lines += ["", "LEVERS:"]
    lines += [f"  - {x}" for x in b.levers]
    lines += ["", "RISK FLAGS:"]
    lines += [f"  - {x}" for x in b.risk_flags]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def save_signals(signals: Sequence[ContentSignal], name: str) -> Path:
    path = _store_dir() / f"signals_{name}.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for s in signals:
            fh.write(json.dumps(s.to_dict(), ensure_ascii=False) + "\n")
    return path


def load_signals(name: str) -> List[ContentSignal]:
    path = _store_dir() / f"signals_{name}.jsonl"
    if not path.exists():
        return []
    return LocalFileAdapter(path).fetch(limit=10_000)


def save_brief(brief: ContentBrief, name: str) -> Path:
    path = _store_dir() / f"brief_{name}.json"
    payload = {
        "niche": brief.niche,
        "created": brief.created,
        "target_platforms": brief.target_platforms,
        "proven_patterns": brief.proven_patterns,
        "originality_gaps": brief.originality_gaps,
        "text_format": brief.text_format,
        "video_format": brief.video_format,
        "hook_library": brief.hook_library,
        "levers": brief.levers,
        "risk_flags": brief.risk_flags,
        "hypothesis": brief.hypothesis,
        "engine": brief.engine,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
