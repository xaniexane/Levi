"""page_memory — agent memory framed as an operating system's virtual memory.

Studied from: ai-si-software-internals-20260916-0005/report.md (Part 2) [S2.7].

The studied shape: the agent's context is *main memory* (small, fast,
expensive), archival storage is *disk*, and recall memory is an index —
and the agent itself issues the page-in / page-out calls, like a process
managing its own address space. LEVI's version:

* **Three tiers.** ``MainMemory`` (token-budgeted working set),
  ``Archive`` (unbounded page store), and ``RecallIndex`` (keyword
  lookup over pages). A ``Page`` is one chunk of remembered text with
  an id, a token estimate, and tags.
* **Agent-issued paging.** ``page_in(page_id)`` and ``page_out(page_id)``
  are explicit calls — the agent decides what stays resident. Paging a
  page in over budget triggers LRU eviction of resident pages (their
  content is never lost: eviction just means "not resident").
* **Page faults.** Every ``read`` of a non-resident page counts a fault
  and auto-pages it in — the honest cost of forgetting what's loaded.
* **Recall.** ``recall(query)`` searches the archive (resident or not)
  and returns matching page ids ranked by term overlap, so the agent
  can find what to page in next.

Honest limits: token estimates are word-count heuristics, not a real
tokenizer; the recall index is substring/term overlap, not embeddings;
eviction is plain LRU. This is a memory-management discipline for agent
loops, not a database.

This is an original, from-scratch implementation for LEVI. Not
artificial. Synthetic.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

ORIGIN = "levi-revival/page_memory"


def estimate_tokens(text: str) -> int:
    """Heuristic token estimate: ~4 chars per token, minimum 1."""
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Pages and the archive
# ---------------------------------------------------------------------------


@dataclass
class Page:
    """One chunk of remembered text."""

    page_id: str
    text: str
    tags: Tuple[str, ...] = ()
    pinned: bool = False  # pinned pages are never evicted

    @property
    def tokens(self) -> int:
        return estimate_tokens(self.text)


class Archive:
    """The disk tier: unbounded, durable page store."""

    def __init__(self) -> None:
        self.pages: Dict[str, Page] = {}

    def store(self, page: Page) -> None:
        self.pages[page.page_id] = page

    def fetch(self, page_id: str) -> Page:
        try:
            return self.pages[page_id]
        except KeyError:
            raise KeyError(f"no page {page_id!r} in archive") from None

    def drop(self, page_id: str) -> None:
        self.pages.pop(page_id, None)

    def __len__(self) -> int:
        return len(self.pages)


# ---------------------------------------------------------------------------
# Main memory: the resident working set
# ---------------------------------------------------------------------------


class MainMemory:
    """The RAM tier: token-budgeted, LRU-ordered resident set.

    The *agent* calls page_in/page_out explicitly; reads of non-resident
    pages fault (counted) and page the page in automatically.
    """

    def __init__(self, archive: Archive, token_budget: int) -> None:
        self.archive = archive
        self.token_budget = token_budget
        self.resident: "OrderedDict[str, Page]" = OrderedDict()
        self.tokens_used = 0
        self.faults = 0
        self.evictions = 0

    def is_resident(self, page_id: str) -> bool:
        return page_id in self.resident

    def _touch(self, page_id: str) -> None:
        self.resident.move_to_end(page_id)

    def _evict_lru(self, need: int) -> List[str]:
        """Evict least-recently-used unpinned pages until ``need`` fits."""
        evicted = []
        for pid in list(self.resident):
            if self.tokens_used + need <= self.token_budget:
                break
            page = self.resident[pid]
            if page.pinned:
                continue
            self.resident.pop(pid)
            self.tokens_used -= page.tokens
            self.evictions += 1
            evicted.append(pid)
        if self.tokens_used + need > self.token_budget:
            raise MemoryError(
                f"page needs {need} tokens; budget {self.token_budget} "
                f"has {self.tokens_used} used (pinned pages block eviction)"
            )
        return evicted

    def page_in(self, page_id: str) -> Page:
        """Agent-issued: bring a page resident (LRU-evicts as needed)."""
        if page_id in self.resident:
            self._touch(page_id)
            return self.resident[page_id]
        page = self.archive.fetch(page_id)
        self._evict_lru(page.tokens)
        self.resident[page_id] = page
        self.tokens_used += page.tokens
        return page

    def page_out(self, page_id: str) -> bool:
        """Agent-issued: drop a page from the working set (archive keeps it)."""
        page = self.resident.pop(page_id, None)
        if page is None:
            return False
        self.tokens_used -= page.tokens
        return True

    def read(self, page_id: str) -> str:
        """Read a page; faults (and auto-pages-in) if not resident."""
        if page_id not in self.resident:
            self.faults += 1
            self.page_in(page_id)
        else:
            self._touch(page_id)
        return self.resident[page_id].text

    def pin(self, page_id: str) -> None:
        self.page_in(page_id).pinned = True

    def unpin(self, page_id: str) -> None:
        if page_id in self.resident:
            self.resident[page_id].pinned = False

    def resident_ids(self) -> List[str]:
        return list(self.resident)

    def pressure(self) -> float:
        """Fraction of the token budget currently used."""
        return self.tokens_used / self.token_budget if self.token_budget else 0.0


# ---------------------------------------------------------------------------
# Recall: the index tier
# ---------------------------------------------------------------------------


class RecallIndex:
    """Keyword recall over the archive: find what to page in next."""

    def __init__(self, archive: Archive) -> None:
        self.archive = archive

    @staticmethod
    def _terms(text: str) -> Set[str]:
        return {t.strip(".,!?;:\"'()").lower() for t in text.split() if t.strip()}

    def recall(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """Rank pages by query-term overlap; returns (page_id, score)."""
        qterms = self._terms(query)
        scored = []
        for pid, page in self.archive.pages.items():
            pterms = self._terms(page.text) | {t.lower() for t in page.tags}
            overlap = qterms & pterms
            if overlap:
                scored.append((pid, len(overlap) / max(1, len(qterms))))
        scored.sort(key=lambda r: (-r[1], r[0]))
        return scored[:top_k]


# ---------------------------------------------------------------------------
# One convenient bundle
# ---------------------------------------------------------------------------


@dataclass
class MemoryOS:
    """Archive + main memory + recall wired together."""

    token_budget: int = 2000
    archive: Archive = field(default_factory=Archive)
    main: Optional[MainMemory] = None
    recall: Optional[RecallIndex] = None

    def __post_init__(self) -> None:
        self.main = MainMemory(self.archive, self.token_budget)
        self.recall = RecallIndex(self.archive)

    def remember(
        self,
        page_id: str,
        text: str,
        tags: Tuple[str, ...] = (),
        resident: bool = False,
    ) -> Page:
        page = Page(page_id, text, tags)
        self.archive.store(page)
        if resident:
            assert self.main is not None
            self.main.page_in(page_id)
        return page

    def stats(self) -> Dict[str, int]:
        assert self.main is not None
        return {
            "archived_pages": len(self.archive),
            "resident_pages": len(self.main.resident),
            "tokens_used": self.main.tokens_used,
            "token_budget": self.main.token_budget,
            "page_faults": self.main.faults,
            "evictions": self.main.evictions,
        }
