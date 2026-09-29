"""Tests for the intake connector (drop-folder staging ear)."""

import pytest

from levi.connectors import registry
from levi.connectors.base import ConnectorError
from levi.connectors import intake as intake_mod  # noqa: F401  (self-registers)


def _poll(tmp_path, **kw):
    kw.setdefault("allowed_roots", [str(tmp_path)])
    return registry.poll("intake", path=str(tmp_path), **kw)


def test_intake_registered():
    assert registry.get("intake").id == "intake"


def test_new_file_emits_candidate_once(tmp_path):
    (tmp_path / "note.txt").write_text("hello world\nsecond line\n")
    events, state = _poll(tmp_path)
    assert len(events) == 1
    ev = events[0]
    assert ev["kind"] == "intake_candidate"
    assert ev["path"] == "note.txt"
    assert ev["bytes"] > 0
    assert ev["sniff"] == "text"
    assert ev["head"] == "hello world"
    assert ev["quarantine"] is None
    assert len(ev["sha256"]) == 64
    # second poll: already seen, never re-emits
    events2, _state2 = _poll(tmp_path, state=state)
    assert events2 == []


def test_modified_file_does_not_reemit(tmp_path):
    f = tmp_path / "doc.txt"
    f.write_text("v1")
    _events, state = _poll(tmp_path)
    f.write_text("v2 changed content")
    events, _state = _poll(tmp_path, state=state)
    assert events == []  # intake is one-shot


def test_empty_and_binary_sniff(tmp_path):
    (tmp_path / "empty.txt").write_text("")
    (tmp_path / "blob.bin").write_bytes(bytes(range(256)))
    events, _state = _poll(tmp_path)
    by_path = {e["path"]: e for e in events}
    assert by_path["empty.txt"]["sniff"] == "empty"
    assert by_path["blob.bin"]["sniff"] == "binary"
    assert by_path["blob.bin"]["head"] == ""


def test_oversize_reported_but_quarantined(tmp_path):
    (tmp_path / "big.bin").write_bytes(b"x" * 2048)
    events, _state = _poll(tmp_path, max_bytes=100)
    assert len(events) == 1
    assert events[0]["quarantine"] == {"reason": "oversize"}
    assert events[0]["bytes"] == 2048  # still reported honestly


def test_escaping_symlink_skipped(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    ext = tmp_path / "ext"
    ext.mkdir()
    (ext / "secret.txt").write_text("not yours")
    (inbox / "evil").symlink_to(ext / "secret.txt")  # escapes the allowed root
    events, _state = registry.poll(
        "intake", path=str(inbox), allowed_roots=[str(inbox)]
    )
    assert events == []  # skipped, never read


def test_path_outside_roots_refused(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    ext = tmp_path / "ext"
    ext.mkdir()
    with pytest.raises(ConnectorError):
        registry.poll("intake", path=str(ext), allowed_roots=[str(inbox)])


def test_missing_path_refused():
    with pytest.raises(ConnectorError):
        registry.poll("intake", path="/does/not/exist", allowed_roots=["/"])


def test_state_roundtrip_is_stable(tmp_path):
    (tmp_path / "a.txt").write_text("aaa")
    events, state = _poll(tmp_path)
    assert len(events) == 1
    (tmp_path / "b.txt").write_text("bbb")
    events, state = _poll(tmp_path, state=state)
    assert [e["path"] for e in events] == ["b.txt"]
    events, _state = _poll(tmp_path, state=state)
    assert events == []
