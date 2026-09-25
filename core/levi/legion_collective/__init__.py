"""Legion of Anomalies — the collective layer ("1 is all, all is one").

The registry, capability manifest, shared conventions, canon lock, and
shared-surface guard that make the fourteen KFX² workstreams one organism:
shared named constants, local JSON stores, 127.0.0.1-safe, stdlib-only.
No silo formats, no private protocols a sibling workstream can't read.

Everything here is opt-in and local-first. Nothing phones home, nothing
binds a socket, nothing auto-registers.
"""

from levi.legion_collective import canon, conventions, manifest, registry, surface_guard

__all__ = ["canon", "conventions", "manifest", "registry", "surface_guard"]
