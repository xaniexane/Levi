"""Companion lenses for LEVI — lenses, not identities.

The higher-order companion layer on top of the PersonaLattice roster:
friend, mentor, challenger, protector, trickster, archivist.

Stdlib only.
"""

from levi.personas.lenses import (
    DEFAULT_LENS,
    LENS_LAW,
    LENSES,
    Lens,
    Tone,
    active_lens,
    active_lens_id,
    get_lens,
    list_lenses,
    register_into_lattice,
    set_active_lens,
)

from levi.personas.signal_lenses import (
    SIGNAL_LENSES,
    get_signal_lens,
    list_signal_lenses,
    register_signal_lenses_into_lattice,
)

from levi.personas.mode_lenses import (
    MODE_LENSES,
    get_mode_lens,
    list_mode_lenses,
    register_mode_lenses_into_lattice,
)

from levi.personas.duty_lenses import (
    DEFAULT_DUTY_LENS,
    DUTY_LAW,
    DUTY_LENSES,
    get_duty_lens,
    list_duty_lenses,
    register_duty_lenses_into_lattice,
)

__all__ = [
    "DEFAULT_LENS",
    "DEFAULT_DUTY_LENS",
    "LENS_LAW",
    "DUTY_LAW",
    "LENSES",
    "SIGNAL_LENSES",
    "MODE_LENSES",
    "DUTY_LENSES",
    "Lens",
    "Tone",
    "active_lens",
    "active_lens_id",
    "get_lens",
    "get_signal_lens",
    "get_mode_lens",
    "get_duty_lens",
    "list_lenses",
    "list_signal_lenses",
    "list_mode_lenses",
    "list_duty_lenses",
    "register_into_lattice",
    "register_signal_lenses_into_lattice",
    "register_mode_lenses_into_lattice",
    "register_duty_lenses_into_lattice",
    "set_active_lens",
]
