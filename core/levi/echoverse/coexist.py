"""Echoverse x Mandella interpenetration (L7).

Echoverse explores space; Mandella forces a stake — and remembers what
was refused. Neither owns the other:

- Mandella can SEED an Echoverse run from the chosen option.
- Echoverse can FEED Mandella constraints from a wild branch.

This module works on plain data (dicts) — it does not import the
Mandella organ, so neither module owns the other in code either.

Operational contracts (product copy, from the coexistence design):
  "Show me parallel paths / counterfactuals / what if we don't" -> Echoverse
  "I must choose under incomplete info — A/B/C"                  -> Mandella
  "Remember the path we didn't take"                            -> Mandella phantom
  "Simulate pressure over cycles"                               -> Echoverse cycles
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.echoverse.branches import BranchStore, EchoRun


def seed_from_mandella(
    option: Dict[str, Any],
    store: Optional[BranchStore] = None,
    data_dir: Optional[Path] = None,
) -> EchoRun:
    """Start an Echoverse run seeded from a Mandella-chosen option.

    ``option`` is the chosen option's data: requires at least a label
    (``label`` or ``key``). Raises ValueError without one — Mandella must
    hand over an explicit stake, never a vague pointer.
    """
    label = str(option.get("label") or option.get("key") or "").strip()
    if not label:
        raise ValueError("seed_from_mandella requires an explicit option label/key")
    store = store or BranchStore(data_dir=data_dir)
    seed = f"mandella:{option.get('key', '?')}: {label}"
    run = store.simulate(seed, cycles=int(option.get("cycles", 3) or 3))
    run.metadata["seeded_from"] = "mandella"
    run.metadata["mandella_option"] = {k: option.get(k) for k in ("key", "label", "score") if k in option}
    return run


def constraints_for_mandella(run: EchoRun) -> List[Dict[str, Any]]:
    """Extract constraints for Mandella from a run's WILD branches only.

    Wild branches are high-novelty / high-verification-burden — exactly
    the material a choice-under-fog needs as guardrails. Taken and
    not_taken branches are not Mandella's business here.
    """
    out = []
    for b in run.branches:
        if b.kind != "wild":
            continue
        out.append(
            {
                "constraint": b.label,
                "detail": b.summary,
                "risk": b.risk,
                "optionality": b.optionality,
                "source_run": run.id,
            }
        )
    return out


def phantom_record(rejected: List[Dict[str, Any]]) -> Dict[str, Any]:
    """The Mandella phantom: the path not taken, remembered.

    Stored as data the caller persists — Echoverse does not own Mandella's
    memory, it only shapes the record.
    """
    return {
        "kind": "mandella_phantom",
        "rejected": [
            {"key": r.get("key"), "label": r.get("label"), "reason": r.get("reason", "")}
            for r in rejected
        ],
        "note": "the erased track still haunts — alternate-reality memory, not just options",
    }
