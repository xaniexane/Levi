"""Ranked search over the video-learn corpus (stdlib-only).

Same scoring pattern as knowledge/news/search.py:
  - +3 per query token found in the title
  - +1 per query token found in the summary / key points
  - +4 exact-phrase bonus (query minus stopwords as a substring of
    title+summary)
  - x recency weight 1/(1+age_days/7): dated entries, staleness priced in.

Empty query or empty corpus -> [] — the caller reports "no matches",
never improvises.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

BASE = Path(__file__).resolve().parent
DEFAULT_DAYS = BASE / "days"

TITLE_W = 3.0
BODY_W = 1.0
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


def tokenize(text: Optional[str]) -> List[str]:
    if not isinstance(text, str):
        return []
    return [
        t
        for t in re.findall(r"[a-z0-9]+", text.lower())
        if t not in _STOP and len(t) > 1
    ]


def _age_days(rec: Dict, today: Optional[date] = None) -> int:
    today = today or date.today()
    try:
        y, m, d = (int(x) for x in rec.get("date", "").split("-"))
        return max(0, (today - date(y, m, d)).days)
    except Exception:
        return 0


def _body(rec: Dict) -> str:
    parts = [rec.get("refined_summary") or ""]
    parts.extend(rec.get("key_points") or [])
    parts.extend(rec.get("tags") or [])
    return " ".join(parts)


def _score(rec: Dict, qtokens: List[str], phrase: str, today: Optional[date]) -> float:
    title = rec.get("title") or ""
    body = _body(rec)
    title_tokens = set(tokenize(title))
    body_tokens = set(tokenize(body))
    s = sum(TITLE_W for t in qtokens if t in title_tokens)
    s += sum(BODY_W for t in qtokens if t in body_tokens)
    if phrase and phrase in (title + " " + body).lower():
        s += PHRASE_W
    age = _age_days(rec, today)
    s *= 1.0 / (1.0 + age / RECENCY_HALF_LIFE_DAYS)
    return s


def _iter_records(days_dir: Path):
    if not days_dir.exists():
        return
    for day_file in sorted(days_dir.glob("*.jsonl")):
        for line in day_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue


def search_video_learn(
    query: str,
    days_dir: Optional[Path] = None,
    limit: int = 10,
    today: Optional[date] = None,
) -> List[Dict]:
    """Ranked hits over the video-learn corpus. [] when nothing matches."""
    qtokens = tokenize(query)
    if not qtokens:
        return []
    phrase = " ".join(t for t in tokenize(query) if t not in _STOP) or " ".join(qtokens)
    root = days_dir or DEFAULT_DAYS
    scored = []
    for rec in _iter_records(root):
        s = _score(rec, qtokens, phrase, today)
        if s > 0:
            scored.append((s, rec))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [
        {
            "score": round(s, 3),
            "title": r.get("title"),
            "source_url": r.get("source_url"),
            "date": r.get("date"),
            "refined_by": r.get("refined_by"),
            "refined_summary": (r.get("refined_summary") or "")[:400],
        }
        for s, r in scored[:limit]
    ]
