"""alpha: the SI team's first mind — reasoning.

Alpha is LEVI's own deliberator: a task goes in, multi-step
propose -> critique -> verdict deliberation comes out. It routes over
the native-brain weights when they are genuinely usable and falls back
to the rules engine otherwise — and the verdict always states which
substrate reasoned.

SUBSTRATE CONTRACT (shared with the si_team worker — do not break):

- ``ALPHA_ROLE = "alpha"``
- ``probe_alpha() -> Optional[object]`` returns a reasoner exposing
  ``.reason(task: str) -> dict`` with keys ``answer``, ``substrate``,
  ``limits`` — or ``None`` if Alpha is unavailable. The prober calls
  this inside ``try/except ImportError``; keep this module import-light
  (stdlib only, no torch, no weights touched at import time).
"""

from __future__ import annotations

from typing import Any, Optional

ALPHA_ROLE = "alpha"

__all__ = ["ALPHA_ROLE", "probe_alpha", "Reasoner"]


def probe_alpha() -> Optional[Any]:
    """Return a reasoner with ``.reason(task) -> dict``, or None."""
    try:
        from .reason import Reasoner
    except Exception:  # pragma: no cover - defensive: contract says Optional
        return None
    try:
        return Reasoner()
    except Exception:  # pragma: no cover
        return None


def __getattr__(name: str) -> Any:
    # Lazy Reasoner: keeps ``import levi.alpha`` light for the prober.
    if name == "Reasoner":
        from .reason import Reasoner

        return Reasoner
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
