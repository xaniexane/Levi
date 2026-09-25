"""Creation Console proof tests — law -> guard -> prove, hermetic.

Each law from levi.hub.create's docstring gets a machine-checkable proof:

1. No artifact files without approval.
2. Dest containment of every ledgered path.
3. HONEST.md present on every ok materialization.
4. Receipt linkage: ledger sha256 hashes match disk; verify catches tamper.
5. list/verify are read-only.
6. Ledger is append-only.
"""

import hashlib
import json
from pathlib import Path

import pytest

from levi.hub import create as C

PROMPT = "a simple todo list web page"


@pytest.fixture()
def ledger(tmp_path, monkeypatch):
    root = tmp_path / "creation"
    monkeypatch.setattr(C, "CREATION_ROOT", root)
    monkeypatch.setattr(C, "LEDGER_PATH", root / "ledger.jsonl")
    return root


def _files_under(dest: Path):
    return [p for p in Path(dest).rglob("*") if p.is_file()]


def test_law1_no_write_without_approval(ledger, tmp_path):
    dest = tmp_path / "build1"
    summary = C.create(PROMPT, str(dest), approve=False)
    assert summary["ok"] is False
    assert summary["approved"] is False
    # Law 1: zero artifact files. (The empty dest dir may exist.)
    assert _files_under(dest) == []
    entry = C.get_creation(summary["id"])
    assert entry["ok"] is False
    assert entry["files"] == []


def test_law2_law3_law4_happy_path(ledger, tmp_path):
    dest = tmp_path / "build2"
    summary = C.create(PROMPT, str(dest), approve=True)
    assert summary["ok"] is True
    assert summary["honest_label"] is True

    # Law 3: honest labeling on every ok materialization.
    honest = dest / "HONEST.md"
    assert honest.exists()
    text = honest.read_text(encoding="utf-8")
    assert "working scaffold" in text
    assert "a production application" in text
    assert "Never claim production-readiness" in text
    assert summary["id"] in text

    # Law 4: receipt linkage — every ledgered file hash matches disk,
    # and Law 2: every ledgered path resolves inside dest.
    entry = C.get_creation(summary["id"])
    assert entry["ok"] is True
    assert len(entry["files"]) >= 2  # generator files + HONEST.md
    dest_r = dest.resolve()
    for f in entry["files"]:
        target = (dest / f["path"]).resolve()
        assert target == dest_r or dest_r in target.parents  # Law 2
        assert target.exists()
        h = hashlib.sha256(target.read_bytes()).hexdigest()
        assert h == f["sha256"]  # Law 4

    # Pipeline stages are all recorded with did/did_not honesty.
    stages = {s["stage"]: s for s in entry["stages"]}
    assert set(stages) >= {"echo", "alpha", "preview", "permission",
                           "materialize", "nexus"}
    assert all(s["ok"] for s in stages.values())


def test_law4_verify_catches_tamper(ledger, tmp_path):
    dest = tmp_path / "build3"
    summary = C.create(PROMPT, str(dest), approve=True)
    cid = summary["id"]

    v = C.verify(cid)
    assert v["ok"] is True
    assert v["mismatches"] == [] and v["missing"] == []

    # Tamper with one generated file.
    victim = dest / summary["files"][0]
    victim.write_text(victim.read_text(encoding="utf-8") + "\n<!-- tampered -->",
                      encoding="utf-8")
    v2 = C.verify(cid)
    assert v2["ok"] is False
    assert str(summary["files"][0]) in v2["mismatches"]

    # Delete the honest label.
    (dest / "HONEST.md").unlink()
    v3 = C.verify(cid)
    assert v3["ok"] is False
    assert "HONEST.md" in v3["missing"]


def test_law5_list_and_verify_are_readonly(ledger, tmp_path):
    dest = tmp_path / "build4"
    summary = C.create(PROMPT, str(dest), approve=True)
    before_files = {str(p): p.stat().st_mtime_ns for p in _files_under(dest)}
    before_ledger = C.LEDGER_PATH.read_bytes()

    C.list_creations()
    C.verify(summary["id"])
    C.get_creation(summary["id"])

    after_files = {str(p): p.stat().st_mtime_ns for p in _files_under(dest)}
    assert after_files == before_files
    assert C.LEDGER_PATH.read_bytes() == before_ledger


def test_law6_ledger_append_only(ledger, tmp_path):
    s1 = C.create(PROMPT, str(tmp_path / "b5a"), approve=True)
    s2 = C.create(PROMPT, str(tmp_path / "b5b"), approve=False)
    assert s1["id"] != s2["id"]
    entries = C.list_creations()
    assert [e["id"] for e in entries] == [s1["id"], s2["id"]]
    # First entry untouched by the second append.
    assert C.get_creation(s1["id"])["ok"] is True
    assert C.get_creation(s2["id"])["ok"] is False
    # No mutation API exists.
    for forbidden in ("update", "delete", "remove", "edit", "rewrite"):
        assert not hasattr(C, forbidden + "_entry")
        assert not hasattr(C, forbidden + "_ledger")


def test_bad_args_raise(ledger, tmp_path):
    with pytest.raises(ValueError):
        C.create("", str(tmp_path / "x"), approve=True)
    with pytest.raises(ValueError):
        C.create("   ", str(tmp_path / "x"), approve=True)
    with pytest.raises(ValueError):
        C.create(PROMPT, "", approve=True)
    with pytest.raises(ValueError):
        C.verify("does-not-exist")


def test_cli_list_and_verify_paths(ledger, tmp_path, capsys):
    dest = tmp_path / "build6"
    summary = C.create(PROMPT, str(dest), approve=True)
    assert C.main(["--list"]) == 0
    out = capsys.readouterr().out
    assert summary["id"] in out
    assert C.main(["--verify", summary["id"]]) == 0
    with pytest.raises(ValueError):
        C.main(["--verify", "nope"])
