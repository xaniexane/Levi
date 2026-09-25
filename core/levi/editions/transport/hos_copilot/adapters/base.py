"""Provider contract: read-only HOS clock ingestion."""

from __future__ import annotations

import abc
from typing import List, Optional, Sequence

from ..clocks import DriverClock


class ProviderError(Exception):
    """The provider call failed (network, auth, unexpected payload)."""


class NotConfiguredError(ProviderError):
    """No credentials / wiring for this provider — fail closed, never guess."""


class PayloadSchemaError(ProviderError):
    """The provider answered, but the payload didn't match the map."""


class HosProvider(abc.ABC):
    """One ELD vendor's read-only clock source.

    Contract:
    - ``read_only`` is always True: GETs only, never writes.
    - ``required_scopes`` names the exact token scopes the fleet must grant.
    - ``get_clocks`` raises ``NotConfiguredError`` without credentials —
      it never fabricates data.
    """

    provider_name: str = "base"
    read_only: bool = True
    required_scopes: Sequence[str] = ()

    @abc.abstractmethod
    def get_clocks(
        self, driver_ids: Optional[Sequence[str]] = None
    ) -> List[DriverClock]:
        """Current HOS clocks, optionally filtered to driver ids."""
        raise NotImplementedError
