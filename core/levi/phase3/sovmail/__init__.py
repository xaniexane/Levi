"""C12 sovereign mail (WORKING TITLE: naming is Chauncey's).

Eudora's contract, modernized as a refinement of the existing
`levi.mailtriage` — never a rewrite. Survey first: see SURVEY.md for
the kept / extended / superseded mapping.

- `filters.disposition()`: deterministic, priority-ordered filter
  evaluation with matched-filter stamping.
- `bayes`: naive-Bayes spam scoring trained on the local corpus;
  offline retrain is a housekeeping operation.
- `scamlinks`: deterministic scam-link analysis (display-vs-href,
  punycode, credential patterns, IP hosts). No cloud lookups, ever.
- `stationery`: named reply templates with slots; composes DRAFTS
  ONLY — there is no send path in this module.
- `archive`: plain-text mbox files, one per folder; the search index
  is derived from the archive and rebuildable from it.
- `search`: instant local search over the derived index.
- `bridge`: intake via mailtriage's read-only MailStore.

Stdlib-only at import; zero network at runtime; deterministic.
"""

from __future__ import annotations

from . import archive, bayes, scamlinks, search
from .archive import Archive
from .bayes import BayesModel, retrain, score, train
from .filters import Filter, disposition
from .scamlinks import analyze_links, is_suspicious
from .search import search_index
from .stationery import Stationery, compose

__all__ = [
    "Archive",
    "BayesModel",
    "Filter",
    "Stationery",
    "analyze_links",
    "archive",
    "bayes",
    "compose",
    "disposition",
    "is_suspicious",
    "retrain",
    "scamlinks",
    "score",
    "search",
    "search_index",
    "train",
]
