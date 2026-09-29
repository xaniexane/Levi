"""Units plugin — honest stdlib unit conversion as a connector plugin.

Where ``netcheck`` probes the network and ``weather`` reads the sky,
``units`` answers the desk question "how many X in Y" with pure math:
no network, no API, no fabrication — every conversion is an exact
factor chain through a per-category base unit (temperature excepted:
Celsius/Fahrenheit/Kelvin convert by the exact standard formulas).

Operations (all read-only; no confirmation gate can ever trigger):
* ``convert`` — convert a value between two units of the same category
  (params: ``value``, ``from``, ``to``);
* ``describe`` — list every category and its units
  (params: none, or ``category`` to narrow).

Honesty rules, deny-closed:
* unknown unit → ``invalid_params`` — never guess which unit was meant;
* cross-category conversion (meters → kilograms) → ``invalid_params``;
* unit aliases are explicit (``m``/``meter``/``metres``...), never fuzzy;
* temperature formulas use the exact offsets, not approximations;
* value must be a finite number — NaN/inf are refused.

``units`` is the reference converter ("units"), never LEVI identity.
Credentialless by design: ``credential()`` returns the ``"public"``
sentinel so the registry's credential gate never fires for reads.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from .registry import (
    Capability,
    Connector,
    InvalidParams,
    Operation,
    Transport,
    register_connector,
)

_REFERENCE = "units"

# Factors to the category's base unit. Aliases map to the canonical key.
_LENGTH = {
    "mm": 0.001,
    "millimeter": 0.001,
    "millimetre": 0.001,
    "cm": 0.01,
    "centimeter": 0.01,
    "centimetre": 0.01,
    "m": 1.0,
    "meter": 1.0,
    "metre": 1.0,
    "km": 1000.0,
    "kilometer": 1000.0,
    "kilometre": 1000.0,
    "in": 0.0254,
    "inch": 0.0254,
    "ft": 0.3048,
    "foot": 0.3048,
    "feet": 0.3048,
    "yd": 0.9144,
    "yard": 0.9144,
    "mi": 1609.344,
    "mile": 1609.344,
}
_MASS = {
    "g": 1.0,
    "gram": 1.0,
    "gramme": 1.0,
    "kg": 1000.0,
    "kilogram": 1000.0,
    "oz": 28.349523125,
    "ounce": 28.349523125,
    "lb": 453.59237,
    "pound": 453.59237,
    "lbs": 453.59237,
}
_VOLUME = {
    "ml": 1.0,
    "milliliter": 1.0,
    "millilitre": 1.0,
    "l": 1000.0,
    "liter": 1000.0,
    "litre": 1000.0,
    "cup": 236.5882365,
    "cups": 236.5882365,
    "floz": 29.5735295625,
    "fl-oz": 29.5735295625,
    "fluid-ounce": 29.5735295625,
    "qt": 946.352946,
    "quart": 946.352946,
    "gal": 3785.411784,
    "gallon": 3785.411784,
}
_TIME = {
    "s": 1.0,
    "sec": 1.0,
    "second": 1.0,
    "seconds": 1.0,
    "min": 60.0,
    "minute": 60.0,
    "minutes": 60.0,
    "h": 3600.0,
    "hr": 3600.0,
    "hour": 3600.0,
    "hours": 3600.0,
    "day": 86400.0,
    "days": 86400.0,
    "week": 604800.0,
    "weeks": 604800.0,
}
_SPEED = {
    "m/s": 1.0,
    "mps": 1.0,
    "km/h": 1000.0 / 3600.0,
    "kph": 1000.0 / 3600.0,
    "mph": 1609.344 / 3600.0,
    "ft/s": 0.3048,
    "fps": 0.3048,
}
_TEMPERATURES = ("c", "celsius", "f", "fahrenheit", "k", "kelvin")

_CATEGORIES: Dict[str, Dict[str, float]] = {
    "length": _LENGTH,
    "mass": _MASS,
    "volume": _VOLUME,
    "time": _TIME,
    "speed": _SPEED,
}


def _category_of(unit: str) -> Optional[str]:
    for cat, table in _CATEGORIES.items():
        if unit in table:
            return cat
    return "temperature" if unit in _TEMPERATURES else None


def _guard_number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidParams("value must be a number — nothing was converted.")
    v = float(value)
    if not math.isfinite(v):
        raise InvalidParams("value must be finite (no NaN/inf).")
    return v


def _guard_unit(unit: Any) -> str:
    if not isinstance(unit, str) or not unit.strip():
        raise InvalidParams("unit must be a non-empty string.")
    u = unit.strip().lower()
    if _category_of(u) is None:
        raise InvalidParams(f"unknown unit {unit!r} — conversion refused, not guessed.")
    return u


def _convert_temperature(value: float, src: str, dst: str) -> float:
    src_c = src[0]  # c | f | k — aliases all start with the same letter
    dst_c = dst[0]
    if src_c == dst_c:
        return value
    # to Celsius (exact)
    c = {"c": value, "f": (value - 32.0) * 5.0 / 9.0, "k": value - 273.15}[src_c]
    # from Celsius (exact)
    return {"c": c, "f": c * 9.0 / 5.0 + 32.0, "k": c + 273.15}[dst_c]


def convert(value: float, src: str, dst: str) -> Dict[str, Any]:
    """Pure conversion: value in ``dst`` units. Deny-closed."""
    v = _guard_number(value)
    s = _guard_unit(src)
    d = _guard_unit(dst)
    cat_s, cat_d = _category_of(s), _category_of(d)
    if cat_s != cat_d:
        raise InvalidParams(f"cannot convert {cat_s} to {cat_d} — same category only.")
    if cat_s == "temperature":
        result = _convert_temperature(v, s, d)
    else:
        table = _CATEGORIES[cat_s]
        result = v * table[s] / table[d]
    return {
        "value": v,
        "from": s,
        "to": d,
        "category": cat_s,
        "result": result,
    }


def describe(category: Optional[str] = None) -> Dict[str, Any]:
    """Every category and its canonical units."""
    if category is not None:
        cat = str(category).strip().lower()
        table = _CATEGORIES.get(cat)
        if table is None:
            if cat != "temperature":
                raise InvalidParams(f"unknown category {category!r}.")
            return {"category": "temperature", "units": sorted(set(_TEMPERATURES))}
        return {"category": cat, "units": sorted(set(table))}
    out: Dict[str, List[str]] = {
        cat: sorted(set(table)) for cat, table in _CATEGORIES.items()
    }
    out["temperature"] = sorted(set(_TEMPERATURES))
    return {"categories": out}


class UnitsConnector(Connector):
    """The stdlib unit-conversion connector plugin."""

    id = "units"
    reference = _REFERENCE
    credential_env_var = "LEVI_UNITS_TOKEN"  # never set: credentialless by design
    display_name = "Units"
    description = (
        "Exact stdlib unit conversion across length, mass, volume, "
        "temperature, time, and speed — deny-closed, credentialless."
    )
    capabilities = (
        Capability("read.units.convert", "Convert a value between same-category units"),
        Capability("read.units.describe", "List conversion categories and units"),
    )
    operations = (
        Operation(
            "convert",
            "Unit conversion (params: value, from, to)",
            params=("value", "from", "to"),
        ),
        Operation(
            "describe",
            "List units (params: category — optional)",
            params=("category",),
        ),
    )
    references = (_REFERENCE,)

    def credential(self) -> Optional[str]:
        return super().credential() or "public"

    def perform(
        self,
        operation: str,
        params: Dict[str, Any],
        token: Optional[str],
        transport: Transport | None,
    ) -> Any:
        if operation == "convert":
            return convert(params.get("value"), params.get("from"), params.get("to"))
        if operation == "describe":
            return describe(params.get("category"))
        raise InvalidParams(f"unknown operation {operation!r}.")


register_connector(UnitsConnector)
