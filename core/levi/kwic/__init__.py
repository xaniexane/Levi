"""kwic — Key Word In Context concordances for LEVI's local archive.

Clean-room LEVI-native revival of the KWIC permuted index (Luhn, IBM, 1958;
Crestadoro's keyword-in-titles, 1864; perpetual-hunt daily 2026-09-27,
record ``arch-method-kwic-permuted-index``): rotate every significant word
of every title into a fixed position, show it in context, alphabetize —
browse a collection with no search box. This is NOT any product's code; it
is the published indexing procedure, reimplemented from first principles.

LAWS (declared first, proved by tests/test_kwic.py):
  L1 every significant word becomes exactly one entry — nothing significant
     is lost, nothing insignificant is indexed.
  L2 entries sort case-insensitively by keyword — the index is browsable.
  L3 rotation is lossless — left + keyword + right reconstructs the title.

Public API:
    kwic_index(entries, stopwords=STOPWORDS) -> list[KWICEntry]
    render(entries, keyword_col=32) -> str
    from_records(records) -> list of (title, id) pairs
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

__all__ = [
    "STOPWORDS",
    "KWICEntry",
    "kwic_index",
    "render",
    "from_records",
]

# Articles, prepositions, conjunctions, and other approach-term-poor words.
# Deliberately small and English-only; pass your own set for other corpora.
STOPWORDS = frozenset(
    """
    a an the and or of to in on for with by at from as is are was were be
    been being it its this that these those which who whom whose what when
    where how why not no nor so than too very can will just don should now
    """.split()
)

_PUNCT = ".,;:!?()[]{}\"'`"


@dataclass(frozen=True)
class KWICEntry:
    keyword: str  # the approach term, in its original casing
    left: str     # words before the keyword
    right: str    # words after the keyword
    loc: str      # location code (record id, page, ...)

    def reconstruct(self) -> str:
        """L3: the rotation loses nothing."""
        return " ".join(part for part in (self.left, self.keyword, self.right) if part)


def _significant(word: str, stopwords: frozenset) -> bool:
    key = word.strip(_PUNCT)
    return bool(key) and key.lower() not in stopwords


def kwic_index(entries: Iterable[Tuple[str, str]],
               stopwords: frozenset = STOPWORDS) -> List[KWICEntry]:
    """Build the permuted index. ``entries``: (title, loc) pairs."""
    out: List[KWICEntry] = []
    for title, loc in entries:
        words = title.split()
        for i, word in enumerate(words):
            if not _significant(word, stopwords):
                continue  # L1: stopwords never become entry points
            out.append(
                KWICEntry(
                    keyword=word,  # original token: L3 stays lossless
                    left=" ".join(words[:i]),
                    right=" ".join(words[i + 1:]),
                    loc=str(loc),
                )
            )
    # L2: sort by the keyword's significant form, case-insensitively
    out.sort(key=lambda e: (e.keyword.strip(_PUNCT).lower(),
                            e.left.lower(), e.loc))
    return out


def render(entries: List[KWICEntry], keyword_col: int = 32) -> str:
    """Render entries as aligned concordance lines.

    The keyword starts at ``keyword_col``; left context is right-aligned
    against it (classic centered-keyword layout, adapted to terminals).
    Long left contexts are truncated on the left with '...' — the keyword
    column never moves.
    """
    lines = []
    for e in entries:
        left = e.left
        keep = keyword_col - 1
        if len(left) > keep:
            left = "..." + left[-(keep - 3):]
        pad = " " * max(0, keyword_col - len(left))
        line = "%s%s%s  %s  [%s]" % (left, pad, e.keyword, e.right, e.loc)
        lines.append(line)
    return "\n".join(lines)


def from_records(records: Iterable[Dict]) -> List[Tuple[str, str]]:
    """Turn archive record dicts into (title, id) entry pairs."""
    pairs = []
    for rec in records:
        title = rec.get("title") or ""
        rid = rec.get("id") or ""
        if title:
            pairs.append((str(title), str(rid)))
    return pairs
