"""Invariant tests for Cybrus BACK backup-integrity (levi.cybrus.backup_manifest).

The PROOF gate for laws BM1-BM4 — machine-checked invariants, honestly
named: nothing here is formally proven, only tested against the laws.

Hermetic: everything under tmp_path — no real HOME writes. Includes the
RED-team assertions: manifest tampering, archive tampering, archive
deletion, and a corrupt manifest must all fail closed with the exact
failing sequence number.
"""

import json

import pytest

from levi.cybrus import backup_manifest as bm
from levi.cybrus._paths import CorruptStoreError
from levi.cybrus.audit import AuditEngine
from levi.cybrus.backup_manifest import ManifestEngine, ManifestError


@pytest.fixture()
def eng(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    return ManifestEngine(
        backup_dir=backup_dir, manifest_path=tmp_path / "manifest.jsonl"
    )


def _make_archive(backup_dir, name, content=b"encrypted-bytes"):
    p = backup_dir / name
    p.write_bytes(content)
    return p


# --- BM1: hash-chained entries -----------------------------------------------


def test_laws_declared(eng):
    assert [lid for lid, _ in bm.LAWS] == ["BM1", "BM2", "BM3", "BM4"]


def test_record_chains_to_genesis_and_predecessor(eng):
    a = _make_archive(eng.backup_dir, "a.7z")
    b = _make_archive(eng.backup_dir, "b.7z", b"other-bytes")
    e0 = eng.record(a, "back-pair")
    e1 = eng.record(b, "back-pair")
    assert e0["seq"] == 0
    assert e0["prev_hash"] == bm.GENESIS
    assert e1["seq"] == 1
    assert e1["prev_hash"] == e0["entry_hash"]
    assert e0["entry_hash"] != e1["entry_hash"]
    result = eng.verify()
    assert result["ok"] is True and result["checked"] == 2


def test_record_refuses_outside_backup_dir(eng, tmp_path):
    outsider = tmp_path / "evil.7z"
    outsider.write_bytes(b"x")
    with pytest.raises(ManifestError):
        eng.record(outsider, "back-pair")


def test_record_refuses_missing_file(eng):
    with pytest.raises(ManifestError):
        eng.record(eng.backup_dir / "nope.7z", "back-pair")


# --- BM2: full-chain verification, fail closed --------------------------------


def test_tampered_manifest_entry_fails_closed(eng):
    a = _make_archive(eng.backup_dir, "a.7z")
    b = _make_archive(eng.backup_dir, "b.7z", b"other-bytes")
    eng.record(a, "back-pair")
    eng.record(b, "back-pair")
    # RED: flip one hex char in the first entry's recorded sha256.
    lines = eng.manifest_path.read_text(encoding="utf-8").splitlines()
    entry = json.loads(lines[0])
    entry["sha256"] = "0" + entry["sha256"][1:]
    lines[0] = json.dumps(entry, sort_keys=True, separators=(",", ":"))
    eng.manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = eng.verify()
    assert result["ok"] is False
    reasons = {(f["seq"], f["reason"]) for f in result["failures"]}
    assert (0, "entry_hash_mismatch") in reasons


def test_spliced_manifest_link_fails_closed(eng):
    a = _make_archive(eng.backup_dir, "a.7z")
    b = _make_archive(eng.backup_dir, "b.7z", b"other-bytes")
    eng.record(a, "back-pair")
    eng.record(b, "back-pair")
    # RED: point the second entry at a forged predecessor hash.
    lines = eng.manifest_path.read_text(encoding="utf-8").splitlines()
    entry = json.loads(lines[1])
    entry["prev_hash"] = "f" * 64
    lines[1] = json.dumps(entry, sort_keys=True, separators=(",", ":"))
    eng.manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = eng.verify()
    assert result["ok"] is False
    assert any(
        f["seq"] == 1 and f["reason"] == "chain_break" for f in result["failures"]
    )


# --- BM3: archive re-hash detects on-disk tampering ---------------------------


def test_tampered_archive_fails_verification(eng):
    a = _make_archive(eng.backup_dir, "a.7z")
    eng.record(a, "back-pair")
    assert eng.verify()["ok"] is True
    # RED: modify one byte of the archive on disk.
    with open(a, "r+b") as fh:
        fh.seek(0)
        fh.write(b"X")
    result = eng.verify()
    assert result["ok"] is False
    assert any(
        f["seq"] == 0 and f["reason"] == "archive_tampered"
        for f in result["failures"]
    )


def test_deleted_archive_fails_verification(eng):
    a = _make_archive(eng.backup_dir, "a.7z")
    eng.record(a, "back-pair")
    a.unlink()
    result = eng.verify()
    assert result["ok"] is False
    assert any(
        f["seq"] == 0 and f["reason"] == "archive_missing"
        for f in result["failures"]
    )


# --- BM4: append-only ----------------------------------------------------------


def test_manifest_has_no_edit_or_delete_api(eng):
    for name in ("delete", "edit", "rewrite", "update", "remove", "truncate"):
        assert not hasattr(eng, name), f"append-only violated: {name} exists"


def test_snapshot_is_idempotent(eng):
    _make_archive(eng.backup_dir, "a.7z")
    _make_archive(eng.backup_dir, "b.7z", b"other-bytes")
    first = eng.snapshot("back-pair")
    assert first["recorded"] == ["a.7z", "b.7z"] and first["skipped"] == []
    second = eng.snapshot("back-pair")
    assert second["recorded"] == [] and sorted(second["skipped"]) == ["a.7z", "b.7z"]
    assert eng.verify()["ok"] is True


def test_corrupt_manifest_quarantined_not_absorbed(eng):
    _make_archive(eng.backup_dir, "a.7z")
    eng.record(_make_archive(eng.backup_dir, "b.7z", b"z"), "back-pair")
    eng.manifest_path.write_text("this is not jsonl{{{\n", encoding="utf-8")
    with pytest.raises(CorruptStoreError):
        eng._read_entries()
    quarantined = list(eng.manifest_path.parent.glob("manifest.corrupt-*.jsonl"))
    assert quarantined, "corrupt manifest must be quarantined for forensics"
    # A fresh chain starts rather than inventing continuity.
    eng.record(eng.backup_dir / "a.7z", "back-pair")
    assert eng.verify()["ok"] is True


def test_verify_and_record_are_audit_logged(eng):
    a = _make_archive(eng.backup_dir, "a.7z")
    eng.record(a, "back-pair")
    eng.verify()
    events = {e["event"] for e in AuditEngine().tail(20)}
    assert "backup.manifest.recorded" in events
    assert "backup.manifest.verified" in events
    # Metadata only: audit details never carry archive contents.
    blob = json.dumps(AuditEngine().tail(20))
    assert "encrypted-bytes" not in blob


def test_status_reports_unrecorded_archives(eng):
    _make_archive(eng.backup_dir, "a.7z")
    _make_archive(eng.backup_dir, "new.7z", b"fresh")
    eng.record(eng.backup_dir / "a.7z", "back-pair")
    status = eng.status()
    assert status["manifest_entries"] == 1
    assert status["unrecorded_archives"] == ["new.7z"]


def test_describe_posture_is_honest(eng):
    p = eng.describe_posture()
    assert p["prevents_tampering"] is False
    assert p["detects_tampering"] is True
    assert p["append_only"] is True
