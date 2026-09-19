"""LEVI's context budget packer: fit more knowing into fewer tokens.

Studied from: ai-si-software-internals-20260916-0005/report.md (section 2.3)

The lesson is SmolVLM's: encode an image patch into 81 tokens instead of
16,000, because **context tokens are the scarce resource** — input
compression beats parameter scaling. This module is that lesson as a
runnable tool for text: given content pieces with token costs and a hard
budget, it packs the most valuable content first, summarizes what almost
fits, truncates what stubbornly doesn't, and cuts what can't earn its
place — then tells you exactly what went where and why.

Token counting is an honest estimate: words times a small multiplier, not
a real tokenizer. Anything that charges real money should measure with
the real tokenizer; this is a planning instrument.

Pieces carry a salience score (0.0–1.0): how much of the answer depends
on this piece. The packer orders by salience density (salience per token)
so a short, crucial note outranks a long, decorative one, then fills the
budget greedily:

- fits whole        -> kept verbatim
- fits summarized   -> extractive summary (top sentences by in-piece word
                       frequency, order preserved) sized to the remaining
                       budget share
- fits truncated    -> lead truncated at a sentence boundary with an
                       explicit marker
- doesn't fit       -> cut, with the reason recorded

Every decision lands in the report. Nothing is silently dropped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

ORIGIN = "levi-revival/contextpack"

ESTIMATE_MULTIPLIER = 1.3  # words -> tokens; a guess, labeled as such
SUMMARY_FLOOR_TOKENS = 24  # below this a summary is not worth the paper


def estimate_tokens(text: str) -> int:
    """Estimated token cost of text (word-count heuristic, NOT a tokenizer)."""
    words = len(text.split())
    return max(1, int(words * ESTIMATE_MULTIPLIER)) if words else 0


def split_sentences(text: str) -> List[str]:
    """Naive sentence splitter: good enough for a planning instrument."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]


def _word_frequencies(sentences: List[str]) -> dict:
    freq: dict = {}
    for sent in sentences:
        for word in re.findall(r"[a-z0-9']+", sent.lower()):
            freq[word] = freq.get(word, 0) + 1
    return freq


def extractive_summary(text: str, token_allowance: int) -> str:
    """Top sentences by in-piece word frequency, original order preserved.

    Returns "" if even one good sentence can't fit the allowance.
    """
    sentences = split_sentences(text)
    if not sentences:
        return ""
    freq = _word_frequencies(sentences)
    scored = []
    for i, sent in enumerate(sentences):
        words = re.findall(r"[a-z0-9']+", sent.lower())
        if not words:
            continue
        # length-normalized so long sentences don't win by mass alone
        score = sum(freq.get(w, 0) for w in words) / (len(words) ** 0.5)
        scored.append((score, i, sent))
    scored.sort(key=lambda s: (-s[0], s[1]))
    chosen: List[str] = []
    used = 0
    for _, _, sent in scored:
        cost = estimate_tokens(sent)
        if used + cost <= token_allowance:
            chosen.append(sent)
            used += cost
    if not chosen:
        return ""
    # restore original order so the summary still reads like the source
    chosen.sort(key=lambda s: sentences.index(s))
    return " ".join(chosen)


def truncate_lead(text: str, token_allowance: int) -> str:
    """Keep the leading sentences that fit; mark the cut honestly."""
    sentences = split_sentences(text)
    kept: List[str] = []
    used = 0
    for sent in sentences:
        cost = estimate_tokens(sent)
        if used + cost <= token_allowance:
            kept.append(sent)
            used += cost
        else:
            break
    if not kept:
        return ""
    return " ".join(kept) + " [...truncated]"


@dataclass
class Piece:
    """One candidate chunk of context with its asking price."""

    id: str
    text: str
    salience: float = 0.5  # 0.0-1.0: how much the answer depends on this
    tag: str = ""

    @property
    def tokens(self) -> int:
        return estimate_tokens(self.text)

    @property
    def density(self) -> float:
        """Salience per token — the packing order."""
        return self.salience / max(1, self.tokens)


@dataclass
class Decision:
    """What the packer did with one piece, and why."""

    piece_id: str
    action: str  # kept | summarized | truncated | cut
    reason: str
    tokens_before: int
    tokens_after: int


@dataclass
class PackResult:
    """The packed context plus its paper trail."""

    packed_text: str
    decisions: List[Decision] = field(default_factory=list)
    tokens_used: int = 0
    budget: int = 0

    @property
    def pieces_kept(self) -> List[str]:
        return [d.piece_id for d in self.decisions if d.action == "kept"]

    @property
    def pieces_cut(self) -> List[str]:
        return [d.piece_id for d in self.decisions if d.action == "cut"]

    def explain(self) -> str:
        lines = [
            f"budget={self.budget} used={self.tokens_used}",
        ]
        for d in self.decisions:
            lines.append(
                f"  [{d.action:>10}] {d.piece_id} "
                f"({d.tokens_before}->{d.tokens_after} tok): {d.reason}"
            )
        return "\n".join(lines)


def pack(pieces: List[Piece], budget: int, reserve: int = 0) -> PackResult:
    """Pack pieces into ``budget`` tokens (minus an optional reserve).

    Highest salience-density first; summarize or truncate the almost-fits;
    cut the rest. Returns the packed text and a full decision report.
    """
    if budget < 0:
        raise ValueError("budget must be non-negative")
    allowance = max(0, budget - reserve)
    ordered = sorted(pieces, key=lambda p: (-p.density, p.id))
    chunks: List[str] = []
    decisions: List[Decision] = []
    used = 0

    for piece in ordered:
        remaining = allowance - used
        cost = piece.tokens
        if cost <= 0:
            decisions.append(Decision(piece.id, "cut", "empty piece", 0, 0))
            continue
        if cost <= remaining:
            chunks.append(piece.text)
            used += cost
            decisions.append(
                Decision(piece.id, "kept", "fits whole within budget", cost, cost)
            )
            continue
        # Almost fits? Try a summary sized to the remaining room.
        if remaining >= SUMMARY_FLOOR_TOKENS:
            summary = extractive_summary(piece.text, remaining)
            if summary:
                scost = estimate_tokens(summary)
                chunks.append(summary)
                used += scost
                decisions.append(
                    Decision(
                        piece.id,
                        "summarized",
                        f"extractive summary to {scost} tok",
                        cost,
                        scost,
                    )
                )
                continue
        # Last resort: keep the lead, mark the cut.
        if remaining > 0:
            lead = truncate_lead(piece.text, remaining)
            if lead:
                lcost = estimate_tokens(lead)
                chunks.append(lead)
                used += lcost
                decisions.append(
                    Decision(
                        piece.id,
                        "truncated",
                        "lead kept at sentence boundary",
                        cost,
                        lcost,
                    )
                )
                continue
        decisions.append(
            Decision(
                piece.id,
                "cut",
                f"no room left (needs {cost}, {remaining} remain)",
                cost,
                0,
            )
        )
    return PackResult(
        packed_text="\n\n".join(chunks),
        decisions=decisions,
        tokens_used=used,
        budget=budget,
    )


def demo() -> str:
    pieces = [
        Piece(
            "sys", "You are LEVI, a local-first synthetic intelligence.", 1.0, "system"
        ),
        Piece(
            "notes",
            "Levi likes terse replies. Levi is building an organism, not an app. "
            "Context tokens are the scarce resource. Compression beats scaling. "
            "Salience density decides what survives. Summaries keep the shape.",
            0.8,
            "memory",
        ),
        Piece(
            "fluff",
            "It was a dark and stormy night, and the rain fell in torrents, "
            "except at occasional intervals, when it was checked by a violent "
            "gust of wind which swept up the streets.",
            0.1,
            "color",
        ),
    ]
    result = pack(pieces, budget=40)
    return result.explain()


if __name__ == "__main__":
    print(demo())
