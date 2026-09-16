"""measures — the museum of dead measures.

Pre-industrial measurement systems, revived as a working converter with
provenance. Every unit carries its master standard (the royal-cubit idea:
working rods were checked against a granite master, so the unit was
state-fixed even when body-anchored).

Honest limits: pre-modern units varied by city, trade, and century. Values
here are the conventional modern equivalents used by metrology references;
regional variants are flagged, never silently averaged. This is a museum
and a teaching tool, not a legal metrology instrument.

Units implemented from hunt wave-014 (lost crafts):
  arch-craft-egyptian-royal-cubit, arch-craft-roman-pes-actus,
  arch-craft-furlong-chain-rod-acre, plus barleycorn, toise, braccio,
  arshin/verst, shekel/mina/talent, hogshead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

METRE = "m"
KILOGRAM = "kg"
LITRE = "L"


@dataclass(frozen=True)
class Unit:
    """One historical unit with its master-standard provenance."""

    name: str
    symbol: str
    system: str  # e.g. "egyptian", "roman", "english", "french", ...
    era: str
    base_value: float  # in SI base (metres, kg, litres)
    base_unit: str  # METRE | KILOGRAM | LITRE
    master: str  # the master standard this unit is checked against
    note: str = ""
    variant: bool = False  # True when this value is one regional variant


_UNITS: Dict[str, Unit] = {}


def _add(unit: Unit) -> None:
    _UNITS[unit.name] = unit


# -- SI anchors (the museum's modern reference; the master all else converts to)
_add(
    Unit(
        "metre",
        "m",
        "si",
        "1799 - present",
        1.0,
        METRE,
        master="speed of light definition (2019 SI)",
        note="The unit that dethroned the toise.",
    )
)
_add(
    Unit(
        "kilogram",
        "kg",
        "si",
        "1799 - present",
        1.0,
        KILOGRAM,
        master="Planck constant definition (2019 SI)",
        note="",
    )
)
_add(
    Unit(
        "litre",
        "L",
        "si",
        "1799 - present",
        1.0,
        LITRE,
        master="1 cubic decimetre (2019 SI)",
        note="",
    )
)

# -- Egyptian (royal cubit master; Lepsius mean ~523.5-529.2 mm) ---------------
_add(
    Unit(
        "royal-cubit",
        "rc",
        "egyptian",
        "c. 2700 BC - Ptolemaic",
        0.5235,
        METRE,
        master="granite royal-cubit master (state-fixed)",
        note="7 palms = 28 digits. Body-anchored, state-fixed.",
    )
)
_add(
    Unit(
        "palm",
        "palm",
        "egyptian",
        "c. 2700 BC - Ptolemaic",
        0.5235 / 7,
        METRE,
        master="royal-cubit master / 7",
        note="1/7 royal cubit.",
    )
)
_add(
    Unit(
        "digit",
        "dgt",
        "egyptian",
        "c. 2700 BC - Ptolemaic",
        0.5235 / 28,
        METRE,
        master="royal-cubit master / 28",
        note="1/28 royal cubit = finger width.",
    )
)

# -- Roman (agrimensores; pes monetalis) ----------------------------------------
_add(
    Unit(
        "pes",
        "pes",
        "roman",
        "Roman Republic/Empire",
        0.296,
        METRE,
        master="pes monetalis (capitol standard)",
        note="Roman foot; 16 digiti.",
    )
)
_add(
    Unit(
        "passus",
        "passus",
        "roman",
        "Roman Republic/Empire",
        5 * 0.296,
        METRE,
        master="5 pedes",
        note="Double step; the mile is 1000 passus.",
    )
)
_add(
    Unit(
        "actus",
        "actus",
        "roman",
        "Roman Republic/Empire",
        120 * 0.296,
        METRE,
        master="120 pedes",
        note="Furrow length; basis of the iugerum.",
    )
)
_add(
    Unit(
        "iugerum",
        "iug",
        "roman",
        "Roman Republic/Empire",
        2 * (120 * 0.296) ** 2,
        METRE,
        master="2 square actus",
        note="Area unit (~2518 m^2); stored as square metres.",
    )
)

# -- English (Gunter's chain 1620; statute measures) -----------------------------
_barleycorn = 0.0254 / 3
_add(
    Unit(
        "barleycorn",
        "bc",
        "english",
        "medieval - 19th c.",
        _barleycorn,
        METRE,
        master="3 barleycorns = 1 inch (statute)",
        note="The inch's own origin story; still the shoe-size unit.",
    )
)
_add(
    Unit(
        "inch",
        "in",
        "english",
        "medieval - present",
        0.0254,
        METRE,
        master="international yard 1959",
        note="",
    )
)
_add(
    Unit(
        "foot",
        "ft",
        "english",
        "medieval - present",
        0.3048,
        METRE,
        master="international yard 1959",
        note="",
    )
)
_add(
    Unit(
        "yard",
        "yd",
        "english",
        "medieval - present",
        0.9144,
        METRE,
        master="international yard 1959",
        note="",
    )
)
_add(
    Unit(
        "rod",
        "rod",
        "english",
        "medieval - 19th c.",
        5.5 * 0.9144,
        METRE,
        master="5.5 yards (statute)",
        note="Also perch/pole.",
    )
)
_add(
    Unit(
        "chain",
        "ch",
        "english",
        "1620 (Gunter) - 19th c.",
        22 * 0.9144,
        METRE,
        master="Gunter's chain: 100 links = 4 rods",
        note="The decimal trick: 10 square chains = 1 acre exactly.",
    )
)
_add(
    Unit(
        "link",
        "lnk",
        "english",
        "1620 (Gunter) - 19th c.",
        22 * 0.9144 / 100,
        METRE,
        master="chain / 100",
        note="7.92 inches; the surveyor's digit.",
    )
)
_add(
    Unit(
        "furlong",
        "fur",
        "english",
        "medieval - 19th c.",
        220 * 0.9144,
        METRE,
        master="10 chains = 220 yards (statute)",
        note="Agronomic origin: how far oxen pull before resting.",
    )
)
_add(
    Unit(
        "mile",
        "mi",
        "english",
        "1593 (statute) - present",
        8 * 220 * 0.9144,
        METRE,
        master="8 furlongs (statute mile)",
        note="",
    )
)
_add(
    Unit(
        "acre",
        "ac",
        "english",
        "statute 16th c. - present",
        10 * (22 * 0.9144) ** 2,
        METRE,
        master="10 square chains (statute)",
        note="4840 sq yd; stored as square metres.",
    )
)

# -- French / Italian / Russian --------------------------------------------------
_add(
    Unit(
        "toise",
        "T",
        "french",
        "17th-18th c.",
        1.949,
        METRE,
        master="toise du Perou / du Nord (1747)",
        note="6 pieds du roi; the unit the metre replaced.",
    )
)
_add(
    Unit(
        "braccio",
        "br",
        "italian",
        "medieval - 19th c.",
        0.5836,
        METRE,
        master="Florentine braccio a panno (regional)",
        note="Varied wildly by city (0.58-0.68 m); this is Florence.",
        variant=True,
    )
)
_add(
    Unit(
        "arshin",
        "ar",
        "russian",
        "16th-19th c.",
        0.7112,
        METRE,
        master="Peter the Great standard 1701+",
        note="28 English inches by decree.",
    )
)
_add(
    Unit(
        "verst",
        "vst",
        "russian",
        "17th-19th c.",
        1066.8,
        METRE,
        master="500 sazhen (statute)",
        note="~2/3 statute mile.",
    )
)

# -- Weights (Near Eastern) -------------------------------------------------------
_add(
    Unit(
        "shekel",
        "sh",
        "near-eastern",
        "Bronze Age - antiquity",
        0.0114,
        KILOGRAM,
        master="royal weight stones (varied by kingdom)",
        note="~11.4 g; varied 8-14 g by place/period.",
        variant=True,
    )
)
_add(
    Unit(
        "mina",
        "mina",
        "near-eastern",
        "Bronze Age - antiquity",
        60 * 0.0114,
        KILOGRAM,
        master="60 shekels (sexagesimal)",
        note="",
    )
)
_add(
    Unit(
        "talent",
        "tal",
        "near-eastern",
        "Bronze Age - antiquity",
        60 * 60 * 0.0114,
        KILOGRAM,
        master="60 minas (sexagesimal)",
        note="~41 kg: a porter's load, hence the scale.",
    )
)

# -- Capacity ---------------------------------------------------------------------
_add(
    Unit(
        "hogshead",
        "hhd",
        "english",
        "15th-19th c.",
        238.5,
        LITRE,
        master="wine hogshead 63 gallons (statute, regional)",
        note="Varied by commodity and port; wine measure shown.",
        variant=True,
    )
)


def list_units(system: Optional[str] = None) -> List[Unit]:
    """All units, optionally filtered by system (egyptian/roman/english/...)."""
    units = sorted(_UNITS.values(), key=lambda u: (u.system, u.name))
    if system:
        units = [u for u in units if u.system == system]
    return units


def get_unit(name: str) -> Unit:
    """Look up a unit by name or symbol. Raises KeyError on unknown units."""
    key = name.strip().lower()
    if key in _UNITS:
        return _UNITS[key]
    for unit in _UNITS.values():
        if unit.symbol.lower() == key:
            return unit
    raise KeyError("unknown unit %r; see list_units()" % (name,))


def convert(value: float, from_unit: str, to_unit: str) -> float:
    """Convert value from one unit to another. Units must share a dimension.

    Raises ValueError on dimension mismatch (length vs weight vs capacity) —
    the museum refuses to weigh a furlong.
    """
    src = get_unit(from_unit)
    dst = get_unit(to_unit)
    if src.base_unit != dst.base_unit:
        raise ValueError(
            "dimension mismatch: %s is %s, %s is %s"
            % (src.name, src.base_unit, dst.name, dst.base_unit)
        )
    return value * src.base_value / dst.base_value


def describe(name: str) -> Dict[str, object]:
    """Full museum card for a unit, including master-standard provenance."""
    u = get_unit(name)
    return {
        "name": u.name,
        "symbol": u.symbol,
        "system": u.system,
        "era": u.era,
        "si_equivalent": u.base_value,
        "si_unit": u.base_unit,
        "master_standard": u.master,
        "note": u.note,
        "regional_variant": u.variant,
    }


def master_chain(name: str) -> str:
    """The provenance chain back to the master standard (royal-cubit idea)."""
    return "%s <- %s" % (get_unit(name).name, get_unit(name).master)


def chain_area(square_chains: float) -> float:
    """Gunter's decimal trick: area in acres from square chains.

    Because the acre is exactly 10 square chains, field data converts by
    moving a decimal point — no fractions, no error.
    """
    return square_chains / 10.0


def seked(rise: float, run: float) -> float:
    """Egyptian seked: palms of run per cubit of rise — slope as a ratio.

    Effectively cotangent arithmetic, millennia before trigonometry.
    """
    if rise <= 0:
        raise ValueError("rise must be positive")
    return (run / rise) * 7.0
