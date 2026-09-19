"""Faceted classification: build any subject from five facets at cataloging time.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #12)

The load-bearing mechanism is analytico-synthetic classification. Instead
of enumerating every possible subject in a fixed hierarchy, analyze a
subject into its facet values and *synthesize* a class number mechanically:

    Personality : Matter : Energy : Space : Time

- **P**ersonality — the "who/what" the subject is about
- **M**atter — the material or properties involved
- **E**nergy — the process, action, or operation
- **S**pace — the place
- **T**ime — the period

Infinite subjects from finite facets: the synthesis needs no
pre-enumeration — any value may be used at cataloging time, so the
universe of subjects is *generated*, not listed. Facet order is fixed
(P before M before E before S before T) no matter what order you supply
the values in, and :meth:`ColonClass.parse` round-trips any notation back
to its facets.

This is an original, from-scratch LEVI implementation — no historical
code is used or copied. Stdlib only, no network.

Honesty: the mechanism revived is faceted synthesis with fixed facet
order. Not revived: any universalist claim that five facets suffice for
all knowledge — LEVI lets each collection register its own facet values,
and ad-hoc values are always allowed.
"""

from __future__ import annotations

import json
from pathlib import Path


ORIGIN = "levi-revival/colonclass"


FACETS = ("Personality", "Matter", "Energy", "Space", "Time")
_FACET_KEYS = ("P", "M", "E", "S", "T")
_SEPARATOR = ":"
_INNER = ";"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ColonClassError(Exception):
    """Base class for colon-classification failures."""


class NotationError(ColonClassError):
    """A notation string could not be parsed."""


# ---------------------------------------------------------------------------
# Notation
# ---------------------------------------------------------------------------


def _clean(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("facet values must be non-empty")
    if _SEPARATOR in value or _INNER in value:
        raise ValueError(
            f"facet values may not contain {(_SEPARATOR + _INNER)!r}: {value!r}"
        )
    return value


def synthesize(**facets: str | list[str]) -> str:
    """Build a facet-ordered notation string from any facet values.

    Accepts facet names (``personality=...``) or single letters
    (``P=...``); each facet takes one value or a list (joined with
    ``;``). Facets come out in P-M-E-S-T order regardless of input order.
    At least one facet is required.
    """
    keymap = {k: k for k in _FACET_KEYS}
    keymap.update({k.lower(): k for k in _FACET_KEYS})
    keymap.update({f[0].upper(): f[0].upper() for f in FACETS})
    keymap.update({f.lower(): f[0].upper() for f in FACETS})
    keymap.update({f.upper(): f[0].upper() for f in FACETS})

    ordered: dict[str, str] = {}
    for name, value in facets.items():
        key = keymap.get(name.strip())
        if key is None:
            raise ValueError(
                f"unknown facet {name!r}; use P/M/E/S/T or Personality/Matter/Energy/Space/Time"
            )
        values = value if isinstance(value, (list, tuple)) else [value]
        ordered[key] = _INNER.join(_clean(str(v)) for v in values)

    if not ordered:
        raise ValueError("at least one facet value is required")
    return _SEPARATOR.join(ordered[k] for k in _FACET_KEYS if k in ordered)


def parse(notation: str) -> dict[str, str | list[str]]:
    """Split a notation back into its facets, in facet order. A facet with
    ``;``-joined values returns a list."""
    if not notation or not notation.strip():
        raise NotationError("empty notation")
    parts = notation.strip().split(_SEPARATOR)
    if len(parts) > len(_FACET_KEYS):
        raise NotationError(f"too many facet groups in {notation!r}")
    result: dict[str, str | list[str]] = {}
    for key, part in zip(_FACET_KEYS, parts, strict=False):
        if _INNER in part:
            result[key] = part.split(_INNER)
        else:
            result[key] = part
    return result


# ---------------------------------------------------------------------------
# The catalog
# ---------------------------------------------------------------------------


class ColonClass:
    """A faceted catalog: register facet vocabularies (optional), then
    synthesize subjects freely."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self.vocab: dict[str, list[str]] = {k: [] for k in _FACET_KEYS}
        self.entries: dict[str, dict] = {}  # title -> {notation, facets}
        if self.path is not None:
            self._load()

    # -- persistence ------------------------------------------------------
    def _file(self) -> Path:
        assert self.path is not None
        return self.path / "colonclass.json"

    def _load(self) -> None:
        f = self._file()
        if not f.exists():
            return
        data = json.loads(f.read_text(encoding="utf-8"))
        vocab = data.get("vocab", {})
        self.vocab = {k: list(vocab.get(k, [])) for k in _FACET_KEYS}
        self.entries = dict(data.get("entries", {}))

    def save(self) -> Path:
        """Persist the catalog. Only meaningful with a path."""
        if self.path is None:
            raise ColonClassError("no path: this catalog is in-memory only")
        self.path.mkdir(parents=True, exist_ok=True)
        target = self._file()
        tmp = target.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {"vocab": self.vocab, "entries": self.entries},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        tmp.replace(target)
        return target

    # -- vocabularies: finite facets, entirely optional ---------------------
    def define(self, facet: str, *values: str) -> list[str]:
        """Register allowed values for a facet. Purely a convenience —
        synthesis never requires registration."""
        key = self._facet_key(facet)
        for value in values:
            clean = _clean(value)
            if clean not in self.vocab[key]:
                self.vocab[key].append(clean)
        return list(self.vocab[key])

    def _facet_key(self, facet: str) -> str:
        f = facet.strip().lower()
        for full, key in zip(FACETS, _FACET_KEYS, strict=False):
            if f in (full.lower(), key.lower()):
                return key
        raise ValueError(f"unknown facet {facet!r}")

    # -- synthesis: the cataloging act --------------------------------------
    def catalog(self, title: str, **facets: str | list[str]) -> str:
        """Catalog a subject: analyze into facets, synthesize the notation,
        file the entry. Returns the notation."""
        if not title or not title.strip():
            raise ValueError("title must be non-empty")
        notation = synthesize(**facets)
        self.entries[title] = {"notation": notation, "facets": parse(notation)}
        return notation

    def notation_of(self, title: str) -> str:
        try:
            return self.entries[title]["notation"]
        except KeyError:
            raise ColonClassError(f"nothing cataloged under {title!r}") from None

    def subjects_in_facet(self, facet: str, value: str) -> list[str]:
        """Every cataloged subject sharing one facet value — pivoting the
        archive on a single facet."""
        key = self._facet_key(facet)
        hits = []
        for title, entry in self.entries.items():
            stored = entry["facets"].get(key)
            values = stored if isinstance(stored, list) else [stored]
            if _clean(value) in (values or []):
                hits.append(title)
        return sorted(hits)

    def titles(self) -> list[str]:
        return sorted(self.entries)


__all__ = [
    "ORIGIN",
    "FACETS",
    "ColonClassError",
    "NotationError",
    "synthesize",
    "parse",
    "ColonClass",
]
