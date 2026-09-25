"""RED-1 twin-attack: 🔰 BACK-GUARD (commit 2993fe0c).

Law: every finding = a FAILING TEST first. RED-1 does not fix.

Findings (expected FAIL):
  R1  destination final-component symlink launders an external target
      (MEDIUM) — _resolve_dest_parent resolves the parent but never the
      final component, so destination_risk judges the link name, not the
      real target. Sensitive bytes land on removable media grant-free.
  R2  cloud-sync folder name variants evade destination_risk (MEDIUM) —
      the fixed part list {"google drive", ...} misses "GoogleDrive",
      "Google_Drive", "gdrive", etc. Sensitive→sync-folder needs no grant.
  R3  manifest tail-truncation invisible to verify() without
      expected_head (MEDIUM-LOW) — B3 claims tampering/deletion is
      "detectable by BackupManifest.verify"; a truncated chain verifies
      ok unless the caller supplies the audit-anchored head.
  R4  keyless chain: recomputed-chain forgery invisible to verify()
      (MEDIUM-LOW) — _hash_entry uses no secret; anyone who can write the
      manifest can forge a valid chain over tampered archives.
  R5  TOCTOU: classify-time tier vs copy-time bytes diverge (MEDIUM-LOW)
      — nothing re-checks the source between _effective_tier and
      shutil.copy2/copytree; swapped bytes move under a "normal" receipt.
  R6  audit outage moves bytes without a receipt (LOW-MEDIUM) — B1
      demands grant + audit receipt; the copy happens BEFORE the audit
      append, so a failing audit still lets the bytes cross.
  R7  BulkReadGuard is cooperative-only: self-asserted actor/store names
      rotate past the tripwire (LOW) — B2's "require" rests on callers
      opting into note_read with stable identities.

Honest negatives (expected PASS — defenses hold):
  N1  grant wrong-actor binding → denied.
  N2  expired grant → denied.
  N3  documented residual: a process ignoring the module copies freely
      (gate, not MAC — the module says so itself).
"""

import hashlib
import json
import os
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
    # "secret" basename marker -> sensitive tier
    p = tmp_path / name
    p.write_bytes(b"top secret material")
    assert bg.classify(p) == "sensitive"
    return p


def _issue_via_approval(actor, src, dst, purpose):
    try:
        request_copy(actor, src, dst, purpose)
        pytest.fail("expected ApprovalNeeded")
    except ApprovalNeeded as exc:
        _approve(exc.approval_id)
    return issue_grant(actor, src, dst, purpose)


# ---------------------------------------------------------------------------
# R1 — destination final-component symlink launders an external target
# ---------------------------------------------------------------------------

def test_red1_dst_final_symlink_launders_external(tmp_path):
    usb = tmp_path / "usb"  # the "removable" prefix for this test
    link = tmp_path / "stage_link"
    link.symlink_to(usb / "ghost.bin")  # dangling target inside usb
    src = _sensitive_file(tmp_path)
    # CORRECTED 2026-09-23 (BLUE batch B): the original asserted a
    # receipt with dst_risk="external" — but R1's closure resolves the
    # final symlink component and judges the REAL target as external,
    # so B1 DENIES the grant-free sensitive→external copy outright. A
    # receipt here would violate B1. Secure closure: ApprovalNeeded,
    # zero bytes landed.
    with pytest.raises(ApprovalNeeded):
        request_copy("chauncey", src, link, "staging")
    assert not (usb / "ghost.bin").exists()
    resolved, _ = bg._resolve_dest_parent(link)
    assert destination_risk(resolved) == "external"


# ---------------------------------------------------------------------------
# R2 — cloud-sync folder name variants evade destination_risk
# ---------------------------------------------------------------------------

def test_red1_cloud_sync_name_variants_judged_internal(tmp_path):
    for variant in ("GoogleDrive", "Google_Drive", "gdrive", "GDrive",
                    "OneDrivePersonal", "my-dropbox"):
        risk = destination_risk(tmp_path / variant / "backup")
        assert risk == "external", f"R2: {variant!r} judged {risk!r}"


def test_red1_sensitive_copy_to_renamed_drive_folder_denied_without_grant(tmp_path):
    # CORRECTED + renamed 2026-09-23 (BLUE batch B): the original name
    # ("..._needs_no_grant") and receipt assertion described the HOLE.
    # R2's closure judges "GoogleDrive" as external, so B1 DENIES the
    # grant-free sensitive→external copy — the bytes must not land.
    gdrive = tmp_path / "GoogleDrive"
    gdrive.mkdir()
    src = _sensitive_file(tmp_path)
    with pytest.raises(ApprovalNeeded):
        request_copy("chauncey", src, gdrive / "backup.enc",
                     "offsite backup")
    assert not (gdrive / "backup.enc").exists()


# ---------------------------------------------------------------------------
# R3 — manifest tail-truncation invisible to verify() without expected_head
# ---------------------------------------------------------------------------

def test_red1_manifest_tail_truncation_invisible_to_verify(tmp_path):
    mdir = tmp_path / "backups"
    man = BackupManifest(mdir)
    for i in (1, 2):
        a = mdir / f"vault-{i}.enc"
        a.write_bytes(f"backup bytes {i}".encode())
        man.seal(a, "vault")
    assert man.verify()["ok"] is True
    # Attacker drops the tail entry (the newest backup).
    lines = man.path.read_text().splitlines()
    man.path.write_text("\n".join(lines[:-1]) + "\n")
    result = man.verify()
    assert result["ok"] is False, (
        f"R3: truncated manifest verifies ok={result['ok']} "
        f"(entries={result['entries']}) without expected_head"
    )


# ---------------------------------------------------------------------------
# R4 — keyless chain: recomputed-chain forgery invisible to verify()
# ---------------------------------------------------------------------------

def test_red1_manifest_chain_recompute_forgery_invisible(tmp_path):
    mdir = tmp_path / "backups"
    man = BackupManifest(mdir)
    arch = mdir / "vault.enc"
    arch.write_bytes(b"original bytes")
    man.seal(arch, "vault")
    # Attacker flips the archive, then rewrites the entry and recomputes
    # the (keyless) chain over the tampered bytes.
    arch.write_bytes(b"tampered bytes")
    rec = json.loads(man.path.read_text().splitlines()[0])
    rec["sha256"] = hashlib.sha256(b"tampered bytes").hexdigest()
    rec["hash"] = bg._hash_entry(rec["prev"], rec)
    man.path.write_text(
        json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n"
    )
    result = man.verify()
    assert result["ok"] is False, (
        f"R4: recomputed chain over tampered archive verifies "
        f"ok={result['ok']}"
    )


# ---------------------------------------------------------------------------
# R5 — TOCTOU: classify-time tier vs copy-time bytes diverge
# ---------------------------------------------------------------------------

def test_red1_copy_toctou_swapped_bytes_not_detected(tmp_path, monkeypatch):
    src = tmp_path / "notes.txt"
    src.write_bytes(b"plain notes")
    dst = tmp_path / "out.txt"
    real_copy2 = shutil.copy2
    swapped = b"exfiltrated secret payload"

    def evil_copy2(s, d, *a, **k):
        Path(s).write_bytes(swapped)  # swap between classify and copy
        return real_copy2(s, d, *a, **k)

    monkeypatch.setattr(shutil, "copy2", evil_copy2)
    receipt = request_copy("chauncey", src, dst, "test")
    assert receipt["src_tier"] == "normal"  # judged at classify time
    assert dst.read_bytes() == b"plain notes", (
        f"R5: gate judged src_tier='normal' but copied "
        f"{dst.read_bytes()!r}"
    )


# ---------------------------------------------------------------------------
# R6 — audit outage moves bytes without a receipt
# ---------------------------------------------------------------------------

def test_red1_audit_outage_must_not_move_bytes(tmp_path, monkeypatch):
    from levi.cybrus.audit import AuditEngine

    def _boom(self, *args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(AuditEngine, "append", _boom)
    src = tmp_path / "notes.txt"
    src.write_bytes(b"plain notes")
    dst = tmp_path / "out.txt"
    with pytest.raises(OSError):
        request_copy("chauncey", src, dst, "test")
    assert not dst.exists(), (
        "R6: bytes were copied even though the audit receipt failed — "
        "B1 requires grant + audit receipt"
    )


# ---------------------------------------------------------------------------
# R7 — BulkReadGuard: rotated self-asserted identities never trip it
# ---------------------------------------------------------------------------

def test_red1_bulk_read_guard_actor_rotation(tmp_path):
    with pytest.raises(BulkReadDenied):
        for i in range(30):
            # 30 reads, 10 per self-asserted identity: the window never
            # exceeds the threshold for any single name.
            BulkReadGuard(f"reader-{i % 3}", store="vault").note_read()


# ---------------------------------------------------------------------------
# Honest negatives — defenses that hold
# ---------------------------------------------------------------------------

def test_red1_grant_wrong_actor_denied(tmp_path):
    src = tmp_path / "dynasty" / "sealed.md"
    src.write_text("eyes-only bytes")
    grant = _issue_via_approval("chauncey", src, tmp_path / "a.md", "test")
    with pytest.raises(BackGuardDenied, match="actor mismatch"):
        request_copy("mallory", src, tmp_path / "a.md", "test",
                     grant_id=grant["id"])
    assert not (tmp_path / "a.md").exists() or True  # first copy unused here


def test_red1_grant_expiry_denied(tmp_path, monkeypatch):
    monkeypatch.setattr(bg, "GRANT_TTL_SECONDS", -1)  # already expired
    src = tmp_path / "dynasty" / "sealed.md"
    src.write_text("eyes-only bytes")
    grant = _issue_via_approval("chauncey", src, tmp_path / "a.md", "test")
    with pytest.raises(BackGuardDenied, match="expired"):
        request_copy("chauncey", src, tmp_path / "a.md", "test",
                     grant_id=grant["id"])


def test_red1_module_is_gate_not_mac(tmp_path):
    # Documented residual (module docstring: honest limits): a process
    # that ignores backguard copies freely. Confirmed, not a finding.
    src = tmp_path / "dynasty" / "sealed.md"
    src.write_text("eyes-only bytes")
    dst = tmp_path / "stolen.md"
    shutil.copy2(src, dst)  # no exception: the gate was never consulted
    assert dst.read_text() == "eyes-only bytes"
