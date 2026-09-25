"""DemandPulse watcher — polls notification / email / text sources for unmet-need signals.

LAWS (law -> guard -> prove; Chauncey 2026-09-22):
  L1 POLL, NEVER STREAM.  The watcher only runs when invoked (cron tick or
     CLI). It keeps per-channel watermarks (last poll time + seen ids) and
     fetches only what arrived since the last poll. No persistent
     connections, no background listeners, no push subscriptions.
  L2 CANDIDATE UNMET NEEDS ONLY.  Extraction is a conservative,
     first-person-need heuristic (``extract_needs``). It is NOT semantic
     understanding and never claims to be. Marketing copy, receipts, and
     status updates without a need marker are ignored. Quality gates
     (2026-09-24): word-boundary marker matching, first-person gate for
     third-person prose, supply-side offer and template exclusions,
     substance check, HTML unescape.
  L3 EVERYTHING STAYS HYPOTHESIS.  All ingestion goes through
     ``DemandPulse.scan_seed``, which hardcodes ``kind="HYPOTHESIS"`` and
     confidence 0.35 for new signals. The watcher can never mint an
     OBSERVED/INFERENCE signal or raise confidence.
  L4 SOURCE LABELS PRESERVED.  Signals carry ``source`` =
     "notification" | "email" | "text" | "rss" | "hn" | "facebook" |
     "reddit" | "stackoverflow" | "github" | "arxiv" | "jobs" so Chauncey
     can see where each candidate came from. Feed-mined signals also
     carry ``origin`` (the source item's ref/link) and honest
     ``evidence`` (``observed:<source>``) so every signal traces back to
     the item it was mined from — no untraceable signals.
  L5 MINIMAL PII.  Only the extracted need-text (one sentence, truncated
     to 280 chars) is kept, and only inside the signal store. Full message
     bodies are read transiently and never persisted; the watcher state
     file holds ids + timestamps only, never bodies or snippets.
  L6 INBOUND ONLY.  The watcher never touches alerts: no alert creation,
     no alert evaluation, no cadence or quiet-hour changes. (This module
     must not import the alerts subsystem — there is a test that fails
     the build if it does.)
  L7 HONEST CHANNEL STATUS.  A channel with no usable transport reports
     ``not_configured`` and ingests nothing. The watcher never fabricates
     channel data. Gmail is gated on ``hatch_gws_cli gmail status``;
     facebook is gated on ``facebook-cli me``; device channels
     (text/notification) need the agent runtime's device tools, which a
     headless process cannot reach — from cron/CLI they report
     ``not_configured`` unless the caller injects fetched items via
     ``ingest_items``.
  L8 CYBRUS ALLIANCE (Chauncey 2026-09-22).  Threat/scam matches are NOT
     demand: they never become signals and never touch scoring. They are
     routed to Cybrus's tamper-evident audit log as HYPOTHESIS screening
     intel via ``levi.demand.cybrus_alliance.share_intel``. Watcher tick
     summaries are also recorded there. The watcher never enforces —
     blocking and screening decisions are Cybrus's.

Channel transports:
  email        -> ``hatch_gws_cli gmail`` subprocess (works headless).
                 Deepened 2026-09-22 (greatness build): triage max 50,
                 3-day lookback, per-tick body-read cap 15.
  text         -> device ``message.search`` (agent runtime only).
  notification -> device ``notifications.get`` (agent runtime only).
  rss          -> stdlib urllib RSS/Atom poll (greatness build "more eyes";
                 see levi.demand.eyes). Headless-safe, keyless, polite.
  hn           -> Hacker News via the keyless Algolia API (greatness build).
                 Headless-safe.
  facebook     -> ``facebook-cli feed newsfeed`` subprocess (headless-safe
                 shell CLI with a stored session; wired 2026-09-23 on
                 Chauncey's direct order). Auth failure -> not_configured.
  reddit/stackoverflow/github/arxiv/jobs -> keyless provider fetchers in
                 levi.demand.ingest, polled on the tick by eyes
                 ``poll_providers`` (2026-09-23, same order). Headless-safe.
"""

from __future__ import annotations

import html as _html
import json
import os
import re
import subprocess  # noqa: S404 - argv-list only, fixed binary (see _run_cli)
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from levi.demand import cybrus_alliance as _alliance
from levi.demand import eyes as _eyes

# ---------------------------------------------------------------------------
# Laws as importable constants (so tests can pin them, not just docstrings)


LAWS = (
    "L1 poll, never stream",
    "L2 candidate unmet needs only",
    "L3 everything stays HYPOTHESIS",
    "L4 source labels preserved",
    "L5 minimal PII",
    "L6 inbound only (never touches alerts)",
    "L7 honest channel status",
    "L8 cybrus alliance — threats routed as HYPOTHESIS intel, ticks audited",
)

CHANNELS = ("notification", "email", "text", "rss", "hn", "facebook")

# Keep only the need sentence; 280 chars is enough for a demand signal and
# bounds how much of someone's message can land in the store.
NEED_TEXT_MAX = 280

# Watcher state (watermarks) — ids + timestamps only, never bodies.
_STATE_SEEN_CAP = 500


def _home() -> Path:
    return Path(os.environ.get("LEVI_HOME") or os.path.expanduser("~/.levi"))


def state_path() -> Path:
    return _home() / "demand_watcher.json"


# ---------------------------------------------------------------------------
# CLI plumbing (argv lists only — never shell=True; tests monkeypatch _run_cli)


_CLI = "hatch_gws_cli"
_GATED_PREVIEW = "gated: needs Chauncey's Google sign-in"


def _run_cli(argv: List[str], timeout_s: float = 45.0) -> Tuple[int, str, str]:
    """Run the vendored CLI. Tests monkeypatch this — never real Google."""
    try:
        proc = subprocess.run(  # noqa: S603 - argv list, fixed binary
            argv, capture_output=True, text=True, timeout=timeout_s
        )
    except FileNotFoundError:
        return 127, "", f"CLI not found: {argv[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", "CLI timed out"
    return proc.returncode, proc.stdout, proc.stderr


def _rate_limited(payload: Any) -> bool:
    """True when the connector says to stop for this attempt (hard stop)."""
    if isinstance(payload, dict):
        if payload.get("kind") == "connector_rate_limited" and payload.get(
            "terminal_for_attempt"
        ):
            return True
        return any(_rate_limited(v) for v in payload.values())
    if isinstance(payload, list):
        return any(_rate_limited(v) for v in payload)
    return False


# ---------------------------------------------------------------------------
# Email source (Gmail, via hatch_gws_cli)


def gmail_status() -> Dict[str, Any]:
    """Auth gate: connected / not_connected / unavailable. Never fakes."""
    rc, out, err = _run_cli([_CLI, "gmail", "status"])
    if rc != 0:
        return {"ok": False, "status": "unavailable", "detail": (err or out)[:200]}
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return {"ok": False, "status": "unavailable", "detail": "unparseable status"}
    st = str(data.get("status", "unknown"))
    return {"ok": True, "status": st}


def gmail_triage(max_n: int = 50, days: int = 3) -> Dict[str, Any]:
    """Recent metadata (sender/subject/date) — no bodies fetched here.

    Deepened 2026-09-22 (greatness build): up to 50 candidates, 3-day
    lookback. Both bounds are parameters so tests stay hermetic.
    """
    rc, out, err = _run_cli(
        [_CLI, "gmail", "+triage", "--query", f"newer_than:{days}d",
         "--max", str(max_n), "--format", "json"]
    )
    if rc != 0:
        return {"ok": False, "detail": (err or out)[:200]}
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return {"ok": False, "detail": "unparseable triage"}
    if _rate_limited(data):
        return {"ok": False, "rate_limited": True, "detail": "connector rate limit"}
    msgs = data.get("messages") or []
    return {"ok": True, "messages": msgs}


def gmail_read(message_id: str) -> Dict[str, Any]:
    """Read one message (transient — body is never persisted by the watcher)."""
    rc, out, err = _run_cli(
        [_CLI, "gmail", "+read", "--id", message_id, "--headers", "--format", "json"]
    )
    if rc != 0:
        return {"ok": False, "detail": (err or out)[:200]}
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return {"ok": False, "detail": "unparseable message"}
    if _rate_limited(data):
        return {"ok": False, "rate_limited": True, "detail": "connector rate limit"}
    return {"ok": True, "message": data}


def _gmail_body_text(message: Dict[str, Any]) -> str:
    """Best-effort plain text out of a +read payload. Transient only."""
    for key in ("body", "snippet", "text"):
        val = message.get(key)
        if isinstance(val, str) and val.strip():
            return val
    # Raw RFC822-ish fallback
    raw = message.get("raw")
    if isinstance(raw, str):
        return raw
    parts = message.get("parts") or message.get("payload", {}).get("parts") or []
    chunks = []
    for part in parts:
        body = part.get("body", {}).get("data") if isinstance(part, dict) else None
        if body:
            chunks.append(str(body)[:2000])
    return "\n".join(chunks)


# ---------------------------------------------------------------------------
# Need extraction — conservative heuristic, explicitly not semantic


# First-person / direct unmet-need markers. A sentence must contain one of
# these to become a candidate. Deliberately narrow: false negatives are
# cheaper than inventing demand Chauncey never saw.
#
# Quality build 2026-09-24 (diagnosis on 100 live signals: ~1/3 junk):
# matching is WORD-BOUNDARY now — the old substring check let "broken"
# fire inside "housebroken" and "i want" inside "wanted".
_NEED_MARKERS = (
    "i need",
    "i want",
    "i wish",
    "i'm looking for",
    "i am looking for",
    "looking for",
    "can't find",
    "cannot find",
    "struggling with",
    "struggle with",
    "problem with",
    "problems with",
    "frustrated",
    "frustrat",
    "wish there was",
    "wish i had",
    "does anyone know",
    "any recommendations",
    "anyone recommend",
    "help me find",
    "need help",
    "hate dealing with",
    "tired of",
    "broken",
    "doesn't work",
    "does not work",
    "stopped working",
    # Gated markers (require first-person): genuine need language that
    # also shows up in third-person prose ("pain points in the market",
    # "desperate times"). Added 2026-09-24 after "I am desperate for a
    # mattress that helps with pain" fired nothing.
    "desperate",
    "in pain",
    "pain",
    "help with",
)

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def _marker_re(marker: str) -> "re.Pattern[str]":
    return re.compile(r"\b" + re.escape(marker) + r"\b", re.IGNORECASE)


# Markers that already carry first-person / direct-address force. They need
# no further gate: the speaker is the one with the need.
_UNGATED_MARKERS = frozenset(
    {
        "i need",
        "i want",
        "i wish",
        "i'm looking for",
        "i am looking for",
        "wish i had",
        "does anyone know",
        "any recommendations",
        "anyone recommend",
        "help me find",
        "need help",
    }
)

# The rest can fire in third-person prose ("Locals reportedly frustrated
# with Waymo", "Researchers looking for mRNA were ridiculed"). Those are
# news about other people, not expressed needs — they require a
# first-person token in the same sentence or they are dropped.
_FIRST_PERSON_RE = re.compile(
    r"\b(i|me|my|mine|we|us|our|ours|myself|ourselves|"
    r"i'm|i've|i'd|i'll|we're|we've)\b",
    re.IGNORECASE,
)

# Supply-side and template patterns: never demand, however the markers read.
# ("What I can build for you ... I want to solve your bottleneck" is someone
# selling, not someone needing. "[business] / [industry]" is a template.)
_EXCLUDE_RES = (
    re.compile(
        r"\b(i can build|hire me|my services|for hire|what i can build|"
        r"let me build|my rate is|book a call)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\[[^\]\n]{1,40}\]"),
)

# A need sentence must say SOMETHING beyond the marker itself.
# ("Happy for any recommendations!" names no object — content-free.)
# After stripping the fired markers, >= this many alpha tokens of len >= 3.
_SUBSTANCE_MIN_TOKENS = 3
_SUBSTANCE_TOKEN_RE = re.compile(r"[a-z]{3,}")
# Stopwords ignored by the substance check: a sentence that carries
# nothing beyond markers + stopwords (e.g. "Happy for any
# recommendations!") is content-free and stays out. Kept small and
# local — this is a quality gate, not a language model.
_SUBSTANCE_STOPWORDS = frozenset(
    "the a an and or but for nor of to in on at by with from as is are was "
    "were be been it its this that these those they them their you your he "
    "she his her we our us i me my any all some more most other such only "
    "own same so if then than too very just can could would should will do "
    "does did have has had not no yes how what when where why which who am "
    "are im ive dont doesnt wanna gonna like get got go going come make "
    "take please thanks thank hi hey hello here there into out over under "
    "again once about up down".split()
)


def _fired_markers(sentence: str) -> List[str]:
    return [m for m in _NEED_MARKERS if _marker_re(m).search(sentence)]


def candidate_count(text: str) -> int:
    """Sentences with any need marker (pre-filter) — the denominator for
    per-channel extraction yield. Deterministic."""
    if not text:
        return 0
    n = 0
    for sent in _SENT_SPLIT.split(_html.unescape(text)):
        s = " ".join(sent.split())
        if len(s) >= 12 and _fired_markers(s):
            n += 1
    return n


def _has_substance(sentence: str, fired: List[str]) -> bool:
    """The sentence must carry 3+ meaningful tokens.

    Markers are NOT stripped first: stripping gutted genuine sentences
    ("I am desperate for a mattress that helps with pain" loses
    desperate/pain/helps and keeps only "mattress"). With a threshold of
    3 + stopword filtering, marker-only sentences ("Happy for any
    recommendations!", "I need help", "Looking for recommendations")
    still fail — they simply don't carry enough content.
    """
    tokens = _SUBSTANCE_TOKEN_RE.findall(sentence.lower())
    meaningful = [t for t in tokens if t not in _SUBSTANCE_STOPWORDS]
    return len(meaningful) >= _SUBSTANCE_MIN_TOKENS


def extract_needs(text: str) -> List[str]:
    """Pull candidate unmet-need sentences out of free text.

    Returns the need sentences only (truncated to NEED_TEXT_MAX), never the
    full body. Empty list when nothing matches — silence, not invention.

    Quality gates (2026-09-24, from a 100-signal diagnosis):
    - HTML entities are unescaped first (``don&#39;t`` -> ``don't``).
    - Marker matching is word-boundary (``broken`` no longer fires inside
      ``housebroken``; ``i want`` no longer fires inside ``wanted``).
    - Third-person prose is dropped: markers that can fire without a
      first-person subject (``frustrated``, ``looking for``, ``broken``,
      ...) require a first-person token in the sentence. News headlines
      about other people are not needs.
    - Supply-side offers (``hire me``, ``i can build``) and template
      placeholders (``[business]``) are never demand.
    - The sentence must carry 3+ meaningful tokens beyond stopwords
      (substance check) — ``Happy for any recommendations!`` is a
      content-free request and stays out, while genuine thin needs
      (``I need help scheduling shifts``) still pass.
    Deterministic: same text in, same list out.
    """
    if not text:
        return []
    found: List[str] = []
    for sent in _SENT_SPLIT.split(_html.unescape(text)):
        s = " ".join(sent.split())
        if len(s) < 12:
            continue
        if any(rx.search(s) for rx in _EXCLUDE_RES):
            continue
        fired = _fired_markers(s)
        if not fired:
            continue
        # Drop quoted forwards / headers that slipped in.
        if s.lower().startswith((">", "on ", "from:", "sent:", "subject:")):
            continue
        # First-person gate for markers that fire in third-person prose.
        if not all(m in _UNGATED_MARKERS for m in fired):
            if not _FIRST_PERSON_RE.search(s):
                continue
        if not _has_substance(s, fired):
            continue
        found.append(s[:NEED_TEXT_MAX])
        if len(found) >= 3:
            break
    return found


# ---------------------------------------------------------------------------
# Watcher state (watermarks)


@dataclass
class WatcherState:
    path: Path = field(default_factory=state_path)
    channels: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "WatcherState":
        p = path or state_path()
        st = cls(path=p)
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    st.channels = data.get("channels", {})
            except (json.JSONDecodeError, OSError):
                st.channels = {}
        for ch in CHANNELS:
            st.channels.setdefault(ch, {"last_poll": None, "seen_ids": []})
        return st

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"channels": self.channels, "updated_at": _now_iso()}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def mark_seen(self, channel: str, item_id: str) -> bool:
        """Record an id; return False if it was already seen (skip re-ingest)."""
        seen = self.channels[channel].setdefault("seen_ids", [])
        if item_id in seen:
            return False
        seen.append(item_id)
        del seen[: max(0, len(seen) - _STATE_SEEN_CAP)]
        return True

    def touch(self, channel: str) -> None:
        self.channels[channel]["last_poll"] = _now_iso()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Ingest path — everything funnels through DemandPulse.scan_seed


def _bump_quality(state: WatcherState, channel: str,
                  candidates: int, kept: int) -> None:
    """Track per-channel extraction yield: marker-hit sentences vs sentences
    that survived the quality gates. The ratio is the channel's observed
    reliability (see DemandPulse.channel_reliability). Counters only."""
    q = (
        state.channels.setdefault(channel, {"last_poll": None, "seen_ids": []})
        .setdefault("quality", {"candidates": 0, "kept": 0})
    )
    q["candidates"] = int(q.get("candidates", 0)) + max(0, candidates)
    q["kept"] = int(q.get("kept", 0)) + max(0, kept)


def ingest_items(
    dp,
    state: WatcherState,
    channel: str,
    items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Ingest pre-fetched device items: [{id, text, ts?}] -> signals.

    Used by the agent-runtime cron worker for the text/notification
    channels (device.invoke results mapped into this shape). Each item's
    text is mined for need sentences; only those become signals, via
    scan_seed (HYPOTHESIS, dedup, confidence 0.35 — L2/L3/L4).
    """
    if channel not in CHANNELS:
        raise ValueError(f"unknown channel {channel!r}")
    receipt = {
        "channel": channel,
        "items": len(items),
        "skipped_seen": 0,
        "candidates": 0,
        "signals": 0,
        "signal_ids": [],
    }
    intel_items: List[Dict[str, Any]] = []
    for item in items:
        iid = str(item.get("id") or "")
        if not iid or not state.mark_seen(channel, iid):
            receipt["skipped_seen"] += 1
            continue
        text = str(item.get("text") or "")
        needs = extract_needs(text)
        _bump_quality(state, channel, candidate_count(text), len(needs))
        for need in needs:
            receipt["candidates"] += 1
            sig = dp.scan_seed(
                need, segment="general", source=channel,
                origin={"ref": iid},
            )
            receipt["signals"] += 1
            if sig.id not in receipt["signal_ids"]:
                receipt["signal_ids"].append(sig.id)
        # L8: threats are not demand — route to Cybrus as screening intel.
        if _alliance.extract_threats(text):
            intel_items.append(
                {"id": iid, "text": text, "channel": channel}
            )
    if intel_items:
        receipt["threat_intel"] = _alliance.share_intel(intel_items)
    state.touch(channel)
    return receipt


# Per-tick body-read cap: the triage list can be 50 deep, but a tick
# spends at most this many body reads (E4 bounded work / politeness).
_EMAIL_READ_CAP = 15


def poll_email(dp, state: WatcherState, max_n: int = 50) -> Dict[str, Any]:
    """Poll Gmail for candidate need signals. Headless-safe.

    Deepened 2026-09-22 (greatness build): ``max_n`` defaults to 50
    with a 3-day lookback, but at most ``_EMAIL_READ_CAP`` bodies are
    read per tick — the rest wait for the next tick.
    """
    gate = gmail_status()
    if not gate.get("ok"):
        return {"channel": "email", "status": "not_configured",
                "detail": gate.get("detail", "gmail unavailable")}
    if gate.get("status") != "connected":
        return {"channel": "email", "status": "not_configured",
                "detail": "gmail not connected"}
    tri = gmail_triage(max_n=max_n)
    if not tri.get("ok"):
        if tri.get("rate_limited"):
            return {"channel": "email", "status": "rate_limited",
                    "detail": tri["detail"]}
        return {"channel": "email", "status": "error", "detail": tri["detail"]}
    receipt = {
        "channel": "email",
        "status": "ok",
        "messages": len(tri["messages"]),
        "skipped_seen": 0,
        "read": 0,
        "read_capped": 0,
        "candidates": 0,
        "signals": 0,
        "signal_ids": [],
    }
    intel_items: List[Dict[str, Any]] = []
    for msg in tri["messages"]:
        mid = str(msg.get("id") or "")
        if not mid:
            receipt["skipped_seen"] += 1
            continue
        if mid in state.channels["email"].get("seen_ids", []):
            receipt["skipped_seen"] += 1
            continue
        # Cheap metadata pre-filter before spending a body read.
        hay = f"{msg.get('subject', '')} {msg.get('from', '')}".lower()
        needs_read = True
        if not any(m in hay for m in _NEED_MARKERS):
            # Subject shows nothing; peek at the body only for personal
            # (non-noreply) senders to bound API cost.
            frm = str(msg.get("from", "")).lower()
            if "noreply" in frm or "no-reply" in frm or "donotreply" in frm:
                needs_read = False
        if not needs_read:
            state.mark_seen("email", mid)  # consumed: no read spent
            continue
        if receipt["read"] >= _EMAIL_READ_CAP:
            # NOT marked seen — the next tick picks this message up.
            receipt["read_capped"] += 1
            continue
        state.mark_seen("email", mid)
        got = gmail_read(mid)
        if not got.get("ok"):
            if got.get("rate_limited"):
                receipt["status"] = "rate_limited"
                break
            continue
        receipt["read"] += 1
        body = _gmail_body_text(got["message"])
        # Body is transient: mined for need sentences, then dropped.
        full_text = f"{msg.get('subject', '')}. {body}"
        needs = extract_needs(full_text)
        _bump_quality(state, "email", candidate_count(full_text), len(needs))
        for need in needs:
            receipt["candidates"] += 1
            sig = dp.scan_seed(
                need, segment="general", source="email",
                origin={"ref": mid},
            )
            receipt["signals"] += 1
            if sig.id not in receipt["signal_ids"]:
                receipt["signal_ids"].append(sig.id)
        # L8: threats are not demand — route to Cybrus as screening intel.
        if _alliance.extract_threats(full_text):
            intel_items.append(
                {"id": mid, "text": full_text, "channel": "email"}
            )
    if intel_items:
        receipt["threat_intel"] = _alliance.share_intel(intel_items)
    state.touch("email")
    return receipt


# ---------------------------------------------------------------------------
# Facebook source (facebook-cli, headless-safe shell CLI)


_FB_CLI = "facebook-cli"


def _run_facebook_cli(argv: List[str],
                      timeout_s: float = 45.0) -> Tuple[int, str, str]:
    """Run facebook-cli (argv list only — never shell=True).

    Tests monkeypatch this — never the real session. Separate runner from
    ``_run_cli`` so the gmail CLI test sequences are not disturbed.
    """
    try:
        proc = subprocess.run(  # noqa: S603 - argv list, fixed binary
            argv, capture_output=True, text=True, timeout=timeout_s
        )
    except FileNotFoundError:
        return 127, "", f"CLI not found: {argv[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", "CLI timed out"
    return proc.returncode, proc.stdout, proc.stderr


def facebook_status() -> Dict[str, Any]:
    """Auth gate: light ``facebook-cli me`` probe. Never fakes (L7)."""
    rc, out, err = _run_facebook_cli([_FB_CLI, "me"])
    if rc != 0:
        return {"ok": False, "status": "unavailable",
                "detail": (err or out)[:200]}
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return {"ok": False, "status": "unavailable",
                "detail": "unparseable me"}
    name = data.get("name") if isinstance(data, dict) else None
    if name:
        return {"ok": True, "status": "connected", "name": str(name)}
    return {"ok": False, "status": "not_connected",
            "detail": "no facebook session"}


def poll_facebook(dp, state: WatcherState, limit: int = 25,
                  deadline: Optional[float] = None) -> Dict[str, Any]:
    """Poll the authenticated Facebook newsfeed for need candidates.

    Headless-safe: facebook-cli is a shell CLI with a stored session
    (verified 2026-09-23). Auth/CLI failure -> ``not_configured`` and
    zero ingestion (L7). Captions are mined for need sentences only;
    full captions are never persisted (L5).
    """
    import time as _time

    if deadline is not None and _time.time() >= deadline:
        return {"channel": "facebook", "status": "budget_exceeded", "posts": 0}
    rc, out, err = _run_facebook_cli(
        [_FB_CLI, "feed", "newsfeed", "--limit", str(limit)]
    )
    if rc != 0:
        return {"channel": "facebook", "status": "not_configured",
                "detail": (err or out or "facebook-cli unavailable")[:200]}
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return {"channel": "facebook", "status": "not_configured",
                "detail": "unparseable facebook feed"}
    if isinstance(data, dict) and data.get("error"):
        return {"channel": "facebook", "status": "not_configured",
                "detail": str(data.get("error"))[:200]}
    posts = data.get("posts") if isinstance(data, dict) else None
    if not isinstance(posts, list):
        return {"channel": "facebook", "status": "not_configured",
                "detail": "no posts in facebook feed payload"}
    receipt = {
        "channel": "facebook", "status": "ok", "posts": len(posts),
        "skipped_seen": 0, "candidates": 0, "signals": 0, "signal_ids": [],
    }
    intel_items: List[Dict[str, Any]] = []
    for post in posts:
        if not isinstance(post, dict):
            continue
        pid = str(post.get("post_id") or post.get("id") or "")
        if not pid or not state.mark_seen("facebook", pid):
            receipt["skipped_seen"] += 1
            continue
        caption = post.get("post_caption") or post.get("text") or ""
        text = str(caption)
        needs = extract_needs(text)
        _bump_quality(state, "facebook", candidate_count(text), len(needs))
        for need in needs:
            receipt["candidates"] += 1
            sig = dp.scan_seed(
                need, segment="general", source="facebook",
                origin={"ref": pid},
            )
            receipt["signals"] += 1
            if sig.id not in receipt["signal_ids"]:
                receipt["signal_ids"].append(sig.id)
        # L8: threats are not demand — route to Cybrus as screening intel.
        if text and _alliance.extract_threats(text):
            intel_items.append({"id": pid, "text": text, "channel": "facebook"})
    if intel_items:
        receipt["threat_intel"] = _alliance.share_intel(intel_items)
    state.touch("facebook")
    return receipt


# ---------------------------------------------------------------------------
# Headless run: email only; device channels honestly report not_configured


def device_channel_status() -> Dict[str, str]:
    """Headless processes cannot reach device.invoke -> not_configured.

    The agent-runtime cron worker injects device payloads via ingest_items;
    a bare ``watcher run`` must not pretend it polled them.
    """
    return {"text": "not_configured", "notification": "not_configured"}


def run(
    dp=None,
    state: Optional[WatcherState] = None,
    max_n: int = 50,
    budget_s: float = _eyes.TICK_BUDGET_S,
) -> Dict[str, Any]:
    """One poll tick: email + server-side eyes headless; device channels
    need injected items. The tick budget is shared across channels (E4):
    eyes stop when the deadline hits and report ``budget_exceeded``.
    """
    import time as _time

    from levi.demand.pulse import DemandPulse

    dp = dp or DemandPulse()
    state = state or WatcherState.load()
    deadline = _time.time() + budget_s
    channels: Dict[str, Any] = {}
    channels["email"] = poll_email(dp, state, max_n=max_n)
    channels["facebook"] = poll_facebook(dp, state, deadline=deadline)
    channels["rss"] = _eyes.poll_rss(dp, state, deadline=deadline)
    channels["hn"] = _eyes.poll_hn(dp, state, deadline=deadline)
    providers = _eyes.poll_providers(dp, state, deadline=deadline)["channels"]
    channels.update(providers)
    dev = device_channel_status()
    channels["text"] = {
        "channel": "text",
        "status": dev["text"],
        "detail": "device SMS needs the agent runtime (device.invoke message.search); "
                  "feed items via: levi.demand watcher ingest --channel text",
    }
    channels["notification"] = {
        "channel": "notification",
        "status": dev["notification"],
        "detail": "device notifications need the agent runtime (device.invoke "
                  "notifications.get); feed items via: levi.demand watcher ingest "
                  "--channel notification",
    }
    # L8: the tick itself is recorded in Cybrus's audit log (best-effort).
    # The payload shape is additive only: existing keys keep their shape.
    _alliance.audit_mutation(
        "demandpulse.watcher_tick",
        {
            "email": {
                "status": channels["email"].get("status"),
                "signals": channels["email"].get("signals", 0),
                "threats_shared": channels["email"]
                .get("threat_intel", {})
                .get("shared", 0),
            },
            "facebook": {
                "status": channels["facebook"].get("status"),
                "signals": channels["facebook"].get("signals", 0),
                "threats_shared": channels["facebook"]
                .get("threat_intel", {})
                .get("shared", 0),
            },
            "rss": {
                "status": channels["rss"].get("status"),
                "signals": channels["rss"].get("signals", 0),
            },
            "hn": {
                "status": channels["hn"].get("status"),
                "signals": channels["hn"].get("signals", 0),
            },
            "providers": {
                ch: {
                    "status": r.get("status"),
                    "signals": r.get("signals", 0),
                }
                for ch, r in providers.items()
            },
            "text": {"status": channels["text"].get("status")},
            "notification": {"status": channels["notification"].get("status")},
        },
    )
    state.save()
    return {"at": _now_iso(), "channels": channels}


def status(dp=None, state: Optional[WatcherState] = None) -> Dict[str, Any]:
    """Channel health + watermarks. Read-only."""
    state = state or WatcherState.load()
    gate = gmail_status()
    email_state = state.channels["email"]
    fb = facebook_status()
    out = {
        "email": {
            "transport": "hatch_gws_cli gmail",
            "status": "connected"
            if (gate.get("ok") and gate.get("status") == "connected")
            else "not_configured",
            "last_poll": email_state.get("last_poll"),
            "seen": len(email_state.get("seen_ids", [])),
        },
        "facebook": {
            "transport": "facebook-cli feed newsfeed (shell CLI, stored session)",
            "status": "connected"
            if (fb.get("ok") and fb.get("status") == "connected")
            else "not_configured",
            "as": fb.get("name"),
            "last_poll": state.channels["facebook"].get("last_poll"),
            "seen": len(state.channels["facebook"].get("seen_ids", [])),
        },
        "text": {
            "transport": "device.invoke message.search (agent runtime only)",
            "status": device_channel_status()["text"],
            "last_poll": state.channels["text"].get("last_poll"),
            "seen": len(state.channels["text"].get("seen_ids", [])),
        },
        "notification": {
            "transport": "device.invoke notifications.get (agent runtime only)",
            "status": device_channel_status()["notification"],
            "last_poll": state.channels["notification"].get("last_poll"),
            "seen": len(state.channels["notification"].get("seen_ids", [])),
        },
        "rss": {
            "transport": "stdlib urllib RSS/Atom (keyless public reads)",
            "status": "ok",
            "last_poll": state.channels["rss"].get("last_poll"),
            "seen": len(state.channels["rss"].get("seen_ids", [])),
        },
        "hn": {
            "transport": "Hacker News Algolia API (keyless public reads)",
            "status": "ok",
            "last_poll": state.channels["hn"].get("last_poll"),
            "seen": len(state.channels["hn"].get("seen_ids", [])),
        },
    }
    return out
