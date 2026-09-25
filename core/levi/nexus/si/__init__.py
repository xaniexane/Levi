"""NEXUS native SI core — the authoritative router.

stdlib only. In-memory routing with an optional JSONL journal under
``~/.levi/nexus/`` (overridable via the ``LEVI_HOME`` environment
variable). This package never imports the ``ai`` bridge: the SI core
is authoritative and stands alone.
"""

from .engine import NexusEngine

__all__ = ["NexusEngine"]
