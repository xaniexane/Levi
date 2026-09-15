"""Hermetic tests for the backup pipeline.

No network, no real HOME writes (LEVI_HOME is pointed at tmp_path), and
rclone is always mocked or declared missing — the real binary is never
executed by these tests.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tarfile
from pathlib import Path

import pytest

from levi.backup import cli as backup_cli
from levi.backup import config as config_mod
from levi.backup import daily as daily_mod
from levi.backup import restore as restore_mod
from levi.backup import snapshot as snapshot_mod
from levi.backup import sync as sync_mod
from levi.backup.config import load_config, save_config


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A fake ~/.levi with representative state + heavies to exclude."""
    h = tmp_path / "home"
    (h / "growth").mkdir(parents=True)
    (h / "growth" / "journal.jsonl").write_text('{"event":"learned"}\n')
    (h / "memory").mkdir()
    (h / "memory" / "facts.json").write_text('{"a": 1}')
    (h / "bounty").mkdir()
    (h / "bounty" / "findings.json").write_text("[]")
    (h / "corpus.jsonl").write_text("doc one\n")
    # heavies that must be excluded
    (h / "models").mkdir()
    (h / "models" / "weights.pt").write_bytes(b"\x00" * 1024)
    (h / "cache").mkdir()
    (h / "cache" / "blob").write_bytes(b"x" * 512)
    (h / "agent" / "sessions").mkdir(parents=True)
    (h / "agent" / "sessions" / "s1.jsonl").write_text("{}\n")
    monkeypatch.setenv("LEVI_HOME", str(h))
    return h


def _no_rclone(monkeypatch):
    monkeypatch.setattr(config_mod, "rclone_path", lambda: None)
    monkeypatch.setattr(sync_mod, "rclone_path", lambda: None)


class _Proc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _fake_rclone(monkeypatch, dump: dict, copy_rc: int = 0, copy_err: str = ""):
    def fake(*args, timeout=300):
        if args[:2] == ("config", "dump"):
            return _Proc(0, stdout=json.dumps(dump))
        if args[0] == "copy":
            return _Proc(copy_rc, stderr=copy_err)
        return _Proc(1, stderr="unexpected")

    monkeypatch.setattr(config_mod, "rclone_path", lambda: "/usr/bin/rclone")
    monkeypatch.setattr(sync_mod, "rclone_path", lambda: "/usr/bin/rclone")
    monkeypatch.setattr(sync_mod, "run_rclone", fake)


# -- snapshot ---------------------------------------------------------------

def test_snapshot_roundtrip_and_verify(home):
    snap = snapshot_mod.create_snapshot()
    assert Path(snap["tarball"]).exists()
    assert Path(snap["manifest"]).exists()
    assert snap["files"] == 5  # journal, facts, findings, corpus, session
    with tarfile.open(snap["tarball"], "r:gz") as tf:
        names = {m.name for m in tf.getmembers() if m.isfile()}
    assert "models/weights.pt" not in names
    assert "cache/blob" not in names
    assert "growth/journal.jsonl" in names
    assert "corpus.jsonl" in names
    ok, problems = snapshot_mod.verify_snapshot(snap["snapshot_id"])
    assert ok, problems


def test_verify_catches_tampering(home, tmp_path):
    import gzip

    snap = snapshot_mod.create_snapshot()
    p = Path(snap["tarball"])
    # Deterministic tamper: extract, modify one file's content, re-pack.
    # The manifest still holds the original hashes -> must report mismatch.
    work = tmp_path / "work"
    with tarfile.open(p, "r:gz") as tf:
        tf.extractall(work, filter="data")
    (work / "corpus.jsonl").write_text("TAMPERED\n")
    with p.open("wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb") as gz:
            with tarfile.open(fileobj=gz, mode="w") as tf:
                for f in sorted(work.rglob("*")):
                    if f.is_file():
                        tf.add(f, arcname=f.relative_to(work).as_posix())
    ok, problems = snapshot_mod.verify_snapshot(snap["snapshot_id"])
    assert not ok
    assert any("hash mismatch" in x for x in problems)


def test_prune_local_keeps_newest(home):
    ids = [snapshot_mod.create_snapshot(label=f"s{i}")["snapshot_id"] for i in range(3)]
    removed = snapshot_mod.prune_local(keep=2)
    assert len(removed) == 1
    assert removed[0] == ids[0]
    remaining = [s["snapshot_id"] for s in snapshot_mod.list_snapshots()]
    assert ids[2] in remaining and ids[1] in remaining


# -- sync -------------------------------------------------------------------

def test_sync_rclone_missing(home, monkeypatch):
    _no_rclone(monkeypatch)
    snap = snapshot_mod.create_snapshot()
    res = sync_mod.sync_snapshot(snap["tarball"], snap["manifest"], remote="levi-crypt")
    assert res["ok"] is False and res["synced"] is False
    assert "not installed" in res["message"]


def test_sync_remote_unconfigured(home, monkeypatch):
    monkeypatch.setattr(config_mod, "rclone_path", lambda: "/usr/bin/rclone")
    monkeypatch.setattr(sync_mod, "rclone_path", lambda: "/usr/bin/rclone")
    save_config({})
    res = sync_mod.sync_snapshot("/tmp/x.tar.gz", "/tmp/x.manifest.json")
    assert res["ok"] is False
    assert "no remote configured" in res["message"]


def test_verify_remote_accepts_crypt(home, monkeypatch):
    _fake_rclone(monkeypatch, {"levi-crypt": {"type": "crypt", "remote": "drive:LEVI-Backups"}})
    ok, why = sync_mod.verify_remote("levi-crypt")
    assert ok, why
    assert "crypt overlay" in why


def test_verify_remote_rejects_plaintext_backend(home, monkeypatch):
    _fake_rclone(monkeypatch, {"gdrive": {"type": "drive"}})
    ok, why = sync_mod.verify_remote("gdrive")
    assert not ok
    assert "not 'crypt'" in why


def test_sync_success_and_failure_recorded(home, monkeypatch):
    save_config({"remote": "levi-crypt"})
    snap = snapshot_mod.create_snapshot()
    _fake_rclone(monkeypatch, {"levi-crypt": {"type": "crypt", "remote": "drive:LEVI-Backups"}})
    res = sync_mod.sync_snapshot(snap["tarball"], snap["manifest"])
    assert res["ok"] and res["synced"]
    state = json.loads((home / "backup_state.json").read_text())
    assert state["last_sync_ok"] is True

    _fake_rclone(
        monkeypatch,
        {"levi-crypt": {"type": "crypt", "remote": "drive:LEVI-Backups"}},
        copy_rc=1,
        copy_err="directory not found",
    )
    res = sync_mod.sync_snapshot(snap["tarball"], snap["manifest"])
    assert res["ok"] is False
    assert "directory not found" in res["message"]
    state = json.loads((home / "backup_state.json").read_text())
    assert state["last_sync_ok"] is False
    assert "directory not found" in state["last_sync_error"]


# -- restore ----------------------------------------------------------------

def test_restore_stages_and_matches(home):
    snap = snapshot_mod.create_snapshot()
    res = restore_mod.restore_snapshot(snap["snapshot_id"])
    assert res["applied"] is False
    staged = Path(res["extracted_at"])
    assert (staged / "growth" / "journal.jsonl").read_text() == '{"event":"learned"}\n'
    assert (staged / "corpus.jsonl").read_text() == "doc one\n"


def test_restore_refuses_tampered(home):
    snap = snapshot_mod.create_snapshot()
    p = Path(snap["tarball"])
    data = bytearray(p.read_bytes())
    data[len(data) // 2] ^= 0xFF
    p.write_bytes(bytes(data))
    with pytest.raises(ValueError, match="FAILED verification"):
        restore_mod.restore_snapshot(snap["snapshot_id"])


def test_restore_apply_needs_confirmation(home, monkeypatch):
    snap = snapshot_mod.create_snapshot()
    monkeypatch.setattr("builtins.input", lambda _prompt: "no")
    res = restore_mod.restore_snapshot(snap["snapshot_id"], apply=True)
    assert res["applied"] is False
    assert "aborted" in res["message"]


def test_restore_apply_with_yes_updates_state(home):
    snap = snapshot_mod.create_snapshot()
    # change live state, then restore the snapshot over it
    (home / "corpus.jsonl").write_text("CHANGED\n")
    res = restore_mod.restore_snapshot(snap["snapshot_id"], apply=True, yes=True)
    assert res["applied"] is True
    assert (home / "corpus.jsonl").read_text() == "doc one\n"
    # safety snapshot of the pre-restore state exists
    assert res["safety_snapshot"]
    assert any(
        s["snapshot_id"] == res["safety_snapshot"]
        for s in snapshot_mod.list_snapshots()
    )


# -- daily + CLI ------------------------------------------------------------

def test_daily_snapshots_without_remote(home, monkeypatch):
    _no_rclone(monkeypatch)
    save_config({})
    report = daily_mod.run_daily()
    assert report["snapshot"] is not None
    assert "skipped" in report["sync"]["message"]
    assert report["sync"]["synced"] is False


def _args(cmd, **kw):
    ns = argparse.Namespace(backup_cmd=cmd)
    for k, v in kw.items():
        setattr(ns, k, v)
    return ns


def test_cli_status_and_now(home, monkeypatch, capsys):
    _no_rclone(monkeypatch)
    assert backup_cli.cmd_backup(_args("status")) == 0
    out = capsys.readouterr().out
    assert "rclone: NOT INSTALLED" in out
    assert backup_cli.cmd_backup(_args("now", remote=None, label=None)) == 0
    out = capsys.readouterr().out
    assert "snapshot" in out and "no remote configured" in out


def test_cli_configure_rejects_without_rclone(home, monkeypatch, capsys):
    _no_rclone(monkeypatch)
    rc = backup_cli.cmd_backup(_args("configure", remote="levi-crypt"))
    assert rc == 1
    assert "not installed" in capsys.readouterr().out


def test_parser_registers_all_subcommands():
    import argparse as ap

    parser = ap.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    backup_cli.register_backup_parser(sub)
    for cmd, rest in [
        ("now", []),
        ("status", []),
        ("configure", ["--remote", "x"]),
        ("daily", []),
        ("restore", ["--snapshot", "abc"]),
    ]:
        ns = parser.parse_args(["backup", cmd, *rest])
        assert ns.backup_cmd == cmd
