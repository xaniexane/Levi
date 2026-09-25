"""LEVI's passage workbench: non-programmer interactive-fiction authoring.

Studied from: games-hunt-20260916-0022/report.md [Find 1 — Interactive fiction].

The shape being studied: Twine democratized IF authoring by making the
*passage* the unit of thought. A story is a graph of passages; each
passage is prose with ``[[links]]`` to other passages. No parser, no code
— an author who can write a paragraph and draw an arrow can ship a game.

``twine_authoring`` rebuilds that shape from scratch, LEVI-native:

- ``Passage`` — a named unit: body prose carrying ``[[label|target]]``
  (or bare ``[[target]]``) links, plus simple ``(set: $var to value)``
  directives for state.
- ``Story`` — the graph: add passages, parse links, and ``validate()``
  it like an editor would — orphans nobody links to, dead ends with no
  way forward, links pointing at passages that don't exist.
- ``Session`` — playtest the story: render the current passage (markup
  stripped, choices listed), ``choose(i)`` to follow a link, variables
  carried in ``state``.

Honest limits: the directive dialect is deliberately tiny — ``set`` only,
values are ints, quoted strings, or true/false. There are no
conditionals, no macros, no expression language. Validation is
structural, not semantic: it can't tell you a story is *good*.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


ORIGIN = "levi-revival/twine-authoring"


class TwineError(Exception):
    """Base class for authoring failures."""


class DuplicatePassage(TwineError):
    """A passage with that name already exists."""


class UnknownPassage(TwineError):
    """No passage with that name exists."""


class BadChoice(TwineError):
    """The choice index doesn't match any link."""


LINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|([^\]]+?))?\]\]")
SET_RE = re.compile(r"\(set:\s*\$([A-Za-z_]\w*)\s+to\s+([^)]+)\)")


def _parse_value(raw: str):
    raw = raw.strip()
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        return raw[1:-1]
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw  # bare word stays a string — honest, not clever


@dataclass
class Passage:
    """One node of the story: prose, links, and set-directives."""

    name: str
    body: str

    def links(self) -> List[Tuple[str, str]]:
        """(label, target) pairs in order of appearance."""
        out = []
        for m in LINK_RE.finditer(self.body):
            label = m.group(1).strip()
            target = (m.group(2) or m.group(1)).strip()
            out.append((label, target))
        return out

    def directives(self) -> List[Tuple[str, object]]:
        """(variable, value) pairs from ``(set: $var to value)`` lines."""
        return [
            (m.group(1), _parse_value(m.group(2))) for m in SET_RE.finditer(self.body)
        ]

    def text(self) -> str:
        """Body with markup stripped for reading."""
        clean = LINK_RE.sub(lambda m: m.group(1).strip(), self.body)
        clean = SET_RE.sub("", clean)
        return "\n".join(
            line for line in (ln.rstrip() for ln in clean.splitlines()) if line
        ).strip()


@dataclass
class ValidationReport:
    orphans: List[str]  # unreachable from the start passage
    dead_ends: List[str]  # passages with no outgoing links
    broken_links: List[Tuple[str, str, str]]  # (passage, label, missing target)

    @property
    def ok(self) -> bool:
        return not (self.orphans or self.broken_links)

    def describe(self) -> str:
        if self.ok and not self.dead_ends:
            return "Story validates clean."
        parts = []
        for src, label, target in self.broken_links:
            parts.append(f"broken link in {src!r}: [[{label}]] -> missing {target!r}")
        for name in self.orphans:
            parts.append(f"orphan passage {name!r}: nothing links to it")
        for name in self.dead_ends:
            parts.append(f"dead end {name!r}: no outgoing links")
        return "\n".join(parts)


class Story:
    """The passage graph."""

    def __init__(self, title: str = "untitled", start: str = "start"):
        self.title = title
        self.start = start
        self.passages: Dict[str, Passage] = {}

    def add_passage(self, name: str, body: str) -> Passage:
        if name in self.passages:
            raise DuplicatePassage(f"passage {name!r} already exists")
        p = Passage(name=name, body=body)
        self.passages[name] = p
        return p

    def get(self, name: str) -> Passage:
        try:
            return self.passages[name]
        except KeyError:
            raise UnknownPassage(f"no passage named {name!r}") from None

    def validate(self) -> ValidationReport:
        broken = []
        for p in self.passages.values():
            for label, target in p.links():
                if target not in self.passages:
                    broken.append((p.name, label, target))
        # Reachability from the start passage (broken links don't count as edges).
        reachable = set()
        if self.start in self.passages:
            frontier = [self.start]
            while frontier:
                name = frontier.pop()
                if name in reachable:
                    continue
                reachable.add(name)
                frontier.extend(
                    t for _, t in self.passages[name].links() if t in self.passages
                )
        orphans = sorted(
            n for n in self.passages if n not in reachable and n != self.start
        )
        dead_ends = sorted(n for n, p in self.passages.items() if not p.links())
        return ValidationReport(
            orphans=orphans, dead_ends=dead_ends, broken_links=broken
        )

    def link_map(self) -> Dict[str, List[str]]:
        return {n: [t for _, t in p.links()] for n, p in self.passages.items()}


class Session:
    """A playtest walk through a story, carrying variable state."""

    def __init__(self, story: Story, start: Optional[str] = None):
        self.story = story
        self.current = start or story.start
        if self.current not in story.passages:
            raise UnknownPassage(f"start passage {self.current!r} not in story")
        self.state: Dict[str, object] = {}
        self.visits: List[str] = []
        self._enter(self.current)

    def _enter(self, name: str) -> None:
        self.current = name
        self.visits.append(name)
        for var, value in self.story.get(name).directives():
            self.state[var] = value

    def passage(self) -> Passage:
        return self.story.get(self.current)

    def render(self) -> Tuple[str, List[str]]:
        """(readable text, choice labels) for the current passage."""
        p = self.passage()
        return p.text(), [label for label, _ in p.links()]

    def choose(self, index: int) -> Tuple[str, List[str]]:
        links = self.passage().links()
        if not 0 <= index < len(links):
            raise BadChoice(f"choice {index} out of range (0..{len(links) - 1})")
        _, target = links[index]
        if target not in self.story.passages:
            raise UnknownPassage(
                f"link from {self.current!r} points at missing passage {target!r}"
            )
        self._enter(target)
        return self.render()
