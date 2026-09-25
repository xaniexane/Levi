"""ELD provider adapters: read-only clock ingestion.

Every adapter declares ``read_only = True`` and only ever performs
HTTP GETs against the fleet's own ELD credentials. Nothing here writes
logs, touches ELD hardware, or stores credentials.

- ``MotiveProvider`` — interface + required scopes; live wiring pending
  the fleet's own Motive developer app (no endpoint path fabricated).
- ``SamsaraProvider`` — vendor-confirmed ``GET /fleet/hos/clocks``;
  field map marked provisional until verified against a live response.
- ``FixtureProvider`` — deterministic sample clocks for tests and demos.

Stdlib only (urllib, no third-party HTTP).
"""

from __future__ import annotations

from .base import (
    HosProvider,
    NotConfiguredError,
    PayloadSchemaError,
    ProviderError,
)
from .fixture_provider import FixtureProvider
from .motive import MotiveProvider
from .samsara import SamsaraProvider

__all__ = [
    "HosProvider",
    "ProviderError",
    "NotConfiguredError",
    "PayloadSchemaError",
    "MotiveProvider",
    "SamsaraProvider",
    "FixtureProvider",
]
