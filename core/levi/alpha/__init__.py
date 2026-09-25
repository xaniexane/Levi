"""alpha: the builder seat — Echo's facet that builds.

Canon (Chauncey): ALPHA is the builder — it builds things. Alpha and
Omega are the same individual with two personalities, twin facets of
Echo: "Omega powered by Alpha"; "Alpha echoes Omega; the builder is
the daemon's echo."

One seat, two faces, one job — build:

- the deliberation core (``reason.py`` / ``si/``): Alpha's build-planning
  deliberation — propose build approaches -> critique -> verdict on the
  plan. Plan-first is the builder's law, and the verdict always states
  which substrate reasoned.
- the build engine (``build.py``): natural-language build intent routed
  into the E3-E6 tiered builder (plan -> tier gates -> apply), in the
  shape of the original alphaEngine: NL -> route -> build.

SUBSTRATE CONTRACT (shared with the si_team worker — do not break):

- ``ALPHA_ROLE = "alpha"``
- ``ALPHA_SEAT = "builder"`` (canon identity marker)
- ``probe_alpha() -> Optional[object]`` returns a reasoner exposing
  ``.reason(task: str) -> dict`` with keys ``answer``, ``substrate``,
  ``limits`` — or ``None`` if Alpha is unavailable. The prober calls
  this inside ``try/except ImportError``; keep this module import-light
  (stdlib only, no torch, no weights touched at import time).
"""

from __future__ import annotations

from typing import Any, Optional

ALPHA_ROLE = "alpha"
ALPHA_SEAT = "builder"

__all__ = ["ALPHA_ROLE", "ALPHA_SEAT", "probe_alpha", "Reasoner"]


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
