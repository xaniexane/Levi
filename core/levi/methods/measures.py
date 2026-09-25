"""The unit-conversion ladder: ten historical measure systems as data.

Covered archive records:
  arch-craft-egyptian-royal-cubit — royal cubit = 28 digits (7 palms of
    4 digits), ~52.4 cm.
  arch-craft-barleycorn-inch — inch = 3 barleycorns; 12 in = 1 ft;
    3 ft = 1 yd; 5.5 yd = 1 perch; acre = 160 square perches (area, so it
    stays out of the linear ladder).
  arch-craft-roman-pes-actus — pes ~296 mm; 12 unciae or 16 digiti to the
    pes; passus = 5 ft; actus = 120 ft; iugerum = 28,800 sq ft (area).
  arch-craft-furlong-chain-rod-acre — rod = 16.5 ft; furlong = 40 rods;
    Gunter's chain = 66 ft of 100 links; acre = 4,840 sq yd (area).
  arch-craft-english-ell — cloth ells: English 45 in., Scots ~37 in.,
    Flemish 27 in., yard-and-handful 40 in.
  arch-craft-french-toise — toise = 6 pieds du roi ~ 1.949 m, 864 lignes.
  arch-craft-russian-arshin-verst — vershok = 1/16 arshin; pyad = 1/4;
    arshin = 16 vershoks = 28 English inches = 71.12 cm; sazhen = 3
    arshins; verst = 500 sazhens.
  arch-craft-talent-mina-shekel — shekel ~8.3 g x 60 = mina x 60 = talent;
    Greek branch: 6 obols = 1 drachma, 100 drachmae = 1 mina,
    6,000 drachmae = 1 talent (reconciled here as 1 drachma = 0.6 shekel,
    so both branches share one self-consistent ladder).
  arch-craft-hogshead-firkin — ale/beer cask ladder in gallons: pin 4.5,
    firkin 9, kilderkin 18, barrel 36, hogshead 54, puncheon 72, butt 108,
    tun 216. Grounded on the imperial gallon (4.54609 L) as canonical.
  arch-craft-braccio — city arms in cm: Milan 59.5, Florence 58.3, Venice
    wool 68.3 vs silk 63.8.

What it is in LEVI: ConversionLadder — each system is a named chain of
(unit, ratio-to-base) links. ``convert`` walks one ladder; ``to_metric``
and ``from_metric`` pass through the metric canonical base (metres for
length, grams for weight, litres for capacity), which is also how
``convert_cross`` crosses between systems of the same dimension.

Honesty label: LOAD-BEARING — every factor below is grounded in its
record's summary; area units (acre, iugerum) are documented, not fudged
into linear ladders.

Deny-closed inputs: unknown systems, units not in the named system,
non-numeric or non-finite values, and cross-system conversions across
different dimensions are all rejected with ValueError.
"""

from __future__ import annotations

import math

__all__ = ["SYSTEMS", "ConversionLadder"]

# Each system: base unit, metric canonical unit, metric-per-base factor,
# and (unit name -> ratio to base). All factors grounded in the records.
_SYSTEMS: dict[str, dict] = {
    "egyptian": {
        "base": "digit",
        "metric_unit": "m",
        "metric_per_base": 0.524 / 28,  # royal cubit 28 digits ~ 52.4 cm
        "units": {"digit": 1, "palm": 4, "royal_cubit": 28},
    },
    "barleycorn": {
        "base": "barleycorn",
        "metric_unit": "m",
        "metric_per_base": 0.0254 / 3,  # inch = 3 grains = 2.54 cm
        "units": {
            "barleycorn": 1,
            "inch": 3,
            "foot": 36,
            "yard": 108,
            "perch": 594,
        },  # 5.5 yards = 594 barleycorns
    },
    "roman": {
        "base": "pes",
        "metric_unit": "m",
        "metric_per_base": 0.296,  # pes ~ 296 mm
        "units": {
            "digitus": 1 / 16,
            "uncia": 1 / 12,
            "pes": 1,
            "passus": 5,
            "actus": 120,
        },
    },
    "survey": {
        "base": "link",
        "metric_unit": "m",
        "metric_per_base": 66 * 0.3048 / 100,  # Gunter chain: 66 ft, 100 links
        "units": {
            "link": 1,
            "foot": 100 / 66,
            "yard": 100 / 22,
            "rod": 25,
            "chain": 100,
            "furlong": 1000,
        },
        # rod = 16.5 ft = 25 links; furlong = 40 rods = 1000 links
    },
    "ell": {
        "base": "inch",
        "metric_unit": "m",
        "metric_per_base": 0.0254,
        "units": {
            "inch": 1,
            "flemish_ell": 27,
            "scots_ell": 37,
            "yard_and_handful": 40,
            "english_cloth_ell": 45,
        },
    },
    "toise": {
        "base": "ligne",
        "metric_unit": "m",
        "metric_per_base": 1.949 / 864,  # toise ~ 1.949 m, 864 lignes
        "units": {"ligne": 1, "pied_du_roi": 144, "toise": 864},
    },
    "russian": {
        "base": "vershok",
        "metric_unit": "m",
        "metric_per_base": 0.7112 / 16,  # arshin 16 vershoks = 71.12 cm
        "units": {
            "vershok": 1,
            "pyad": 4,
            "arshin": 16,
            "sazhen": 48,
            "verst": 24000,
        },  # 500 sazhens of 48 vershoks
    },
    "weight": {
        "base": "shekel",
        "metric_unit": "g",
        "metric_per_base": 8.3,  # shekel ~ 8.3 g
        "units": {"shekel": 1, "obol": 0.1, "drachma": 0.6, "mina": 60, "talent": 3600},
        # 60 shekels = 1 mina = 100 drachmae -> drachma = 0.6 shekel
    },
    "cask": {
        "base": "gallon",
        "metric_unit": "L",
        "metric_per_base": 4.54609,  # imperial gallon, canonical
        "units": {
            "gallon": 1,
            "pin": 4.5,
            "firkin": 9,
            "kilderkin": 18,
            "barrel": 36,
            "hogshead": 54,
            "puncheon": 72,
            "butt": 108,
            "tun": 216,
        },
    },
    "braccio": {
        "base": "cm",
        "metric_unit": "m",
        "metric_per_base": 0.01,
        "units": {
            "cm": 1,
            "florence_braccio": 58.3,
            "milan_braccio": 59.5,
            "venice_silk_braccio": 63.8,
            "venice_wool_braccio": 68.3,
        },
    },
}

SYSTEMS = tuple(_SYSTEMS)


def _require_value(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"value must be a number, got {value!r}")
    if not math.isfinite(value):
        raise ValueError(f"value must be finite, got {value!r}")
    return float(value)


class ConversionLadder:
    """Ten historical measure systems, convertible within and across."""

    def __init__(self) -> None:
        self._systems = _SYSTEMS

    def systems(self) -> list[str]:
        return list(self._systems)

    def units(self, system: str) -> list[str]:
        return list(self._units(system))

    def dimension(self, system: str) -> str:
        """The metric canonical unit of a system: 'm', 'g', or 'L'."""
        return self._system(system)["metric_unit"]

    def _system(self, system: str) -> dict:
        spec = self._systems.get(system)
        if spec is None:
            raise ValueError(f"unknown system: {system!r}; known={list(self._systems)}")
        return spec

    def _units(self, system: str) -> dict[str, float]:
        return self._system(system)["units"]

    def _ratio(self, system: str, unit: str) -> float:
        ratio = self._units(system).get(unit)
        if ratio is None:
            raise ValueError(
                f"unknown unit {unit!r} in system {system!r}; "
                f"known={list(self._units(system))}"
            )
        return ratio

    # -- within one ladder -------------------------------------------------
    def convert(self, value: float, from_unit: str, to_unit: str, system: str) -> float:
        """Convert within one system via the base unit."""
        amount = _require_value(value)
        return amount * self._ratio(system, from_unit) / self._ratio(system, to_unit)

    # -- through the metric canonical base ---------------------------------
    def to_metric(self, value: float, unit: str, system: str) -> tuple[float, str]:
        """A measurement -> (canonical metric value, metric unit)."""
        amount = _require_value(value)
        spec = self._system(system)
        base_amount = amount * self._ratio(system, unit)
        return base_amount * spec["metric_per_base"], spec["metric_unit"]

    def from_metric(self, value: float, unit: str, system: str) -> float:
        """A canonical metric value -> the named historical unit."""
        amount = _require_value(value)
        spec = self._system(system)
        return (amount / spec["metric_per_base"]) / self._ratio(system, unit)

    def convert_cross(
        self,
        value: float,
        from_unit: str,
        from_system: str,
        to_unit: str,
        to_system: str,
    ) -> float:
        """Cross between systems via the metric canonical base.

        Only systems sharing a dimension (m, g, L) may cross.
        """
        metric_value, metric_unit = self.to_metric(value, from_unit, from_system)
        to_spec = self._system(to_system)
        if to_spec["metric_unit"] != metric_unit:
            raise ValueError(
                f"cannot cross dimensions: {from_system!r} is {metric_unit}, "
                f"{to_system!r} is {to_spec['metric_unit']}"
            )
        self._ratio(to_system, to_unit)  # deny-closed on the target unit
        return self.from_metric(metric_value, to_unit, to_system)
