"""Instant local search over the archive-derived index."""

from __future__ import annotations

import re
from typing import Dict, List

__all__ = ["search_index"]

_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")


def search_index(index: Dict[str, List[str]], query: str) -> List[str]:
    """AND-search: message ids containing every query token, sorted."""
    tokens = _TOKEN_RE.findall(query.lower())
    if not tokens:
        return []
    sets = [set(index.get(tok, ())) for tok in tokens]
    hits = set.intersection(*sets) if sets else set()
    return sorted(hits)
