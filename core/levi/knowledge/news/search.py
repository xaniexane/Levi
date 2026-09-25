"""Ranked search over LEVI's dated news corpus (stdlib-only).

Scoring per record:
  - +3 per query token found in the title (normalized token match)
  - +1 per query token found in the summary
  - +4 exact-phrase bonus (the full query, minus stopwords, as a substring
    of title+summary)
  - × recency weight 1/(1+age_days/7): a week-old hit scores half a fresh
    one. Dated recall, so staleness is priced in, not hidden.

Empty query or empty corpus → [] — the caller reports "no matches",
never improvises. 2-letter tokens (AI, EU, US) count: dropping them
silently returned zero hits for the queries people actually type.

Usage:
    from levi.knowledge.news import search
    hits = search.search_news("quantum error correction")
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent
DEFAULT_DAYS = BASE / "days"

TITLE_W = 3.0
SUMMARY_W = 1.0
PHRASE_W = 4.0
RECENCY_HALF_LIFE_DAYS = 7.0

_STOP = frozenset(
    """
    a an the and or but of for to in on at by with from as is are was were
    be been being it its this that these those they them their he she we you
    your our his her has have had will would can could should may might do
    does did not no yes if then than so such over under into out up down
    about after before between during while where when what which who whom
    whose how all any both each few more most other some such only own same
    too very can will just don should now over under again further once here
    there when where why how
    """.split()
)


def tokenize(text: str | None) -> list[str]:
    """Lowercase alphanumeric tokens, stopwords removed, length > 1."""
    if not isinstance(text, str):
        return []
    return [
        t
        for t in re.findall(r"[a-z0-9]+", text.lower())
        if t not in _STOP and len(t) > 1
    ]


def _age_days(rec: dict, today: date | None = None) -> int:
    today = today or date.today()
    try:
        d = date.fromisoformat(str(rec.get("date", "")))
    except (ValueError, TypeError):
        return 0
    age = (today - d).days
    return age if age >= 0 else 0


def load_corpus(days_dir: "str | Path | None" = None) -> list[dict]:
    """All records in days/*.jsonl. Corrupt lines are skipped loudly."""
    d = Path(days_dir) if days_dir is not None else DEFAULT_DAYS
    records: list[dict] = []
    if not d.is_dir():
        return records
    for fp in sorted(d.glob("*.jsonl")):
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
                print(f"  warn: {fp.name}:{lineno}: corrupt JSON line, skipping")
                continue
            if isinstance(rec, dict) and rec.get("title"):
                records.append(rec)
    return records


def corpus_range(days_dir: "str | Path | None" = None) -> str:
    """'YYYY-MM-DD..YYYY-MM-DD (N records)' or 'empty' — honest bounds."""
    recs = load_corpus(days_dir)
    if not recs:
        return "empty"
    dates = sorted(r.get("date", "?") for r in recs)
    return f"{dates[0]}..{dates[-1]} ({len(recs)} records)"


def latest(days_dir: "str | Path | None" = None, limit: int = 10) -> list[dict]:
    recs = load_corpus(days_dir)
    recs.sort(key=lambda r: str(r.get("date", "")), reverse=True)
    return recs[: max(limit, 0)]


def search_news(
    query: str,
    days_dir: "str | Path | None" = None,
    limit: int = 20,
    today: date | None = None,
) -> list[dict]:
    """Ranked keyword search. Returns hits as copies of the record plus
    'score' (rounded) and 'age_days'. Sorted best-first."""
    tokens = tokenize(query)
    if not tokens:
        return []
    phrase = " ".join(tokens)
    hits = []
    for rec in load_corpus(days_dir):
        title = str(rec.get("title", ""))
        summary = str(rec.get("summary", ""))
        title_t = set(tokenize(title))
        summary_t = set(tokenize(summary))
        score = sum(TITLE_W for t in tokens if t in title_t)
        score += sum(SUMMARY_W for t in tokens if t in summary_t)
        if phrase and phrase in f"{title} {summary}".lower():
            score += PHRASE_W
        if score <= 0:
            continue
        age = _age_days(rec, today)
        score *= 1.0 / (1.0 + age / RECENCY_HALF_LIFE_DAYS)
        hit = dict(rec)
        hit["score"] = round(score, 2)
        hit["age_days"] = age
        hits.append(hit)
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[: max(limit, 0)]
