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

__all__ = [
    "DEFAULT_LENS",
    "LENS_LAW",
    "LENSES",
    "SIGNAL_LENSES",
    "Lens",
    "Tone",
    "active_lens",
    "active_lens_id",
    "get_lens",
    "get_signal_lens",
    "list_lenses",
    "list_signal_lenses",
    "register_into_lattice",
    "register_signal_lenses_into_lattice",
    "set_active_lens",
]
