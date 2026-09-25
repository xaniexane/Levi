"""Tests for the logtail connector."""

import pytest

from levi.connectors import registry
from levi.connectors.base import ConnectorError


def _poll(path, **kw):
    return registry.poll(
        "logtail", path=str(path), allowed_roots=[str(path.parent)], **kw
    )


def test_registered():
    assert "logtail" in {c.id for c in registry.list()}


def test_new_lines_emitted(tmp_path):
    log = tmp_path / "app.log"
    log.write_text("first\nsecond\n")
    events, state = _poll(log)
    assert [e["text"] for e in events] == ["first", "second"]
    assert [e["line_no"] for e in events] == [1, 2]
    assert all(e["kind"] == "line" for e in events)

    log.write_text("first\nsecond\nthird\n")
    events, state = _poll(log, state=state)
    assert [e["text"] for e in events] == ["third"]
    assert events[0]["line_no"] == 3


def test_no_new_lines_is_quiet(tmp_path):
    log = tmp_path / "app.log"
    log.write_text("only\n")
    _, state = _poll(log)
    events, state = _poll(log, state=state)
    assert events == []


def test_rotation_reported_and_rebased(tmp_path):
    log = tmp_path / "app.log"
    log.write_text("old line\n")
    _, state = _poll(log)
    # Simulate log rotation: replace the file (new inode) with fresh content.
    log.unlink()
    log.write_text("fresh\n")
    events, state = _poll(log, state=state)
    assert len(events) == 1
    assert events[0]["kind"] == "rotated"
    # Re-baselined: the next poll reads the new file from the start.
    events, state = _poll(log, state=state)
    assert [e["text"] for e in events] == ["fresh"]
    assert events[0]["line_no"] == 1


def test_shrink_reports_rotation(tmp_path):
    log = tmp_path / "app.log"
    log.write_text("a\nb\nc\n")
    _, state = _poll(log)
    log.write_text("a\n")  # truncated in place: size < remembered offset
    events, _ = _poll(log, state=state)
    assert events[0]["kind"] == "rotated"


def test_outside_allowed_roots_refused(tmp_path):
    log = tmp_path / "app.log"
    log.write_text("x\n")
    with pytest.raises(ConnectorError):
        registry.poll("logtail", path=str(log), allowed_roots=[str(tmp_path / "jail")])


def test_missing_file_refused(tmp_path):
    with pytest.raises(ConnectorError):
        registry.poll(
            "logtail",
            path=str(tmp_path / "nope.log"),
            allowed_roots=[str(tmp_path)],
        )


def test_flood_refused_not_half_read(tmp_path):
    log = tmp_path / "app.log"
    log.write_text("\n".join(f"line {i}" for i in range(20)) + "\n")
    with pytest.raises(ConnectorError):
        _poll(log, max_lines=5)


def test_long_lines_truncated(tmp_path):
    log = tmp_path / "app.log"
    log.write_text("x" * 5000 + "\n")
    events, _ = _poll(log, max_line_chars=100)
    assert len(events[0]["text"]) == 100


def test_bad_inputs_refused(tmp_path):
    log = tmp_path / "app.log"
    log.write_text("x\n")
    with pytest.raises(ConnectorError):
        _poll(log, max_lines=0)
    with pytest.raises(ConnectorError):
        _poll(log, max_line_chars=-1)
    with pytest.raises(ConnectorError):
        registry.poll("logtail", path=123, allowed_roots=[str(tmp_path)])
