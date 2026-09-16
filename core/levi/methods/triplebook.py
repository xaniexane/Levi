"""Paciolian triple-book: intellectual double-entry accounting.

History: Luca Pacioli's 1494 *Summa* codified Venetian double-entry, but the
*intellectual* method underneath is the three-book pipeline: the
**memoriale** (rough daybook — capture everything as it happens), the
**giornale** (formal chronological journal in standardized form), and the
**quaderno grande** (the ledger, reorganized *by account* with debits left,
credits right), tied together by cross-references and the **trial balance** —
a mechanical error detector ("a person should not go to sleep at night until
the debits equal the credits").

In LEVI: :class:`TripleBook` runs your intellectual life as three books.
Every journal entry is *dual*: it debits one account and credits another
(what it costs, what it buys — a commitment logged against both a project
*and* a calendar slot). :meth:`trial_balance` is the killer feature: it
mechanically flags unbalanced accounts — commitments with no time allocated,
notes with no project, goals with no next action. Raw captures that never
make it into the journal show up as unposted. Persists under
``~/.levi/methods/``.

Honesty: USEFUL PATTERN — the duality-as-consistency-check transfers
directly; the merchant-house metaphysics need not.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from . import _persist


@dataclass
class Capture:
    """memoriale: raw, unprocessed capture."""

    text: str
    captured: str = ""  # ISO datetime
    posted: bool = False  # moved into the giornale yet?

    def validate(self) -> None:
        if not self.text or not self.text.strip():
            raise ValueError("capture text must be non-empty")


@dataclass
class JournalEntry:
    """giornale: one dual-aspect entry — debit one account, credit another."""

    narrative: str
    debit_account: str
    credit_account: str
    amount: float = 1.0  # abstract units of attention/obligation, not money
    date: str = ""

    def validate(self) -> None:
        if not self.narrative or not self.narrative.strip():
            raise ValueError("narrative must be non-empty")
        for attr in ("debit_account", "credit_account"):
            if not getattr(self, attr) or not getattr(self, attr).strip():
                raise ValueError(f"{attr} must be non-empty")
        if self.debit_account == self.credit_account:
            raise ValueError("debit and credit accounts must differ (duality)")
        if not isinstance(self.amount, (int, float)) or self.amount <= 0:
            raise ValueError("amount must be a positive number")


class TripleBook:
    """memoriale -> giornale -> quaderno, with a nightly trial balance."""

    def __init__(self, store: str = "triplebook"):
        self._store = _persist.store_path(store)
        self.memoriale: list[Capture] = []
        self.giornale: list[JournalEntry] = []
        self._load()

    def _load(self) -> None:
        data = _persist.load_json(self._store)
        if not data:
            return
        if not isinstance(data, dict) or "giornale" not in data:
            raise _persist.CorruptStoreError(
                f"triplebook store {self._store} has bad shape"
            )
        for cd in data.get("memoriale", []):
            c = Capture(**cd)
            c.validate()
            self.memoriale.append(c)
        for jd in data["giornale"]:
            j = JournalEntry(**jd)
            j.validate()
            self.giornale.append(j)

    def save(self) -> None:
        _persist.save_json(
            self._store,
            {
                "memoriale": [asdict(c) for c in self.memoriale],
                "giornale": [asdict(j) for j in self.giornale],
            },
        )

    # ---- memoriale -------------------------------------------------------
    def jot(self, text: str, captured: str = "") -> int:
        """Rough capture. Returns its index."""
        cap = Capture(text.strip(), captured)
        cap.validate()
        self.memoriale.append(cap)
        return len(self.memoriale) - 1

    # ---- giornale --------------------------------------------------------
    def post(self, entry: JournalEntry, from_capture: int | None = None) -> int:
        """Post a dual entry to the journal. Optionally marks a memoriale
        capture as posted, preserving the cross-reference."""
        entry.validate()
        if from_capture is not None:
            if not (0 <= from_capture < len(self.memoriale)):
                raise IndexError(f"no capture at index {from_capture}")
            self.memoriale[from_capture].posted = True
        self.giornale.append(entry)
        return len(self.giornale) - 1

    # ---- quaderno (the ledger, computed from the journal) ----------------
    def ledger(self) -> dict[str, dict[str, float]]:
        """Reorganize the journal by account: {account: {debit, credit}}."""
        accounts: dict[str, dict[str, float]] = {}
        for j in self.giornale:
            for side, acct in (
                ("debit", j.debit_account),
                ("credit", j.credit_account),
            ):
                acc = accounts.setdefault(acct, {"debit": 0.0, "credit": 0.0})
                acc[side] += float(j.amount)
        return accounts

    def balances(self) -> dict[str, float]:
        """Net balance per account (debit − credit)."""
        return {a: v["debit"] - v["credit"] for a, v in self.ledger().items()}

    def trial_balance(self) -> dict:
        """The mechanical error detector: totals must agree, and every account
        should net to zero *within a closed set* — accounts with a nonzero
        balance are flagged as unbalanced (commitments with no allocation,
        notes with no project, goals with no next action)."""
        accounts = self.ledger()
        total_debit = sum(v["debit"] for v in accounts.values())
        total_credit = sum(v["credit"] for v in accounts.values())
        unbalanced = {
            a: v["debit"] - v["credit"]
            for a, v in accounts.items()
            if abs(v["debit"] - v["credit"]) > 1e-9
        }
        unposted = [i for i, c in enumerate(self.memoriale) if not c.posted]
        return {
            "balanced": abs(total_debit - total_credit) < 1e-9,
            "total_debit": total_debit,
            "total_credit": total_credit,
            "unbalanced_accounts": unbalanced,
            "unposted_captures": unposted,
        }
