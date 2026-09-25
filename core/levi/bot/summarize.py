"""LEVI bot summarizer — deterministic extractive summaries on a hard budget.

``brief.py`` renders briefing cards with a hard line budget; this is the
matching compressor for long text: ``summarize`` takes a wall of words and
returns the sentences that carry the weight, on a fixed sentence budget.
Nothing is generated — sentences are *selected* from the source, so the
output is verifiable word-for-word against the input.

Algorithm (stdlib-only, deterministic, LEVI-original):
* split the text into sentences (``.!?`` followed by whitespace);
* score each sentence by the sum of its significant-word frequencies —
  significant = lowercase alphabetic, length >= 4, not in a small stop
  list; frequency is computed over the whole text;
* ties break toward the earlier sentence, then the shorter one — same
  inputs always yield the same summary;
* keep the top ``max_lines`` sentences in original order; the rest are
  counted in ``dropped`` and reported, never silently lost.

Deny-closed: empty or non-string input, non-positive budgets, and
oversized single sentences that violate ``max_chars`` on their own are
refused with a named error, never coerced. ``max_chars`` trims at
sentence boundaries — a sentence is never cut in half.

Usage::

    from levi.bot.summarize import summarize

    result = summarize(long_thread, max_lines=4)
    print(result.text)      # <= 4 sentences, source order
    print(result.dropped)   # how many sentences didn't fit
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

__all__ = ["SummaryError", "SummaryResult", "summarize", "SHELF"]


class SummaryError(ValueError):
    """Raised when summarizer inputs fail validation."""


@dataclass(frozen=True)
class SummaryResult:
    """The summary plus honest accounting of the compression."""

    text: str
    sentences: int  # sentences in the summary (always <= max_lines)
    dropped: int  # source sentences held back for lack of budget
    compression: float  # sentences kept / sentences in source (1.0 = no cut)


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[\"'(\[]?[A-Z0-9])")
_WORD = re.compile(r"[a-z]+")

_STOP = frozenset(
    """
    about above after again along also always among another because before being
    been between both could does doing down each either even every first from
    had have having here however into itself just like many more most much only
    other over same should such than that them then there these they this those
    though through under very what when where which while with within would
    their will your just than then than them
    """.split()
)


def _sentences(text: str) -> List[str]:
    chunks = _SENTENCE_SPLIT.split(text.strip())
    out: List[str] = []
    buf = ""
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        buf = f"{buf} {chunk}".strip() if buf else chunk
        # Merge a chunk that is clearly a fragment (no terminal punctuation)
        # with the next one instead of scoring it alone.
        if not re.search(r"[.!?][\"')\]]?\s*$", chunk):
            continue
        out.append(buf)
        buf = ""
    if buf:
        out.append(buf)
    return [s for s in out if s]


def _significant_words(sentence: str) -> List[str]:
    return [
        w for w in _WORD.findall(sentence.lower()) if len(w) >= 4 and w not in _STOP
    ]


def summarize(
    text: str,
    max_lines: int = 6,
    max_chars: int | None = None,
) -> SummaryResult:
    """Summarize *text* to at most *max_lines* sentences from the source."""
    if not isinstance(text, str):
        raise SummaryError("text must be a string")
    if not text.strip():
        raise SummaryError("text is empty — nothing to summarize")
    if isinstance(max_lines, bool) or not isinstance(max_lines, int):
        raise SummaryError("max_lines must be an integer")
    if max_lines < 1:
        raise SummaryError(f"max_lines must be >= 1, got {max_lines}")
    if max_chars is not None:
        if isinstance(max_chars, bool) or not isinstance(max_chars, int):
            raise SummaryError("max_chars must be an integer")
        if max_chars < 1:
            raise SummaryError(f"max_chars must be >= 1, got {max_chars}")

    sentences = _sentences(text)
    if not sentences:
        raise SummaryError("text contains no sentences — nothing to summarize")

    freq: Dict[str, int] = {}
    words_per: List[List[str]] = []
    for s in sentences:
        words = _significant_words(s)
        words_per.append(words)
        for w in words:
            freq[w] = freq.get(w, 0) + 1

    scored: List[Tuple[int, int, int, str]] = []
    for idx, (s, words) in enumerate(zip(sentences, words_per, strict=True)):
        score = sum(freq[w] for w in words)
        # Deterministic ordering: highest score first; ties break toward
        # the earlier sentence, then the shorter one.
        scored.append((-score, idx, len(s), s))

    budget = max_lines
    if max_chars is not None and any(len(s) > max_chars for s in sentences):
        raise SummaryError(
            "a source sentence exceeds max_chars on its own — "
            "sentences are never cut in half"
        )

    chosen_idx = sorted(i for _, i, _, _ in sorted(scored)[:budget])
    if max_chars is not None:
        kept: List[int] = []
        total = 0
        for i in chosen_idx:
            add = len(sentences[i]) + (1 if kept else 0)
            if total + add > max_chars:
                break
            kept.append(i)
            total += add
        if not kept:
            raise SummaryError(
                "max_chars budget fits no full sentence — nothing returned"
            )
        chosen_idx = kept

    chosen = [sentences[i] for i in chosen_idx]
    kept_text = " ".join(chosen)
    compression = len(chosen) / len(sentences)
    return SummaryResult(
        text=kept_text,
        sentences=len(chosen),
        dropped=len(sentences) - len(chosen),
        compression=round(compression, 4),
    )


SHELF = {
    "name": "bot-summarize",
    "summary": (
        "Deterministic extractive summaries on a hard sentence budget: "
        "sentences are selected from the source, never generated; scoring "
        "by significant-word frequency with positional tie-breaks; held-back "
        "sentences counted, never silently lost."
    ),
    "items": [
        {
            "name": "summarize",
            "kind": "function",
            "path": "levi/bot/summarize.py",
            "description": "summarize(text, max_lines=6, max_chars=None) -> SummaryResult",
        },
    ],
}
