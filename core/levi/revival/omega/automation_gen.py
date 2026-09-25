"""Omega automation generator: declarative spec -> Minion-compatible dicts.

Organ-facing API over the SI core (``levi.revival.omega.si.automation_core``).
The real logic lives in the core; this module is the organ's front door.

Public surface:

- ``validate_spec(spec)`` — list of spec problems (empty = valid).
- ``generate_minions(spec)`` — ``List[Dict]``; raises ``ValueError`` on
  invalid specs. Every dict constructs :class:`levi.automation.minions.Minion`.
- ``generate_minion_objects(spec)`` — real ``Minion`` objects.
- ``spec_from_json(text)`` — parse a CLI-supplied JSON spec.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from levi.automation.minions import Minion

from .si.automation_core import (
    GENERATED_ORIGIN,
    ORIGIN,
    generate_minion_objects,
    generate_minions,
    validate_spec,
)

__all__ = [
    "ORIGIN",
    "GENERATED_ORIGIN",
    "Minion",
    "validate_spec",
    "generate_minions",
    "generate_minion_objects",
    "spec_from_json",
]


def spec_from_json(text: str) -> Dict[str, Any]:
    """Parse a JSON spec string; raise ValueError with a plain reason."""
    try:
        spec = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"spec is not valid JSON: {exc}") from exc
    if not isinstance(spec, dict):
        raise ValueError(f"spec must be a JSON object, got {type(spec).__name__}")
    return spec
