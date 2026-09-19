"""alpha/ai: conventional-protocol bridge to the SI reasoning core.

Separation law: the bridge may import the ``si/`` core — the core is
authoritative — but nothing under ``si/`` imports this package. The
bridge carries the bridge label and claims nothing of its own.
"""

from __future__ import annotations

BRIDGE_LABEL = (
    "AI counterpart bridge — conventional-protocol interface; "
    "the SI core is authoritative; this bridge claims nothing"
)

__all__ = ["BRIDGE_LABEL"]
