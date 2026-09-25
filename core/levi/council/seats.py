"""Council seats — the three LEVI-native minds.

No network, no keys, no external APIs. A seat is skipped (never an
error) when its mind is unavailable, with the reason recorded.
"""

from __future__ import annotations

from dataclasses import dataclass

from .minds import NativeBrainMind, RulesEngineMind, SpecialistsMind

SEAT_NATIVE_BRAIN = "native-brain"
SEAT_RULES_ENGINE = "rules-engine"
SEAT_SPECIALISTS = "specialists"

ALL_SEATS: tuple[str, ...] = (
    SEAT_NATIVE_BRAIN,
    SEAT_RULES_ENGINE,
    SEAT_SPECIALISTS,
)


@dataclass
class Seat:
    """One chair at the council table — always one of LEVI's own minds."""

    id: str
    available: bool
    label: str = ""
    note: str = ""


def detect_seats() -> list[Seat]:
    """Detect which LEVI minds can sit at the table right now."""
    seats: list[Seat] = []

    brain = NativeBrainMind()
    if brain.is_available():
        seats.append(
            Seat(
                id=SEAT_NATIVE_BRAIN,
                available=True,
                label="native-brain (LEVI's own trained brain)",
                note=brain.availability_note(),
            )
        )
    else:
        seats.append(
            Seat(
                id=SEAT_NATIVE_BRAIN,
                available=False,
                label="native-brain (LEVI's own trained brain)",
                note="skipped: %s (not an error)" % brain.availability_note(),
            )
        )

    rules = RulesEngineMind()
    seats.append(
        Seat(
            id=SEAT_RULES_ENGINE,
            available=True,
            label="rules-engine (deterministic symbolic mind)",
            note=rules.availability_note(),
        )
    )

    specs = SpecialistsMind()
    if specs.is_available():
        seats.append(
            Seat(
                id=SEAT_SPECIALISTS,
                available=True,
                label="specialists (LEVI's specialist personas)",
                note=specs.availability_note(),
            )
        )
    else:
        seats.append(
            Seat(
                id=SEAT_SPECIALISTS,
                available=False,
                label="specialists (LEVI's specialist personas)",
                note="skipped: %s (not an error)" % specs.availability_note(),
            )
        )

    return seats
