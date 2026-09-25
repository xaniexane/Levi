"""Tests for levi.plugins.hn — the credentialless Hacker News reader."""

from __future__ import annotations

import pytest

from levi.plugins import hn as hn_mod
from levi.plugins.hn import HackerNewsConnector
from levi.plugins.registry import get_connector, list_connectors


def test_registered_and_credentialless():
    ids = [c.id for c in list_connectors()]
    assert "hn" in ids
    inst = get_connector("hn")
    assert isinstance(inst, HackerNewsConnector)
    assert inst.credential() == "public"  # no env var, no gate


def test_read_only_never_requires_confirmation():
    assert HackerNewsConnector.requires_confirmation is False
    assert not any(c.write for c in HackerNewsConnector.capabilities)
    assert not any(o.write for o in HackerNewsConnector.operations)


def _fake_download_json(url):
    if url.endswith("topstories.json"):
        return [111, 222, 333, 444]
    if url.endswith("newstories.json"):
        return [555, 666]
    if "/item/111.json" in url:
        return {
            "id": 111,
            "type": "story",
            "title": "Test story",
            "url": "https://example.test/story",
            "score": 42,
            "by": "tester",
            "time": 1758412800,
            "descendants": 7,
            "kids": [112, 113],
        }
    raise AssertionError(f"unexpected url {url}")


@pytest.fixture()
def no_network(monkeypatch):
    monkeypatch.setattr(hn_mod, "_download_json", _fake_download_json)


def test_top_respects_limit(no_network):
    inst = HackerNewsConnector()
    res = inst.execute("top", {"limit": 2})
    assert res.ok and res.status == "ok"
    assert res.data["feed"] == "top"
    assert res.data["ids"] == [111, 222]


def test_new(no_network):
    inst = HackerNewsConnector()
    res = inst.execute("new", {})
    assert res.ok
    assert res.data["ids"] == [555, 666]


def test_item_normalized(no_network):
    inst = HackerNewsConnector()
    res = inst.execute("item", {"id": 111})
    assert res.ok
    item = res.data
    assert item["title"] == "Test story"
    assert item["score"] == 42
    assert item["by"] == "tester"
    assert item["time_iso"] == "2025-09-21T00:00:00Z"
    assert item["kids"] == [112, 113]


def test_item_id_validated():
    inst = HackerNewsConnector()
    for bad in ("abc", -3, 0, None):
        res = inst.execute("item", {"id": bad})
        assert res.ok is False and res.status == "invalid_params"


def test_limit_validated():
    inst = HackerNewsConnector()
    for bad in (0, 51, "many"):
        res = inst.execute("top", {"limit": bad})
        assert res.ok is False and res.status == "invalid_params"


def test_unknown_operation():
    inst = HackerNewsConnector()
    res = inst.execute("bogus", {})
    assert res.ok is False and res.status == "unknown_operation"


def test_api_error_is_honest(monkeypatch):
    from levi.plugins.registry import ConnectorAPIError

    def boom(url):
        raise ConnectorAPIError("server down — nothing fetched.")

    monkeypatch.setattr(hn_mod, "_download_json", boom)
    inst = HackerNewsConnector()
    res = inst.execute("top", {})
    assert res.ok is False and res.status == "api_error"
    assert "nothing fetched" in res.message
