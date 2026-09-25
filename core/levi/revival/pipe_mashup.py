"""Pipe mashup — Unix pipes for the web, shareable and remixable.

Studied from: honest-markets-20260916, findings.jsonl
[arch-honest-yahoo-pipes] — Yahoo Pipes: a visual data-mashup editor
where modules are dragged, connected, and run; feeds, pages, and services
are remixed with filter rules and published as RSS/JSON/KML.

This module models that pattern as a local DAG of ``Module`` stages:
``Fetch`` (a named in-memory feed), ``Filter`` (predicate rules),
``Sort``, ``Truncate``, and ``Union`` run in topological order over a
``Pipe``; ``run()`` executes it; ``emit_json()``/``emit_rss()`` publish
the result; ``fork()`` clones a pipe so anyone can remix it. Records are
plain dicts; predicates are caller-supplied callables. No network — feeds
are registered locally.

Honesty: the engine is a deterministic DAG evaluator, not a visual
editor and not a web fetcher; "AI" nowhere appears. Filter logic is the
caller's predicate, stated openly.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Callable, Dict, List

ORIGIN = "levi-revival/pipe-mashup"

Record = Dict[str, Any]
Predicate = Callable[[Record], bool]


class Module:
    """One stage of a pipe. Subclasses implement ``process``."""

    name: str = "module"

    def process(
        self, inputs: List[List[Record]], feeds: Dict[str, List[Record]]
    ) -> List[Record]:
        raise NotImplementedError


class Fetch(Module):
    """Pull one registered feed into the pipe."""

    name = "fetch"

    def __init__(self, feed_name: str) -> None:
        if not feed_name:
            raise ValueError("feed_name must not be empty")
        self.feed_name = feed_name

    def process(
        self, inputs: List[List[Record]], feeds: Dict[str, List[Record]]
    ) -> List[Record]:
        if self.feed_name not in feeds:
            raise ValueError(f"unknown feed {self.feed_name!r}")
        return [dict(r) for r in feeds[self.feed_name]]


class Filter(Module):
    """Keep only records matching every predicate rule."""

    name = "filter"

    def __init__(self, *rules: Predicate) -> None:
        if not rules:
            raise ValueError("filter needs at least one rule")
        self.rules = list(rules)

    def process(
        self, inputs: List[List[Record]], feeds: Dict[str, List[Record]]
    ) -> List[Record]:
        rows = [r for stream in inputs for r in stream]
        return [r for r in rows if all(rule(r) for rule in self.rules)]


class Sort(Module):
    """Order records by a key function (ascending by default)."""

    name = "sort"

    def __init__(self, key: Callable[[Record], Any], reverse: bool = False) -> None:
        self.key = key
        self.reverse = reverse

    def process(
        self, inputs: List[List[Record]], feeds: Dict[str, List[Record]]
    ) -> List[Record]:
        rows = [r for stream in inputs for r in stream]
        return sorted(rows, key=self.key, reverse=self.reverse)


class Truncate(Module):
    """Keep at most ``limit`` records (the head)."""

    name = "truncate"

    def __init__(self, limit: int) -> None:
        if limit < 0:
            raise ValueError("limit must be >= 0")
        self.limit = limit

    def process(
        self, inputs: List[List[Record]], feeds: Dict[str, List[Record]]
    ) -> List[Record]:
        rows = [r for stream in inputs for r in stream]
        return rows[: self.limit]


class Union(Module):
    """Merge all input streams into one."""

    name = "union"

    def process(
        self, inputs: List[List[Record]], feeds: Dict[str, List[Record]]
    ) -> List[Record]:
        return [r for stream in inputs for r in stream]


class Pipe:
    """A named DAG of modules: edges map module index -> input indices."""

    def __init__(self, title: str) -> None:
        if not title.strip():
            raise ValueError("pipe title must not be empty")
        self.title = title
        self.modules: List[Module] = []
        self.edges: Dict[int, List[int]] = {}
        self.feeds: Dict[str, List[Record]] = {}

    def register_feed(self, name: str, records: List[Record]) -> None:
        self.feeds[name] = [dict(r) for r in records]

    def add(self, module: Module, inputs: List[int] | None = None) -> int:
        """Append a module; ``inputs`` are indices of upstream modules."""
        idx = len(self.modules)
        for i in inputs or []:
            if not 0 <= i < idx:
                raise ValueError(f"bad input index {i}")
        self.modules.append(module)
        self.edges[idx] = list(inputs or [])
        return idx

    def run(self) -> List[Record]:
        """Execute modules in order; returns the terminal output."""
        if not self.modules:
            raise ValueError("pipe has no modules")
        outputs: Dict[int, List[Record]] = {}
        for idx, module in enumerate(self.modules):
            ins = [outputs[i] for i in self.edges[idx]]
            outputs[idx] = module.process(ins, self.feeds)
        return outputs[len(self.modules) - 1]

    def fork(self, new_title: str) -> "Pipe":
        """Clone the pipe so someone else can remix it."""
        clone = Pipe(new_title)
        clone.feeds = copy.deepcopy(self.feeds)
        clone.modules = copy.deepcopy(self.modules)
        clone.edges = copy.deepcopy(self.edges)
        return clone

    def emit_json(self, records: List[Record]) -> str:
        return json.dumps(
            {"pipe": self.title, "items": records}, indent=2, sort_keys=True
        )

    def emit_rss(
        self,
        records: List[Record],
        title_field: str = "title",
        link_field: str = "link",
    ) -> str:
        items = []
        for record in records:
            title = str(record.get(title_field, ""))
            link = str(record.get(link_field, ""))
            items.append(
                f"<item><title>{_xml(title)}</title><link>{_xml(link)}</link></item>"
            )
        return (
            '<?xml version="1.0"?>'
            f'<rss version="2.0"><channel><title>{_xml(self.title)}'
            "</title>" + "".join(items) + "</channel></rss>"
        )


def _xml(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
