"""Motive ELD adapter — interface and scope declaration.

Research basis (2026-09-21): Motive exposes HOS data under read scopes
``available_time``, ``hours_of_service``, and ``hos_violations``, with a
dispatch-operations integration guide. The exact endpoint paths were not
captured at vendor level in that pass, so this adapter deliberately
declares the interface and the required scopes WITHOUT fabricating a
URL: live wiring happens with the fleet's own Motive developer app and
the fleet's own credentials, and the endpoint is filled in from Motive's
developer docs at that time.

Until then, every call fails closed with ``NotConfiguredError`` — the
co-pilot runs on fixtures, never on guesses.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from ..clocks import DriverClock
from .base import HosProvider, NotConfiguredError


class MotiveProvider(HosProvider):
    """Motive (KeepTruckin) ELD: read-only HOS ingestion interface."""

    provider_name = "motive"

    #: Read scopes the fleet's Motive API token must carry (verified 2026-09-21).
    required_scopes = ("available_time", "hours_of_service", "hos_violations")

    def __init__(self, api_key: Optional[str] = None) -> None:
        # The key is held transiently for the call; never logged, never stored.
        self._api_key = api_key

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    def get_clocks(
        self, driver_ids: Optional[Sequence[str]] = None
    ) -> List[DriverClock]:
        if not self._api_key:
            raise NotConfiguredError(
                "Motive is not wired: provide the fleet's own Motive API key "
                "(scopes: %s). Live endpoint paths come from Motive's "
                "developer docs at wiring time — none are fabricated here."
                % ", ".join(self.required_scopes)
            )
        # Live wiring point: GET the fleet's Motive HOS endpoints with the
        # key above, map to DriverClock, and return. Until that wiring is
        # built and tested against a real fleet, fail closed.
        raise NotConfiguredError(
            "Motive live wiring is not built yet: endpoint paths must be "
            "taken from Motive's developer docs during fleet onboarding. "
            "Use FixtureProvider for development and tests."
        )
