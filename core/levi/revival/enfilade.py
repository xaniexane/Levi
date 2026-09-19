"""enfilade — versioned-document structure as a tree of spans.

Studied from: interfaces-hunt-20260915/report.md (1. Project
Xanadu: enfilade data structures in later Xanadu prototypes).

The load-bearing idea: a document is not a string — it is a tree of
*spans* (start, length) pointing into content versions. Edits do not
rewrite the tree; they append a new version and the spans resolve
through it. History is structural, not a log bolted on after.

LEVI's take: ``Enfilade`` holds an append-only list of content
versions and a tree of ``Span`` nodes. ``edit`` appends a new
version (insert/delete on the resolved text); ``resolve(span)``
returns the text a span covers in the current version; ``history``
walks every version. Spans address content by stable anchor text
rather than raw offsets, so overlapping edits stay meaningful.
This is an original, from-scratch interpretation for LEVI.

Honest limits: a simplified model — spans are stored per version
and rebased naively on edit (O(spans)); no transclusion across
documents (see ``levi.revival.xanadu`` for that); no branching.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

ORIGIN = "levi-revival/enfilade"


@dataclass(frozen=True)
class Span:
    """An addressable stretch of a document version."""

    name: str
    start: int  # offset into the version's text
    length: int

    @property
    def end(self) -> int:
        return self.start + self.length


@dataclass
class Version:
    """One immutable content snapshot."""

    number: int
    text: str
    note: str = ""
    parent: Optional[int] = None


class Enfilade:
    """A versioned document as a tree of spans over content versions."""

    def __init__(self, text: str = "") -> None:
        self._versions: List[Version] = [Version(number=0, text=text, note="genesis")]
        self._spans: Dict[int, Dict[str, Span]] = {0: {}}  # version -> name -> span

    # -- versions -----------------------------------------------------
    @property
    def current(self) -> int:
        return self._versions[-1].number

    def text(self, version: Optional[int] = None) -> str:
        v = self.current if version is None else version
        return self._versions[v].text

    def history(self) -> List[Tuple[int, str, int]]:
        """(number, note, text length) for every version."""
        return [(v.number, v.note, len(v.text)) for v in self._versions]

    def edit(self, start: int, length: int, replacement: str, note: str = "") -> int:
        """Replace [start, start+length) with new text; returns the new
        version number. Spans are rebased across the edit."""
        old = self.text()
        if not (0 <= start <= len(old) and 0 <= length <= len(old) - start):
            raise ValueError("edit range out of bounds")
        new_text = old[:start] + replacement + old[start + length :]
        old_number = self.current
        new_number = len(self._versions)
        self._versions.append(
            Version(number=new_number, text=new_text, note=note, parent=old_number)
        )
        delta = len(replacement) - length
        rebased: Dict[str, Span] = {}
        for name, span in self._spans[old_number].items():
            rebased[name] = self._rebase_span(span, start, length, delta)
        self._spans[new_number] = rebased
        return new_number

    @staticmethod
    def _rebase_span(span: Span, estart: int, elen: int, delta: int) -> Span:
        eend = estart + elen
        if span.end <= estart:
            return span  # fully before the edit
        if span.start >= eend:
            return Span(span.name, span.start + delta, span.length)  # shifted
        # overlap: the span absorbs the edit — it covers its surviving
        # prefix, the replacement text, and its surviving suffix.
        new_start = min(span.start, estart)
        repl_len = delta + elen
        tail = max(0, span.end - eend)
        return Span(span.name, new_start, (estart - new_start) + repl_len + tail)

    # -- spans --------------------------------------------------------
    def add_span(self, name: str, start: int, length: int) -> Span:
        text = self.text()
        if not (0 <= start <= len(text) and 0 <= length <= len(text) - start):
            raise ValueError("span out of bounds")
        if name in self._spans[self.current]:
            raise ValueError(f"span {name!r} already exists in version {self.current}")
        span = Span(name, start, length)
        self._spans[self.current][name] = span
        return span

    def spans(self, version: Optional[int] = None) -> List[Span]:
        v = self.current if version is None else version
        return [self._spans[v][k] for k in sorted(self._spans[v])]

    def resolve(self, name: str, version: Optional[int] = None) -> str:
        """Return the text covered by a span in a given version."""
        v = self.current if version is None else version
        span = self._spans[v].get(name)
        if span is None:
            raise KeyError(f"no span {name!r} in version {v}")
        text = self.text(v)
        return text[span.start : span.end]


def demo() -> dict:
    """Build a document, span it, edit it, resolve through history."""
    enf = Enfilade("The quick brown fox jumps over the lazy dog.")
    enf.add_span("subject", 4, 15)  # "quick brown fox"
    v1 = enf.edit(4, 15, "slow green turtle", note="swap the subject")
    return {
        "versions": enf.history(),
        "span_now": enf.resolve("subject"),
        "span_v0": enf.resolve("subject", version=0),
        "current_version": v1,
        "spans": [(s.name, s.start, s.length) for s in enf.spans()],
    }
