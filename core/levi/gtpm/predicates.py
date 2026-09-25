"""The closed contact-predicate language shared by the scan-mind and the
rule-reflex layer.

Working module name — **naming is Chauncey's**.

GTPM framing (Chauncey): "Basically analyzing but pure deterministic. I call
it goal targeted predator mentality." These predicates are the predator's
senses: the complete, fixed set of conditions it may test against a frozen
process image. The set is closed by design — adding a predicate is a spec
change with a test, never an ad-hoc extension. No arbitrary code in
contacts; predicates are data.

Semantics (per the scan-mind formal spec, section 4):
- ``is_true`` / ``is_false``: truthiness of the signal in the image. A
  missing signal is falsy (``is_true`` → False, ``is_false`` → True).
- ``eq`` / ``neq``: equality against ``value``. Missing signal → ``eq``
  is False, ``neq`` is True.
- ``gt`` / ``lt`` / ``gte`` / ``lte``: ordered comparison, numeric or
  lexicographic. Type mismatch → False (never an exception).
- ``changed``: ``image[s] != prev_image[s]``. With no previous image,
  always False.
- ``present``: the signal exists in the image at all.

``eval_contact`` is pure: no I/O, no clock, no randomness. Determinism is
structural.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

ORIGIN = "levi-gtpm/predicates"

PREDICATES = (
    "is_true",
    "is_false",
    "eq",
    "neq",
    "gt",
    "lt",
    "gte",
    "lte",
    "changed",
    "present",
)

_MISSING = object()


def eval_contact(
    contact: Dict[str, Any],
    image: Dict[str, Any],
    prev_image: Optional[Dict[str, Any]] = None,
) -> bool:
    """Evaluate one contact against a frozen process image.

    ``contact`` is ``{"signal": str, "pred": str, "value": any}``
    (``value`` only used by the comparison predicates). Raises
    ``ValueError`` on an unknown predicate or a malformed contact —
    fail-closed, never a guessed False.
    """
    if not isinstance(contact, dict):
        raise ValueError(f"contact must be a dict, got {type(contact).__name__}")
    pred = contact.get("pred")
    signal = contact.get("signal")
    if pred not in PREDICATES:
        raise ValueError(
            f"unknown predicate {pred!r}; closed set is {PREDICATES}"
        )
    if not isinstance(signal, str) or not signal:
        raise ValueError("contact needs a non-empty string 'signal'")

    present = signal in image
    value = image.get(signal, _MISSING)

    if pred == "present":
        return present
    if pred == "is_true":
        return present and bool(value)
    if pred == "is_false":
        return not present or not bool(value)
    if pred == "eq":
        return present and value == contact.get("value")
    if pred == "neq":
        return not present or value != contact.get("value")
    if pred == "changed":
        if prev_image is None or not present:
            return False
        return value != prev_image.get(signal, _MISSING)
    # Ordered comparisons: type mismatch is False, never an exception.
    if not present:
        return False
    other = contact.get("value")
    try:
        if pred == "gt":
            return bool(value > other)
        if pred == "lt":
            return bool(value < other)
        if pred == "gte":
            return bool(value >= other)
        if pred == "lte":
            return bool(value <= other)
    except TypeError:
        return False
    raise AssertionError(f"unreachable predicate {pred!r}")


__all__ = ["ORIGIN", "PREDICATES", "eval_contact"]
