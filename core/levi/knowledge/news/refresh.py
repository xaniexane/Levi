"""Current-events ingestion for LEVI (stdlib-only).

Fetches a curated source list (RSS via xml.etree, Hacker News JSON API,
arXiv RSS), stores per-day JSONL at days/YYYY-MM-DD.jsonl with records
{date, source, title, summary, url}. Dedupes by URL within and across days.

Polite: 10s timeout, 0.5s delay between requests, LEVI user-agent.
A dead source never crashes the pass — its status is recorded in
sources.json.

Deliberate design: news is DATED RECALL, not training data. It goes stale;
the tiny brain trains on stable knowledge only (see docs/BRAIN_TRAINING.md).

Usage: python3 refresh.py [--date YYYY-MM-DD] [--limit N]
"""
from __future__ import annotations

import html
import json
import re
import sys
import time
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
    {"id": "bbc-world", "kind": "rss",
     "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
    {"id": "reuters-world", "kind": "rss",
     "url": "https://www.reuters.com/rssfeed/worldNews"},
    {"id": "ap-mirror", "kind": "rss",  # AP headlines via feedx.net mirror
     "url": "https://feedx.net/rss/ap.xml"},
    {"id": "hackernews", "kind": "hn",
     "url": "https://hacker-news.firebaseio.com/v0/topstories.json"},
    {"id": "arxiv-csai", "kind": "rss",
     "url": "https://export.arxiv.org/rss/cs.AI"},
    {"id": "arxiv-cscl", "kind": "rss",
     "url": "https://export.arxiv.org/rss/cs.CL"},
]


def _fetch(url: str) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            ctype = resp.headers.get("Content-Type", "")
            body = resp.read(2_000_000)
            if "html" in ctype and "xml" not in ctype and "rss" not in ctype \
                    and "json" not in ctype and "text" not in ctype:
                return None
            return body
    except Exception:
        return None


def _clean(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_rss(body: bytes) -> list[dict]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return []
    items = []
    for item in root.iter("item"):
        title = _clean(item.findtext("title"))
        link = (item.findtext("link") or "").strip()
        desc = _clean(item.findtext("description"))
        if title and link:
            items.append({"title": title, "summary": desc[:600], "url": link})
    return items


def _parse_hn(body: bytes, limit: int) -> list[dict]:
    try:
        ids = json.loads(body.decode("utf-8", "replace"))
    except Exception:
        return []
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
        if it.get("type") != "story":
            continue
        url = it.get("url") or f"https://news.ycombinator.com/item?id={sid}"
        items.append({
            "title": _clean(it.get("title")),
            "summary": f"{it.get('score', 0)} points, {it.get('descendants', 0)} comments",
            "url": url,
        })
    return items


def _known_urls(day: str) -> set[str]:
    known: set[str] = set()
    if DAYS.exists():
        for fp in sorted(DAYS.glob("*.jsonl")):
            try:
                for line in fp.read_text(encoding="utf-8").splitlines():
                    u = json.loads(line).get("url")
                    if u:
                        known.add(u)
            except OSError:
                continue
    return known


def refresh(day: str | None = None, limit: int = DEFAULT_LIMIT) -> dict:
    day = day or date.today().isoformat()
    DAYS.mkdir(parents=True, exist_ok=True)
    known = _known_urls(day)
    records: list[dict] = []
    statuses: dict[str, str] = {}
    if SOURCES_JSON.exists():
        try:
            statuses = json.loads(SOURCES_JSON.read_text(encoding="utf-8"))
        except Exception:
            statuses = {}

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
            if it["url"] in known:
                continue
            known.add(it["url"])
            records.append({"date": day, "source": sid,
                            "title": it["title"], "summary": it["summary"],
                            "url": it["url"]})
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
            limit = int(a.split("=", 1)[1])
    refresh(day, limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
