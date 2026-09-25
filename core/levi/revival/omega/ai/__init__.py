"""omega/ai: conventional-protocol bridges to the SI generator cores.

Separation law: the bridges may import the ``si/`` cores — the cores are
authoritative — but nothing under ``si/`` imports this package. Every
bridge carries the bridge label and claims nothing of its own.
"""

from __future__ import annotations

BRIDGE_LABEL = (
    "AI counterpart bridge — conventional-protocol interface; "
    "the SI core is authoritative; this bridge claims nothing"
)

__all__ = ["BRIDGE_LABEL"]
