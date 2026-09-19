"""LEVI Offline — the offline-first answer chain.

Studied from an external upload (an offline-first assistant MVP built on
docker/ollama/qdrant). The docker pieces stay outside the repo; what LEVI
keeps is the *pattern*, recreated LEVI-native with LEVI's own twist:

- the chain answers locally FIRST, always;
- a cloud backend may answer only when local confidence falls below a
  threshold AND the dual gate passes — keeper policy allows cloud AND the
  individual call consents. One gate alone never opens the wire.
- secrets are scrubbed before anything touches disk or a wire, using
  LEVI's own :mod:`levi.growth.redact` gate (not a second copy of it);
- local recall comes from LEVI's own stdlib retrieval
  (:mod:`levi.memory.retrieval`, :mod:`levi.rag`) — this package holds no
  vector store of its own;
- every run returns a :class:`ChainReceipt`: which backend answered,
  what the confidence was, whether escalation was considered, granted,
  or denied, and why. Never just a string.

Canon: Alpha & Omega first and last (OMEGA Powered by Alpha); Levi
beneath them, head of everything below. This module serves the organism
below Levi — a lawful local-first policy, not a new brain.

stdlib-only. Local-first. No network, no telemetry, no sentience claims.
"""

from __future__ import annotations

from .chain import (
    Answer,
    Backend,
    ChainReceipt,
    ChainResult,
    Offliner,
    RuleBackend,
)
from .gates import GatePolicy, default_policy
from .journal import Journal

__all__ = [
    "Answer",
    "Backend",
    "ChainReceipt",
    "ChainResult",
    "GatePolicy",
    "Journal",
    "Offliner",
    "RuleBackend",
    "default_policy",
]
