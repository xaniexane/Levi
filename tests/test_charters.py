"""Hermetic tests for levi.charters — no network, tmp HOME."""

from __future__ import annotations

import json
import stat

import pytest

from levi.charters import SHELF
from levi.charters.charters import CharterError, CharterStore
from levi.charters.__main__ import main


def _herm(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LEVI_HOME", raising=False)


def test_shelf_shape():
    assert SHELF["name"] == "charters"
    assert SHELF["summary"]
    assert isinstance(SHELF["items"], list) and SHELF["items"]


def test_new_signs_and_verifies(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    store = CharterStore()
    doc = store.new("haven-c", "haven", "ada", rules=["be kind"])
    assert doc["version"] == 1
    assert store.verify("haven-c") is True
    # founder key is owner-only
    mode = stat.S_IMODE((tmp_path / ".levi" / "charters" / "haven-c.key").stat().st_mode)
    assert mode == 0o600


def test_tampered_charter_fails_verify(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    store = CharterStore()
    store.new("haven-c", "haven", "ada", rules=["be kind"])
    p = tmp_path / ".levi" / "charters" / "haven-c.charter.json"
    doc = json.loads(p.read_text())
    doc["rules"][0]["text"] = "be cruel"
    p.write_text(json.dumps(doc))
    assert store.verify("haven-c") is False


def test_amendment_quorum_enforced(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    store = CharterStore()
    store.new("c1", "haven", "ada")
    store.set_amendment("c1", "2/3 of mods", 2)
    with pytest.raises(CharterError, match="needs 2 distinct approvals"):
        store.amend("c1", ["add rule"], ["ada"])
    doc = store.amend("c1", ["add rule"], ["ada", "grace"])
    assert doc["version"] == 2
    assert doc["history"][-1]["approvals_claimed"] == ["ada", "grace"]
    assert store.verify("c1") is True


def test_mod_action_requires_reason(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    store = CharterStore()
    store.new("c1", "haven", "ada")
    with pytest.raises(CharterError, match="REQUIRE a reason"):
        store.mod_action("c1", "ada", "ban", "mallory", "   ")
    a = store.mod_action("c1", "ada", "warn", "mallory", "spam x3")
    ap = store.appeal("c1", a["id"], "mallory", "it was a test post")
    assert ap["status"] == "open"
    decided = store.decide_appeal("c1", ap["id"], "grace", "overturned", note="first offense")
    assert decided["status"] == "overturned"
    with pytest.raises(CharterError, match="already decided"):
        store.decide_appeal("c1", ap["id"], "grace", "upheld")


def test_export_import_roundtrip_rekeys(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    store = CharterStore()
    store.new("c1", "haven", "ada", rules=["be kind"])
    store.mod_action("c1", "ada", "warn", "mallory", "spam")
    out = tmp_path / "c1.levicharter.json"
    store.export("c1", out)
    monkeypatch.setenv("HOME", str(tmp_path / "home2"))
    store2 = CharterStore()
    cid = store2.import_charter(out, as_id="c1b")
    assert cid == "c1b"
    assert store2.get("c1b")["rules"][0]["text"] == "be kind"
    assert len(store2.mod_log("c1b")) == 1
    # re-keyed locally: history says so, and local verify passes
    assert "re-keyed locally" in store2.get("c1b")["history"][-1]["changes"][0]
    assert store2.verify("c1b") is True


def test_tampered_charter_export_refused(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    store = CharterStore()
    store.new("c1", "haven", "ada", rules=["be kind"])
    out = tmp_path / "c1.json"
    store.export("c1", out)
    doc = json.loads(out.read_text())
    doc["sections"]["charter"]["rules"][0]["text"] = "be cruel"
    out.write_text(json.dumps(doc))
    with pytest.raises(CharterError, match="checksum mismatch"):
        store.import_charter(out, as_id="c2")


def test_attach_writes_charter_ref_into_community(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    from levi.communities.model import CommunityStore
    cs = CommunityStore()
    cs.create("haven", "Haven")
    store = CharterStore()
    store.new("haven-c", "haven", "ada")
    ref = store.attach("haven-c", "haven")
    assert ref["id"] == "haven-c"
    got = CommunityStore().get("haven")
    assert got.governance.charter_ref["id"] == "haven-c"
    assert got.governance.charter_ref["checksum"] == ref["checksum"]


def test_cli_roundtrip(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert main(["new", "c1", "--community", "haven", "--founder", "ada",
                 "--rules", "be kind", "no spam"]) == 0
    assert main(["verify", "c1"]) == 0
    assert "VALID" in capsys.readouterr().out
    assert main(["mod", "c1", "--moderator", "ada", "--action", "warn",
                 "--target", "mallory", "--reason", "spam"]) == 0
    assert main(["show", "c1"]) == 0
    assert "be kind" in capsys.readouterr().out
    assert main(["modlog", "c1"]) == 0
    assert "mallory" in capsys.readouterr().out
    out = tmp_path / "c1.json"
    assert main(["export", "c1", "--out", str(out)]) == 0
    assert main(["import", "--in", str(out), "--as", "c2"]) == 0
    assert "re-keyed locally" in capsys.readouterr().out
    # quorum refusal path
    assert main(["set-amendment", "c2", "--procedure", "vote", "--quorum", "2"]) == 0
    assert main(["amend", "c2", "--changes", "x", "--approvals", "ada"]) == 1
