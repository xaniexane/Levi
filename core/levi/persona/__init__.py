"""Persona layer — lenses, composition, canon guardrails, operator seats."""

from .seats import (  # noqa: F401
    SEATS,
    Seat,
    SeatError,
    all_seats,
    get as get_seat,
    provisional_notice,
    render as render_seat,
    suggest as suggest_seat,
    twin_facets,
)
