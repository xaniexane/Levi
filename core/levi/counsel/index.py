"""Local inverted index + clause retrieval for the counsel vault.

Stdlib-only, JSON on local disk, no embeddings, no network — deterministic
retrieval: the same corpus and the same query always return the same hits
in the same order.

Every hit carries a quoted span: the exact source text around the match,
plus the document id. Stage 2 (clause extraction) will build obligation
tables on top of these spans; Stage 1's contract is simpler — no result
without a quote.

The not-legal-advice draft notice is attached to every search result via
``notices.NOTICE_STATUS`` so retrieval can never be separated from the
disclaimer about what it is.
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from levi.counsel.notices import NOTICE_STATUS
from levi.counsel.vault import FILE_MODE, CounselVault, _locked_open

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
_SNIPPET_RADIUS = 120
_MIN_TOKEN_LEN = 2

STOPWORDS = frozenset(
    """
    a an the and or but if then else when where which who whom whose what
    that this these those is are was were be been being have has had do does
    did will would shall should may might must can could of to in on for
    with by as at from into out over under again further once here there
    all any both each few more most other some such no nor not only own
    same so than too very its it he she we they you i me my our your his
    her their them us him
    """.split()
)


@dataclass
class Hit:
    doc_id: str
    source_name: str
    score: float
    snippet: str  # quoted verbatim span from the source text
    matched_terms: List[str] = field(default_factory=list)
    notice_status: str = NOTICE_STATUS


def tokenize(text: str) -> List[str]:
    tokens = _TOKEN_RE.findall(text.lower())
    return [t for t in tokens if len(t) >= _MIN_TOKEN_LEN and t not in STOPWORDS]


class CounselIndex:
    """Inverted index stored as local JSON next to the vault."""

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = Path(root) if root is not None else CounselVault().root
        self.path = self.root / "index.json"
        self._docs: Dict[str, Dict] = {}
        self._postings: Dict[str, Dict[str, List[int]]] = {}
        self._load()

    # -- persistence -------------------------------------------------

    def _load(self) -> None:
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._docs = data.get("docs", {})
            self._postings = data.get("postings", {})

    def _save(self) -> None:
        with _locked_open():
            self.path.write_text(
                json.dumps(
                    {"version": 1, "docs": self._docs, "postings": self._postings},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            os.chmod(self.path, FILE_MODE)

    # -- indexing ----------------------------------------------------

    def add(self, doc_id: str, source_name: str, text: str) -> None:
        """Index an accepted document's extracted text. Idempotent: re-adding
        the same doc_id replaces its entry."""
        self.remove(doc_id)
        tokens = tokenize(text)
        positions: Dict[str, List[int]] = {}
        for i, tok in enumerate(tokens):
            positions.setdefault(tok, []).append(i)
        for tok, pos_list in positions.items():
            self._postings.setdefault(tok, {})[doc_id] = pos_list
        self._docs[doc_id] = {
            "source_name": source_name,
            "token_count": len(tokens),
            "char_count": len(text),
        }
        self._save()

    def remove(self, doc_id: str) -> None:
        self._docs.pop(doc_id, None)
        for tok in list(self._postings):
            self._postings[tok].pop(doc_id, None)
            if not self._postings[tok]:
                del self._postings[tok]

    def doc_count(self) -> int:
        return len(self._docs)

    # -- retrieval ---------------------------------------------------

    def _snippet(self, text: str, query_terms: List[str]) -> str:
        lowered = text.lower()
        best = -1
        for term in query_terms:
            idx = lowered.find(term)
            if idx != -1 and (best == -1 or idx < best):
                best = idx
        if best == -1:
            start, end = 0, min(len(text), 2 * _SNIPPET_RADIUS)
        else:
            start = max(0, best - _SNIPPET_RADIUS)
            end = min(len(text), best + _SNIPPET_RADIUS)
            # snap to word boundaries so the quote is readable
            while start > 0 and not text[start].isspace():
                start -= 1
            while end < len(text) and not text[end].isspace():
                end += 1
        span = text[start:end].strip()
        prefix = "\u2026" if start > 0 else ""
        suffix = "\u2026" if end < len(text) else ""
        return f'"{prefix}{span}{suffix}"'

    def search(
        self,
        query: str,
        vault: CounselVault,
        limit: int = 10,
    ) -> List[Hit]:
        """Retrieve documents matching the query. Returns hits ordered by
        score, each with a quoted source span. Quarantined documents are
        never indexed and therefore never returned."""
        terms = tokenize(query)
        if not terms:
            return []
        scores: Dict[str, float] = {}
        matched: Dict[str, List[str]] = {}
        doc_freq = {t: len(self._postings.get(t, {})) for t in terms}
        n_docs = max(1, len(self._docs))
        for term in terms:
            postings = self._postings.get(term, {})
            idf = math.log(1 + n_docs / (1 + doc_freq[term]))
            for doc_id, positions in postings.items():
                tf = len(positions)
                scores[doc_id] = scores.get(doc_id, 0.0) + tf * idf
                matched.setdefault(doc_id, []).append(term)
        # phrase bonus: all query terms present in the document
        for doc_id in list(scores):
            if all(t in self._postings and doc_id in self._postings[t] for t in terms):
                scores[doc_id] *= 1.5
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        hits: List[Hit] = []
        for doc_id, score in ranked[:limit]:
            text = vault.stored_text(doc_id)
            if text is None:
                continue  # not retrievable as text (e.g. removed)
            meta = self._docs.get(doc_id, {})
            hits.append(
                Hit(
                    doc_id=doc_id,
                    source_name=meta.get("source_name", doc_id),
                    score=round(score, 4),
                    snippet=self._snippet(text, terms),
                    matched_terms=sorted(set(matched.get(doc_id, []))),
                )
            )
        return hits
