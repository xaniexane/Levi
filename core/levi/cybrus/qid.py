"""QID addressing for Cybrus — "QID = address of thought".

A QID names a point in the canonical coordinate space::

    shell.form.logic_state.recursion   e.g.  "3.42.7.0"

Ranges (canonical, enforced):
- ``shell``:        1..21
- ``form``:         1..315
- ``logic_state``:  1..13
- ``recursion``:    0..10**30

Name tables (the 18 SER-18 phase names, the 13 SER-13 state names) live in
the canonical master spec (SER-13/18/21 conversation, 2026-07-05/06). That
spec file is not present in this build, so the tables are intentionally
**empty by default** — nothing here invents the canonical names. They can
be loaded at runtime via :func:`register_spec_tables` (from the spec file
when it is available), which validates the exact counts (18 / 13).
Numeric range validation always applies, with or without the tables.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

SHELL_MIN, SHELL_MAX = 1, 21
FORM_MIN, FORM_MAX = 1, 315
LOGIC_STATE_MIN, LOGIC_STATE_MAX = 1, 13
RECURSION_MIN, RECURSION_MAX = 0, 10**30

#: Canonical SER-18 phase names (18). Empty until loaded from the spec —
#: see module docstring. Never invented here.
PHASE_NAMES: List[str] = []

#: Canonical SER-13 state names (13). Empty until loaded from the spec.
STATE_NAMES: List[str] = []


def register_spec_tables(phases: List[str], states: List[str]) -> None:
    """Load the canonical name tables (e.g. from the master spec file).

    Validates the exact canonical counts — 18 phase names, 13 state names —
    and that every entry is a non-empty string. Raises :class:`ValueError`
    otherwise.
    """
    if len(phases) != 18:
        raise ValueError(
            f"canonical SER-18 table must hold exactly 18 phase names, "
            f"got {len(phases)}"
        )
    if len(states) != 13:
        raise ValueError(
            f"canonical SER-13 table must hold exactly 13 state names, "
            f"got {len(states)}"
        )
    for table, what in ((phases, "phase"), (states, "state")):
        for name in table:
            if not isinstance(name, str) or not name.strip():
                raise ValueError(f"canonical {what} names must be non-empty strings")
    global PHASE_NAMES, STATE_NAMES
    PHASE_NAMES = [name.strip() for name in phases]
    STATE_NAMES = [name.strip() for name in states]


def load_spec_tables(path: str | Path) -> None:
    """Load name tables from a JSON spec file of the shape
    ``{"phases": [...18 strings...], "states": [...13 strings...]}``."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    register_spec_tables(data["phases"], data["states"])


def _check_range(name: str, value: int, lo: int, hi: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"QID {name} must be an int, got {value!r}")
    if not (lo <= value <= hi):
        raise ValueError(
            f"QID {name} out of range: {value} (canonical range {lo}..{hi})"
        )
    return value


@dataclass(frozen=True)
class QID:
    """A validated address of thought: shell.form.logic_state.recursion."""

    shell: int
    form: int
    logic_state: int
    recursion: int

    def __post_init__(self) -> None:
        _check_range("shell", self.shell, SHELL_MIN, SHELL_MAX)
        _check_range("form", self.form, FORM_MIN, FORM_MAX)
        _check_range("logic_state", self.logic_state, LOGIC_STATE_MIN, LOGIC_STATE_MAX)
        _check_range("recursion", self.recursion, RECURSION_MIN, RECURSION_MAX)

    @classmethod
    def parse(cls, text: str) -> "QID":
        """Parse ``"s.f.l.r"`` into a validated :class:`QID`. Raises
        :class:`ValueError` on malformed input or out-of-range components."""
        if not isinstance(text, str):
            raise ValueError(f"QID must be a string, got {type(text).__name__}")
        parts = text.strip().split(".")
        if len(parts) != 4:
            raise ValueError(
                f"malformed QID {text!r}: expected 'shell.form.logic_state.recursion'"
            )
        try:
            values = [int(part) for part in parts]
        except ValueError:
            raise ValueError(
                f"malformed QID {text!r}: all four components must be integers"
            ) from None
        return cls(*values)

    def __str__(self) -> str:
        return f"{self.shell}.{self.form}.{self.logic_state}.{self.recursion}"

    def phase_name(self) -> Optional[str]:
        """The SER-18 phase name for this QID's shell, or None when the
        canonical table has not been loaded."""
        if not PHASE_NAMES:
            return None
        return PHASE_NAMES[(self.shell - 1) % len(PHASE_NAMES)]

    def state_name(self) -> Optional[str]:
        """The SER-13 state name for this QID's logic_state, or None when
        the canonical table has not been loaded."""
        if not STATE_NAMES:
            return None
        return STATE_NAMES[(self.logic_state - 1) % len(STATE_NAMES)]
