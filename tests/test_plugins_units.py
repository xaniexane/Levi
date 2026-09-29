"""Tests for the units plugin — exact stdlib conversion, deny-closed."""

import pytest

from levi.plugins.units import UnitsConnector, convert, describe
from levi.plugins.registry import InvalidParams


def test_length_exact():
    out = convert(1, "mi", "m")
    assert out["result"] == pytest.approx(1609.344)
    assert out["category"] == "length"


def test_alias_resolution():
    assert convert(12, "inch", "ft")["result"] == pytest.approx(1.0)
    assert convert(1, "foot", "in")["result"] == pytest.approx(12.0)


def test_temperature_exact():
    assert convert(0, "c", "f")["result"] == pytest.approx(32.0)
    assert convert(212, "f", "c")["result"] == pytest.approx(100.0)
    assert convert(0, "c", "k")["result"] == pytest.approx(273.15)
    assert convert(32, "fahrenheit", "kelvin")["result"] == pytest.approx(273.15)


def test_mass_volume_time_speed():
    assert convert(1, "kg", "g")["result"] == pytest.approx(1000.0)
    assert convert(1, "gal", "l")["result"] == pytest.approx(3.785411784)
    assert convert(1, "h", "s")["result"] == pytest.approx(3600.0)
    assert convert(60, "mph", "km/h")["result"] == pytest.approx(96.56064)


def test_deny_closed_unknown_unit():
    with pytest.raises(InvalidParams):
        convert(1, "furlong", "m")
    with pytest.raises(InvalidParams):
        convert(1, "m", "parsec")


def test_deny_closed_cross_category():
    with pytest.raises(InvalidParams):
        convert(1, "m", "kg")


def test_deny_closed_bad_value():
    with pytest.raises(InvalidParams):
        convert(float("nan"), "m", "km")
    with pytest.raises(InvalidParams):
        convert(float("inf"), "m", "km")
    with pytest.raises(InvalidParams):
        convert("twelve", "m", "km")


def test_describe_all_and_one():
    all_cats = describe()["categories"]
    assert {"length", "mass", "volume", "temperature", "time", "speed"} <= set(all_cats)
    assert "c" in describe("temperature")["units"]
    with pytest.raises(InvalidParams):
        describe("spacetime")


def test_connector_registered_and_operations():
    # module self-registers on import
    assert UnitsConnector.reference == "units"
    names = {op.name for op in UnitsConnector.operations}
    assert names == {"convert", "describe"}
    conn = UnitsConnector()
    assert conn.credential() == "public"
    out = conn.perform("convert", {"value": 1, "from": "km", "to": "m"}, None, None)
    assert out["result"] == pytest.approx(1000.0)
    with pytest.raises(InvalidParams):
        conn.perform("teleport", {}, None, None)


def test_read_only_capabilities():
    assert all(not c.write for c in UnitsConnector.capabilities)
    assert all(not op.write for op in UnitsConnector.operations)
