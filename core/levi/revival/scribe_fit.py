"""scribe_fit — scribe-rule joints: absorb irregularity, don't standardize.

Studied from: lost-crafts-20260916 — report.md [Batch 3]
(Scribe-Rule Timber Framing).

Load-bearing idea: in scribe-rule framing each timber stays its own
irregular shape; the carpenter scribes one piece against the other so
the *joint* absorbs the irregularity, while plumb and level stand as
the inerrant reference that never bends. LEVI's take: a ``ScribeBench``
joins irregular per-source payloads to one inerrant canonical schema
(the plumb/level). Instead of normalizing every source into the same
mold, each source gets a fitted *shim* — small correction functions
plus per-field offsets recorded at fit time. The canonical schema is
never modified by a shim; the shim only adapts the joint. Fitting is
measurable: ``misfit`` reports how much correction each joint needed.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


ORIGIN = "levi-revival/scribe-fit"


class ScribeError(Exception):
    """A joint cannot be scribed: the inerrant reference rejects the payload."""


# A correction maps a raw value to its fitted value. Signature: (value) -> value.
Correction = Callable[[Any], Any]


@dataclass
class Shim:
    """The fitted joint for one source: per-field corrections + offsets."""

    source: str
    corrections: Dict[str, Correction] = field(default_factory=dict)
    offsets: Dict[str, float] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def fit_value(self, field_name: str, value: Any) -> Any:
        if field_name in self.corrections:
            value = self.corrections[field_name](value)
        if field_name in self.offsets and isinstance(value, (int, float)):
            value = value + self.offsets[field_name]
        return value


@dataclass
class FieldRule:
    """One inerrant plumb/level rule: required, type, optional bounds."""

    dtype: type
    required: bool = True
    low: Optional[float] = None
    high: Optional[float] = None

    def check(self, name: str, value: Any) -> Any:
        if not isinstance(value, self.dtype):
            raise ScribeError(
                f"field {name!r}: expected {self.dtype.__name__}, "
                f"got {type(value).__name__}"
            )
        if self.low is not None and value < self.low:
            raise ScribeError(f"field {name!r}: {value} below plumb {self.low}")
        if self.high is not None and value > self.high:
            raise ScribeError(f"field {name!r}: {value} above level {self.high}")
        return value


class ScribeBench:
    """Fits irregular source payloads to one inerrant schema via shims."""

    def __init__(self, schema: Dict[str, FieldRule]) -> None:
        self.schema = dict(schema)  # the inerrant reference: never modified
        self.shims: Dict[str, Shim] = {}
        self._misfit: Dict[str, float] = {}  # source -> total correction magnitude

    # -- fitting the joint -------------------------------------------------

    def scribe(
        self,
        source: str,
        corrections: Optional[Dict[str, Correction]] = None,
        offsets: Optional[Dict[str, float]] = None,
        note: str = "",
    ) -> Shim:
        """Cut a shim for a source. The schema stays untouched."""
        shim = Shim(
            source=source,
            corrections=dict(corrections or {}),
            offsets=dict(offsets or {}),
        )
        if note:
            shim.notes.append(note)
        self.shims[source] = shim
        self._misfit[source] = sum(abs(v) for v in shim.offsets.values()) + float(
            len(shim.corrections)
        )
        return shim

    # -- joining: raw payload -> canonical record ---------------------------

    def join(self, source: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Scribe-fit a source payload against the plumb/level schema.

        Corrections absorb the irregularity; the returned record always
        satisfies the schema exactly. Raises ScribeError when even the
        shim cannot bring the joint true.
        """
        shim = self.shims.get(source, Shim(source=source))
        fitted: Dict[str, Any] = {}
        for name, rule in self.schema.items():
            if name in payload:
                fitted[name] = rule.check(name, shim.fit_value(name, payload[name]))
            elif rule.required:
                raise ScribeError(f"source {source!r}: missing required field {name!r}")
        # Extra keys in the payload are left at the door — the reference
        # defines the joint, not the timber.
        return fitted

    def misfit(self, source: str) -> float:
        """How much correction this joint needed. 0.0 = true fit, no shim."""
        return self._misfit.get(source, 0.0)

    def schema_names(self) -> List[str]:
        return list(self.schema)
