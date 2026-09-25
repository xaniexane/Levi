"""Offline security knowledge index — defensive blue-team content. See catalog.py for the validated loader."""

from __future__ import annotations

from levi.knowledge.security.catalog import (  # noqa: F401
    CATALOG_PATH,
    CatalogError,
    SecurityCatalog,
    SecurityDomain,
    load_catalog,
)
