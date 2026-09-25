"""Organ registry — deny-closed dispatch over the four branching organs.

The registry maps organ names to their entry points. Entry points are
resolved by lazy import (inside functions), so importing this module never
loads reim/riem, and never loads anything beyond what
levi/organs/__init__.py already imports (echo, mandella) — those two are
pre-existing package imports this file cannot change under additive-only
rules. Every organ is resolved at call time via :func:`run_organ`.

The name "echoverse" maps to the existing run_echo implementation in
levi/organs/echo.py — there is deliberately no separate echoverse.py
(see that module's docstring: a prior lineage's competing graph/
implementation was rejected at merge time; do not reintroduce one).

Unknown organ names are denied with ValueError (deny-closed dispatch).
"""

from __future__ import annotations

from importlib import import_module
from typing import Any, Callable, Dict, List

ORGAN = "registry"

_ENTRY_POINTS = {
    "echoverse": "levi.organs.echo:run_echo",
    "mandella": "levi.organs.mandella:run_mandella",
    "reim": "levi.organs.reim:compost_failure",
    "riem": "levi.organs.riem:promote",
}

_DESCRIBE = {
    "echoverse": (
        "Branch exploration: taken / not-taken / wild parallel paths for a "
        "seed. Implemented by run_echo in levi/organs/echo.py (no separate "
        "echoverse.py — the competing implementation was rejected at merge)."
    ),
    "mandella": (
        "Stake selection under domain pressure: options, a recommended "
        "stake, and the unchosen 'phantoms' that haunt the decision."
    ),
    "reim": (
        "Failure composting: extracts lesson, inverse map, compost class "
        "and reusability from a failure record. Returns compost data; "
        "writes nothing."
    ),
    "riem": (
        "Compost-to-genome: promotes eligible REIM compost records into "
        "genome proposals (procedural-memory / checklist-item / "
        "guard-rule). Proposals are data, never auto-applied."
    ),
}

_RISK = {
    "echoverse": "low",
    "mandella": "low",
    "reim": "low",
    "riem": "low",
}

# Registry shape per the blueprint contract.
ORGAN_REGISTRY: Dict[str, Dict[str, Any]] = {
    name: {
        "entry": _ENTRY_POINTS[name],
        "describe": _DESCRIBE[name],
        "risk": _RISK[name],
    }
    for name in _ENTRY_POINTS
}


def _resolve(name: str) -> Callable:
    """Lazily import and return the entry point for ``name``."""
    module_path, _, func_name = _ENTRY_POINTS[name].partition(":")
    module = import_module(module_path)
    func = getattr(module, func_name, None)
    if not callable(func):
        raise ValueError(
            "run_organ: entry point %r for organ %r is not callable"
            % (_ENTRY_POINTS[name], name)
        )
    return func


def list_organs() -> List[Dict[str, Any]]:
    """List the registered organs (name, describe, risk, entry)."""
    return [
        {
            "name": name,
            "entry": meta["entry"],
            "describe": meta["describe"],
            "risk": meta["risk"],
        }
        for name, meta in ORGAN_REGISTRY.items()
    ]


def run_organ(name: str, **kwargs) -> Any:
    """Run a registered organ by name with keyword arguments.

    Raises ValueError when ``name`` is not a registered organ (deny-closed).
    Imports the organ module lazily at call time.
    """
    if not isinstance(name, str) or name not in ORGAN_REGISTRY:
        raise ValueError(
            "run_organ: unknown organ %r (known: %s)"
            % (name, ", ".join(sorted(ORGAN_REGISTRY)))
        )
    return _resolve(name)(**kwargs)
