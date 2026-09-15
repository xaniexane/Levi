"""Plugin catalog — a read-model over the connector registry.

Historical note: the CLI surfaces ``levi plugins`` (closed-source
capability catalog) and ``levi symbiosis --orphans`` both referenced a
``PluginCatalog`` that was never built — ``core/levi/plugins/`` did not
exist at all, so both commands died with ``ModuleNotFoundError`` the
moment they ran. The connector registry (``levi.plugins.registry``,
blueprint §3) is the one canonical implementation of "what plugins
exist"; this module is a thin read-model over it, not a second registry
(blueprint §1.2: one canonical implementation per concept).
"""

from __future__ import annotations

from dataclasses import dataclass

from levi.plugins.registry import describe, list_connectors


@dataclass(frozen=True)
class CatalogEntry:
    """One row of the catalog. ``id`` is the stable connector id."""

    id: str
    display_name: str
    credential_env_var: str
    requires_confirmation: bool
    category: str = "connector"


class PluginCatalog:
    """Read-model over the plugin connector registry.

    ``list()`` returns :class:`CatalogEntry` rows (each carries ``.id``);
    ``format()`` renders the human-readable catalog the ``levi plugins``
    command prints.
    """

    def list(self) -> list[CatalogEntry]:
        return [
            CatalogEntry(
                id=c.id,
                display_name=c.display_name,
                credential_env_var=c.credential_env_var,
                requires_confirmation=c.requires_confirmation,
            )
            for c in list_connectors()
        ]

    def format(self, category: str | None = None) -> str:
        entries = self.list()
        if category:
            entries = [e for e in entries if e.category == category]
            if not entries:
                return f"No plugin connectors in category {category!r}."
        if not entries:
            return "No plugin connectors registered."
        by_id = {c.id: c for c in list_connectors()}
        blocks = ["=== LEVI Plugin Catalog ===", ""]
        for e in entries:
            blocks.append(describe(by_id[e.id]))
            blocks.append("")
        return "\n".join(blocks).rstrip() + "\n"
