"""LEVI survivability catalog: what keeps LEVI alive offline.

Machine-readable catalog of capabilities, their primary path, fallback path,
degraded mode, and whether they survive with no network. Entries are plain
dicts (stdlib, serializable).

Example:
    from levi.survivability import catalog, check_all
    for entry in catalog():
        print(entry["id"], entry["offline_ok"])
    for result in check_all():
        print(result["id"], "OK" if result["ok"] else "MISSING")
"""

from .catalog import Entry, catalog, check_all, check_entry, get

__all__ = ["Entry", "catalog", "check_all", "check_entry", "get"]
