"""hypercube: dimensional projection; deep theoretical recursion (LEVI-native).

Canon role (ORGANISM_FORMS): "dimensional projection; deep theoretical
recursion".

Canon evidence (founder corpus: copilot-sweep/ser13-18-21-master-conversation.md):
  - "HyperCube (Projection) — deep theoretical recursion
    (hypercube_projection.py)."
  - SER-21 (World Model) maps to SER-18 Core, Oracle, HyperCube, OmniPulse.
  - Quetta-Scale Matrix: "21 shells x 315 forms x quetta-scale recursion
    indices (QID)"; "QID = (shell 1-21, form 1-315, logic state 1-13,
    recursion index 0-10^30) — each QID a 'cubie' in the hyper-cube."
  - "HyperCube explores high-depth projections."

This is a LEVI-native recreation with LEVI's own twist — never a copy of
the original code. HyperCube projects QID tuples onto a unit hyper-cube
(``[0, 1)^3``: shell/form/logic-state axes) via a stable, deterministic
hash — pure functions, stdlib only (``hashlib.blake2b``):

  - :func:`project`: (shell, form, logic_state, recursion=0) ->
    (x, y, z) in [0, 1)^3. Deterministic: same QID, same cubie, forever.
  - :func:`cubie`: the full projection record, including the SER-18 phase
    name and SER-13 state name when the name tables are seated.
  - Fail-closed: every coordinate is validated against the canon ranges
    (``levi.cybrus.qid``); out-of-range inputs raise ValueError, non-integer
    inputs raise ValueError — hostile inputs are rejected, never projected.

HONESTY LAW: this is a stable coordinate hash for addressing and
visualization — a map, not the territory. It does not perform real
dimensional recursion, does not "explore" anything, and is one-way
(projection is not invertible: many QIDs can share a neighborhood, and
the module never claims a unique inverse).

Ready-for-review by the keeper. Never claims his review.
"""

from __future__ import annotations

import hashlib
import struct
from typing import Any, Dict, Tuple

from levi.cybrus import qid

FORM_NAME = "hypercube"
AXES = ("shell", "form", "logic_state")
_CUBE_MIN, _CUBE_MAX = qid.FORM_MIN, qid.FORM_MAX  # 1..315 shared form range


def _check(name: str, value: Any, lo: int, hi: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an int, got {value!r}")
    if not lo <= value <= hi:
        raise ValueError(f"{name} must be in [{lo}, {hi}] (canon range), got {value}")
    return value


def _axis(value: int, salt: bytes) -> float:
    """One unit-axis coordinate: stable blake2b digest -> [0, 1)."""
    digest = hashlib.blake2b(
        str(value).encode("utf-8"), digest_size=8, key=salt
    ).digest()
    return struct.unpack(">Q", digest)[0] / 2**64


def project(
    shell: int,
    form: int,
    logic_state: int,
    recursion: int = 0,
) -> Tuple[float, float, float]:
    """Project a QID tuple onto the unit hyper-cube.

    (shell, form, logic_state) set the three axes; ``recursion`` perturbs
    them deterministically (a fixed rotation, not a new dimension).
    """
    _check("shell", shell, qid.FORM_MIN, 21)
    _check("form", form, qid.FORM_MIN, qid.FORM_MAX)
    _check("logic_state", logic_state, qid.LOGIC_STATE_MIN, qid.LOGIC_STATE_MAX)
    _check("recursion", recursion, qid.RECURSION_MIN, qid.RECURSION_MAX)

    x = _axis(shell, b"hypercube:shell")
    y = _axis(form, b"hypercube:form")
    z = _axis(logic_state, b"hypercube:logic")

    if recursion:
        # Deterministic fixed-point rotation of the axes by the recursion
        # index. Depth changes WHERE the cubie sits, never which cube.
        r = (recursion % 360) / 360.0
        x, y, z = (
            (x + r) % 1.0,
            (y + 2 * r) % 1.0,
            (z + 3 * r) % 1.0,
        )
    return (round(x, 6), round(y, 6), round(z, 6))


def cubie(
    shell: int, form: int, logic_state: int, recursion: int = 0
) -> Dict[str, Any]:
    """The full projection record for one QID 'cubie'."""
    coords = project(shell, form, logic_state, recursion)
    phase = qid.PHASE_NAMES[form - 1] if qid.PHASE_NAMES else None
    state = qid.STATE_NAMES[logic_state - 1] if qid.STATE_NAMES else None
    return {
        "form": FORM_NAME,
        "qid": {
            "shell": shell,
            "form": form,
            "logic_state": logic_state,
            "recursion": recursion,
        },
        "projection": {"x": coords[0], "y": coords[1], "z": coords[2]},
        "phase_name": phase,  # None until the SER-18 canon tables are seated
        "state_name": state,
        "honest_limit": (
            "projection is a stable coordinate hash (map, not territory); "
            "one-way — no inverse lookup is offered or claimed"
        ),
    }


def capabilities() -> Dict[str, Any]:
    return {
        "form": FORM_NAME,
        "axes": list(AXES),
        "projection": "deterministic blake2b unit-cube projection, pure function",
        "name_tables_seated": bool(qid.PHASE_NAMES and qid.STATE_NAMES),
        "honest_limit": (
            "HyperCube addresses and visualizes the QID space; it does not "
            "perform dimensional recursion or explore real depths"
        ),
    }
