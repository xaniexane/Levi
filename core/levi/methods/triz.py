"""TRIZ contradiction matrix: innovation by indexed analogy.

Origin: Genrich Altshuller's Soviet-era Theory of Inventive Problem
Solving. After studying large numbers of patents, Altshuller found that
technical problems reduce to contradictions between 39 engineering
parameters — and that each (improving X, worsening Y) contradiction points
to a handful of 40 *inventive principles* that historically resolved it.
Look up the contradiction, get the principles to try.

What it is in LEVI: the assistant runs the TRIZ interview — "what are you
trying to improve? what gets worse when you do?" — maps your answers onto
the contradiction structure, and retrieves the relevant inventive
principles with concrete instantiation prompts. The AI holds the matrix;
you hold the judgment.

Honesty label: LOAD-BEARING for concrete technical contradictions — with
two caveats from the research: the "millions of patents" legend inflates
with retelling, and business-TRIZ stretches the patent-derived principles
past their evidence. Treat those claims as suggestive, not proven.

DATA HONESTY: the 39 parameters and 40 principles are encoded in full
(names + original one-line descriptions). The contradiction matrix itself
is a CURATED SUBSET of classic, frequently-cited cells — not the full
1521-cell table. Transcribing the entire matrix from memory would risk
shipping wrong cells; an unencoded pair returns no principles (never a
guess). ``coverage()`` lists exactly which pairs are encoded.

Deny-closed inputs: unknown parameter ids/names and principle ids are
rejected with ValueError.
"""

from __future__ import annotations

from typing import Optional

__all__ = [
    "PARAMETERS",
    "PRINCIPLES",
    "MATRIX",
    "resolve_parameter",
    "lookup",
    "describe_principle",
    "contradiction_report",
    "coverage",
]

# ---------------------------------------------------------------------------
# The 39 engineering parameters (Altshuller's standard list).
# ---------------------------------------------------------------------------
PARAMETERS: dict[int, str] = {
    1: "Weight of moving object",
    2: "Weight of stationary object",
    3: "Length of moving object",
    4: "Length of stationary object",
    5: "Area of moving object",
    6: "Area of stationary object",
    7: "Volume of moving object",
    8: "Volume of stationary object",
    9: "Speed",
    10: "Force (intensity)",
    11: "Stress or pressure",
    12: "Shape",
    13: "Stability of the object's composition",
    14: "Strength",
    15: "Duration of action by a moving object",
    16: "Duration of action by a stationary object",
    17: "Temperature",
    18: "Illumination intensity",
    19: "Use of energy by moving object",
    20: "Use of energy by stationary object",
    21: "Power",
    22: "Loss of energy",
    23: "Loss of substance",
    24: "Loss of information",
    25: "Loss of time",
    26: "Quantity of substance / the matter",
    27: "Reliability",
    28: "Measurement accuracy",
    29: "Manufacturing precision",
    30: "Object-affected harmful factors",
    31: "Object-generated harmful factors",
    32: "Ease of manufacture",
    33: "Ease of operation",
    34: "Ease of repair",
    35: "Adaptability or versatility",
    36: "Device complexity",
    37: "Difficulty of detecting and measuring",
    38: "Extent of automation",
    39: "Productivity",
}

# ---------------------------------------------------------------------------
# The 40 inventive principles: (name, one-line description).
# ---------------------------------------------------------------------------
PRINCIPLES: dict[int, tuple[str, str]] = {
    1: ("Segmentation", "Divide an object into independent parts; make it sectional or modular."),
    2: ("Taking out", "Separate the interfering part or property from the object."),
    3: ("Local quality", "Change a uniform structure into a non-uniform one; let each part serve its own function."),
    4: ("Asymmetry", "Replace symmetry with asymmetry."),
    5: ("Merging", "Bring together identical or similar objects; perform parallel operations."),
    6: ("Universality", "Make one part perform multiple functions, eliminating the need for others."),
    7: ("Nested doll", "Place one object inside another; let one pass through a cavity of the other."),
    8: ("Anti-weight", "Compensate for weight: join with something that provides lift, or work in a counter-gravitational field."),
    9: ("Preliminary anti-action", "Counteract an anticipated harmful action in advance."),
    10: ("Preliminary action", "Do the required action in advance, fully or partially; pre-arrange objects so they act at the right time and place."),
    11: ("Beforehand cushioning", "Prepare emergency means in advance to compensate for low reliability."),
    12: ("Equipotentiality", "Change working conditions so you don't have to lift or lower the object."),
    13: ("The other way round", "Invert the action; make movable parts fixed and fixed parts movable; turn the object upside down."),
    14: ("Spheroidality / curvature", "Replace flat/linear forms with curves; use rotation and centrifugal force."),
    15: ("Dynamics", "Let characteristics, shape, or process change to be optimal at each stage; divide into relatively movable parts."),
    16: ("Partial or excessive actions", "If 100% is hard, do slightly less or slightly more — overshoot, then remove the excess."),
    17: ("Another dimension", "Move from one dimension to two or three; use multiple layers instead of one."),
    18: ("Mechanical vibration", "Set the object into oscillation; increase frequency toward resonance."),
    19: ("Periodic action", "Replace continuous action with periodic or pulsating action."),
    20: ("Continuity of useful action", "Run all parts continuously at full load; eliminate idle and intermediate actions."),
    21: ("Skipping", "Conduct a process at high speed, skipping harmful or hazardous stages."),
    22: ("Blessing in disguise", "Use harmful factors — especially environmental ones — to get a positive effect."),
    23: ("Feedback", "Introduce feedback to improve a process or action."),
    24: ("Intermediary", "Use an intermediary carrier or process; temporarily merge with something easily removed."),
    25: ("Self-service", "Make the object service itself: auxiliary and repair operations become self-performed."),
    26: ("Copying", "Replace an expensive or fragile object with a simple inexpensive copy."),
    27: ("Cheap short-living objects", "Replace an expensive object with a multitude of inexpensive ones, accepting some loss of quality."),
    28: ("Mechanics substitution", "Replace mechanical means with sensory (optical, acoustic, taste, smell) means."),
    29: ("Pneumatics and hydraulics", "Use gas and liquid parts instead of solid parts."),
    30: ("Flexible shells and thin films", "Use flexible shells and thin films instead of three-dimensional structures."),
    31: ("Porous materials", "Make an object porous or add porous elements; fill pores with something useful."),
    32: ("Color changes", "Change the color or transparency of an object or its surroundings."),
    33: ("Homogeneity", "Make interacting objects of the same material or with close properties."),
    34: ("Discarding and recovering", "After it has served its purpose, discard (dissolve, evaporate) the part — or restore it during operation."),
    35: ("Parameter changes", "Change the physical state, concentration, flexibility, or temperature of the object."),
    36: ("Phase transitions", "Use phenomena occurring during phase transitions (volume change, heat release/absorption)."),
    37: ("Thermal expansion", "Use thermal expansion or contraction of materials, possibly in combination."),
    38: ("Strong oxidants", "Replace normal air with enriched air or oxygen; expose to ionizing radiation in oxygen."),
    39: ("Inert atmosphere", "Replace the normal environment with an inert one; run the process in vacuum."),
    40: ("Composite materials", "Replace homogeneous materials with composite ones."),
}

# ---------------------------------------------------------------------------
# Curated contradiction cells: (improving, worsening) -> principle ids.
# Classic, frequently-cited pairs only. See module docstring on coverage.
# ---------------------------------------------------------------------------
MATRIX: dict[tuple[int, int], tuple[int, ...]] = {
    # Lighter moving object, but it must stay strong (the textbook aircraft case).
    (1, 14): (1, 8, 15, 34),
    # Stronger, but it must stay light (the inverse contradiction).
    (14, 1): (1, 8, 40, 15),
    # More productive, but each unit must take less time
    # (the newsletter-frequency case from the research brief).
    (39, 25): (1, 10, 15),
    # More power, but less energy wasted.
    (21, 22): (19, 24, 26, 31),
    # More force, but the thing must stay strong.
    (10, 14): (8, 1, 37, 18),
    # More reliable, but the device must stay simple.
    (27, 36): (13, 35, 8, 24),
    # Simpler device, but it must stay reliable.
    (36, 27): (26, 24, 32, 28),
    # More productive, but the device must stay simple.
    (39, 36): (15, 10, 37, 28),
    # Longer action by the moving object, but less energy used doing it.
    (15, 19): (19, 5, 34, 31),
}


def resolve_parameter(ref: object) -> int:
    """Resolve a parameter id, full name, or unambiguous name fragment to its id."""
    if isinstance(ref, int):
        if ref in PARAMETERS:
            return ref
        raise ValueError(f"unknown TRIZ parameter id: {ref!r} (1..39)")
    if isinstance(ref, str) and ref.strip():
        text = ref.strip().lower()
        if text.isdigit() and int(text) in PARAMETERS:
            return int(text)
        matches = [pid for pid, name in PARAMETERS.items() if text in name.lower()]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise ValueError(f"no TRIZ parameter matches {ref!r}")
        raise ValueError(f"ambiguous TRIZ parameter {ref!r}: matches "
                         + ", ".join(f"{p} ({PARAMETERS[p]})" for p in matches))
    raise ValueError(f"parameter reference must be an id or name, got {ref!r}")


def describe_principle(principle_id: int) -> dict:
    """Name, description, and an instantiation prompt for one principle."""
    if principle_id not in PRINCIPLES:
        raise ValueError(f"unknown inventive principle: {principle_id!r} (1..40)")
    name, description = PRINCIPLES[principle_id]
    return {
        "id": principle_id,
        "name": name,
        "description": description,
        "try_this": f"How could '{name}' apply here? {description} "
                    "Name one concrete change in your domain that does this.",
    }


def lookup(improving: object, worsening: object) -> list[dict]:
    """Principles the classic matrix suggests for (improving, worsening).

    Returns [] when the pair is not in the curated subset — an honest
    unknown, never a guess. See ``coverage()``.
    """
    imp = resolve_parameter(improving)
    wor = resolve_parameter(worsening)
    if imp == wor:
        raise ValueError("improving and worsening must be different parameters")
    ids = MATRIX.get((imp, wor), ())
    return [describe_principle(pid) for pid in ids]


def contradiction_report(improving: object, worsening: object) -> dict:
    """The TRIZ interview result: the contradiction, the principles, next steps."""
    imp = resolve_parameter(improving)
    wor = resolve_parameter(worsening)
    principles = lookup(imp, wor)
    return {
        "improving": {"id": imp, "name": PARAMETERS[imp]},
        "worsening": {"id": wor, "name": PARAMETERS[wor]},
        "contradiction": f"Improve '{PARAMETERS[imp]}' without worsening '{PARAMETERS[wor]}'.",
        "principles": principles,
        "in_matrix": (imp, wor) in MATRIX,
        "guidance": (
            "Work the principles in order; for each, write one concrete "
            "instantiation in your domain before judging it."
            if principles else
            "This pair is outside the curated subset — consult the full "
            "published Altshuller matrix for this contradiction rather than "
            "guessing from the principles list."
        ),
    }


def coverage() -> dict:
    """Exactly which contradiction pairs are encoded (the honest coverage map)."""
    pairs = sorted(MATRIX)
    return {
        "parameters_encoded": len(PARAMETERS),
        "principles_encoded": len(PRINCIPLES),
        "matrix_cells_encoded": len(pairs),
        "matrix_cells_possible": 39 * 39,
        "note": "Curated subset of classic cells; unencoded pairs return [].",
        "encoded_pairs": [
            {"improving": PARAMETERS[i], "worsening": PARAMETERS[w],
             "principles": list(MATRIX[(i, w)])}
            for i, w in pairs
        ],
    }
