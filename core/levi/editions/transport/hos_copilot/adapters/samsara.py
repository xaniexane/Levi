"""Samsara ELD adapter — vendor-confirmed live clocks endpoint.

Research basis (2026-09-23, Samsara's own developer docs):
- ``GET https://api.samsara.com/fleet/hos/clocks`` — "Get the current
  HOS status for all drivers", filterable by ``driverIds`` / tag IDs,
  512-object limit.
- Token scope: "Read ELD Compliance Settings (US)" under Compliance.

Honest limit, machine-pinned: the exact JSON field names of the
response were NOT captured in that pass, so the field map below is
declared ``FIELD_MAP_PROVISIONAL = True`` and ``parse_clocks`` raises
``PayloadSchemaError`` on any missing field. Verify the map against a
live vendor response during fleet onboarding before trusting it.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence

from ..clocks import DriverClock
from .base import HosProvider, NotConfiguredError, PayloadSchemaError, ProviderError

#: Vendor-confirmed 2026-09-23 (developers.samsara.com/reference/gethosclocks).
HOS_CLOCKS_URL = "https://api.samsara.com/fleet/hos/clocks"

#: Token scope the fleet's Samsara API token must carry.
REQUIRED_SCOPE = "Read ELD Compliance Settings (US)"


class SamsaraProvider(HosProvider):
    """Samsara ELD: read-only HOS clocks ingestion."""

    provider_name = "samsara"
    required_scopes = (REQUIRED_SCOPE,)

    #: True until the map below is verified against a live vendor
    #: response. Pinned by test — it must not silently become verified.
    FIELD_MAP_PROVISIONAL = True

    #: Response-field map. Provisional — see FIELD_MAP_PROVISIONAL.
    FIELD_MAP = {
        "driver_id": "driverId",
        "drive_remaining_ms": "driveTimeRemainingDurationMs",
        "shift_remaining_ms": "shiftRemainingDurationMs",
        "time_to_break_ms": "timeUntilBreakDurationMs",
        "cycle_remaining_ms": "cycleRemainingDurationMs",
    }

    def __init__(self, api_token: Optional[str] = None) -> None:
        # Held transiently for the call; never logged, never stored.
        self._api_token = api_token

    @property
    def is_configured(self) -> bool:
        return bool(self._api_token)

    def get_clocks(
        self, driver_ids: Optional[Sequence[str]] = None
    ) -> List[DriverClock]:
        if not self._api_token:
            raise NotConfiguredError(
                "Samsara is not wired: provide the fleet's own API token "
                "with scope %r." % REQUIRED_SCOPE
            )
        params: Dict[str, str] = {}
        if driver_ids:
            params["driverIds"] = ",".join(driver_ids)
        url = HOS_CLOCKS_URL
        if params:
            url += "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": "Bearer " + self._api_token,
                "Accept": "application/json",
            },
            method="GET",  # read-only: GETs only, never writes
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except NotConfiguredError:
            raise
        except Exception as exc:  # network/auth failures fail closed
            raise ProviderError("Samsara HOS clocks request failed: %s" % exc)
        return self.parse_clocks(payload)

    @classmethod
    def parse_clocks(cls, payload: Mapping[str, Any]) -> List[DriverClock]:
        """Map a /fleet/hos/clocks response to DriverClock snapshots."""
        items = payload.get("data") if isinstance(payload, Mapping) else None
        if not isinstance(items, list):
            raise PayloadSchemaError(
                "expected a mapping with a 'data' list from %s" % HOS_CLOCKS_URL
            )
        clocks: List[DriverClock] = []
        for item in items:
            try:
                values = {
                    key: item[field] for key, field in cls.FIELD_MAP.items()
                }
            except KeyError as exc:
                raise PayloadSchemaError(
                    "Samsara payload missing field %r — the provisional "
                    "field map needs verification against a live response"
                    % (exc.args[0],)
                )
            clocks.append(
                DriverClock(
                    driver_id=str(values["driver_id"]),
                    captured_at=datetime.now(timezone.utc),
                    drive_remaining_hrs=values["drive_remaining_ms"] / 3_600_000,
                    shift_remaining_hrs=values["shift_remaining_ms"] / 3_600_000,
                    break_remaining_hrs=values["time_to_break_ms"] / 3_600_000,
                    cycle_remaining_hrs=values["cycle_remaining_ms"] / 3_600_000,
                    source="samsara",
                )
            )
        return clocks
