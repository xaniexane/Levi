"""levi.desk — the user's own status desk.

Revived from iGoogle (Google, 2005-2013): the user-composed dashboard of
small modules ('gadgets'), arranged by the user, never ranked for them.
The inversion of the portal's death: Google replaced the desk with
platform-controlled app surfaces; LEVI gives the desk back, local-first.

Every tile is a named callable: ``render(ctx) -> list[str]``. Tiles read
LEVI's own local stores and degrade honestly — a missing subsystem reads
as 'unavailable' or 'not-initialized', never as zero, never as a crash.
A tile that throws renders its own error line; the desk never falls over.

Data layout under ``~/.levi/desk/``::

    layout.json    [ {"tile": name, "enabled": bool, "prefs": {...}} ... ]

Everything is owner-only: dirs 0700, files 0600. Writes are atomic.
No network, no threads, no sleeps. stdlib only.
"""

from __future__ import annotations

from .registry import TileRegistry, register_builtin_tiles

__all__ = ["TileRegistry", "register_builtin_tiles"]
