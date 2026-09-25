"""The first ETL: punched-card tabulation as an extract-transform-load pipeline.

Studied from: pre-digital-computation-20260916/report.md [Beat A #8] (Hollerith pipeline, 1884-1951)

The studied shape: a schema fixes which columns hold which fields
(holes = fields), a keypunch operator punches records into cards, a
pin/mercury reader reads them back as electrical contacts, dial
counters accumulate totals by column, and a sorter reorders the deck.
Encode -> read -> count -> sort: the first ETL.

LEVI-native re-expression: a fixed-width card schema maps named fields
to column ranges; a **KeyPunch** encodes records (dicts of decimal
integers) into cards (tuples of per-column digits); a **PinReader**
decodes cards back; **DialCounters** tally per-field value
frequencies; a **Sorter** reorders decks by a key field. The round-trip
punch -> read is exact, so the reader is an honest verifier of the
punch.

Operations:

* ``CardSchema.define(name, width)`` / ``schema.field(name, start, width)``
* ``KeyPunch.punch(schema, record)`` -> Card (tuple of digits)
* ``PinReader.read(schema, card)`` -> record dict
* ``DialCounters.tally(cards)`` -> per-field Counter of values
* ``Sorter.sort(deck, schema, key)`` -> reordered deck

Honest limits: fields hold non-negative integers that fit their column
width; no character encoding, no negative numbers, no arithmetic in
the counters beyond tallying. The "holes" are simulated as digits —
this is the pipeline's data shape, not electromechanical fidelity.
"""

from __future__ import annotations

from collections import Counter
from typing import Dict, Iterable, List, Sequence, Tuple


ORIGIN = "levi-revival/hollerith-etl"

# A Card is a fixed-width tuple of punched decimal digits, one per column.
Card = Tuple[int, ...]


class CardField:
    """One named field occupying a contiguous run of card columns."""

    def __init__(self, name: str, start: int, width: int) -> None:
        if width <= 0:
            raise ValueError("field width must be positive")
        if start < 0:
            raise ValueError("field start must be non-negative")
        self.name = name
        self.start = start
        self.width = width

    @property
    def end(self) -> int:
        return self.start + self.width

    def encode(self, value: int) -> List[int]:
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"field {self.name!r}: value must be a non-negative int")
        digits = [int(d) for d in str(value)]
        if len(digits) > self.width:
            raise ValueError(
                f"field {self.name!r}: value {value} needs {len(digits)} columns, field is {self.width}"
            )
        return [0] * (self.width - len(digits)) + digits

    def decode(self, digits: Sequence[int]) -> int:
        return int("".join(str(d) for d in digits))


class CardSchema:
    """Fixed-width layout: which columns carry which named field."""

    def __init__(self, columns: int) -> None:
        if columns <= 0:
            raise ValueError("card must have at least one column")
        self.columns = columns
        self.fields: Dict[str, CardField] = {}

    def field(self, name: str, start: int, width: int) -> "CardSchema":
        fld = CardField(name, start, width)
        if fld.end > self.columns:
            raise ValueError(f"field {name!r} runs past card width {self.columns}")
        for other in self.fields.values():
            if not (fld.end <= other.start or other.end <= fld.start):
                raise ValueError(f"field {name!r} overlaps field {other.name!r}")
        self.fields[name] = fld
        return self

    def __contains__(self, name: str) -> bool:
        return name in self.fields


class KeyPunch:
    """Encodes record dicts into punched cards (extract + transform)."""

    @staticmethod
    def punch(schema: CardSchema, record: Dict[str, int]) -> Card:
        card = [0] * schema.columns
        for name, field in schema.fields.items():
            value = record.get(name, 0)
            card[field.start : field.end] = field.encode(value)
        return tuple(card)


class PinReader:
    """Reads punched cards back into record dicts (load back into data)."""

    @staticmethod
    def read(schema: CardSchema, card: Card) -> Dict[str, int]:
        if len(card) != schema.columns:
            raise ValueError(
                f"card has {len(card)} columns, schema expects {schema.columns}"
            )
        return {
            name: field.decode(card[field.start : field.end])
            for name, field in schema.fields.items()
        }


class DialCounters:
    """Tallies how often each value appears per field across a deck."""

    def __init__(self, schema: CardSchema) -> None:
        self.schema = schema
        self.counters: Dict[str, Counter] = {name: Counter() for name in schema.fields}
        self.total = 0

    def feed(self, card: Card) -> None:
        record = PinReader.read(self.schema, card)
        for name, value in record.items():
            self.counters[name][value] += 1
        self.total += 1

    def feed_all(self, deck: Iterable[Card]) -> None:
        for card in deck:
            self.feed(card)

    def report(self) -> Dict[str, Dict[int, int]]:
        return {name: dict(counter) for name, counter in self.counters.items()}


class Sorter:
    """Reorders a deck by a key field (mechanical sort pass)."""

    @staticmethod
    def sort(deck: Sequence[Card], schema: CardSchema, key: str) -> List[Card]:
        if key not in schema:
            raise ValueError(f"no field named {key!r} in schema")
        field = schema.fields[key]
        return sorted(
            deck, key=lambda card: field.decode(card[field.start : field.end])
        )
