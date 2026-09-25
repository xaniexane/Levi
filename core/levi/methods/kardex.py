"""Kardex visible records: one-card-per-entity ambient dashboard.

History: early-20th-century office technology (Kardex, Library Bureau's
Speedac, Index Visible) — overlapping cards fixed in shallow trays so a
labeled *edge-strip* of every card stays visible at once: dozens of records
scannable in a glance, updatable by swapping a single card. The visible file
turned a card index into a *dashboard*: inventory levels, subscription
expirations, project statuses, all readable without opening anything. Died
when spreadsheets and databases absorbed it.

In LEVI: :class:`VisibleFile` is the ambient dashboard for recurring
systems — subscriptions, habit streaks, project pipelines. One card per
entity, each with a one-line status strip; :meth:`VisibleFile.dashboard`
renders every strip in one view; :meth:`VisibleFile.flagged` surfaces the
cards whose strips turned red (overdue / breached / attention). Updating is
one card-swap. Persists under ``~/.levi/methods/``.

Honesty: USEFUL PATTERN — ambient legibility plus single-card updates; the
trays are not coming back.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from . import _persist

STATUSES = ("green", "amber", "red")


@dataclass
class VisibleCard:
    entity: str
    strip: str = ""  # the one-line visible status, e.g. "renews 2026-10-01"
    status: str = "green"
    detail: str = ""  # behind the card; only read when you pull it
    updated: str = ""  # ISO date of last card-swap

    def validate(self) -> None:
        if not self.entity or not self.entity.strip():
            raise ValueError("entity must be non-empty")
        if self.status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")


class VisibleFile:
    """A tray of visible cards: whole-system state, legible at a glance."""

    def __init__(self, name: str, store: str | None = None):
        if not name or not name.strip():
            raise ValueError("visible-file name must be non-empty")
        self.name = name.strip()
        self._store = _persist.store_path(store or f"kardex-{self.name}")
        self.cards: dict[str, VisibleCard] = {}
        self._load()

    def _load(self) -> None:
        data = _persist.load_json(self._store)
        if not data:
            return
        if not isinstance(data, dict) or data.get("name") != self.name:
            raise _persist.CorruptStoreError(
                f"kardex store {self._store} does not match {self.name!r}"
            )
        for entity, cd in data.get("cards", {}).items():
            card = VisibleCard(**cd)
            card.validate()
            self.cards[entity] = card

    def save(self) -> None:
        _persist.save_json(
            self._store,
            {"name": self.name, "cards": {e: asdict(c) for e, c in self.cards.items()}},
        )

    def file_card(self, card: VisibleCard) -> None:
        """File (or swap in) a card — the single-card update."""
        card.validate()
        self.cards[card.entity.strip()] = card

    def pull(self, entity: str) -> VisibleCard:
        """Pull a card out of the tray to read the detail behind the strip."""
        if entity not in self.cards:
            raise KeyError(f"no card for {entity!r}")
        return self.cards[entity]

    def remove(self, entity: str) -> None:
        if entity not in self.cards:
            raise KeyError(f"no card for {entity!r}")
        del self.cards[entity]

    def dashboard(self) -> str:
        """The visible tray: every strip, scannable in one glance."""
        glyph = {"green": "●", "amber": "◐", "red": "■"}
        lines = [f"VISIBLE FILE: {self.name} — {len(self.cards)} cards"]
        for entity in sorted(self.cards, key=str.lower):
            card = self.cards[entity]
            lines.append(
                f"  {glyph[card.status]} {entity}: {card.strip or '(no strip)'}"
                + (f"  [updated {card.updated}]" if card.updated else "")
            )
        return "\n".join(lines)

    def flagged(self) -> list[VisibleCard]:
        """Cards whose strips turned red — the algedonic layer of the tray."""
        return [c for c in self.cards.values() if c.status == "red"]

    def set_status(
        self, entity: str, status: str, strip: str | None = None, updated: str = ""
    ) -> VisibleCard:
        if entity not in self.cards:
            raise KeyError(f"no card for {entity!r}")
        card = self.cards[entity]
        if status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        card.status = status
        if strip is not None:
            card.strip = strip
        if updated:
            card.updated = updated
        return card
