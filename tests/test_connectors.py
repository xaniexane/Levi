"""Tests for the connectors substrate and builtin connectors."""

import pytest

from levi.connectors import registry
from levi.connectors.base import Connector, ConnectorError


def test_builtin_connectors_registered():
    ids = {c.id for c in registry.list()}
    assert {"directory", "clock"} <= ids


def test_unknown_connector_refused():
    with pytest.raises(ConnectorError):
        registry.poll("nope", foo=1)


def test_contract_violation_refused():
    bad = Connector(
        id="bad-test",
        name="Bad",
        description="breaks contract",
        poll=lambda **kw: ["not", "a", "tuple"],
    )
    registry.register(bad)
    try:
        with pytest.raises(ConnectorError):
            registry.poll("bad-test")
    finally:
        del registry._connectors["bad-test"]


# -- directory connector --------------------------------------------------


def _write(p, text):
    p.write_text(text)
    return p


def test_directory_added_modified_removed(tmp_path):
    events, state = registry.poll(
        "directory", path=str(tmp_path), allowed_roots=[str(tmp_path)]
    )
    assert events == []
    f = _write(tmp_path / "a.txt", "one")
    events, state = registry.poll(
        "directory", path=str(tmp_path), allowed_roots=[str(tmp_path)], state=state
    )
    assert [e["kind"] for e in events] == ["added"]
    assert events[0]["path"] == "a.txt"
    _write(tmp_path / "a.txt", "one-more")
    events, state = registry.poll(
        "directory", path=str(tmp_path), allowed_roots=[str(tmp_path)], state=state
    )
    assert [e["kind"] for e in events] == ["modified"]
    f.unlink()
    events, _state = registry.poll(
        "directory", path=str(tmp_path), allowed_roots=[str(tmp_path)], state=state
    )
    assert [e["kind"] for e in events] == ["removed"]


def test_directory_outside_allowed_roots_refused(tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    # allowed root is a real dir, but the watched path is not under it.
    with pytest.raises(ConnectorError):
        registry.poll("directory", path=str(tmp_path), allowed_roots=[str(other)])


def test_directory_nonexistent_refused(tmp_path):
    with pytest.raises(ConnectorError):
        registry.poll(
            "directory", path=str(tmp_path / "missing"), allowed_roots=[str(tmp_path)]
        )


def test_directory_max_files_refused(tmp_path):
    for i in range(4):
        (tmp_path / f"f{i}.txt").write_text("x")
    with pytest.raises(ConnectorError):
        registry.poll(
            "directory", path=str(tmp_path), allowed_roots=[str(tmp_path)], max_files=2
        )


# -- clock connector ------------------------------------------------------


def test_clock_ticks():
    events, state = registry.poll(
        "clock", since=0.0, now=3700.0, period_seconds=1800.0, name="halfhour"
    )
    assert [e["at"] for e in events] == [1800.0, 3600.0]
    assert all(e["kind"] == "tick" and e["name"] == "halfhour" for e in events)
    assert state == {"last": 3600.0}
    # second poll continues from state, no duplicates
    events2, _ = registry.poll(
        "clock", since=0.0, now=3700.0, period_seconds=1800.0, state=state
    )
    assert events2 == []


def test_clock_no_due_ticks():
    events, _ = registry.poll("clock", since=0.0, now=100.0, period_seconds=3600.0)
    assert events == []


def test_clock_refusals():
    with pytest.raises(ConnectorError):
        registry.poll("clock", since=0.0, now=100.0, period_seconds=0)
    with pytest.raises(ConnectorError):
        registry.poll("clock", since=200.0, now=100.0, period_seconds=60.0)
