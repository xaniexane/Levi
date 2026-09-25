"""Portable Communities — leave any platform, keep the community.

Remix delta: Discord/Reddit lock-in works because the community's
structure, history, and governance live on the giant's servers in
proprietary form. Portability removes the lock-in that lets giants
neglect mods and users. LEVI inverts this: the community is a local
first-class data model with a one-command export to an open,
documented, checksummed JSON format — and an import that VERIFIES
integrity before accepting anything.

Warehouse shelf for the interop atlas crew (see docs/WAREHOUSES.md).
"""

from __future__ import annotations

SHELF = {
    "name": "communities",
    "summary": (
        "Portable communities: local data model (channels, members, roles, "
        "message history, governance) with one-command export to an open "
        "checksummed JSON format and verifying import. Leave any platform."
    ),
    "items": [
        {
            "name": "community-model",
            "provides": "channels/rooms, members, roles, message history, governance rules as local dataclasses",
        },
        {
            "name": "community-export",
            "provides": "one-command export to open documented JSON with per-section SHA-256 checksums",
        },
        {
            "name": "community-import",
            "provides": "import that verifies every checksum and refuses tampered/corrupt files",
        },
    ],
}
