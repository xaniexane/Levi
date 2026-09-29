"""DemandPulse eyes — server-side sensing (greatness build, 2026-09-22).

"More eyes / deeper pulls": RSS/Atom feeds and Hacker News polled
headless on the server, mined for candidate unmet-need sentences with
the watcher's conservative heuristic, ingested as HYPOTHESIS via
``DemandPulse.scan_seed``. No device needed — this is the half of
sensing that works from cron.

LAWS (law -> guard -> prove; Chauncey 2026-09-22):
  E1 POLITE KEYLESS READS ONLY. Bounded timeouts, an honest
     User-Agent, per-source cooldowns. Any failure — DNS, 429,
     timeout, bad payload — degrades to an empty list. No fetcher
     ever lets an exception escape; a dead source contributes nothing.
  E2 PUBLIC CHATTER IS NOT DEMAND. Everything ingested is HYPOTHESIS
     (scan_seed hardcodes kind + confidence 0.35). Source labels
     "rss" / "hn" are preserved so Chauncey can see where each
     candidate came from. No claim about real market demand, ever.
  E3 NEVER STREAMS. One bounded poll per tick; no persistent
     connections, no subscriptions, no background listeners.
  E4 BOUNDED WORK. Per-tick caps on feeds, items, and seconds; a
     tick budget (default 240s) is honored across channels.
  E5 STDLIB ONLY. urllib + xml.etree — no new dependencies, consistent
     with the LEVI kernel.

Honest limits (also in the docstrings where they bite):
  - RSS/HN/providers are public chatter, N=whoever-posted — not a market sample.
  - The keyless fetchers in ``levi.demand.ingest`` (reddit / stackoverflow /
    github / arxiv / jobs) were studio-pipeline tools; since 2026-09-23
    (Chauncey's direct order) they also poll on the ambient tick via
    ``poll_providers`` with fixed, documented ambient queries.
  - Feed list: HN front-page RSS first, then demand-shaped subreddits,
    by default; Chauncey adds feeds via the DP_EYES_FEEDS env var
    (comma-separated URLs) or the ``feeds`` argument. Nothing is scraped
    that requires auth.
  - Reddit rate-limits aggressively from datacenters — a 429 is just an
    empty contribution, never an error that breaks the tick.

Standing limits honored: nothing here publishes, spends, contacts
anyone, touches alerts, or changes quiet hours.
"""

from __future__ import annotations

import html as _html
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Laws as importable constants (so tests can pin them, not just docstrings)

LAWS = (
    "E1 polite keyless reads only (failures -> empty)",
    "E2 public chatter is not demand (HYPOTHESIS only)",
    "E3 never streams (one bounded poll per tick)",
    "E4 bounded work (per-tick caps + tick budget)",
    "E5 stdlib only",
)

EYE_CHANNELS = ("rss", "hn", "reddit", "stackoverflow", "github", "arxiv", "jobs")

_USER_AGENT = "levi-demandpulse/1.0 (+local-first demand research; stdlib urllib)"

# Per-tick bounds (E4)
MAX_FEEDS_PER_TICK = 10
MAX_ITEMS_PER_FEED = 25
FETCH_TIMEOUT_S = 15.0
SOURCE_COOLDOWN_S = 1800.0  # 30 min between fetches of the same source
TICK_BUDGET_S = 240.0
MAX_BODY_BYTES = 1_000_000  # 1MB cap on any single fetch

# HN Algolia ambient queries: "ask"-shaped demand language. Fixed and
# documented — the tick does not invent queries.
HN_AMBIENT_QUERIES = ("i need", "looking for", "frustrated with")
HN_HITS_PER_QUERY = 10

# Ambient provider queries — fixed and documented, the tick invents none
# (E4). Demand-shaped per source: first-person need language on
# reddit/github, tool-seeking question shapes on Stack Overflow, minimal
# on arXiv, and hiring-role queries on the job boards (hiring surges =
# employer demand).
REDDIT_AMBIENT_QUERIES = ("i need", "looking for", "wish there was")
SO_AMBIENT_QUERIES = ("is there a", "alternative to", "how do i")
GITHUB_AMBIENT_QUERIES = ("i need", "looking for")
ARXIV_AMBIENT_QUERIES = ("demand",)
JOB_AMBIENT_QUERIES = ("customer support", "virtual assistant")
PROVIDER_HITS_PER_QUERY = 10

# (channel, ingest-fetcher name, queries). Order is poll order.
_PROVIDER_SPECS: Tuple[Tuple[str, str, Tuple[str, ...]], ...] = (
    ("reddit", "fetch_reddit_signals", REDDIT_AMBIENT_QUERIES),
    ("stackoverflow", "fetch_stackoverflow_signals", SO_AMBIENT_QUERIES),
    ("github", "fetch_github_signals", GITHUB_AMBIENT_QUERIES),
    ("arxiv", "fetch_arxiv_signals", ARXIV_AMBIENT_QUERIES),
    ("jobs", "fetch_job_signals", JOB_AMBIENT_QUERIES),
)

DEFAULT_FEEDS: Tuple[str, ...] = (
    "https://news.ycombinator.com/rss",
    "https://www.reddit.com/r/SomebodyMakeThis/.rss",
    "https://www.reddit.com/r/BusinessIdeas/.rss",
    "https://www.reddit.com/r/startups/.rss",
    "https://www.reddit.com/r/smallbusiness/.rss",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def feed_list(extra: Optional[List[str]] = None) -> List[str]:
    """Effective RSS/Atom feed list: defaults + DP_EYES_FEEDS + ``extra``.

    DP_EYES_FEEDS is a comma-separated env var Chauncey controls.
    Duplicates and empties are dropped; order is stable.
    """
    feeds: List[str] = list(DEFAULT_FEEDS)
    env = os.environ.get("DP_EYES_FEEDS", "")
    feeds.extend(u.strip() for u in env.split(",") if u.strip())
    feeds.extend(u.strip() for u in (extra or []) if u and u.strip())
    seen = set()
    out = []
    for f in feeds:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


# ---------------------------------------------------------------------------
# Polite fetch (E1)


def _http_get(url: str, timeout: float = FETCH_TIMEOUT_S
              ) -> Tuple[Optional[int], bytes]:
    """GET ``url``; return ``(status, body)``. Never raises.

    Any failure — DNS, refused, timeout, HTTP error, over the body cap —
    returns ``(None, b"")``. A 429 is also just "source busy": empty.
    """
    if not url.startswith(("http://", "https://")):
        return None, b""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = int(resp.status)
            if status == 429:
                return None, b""
            chunks = []
            remaining = MAX_BODY_BYTES
            while remaining > 0:
                chunk = resp.read(min(65536, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            return status, b"".join(chunks)
    except Exception:
        return None, b""


_TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(text: str) -> str:
    """Strip HTML tags, unescape entities, collapse whitespace, bound length.

    Entities (``don&#39;t``) are unescaped so stored need text is readable
    and dedup compares real words, not entity soup.
    """
    s = _TAG_RE.sub(" ", text or "")
    s = _html.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:2000]


def parse_feed(body: bytes) -> List[Dict[str, str]]:
    """Parse RSS or Atom bytes -> [{title, link, summary}]. Never raises.

    Returns [] on any malformed input. Titles/summaries are cleaned
    (HTML stripped) but otherwise verbatim — never invented.
    """
    try:
        text = body.decode("utf-8", errors="replace")
        root = ET.fromstring(text)
    except Exception:
        return []
    items: List[Dict[str, str]] = []
    tag = root.tag.lower()

    def _txt(el) -> str:
        return (el.text or "").strip() if el is not None else ""

    if tag.endswith("rss") or root.find("channel") is not None:
        # RSS 2.0
        for item in root.iter("item"):
            title = _clean_text(_txt(item.find("title")))
            if not title:
                continue
            link = _txt(item.find("link"))
            summary = _clean_text(_txt(item.find("description")))
            items.append({"title": title, "link": link, "summary": summary})
            if len(items) >= MAX_ITEMS_PER_FEED:
                break
    elif tag.endswith("feed"):
        # Atom — strip namespace by suffix matching
        for entry in root.iter():
            if not entry.tag.lower().endswith("entry"):
                continue
            title = ""
            link = ""
            summary = ""
            for child in entry:
                ctag = child.tag.lower()
                if ctag.endswith("title"):
                    title = _clean_text(child.text or "")
                elif ctag.endswith("link") and not link:
                    link = (child.attrib.get("href") or "").strip()
                elif ctag.endswith(("summary", "content")) and not summary:
                    summary = _clean_text(child.text or "")
            if title:
                items.append({"title": title, "link": link, "summary": summary})
            if len(items) >= MAX_ITEMS_PER_FEED:
                break
    return items


# ---------------------------------------------------------------------------
# Cooldowns (E1/E4) — kept in the watcher state file, ids+timestamps only


def _cooldown_ok(state, channel: str, source: str,
                 now: Optional[float] = None) -> bool:
    now = time.time() if now is None else now
    cd = (state.channels.get(channel, {}).get("cooldowns") or {}).get(source, 0)
    return now >= float(cd or 0)


def _stamp_cooldown(state, channel: str, source: str,
                    now: Optional[float] = None) -> None:
    now = time.time() if now is None else now
    ch = state.channels.setdefault(channel, {})
    cds = ch.setdefault("cooldowns", {})
    cds[source] = now + SOURCE_COOLDOWN_S


# ---------------------------------------------------------------------------
# Polls — mine with the watcher's heuristic, ingest via scan_seed (E2)


def _mine(dp, state, channel: str,
          items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Mine candidate need sentences -> HYPOTHESIS signals (E2).

    ``items`` are ``{"text": str, "origin": {...}|None}`` — the origin
    (source-item link/ref) rides into ``scan_seed`` so every signal
    traces back to the item it was mined from. Per-channel extraction
    yield is recorded on the watcher state for reliability weighting.
    Silence when nothing matches — never invention.
    """
    from levi.demand.watcher import (  # lazy: no import cycle
        _bump_quality,
        candidate_count,
        extract_needs,
    )

    receipt = {"items": len(items), "candidates": 0, "signals": 0,
               "signal_ids": []}
    for it in items:
        text = str(it.get("text") or "")
        origin = it.get("origin")
        needs = extract_needs(text)
        _bump_quality(state, channel, candidate_count(text), len(needs))
        for need in needs:
            receipt["candidates"] += 1
            sig = dp.scan_seed(need, segment="general", source=channel,
                               origin=origin)
            if getattr(sig, "is_new_registration", True):
                receipt["signals"] += 1
                if sig.id not in receipt["signal_ids"]:
                    receipt["signal_ids"].append(sig.id)
    return receipt


def poll_rss(dp, state, feeds: Optional[List[str]] = None,
             deadline: Optional[float] = None) -> Dict[str, Any]:
    """One bounded RSS/Atom poll tick (E3/E4)."""
    from levi.demand import cybrus_alliance as _alliance

    urls = feed_list(feeds)[:MAX_FEEDS_PER_TICK]
    receipt: Dict[str, Any] = {
        "channel": "rss", "status": "ok", "feeds": 0, "fetched": 0,
        "cooled_down": 0, "failed": 0, "candidates": 0, "signals": 0,
        "signal_ids": [],
    }
    for url in urls:
        if deadline is not None and time.time() >= deadline:
            receipt["status"] = "budget_exceeded"
            break
        receipt["feeds"] += 1
        if not _cooldown_ok(state, "rss", url):
            receipt["cooled_down"] += 1
            continue
        _stamp_cooldown(state, "rss", url)
        status, body = _http_get(url)
        if status != 200 or not body:
            receipt["failed"] += 1
            continue
        receipt["fetched"] += 1
        items = []
        for it in parse_feed(body):
            # One mining pass per item (title + summary combined). The old
            # code mined the title alone AND title+summary, doubling
            # candidates and inflating seen_count with re-poll artifacts.
            title = it["title"]
            summary = it["summary"]
            text = f"{title}. {summary}" if summary else title
            items.append(
                {
                    "text": text,
                    "origin": {"link": it["link"], "feed": url}
                    if it["link"]
                    else {"feed": url},
                }
            )
        # L8 (watcher law): threats are not demand — route as intel.
        mined = _mine(dp, state, "rss", items)
        receipt["candidates"] += mined["candidates"]
        receipt["signals"] += mined["signals"]
        receipt["signal_ids"].extend(
            i for i in mined["signal_ids"] if i not in receipt["signal_ids"]
        )
        intel = [it["text"] for it in items
                 if _alliance.extract_threats(it["text"])]
        if intel:
            receipt.setdefault("threat_intel", {"shared": 0})
            shared = _alliance.share_intel(
                [{"id": url, "text": t, "channel": "rss"} for t in intel[:5]]
            )
            receipt["threat_intel"]["shared"] += shared.get("shared", 0)
    state.touch("rss")
    return receipt


def poll_hn(dp, state, queries: Tuple[str, ...] = HN_AMBIENT_QUERIES,
            deadline: Optional[float] = None) -> Dict[str, Any]:
    """One bounded Hacker News poll tick via the keyless Algolia API (E1-E4)."""
    from levi.demand.ingest import fetch_hackernews  # stdlib, keyless

    receipt: Dict[str, Any] = {
        "channel": "hn", "status": "ok", "queries": 0, "fetched": 0,
        "cooled_down": 0, "candidates": 0, "signals": 0, "signal_ids": [],
    }
    for q in queries:
        if deadline is not None and time.time() >= deadline:
            receipt["status"] = "budget_exceeded"
            break
        receipt["queries"] += 1
        if not _cooldown_ok(state, "hn", q):
            receipt["cooled_down"] += 1
            continue
        _stamp_cooldown(state, "hn", q)
        try:
            hits = fetch_hackernews(q)[:HN_HITS_PER_QUERY]
        except Exception:
            hits = []
        if not hits and not _cooldown_ok(state, "hn", q):
            pass
        receipt["fetched"] += len(hits)
        items = [
            {
                "text": h.get("text", ""),
                "origin": {"link": h.get("url", ""), "query": q}
                if h.get("url")
                else {"query": q},
            }
            for h in hits if h.get("text")
        ]
        mined = _mine(dp, state, "hn", items)
        receipt["candidates"] += mined["candidates"]
        receipt["signals"] += mined["signals"]
        receipt["signal_ids"].extend(
            i for i in mined["signal_ids"] if i not in receipt["signal_ids"]
        )
    state.touch("hn")
    return receipt


def poll_providers(dp, state,
                   deadline: Optional[float] = None) -> Dict[str, Any]:
    """One bounded tick across the keyless provider fetchers in
    ``levi.demand.ingest`` (reddit / stackoverflow / github / arxiv / jobs).

    Every fetcher degrades to ``[]`` on any failure and never raises
    (E1); there is a belt-and-braces try/except here too. Per-provider-
    query cooldowns ride the watcher state — timestamps only, never
    bodies (L5). Mining and ingestion go through ``_mine`` ->
    ``DemandPulse.scan_seed``: HYPOTHESIS at 0.35 with the provider name
    as the source label (E2). Honest limit: Reddit rate-limits
    aggressively from datacenters — a 429 is an empty contribution,
    never a tick-breaking error.
    """
    from levi.demand import ingest as _ing

    channels: Dict[str, Any] = {}
    for channel, fetcher_name, queries in _PROVIDER_SPECS:
        if deadline is not None and time.time() >= deadline:
            channels[channel] = {
                "channel": channel, "status": "budget_exceeded",
                "queries": 0, "signals": 0,
            }
            continue
        state.channels.setdefault(
            channel, {"last_poll": None, "seen_ids": []})
        fetcher = getattr(_ing, fetcher_name)
        receipt: Dict[str, Any] = {
            "channel": channel, "status": "ok", "queries": 0, "fetched": 0,
            "cooled_down": 0, "candidates": 0, "signals": 0, "signal_ids": [],
        }
        for q in queries:
            if deadline is not None and time.time() >= deadline:
                receipt["status"] = "budget_exceeded"
                break
            receipt["queries"] += 1
            if not _cooldown_ok(state, channel, q):
                receipt["cooled_down"] += 1
                continue
            _stamp_cooldown(state, channel, q)
            try:
                hits = fetcher(q)[:PROVIDER_HITS_PER_QUERY]
            except Exception:
                hits = []
            receipt["fetched"] += len(hits)
            items = [
                {
                    "text": h.get("text", ""),
                    "origin": {"link": h.get("url", ""), "query": q}
                    if isinstance(h, dict) and h.get("url")
                    else ({"query": q} if isinstance(h, dict) else None),
                }
                for h in hits
                if isinstance(h, dict) and h.get("text")
            ]
            mined = _mine(dp, state, channel, items)
            receipt["candidates"] += mined["candidates"]
            receipt["signals"] += mined["signals"]
            receipt["signal_ids"].extend(
                i for i in mined["signal_ids"]
                if i not in receipt["signal_ids"]
            )
        state.touch(channel)
        channels[channel] = receipt
    return {"at": _now_iso(), "channels": channels}


def run_eyes(dp=None, state=None,
             budget_s: float = TICK_BUDGET_S) -> Dict[str, Any]:
    """Run the server-side sensing tick: rss + hn + keyless providers
    inside one budget (E4)."""
    from levi.demand.pulse import DemandPulse
    from levi.demand.watcher import WatcherState

    dp = dp or DemandPulse()
    state = state or WatcherState.load()
    deadline = time.time() + budget_s
    channels = {
        "rss": poll_rss(dp, state, deadline=deadline),
        "hn": poll_hn(dp, state, deadline=deadline),
    }
    channels.update(poll_providers(dp, state, deadline=deadline)["channels"])
    state.save()
    return {"at": _now_iso(), "channels": channels}


_PROVIDER_QUERY_MAP = {ch: list(qs) for ch, _, qs in _PROVIDER_SPECS}

_TRANSPORTS = {
    "rss": "stdlib urllib RSS/Atom (keyless public reads)",
    "hn": "Hacker News Algolia API (keyless public reads)",
    "reddit": "Reddit public search.json (keyless; rate-limited from datacenters)",
    "stackoverflow": "Stack Exchange API (keyless public reads)",
    "github": "GitHub repo search API (keyless, unauthenticated quota)",
    "arxiv": "arXiv export API (keyless public reads)",
    "jobs": "Remotive + Arbeitnow job boards (keyless public reads)",
}


def status(state=None) -> Dict[str, Any]:
    """Eye health + watermarks. Read-only."""
    from levi.demand.watcher import WatcherState

    state = state or WatcherState.load()
    out = {}
    for ch in EYE_CHANNELS:
        chs = state.channels.get(ch, {})
        if ch == "rss":
            sources = feed_list()
        elif ch == "hn":
            sources = list(HN_AMBIENT_QUERIES)
        else:
            sources = _PROVIDER_QUERY_MAP.get(ch, [])
        out[ch] = {
            "transport": _TRANSPORTS[ch],
            "status": "ok",
            "last_poll": chs.get("last_poll"),
            "cooled_sources": len(chs.get("cooldowns") or {}),
            "feeds": sources,
        }
    return out
