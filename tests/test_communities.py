"""Hermetic tests for levi.communities — no network, tmp HOME."""

from __future__ import annotations

import json

import pytest

from levi.communities import SHELF
from levi.communities.model import (
    CommunityError,
    CommunityStore,
    verify_export,
)
from levi.communities.__main__ import main


def _herm(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LEVI_HOME", raising=False)


def _seed(store: CommunityStore):
    c = store.create("haven", "Haven")
    store.add_channel("haven", "general", "general", topic="lobby")
    store.add_member("haven", "ada", "Ada")
    store.add_member("haven", "grace", "Grace")
    store.add_role("haven", "mod", "Moderator", permissions=["moderate", "post"])
    store.grant_role("haven", "mod", "ada")
    store.post("haven", "general", "ada", "hello world")
    store.set_rules("haven", ["be kind", "no spam"])
    return c


def test_shelf_shape():
    assert SHELF["name"] == "communities"
    assert SHELF["summary"]
    assert isinstance(SHELF["items"], list) and SHELF["items"]


def test_export_import_roundtrip(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    store = CommunityStore()
    _seed(store)
    out = tmp_path / "haven.levicommunity.json"
    store.export("haven", out)
    doc = json.loads(out.read_text())
    assert doc["format"] == "levi-community-export"
    assert set(doc["checksums"]) == {
        "channels",
        "members",
        "roles",
        "messages",
        "governance",
    }
    # import into a fresh home as a different id
    monkeypatch.setenv("HOME", str(tmp_path / "home2"))
    store2 = CommunityStore()
    c2 = store2.import_community(out, as_id="haven2")
    assert c2.name == "Haven"
    assert len(c2.members) == 2 and len(c2.messages) == 1
    assert c2.governance.rules == ["be kind", "no spam"]
    assert c2.roles[0].member_ids == ["ada"]


def test_tampered_export_refused(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    store = CommunityStore()
    _seed(store)
    out = tmp_path / "haven.json"
    store.export("haven", out)
    doc = json.loads(out.read_text())
    doc["sections"]["messages"][0]["text"] = "forged message"
    with pytest.raises(CommunityError, match="checksum mismatch"):
        verify_export(doc)


def test_tampered_checksum_table_refused(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    store = CommunityStore()
    _seed(store)
    out = tmp_path / "haven.json"
    store.export("haven", out)
    doc = json.loads(out.read_text())
    doc["checksums"]["messages"] = "0" * 64
    with pytest.raises(CommunityError):
        verify_export(doc)


def test_import_wrong_format_refused(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    store = CommunityStore()
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"format": "discord-export"}))
    with pytest.raises(CommunityError, match="not a LEVI community export"):
        store.import_community(bad)


def test_import_refuses_overwrite(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    store = CommunityStore()
    _seed(store)
    out = tmp_path / "haven.json"
    store.export("haven", out)
    with pytest.raises(CommunityError, match="already exists"):
        store.import_community(out)


def test_cli_roundtrip(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert main(["create", "c1", "--name", "Club"]) == 0
    assert main(["add-channel", "c1", "lobby", "--name", "lobby"]) == 0
    assert main(["add-member", "c1", "u1", "--name", "Uma"]) == 0
    assert (
        main(["post", "c1", "--channel", "lobby", "--author", "u1", "--text", "hi"])
        == 0
    )
    out = tmp_path / "c1.json"
    assert main(["export", "c1", "--out", str(out)]) == 0
    assert main(["verify", "--in", str(out)]) == 0
    assert "VALID export" in capsys.readouterr().out
    assert main(["status", "c1"]) == 0
    assert "Club" in capsys.readouterr().out
    # unknown channel / member rejected
    assert (
        main(["post", "c1", "--channel", "nope", "--author", "u1", "--text", "x"]) == 1
    )
