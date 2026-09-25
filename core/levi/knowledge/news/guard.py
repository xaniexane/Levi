"""Out-of-weights guard: news is dated recall, never training data.

LEVI's news corpus goes stale by design — headlines are true today and
noise next month. The native brain trains on stable knowledge only.
This module gives the training pipeline (and its tests) a mechanical
check: any JSONL training corpus must contain zero news-shaped records.

A news-shaped record is the refresh.py record format:
{"date", "source", "title", "summary", "url"}. The brain's training
records are {"text": ...} — a different shape, so the check is cheap
and has no false positives on real training data.
"""

from __future__ import annotations

import json
from pathlib import Path

NEWS_RECORD_KEYS = ("date", "source", "title", "summary", "url")
NEWS_DIR = Path(__file__).resolve().parent


class GuardError(Exception):
    """A news record leaked into a training corpus."""


def looks_like_news_record(rec: object) -> bool:
    return (
        isinstance(rec, dict)
        and all(k in rec for k in NEWS_RECORD_KEYS)
        and isinstance(rec.get("url"), str)
        and rec["url"].startswith("http")
    )


def assert_no_news_records(corpus_path: "str | Path") -> int:
    """Scan a JSONL training corpus. Raise GuardError on the first
    news-shaped record; return the number of lines scanned otherwise.

    Non-JSON lines are not this guard's business — the training pipe
    judges corrupt corpora itself (it fails loudly, not silently).
    """
    corpus_path = Path(corpus_path)
    scanned = 0
    with corpus_path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            scanned += 1
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if looks_like_news_record(rec):
                raise GuardError(
                    "%s:%d: news record leaked into a training corpus — "
                    "news is dated recall and is never baked into weights "
                    "(see docs/NEWS.md)" % (corpus_path, lineno)
                )
    return scanned
