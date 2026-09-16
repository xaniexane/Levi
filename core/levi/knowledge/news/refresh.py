"""Current-events ingestion for LEVI (stdlib-only).

Fetches a curated source list (RSS/Atom via xml.etree, Hacker News JSON
API, arXiv RSS), stores per-day JSONL at days/YYYY-MM-DD.jsonl with
records {date, source, title, summary, url}. Dedupes by normalized URL
(tracking params stripped) and by normalized-title hash within and
across days, so the same story syndicated under two URLs is kept once.

Polite: 10s timeout, 0.5s delay between requests, LEVI user-agent.
A dead source never crashes the pass — its status is recorded in
sources.json.

Deliberate design: news is DATED RECALL, not training data. It goes stale;
the tiny brain trains on stable knowledge only (see docs/NEWS.md §
"News never enters training weights").

Deliberate design: news is DATED RECALL, not training data. It goes stale;
the tiny brain trains on stable knowledge only (see docs/BRAIN_TRAINING.md).

Usage: python3 refresh.py [--date YYYY-MM-DD] [--limit N]
"""

from __future__ import annotations

import hashlib
import html
import itertools
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent
DAYS = BASE / "days"
SOURCES_JSON = BASE / "sources.json"
UA = "LEVI-news-refresh/1.0 (dated current-events recall; polite 0.5s delay)"
TIMEOUT = 10
DELAY = 0.5
DEFAULT_LIMIT = 30

SOURCES = [
    {
        "id": "bbc-world",
        "kind": "rss",
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
    },
    {
        "id": "reuters-world",
        "kind": "rss",
        "url": "https://www.reuters.com/rssfeed/worldNews",
    },
    {
        "id": "ap-mirror",
        "kind": "rss",  # AP headlines via feedx.net mirror
        "url": "https://feedx.net/rss/ap.xml",
    },
    {
        "id": "hackernews",
        "kind": "hn",
        "url": "https://hacker-news.firebaseio.com/v0/topstories.json",
    },
    {"id": "arxiv-csai", "kind": "rss", "url": "https://export.arxiv.org/rss/cs.AI"},
    {"id": "arxiv-cscl", "kind": "rss", "url": "https://export.arxiv.org/rss/cs.CL"},
]


def _fetch(url: str) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            ctype = resp.headers.get("Content-Type", "")
            body = resp.read(2_000_000)
            if (
                "html" in ctype
                and "xml" not in ctype
                and "rss" not in ctype
                and "json" not in ctype
                and "text" not in ctype
            ):
                return None
            return body
    except Exception:
        return None


def _clean(text: str | None) -> str:
    if not isinstance(text, str):
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


ATOM_NS = "http://www.w3.org/2005/Atom"


def _rss_items(root: ET.Element):
    for item in root.iter("item"):
        title = _clean(item.findtext("title"))
        link = (item.findtext("link") or "").strip()
        desc = _clean(item.findtext("description"))
        yield title, link, desc


def _atom_entries(root: ET.Element):
    a = ATOM_NS
    for entry in root.iter("{%s}entry" % a):
        title = _clean(entry.findtext("{%s}title" % a))
        link = ""
        for ln in entry.iter("{%s}link" % a):
            href = (ln.get("href") or "").strip()
            rel = (ln.get("rel") or "alternate").strip()
            if href and rel == "alternate" and not link:
                link = href
        summary = _clean(entry.findtext("{%s}summary" % a)) or _clean(
            entry.findtext("{%s}content" % a)
        )
        yield title, link, summary


def _parse_rss(body: bytes) -> list[dict]:
    """Parse an RSS 2.0 or Atom feed into {title, summary, url} items.

    Unparseable or unrecognized feeds degrade to [] — never raise.
    """
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return []
    items = []
    for title, link, summary in itertools.chain(_rss_items(root), _atom_entries(root)):
        if title and link:
            items.append({"title": title, "summary": summary[:600], "url": link})
    return items


def _parse_hn(body: bytes, limit: int) -> list[dict]:
    try:
        ids = json.loads(body.decode("utf-8", "replace"))
    except Exception:
        return []
    if not isinstance(ids, list):
        return []  # unexpected shape from the HN API — degrade, don't crash
    items = []
    for sid in ids[:limit]:
        time.sleep(DELAY)
        raw = _fetch(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json")
        if not raw:
            continue
        try:
            it = json.loads(raw.decode("utf-8", "replace"))
        except Exception:
            continue
        if not isinstance(it, dict) or it.get("type") != "story":
            continue
        url = it.get("url") or f"https://news.ycombinator.com/item?id={sid}"
        items.append(
            {
                "title": _clean(it.get("title")),
                "summary": f"{it.get('score', 0)} points, {it.get('descendants', 0)} comments",
                "url": url,
            }
        )
    return items


# Query params that carry tracking, not identity — stripped for dedup.
_TRACKING_PARAMS = frozenset(
    (
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "at_medium",
        "at_campaign",
    )
)


def _norm_url(url: str) -> str:
    """Canonicalize a URL for dedup: lowercase host, drop tracking params,
    drop trailing slash. Two links to the same story must collide."""
    try:
        p = urllib.parse.urlparse(url)
        q = sorted(
            (k, v)
            for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True)
            if k.lower() not in _TRACKING_PARAMS
        )
        path = p.path.rstrip("/") or "/"
        return urllib.parse.urlunparse(
            (
                p.scheme.lower(),
                p.netloc.lower(),
                path,
                "",
                urllib.parse.urlencode(q),
                "",
            )
        )
    except Exception:
        return url


def _title_key(title: str) -> str:
    """Stable hash of a normalized title — the same story syndicated under
    two different URLs still dedups."""
    norm = re.sub(r"[^a-z0-9 ]", " ", title.lower())
    norm = re.sub(r"\s+", " ", norm).strip()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def _load_known() -> tuple[set[str], set[str]]:
    """(normalized URLs, title hashes) seen in any stored day."""
    urls: set[str] = set()
    titles: set[str] = set()
    if DAYS.exists():
        for fp in sorted(DAYS.glob("*.jsonl")):
            try:
                text = fp.read_text(encoding="utf-8")
            except OSError:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    # Corrupt line in a prior day's harvest: skip it loudly
                    # rather than aborting the whole refresh.
                    print(f"  warn: {fp.name}:{lineno}: corrupt JSON line, skipping")
                    continue
                if isinstance(rec, dict):
                    if rec.get("url"):
                        urls.add(_norm_url(rec["url"]))
                    if rec.get("title"):
                        titles.add(_title_key(rec["title"]))
    return urls, titles


def _known_urls(day: str) -> set[str]:  # noqa: ARG001 - day kept for API compat
    """URLs (normalized) seen in any stored day."""
    return _load_known()[0]


def _known_title_keys() -> set[str]:
    """Title hashes seen in any stored day."""
    return _load_known()[1]


def refresh(day: str | None = None, limit: int = DEFAULT_LIMIT) -> dict:
    day = day or date.today().isoformat()
    try:
        date.fromisoformat(day)
    except (ValueError, TypeError):
        raise ValueError("refresh: day must be YYYY-MM-DD, got %r" % (day,)) from None
    if not isinstance(limit, int) or limit < 1:
        raise ValueError("refresh: limit must be a positive int, got %r" % (limit,))
    DAYS.mkdir(parents=True, exist_ok=True)
    known = _known_urls(day)
    known_titles = _known_title_keys()
    records: list[dict] = []
    statuses: dict[str, str] = {}
    if SOURCES_JSON.exists():
        try:
            loaded = json.loads(SOURCES_JSON.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(
                "refresh: sources.json is corrupt (%s); fix or delete %s"
                % (exc, SOURCES_JSON)
            ) from exc
        if not isinstance(loaded, dict):
            raise ValueError(
                "refresh: sources.json must be a JSON object, got %s; "
                "fix or delete %s" % (type(loaded).__name__, SOURCES_JSON)
            )
        statuses = loaded

    for src in SOURCES:
        sid = src["id"]
        body = _fetch(src["url"])
        time.sleep(DELAY)
        if body is None:
            statuses[sid] = f"dead ({day})"
            continue
        try:
            if src["kind"] == "hn":
                items = _parse_hn(body, limit)
            else:
                items = _parse_rss(body)[:limit]
        except Exception as exc:  # noqa: BLE001 - never crash the pass
            statuses[sid] = f"parse-error ({day}): {type(exc).__name__}"
            continue
        if not items:
            statuses[sid] = f"empty ({day})"
            continue
        added = 0
        for it in items:
            nurl = _norm_url(it["url"])
            tkey = _title_key(it["title"])
            if nurl in known or tkey in known_titles:
                continue
            known.add(nurl)
            known_titles.add(tkey)
            records.append(
                {
                    "date": day,
                    "source": sid,
                    "title": it["title"],
                    "summary": it["summary"],
                    "url": it["url"],
                }
            )
            added += 1
        statuses[sid] = f"ok ({day}): {added} new / {len(items)} fetched"

    if records:
        day_path = DAYS / f"{day}.jsonl"
        with open(day_path, "a", encoding="utf-8") as fh:
            for r in records:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    SOURCES_JSON.write_text(json.dumps(statuses, indent=1), encoding="utf-8")
    summary = {"day": day, "new_records": len(records), "sources": statuses}
    print(f"day {day}: {len(records)} new records")
    for sid, st in statuses.items():
        print(f"  {sid}: {st}")
    return summary


def main(argv: list[str]) -> int:
    day = None
    limit = DEFAULT_LIMIT
    for a in argv:
        if a.startswith("--date="):
            day = a.split("=", 1)[1]
        elif a.startswith("--limit="):
            try:
                limit = int(a.split("=", 1)[1])
            except ValueError:
                print(
                    "refresh: --limit must be a positive integer, got %r"
                    % a.split("=", 1)[1]
                )
                return 2
    try:
        refresh(day, limit)
    except ValueError as exc:
        print("refresh: %s" % exc)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
