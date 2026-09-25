"""Open-Meteo weather connector — credentialless, read-only, stdlib-only.

Open-Meteo is a free, keyless public weather API, so ``credential()``
returns the ``"public"`` sentinel and the registry's credential gate never
fires for reads. No secret can leak into a message by construction.

Operations (all read-only; no confirmation gate can ever trigger):
* ``current`` — current conditions for a coordinate
  (``latitude``, ``longitude`` required);
* ``forecast`` — daily summary for a coordinate (``latitude``,
  ``longitude`` required, ``days`` optional, 1..16, default 7).

Honesty: a fetch failure (DNS, HTTP error, unparseable JSON) is a
``ConnectorAPIError`` → ``status="api_error"``, ``ok=False``. Coordinates
are validated into real ranges before anything is sent; out-of-range
input is ``invalid_params``, never a guessed request. Open-Meteo is
recorded as a *reference* (provider name, never LEVI identity).
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict

from .registry import (
    Capability,
    Connector,
    ConnectorAPIError,
    InvalidParams,
    Operation,
    Transport,
    register_connector,
)

_API_BASE = "https://api.open-meteo.com/v1/forecast"
_USER_AGENT = "LEVI-weather/1.0 (local-first reader; +https://levi.local)"
_FETCH_TIMEOUT_SEC = 20
_MAX_BODY_BYTES = 1_000_000  # 1 MB — weather payloads are tiny


def _coords(params: dict[str, Any]) -> tuple[float, float]:
    try:
        lat = float(params.get("latitude"))
        lon = float(params.get("longitude"))
    except (TypeError, ValueError):
        raise InvalidParams(
            "latitude and longitude are required numbers — nothing was sent."
        ) from None
    if not -90.0 <= lat <= 90.0 or not -180.0 <= lon <= 180.0:
        raise InvalidParams(
            "latitude must be -90..90 and longitude -180..180 — nothing was sent."
        )
    return lat, lon


def _days(params: dict[str, Any]) -> int:
    try:
        days = int(params.get("days") or 7)
    except (TypeError, ValueError):
        raise InvalidParams("days must be an integer — nothing was sent.") from None
    if not 1 <= days <= 16:
        raise InvalidParams("days must be 1..16 — nothing was sent.")
    return days


def _download(url: str) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT_SEC) as resp:
            body = resp.read(_MAX_BODY_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise ConnectorAPIError(
            f"the weather server answered HTTP {exc.code} — nothing fetched."
        ) from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectorAPIError(
            f"could not reach the weather server ({type(exc).__name__}) — "
            "nothing fetched."
        ) from None
    if len(body) > _MAX_BODY_BYTES:
        raise ConnectorAPIError("weather response too large — nothing parsed.")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ConnectorAPIError(
            "weather response was not parseable JSON — nothing returned."
        ) from exc
    if not isinstance(payload, dict):
        raise ConnectorAPIError(
            "weather response had an unexpected shape — nothing returned."
        )
    return payload


class WeatherConnector(Connector):
    """Read-only weather reader. No credential, no writes, no confirmation."""

    id = "weather"
    display_name = "Open-Meteo weather"
    # Keyless public API; the var is accepted but never required —
    # credential() returns "public" when it is unset.
    credential_env_var = "LEVI_WEATHER_TOKEN"
    capabilities = (
        Capability("read.weather.current", "Current conditions for a coordinate"),
        Capability("read.weather.forecast", "Daily forecast summary for a coordinate"),
    )
    operations = (
        Operation(
            "current",
            "Current conditions (params: latitude, longitude)",
            params=("latitude", "longitude"),
        ),
        Operation(
            "forecast",
            "Daily forecast (params: latitude, longitude, days=7)",
            params=("latitude", "longitude", "days"),
        ),
    )
    references = ("open-meteo",)

    def credential(self) -> str | None:
        # Credentialless by design: keyless public API. Returns the env value
        # when present (harmless), else the "public" sentinel so execute()'s
        # credential gate never fires for reads.
        return super().credential() or "public"

    def perform(
        self,
        operation: str,
        params: dict[str, Any],
        token: str,
        transport: Transport | None,
    ) -> Any:
        lat, lon = _coords(params)
        query = {
            "latitude": f"{lat:.4f}",
            "longitude": f"{lon:.4f}",
            "timezone": "auto",
        }
        if operation == "forecast":
            query["daily"] = (
                "temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
                "weathercode"
            )
            query["forecast_days"] = str(_days(params))
        else:
            query["current"] = "temperature_2m,relative_humidity_2m,weathercode"
        url = _API_BASE + "?" + urllib.parse.urlencode(query)
        payload = _download(url)
        payload["fetched_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        payload["requested"] = {"latitude": lat, "longitude": lon}
        return payload


register_connector(WeatherConnector)
