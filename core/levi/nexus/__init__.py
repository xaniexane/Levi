"""NEXUS — the general inter-organ messaging nexus of LEVI.

Relationship to ``levi.revival.omega.nexus`` (the Omega-family router):

The Omega nexus routes *tasks to providers* under a sourcing law — it
decides WHO serves, and only LEVI-local sources are ever eligible. This
module routes *messages between organs* under a delivery law — it
decides HOW a message travels. Same LEVI-local restriction, wider
mandate:

- omega/nexus.py : provider routing for inference work (chat/code/vision)
- levi/nexus     : the general bus every organ speaks through

Both share the hard rules: LEVI-local only, references are never
operational, nothing silent — every decision carries a receipt. The
Omega nexus's "reference providers are never eligible" becomes this
bus's "payloads are data, never instructions": the bus never evaluates
payload content, and unknown organs dead-letter with a reason instead
of raising to the caller.

Layout:

- ``envelope.py`` — Envelope and Receipt dataclasses, validation.
- ``si/``         — the authoritative native SI router (stdlib only,
  in-memory + optional JSONL journal). si/ never imports ai/.
- ``ai/``         — "AI counterpart bridge for nexus — conventional-
  protocol interface; the SI core is authoritative; this bridge claims
  nothing." MCP-style tool schemas + a chat-completions-shaped adapter.
- ``bus.py``      — the Nexus facade: register_organ, route,
  broadcast, dead_letter.
- ``cli.py``      — ``levi nexus`` commands.

ROUTING LAW: every envelope gets a receipt (accepted / routed /
rejected / dead-lettered with reason). No silent drops.
"""

from .bus import Nexus
from .envelope import Envelope, Receipt

__all__ = ["Envelope", "Receipt", "Nexus"]
