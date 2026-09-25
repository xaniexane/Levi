"""Independent recomputation as a discipline: two-path audit trails.

Studied from: pre-digital-computation-20260916, report.md [Cross-entry pattern 1].

Inspired by the *shape* of the old recomputation discipline: every
consequential figure is computed twice along independent paths, and the
*evidence* is kept — mod-9/mod-11 receipts on the figures, trial-balance
audits on the books, and hash-chained logs so a later tamper breaks the
chain. Where :mod:`revival.independent_dup` is about independent
*methods* (other hands), this module is about independent *paths of
evidence* over the same computation. Original, from-scratch LEVI code.

Three mechanisms, one discipline:

- :class:`Receipt` — a mod-9/mod-11 residue pair attached to a result, so
  a later recomputation can be checked without redoing the full work.
- :class:`TrialBalance` — a debit/credit ledger; the books must balance
  to zero, and any single-sided entry is refused.
- :class:`AuditLog` — a hash-chained append-only log of computations;
  :meth:`AuditLog.audit` re-runs every entry's independent path and
  verifies both the chain and the recomputed results.

Honest limits: hash chaining detects *tampering*, not honest mistakes
(an entry wrong from birth chains perfectly); receipts catch residue
mismatches, not all errors; the independent recompute function is
supplied by the caller and trusted to be genuinely independent.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

ORIGIN = "levi-revival/independent-recompute"


class RecomputeError(Exception):
    """Base class for recomputation-discipline failures."""


class UnbalancedBooks(RecomputeError):
    """A ledger entry broke the debit/credit balance."""


class ChainBroken(RecomputeError):
    """A hash-chain link does not match its predecessor."""


class ReceiptMismatch(RecomputeError):
    """Recomputation disagrees with the recorded receipt."""


# ---------------------------------------------------------------------------
# Receipts — mod-9/mod-11 evidence attached to a result
# ---------------------------------------------------------------------------


def _residues(value: int) -> Dict[int, int]:
    n = abs(int(value))
    r9 = n % 9
    digits = [int(d) for d in str(n)][::-1]
    r11 = sum(d if i % 2 == 0 else -d for i, d in enumerate(digits)) % 11
    return {9: r9, 11: r11}


@dataclass(frozen=True)
class Receipt:
    """Residue evidence for a computed integer result."""

    label: str
    result: int
    residues: Dict[int, int]

    @classmethod
    def issue(cls, label: str, result: int) -> "Receipt":
        return cls(label=label, result=int(result), residues=_residues(result))

    def matches(self, candidate: int) -> bool:
        """True when ``candidate`` carries the same residues."""
        return _residues(candidate) == self.residues


# ---------------------------------------------------------------------------
# Trial balance — the books must balance
# ---------------------------------------------------------------------------


@dataclass
class TrialBalance:
    """A double-entry ledger: every debit needs its credit.

    ``post`` records a named movement; the running balance must return to
    zero for the books to close. Single-sided postings are refused.
    """

    entries: List[Dict[str, Any]] = field(default_factory=list)

    def post(self, name: str, debit: float = 0.0, credit: float = 0.0) -> None:
        if debit and credit:
            raise UnbalancedBooks(f"{name!r}: post debit XOR credit, not both")
        if not debit and not credit:
            raise UnbalancedBooks(f"{name!r}: post must move something")
        self.entries.append({"name": name, "debit": debit, "credit": credit})

    def totals(self) -> Dict[str, float]:
        return {
            "debit": round(sum(e["debit"] for e in self.entries), 10),
            "credit": round(sum(e["credit"] for e in self.entries), 10),
        }

    def is_balanced(self) -> bool:
        t = self.totals()
        return t["debit"] == t["credit"]

    def close(self) -> Dict[str, float]:
        """Close the books; raises unless debits equal credits."""
        t = self.totals()
        if not self.is_balanced():
            raise UnbalancedBooks(
                f"books do not balance: debit {t['debit']} != credit {t['credit']}"
            )
        return t


# ---------------------------------------------------------------------------
# Audit log — hash-chained, independently recomputed
# ---------------------------------------------------------------------------


@dataclass
class LogEntry:
    seq: int
    label: str
    inputs: Dict[str, Any]
    result: Any
    receipt: Receipt
    prev_hash: str
    entry_hash: str


@dataclass
class AuditReport:
    entries_checked: int
    chain_ok: bool
    recompute_ok: bool
    failures: List[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return self.chain_ok and self.recompute_ok and not self.failures


class AuditLog:
    """Append-only log where each entry chains to the last and carries a
    receipt, so an independent recomputation path can verify it later."""

    def __init__(self, recompute: Callable[[str, Dict[str, Any]], Any]) -> None:
        #: Maps an entry label to the independent function that recomputes it.
        self.recompute = recompute
        self.entries: List[LogEntry] = []

    @staticmethod
    def _hash(payload: str) -> str:
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _canonical(
        self, seq: int, label: str, inputs: Dict[str, Any], result: Any, prev_hash: str
    ) -> str:
        return json.dumps(
            {
                "seq": seq,
                "label": label,
                "inputs": inputs,
                "result": result,
                "prev": prev_hash,
            },
            sort_keys=True,
            default=str,
        )

    def record(self, label: str, inputs: Dict[str, Any], result: Any) -> LogEntry:
        """Append a computation with its receipt and chain link."""
        seq = len(self.entries)
        prev_hash = self.entries[-1].entry_hash if self.entries else "GENESIS"
        receipt = Receipt.issue(label, int(result)) if _is_int_like(result) else None
        entry_hash = self._hash(self._canonical(seq, label, inputs, result, prev_hash))
        entry = LogEntry(seq, label, inputs, result, receipt, prev_hash, entry_hash)
        self.entries.append(entry)
        return entry

    def verify_chain(self) -> bool:
        """True when every link's hash and prev-pointer are intact."""
        prev = "GENESIS"
        for e in self.entries:
            if e.prev_hash != prev:
                return False
            if e.entry_hash != self._hash(
                self._canonical(e.seq, e.label, e.inputs, e.result, e.prev_hash)
            ):
                return False
            prev = e.entry_hash
        return True

    def audit(self) -> AuditReport:
        """Re-run the independent path for every entry and verify receipts.

        Checks three things: the hash chain is intact, each entry's
        recomputed result carries the recorded receipt, and no entry was
        skipped. Failures are collected, never raised mid-audit.
        """
        report = AuditReport(
            len(self.entries), chain_ok=self.verify_chain(), recompute_ok=True
        )
        if not report.chain_ok:
            report.failures.append("hash chain broken: log was tampered with")
        for e in self.entries:
            try:
                fresh = self.recompute(e.label, dict(e.inputs))
            except Exception as exc:  # noqa: BLE001 - recorded as audit evidence
                report.recompute_ok = False
                report.failures.append(
                    f"entry {e.seq} ({e.label}): recompute raised {exc}"
                )
                continue
            if fresh != e.result:
                report.recompute_ok = False
                report.failures.append(
                    f"entry {e.seq} ({e.label}): recompute gave {fresh!r}, "
                    f"log says {e.result!r}"
                )
            elif e.receipt is not None and not e.receipt.matches(int(fresh)):
                report.recompute_ok = False
                report.failures.append(
                    f"entry {e.seq} ({e.label}): receipt residues disagree"
                )
        return report


def _is_int_like(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
