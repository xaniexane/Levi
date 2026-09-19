"""Agent Workshop — compose, validate, and dry-run agent blueprints.

The workshop is a bench, not a factory: it inventories the parts that
really exist (agents, specialists, substrates, organs, Legion seats),
composes deterministic blueprints from them, validates those blueprints
against current doctrine (fail closed), and dry-runs them locally with
honest labels. It spawns nothing, calls no provider, moves no money.

OPEN DECISION (Chauncey, unresolved — do not settle unilaterally):
whether twins are hybrid/switchable, always-on, or switchable-only, and
what "inverse twin" means, is still an open question. The workshop
records an agent's twin_pair_id from the registry when known, but bakes
in NO twin-mode semantics. A blueprint may carry a free-text
``twin_note``; the workshop treats it as a note, never as doctrine.
"""

from __future__ import annotations

from .blueprint import Blueprint, compose_blueprint, load_blueprint, save_blueprint
from .dryrun import dry_run
from .inventory import inventory
from .validate import ValidationError, validate_blueprint

__all__ = [
    "Blueprint",
    "ValidationError",
    "compose_blueprint",
    "dry_run",
    "inventory",
    "load_blueprint",
    "save_blueprint",
    "validate_blueprint",
]
