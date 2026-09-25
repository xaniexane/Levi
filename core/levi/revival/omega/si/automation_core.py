"""SI core: declarative spec -> automation-minion dicts, LEVI-native.

Takes a plain declarative spec like::

    {
        "name": "morning-rites",
        "minions": [
            {
                "id": "morning-weather-01",
                "category": "Productivity",
                "subcategory": "Weather",
                "trigger": "Time 06:30",
                "condition": "Always",
                "example_rite": "Read the forecast aloud, then stamp the journal.",
                "notes": "Keep it short: three lines, no more.",
            }
        ],
    }

and emits a list of dicts that construct :class:`levi.automation.minions.Minion`
exactly — every generated dict is validated by building the real
dataclass, so a spec that doesn't fit the schema is refused, never
silently mangled.

Spec rules (fail-closed):

- ``spec`` must be a dict with a non-empty ``"minions"`` list.
- Each minion needs non-empty ``id``, ``category``, ``trigger``.
- Minion ids must be unique and slug-shaped (``^[a-z0-9][a-z0-9-]*$``).
- Unknown keys are refused — the schema is the contract, not a hint.
- LEVI-native defaults fill the tool columns: empty tool references,
  ``bridge="local"``, ``usb_auto_launch="none"`` — LEVI wakes its own
  rites; it doesn't dial out to someone else's bridge.

Public surface: ``validate_spec(spec) -> List[str]``,
``generate_minions(spec) -> List[Dict[str, object]]`` (raises ValueError
on invalid specs), ``generate_minion_objects(spec) -> List[Minion]``.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from levi.automation.minions import Minion

ORIGIN = "levi-revival-omega/si/automation-core"
GENERATED_ORIGIN = "omega-automation-gen"

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

_REQUIRED_SPEC_KEYS = ("minions",)
_REQUIRED_BOT_KEYS = ("id", "category", "trigger")

# Every Minion field with a LEVI-native default. Bridge and usb_auto_launch
# are deliberately local: generated minions run on LEVI's own engine.
_BOT_DEFAULTS: Dict[str, Any] = {
    "subcategory": "General",
    "condition": "Always",
    "android_tool": "",
    "windows_tool": "",
    "mac_tool": "",
    "chrome_extension": "",
    "bridge": "local",
    "usb_auto_launch": "none",
    "hitl_type": "Notification",
    "example_rite": "",
    "notes": "",
    "incomplete": False,
    "signature_id": "",
}

_KNOWN_BOT_KEYS = set(_REQUIRED_BOT_KEYS) | set(_BOT_DEFAULTS)


def validate_spec(spec: Any) -> List[str]:
    """Return a list of spec problems; empty means the spec is valid."""
    errors: List[str] = []
    if not isinstance(spec, dict):
        return [f"spec must be a dict, got {type(spec).__name__}"]
    minions = spec.get("minions")
    if not isinstance(minions, list) or not minions:
        return ['spec needs a non-empty "minions" list']
    seen: set = set()
    for i, minion in enumerate(minions):
        where = f"minions[{i}]"
        if not isinstance(minion, dict):
            errors.append(f"{where}: must be a dict, got {type(minion).__name__}")
            continue
        for key in _REQUIRED_BOT_KEYS:
            value = minion.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{where}: missing or empty required field {key!r}")
        minion_id = minion.get("id")
        if isinstance(minion_id, str) and minion_id:
            if not _ID_RE.match(minion_id):
                errors.append(
                    f"{where}: id {minion_id!r} must be a slug "
                    "(lowercase letters, digits, dashes)"
                )
            if minion_id in seen:
                errors.append(f"{where}: duplicate id {minion_id!r}")
            seen.add(minion_id)
        unknown = sorted(set(minion) - _KNOWN_BOT_KEYS)
        if unknown:
            errors.append(f"{where}: unknown fields {unknown} — schema is closed")
    return errors


def _build_bot_dict(bot_spec: Dict[str, Any]) -> Dict[str, object]:
    """Merge defaults over the spec and validate via the real Minion schema."""
    kwargs: Dict[str, Any] = dict(_BOT_DEFAULTS)
    kwargs.update({k: v for k, v in bot_spec.items() if k in _KNOWN_BOT_KEYS})
    kwargs["origin"] = GENERATED_ORIGIN
    try:
        minion = Minion(**kwargs)  # the schema itself is the validator
    except TypeError as exc:
        raise ValueError(f"minion {bot_spec.get('id')!r}: {exc}") from exc
    return minion.to_dict()


def generate_minions(spec: Dict[str, Any]) -> List[Dict[str, object]]:
    """Generate Minion-compatible dicts; raise ValueError on an invalid spec."""
    errors = validate_spec(spec)
    if errors:
        raise ValueError(
            "invalid automation spec — refusing to generate:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )
    return [_build_bot_dict(minion) for minion in spec["minions"]]


def generate_minion_objects(spec: Dict[str, Any]) -> List[Minion]:
    """Same as ``generate_minions`` but returns real :class:`Minion` objects."""
    return [Minion(**d) for d in generate_minions(spec)]
