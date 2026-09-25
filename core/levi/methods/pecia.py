"""Pecia system: verifiable chunked transcription protocol.

History: the medieval university's distributed publishing system (Bologna
c. 1200; Paris regulated by mid-13th c.). An approved master text (the
*exemplar*) was divided into standardized quires (*peciae*, ~4 folios
each), deposited with a licensed *stationer*, and rented out one pecia at
a time — often with a one-week loan norm. Dozens of student-scribes copied
different peciae in parallel, assembling complete books far faster than any
single scriptorium. (Print later kept the logic: compositors setting
different quires simultaneously from the same copy.)

In LEVI: pecia-style parallel production of big artifacts — a book, a
report, a course is chunked into peciae against a locked exemplar (the
approved outline/brief); chunks are checked out one-at-a-time (the
stationer's concurrency control: one pecia per scribe), produced in
parallel, verified, and only verified chunks assemble. Every chunk stays
traceable to its exemplar section and its scribe. State persists as JSON
under ``~/.levi/methods/`` (``LEVI_HOME``-overridable for hermetic tests).

Two verification modes (honest about what "verified" means):
- ``transcribe``: the copy must be byte-identical to the exemplar chunk
  (sha256 match). For literal reproduction jobs.
- ``compose``: the copy is new work — it must cite its exemplar section
  and is checksummed for integrity/audit. For parallel drafting jobs.

Honesty: USEFUL PATTERN — parallelize-by-chunking with a canonical source
and deny-closed assembly (nothing unverified is ever collated).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from . import _persist


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class PeciaError(Exception):
    """Base class for pecia-protocol failures."""


class LeaseError(PeciaError):
    """Concurrency-control violation (double checkout, unknown lease)."""


class VerificationError(PeciaError):
    """A submitted copy failed verification (rejected, lease released)."""


class AssemblyError(PeciaError):
    """Assembly refused: one or more peciae are unverified."""


# ---------------------------------------------------------------------------
# Exemplar + peciae
# ---------------------------------------------------------------------------


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class Pecia:
    """One chunk of the exemplar, with its canonical checksum."""

    pecia_id: str
    index: int
    start: int
    end: int
    text: str
    checksum: str
    kind: str = "transcribe"  # or "compose"
    exemplar_ref: str = ""  # exemplar section this pecia answers to

    def to_dict(self) -> dict:
        return {
            "pecia_id": self.pecia_id,
            "index": self.index,
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "checksum": self.checksum,
            "kind": self.kind,
            "exemplar_ref": self.exemplar_ref,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Pecia":
        return cls(**data)


class Exemplar:
    """The locked, approved master text. Splitting never mutates it."""

    def __init__(self, title: str, text: str):
        if not title or not title.strip():
            raise ValueError("exemplar title must be non-empty")
        if not text:
            raise ValueError("exemplar text must be non-empty")
        self.title = title.strip()
        self.text = text
        self.checksum = _sha256(text)

    def split(
        self, n: int, kind: str = "transcribe", refs: tuple[str, ...] = ()
    ) -> list[Pecia]:
        """Divide the exemplar into ``n`` peciae at line boundaries.

        ``kind`` applies to every pecia; ``refs`` optionally names the
        exemplar section each pecia answers to (used by compose mode).
        """
        if n < 1:
            raise ValueError("n must be >= 1")
        if kind not in ("transcribe", "compose"):
            raise ValueError(f"unknown pecia kind: {kind!r}")
        lines = self.text.splitlines(keepends=True)
        if not lines:
            lines = [self.text]
        n = min(n, len(lines))
        per, extra = divmod(len(lines), n)
        peciae: list[Pecia] = []
        pos = 0
        start_line = 0
        for i in range(n):
            count = per + (1 if i < extra else 0)
            chunk_lines = lines[start_line : start_line + count]
            chunk = "".join(chunk_lines)
            end = pos + len(chunk)
            peciae.append(
                Pecia(
                    pecia_id=f"pecia-{i + 1:02d}",
                    index=i,
                    start=pos,
                    end=end,
                    text=chunk,
                    checksum=_sha256(chunk),
                    kind=kind,
                    exemplar_ref=refs[i] if i < len(refs) else "",
                )
            )
            pos = end
            start_line += count
        return peciae


@dataclass
class Lease:
    pecia_id: str
    scribe: str


@dataclass
class Submission:
    pecia_id: str
    scribe: str
    checksum: str
    exemplar_ref: str
    attempts: int = 1


# ---------------------------------------------------------------------------
# Stationer — the concurrency control + verification authority
# ---------------------------------------------------------------------------


class Stationer:
    """Holds the peciae, rents them one-at-a-time, verifies, assembles.

    Deny-closed: a scribe may hold at most one pecia; a rejected copy
    returns its pecia to the pool; :meth:`assemble` refuses while any
    pecia is unverified.
    """

    def __init__(
        self, exemplar: Exemplar, peciae: list[Pecia], store: str | None = None
    ):
        if not peciae:
            raise ValueError("stationer needs at least one pecia")
        self.exemplar = exemplar
        self._peciae = {p.pecia_id: p for p in peciae}
        self._leases: dict[str, Lease] = {}  # pecia_id -> lease
        self._by_scribe: dict[str, str] = {}  # scribe -> pecia_id
        self._verified: dict[str, Submission] = {}
        self._attempts: dict[str, int] = {}
        self._store = _persist.store_path(store or f"pecia-{_slug(exemplar.title)}")
        self._load()

    # -- persistence ------------------------------------------------------
    def _load(self) -> None:
        data = _persist.load_json(self._store)
        if not data:
            return
        if data.get("exemplar_checksum") != self.exemplar.checksum:
            raise _persist.CorruptStoreError(
                f"pecia store {self._store} belongs to a different exemplar"
            )
        for pid, sub in data.get("verified", {}).items():
            if pid in self._peciae:
                self._verified[pid] = Submission(**sub)

    def save(self) -> None:
        _persist.save_json(
            self._store,
            {
                "exemplar_checksum": self.exemplar.checksum,
                "verified": {pid: vars(s) for pid, s in self._verified.items()},
            },
        )

    # -- the rental discipline ---------------------------------------------
    def available(self) -> list[str]:
        """Pecia ids neither leased nor verified, in exemplar order."""
        return [
            p.pecia_id
            for p in sorted(self._peciae.values(), key=lambda p: p.index)
            if p.pecia_id not in self._leases and p.pecia_id not in self._verified
        ]

    def checkout(self, scribe: str, pecia_id: str | None = None) -> Pecia:
        """Rent one pecia to a scribe. One pecia at a time per scribe."""
        if not scribe or not scribe.strip():
            raise ValueError("scribe must be non-empty")
        scribe = scribe.strip()
        if scribe in self._by_scribe:
            raise LeaseError(
                f"scribe {scribe!r} already holds {self._by_scribe[scribe]!r}: "
                "one pecia at a time"
            )
        target = pecia_id or (self.available()[0] if self.available() else None)
        if target is None:
            raise LeaseError("no peciae available")
        if target not in self._peciae:
            raise LeaseError(f"unknown pecia {target!r}")
        if target in self._leases:
            raise LeaseError(f"pecia {target!r} is already leased")
        if target in self._verified:
            raise LeaseError(f"pecia {target!r} is already verified")
        self._leases[target] = Lease(pecia_id=target, scribe=scribe)
        self._by_scribe[scribe] = target
        return self._peciae[target]

    def submit(
        self, scribe: str, pecia_id: str, copy: str, exemplar_ref: str = ""
    ) -> Submission:
        """Submit a copy; verify it; release the lease on success OR failure.

        transcribe: copy must checksum-match the exemplar chunk exactly.
        compose: copy must be non-empty and cite its exemplar section.
        A failed copy is rejected (recorded as an attempt) — never filed.
        """
        lease = self._leases.get(pecia_id)
        if lease is None or lease.scribe != scribe:
            raise LeaseError(f"scribe {scribe!r} holds no lease on pecia {pecia_id!r}")
        pecia = self._peciae[pecia_id]
        self._attempts[pecia_id] = self._attempts.get(pecia_id, 0) + 1
        try:
            if pecia.kind == "transcribe":
                if _sha256(copy) != pecia.checksum:
                    raise VerificationError(
                        f"pecia {pecia_id!r} copy does not match the exemplar "
                        f"(checksum mismatch on attempt {self._attempts[pecia_id]})"
                    )
                ref = pecia.exemplar_ref
            else:  # compose
                if not copy or not copy.strip():
                    raise VerificationError(
                        f"pecia {pecia_id!r}: composed copy must be non-empty"
                    )
                ref = exemplar_ref.strip() or pecia.exemplar_ref
                if not ref:
                    raise VerificationError(
                        f"pecia {pecia_id!r}: composed copy must cite its "
                        "exemplar section"
                    )
            sub = Submission(
                pecia_id=pecia_id,
                scribe=scribe,
                checksum=_sha256(copy),
                exemplar_ref=ref,
                attempts=self._attempts[pecia_id],
            )
            self._verified[pecia_id] = sub
            return sub
        finally:
            # The lease is always released: verified or rejected, the pecia
            # returns to the pool for the next scribe.
            del self._leases[pecia_id]
            del self._by_scribe[scribe]

    # -- assembly -----------------------------------------------------------
    def unverified(self) -> list[str]:
        return [
            p.pecia_id
            for p in sorted(self._peciae.values(), key=lambda p: p.index)
            if p.pecia_id not in self._verified
        ]

    def assemble(self) -> tuple[str, list[dict]]:
        """Collate verified peciae in exemplar order.

        Returns ``(text, collation)`` where collation lists, per pecia, the
        scribe, checksum, exemplar ref, and attempt count — full provenance.
        Raises :class:`AssemblyError` while anything is unverified.
        """
        missing = self.unverified()
        if missing:
            raise AssemblyError(
                f"refusing assembly: {len(missing)} pecia(e) unverified: "
                + ", ".join(missing)
            )
        ordered = sorted(self._peciae.values(), key=lambda p: p.index)
        collation = [
            {
                "pecia_id": p.pecia_id,
                "scribe": self._verified[p.pecia_id].scribe,
                "checksum": self._verified[p.pecia_id].checksum,
                "exemplar_ref": self._verified[p.pecia_id].exemplar_ref,
                "attempts": self._verified[p.pecia_id].attempts,
            }
            for p in ordered
        ]
        return "".join(p.text for p in ordered), collation

    def progress(self) -> tuple[int, int]:
        """(verified, total)."""
        return len(self._verified), len(self._peciae)


def _slug(title: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in title.lower())[:40].strip("-")


__all__ = [
    "PeciaError",
    "LeaseError",
    "VerificationError",
    "AssemblyError",
    "Pecia",
    "Exemplar",
    "Lease",
    "Submission",
    "Stationer",
]
