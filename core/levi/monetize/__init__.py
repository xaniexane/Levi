"""LEVI monetization modules — 12 concrete income projects.

Each submodule adapts one income concept into original LEVI-native
code: a clear income mechanism, offline-first tooling, a JSONL income
ledger for every earning action, and risk bands. Anything that needs
Chauncey's accounts, credentials, or identity is an explicit
Chauncey-gated step — stubbed, never silently performed.
"""

from __future__ import annotations

from . import ledger, projects

__all__ = ["ledger", "projects"]
