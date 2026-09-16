"""Local inverted index, JSON-persisted under ~/.levi/honestsearch.

Tokenization is deliberately boring and documented: lowercase,
alphanumeric runs of length >= 2, a small fixed English stopword list
(shown in the docs). No stemming, no embeddings, no magic — the ranking
math in rank.py is fully inspectable from these postings.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List

from levi.honestsearch.model import Document

TOKEN_RE = re.compile(r"[a-z0-9]{2,}")

# Fixed, documented, inspectable. Not tuned per user, not learned.
STOPWORDS = frozenset(
    "a an and are as at be but by for from has have he her his in into is it "
    "its of on or that the their them they this to was were will with you your"
    .split()
)


def tokenize(text: str) -> List[str]:
    """Lowercase alphanumeric tokens, stopwords removed."""
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOPWORDS]


class InvertedIndex:
    """doc_id -> Document plus term -> {doc_id: tf} postings."""

    def __init__(self) -> None:
        self.docs: Dict[str, Document] = {}
        self.postings: Dict[str, Dict[str, int]] = {}
        self._by_url: Dict[str, str] = {}  # url -> doc_id

    # -- mutation ----------------------------------------------------------
    def add(self, doc: Document) -> None:
        # Re-adding a URL replaces the old document: wipe its postings
        # first so stale terms can never linger in the index.
        old_id = self._by_url.get(doc.url)
        if old_id is not None:
            self.remove(old_id)
        self.docs[doc.doc_id] = doc
        self._by_url[doc.url] = doc.doc_id
        counts = Counter(tokenize(doc.title + "\n" + doc.text))
        for term, tf in counts.items():
            self.postings.setdefault(term, {})[doc.doc_id] = tf

    def remove(self, doc_id: str) -> bool:
        doc = self.docs.pop(doc_id, None)
        if doc is None:
            return False
        self._by_url.pop(doc.url, None)
        for term in list(self.postings):
            post = self.postings[term]
            post.pop(doc_id, None)
            if not post:
                del self.postings[term]
        return True

    # -- reads ---------------------------------------------------------------
    def __len__(self) -> int:
        return len(self.docs)

    def doc_freq(self, term: str) -> int:
        return len(self.postings.get(term, {}))

    def urls(self) -> List[str]:
        return sorted(self._by_url)

    def stats(self) -> Dict:
        return {
            "documents": len(self.docs),
            "terms": len(self.postings),
            "sources": Counter(d.source for d in self.docs.values()),
        }

    # -- persistence -----------------------------------------------------------
    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"documents": [d.to_dict() for d in self.docs.values()]}
        path.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "InvertedIndex":
        index = cls()
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            return index
        try:
            payload = json.loads(raw)
        except ValueError:
            return index
        for item in payload.get("documents", []):
            try:
                index.add(Document.from_dict(item))
            except (KeyError, TypeError):
                continue
        return index
