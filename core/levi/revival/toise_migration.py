"""LEVI's measure-migration tables: old records stay readable after the unit dies.

Studied from: lost-crafts-20260916 / report.md [Batch 2]
(French Toise)

The studied mechanism: when the new metre was defined, the law did not
pretend the old measure had never existed — it defined the new unit *in
terms of the old*: the 1799 law fixed the metre as exactly 443.296
lignes of the Toise du Pérou. The old master thereby calibrated its own
replacement, and every toise-denominated record ever written stayed
interpretable: multiply by the legal factor. That is the migration
table — a versioned mapping from dead units to living ones, where each
mapping carries the *law* (or decree, or edict) that fixed it and the
date it took effect.

This module rebuilds that as LEVI's own mechanism. A
:class:`MigrationTable` holds :class:`LegalDefinition`s: "1 <new_unit> =
<factor> <old_subunit> of <old_standard>, fixed by <authority> on
<date>." Old :class:`MeasureRecord`s (value + unit + standard + date)
translate through the definition in force at their date; records
predating any definition are refused, not guessed at. The old
standard's own drift is recorded too — the Toise du Pérou was itself a
physical bar, and the law froze a *number*, not the metal.

Honest limits: the 443.296 factor arrives from the studied report; this
module treats legal definitions as *declared data*, not verified
metrology. It keeps old records interpretable — it does not certify
that the old records were ever right.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


ORIGIN = "levi-revival/toise_migration"


class MigrationError(Exception):
    """Base error for measure-migration failures."""


@dataclass(frozen=True)
class LegalDefinition:
    """The law that fixes a new unit in terms of an old one.

    new_unit: e.g. "metre". old_standard: e.g. "Toise du Pérou".
    old_subunit: e.g. "ligne". factor: how many old_subunits equal one
    new_unit (443.296 lignes per metre in the studied case).
    authority/date: who fixed it and when it took effect — the
    provenance of the number.
    """

    new_unit: str
    old_standard: str
    old_subunit: str
    factor: float
    authority: str
    date: str  # effective date, "YYYY-MM-DD" — compared lexicographically

    def __post_init__(self) -> None:
        if self.factor <= 0:
            raise MigrationError("a legal definition's factor must be positive")


@dataclass(frozen=True)
class MeasureRecord:
    """An old record: value in old_subunits of a named old standard."""

    value: float
    old_standard: str
    old_subunit: str
    date: str  # when the measurement was recorded
    note: str = ""


@dataclass
class Translation:
    """A migrated record: the new-unit value plus its full provenance."""

    value_new: float
    new_unit: str
    definition: LegalDefinition
    original: MeasureRecord


class MigrationTable:
    """Versioned migration laws; old records in, new-unit values out."""

    def __init__(self) -> None:
        self._definitions: List[LegalDefinition] = []
        self._drift_notes: List[Tuple[str, str, str]] = []  # (standard, date, note)

    def enact(self, definition: LegalDefinition) -> None:
        """Record a new legal definition. Definitions accumulate; the
        newest one in force at a record's date governs its translation."""
        self._definitions.append(definition)
        self._definitions.sort(key=lambda d: d.date)

    def note_drift(self, standard: str, date: str, note: str) -> None:
        """Record that an old physical standard itself drifted — the law
        froze a number, not the metal."""
        self._drift_notes.append((standard, date, note))

    def drift_notes(self, standard: str) -> List[Tuple[str, str]]:
        return [(d, n) for s, d, n in self._drift_notes if s == standard]

    def definition_in_force(
        self, standard: str, subunit: str, date: str
    ) -> LegalDefinition:
        """The newest definition covering this standard/subunit at ``date``.

        Raises MigrationError if none was in force yet — a record older
        than every law is refused, never guessed at.
        """
        candidates = [
            d
            for d in self._definitions
            if d.old_standard == standard
            and d.old_subunit == subunit
            and d.date <= date
        ]
        if not candidates:
            raise MigrationError(
                f"no legal definition for {standard} {subunit} in force at {date}"
            )
        return candidates[-1]

    def translate(self, record: MeasureRecord) -> Translation:
        """Migrate one old record to the new unit, with provenance attached."""
        definition = self.definition_in_force(
            record.old_standard, record.old_subunit, record.date
        )
        value_new = record.value / definition.factor
        return Translation(
            value_new=value_new,
            new_unit=definition.new_unit,
            definition=definition,
            original=record,
        )

    def translate_all(self, records: List[MeasureRecord]) -> List[Translation]:
        return [self.translate(r) for r in records]
