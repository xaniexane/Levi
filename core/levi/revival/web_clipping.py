"""Server-side content extraction for thin links: web clipping and micro-apps.

Studied from: dead-networks-20260916/report.md [Palm.net]

The studied shape: over an 8-kbps link, nobody shipped whole web
pages. A server-side clipper stripped a page to its essential data —
title, the facts, the one paragraph that mattered — and tiny
single-purpose micro-apps ("PQAs") were built from plain HTML around
that clipped data. The heavy page never crossed the wire.

LEVI-native re-expression: an honest extraction pipeline. The
**clipper** takes page text (HTML-ish markup or plain text) and
produces a **Clipping**: title, summary, and key facts, using
transparently labeled heuristics. A **MicroApp** spec declares a
single-purpose app (name + field extractors); ``build`` runs it
against a page to yield a data card small enough for a thin link.

Operations:

* ``clip(page_text)`` → ``Clipping(title, summary, facts, bytes_in,
  bytes_out)``
* ``MicroApp(name, fields)`` — each field is ``(label, pattern)``;
  ``build(page_text)`` → ``{"app": name, "data": {...}, "bytes": n}``
* ``compression`` on the clipping — honest in/out byte ratio

Honest limits: the extraction heuristics are deliberately simple —
first ``<title>``/``<h1>`` wins, sentences are split on punctuation,
"facts" are lines with numbers or colon-pairs. This is triage, not
understanding; on weird markup it degrades gracefully to the first
readable sentences. No network: pages are handed in as text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

ORIGIN = "levi-revival/web-clipping"

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_SENT = re.compile(r"(?<=[.!?])\s+")
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
_HEADING = re.compile(r"<h[1-6][^>]*>(.*?)</h[1-6]>", re.IGNORECASE | re.DOTALL)
# Heuristic "fact" lines: contain a number, or look like "Label: value".
_FACT = re.compile(r"(?m)^[ \t]*[^\n]*(\d[^\n]*|:)[ \t]*[^\n]*$")


def _clean(html: str) -> str:
    text = _TAG.sub(" ", html)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    return _WS.sub(" ", text).strip()


@dataclass
class Clipping:
    title: str
    summary: str
    facts: List[str]
    bytes_in: int
    bytes_out: int

    @property
    def ratio(self) -> float:
        """Honest out/in byte ratio (lower = more was stripped)."""
        if self.bytes_in == 0:
            return 0.0
        return self.bytes_out / self.bytes_in


def clip(
    page_text: str, max_summary_sentences: int = 3, max_facts: int = 8
) -> Clipping:
    """Strip a page to its essential data.

    Heuristics (labeled as such): title = first ``<title>`` else first
    ``<h1>`` else first 60 chars of body; summary = first N sentences
    of body text longer than 20 chars; facts = up to M lines matching
    the number/colon heuristic.
    """
    m = _TITLE.search(page_text)
    title = _clean(m.group(1)) if m else ""
    if not title:
        m1 = _H1.search(page_text)
        title = _clean(m1.group(1)) if m1 else ""
    body = _clean(_HEADING.sub(" ", page_text))
    if not title:
        title = body[:60].rstrip()
    sentences = [s.strip() for s in _SENT.split(body) if len(s.strip()) > 20]
    summary = " ".join(sentences[:max_summary_sentences])
    facts: List[str] = []
    for m in _FACT.finditer(page_text):
        f = _clean(m.group(0)).strip()
        if f and f not in facts:
            facts.append(f)
        if len(facts) >= max_facts:
            break
    out_text = f"{title}\n{summary}\n" + "\n".join(facts)
    return Clipping(
        title=title,
        summary=summary,
        facts=facts,
        bytes_in=len(page_text.encode("utf-8")),
        bytes_out=len(out_text.encode("utf-8")),
    )


@dataclass
class MicroApp:
    """A single-purpose micro-app spec: name + regex field extractors."""

    name: str
    fields: List[Tuple[str, str]] = field(default_factory=list)  # (label, regex)

    def add_field(self, label: str, pattern: str) -> "MicroApp":
        self.fields.append((label, pattern))
        return self

    def build(self, page_text: str) -> Dict[str, object]:
        """Run the app against a page → a small data card."""
        data: Dict[str, str] = {}
        for label, pattern in self.fields:
            m = re.search(pattern, page_text, re.IGNORECASE | re.DOTALL)
            data[label] = (
                _clean(m.group(1) if m.groups() else m.group(0)).strip() if m else ""
            )
        card = {"app": self.name, "data": data}
        import json as _json

        card["bytes"] = len(_json.dumps(card).encode("utf-8"))
        return card
