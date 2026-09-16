"""Community Charters — governance as a portable artifact.

Remix delta: Reddit's mods are captive — they govern inside a platform
that can overrule, replace, or ignore them, and their governance has no
existence outside Reddit's servers. LEVI inverts this: the charter is a
versioned, founder-signed artifact the community OWNS; the mod action log
(warnings, removals with reasons, appeals) is local and auditable; and
the whole thing exports to an open checksummed format. Founder-held
keys, real mod tooling, governance that can leave.

NOTE: ``levi.identity.charter`` is LEVI's own identity constitution —
a different thing. This package is community governance.

Interop: ``charter.community_id`` matches ``levi.communities`` ids by
convention (see CHARTERS.md); ``attach`` writes the charter reference
into the community's governance block. One-directional, documented.

Warehouse shelf for the interop atlas crew (see docs/WAREHOUSES.md).
"""

from __future__ import annotations

SHELF = {
    "name": "charters",
    "summary": (
        "Community charters: versioned founder-signed governance artifacts "
        "(rules, roles, succession, amendment procedure), an auditable mod "
        "action log with appeals, and checksummed export/import. "
        "Interoperates with levi.communities by community-id convention."
    ),
    "items": [
        {
            "name": "charter-artifact",
            "provides": "versioned signed charter documents with amendment history",
        },
        {
            "name": "mod-log",
            "provides": "auditable moderation actions (reasons required) with appeals workflow",
        },
        {
            "name": "charter-export",
            "provides": "open checksummed export/import of charter + mod log + appeals",
        },
        {
            "name": "charter-attach",
            "provides": "link a charter into a levi.communities governance block",
        },
    ],
}
