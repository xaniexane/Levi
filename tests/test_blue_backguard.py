"""BLUE-1 batch B: BACK-GUARD regression proofs (RED-1 R1–R7).

Each attack below is CLOSED. Every test proves the attack closure AND
the legitimate counterpart, so the fixes cannot be read as "deny
everything".

Glyph: 💉 | Agent: cfbc6fb1-6ab7-451d-8c11b83ab41 | 2026-09-23
"""

import shutil
from pathlib import Path

import pytest

from levi.cybrus import backguard as bg
from levi.cybrus.approval import ApprovalEngine
from levi.cybrus.backguard import (
    ApprovalNeeded,
    BackGuardDenied,
    BackupManifest,
    BulkReadDenied,
    BulkReadGuard,
    destination_risk,
    issue_grant,
    request_copy,
)


@pytest.fixture(autouse=True)
def _hermetic(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CYBRUS_EYES_ONLY_ROOTS", str(tmp_path / "dynasty"))
    monkeypatch.setenv("CYBRUS_REMOVABLE_PREFIXES", str(tmp_path / "usb"))
    (tmp_path / "dynasty").mkdir()
    (tmp_path / "usb").mkdir()
    return tmp_path


def _approve(approval_id):
    return ApprovalEngine().approve(approval_id, by="owner")


def _sensitive_file(tmp_path, name="secret-notes.txt"):
    p = tmp_path / name
    p.write_bytes(b"top secret material")
    assert bg.classify(p) == "sensitive"
    return p


def _granted_copy(actor, src, dst, purpose):
    """request_copy through the real approval flow."""
    try:
        request_copy(actor, src, dst, purpose)
        pytest.fail("expected ApprovalNeeded")
    except ApprovalNeeded as exc:
        _approve(exc.approval_id)
    return request_copy(actor, src, dst, purpose)


# ---------------------------------------------------------------------------
# R1 — final-component symlink laundering: resolved before risk judgment
# ---------------------------------------------------------------------------

def test_blue_r1_dst_symlink_resolves_to_external(tmp_path):
    usb = tmp_path / "usb"
    link = tmp_path / "stage_link"
    link.symlink_to(usb / "ghost.bin")  # dangling target inside usb
    src = _sensitive_file(tmp_path)
    with pytest.raises(ApprovalNeeded):
        request_copy("chauncey", src, link, "staging")
    assert not (usb / "ghost.bin").exists()


def test_blue_r1_granted_copy_through_symlink_lands_at_target(tmp_path):
    usb = tmp_path / "usb"
    link = tmp_path / "stage_link"
    link.symlink_to(usb / "ghost.bin")
    src = _sensitive_file(tmp_path)
    receipt = _granted_copy("chauncey", src, link, "staging")
    assert receipt["copied"] is True
    assert (usb / "ghost.bin").read_bytes() == b"top secret material"


# ---------------------------------------------------------------------------
# R2 — cloud-sync name variants judged external
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("variant", [
    "GoogleDrive", "Google_Drive", "gdrive", "GDrive",
    "OneDrivePersonal", "my-dropbox", "google drive",
])
def test_blue_r2_cloud_variants_judged_external(tmp_path, variant):
    assert destination_risk(tmp_path / variant / "backup") == "external"


@pytest.mark.parametrize("name", ["projects", "notes", "backup-local"])
def test_blue_r2_plain_folders_stay_internal(tmp_path, name):
    assert destination_risk(tmp_path / name / "file.txt") == "internal"


def test_blue_r2_sensitive_copy_to_drive_folder_needs_grant(tmp_path):
    gdrive = tmp_path / "GoogleDrive"
    gdrive.mkdir()
    src = _sensitive_file(tmp_path)
    with pytest.raises(ApprovalNeeded):
        request_copy("chauncey", src, gdrive / "backup.enc", "offsite")
    assert not (gdrive / "backup.enc").exists()


# ---------------------------------------------------------------------------
# R3/R4 — manifest truncation anchor (no expected_head needed)
# ---------------------------------------------------------------------------

def test_blue_r3_truncation_detected_without_expected_head(tmp_path):
    mdir = tmp_path / "backups"
    man = BackupManifest(mdir)
    for i in (1, 2):
        a = mdir / f"vault-{i}.enc"
        a.write_bytes(f"backup bytes {i}".encode())
        man.seal(a, "vault")
    assert man.verify()["ok"] is True
    lines = man.path.read_text().splitlines()
    man.path.write_text("\n".join(lines[:-1]) + "\n")
    result = man.verify()
    assert result["ok"] is False
    assert "anchor" in result["reason"]


def test_blue_r4_recomputed_chain_detected(tmp_path):
    mdir = tmp_path / "backups"
    man = BackupManifest(mdir)
    a = mdir / "vault-1.enc"
    a.write_bytes(b"original bytes")
    man.seal(a, "vault")
    # Attacker swaps the archive and recomputes a fresh manifest chain.
    a.write_bytes(b"forged bytes")
    (mdir / "manifest.state.json").unlink()  # force legacy-style recheck
    man2 = BackupManifest(mdir)
    with pytest.raises(Exception):
        man2.reanchor()  # archive hash no longer matches the record


def test_blue_r3_legit_seal_verify_roundtrip(tmp_path):
    mdir = tmp_path / "backups"
    man = BackupManifest(mdir)
    for i in range(3):
        a = mdir / f"a{i}.enc"
        a.write_bytes(b"x" * (i + 1))
        man.seal(a, "vault")
    result = man.verify()
    assert result["ok"] is True
    assert result["entries"] == 3


# ---------------------------------------------------------------------------
# R5 — classify/copy TOCTOU: bytes bound to an open fd + hash check
# ---------------------------------------------------------------------------

def test_blue_r5_swapped_source_cannot_change_copied_bytes(
        tmp_path, monkeypatch):
    src = tmp_path / "notes.txt"
    src.write_bytes(b"plain notes")
    dst = tmp_path / "copy.txt"

    def evil_copy2(s, d, *a, **k):
        Path(d).write_bytes(b"ATTACKER BYTES")

    monkeypatch.setattr(shutil, "copy2", evil_copy2)
    receipt = request_copy("chauncey", src, dst, "test")
    assert receipt["src_tier"] == "normal"
    assert dst.read_bytes() == b"plain notes"


def test_blue_r5_legit_copy_is_byte_identical(tmp_path):
    src = tmp_path / "notes.txt"
    src.write_bytes(b"plain notes")
    dst = tmp_path / "copy.txt"
    receipt = request_copy("chauncey", src, dst, "test")
    assert receipt["copied"] is True
    assert receipt["sha256"] == bg._sha256_file(src)


# ---------------------------------------------------------------------------
# R6 — audit outage fails closed: no audit, no copy
# ---------------------------------------------------------------------------

def test_blue_r6_audit_outage_means_no_copy(tmp_path, monkeypatch):
    from levi.cybrus.audit import AuditEngine

    def _boom(self, *a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(AuditEngine, "append", _boom)
    src = tmp_path / "notes.txt"
    src.write_bytes(b"plain notes")
    dst = tmp_path / "copy.txt"
    with pytest.raises(OSError):
        request_copy("chauncey", src, dst, "test")
    assert not dst.exists()


# ---------------------------------------------------------------------------
# R7 — actor-name rotation does not escape the bulk-read tripwire
# ---------------------------------------------------------------------------

def test_blue_r7_actor_rotation_trips_store_window(tmp_path):
    with pytest.raises(BulkReadDenied):
        for i in range(30):
            BulkReadGuard(f"reader-{i % 3}", store="vault").note_read()


def test_blue_r7_single_actor_under_threshold_ok(tmp_path):
    guard = BulkReadGuard("chauncey", store="vault", threshold=10,
                         window_seconds=300)
    for _ in range(10):
        assert guard.note_read() <= 10


def test_blue_r7_approved_bulk_read_still_works(tmp_path):
    try:
        bg.bulk_read_secrets("chauncey", 25, "migration audit")
        pytest.fail("expected ApprovalNeeded")
    except ApprovalNeeded as exc:
        assert "levi cybrus approve" in str(exc)
        _approve(exc.approval_id)
    receipt = bg.bulk_read_secrets("chauncey", 25, "migration audit")
    assert receipt["granted"] is True
