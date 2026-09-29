"""Hicomb IDE: guarded access to the sibling-owned quetta_loop module.

``levi.hicomb.quetta_loop`` is sibling work and may be absent (untracked)
on a fresh checkout. Committed code must import cleanly either way: this
module loads with or without it, and any Quetta Pan loop stage fails
CLOSED with a clear error naming the missing module — never a bare
ImportError at module load.

Do NOT duplicate or reimplement quetta_loop here; do NOT commit the
sibling's file under another name. Glyph attribution is sacred.
"""

from __future__ import annotations

from typing import Any, Optional

__all__ = [
    "QuettaPanLoop",
    "QuettaPanUnavailable",
    "quetta_loop_available",
    "require_quetta_loop",
]


class QuettaPanUnavailable(RuntimeError):
    """Raised when a Quetta Pan loop stage is invoked without the module."""


try:
    from levi.hicomb.quetta_loop import QuettaPanLoop
    _IMPORT_ERROR: Optional[BaseException] = None
except ImportError as _exc:  # sibling module not yet committed — fail closed later
    QuettaPanLoop = None  # type: ignore[assignment]
    _IMPORT_ERROR = _exc


def quetta_loop_available() -> bool:
    """True when the sibling's quetta_loop module imported cleanly."""
    return QuettaPanLoop is not None


def require_quetta_loop() -> Any:
    """Return QuettaPanLoop, or raise QuettaPanUnavailable (fail closed).

    Call this at the point where the loop is actually needed — module
    import must never fail because of the missing sibling.
    """
    if QuettaPanLoop is None:
        raise QuettaPanUnavailable(
            "levi.hicomb.quetta_loop is not available in this checkout "
            "(sibling module not yet committed). The Quetta Pan loop stage "
            "cannot run — failing closed. "
            f"Underlying import error: {_IMPORT_ERROR}"
        )
    return QuettaPanLoop
