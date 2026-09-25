"""DemandPulse dedup helpers — normalization + conservative near-dup guard.

Where the dupes came from (found 2026-09-22): ``DemandPulse.scan_seed``,
``score_opportunity`` and ``score_five_factor`` all appended blindly, and
``workflows._feed_clusters`` bypassed the scan path entirely with direct
``dp.signals.append`` calls. The live store held 100 signals with 3 unique
ids and 32 identical "Shift planner" score cards. Every one of those paths
now funnels through these helpers.

Honest limits (read before trusting the "near" in near-dup):
  - This is token-overlap on normalized text, not semantic understanding.
  - An exact normalized match is a hard dupe, always caught.
  - Near-dup fires only when the smaller token set is >= 80% contained in
    the larger one (``NEAR_DUP_CONTAINMENT``). Paraphrases that swap
    vocabulary ("need shift help" vs "require rota assistance") are NOT
    caught and will coexist as separate signals. That is a known gap,
    not a bug — no fuzzy-matching claims are made here.
  - Matching is segment-scoped by the caller: the same words in different
    segments are treated as different signals, so a watched segment never
    silently swallows a signal into another segment's bucket.

stdlib-only.
"""

from __future__ import annotations

import re
import unicodedata
from typing import List, Optional, Tuple

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")

#: Containment ratio at/above which two normalized texts count as near-dupes.
NEAR_DUP_CONTAINMENT = 0.8


def normalize_text(text: str) -> str:
    """Collapse a signal/card title to its canonical dupe-check form.

    NFKC unicode normalize -> casefold -> punctuation to spaces ->
    whitespace collapsed and stripped. ``"Need  Shifts—Help!"`` and
    ``"need shifts help"`` normalize identically.
    """
    t = unicodedata.normalize("NFKC", text or "")
    t = t.casefold()
    t = _PUNCT_RE.sub(" ", t)
    return _WS_RE.sub(" ", t).strip()


def _token_set(normalized: str) -> frozenset:
    return frozenset(normalized.split())


def near_duplicate(
    a_norm: str, b_norm: str, threshold: float = NEAR_DUP_CONTAINMENT
) -> bool:
    """True when two *normalized* texts are the same or near-dupes.

    Near-dupe = the smaller token set is >= ``threshold`` contained in the
    larger one. Symmetric in outcome (uses the min side), cheap, and
    deliberately conservative: "i need help scheduling shifts" matches
    "need shifts help" (3/3 contained), but "need shifts help" does NOT
    match "need tutoring help" (2/3 contained).
    """
    if a_norm == b_norm:
        return True
    ta, tb = _token_set(a_norm), _token_set(b_norm)
    if not ta or not tb:
        return False
    containment = len(ta & tb) / min(len(ta), len(tb))
    return containment >= threshold


def find_duplicate(
    needle_norm: str, candidates: List[Tuple[str, str]]
) -> Optional[str]:
    """Return the key of the first dupe of ``needle_norm`` in ``candidates``.

    ``candidates`` is ``[(key, normalized_text), ...]`` in preference order
    (oldest first). Exact normalized matches win over near-dupes; within
    each class the earliest candidate wins. None when nothing matches.
    """
    for key, cand_norm in candidates:
        if cand_norm == needle_norm:
            return key
    for key, cand_norm in candidates:
        if near_duplicate(needle_norm, cand_norm):
            return key
    return None
