"""Parallel production by chunking — one exemplar, many copyists.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #29).

The mechanism under study: an approved master text (the **exemplar**)
is divided into standardized chunk units (**peciae**); a **stationer**
hands them out *one pecia at a time* — the concurrency control — to
workers who copy concurrently; each returned copy is **verified against
the exemplar** before the book is reassembled in order. The exemplar is
the quality control; the stationer's rental discipline is the
throughput control.

This is an original, from-scratch implementation for LEVI. ``Exemplar``
locks the master text and splits it into numbered peciae. ``Stationer``
tracks which pecia each worker holds (one at a time), verifies every
check-in against the exemplar chunk exactly, returns rejected copies
to the pool for re-copying, and reassembles the verified chunks in
order — naming any missing chunks if the book is incomplete.

Public surface:
- ``Exemplar``: ``from_text``, ``pecia(index)``.
- ``PeciaStatus``: AVAILABLE, CHECKED_OUT, VERIFIED, REJECTED.
- ``Stationer``: ``checkout``, ``checkin``, ``reassemble``,
  ``progress``.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List

ORIGIN = "levi-revival/pecia"


class PeciaError(Exception):
    """The stationer's discipline refused: double checkout, bad worker, gap."""


class PeciaStatus(Enum):
    AVAILABLE = auto()
    CHECKED_OUT = auto()
    VERIFIED = auto()
    REJECTED = auto()


@dataclass
class Exemplar:
    """The approved master text, locked and chunked into peciae."""

    title: str
    chunks: List[str] = field(default_factory=list)

    @classmethod
    def from_text(cls, title: str, text: str, chunk_lines: int = 4) -> "Exemplar":
        """Split the master text into peciae of ``chunk_lines`` lines each."""
        if not title.strip():
            raise PeciaError("an exemplar needs a title")
        lines = [ln for ln in text.splitlines()]
        if not lines:
            raise PeciaError("an exemplar needs text")
        chunks = [
            "\n".join(lines[i : i + chunk_lines])
            for i in range(0, len(lines), chunk_lines)
        ]
        return cls(title.strip(), chunks)

    def __len__(self) -> int:
        return len(self.chunks)

    def pecia(self, index: int) -> str:
        if not 0 <= index < len(self.chunks):
            raise PeciaError(
                f"pecia index {index} out of range (0..{len(self.chunks) - 1})"
            )
        return self.chunks[index]


@dataclass
class Copy:
    """One pecia in a worker's hands."""

    index: int
    worker: str
    text: str = ""
    status: PeciaStatus = PeciaStatus.CHECKED_OUT
    attempts: int = 0


class Stationer:
    """Concurrency control + verification: one pecia at a time per worker,
    every check-in verified against the exemplar before reassembly."""

    def __init__(self, exemplar: Exemplar) -> None:
        self.exemplar = exemplar
        self.pool: Dict[int, PeciaStatus] = {
            i: PeciaStatus.AVAILABLE for i in range(len(exemplar))
        }
        self.copies: Dict[int, Copy] = {}
        self.holdings: Dict[str, int] = {}  # worker -> pecia index (one at a time)
        self.verified: Dict[int, str] = {}  # index -> verified copy text
        self.rejections: List[Dict[str, object]] = []

    # -- distribution --------------------------------------------------
    def checkout(self, worker: str) -> int:
        """Hand one available pecia to a worker. One at a time — the discipline."""
        if worker in self.holdings:
            raise PeciaError(
                f"worker '{worker}' already holds pecia {self.holdings[worker]}; "
                "one pecia at a time"
            )
        for index, status in self.pool.items():
            if status is PeciaStatus.AVAILABLE:
                self.pool[index] = PeciaStatus.CHECKED_OUT
                self.holdings[worker] = index
                self.copies[index] = Copy(index=index, worker=worker)
                return index
        raise PeciaError("no peciae available: the stationer's pool is empty")

    # -- verification ---------------------------------------------------
    def checkin(self, worker: str, text: str) -> bool:
        """Verify a returned copy against the exemplar chunk.

        Exact match: verified and the worker's slot frees up. Mismatch:
        rejected, returned to the pool for re-copying, rejection logged.
        """
        if worker not in self.holdings:
            raise PeciaError(f"worker '{worker}' holds no pecia")
        index = self.holdings.pop(worker)
        copy = self.copies[index]
        copy.attempts += 1
        copy.text = text
        if text == self.exemplar.pecia(index):
            copy.status = PeciaStatus.VERIFIED
            self.pool[index] = PeciaStatus.VERIFIED
            self.verified[index] = text
            return True
        copy.status = PeciaStatus.REJECTED
        self.pool[index] = PeciaStatus.AVAILABLE  # back to the pool, re-copy it
        self.rejections.append(
            {"index": index, "worker": worker, "attempt": copy.attempts}
        )
        return False

    # -- reassembly -----------------------------------------------------
    def missing(self) -> List[int]:
        return [i for i in range(len(self.exemplar)) if i not in self.verified]

    def reassemble(self) -> str:
        """Reassemble the verified copies in order — the finished book."""
        missing = self.missing()
        if missing:
            raise PeciaError(
                f"cannot reassemble: {len(missing)} pecia(e) unverified "
                f"(indices {missing})"
            )
        return "\n".join(self.verified[i] for i in range(len(self.exemplar)))

    def progress(self) -> Dict[str, object]:
        """Where production stands: verified, in flight, rejected, missing."""
        return {
            "title": self.exemplar.title,
            "total_peciae": len(self.exemplar),
            "verified": len(self.verified),
            "checked_out": len(self.holdings),
            "rejections": len(self.rejections),
            "missing": self.missing(),
            "complete": not self.missing(),
        }
