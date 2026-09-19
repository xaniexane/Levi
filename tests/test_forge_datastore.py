"""Tests for the Forge data store (core/levi/forge/datastore.py).

Hermetic: LEVI_HOME pinned to tmp dirs; stdlib sqlite3 only.
"""

import json
import os

import pytest

from levi.forge.datastore import ForgeStore, Receipt, StoreError, open_store, store_home


def _store(tmp_path, name="test"):
    return open_store(name, home=tmp_path)


def test_put_get_roundtrip_with_provenance(tmp_path):
    s = _store(tmp_path)
    rcpt = s.put("issues", "i-1", {"title": "ship it"}, origin="forge/cli")
    assert isinstance(rcpt, Receipt)
    assert rcpt.op == "put" and rcpt.revision == 1
    assert rcpt.receipt_id.startswith("ds-")
    doc = s.get("issues", "i-1")
    assert doc["data"] == {"title": "ship it"}
    assert doc["origin"] == "forge/cli"  # provenance rides with every record
    assert doc["revision"] == 1
    s.close()


def test_origin_required_deny_closed(tmp_path):
    s = _store(tmp_path)
    with pytest.raises(StoreError):
        s.put("issues", "i-1", {"t": 1}, origin="")
    with pytest.raises(StoreError):
        s.delete("issues", "i-1", origin="   ")
    s.close()


def test_put_increments_revision(tmp_path):
    s = _store(tmp_path)
    r1 = s.put("c", "d", {"v": 1}, origin="a")
    r2 = s.put("c", "d", {"v": 2}, origin="a")
    assert (r1.revision, r2.revision) == (1, 2)
    assert s.get("c", "d")["data"] == {"v": 2}
    s.close()


def test_delete_is_receipted_and_audited(tmp_path):
    s = _store(tmp_path)
    s.put("c", "d", {"v": 1}, origin="a", note="first")
    rcpt = s.delete("c", "d", origin="a", note="cleanup")
    assert rcpt.op == "delete"
    assert s.get("c", "d") is None
    trail = s.audit_trail(collection="c")
    ops = [e["op"] for e in trail]
    assert ops == ["put", "delete"]
    # nothing silent: the audit row keeps what was deleted
    assert json.loads(trail[-1]["detail"]["deleted_data"]) == {"v": 1}
    s.close()


def test_every_write_lands_in_audit_trail(tmp_path):
    s = _store(tmp_path)
    s.put("a", "1", {}, origin="x")
    s.put("a", "2", {}, origin="x")
    s.put("b", "1", {}, origin="y")
    trail = s.audit_trail()
    assert [e["receipt_id"] for e in trail]
    assert all(e["seq"] for e in trail)
    by_coll = s.audit_trail(collection="a")
    assert len(by_coll) == 2
    s.close()


def test_query_equality_operators_order_limit(tmp_path):
    s = _store(tmp_path)
    s.put("tasks", "t1", {"status": "open", "prio": 3}, origin="t")
    s.put("tasks", "t2", {"status": "done", "prio": 1}, origin="t")
    s.put("tasks", "t3", {"status": "open", "prio": 5}, origin="t")
    rows = s.query("tasks", where={"status": "open"}, order="-prio")
    assert [r["doc_id"] for r in rows] == ["t3", "t1"]
    rows = s.query("tasks", where={"prio": {"$gte": 3}})
    assert sorted(r["doc_id"] for r in rows) == ["t1", "t3"]
    rows = s.query("tasks", where={"status": {"$ne": "done"}}, limit=1)
    assert len(rows) == 1
    rows = s.query("tasks", where={"status": {"$contains": "ope"}})
    assert len(rows) == 2
    rows = s.query("tasks", order="prio", limit=1, offset=1)
    assert rows[0]["doc_id"] == "t1"
    s.close()


def test_query_dotted_path_and_provenance_column(tmp_path):
    s = _store(tmp_path)
    s.put("c", "d1", {"meta": {"kind": "bug"}}, origin="qa")
    s.put("c", "d2", {"meta": {"kind": "feat"}}, origin="dev")
    rows = s.query("c", where={"meta.kind": "bug"})
    assert [r["doc_id"] for r in rows] == ["d1"]
    rows = s.query("c", where={"origin": "dev"})
    assert [r["doc_id"] for r in rows] == ["d2"]
    s.close()


def test_bad_names_and_inputs_refused(tmp_path):
    s = _store(tmp_path)
    with pytest.raises(StoreError):
        s.put("bad name!", "d", {}, origin="x")
    with pytest.raises(StoreError):
        s.put("c", "../evil", {}, origin="x")
    with pytest.raises(StoreError):
        s.put("c", "d", [1, 2, 3], origin="x")  # not a dict
    with pytest.raises(StoreError):
        s.query("c", where={"f": {"$nope": 1}})
    with pytest.raises(StoreError):
        s.delete("c", "missing", origin="x")
    s.close()


def test_transaction_atomicity(tmp_path):
    s = _store(tmp_path)
    s.put("c", "a", {"v": 1}, origin="x")
    with pytest.raises(RuntimeError):
        with s.transaction():
            s.put("c", "b", {"v": 2}, origin="x")
            raise RuntimeError("boom")
    assert s.get("c", "b") is None  # rolled back
    assert s.get("c", "a")["data"] == {"v": 1}
    s.close()


def test_drop_collection_receipted(tmp_path):
    s = _store(tmp_path)
    s.put("c", "a", {}, origin="x")
    rcpt = s.drop_collection("c", origin="x", note="retire")
    assert rcpt.op == "drop-collection"
    assert rcpt.detail["documents_destroyed"] == 1
    assert "c" not in s.list_collections()
    trail = s.audit_trail(collection="c", op="drop-collection")
    assert len(trail) == 1
    s.close()


def test_levi_home_override_honored(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "custom"))
    home = store_home()
    assert str(home).startswith(str(tmp_path / "custom"))
    s = open_store("env-test")
    assert s.path.parent == home
    s.put("c", "d", {"k": "v"}, origin="env")
    assert s.get("c", "d")["data"] == {"k": "v"}
    s.close()


def test_receipt_render(tmp_path):
    s = _store(tmp_path)
    rcpt = s.put("c", "d", {"k": "v"}, origin="forge/cli", note="seed")
    text = rcpt.render()
    assert "put" in text and "forge/cli" in text and "seed" in text
    d = rcpt.to_dict()
    assert d["collection"] == "c" and d["doc_id"] == "d"
    s.close()
