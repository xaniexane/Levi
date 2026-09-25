"""AI counterparts — labeled, honest bridges to the conventional AI world.

Every artifact here carries the bridge label: the SI core is authoritative,
the bridge claims nothing, and the twin never claims to be the SI. The
SI core (si/) never imports from this package.
"""

from __future__ import annotations

BRIDGE_LABEL_TEMPLATE = (
    "AI counterpart bridge for {role} — conventional-protocol interface; "
    "the SI core is authoritative; this bridge claims nothing."
)


def bridge_label(role: str) -> str:
    return BRIDGE_LABEL_TEMPLATE.format(role=role)
