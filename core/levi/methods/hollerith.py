"""The Hollerith punched-card pipeline: the first ETL, 1890 edition.

Origin (two records, one pipeline):
- arch-w6-the-hollerith-punched-card-pipeline-patent-1884-18 — Herman
  Hollerith's electromechanical tabulating system for the 1890 US census:
  pantograph-punched cards (one per person, holes = attributes) ->
  pin-and-mercury reader -> electromagnetic dial counters -> sorter. The
  1880 census took 7 years to tabulate; 1890's apportionment counts were
  certified within months. Cards were sized to then-current US banknotes so
  Hollerith could buy cheap storage boxes — format pragmatism. Later
  plugboards made the tabulator quasi-programmable: arguably the first
  stored-*configuration* data processor. It ran the Census until UNIVAC I.
- arch-w6-the-us-census-office-the-first-human-to-machine-da — the same
  pipeline as the first human-to-machine data pipeline: the separation of
  data preparation -> encoding -> mechanical processing -> verification
  that every ETL system still uses. Clerks transcribed tally sheets onto
  cards; readers advanced the dials; a bell rang and a clerk read the
  dials; then the same cards went through a 24-compartment sorter for
  cross-classification. Experienced clerks did 7,000-8,000 cards/day.

What it is in LEVI: a batch pipeline. ``CardSchema`` declares fields as
bit widths (hole positions); ``encode`` keypunches a record into a
``Card`` (packed bit-fields); ``tabulate`` runs the counters (value counts
per field); ``sort_pass`` runs the sorter (stable sort by a field); and
``verify`` is the verification pass — an independent recount that must
match, or the batch is rejected.

Honesty label: LOAD-BEARING — schema -> encode -> tabulate -> sort ->
verify is a concrete, transferable batch-data mechanism.

Deny-closed inputs: empty schema names, empty field lists, duplicate or
empty field names, widths outside 1..64, encoding records with missing or
extra fields, non-integer values, values that don't fit their field
width, tabulating/sorting unknown fields or empty decks, and verification
recounts that don't match all raise ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Field", "Card", "CardSchema", "tabulate", "sort_pass", "verify"]

MAX_WIDTH = 64


@dataclass(frozen=True)
class Field:
    name: str
    width: int  # bits; hole positions on the card


@dataclass(frozen=True)
class Card:
    schema_name: str
    bits: int  # packed bit-fields, MSB first


class CardSchema:
    """The schema: hole positions are fields."""

    def __init__(self, name: str, fields: list[Field]) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("schema name must be a non-empty string")
        if not fields:
            raise ValueError(f"schema {name!r}: needs at least one field")
        seen: set[str] = set()
        total = 0
        for f in fields:
            if not isinstance(f, Field):
                raise ValueError(f"schema {name!r}: not a Field: {f!r}")
            if not f.name or not f.name.strip():
                raise ValueError("field names must be non-empty")
            if f.name in seen:
                raise ValueError(f"duplicate field: {f.name!r}")
            if not 1 <= f.width <= MAX_WIDTH:
                raise ValueError(f"field {f.name!r}: width must be 1..{MAX_WIDTH}")
            seen.add(f.name)
            total += f.width
        if total > 1024:
            raise ValueError(f"schema {name!r}: card exceeds 1024 bits")
        self.name = name.strip()
        self.fields = list(fields)
        self.total_bits = total

    def field(self, name: str) -> Field:
        for f in self.fields:
            if f.name == name:
                return f
        raise ValueError(f"schema {self.name!r}: unknown field {name!r}")

    # -- keypunch ----------------------------------------------------------
    def encode(self, values: dict[str, int]) -> Card:
        """Punch one record: values packed into the schema's bit-fields."""
        if not isinstance(values, dict):
            raise ValueError("encode expects a dict of field -> value")
        missing = [f.name for f in self.fields if f.name not in values]
        if missing:
            raise ValueError(f"missing fields: {missing}")
        extra = [k for k in values if k not in {f.name for f in self.fields}]
        if extra:
            raise ValueError(f"unknown fields: {extra}")
        bits = 0
        for f in self.fields:
            v = values[f.name]
            if not isinstance(v, int) or isinstance(v, bool):
                raise ValueError(f"field {f.name!r}: value must be an int")
            if not 0 <= v < (1 << f.width):
                raise ValueError(
                    f"field {f.name!r}: value {v} doesn't fit in {f.width} bits"
                )
            bits = (bits << f.width) | v
        return Card(schema_name=self.name, bits=bits)

    def decode(self, card: Card) -> dict[str, int]:
        """Read a card back into field values (the reader)."""
        self._require_card(card)
        values: dict[str, int] = {}
        rest = card.bits
        for f in reversed(self.fields):
            values[f.name] = rest & ((1 << f.width) - 1)
            rest >>= f.width
        return values

    def _require_card(self, card: Card) -> None:
        if not isinstance(card, Card):
            raise ValueError(f"not a card: {card!r}")
        if card.schema_name != self.name:
            raise ValueError(
                f"card belongs to schema {card.schema_name!r}, not {self.name!r}"
            )


def tabulate(schema: CardSchema, cards: list[Card], field_name: str) -> dict[int, int]:
    """Run the counters: count occurrences of each value of a field."""
    field = schema.field(field_name)  # raises on unknown field
    if not cards:
        raise ValueError("tabulate needs a non-empty deck")
    counts: dict[int, int] = {}
    for card in cards:
        value = schema.decode(card)[field.name]
        counts[value] = counts.get(value, 0) + 1
    return counts


def sort_pass(schema: CardSchema, cards: list[Card], field_name: str) -> list[Card]:
    """Run the sorter: one stable pass ordering the deck by a field."""
    field = schema.field(field_name)  # raises on unknown field
    if not cards:
        raise ValueError("sort_pass needs a non-empty deck")
    keyed = [(schema.decode(card)[field.name], i, card) for i, card in enumerate(cards)]
    keyed.sort(key=lambda t: (t[0], t[1]))
    return [card for _, _, card in keyed]


def verify(
    schema: CardSchema,
    cards: list[Card],
    field_name: str,
    expected: dict[int, int],
) -> bool:
    """The verification pass: an independent recount must match, exactly."""
    schema.field(field_name)  # raises on unknown field
    if not cards:
        raise ValueError("verify needs a non-empty deck")
    if not isinstance(expected, dict):
        raise ValueError("expected counts must be a dict")
    recount = tabulate(schema, cards, field_name)
    if recount != expected:
        only_recount = {k: v for k, v in recount.items() if expected.get(k) != v}
        only_expected = {k: v for k, v in expected.items() if recount.get(k) != v}
        raise ValueError(
            f"verification failed for {field_name!r}: "
            f"recount-extra={only_recount}, expected-extra={only_expected}"
        )
    if sum(recount.values()) != len(cards):
        raise ValueError("verification failed: counts don't cover the deck")
    return True
