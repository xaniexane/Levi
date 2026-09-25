"""auto_hypertext — every known name becomes a cross-reference.

Studied from: dead-networks-20260916/report.md (Delphi: automatic
hypertext — in the Kussmaul Encyclopedia (1981) every word matching
an entry name became a clickable cross-reference link; Delphi's
gateway pivot to real internet access).

The load-bearing idea: maintain a named lexicon; scan ordinary text;
turn every occurrence of a known entry name into a link into that
entry. No author markup — the references are *discovered* by matching
what the corpus already knows.

LEVI's take: ``HypertextIndex`` holds entries (name, summary,
optional aliases). ``link(text)`` finds all non-overlapping matches,
longest-name-first so "Great Library" wins over "Library", and
returns ``Link`` records (span, entry, summary). ``render(text)``
returns the text with links marked up. This is an original,
from-scratch implementation for LEVI.

Kept distinct from ``levi.revival.sparksense`` (care note in the
wave plan): sparksense *detects* ambient entities (dates, money,
addresses) and describes actions for them; this module *links*
against an explicit lexicon the caller supplied. Detection vs.
cross-referencing — different jobs.

Honest limits: matching is literal and case-insensitive, at word
boundaries; there is no stemming and no disambiguation — if a name
appears, it links, even in a metaphorical sense. Aliases are explicit
per entry. Overlapping names resolve to the longest match.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

ORIGIN = "levi-revival/auto-hypertext"


@dataclass(frozen=True)
class Entry:
    """One known thing that can be linked to."""

    name: str
    summary: str
    aliases: tuple = ()


@dataclass(frozen=True)
class Link:
    """One discovered cross-reference."""

    entry: str  # canonical entry name
    span: tuple  # (start, end) offsets into the source text
    matched: str  # the exact substring that matched
    summary: str


class HypertextIndex:
    """A lexicon that turns its own names into links in any text."""

    def __init__(self) -> None:
        self._entries: Dict[str, Entry] = {}  # keyed by lowercased name
        self._pattern: Optional[re.Pattern] = None
        self._alias_of: Dict[str, str] = {}  # lowercased alias -> canonical key

    # -- lexicon ------------------------------------------------------
    def add(self, name: str, summary: str, aliases: tuple = ()) -> None:
        name = name.strip()
        if not name:
            raise ValueError("entry name must be non-empty")
        key = name.lower()
        if key in self._entries:
            raise ValueError(f"entry {name!r} already indexed")
        entry = Entry(name=name, summary=summary, aliases=tuple(aliases))
        self._entries[key] = entry
        for alias in aliases:
            akey = alias.strip().lower()
            if not akey:
                continue
            if akey in self._entries or akey in self._alias_of:
                raise ValueError(f"alias {alias!r} collides with an existing name")
            self._alias_of[akey] = key
        self._pattern = None  # invalidate the compiled matcher

    def remove(self, name: str) -> bool:
        key = name.strip().lower()
        entry = self._entries.pop(key, None)
        if entry is None:
            return False
        for alias in entry.aliases:
            self._alias_of.pop(alias.strip().lower(), None)
        self._pattern = None
        return True

    def entry_names(self) -> List[str]:
        return [self._entries[k].name for k in sorted(self._entries)]

    # -- linking ------------------------------------------------------
    def _matcher(self) -> Optional[re.Pattern]:
        if self._pattern is not None:
            return self._pattern
        names = list(self._entries) + list(self._alias_of)
        if not names:
            return None
        # longest first so multi-word names beat their substrings
        names.sort(key=len, reverse=True)
        alt = "|".join(re.escape(n) for n in names)
        self._pattern = re.compile(rf"(?<!\w)(?:{alt})(?!\w)", re.IGNORECASE)
        return self._pattern

    def link(self, text: str) -> List[Link]:
        """Find all non-overlapping lexicon matches in ``text``."""
        matcher = self._matcher()
        if matcher is None:
            return []
        links: List[Link] = []
        for match in matcher.finditer(text):
            key = match.group(0).lower()
            canonical = self._alias_of.get(key, key)
            entry = self._entries[canonical]
            links.append(
                Link(
                    entry=entry.name,
                    span=(match.start(), match.end()),
                    matched=match.group(0),
                    summary=entry.summary,
                )
            )
        return links

    def render(self, text: str, fmt: str = "[{name}]({summary})") -> str:
        """Return ``text`` with each link replaced by ``fmt``.

        ``fmt`` may reference ``{name}``, ``{summary}`` and
        ``{matched}``. Non-link text is passed through untouched.
        """
        links = self.link(text)
        parts: List[str] = []
        cursor = 0
        for link in links:
            start, end = link.span
            parts.append(text[cursor:start])
            parts.append(
                fmt.format(name=link.entry, summary=link.summary, matched=link.matched)
            )
            cursor = end
        parts.append(text[cursor:])
        return "".join(parts)


def demo() -> dict:
    """Index three entries and link a paragraph."""
    index = HypertextIndex()
    index.add(
        "Great Library", "the archive of all known works", aliases=("the Library",)
    )
    index.add("Kussmaul", "encyclopedia of automatic hypertext")
    index.add("Delphi", "the gateway that pivoted to the internet")
    text = "The Great Library cites Kussmaul, and the Library echoes Delphi."
    links = index.link(text)
    return {
        "entries": index.entry_names(),
        "links": [
            {"entry": link.entry, "matched": link.matched, "span": link.span}
            for link in links
        ],
        "rendered": index.render(text),
    }
