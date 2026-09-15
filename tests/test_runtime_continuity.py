"""Continuity shelf hardening tests (hermetic, stdlib-only)."""

from __future__ import annotations

import json

import pytest

from levi.runtime.continuity import ContinuityError, ContinuityShelf


@pytest.fixture()
def shelf(tmp_path):
    return ContinuityShelf(path=tmp_path / "shelf.json")


def test_snapshot_validates_text_fields(shelf):
    with pytest.raises(ContinuityError, match="last_ask"):
        shelf.snapshot(last_ask=123)  # type: ignore[arg-type]
    with pytest.raises(ContinuityError, match="last_reply"):
        shelf.snapshot(last_reply=None)  # type: ignore[arg-type]
    frame = shelf.snapshot(last_ask="a" * 600, last_reply="b" * 300)
    assert len(frame.last_ask) == 500
    assert len(frame.last_reply_head) == 240


def test_corrupt_history_degrades_to_empty(tmp_path):
    path = tmp_path / "shelf.json"
    path.write_text(json.dumps({"history": "not-a-list"}))
    assert ContinuityShelf(path=path).history == []
    path.write_text("{bad json")
    assert ContinuityShelf(path=path).history == []


def test_mixed_history_keeps_dict_frames(tmp_path):
    path = tmp_path / "shelf.json"
    path.write_text(json.dumps({"history": ["junk", 42, {"at": "t"}]}))
    shelf = ContinuityShelf(path=path)
    assert shelf.history == [{"at": "t"}]


def test_persist_failure_is_domain_error(shelf):
    path = shelf.path
    shelf.snapshot(last_ask="hi")
    path.unlink()
    path.mkdir()
    with pytest.raises(ContinuityError, match="cannot persist"):
        shelf.snapshot(last_ask="boom")
