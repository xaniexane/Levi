"""LEVI news — dated current-events recall (stdlib-only).

refresh.py: polite RSS/Atom + HN/arXiv ingestion into days/YYYY-MM-DD.jsonl
search.py:  ranked keyword search with recency weighting over the corpus
guard.py:   out-of-weights guard — news never enters training corpora

Integration points (do not import the CLI or agent runtimes from here):
  - `levi news refresh|latest|search` → cmd_news in core/levi/cli/main.py
    (currently naive substring match; ranked engine is this module's
    search_news, a drop-in scorer)
  - agent tools `news_latest` / `news_search` → core/levi/agent/tools.py
  - `python -m levi.feedreader news-refresh|news-latest|news-search` →
    core/levi/feedreader/__main__.py (stdlib wrapper, no CLI dependency)
"""

from __future__ import annotations

__all__ = ["guard", "refresh", "search"]
