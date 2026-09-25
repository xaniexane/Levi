"""Pipeline position: Inquiry -> Mandella -> Echoverse -> AIM (L8).

The universal doctrine (GROK 1): GOAL -> Inquiry -> Mandella -> Echoverse
-> AIM -> success|failure -> teach if wrong -> titan absorb.

The Echoverse sits third: Inquiry maps, Mandella chooses paths, Echoverse
multiplies, then the winning path is AIMED at a body. This module is the
wiring — data only. aim() returns a PLAN and never executes anything.

AIM bodies (GROK 1):
  software -> surgeon / e3 / upgrade
  data     -> auto / zim
  music    -> echoplay
  device   -> battery / notify
  general  -> ask / expand
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from levi.echoverse.branches import EchoRun
from levi.echoverse.engine import BOUNDED_MARK
from levi.echoverse.laws import AIM_TARGETS, PIPELINE


def stages() -> List[str]:
    """The pipeline stage order. The Echoverse is third."""
    return list(PIPELINE)


def position() -> Dict[str, Any]:
    """Where the Echoverse sits and what flows in/out."""
    return {
        "stage": "echoverse",
        "index": PIPELINE.index("echoverse"),
        "receives_from": "mandella",
        "receives": "a chosen path (the stake)",
        "produces_for": "aim",
        "produces": "multiplied paths + a preferred path aimed at a body",
        "mark": BOUNDED_MARK,
    }


def aim(run: EchoRun, body: str) -> Dict[str, Any]:
    """Aim the run's preferred path at a body. Returns a PLAN (data) — never executes.

    The preferred path is the highest-optionality branch; ties keep
    branch order (deterministic).
    """
    if body not in AIM_TARGETS:
        raise ValueError(f"unknown body {body!r}; bodies are {sorted(AIM_TARGETS)}")
    preferred = max(run.branches, key=lambda b: b.optionality)
    return {
        "plan": "aim",
        "stage": "echoverse",
        "run_id": run.id,
        "seed": run.seed,
        "body": body,
        "target_engines": list(AIM_TARGETS[body]),
        "preferred_path": preferred.to_dict(),
        "rationale": (
            f"highest-optionality branch ({preferred.kind}) aimed at body "
            f"'{body}' -> engines {', '.join(AIM_TARGETS[body])}"
        ),
        "executes": False,  # L8: plans, never executes
        "mark": BOUNDED_MARK,
    }


def doctrine() -> str:
    """The universal doctrine in one line (GROK 1)."""
    return (
        "GOAL -> Inquiry -> Mandella -> Echoverse -> AIM "
        "-> success|failure -> teach if wrong -> titan absorb"
    )
