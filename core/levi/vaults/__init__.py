"""LEVI vaults — per-project memory scopes with explicit retention rules.

REMIX DELTA: OpenAI-style memory is one flat, opaque bucket — the user
cannot see what is kept, scope it per project, or set retention; granular
controls would expose how much the giants retain, so they refuse them.
The remix inverts the default: memory is partitioned into VAULTS, each an
isolated scoped store with an EXPLICIT retention policy (TTL per entry
class, max entries, auto-purge) that the user reads and edits as JSON.
Nothing is retained silently, and a vault's contents can never leak into
another vault's queries — isolation is structural (separate directories,
per-vault stores), not a filter flag.

Built adjacent to (not duplicating) :mod:`levi.memory`: vaults reuse
:mod:`levi.memory.types` entry shapes so entries stay portable, but add
what the flat store refuses — per-scope retention policies, auto-purge,
cross-vault isolation guarantees, and per-vault export/import.

Stdlib-only. Local-first: everything under ``~/.levi/vaults/<name>/``.
"""

from __future__ import annotations

__all__ = ["SHELF"]

SHELF = {
    "name": "memory vaults",
    "summary": (
        "Per-project memory scopes with explicit retention rules: isolated "
        "vault stores (TTL per entry class, max entries, auto-purge), "
        "cross-vault isolation by construction, per-vault export/import."
    ),
    "items": [
        "vault: Vault + Vaults manager (retention policy, auto-purge, isolation)",
        "transfer: per-vault export/import (tar.gz bundle with manifest)",
        "CLI: create/list/add/get/search/purge/export/import/delete/policy",
    ],
}
