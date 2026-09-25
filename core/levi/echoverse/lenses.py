"""Echoverse lenses — the six Grok-named views (GROK 1, GROK 4).

minimal / maximal / inverse / constraint / deep / reframe.

L2: deterministic — for a fixed (seed, lens) the output is byte-identical
across processes (sha256-seeded, no randomness leaks).
L3: exactly these six; the names are Chauncey's via Grok, not invented.
GROK 5: REIM/RIEM fold into the inverse lens (invert -> recurse) + dream.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

from levi.echoverse.engine import BOUNDED_MARK
from levi.echoverse.laws import LENSES


def _h(seed: str, salt: str) -> int:
    return int(hashlib.sha256(f"{seed}|{salt}".encode("utf-8")).hexdigest()[:8], 16)


_MINIMAL_VIEWS = [
    "the smallest reversible step",
    "the one constraint that matters",
    "the single next action",
]
_MAXIMAL_VIEWS = [
    "the fullest expression of the seed",
    "every branch taken at once",
    "the seed at maximum scope",
]
_CONSTRAINT_VIEWS = [
    "under the tightest real constraint",
    "with half the resources",
    "against the hardest deadline",
]
_DEEP_VIEWS = [
    "the second-order consequences",
    "what this implies in a year",
    "the pattern beneath the pattern",
]
_REFRAME_VIEWS = [
    "the problem restated as an opportunity",
    "the inverse goal: what if the opposite were true",
    "the seed seen from the user's seat",
]


def _inverse_view(seed: str, h: int) -> Dict[str, Any]:
    """Inverse lens: invert -> recurse (REIM folded in, GROK 5)."""
    inversions = [
        f"do not pursue '{seed[:50]}'; pursue its absence and watch what breaks",
        f"assume '{seed[:50]}' already failed; work backwards to the cause",
        f"optimize for the opposite of '{seed[:50]}'; keep what still works",
    ]
    chosen = inversions[h % len(inversions)]
    return {
        "inversion": chosen,
        # recurse: one REIM-style forward pass on the inverted frame
        "recurse": f"Advance: {chosen[:60]}",
        "riem_note": "negative variants vault with extracted good qualities",
    }


def apply_lens(seed: str, lens: str) -> Dict[str, Any]:
    """Apply one lens to a seed. Deterministic (L2). Raises ValueError on unknown lens (L3)."""
    if lens not in LENSES:
        raise ValueError(f"unknown lens {lens!r}; lenses are exactly {LENSES}")
    seed = (seed or "silence").strip()
    h = _h(seed, f"lens:{lens}")
    if lens == "minimal":
        view: Any = {"view": _MINIMAL_VIEWS[h % 3], "discipline": "strip until reversible"}
    elif lens == "maximal":
        view = {"view": _MAXIMAL_VIEWS[h % 3], "discipline": "expand until the frame creaks"}
    elif lens == "inverse":
        view = _inverse_view(seed, h)
    elif lens == "constraint":
        view = {"view": _CONSTRAINT_VIEWS[h % 3], "discipline": "bind it, then move"}
    elif lens == "deep":
        view = {"view": _DEEP_VIEWS[h % 3], "discipline": "follow the implication chain"}
    else:  # reframe
        view = {"view": _REFRAME_VIEWS[h % 3], "discipline": "change the seat, keep the seed"}
    return {
        "lens": lens,
        "seed": seed,
        "mark": BOUNDED_MARK,
        **view,
    }


def all_lenses(seed: str) -> Dict[str, Dict[str, Any]]:
    """All six views of one seed, in canonical order."""
    return {lens: apply_lens(seed, lens) for lens in LENSES}


def lens_fingerprint(seed: str, lens: str) -> str:
    """Byte-stable fingerprint of a lens application (L2 proof hook)."""
    payload = json.dumps(apply_lens(seed, lens), sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
