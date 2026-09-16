"""Hermetic tests for the LEVI surgeon (snapshots, cleanup, advancements).

No HOME writes (SnapshotManager takes tmp_path), no network, no
randomness. All fixtures synthetic.
"""

import json

import pytest

from levi.surgeon.surgeon import (
    EXPORT_HEADERS,
    SnapshotManager,
    apply_advancement,
    cleanup_code,
    default_owner_name,
    propose_advancements,
    stamp_header,
)


def _mgr(tmp_path):
    return SnapshotManager(path=tmp_path / "snaps.json")


def test_snapshot_take_list_revert(tmp_path):
    m = _mgr(tmp_path)
    sid = m.take("before-fix", "x = 1\n")
    listed = m.list()
    assert len(listed) == 1
    assert listed[0]["id"] == sid
    assert listed[0]["label"] == "before-fix"
    assert "code" not in listed[0]  # metadata only
    assert m.revert(sid) == "x = 1\n"
    assert m.revert("nope") is None


def test_snapshot_persists(tmp_path):
    m = _mgr(tmp_path)
    sid = m.take("persist", "y = 2\n")
    m2 = _mgr(tmp_path)
    assert m2.revert(sid) == "y = 2\n"


def test_snapshot_rejects_non_str(tmp_path):
    with pytest.raises(ValueError, match="code must be str"):
        _mgr(tmp_path).take("bad", 123)


def test_cleanup_code_fixes(tmp_path):
    text = "def f():\n\tif x == None:\n\t\tpass   \n\n\n\n"
    cleaned, fixes = cleanup_code(text)
    assert "\t" not in cleaned
    assert "x is None" in cleaned
    assert "   \n" not in cleaned
    assert fixes >= 3
    assert cleaned.endswith("\n")


def test_cleanup_code_not_equal_none(tmp_path):
    cleaned, _ = cleanup_code("if y != None:\n    pass\n")
    assert "y is not None" in cleaned


def test_cleanup_code_rejects_non_str():
    with pytest.raises(ValueError, match="text must be str"):
        cleanup_code(None)


def test_propose_advancements_python(tmp_path):
    advs = propose_advancements("x = 1", "mod.py")
    ids = {a.id for a in advs}
    assert "adv_elite_cleanup" in ids
    assert "adv_type_hints" in ids  # .py gets the type-hint pass
    assert all(a.risk in ("LOW", "MED") for a in advs)


def test_propose_advancements_js_no_type_hints():
    advs = propose_advancements("var x = 1;", "mod.js")
    assert "adv_type_hints" not in {a.id for a in advs}


def test_apply_advancement_snapshot_first(tmp_path):
    m = _mgr(tmp_path)
    res = apply_advancement("x=1\n", "adv_hitl_note", snapshots=m)
    assert res["ok"] is True
    assert "human confirmation required" in res["code"]
    assert m.revert(res["snapshot_id"]) == "x=1\n"


def test_apply_advancement_cleanup(tmp_path):
    res = apply_advancement(
        "x\t= 1   \n", "adv_elite_cleanup", snapshots=_mgr(tmp_path)
    )
    assert res["ok"] is True
    assert "\t" not in res["code"]


def test_apply_advancement_unknown_id(tmp_path):
    res = apply_advancement("x = 1\n", "adv_nope", snapshots=_mgr(tmp_path))
    assert res["ok"] is False
    assert "unknown advancement" in res["reason"]


def test_stamp_header_proprietary():
    res = stamp_header("x = 1\n", "proprietary", owner="Test Owner")
    assert "Test Owner" in res["text"]
    assert "All Rights Reserved" in res["text"]
    assert res["text"].endswith("x = 1\n")


def test_stamp_header_oss():
    res = stamp_header("x = 1\n", "oss", owner="Test Owner")
    assert "SPDX-License-Identifier: MIT" in res["text"]


def test_stamp_header_already_present():
    code = "/**\n * Copyright (c) 2026 Someone\n */\n\nx = 1\n"
    res = stamp_header(code, "proprietary", owner="Other")
    assert res["text"] == code
    assert res["note"] == "header already present"


def test_stamp_header_unknown_mode():
    with pytest.raises(ValueError, match="unknown mode"):
        stamp_header("x", "encrypted_stub")


def test_export_headers_only_two_modes():
    # Free core forever: no tier-limited / code-withholding modes exist.
    assert set(EXPORT_HEADERS) == {"proprietary", "oss"}


def test_default_owner_name_env(monkeypatch):
    monkeypatch.setenv("LEVI_OWNER_NAME", "Env Owner")
    assert default_owner_name() == "Env Owner"


def test_default_owner_name_placeholder(monkeypatch, tmp_path):
    monkeypatch.delenv("LEVI_OWNER_NAME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))  # no owner.json there
    name = default_owner_name()
    assert name and "@" not in name  # never an email, never hardcoded identity


def test_owner_json(monkeypatch, tmp_path):
    monkeypatch.delenv("LEVI_OWNER_NAME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".levi").mkdir()
    (tmp_path / ".levi" / "owner.json").write_text(json.dumps({"name": "File Owner"}))
    # Path.home() reads $HOME on posix
    import pathlib

    monkeypatch.setattr(pathlib.Path, "home", classmethod(lambda cls: tmp_path))
    assert default_owner_name() == "File Owner"
    # restore not needed: monkeypatch undoes it
