"""Double-entry bookkeeping with a linear-time global invariant.

Studied from: pre-digital-computation-20260916/report.md [Beat C #12]
(Double-entry trial balance, 1494)

The studied shape: every transaction is recorded twice — once
chronologically in the journal, once organized by account in the
ledger — and one global invariant checks the whole book: total debits
must equal total credits. Two orthogonal representations plus one
cheap invariant: an ancestor of the Merkle tree's root-hash check.

LEVI-native re-expression: an **Entry** posts balanced debit/credit
lines (each entry must balance on its own); the **Journal** keeps
entries chronological with an append-only hash chain over their
canonical form; the **Ledger** aggregates the same entries by account;
**trial_balance** reports per-account debit/credit/total and asserts
the global invariant sum(debits) == sum(credits) across both
representations, plus a journal-vs-ledger cross-check. The hash chain
is the honestly-labeled "Merkle ancestor": tamper-evidence for the
chronology, not a tree.

Operations:

* ``Entry(date, narration, postings)`` — postings: [(account, debit, credit)]
* ``Journal.post(entry)`` — chronological, hash-chained
* ``Ledger.from_journal(journal)`` — by-account aggregation
* ``trial_balance(journal, ledger)`` -> TrialBalance report with invariant verdict

Honest limits: no currency conversion, no rounding rules, no voiding —
corrections are new balancing entries. The hash chain detects
rewrites of history, it does not prevent them.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, List, Tuple


ORIGIN = "levi-revival/trial-balance"

# A posting: (account, debit_amount, credit_amount). One side must be zero.
Posting = Tuple[str, float, float]


@dataclass(frozen=True)
class Entry:
    """One journal entry: balanced debit/credit postings with a date and narration."""

    date: str
    narration: str
    postings: Tuple[Posting, ...]

    def __post_init__(self) -> None:
        debits = sum(p[1] for p in self.postings)
        credits = sum(p[2] for p in self.postings)
        if not self.postings:
            raise ValueError("entry must have at least one posting")
        for account, debit, credit in self.postings:
            if debit < 0 or credit < 0:
                raise ValueError("posting amounts must be non-negative")
            if debit > 0 and credit > 0:
                raise ValueError(f"posting to {account!r} has both debit and credit")
        if abs(debits - credits) > 1e-9:
            raise ValueError(
                f"entry does not balance: debits {debits} != credits {credits}"
            )

    def canonical(self) -> str:
        lines = [self.date, self.narration]
        lines.extend(f"{a}:{d}:{c}" for a, d, c in sorted(self.postings))
        return "\n".join(lines)


class Journal:
    """The chronological record, with an append-only hash chain over entries."""

    def __init__(self) -> None:
        self.entries: List[Entry] = []
        self.chain: List[str] = []

    def post(self, entry: Entry) -> str:
        prev = self.chain[-1] if self.chain else "GENESIS"
        digest = hashlib.sha256(
            (prev + "\n" + entry.canonical()).encode("utf-8")
        ).hexdigest()
        self.entries.append(entry)
        self.chain.append(digest)
        return digest

    def verify_chain(self) -> bool:
        """Recompute the chain: True iff the chronology is untampered."""
        prev = "GENESIS"
        for entry, digest in zip(self.entries, self.chain, strict=True):
            recomputed = hashlib.sha256(
                (prev + "\n" + entry.canonical()).encode("utf-8")
            ).hexdigest()
            if recomputed != digest:
                return False
            prev = digest
        return True


class Ledger:
    """The by-account representation: the same entries, aggregated per account."""

    def __init__(self) -> None:
        self.accounts: Dict[str, Dict[str, float]] = {}

    @classmethod
    def from_journal(cls, journal: Journal) -> "Ledger":
        ledger = cls()
        for entry in journal.entries:
            for account, debit, credit in entry.postings:
                slot = ledger.accounts.setdefault(
                    account, {"debit": 0.0, "credit": 0.0}
                )
                slot["debit"] += debit
                slot["credit"] += credit
        return ledger

    def balance_of(self, account: str) -> float:
        slot = self.accounts.get(account, {"debit": 0.0, "credit": 0.0})
        return slot["debit"] - slot["credit"]


@dataclass
class TrialBalance:
    """The trial-balance report: per-account totals plus the global invariant."""

    accounts: Dict[str, Dict[str, float]]
    total_debits: float
    total_credits: float
    journal_total_debits: float
    journal_total_credits: float
    invariant_holds: bool
    representations_agree: bool

    def balanced(self) -> bool:
        return self.invariant_holds and self.representations_agree


def trial_balance(journal: Journal, ledger: Ledger) -> TrialBalance:
    """Two orthogonal representations, one linear-time global invariant."""
    total_debits = sum(slot["debit"] for slot in ledger.accounts.values())
    total_credits = sum(slot["credit"] for slot in ledger.accounts.values())
    j_debits = sum(p[1] for e in journal.entries for p in e.postings)
    j_credits = sum(p[2] for e in journal.entries for p in e.postings)
    return TrialBalance(
        accounts={a: dict(s) for a, s in ledger.accounts.items()},
        total_debits=total_debits,
        total_credits=total_credits,
        journal_total_debits=j_debits,
        journal_total_credits=j_credits,
        invariant_holds=abs(total_debits - total_credits) < 1e-9,
        representations_agree=(
            abs(total_debits - j_debits) < 1e-9
            and abs(total_credits - j_credits) < 1e-9
        ),
    )
