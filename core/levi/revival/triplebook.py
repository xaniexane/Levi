"""LEVI's triple-book accounting: three representations, duality as error detection.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #8)

The old mechanism: every economic event is written three times at three
levels — the *memoriale* (raw jottings as they happen), the *giornale*
(chronological journal of balanced debits and credits), and the *quaderno*
(the analytical ledger organized by account). What makes the system
trustworthy is *duality*: every entry must balance — total debits equal
total credits. An unbalanced entry is refused at the door; the trial
balance re-verifies the whole ledger on demand and names the offender.

``TripleBook`` runs the three levels:

  - ``jot`` — memoriale: a raw timestamped note, no balancing required
    (the scratch pad; mistakes are allowed here).
  - ``record`` — giornale + quaderno: a balanced entry with debit and
    credit lines. Raises ``UnbalancedEntry`` if debits ≠ credits, and
    reports the offending entry — the error is flagged, never stored.
  - ``promote`` — carry a memoriale jot into a balanced ``record``.

``trial_balance`` sums every account's net position and asserts the books
still balance; ``account_balance`` reads one account; ``close`` carries
income/expense into equity. Amounts are integer cents — no float drift,
ever.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

ORIGIN = "levi-revival/triplebook"


class BookError(Exception):
    """Base class for bookkeeping failures."""


class UnbalancedEntry(BookError):
    """A journal entry whose debits do not equal its credits.

    Carries the offending entry so the caller knows exactly what failed.
    """

    def __init__(self, entry: "JournalEntry"):
        self.entry = entry
        super().__init__(
            f"unbalanced entry {entry.id} {entry.narration!r}: "
            f"debits {entry.total_debits()} != credits {entry.total_credits()}"
        )


@dataclass
class Line:
    """One debit or credit line against an account (integer cents)."""

    account: str
    debit: int = 0
    credit: int = 0


@dataclass
class JournalEntry:
    """One chronological, double-sided entry: debits must equal credits."""

    id: int
    narration: str
    lines: List[Line]
    at: float = field(default_factory=time.time)

    def total_debits(self) -> int:
        return sum(line.debit for line in self.lines)

    def total_credits(self) -> int:
        return sum(line.credit for line in self.lines)

    def is_balanced(self) -> bool:
        return self.total_debits() == self.total_credits() and self.total_debits() > 0


@dataclass
class Jot:
    """A memoriale note: raw, timestamped, unbalanced by design."""

    id: int
    note: str
    at: float = field(default_factory=time.time)


class TripleBook:
    """Memoriale → giornale → quaderno, with duality enforced."""

    def __init__(self, name: str = "levi-books"):
        self.name = name
        self.memoriale: List[Jot] = []
        self.giornale: List[JournalEntry] = []
        self.quaderno: Dict[str, int] = {}  # account -> net debit balance (cents)
        self._next_id = 1

    # -- level 1: memoriale ----------------------------------------------------
    def jot(self, note: str) -> Jot:
        """Raw jotting. No balancing, no judgment — the scratch pad."""
        entry = Jot(id=self._next_id, note=note)
        self._next_id += 1
        self.memoriale.append(entry)
        return entry

    # -- level 2+3: giornale + quaderno ----------------------------------------
    def record(
        self,
        narration: str,
        debits: List[Tuple[str, int]],
        credits: List[Tuple[str, int]],
    ) -> JournalEntry:
        """Record a balanced entry; refuses unbalanced ones at the door.

        `debits` / `credits` are (account, cents) pairs. Raises
        UnbalancedEntry with the offending entry attached.
        """
        entry = JournalEntry(
            id=self._next_id,
            narration=narration,
            lines=[Line(account=a, debit=c) for a, c in debits]
            + [Line(account=a, credit=c) for a, c in credits],
        )
        self._next_id += 1
        if not entry.is_balanced():
            raise UnbalancedEntry(entry)
        self.giornale.append(entry)
        for line in entry.lines:
            self.quaderno[line.account] = self.quaderno.get(line.account, 0) + (
                line.debit - line.credit
            )
        return entry

    def promote(self, jot_id: int, narration: str, debits, credits) -> JournalEntry:
        """Carry a memoriale jot into a balanced journal entry."""
        jot = next((j for j in self.memoriale if j.id == jot_id), None)
        if jot is None:
            raise KeyError(f"no memoriale jot {jot_id}")
        return self.record(f"{narration} (from jot {jot_id})", debits, credits)

    # -- verification -----------------------------------------------------------
    def trial_balance(self) -> Dict[str, Any]:
        """Re-verify duality across the whole ledger.

        Returns per-account net balances plus the grand totals. If the
        ledger is internally consistent, total debits == total credits and
        the account nets sum to zero. Raises BookError naming the offender
        otherwise — which should never happen, since `record` guards the
        door, but the trial is the independent check.
        """
        total_debits = sum(e.total_debits() for e in self.giornale)
        total_credits = sum(e.total_credits() for e in self.giornale)
        net_sum = sum(self.quaderno.values())
        if total_debits != total_credits:
            raise BookError(
                f"trial balance failed: giornale debits {total_debits} != credits {total_credits}"
            )
        if net_sum != 0:
            raise BookError(
                f"trial balance failed: account nets sum to {net_sum}, expected 0"
            )
        return {
            "accounts": dict(self.quaderno),
            "total_debits": total_debits,
            "total_credits": total_credits,
            "balanced": True,
        }

    def account_balance(self, account: str) -> int:
        """Net debit balance of one account (negative = net credit), in cents."""
        return self.quaderno.get(account, 0)

    def close(
        self, income_account: str, expense_account: str, equity_account: str
    ) -> JournalEntry:
        """Carry income/expense into equity: the period-close entry.

        Income carries a net credit balance (negative in this debit-positive
        scheme), expense a net debit balance. Close them out and book the
        profit (or loss) to equity — itself a balanced entry.
        """
        income_credit = -self.account_balance(income_account)  # >= 0 if income exists
        expense_debit = self.account_balance(expense_account)  # >= 0 if expenses exist
        profit = income_credit - expense_debit
        if profit >= 0:
            return self.record(
                f"close {income_account}/{expense_account} to {equity_account}",
                debits=[(income_account, income_credit)],
                credits=[(expense_account, expense_debit), (equity_account, profit)],
            )
        return self.record(
            f"close {income_account}/{expense_account} to {equity_account} (loss)",
            debits=[(income_account, income_credit), (equity_account, -profit)],
            credits=[(expense_account, expense_debit)],
        )
