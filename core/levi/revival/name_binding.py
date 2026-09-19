"""Name binding: human names bound to addresses per zone.

Studied from: protocols-hunt-20260916-0041 (Find 4 - AppleTalk section of report.md).
AppleTalk's NBP lets services register human-readable names of the form
``object:type@zone``. The local names table is conflict-checked first,
then the registration is broadcast to the zone; a name already owned by
another node is refused. Lookups resolve a name to its owner's address.

This module models the zone as an in-process registry: nodes hold local
names tables, the zone table enforces uniqueness across nodes, and
lookup/registration/removal round-trip through both. No network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "NameError",
    "MalformedName",
    "NameInUse",
    "UnknownName",
    "BoundName",
    "parse_name",
    "ZoneTable",
    "NamesTable",
]

ORIGIN = "levi-revival/appletalk-nbp"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class NameError(Exception):
    """Base class for name-binding failures."""


class MalformedName(NameError):
    """The name does not parse as object:type@zone."""


class NameInUse(NameError):
    """Another node already owns that name in the zone."""


class UnknownName(NameError):
    """No node in the zone has registered that name."""


# ---------------------------------------------------------------------------
# Names
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BoundName:
    """A parsed ``object:type@zone`` name."""

    object: str
    type: str
    zone: str

    def format(self) -> str:
        return f"{self.object}:{self.type}@{self.zone}"


def parse_name(text: str) -> BoundName:
    """Parse ``object:type@zone``. All three parts must be non-empty."""
    if not isinstance(text, str):
        raise MalformedName("name must be a string")
    try:
        obj_type, zone = text.split("@", 1)
        obj, ntype = obj_type.split(":", 1)
    except ValueError:
        raise MalformedName(f"expected object:type@zone, got {text!r}") from None
    obj, ntype, zone = obj.strip(), ntype.strip(), zone.strip()
    if not obj or not ntype or not zone:
        raise MalformedName(f"empty part in {text!r}")
    return BoundName(object=obj, type=ntype, zone=zone)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class ZoneTable:
    """The zone-wide binding table: one owner per name, enforced globally."""

    def __init__(self, zone: str) -> None:
        if not zone:
            raise ValueError("zone must be non-empty")
        self.zone = zone
        self._bindings: dict[str, str] = {}  # formatted name -> node address

    def register(self, name: BoundName, address: str) -> None:
        """Bind ``name`` to ``address``; refuse if another node owns it."""
        if name.zone != self.zone:
            raise MalformedName(
                f"name zone {name.zone!r} does not match table zone {self.zone!r}"
            )
        key = name.format()
        owner = self._bindings.get(key)
        if owner is not None and owner != address:
            raise NameInUse(f"{key!r} is already bound to {owner!r}")
        self._bindings[key] = address

    def lookup(self, name: BoundName) -> str:
        """Resolve a name to its owner's address."""
        try:
            return self._bindings[name.format()]
        except KeyError:
            raise UnknownName(
                f"no such name in zone {self.zone!r}: {name.format()!r}"
            ) from None

    def remove(self, name: BoundName, address: str) -> None:
        """Remove a binding; only the owning address may remove its own name."""
        key = name.format()
        if self._bindings.get(key) != address:
            raise UnknownName(f"{key!r} is not bound to {address!r}")
        del self._bindings[key]

    def list_by_type(self, ntype: str, zone: str | None = None) -> list[str]:
        """All formatted names of a given type in this zone."""
        zone = zone or self.zone
        return sorted(
            key
            for key, addr in self._bindings.items()
            if parse_name(key).type == ntype and parse_name(key).zone == zone
        )


class NamesTable:
    """One node's local names table, backed by the shared zone table.

    Registration is two-phase like the original: check locally, then
    broadcast (here: the zone table) which re-checks globally.
    """

    def __init__(self, node_address: str, zone_table: ZoneTable) -> None:
        if not node_address:
            raise ValueError("node address must be non-empty")
        self.node_address = node_address
        self.zone_table = zone_table
        self._local: set[str] = set()  # formatted names owned by this node

    def register(self, text: str) -> BoundName:
        """Bind a human name to this node; conflicts are refused."""
        name = parse_name(text)
        if name.format() in self._local:
            return name  # idempotent re-registration of our own name
        self.zone_table.register(name, self.node_address)
        self._local.add(name.format())
        return name

    def lookup(self, text: str) -> str:
        """Resolve any name in the zone to its owner's address."""
        return self.zone_table.lookup(parse_name(text))

    def unregister(self, text: str) -> None:
        name = parse_name(text)
        self.zone_table.remove(name, self.node_address)
        self._local.discard(name.format())

    def owned(self) -> list[str]:
        return sorted(self._local)
