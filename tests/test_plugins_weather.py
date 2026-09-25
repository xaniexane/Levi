"""Tests for levi.plugins.weather — the credentialless Open-Meteo reader."""

from __future__ import annotations

import json


from levi.plugins import weather as weather_mod
from levi.plugins.registry import get_connector, list_connectors
from levi.plugins.weather import WeatherConnector


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, n: int = -1) -> bytes:
        return self._payload if n is None or n < 0 else self._payload[:n]


def _patch_urlopen(monkeypatch, payload: dict) -> list:
    seen: list = []

    def fake_urlopen(req, timeout=None):
        seen.append(req.full_url)
        return _FakeResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(weather_mod.urllib.request, "urlopen", fake_urlopen)
    return seen


_CURRENT = {"current": {"temperature_2m": 21.5, "weathercode": 1}}
_FORECAST = {
    "daily": {
        "time": ["2026-09-19", "2026-09-20"],
        "temperature_2m_max": [22.0, 23.0],
        "temperature_2m_min": [14.0, 15.0],
    }
}


def test_connector_registered_and_credentialless():
    ids = [c.id for c in list_connectors()]
    assert "weather" in ids
    conn = get_connector("weather")
    assert isinstance(conn, WeatherConnector)
    # No env var set in test env → still "public", never missing_credential.
    assert conn.credential() == "public"
    assert conn.requires_confirmation is False


def test_current_operation(monkeypatch):
    seen = _patch_urlopen(monkeypatch, _CURRENT)
    conn = get_connector("weather")
    result = conn.execute("current", {"latitude": 39.7817, "longitude": -89.6501})
    assert result.ok, result.message
    assert result.data["current"]["temperature_2m"] == 21.5
    assert result.data["requested"] == {"latitude": 39.7817, "longitude": -89.6501}
    assert "fetched_at" in result.data
    assert "latitude=39.7817" in seen[0]
    assert "current=" in seen[0]


def test_forecast_operation(monkeypatch):
    seen = _patch_urlopen(monkeypatch, _FORECAST)
    conn = get_connector("weather")
    result = conn.execute(
        "forecast", {"latitude": 39.78, "longitude": -89.65, "days": 2}
    )
    assert result.ok, result.message
    assert result.data["daily"]["temperature_2m_max"] == [22.0, 23.0]
    assert "forecast_days=2" in seen[0]
    assert "daily=" in seen[0]


def test_bad_coordinates_rejected_before_network(monkeypatch):
    seen = _patch_urlopen(monkeypatch, _CURRENT)
    conn = get_connector("weather")
    for params in (
        {"latitude": 91.0, "longitude": 0.0},
        {"latitude": 0.0, "longitude": -181.0},
        {"latitude": "north", "longitude": 0.0},
        {"longitude": 0.0},
    ):
        result = conn.execute("current", params)
        assert result.ok is False
        assert result.status == "invalid_params"
    assert seen == []


def test_bad_days_rejected(monkeypatch):
    _patch_urlopen(monkeypatch, _FORECAST)
    conn = get_connector("weather")
    result = conn.execute("forecast", {"latitude": 1.0, "longitude": 1.0, "days": 99})
    assert result.ok is False
    assert result.status == "invalid_params"


def test_network_failure_is_api_error(monkeypatch):
    import urllib.error

    def boom(req, timeout=None):
        raise urllib.error.URLError("no route to host")

    monkeypatch.setattr(weather_mod.urllib.request, "urlopen", boom)
    conn = get_connector("weather")
    result = conn.execute("current", {"latitude": 1.0, "longitude": 1.0})
    assert result.ok is False
    assert result.status == "api_error"
    assert "nothing fetched" in result.message


def test_unparseable_body_is_api_error(monkeypatch):
    def fake(req, timeout=None):
        return _FakeResponse(b"<not json at all")

    monkeypatch.setattr(weather_mod.urllib.request, "urlopen", fake)
    conn = get_connector("weather")
    result = conn.execute("current", {"latitude": 1.0, "longitude": 1.0})
    assert result.ok is False
    assert result.status == "api_error"


def test_unknown_operation():
    conn = get_connector("weather")
    result = conn.execute("snow-dance", {"latitude": 1.0, "longitude": 1.0})
    assert result.ok is False
    assert result.status == "unknown_operation"


def test_coordinates_never_echoed_raw_in_message(monkeypatch):
    _patch_urlopen(monkeypatch, _CURRENT)
    conn = get_connector("weather")
    result = conn.execute("current", {"latitude": 39.7817, "longitude": -89.6501})
    assert result.ok
    # Success path: message must not carry the request URL (query strings
    # are where tokens hide).
    assert "api.open-meteo.com" not in (result.message or "")
