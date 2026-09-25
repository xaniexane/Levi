"""Tests for levi.plugins.arxiv — the credentialless arXiv search reader."""

from __future__ import annotations

import pytest

from levi.plugins import arxiv as arxiv_mod
from levi.plugins.arxiv import ArxivConnector
from levi.plugins.registry import get_connector, list_connectors

ATOM_SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>ArXiv Query</title>
<entry>
<id>http://arxiv.org/abs/2401.12345v1</id>
<title>  A Test Paper on
  Local Brains </title>
<author><name>Ada Lovelace</name></author>
<author><name>Alan Turing</name></author>
<summary>A short abstract about local-first models.</summary>
<published>2024-01-20T12:00:00Z</published>
<updated>2024-01-21T12:00:00Z</updated>
<category term="cs.AI"/>
<category term="cs.LG"/>
</entry>
</feed>"""


def test_registered_and_credentialless():
    ids = [c.id for c in list_connectors()]
    assert "arxiv" in ids
    inst = get_connector("arxiv")
    assert isinstance(inst, ArxivConnector)
    assert inst.credential() == "public"  # no env var, no gate


def test_read_only_never_requires_confirmation():
    assert ArxivConnector.requires_confirmation is False
    assert not any(c.write for c in ArxivConnector.capabilities)
    assert not any(o.write for o in ArxivConnector.operations)


@pytest.fixture()
def no_network(monkeypatch):
    seen = {}

    def fake_download(url):
        seen["url"] = url
        return ATOM_SAMPLE

    monkeypatch.setattr(arxiv_mod, "_download", fake_download)
    return seen


def test_search_parses_atom(no_network):
    inst = ArxivConnector()
    res = inst.execute("search", {"query": "local brains", "max_results": 5})
    assert res.ok and res.status == "ok"
    assert res.data["count"] == 1
    paper = res.data["papers"][0]
    assert paper["title"] == "A Test Paper on Local Brains"
    assert paper["authors"] == ["Ada Lovelace", "Alan Turing"]
    assert paper["categories"] == ["cs.AI", "cs.LG"]
    assert paper["published"] == "2024-01-20T12:00:00Z"
    assert "max_results=5" in no_network["url"]
    assert "sortBy=relevance" in no_network["url"]


def test_lookup(no_network):
    inst = ArxivConnector()
    res = inst.execute("lookup", {"arxiv_id": "2401.12345"})
    assert res.ok
    assert res.data["title"] == "A Test Paper on Local Brains"
    assert "id_list=2401.12345" in no_network["url"]


def test_search_params_validated():
    inst = ArxivConnector()
    for params in (
        {},
        {"query": ""},
        {"query": "x" * 301},
        {"query": "ok", "max_results": 0},
        {"query": "ok", "max_results": 51},
        {"query": "ok", "sort": "newest"},
        {"query": "ok", "order": "sideways"},
    ):
        res = inst.execute("search", params)
        assert res.ok is False and res.status == "invalid_params", params


def test_lookup_id_validated():
    inst = ArxivConnector()
    for bad in ("", "not-an-id", "2401", "abc.def"):
        res = inst.execute("lookup", {"arxiv_id": bad})
        assert res.ok is False and res.status == "invalid_params"


def test_lookup_empty_result_is_honest(monkeypatch):
    empty = (
        b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>"""
    )
    monkeypatch.setattr(arxiv_mod, "_download", lambda url: empty)
    inst = ArxivConnector()
    res = inst.execute("lookup", {"arxiv_id": "2401.99999"})
    assert res.ok is False and res.status == "api_error"


def test_api_error_is_honest(monkeypatch):
    from levi.plugins.registry import ConnectorAPIError

    def boom(url):
        raise ConnectorAPIError("server down — nothing fetched.")

    monkeypatch.setattr(arxiv_mod, "_download", boom)
    inst = ArxivConnector()
    res = inst.execute("search", {"query": "x"})
    assert res.ok is False and res.status == "api_error"
    assert "nothing fetched" in res.message
