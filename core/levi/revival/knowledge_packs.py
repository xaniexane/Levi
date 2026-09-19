"""Scoped knowledge packs — folder-plus-instructions persistent context.

Studied from: giant-patterns-hunt-20260916-0016/report.md [Additions 16].

The mechanism under study: a knowledge pack couples a folder of user-owned
documents with a standing instruction block, forming persistent context
that can be attached to work sessions. This is an original, from-scratch
implementation for LEVI. Packs are composed the way LEVI's Newton soups
are — blended reference material under one instruction header — but the
retrieval here is deliberately simple and honest: case-insensitive keyword
scoring over the documents the user explicitly put in the folder. No
embeddings, no vector store, no remote index.

Public surface:
- ``KnowledgePack``: name, instructions, docs; add_doc / remove_doc /
  rename / set_instructions.
- ``PackStore``: create/get/delete/list packs; ``search(pack, query)``
  returning scored hits; ``render_context(pack, query, max_chars)``
  composing instructions + top matching snippets; ``from_directory``
  to build a pack from a local folder of text files.

stdlib-only. No network. Everything reads from caller-supplied text or
files the caller points at.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

ORIGIN = "levi-revival/knowledge-packs"

_WORD = re.compile(r"[a-z0-9']+")


@dataclass
class Doc:
    name: str
    text: str


@dataclass
class Hit:
    doc_name: str
    score: float
    snippet: str


def _tokens(text: str) -> List[str]:
    return _WORD.findall(text.lower())


def _score(query_terms: List[str], doc_terms: List[str]) -> float:
    """Honest keyword score: sum of term-frequency weights, title-boosted."""
    counts: Dict[str, int] = {}
    for t in doc_terms:
        counts[t] = counts.get(t, 0) + 1
    return sum(counts.get(t, 0) for t in query_terms)


def _snippet(text: str, query_terms: List[str], width: int = 160) -> str:
    lowered = text.lower()
    best = -1
    for term in query_terms:
        idx = lowered.find(term)
        if idx != -1 and (best == -1 or idx < best):
            best = idx
    if best == -1:
        return text[:width].strip()
    start = max(0, best - width // 2)
    window = text[start : start + width].strip()
    prefix = "..." if start > 0 else ""
    suffix = "..." if start + width < len(text) else ""
    return f"{prefix}{window}{suffix}"


class KnowledgePack:
    """One user-owned pack: instructions plus a named document folder."""

    def __init__(self, name: str, instructions: str = "") -> None:
        if not name:
            raise ValueError("pack name must not be empty")
        self.name = name
        self.instructions = instructions
        self.docs: Dict[str, Doc] = {}

    def set_instructions(self, instructions: str) -> None:
        self.instructions = instructions

    def add_doc(self, name: str, text: str) -> Doc:
        if not name:
            raise ValueError("doc name must not be empty")
        doc = Doc(name, text)
        self.docs[name] = doc
        return doc

    def remove_doc(self, name: str) -> bool:
        return self.docs.pop(name, None) is not None

    def list_docs(self) -> List[str]:
        return sorted(self.docs)

    def doc_count(self) -> int:
        return len(self.docs)

    def char_count(self) -> int:
        return sum(len(d.text) for d in self.docs.values())


class PackStore:
    """Owns packs; searches and composes context from them."""

    def __init__(self) -> None:
        self._packs: Dict[str, KnowledgePack] = {}

    def create_pack(self, name: str, instructions: str = "") -> KnowledgePack:
        if name in self._packs:
            raise ValueError(f"pack {name!r} already exists")
        pack = KnowledgePack(name, instructions)
        self._packs[name] = pack
        return pack

    def get_pack(self, name: str) -> KnowledgePack:
        try:
            return self._packs[name]
        except KeyError:
            raise ValueError(f"no pack named {name!r}") from None

    def delete_pack(self, name: str) -> bool:
        return self._packs.pop(name, None) is not None

    def list_packs(self) -> List[str]:
        return sorted(self._packs)

    def from_directory(
        self,
        pack_name: str,
        directory: str,
        instructions: str = "",
        suffixes: Tuple[str, ...] = (".txt", ".md"),
    ) -> KnowledgePack:
        """Build a pack from the text files in a local directory (not recursive)."""
        pack = self.create_pack(pack_name, instructions)
        for fname in sorted(os.listdir(directory)):
            if not fname.lower().endswith(suffixes):
                continue
            path = os.path.join(directory, fname)
            if not os.path.isfile(path):
                continue
            with open(path, encoding="utf-8", errors="replace") as fh:
                pack.add_doc(fname, fh.read())
        return pack

    def search(self, pack_name: str, query: str, top_n: int = 5) -> List[Hit]:
        pack = self.get_pack(pack_name)
        terms = [t for t in _tokens(query) if len(t) > 1]
        if not terms:
            return []
        hits: List[Hit] = []
        for doc in pack.docs.values():
            score = _score(terms, _tokens(doc.text + " " + doc.name))
            # Title matches count double.
            score += _score(terms, _tokens(doc.name))
            if score > 0:
                hits.append(Hit(doc.name, score, _snippet(doc.text, terms)))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_n]

    def render_context(
        self, pack_name: str, query: str, max_chars: int = 4000, top_n: int = 3
    ) -> str:
        """Compose instructions + top matching snippets, budget-capped."""
        pack = self.get_pack(pack_name)
        parts = [f"# Pack: {pack.name}"]
        if pack.instructions:
            parts.append(f"## Instructions\n{pack.instructions}")
        budget = max_chars - sum(len(p) for p in parts)
        parts.append("## Retrieved context")
        for hit in self.search(pack_name, query, top_n=top_n):
            block = f"### {hit.doc_name}\n{hit.snippet}\n"
            if len(block) > budget:
                block = block[: max(0, budget)]
            parts.append(block)
            budget -= len(block)
            if budget <= 0:
                break
        return "\n".join(parts)
