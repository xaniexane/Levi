"""Harvard College Observatory "computers": the piece-rate classification pipeline.

Origin: from ~1875 into the 20th century, Edward Charles Pickering hired
40-80 women — Williamina Fleming, Annie Jump Cannon, Henrietta Swan
Leavitt, Antonia Maury, Cecilia Payne — to process glass-plate spectra at
the Harvard College Observatory. Raw plates photographed at Arequipa, Peru
were shipped to Cambridge, where the women measured magnitudes, classified
spectra against one shared taxonomy, and maintained the Henry Draper
Catalogue. Fleming established the classification system; Cannon compressed
it into the O-B-A-F-G-K-M sequence still taught today; Leavitt derived the
period-luminosity relation that let Hubble measure intergalactic distances.
Quality came from specialization with promotion paths — every plate
examined independently, doubtful spectra kicked back up the chain — and
from decades of analysts refining one taxonomy instead of each observer
inventing their own.

What it is in LEVI: a classification pipeline with piece-rate accounting.
Items flow measure -> classify -> catalogue; every handoff is credited to a
named analyst, and ``throughput()`` is the pay slip — per-analyst piece
counts per stage. The taxonomy is living: ``compress()`` merges old labels
into new ones and REMAPS every item that carried an old label — the Cannon
operation, which turned a sprawling letter-soup into O-B-A-F-G-K-M.

Honesty label: LOAD-BEARING — staged flow + per-item piece accounting +
taxonomy compression remap is a concrete, transferable mechanism.

Deny-closed inputs: empty item ids, duplicate items, unknown item ids,
empty analyst names, empty label names, duplicate labels, measuring with no
measurements, classifying against unknown labels, stage transitions out of
order, and compressing unknown or self-referential labels are all rejected
with ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "Item",
    "ClassificationPipeline",
    "STAGE_INTAKE",
    "STAGE_MEASURED",
    "STAGE_CLASSIFIED",
    "STAGE_CATALOGUED",
]

STAGE_INTAKE = "intake"
STAGE_MEASURED = "measured"
STAGE_CLASSIFIED = "classified"
STAGE_CATALOGUED = "catalogued"


def _clean(value: str, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{what} must be a non-empty string")
    return value.strip()


@dataclass
class Item:
    id: str
    raw: str
    stage: str = STAGE_INTAKE
    measurements: dict = field(default_factory=dict)
    label: str = ""
    credits: list = field(default_factory=list)  # [(stage, analyst)]


class ClassificationPipeline:
    """Piece-rate classification: measure -> classify -> catalogue."""

    def __init__(self) -> None:
        self._items: dict[str, Item] = {}
        self._labels: set[str] = set()

    # -- taxonomy ------------------------------------------------------
    def define_label(self, label: str) -> str:
        """Add a label to the living taxonomy (Fleming's system)."""
        label = _clean(label, "label")
        if label in self._labels:
            raise ValueError(f"duplicate label: {label!r}")
        self._labels.add(label)
        return label

    def labels(self) -> list[str]:
        return sorted(self._labels)

    # -- the pipeline ----------------------------------------------------
    def add_item(self, item_id: str, raw: str) -> Item:
        """A raw plate arrives from Arequipa (intake)."""
        item_id = _clean(item_id, "item id")
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("raw plate data must be a non-empty string")
        if item_id in self._items:
            raise ValueError(f"duplicate item: {item_id!r}")
        item = Item(id=item_id, raw=raw.strip())
        self._items[item_id] = item
        return item

    def measure(self, item_id: str, measurements: dict, analyst: str) -> Item:
        """Measure the plate; credited as piece work to the analyst."""
        item = self._require(item_id)
        analyst = _clean(analyst, "analyst")
        if item.stage != STAGE_INTAKE:
            raise ValueError(f"item {item_id!r} already measured (stage={item.stage})")
        if not isinstance(measurements, dict) or not measurements:
            raise ValueError("measurements must be a non-empty dict")
        item.measurements = dict(measurements)
        item.stage = STAGE_MEASURED
        item.credits.append((STAGE_MEASURED, analyst))
        return item

    def classify(self, item_id: str, label: str, analyst: str) -> Item:
        """Classify against the shared taxonomy; doubtful plates belong
        here, kicked back up the chain — never past it."""
        item = self._require(item_id)
        label = _clean(label, "label")
        analyst = _clean(analyst, "analyst")
        if item.stage != STAGE_MEASURED:
            raise ValueError(
                f"item {item_id!r} must be measured before classification "
                f"(stage={item.stage})"
            )
        if label not in self._labels:
            raise ValueError(f"unknown label: {label!r}")
        item.label = label
        item.stage = STAGE_CLASSIFIED
        item.credits.append((STAGE_CLASSIFIED, analyst))
        return item

    def catalogue(self, item_id: str, analyst: str) -> Item:
        """Enter the classified plate into the catalogue."""
        item = self._require(item_id)
        analyst = _clean(analyst, "analyst")
        if item.stage != STAGE_CLASSIFIED:
            raise ValueError(
                f"item {item_id!r} must be classified before cataloguing "
                f"(stage={item.stage})"
            )
        item.stage = STAGE_CATALOGUED
        item.credits.append((STAGE_CATALOGUED, analyst))
        return item

    # -- the Cannon operation ----------------------------------------------
    def compress(self, merges: dict[str, str]) -> dict[str, str]:
        """Merge old labels into new ones (O-B-A-F-G-K-M style).

        Every item carrying an old label is remapped; the old labels leave
        the taxonomy. Returns the applied remap {old: new}.
        """
        if not isinstance(merges, dict) or not merges:
            raise ValueError("merges must be a non-empty dict of old->new labels")
        remap: dict[str, str] = {}
        for old, new in merges.items():
            old = _clean(old, "old label")
            new = _clean(new, "new label")
            if old not in self._labels:
                raise ValueError(f"unknown label to compress: {old!r}")
            if new not in self._labels:
                raise ValueError(f"unknown compression target: {new!r}")
            if old == new:
                raise ValueError(f"cannot merge label {old!r} into itself")
            remap[old] = new
        for item in self._items.values():
            if item.label in remap:
                item.label = remap[item.label]
        for old in remap:
            self._labels.discard(old)
        return remap

    # -- piece accounting ----------------------------------------------------
    def throughput(self) -> dict[str, dict[str, int]]:
        """The pay slip: per-analyst piece counts per stage."""
        tally: dict[str, dict[str, int]] = {}
        for item in self._items.values():
            for stage, analyst in item.credits:
                row = tally.setdefault(analyst, {"pieces": 0})
                row[stage] = row.get(stage, 0) + 1
                row["pieces"] += 1
        return tally

    # -- internals -------------------------------------------------------------
    def _require(self, item_id: str) -> Item:
        item = self._items.get(item_id)
        if item is None:
            raise ValueError(f"unknown item: {item_id!r}")
        return item
