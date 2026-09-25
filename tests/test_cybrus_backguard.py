"""Tests for levi.cybrus.backguard — the BACK-guard (🔰).

Hermetic: LEVI_HOME is monkeypatched to a tmp dir — no real HOME writes,
no network. Fixtures stand in for Chauncey's real eyes-only material
(the real Google_Passwords.csv is NEVER touched: tests use same-named
fixtures in tmp dirs only).

Law→guard→prove: these invariant tests are the machine-checkable proof
gate for BACK laws B1–B6. Nothing here is called "formally proven".
"""

import json
import os

import pytest

from levi.cybrus.approval import ApprovalEngine
from levi.cybrus.backguard import (
    BACK_LAWS,
    ApprovalNeeded,
    BackGuardDenied,
    BackupManifest,
    BulkReadDenied,
    BulkReadGuard,
    bulk_read_secrets,
    classify,
    describe_posture,
    destination_risk,
    issue_grant,
    request_archive,
    request_copy,
)
from levi.cybrus.policy import PolicyEngine
from levi.cybrus.vault import CredentialVault


@pytest.fixture(autouse=True)
def _hermetic(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CYBRUS_EYES_ONLY_ROOTS", str(tmp_path / "dynasty"))
    monkeypatch.setenv("CYBRUS_REMOVABLE_PREFIXES", str(tmp_path / "usb"))
    (tmp_path / "dynasty").mkdir()
    (tmp_path / "usb").mkdir()
    return tmp_path


def _audit_events(tmp_path):
    p = tmp_path / "home" / ".levi" / "cybrus" / "audit.jsonl"
    if not p.exists():
        return []
    return [
        json.loads(line)
        for line in p.read_text().splitlines()
        if line.strip()
    ]


def _approve(approval_id):
    return ApprovalEngine().approve(approval_id, by="owner")


# ---------------------------------------------------------------------------
# Laws declared (B6: law→guard→prove)
# ---------------------------------------------------------------------------


def test_laws_declared():
    ids = [lid for lid, _ in BACK_LAWS]
    assert ids == ["B1", "B2", "B3", "B4", "B5", "B6"]
    for lid, text in BACK_LAWS:
        assert isinstance(text, str) and len(text) > 20


def test_posture_is_honest():
    posture = describe_posture()
    assert posture["default_allow"] is False
    assert posture["deny_wins"] is True
    assert posture["cannot_stop"], "residual risks must be named, not hidden"
    assert posture["laws"] == ["B1", "B2", "B3", "B4", "B5", "B6"]


# ---------------------------------------------------------------------------
# Classification (B4)
# ---------------------------------------------------------------------------


def test_classify_eyes_only_by_root(tmp_path):
    secret = tmp_path / "dynasty" / "canon" / "playbook.md"
    secret.parent.mkdir(parents=True)
    secret.write_text("dynasty material")
    assert classify(secret) == "eyes-only"


def test_classify_eyes_only_by_passwords_csv_name(tmp_path):
    # Fixture only — the real Google_Passwords.csv is never touched.
    fake = tmp_path / "somewhere" / "Google_Passwords.csv"
    fake.parent.mkdir(parents=True)
    fake.write_text("name,url,username,password\n")
    assert classify(fake) == "eyes-only"


def test_classify_eyes_only_by_marker(tmp_path):
    doc = tmp_path / "IP_PROTECTION.md"
    doc.write_text("ip material")
    assert classify(doc) == "eyes-only"


def test_classify_sensitive(tmp_path):
    blob = tmp_path / "entries.enc"
    blob.write_bytes(b"\x00" * 32)
    assert classify(blob) == "sensitive"


def test_classify_normal(tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("grocery list")
    assert classify(f) == "normal"


def test_classify_symlink_cannot_launder_eyes_only(tmp_path):
    target = tmp_path / "dynasty" / "sealed.md"
    target.write_text("eyes-only")
    link = tmp_path / "innocent.txt"
    link.symlink_to(target)
    assert classify(link) == "eyes-only"


def test_destination_risk(tmp_path):
    assert destination_risk(tmp_path / "usb" / "stick" / "x") == "external"
    assert destination_risk(tmp_path / "home" / "Google Drive" / "x") == "external"
    assert destination_risk("user@host:/srv/x") == "external"
    assert destination_risk("https://example.com/x") == "external"
    assert destination_risk(tmp_path / "home" / "docs" / "x") == "internal"


# ---------------------------------------------------------------------------
# The copy gate (B1, B5)
# ---------------------------------------------------------------------------


def test_eyes_only_copy_denied_without_grant(tmp_path):
    src = tmp_path / "dynasty" / "sealed.md"
    src.write_text("eyes-only bytes")
    with pytest.raises(ApprovalNeeded) as exc_info:
        request_copy("chauncey", src, tmp_path / "out.md", "test")
    assert exc_info.value.approval_id
    assert "levi cybrus approve" in str(exc_info.value)
    assert not (tmp_path / "out.md").exists()
    events = [e["event"] for e in _audit_events(tmp_path)]
    assert "back.copy.approval_required" in events


def test_eyes_only_copy_allowed_after_approval(tmp_path):
    src = tmp_path / "dynasty" / "sealed.md"
    src.write_text("eyes-only bytes")
    dst = tmp_path / "out.md"
    try:
        request_copy("chauncey", src, dst, "test")
        pytest.fail("should have needed approval")
    except ApprovalNeeded as exc:
        _approve(exc.approval_id)
    receipt = request_copy("chauncey", src, dst, "test")
    assert receipt["copied"] is True
    assert receipt["src_tier"] == "eyes-only"
    assert receipt["grant_id"] is not None
    assert dst.read_text() == "eyes-only bytes"
    events = _audit_events(tmp_path)
    by_event = {e["event"] for e in events}
    assert "back.grant.issued" in by_event
    assert "back.copy.completed" in by_event


def test_explicit_grant_path_single_use(tmp_path):
    src = tmp_path / "dynasty" / "sealed.md"
    src.write_text("eyes-only bytes")
    # First request_copy raises ApprovalNeeded; approve; issue explicit grant.
    try:
        request_copy("chauncey", src, tmp_path / "a.md", "test")
        pytest.fail("expected ApprovalNeeded")
    except ApprovalNeeded as exc:
        _approve(exc.approval_id)
    grant = issue_grant("chauncey", src, tmp_path / "a.md", "test")
    assert grant["id"].startswith("bg-")
    r1 = request_copy("chauncey", src, tmp_path / "a.md", "test",
                      grant_id=grant["id"])
    assert r1["copied"] is True
    # Second use of the same grant: denied (single-use).
    with pytest.raises(BackGuardDenied, match="already used"):
        request_copy("chauncey", src, tmp_path / "b.md", "test",
                     grant_id=grant["id"])
    assert not (tmp_path / "b.md").exists()


def test_grant_forgery_denied(tmp_path):
    src = tmp_path / "dynasty" / "sealed.md"
    src.write_text("eyes-only bytes")
    with pytest.raises(BackGuardDenied):
        request_copy("chauncey", src, tmp_path / "x.md", "test",
                     grant_id="bg-" + "0" * 32)


def test_grant_binding_mismatch_denied(tmp_path):
    src = tmp_path / "dynasty" / "sealed.md"
    src.write_text("eyes-only bytes")
    try:
        request_copy("chauncey", src, tmp_path / "a.md", "real purpose")
        pytest.fail("expected ApprovalNeeded")
    except ApprovalNeeded as exc:
        _approve(exc.approval_id)
    grant = issue_grant("chauncey", src, tmp_path / "a.md", "real purpose")
    # Same grant, different purpose: binding mismatch → denied.
    with pytest.raises(BackGuardDenied, match="purpose mismatch"):
        request_copy("chauncey", src, tmp_path / "a.md", "other purpose",
                     grant_id=grant["id"])


def test_sensitive_to_external_denied_by_default(tmp_path):
    src = tmp_path / "entries.enc"
    src.write_bytes(b"\x00" * 64)
    with pytest.raises(ApprovalNeeded):
        request_copy("chauncey", src, tmp_path / "usb" / "stick" / "x.enc",
                     "offsite backup")
    assert not (tmp_path / "usb" / "stick" / "x.enc").exists()


def test_bulk_sensitive_dir_copy_needs_grant(tmp_path):
    srcdir = tmp_path / "vault-bulk"
    srcdir.mkdir()
    for i in range(30):
        (srcdir / f"secret-{i}.enc").write_bytes(b"\x00" * 16)
    with pytest.raises(ApprovalNeeded):
        request_copy("chauncey", srcdir, tmp_path / "bulk-out", "test")


def test_normal_copy_audited_without_grant(tmp_path):
    src = tmp_path / "notes.txt"
    src.write_text("grocery list")
    receipt = request_copy("chauncey", src, tmp_path / "notes-copy.txt",
                           "test copy")
    assert receipt["copied"] is True
    assert receipt["grant_id"] is None
    assert receipt["src_tier"] == "normal"
    events = _audit_events(tmp_path)
    completed = [e for e in events if e["event"] == "back.copy.completed"]
    assert len(completed) == 1
    assert "grocery list" not in json.dumps(completed[0])


def test_copy_never_overwrites(tmp_path):
    src = tmp_path / "a.txt"
    src.write_text("a")
    dst = tmp_path / "b.txt"
    dst.write_text("b")
    with pytest.raises(BackGuardDenied, match="already exists"):
        request_copy("chauncey", src, dst, "test")
    assert dst.read_text() == "b"


def test_policy_deny_wins_over_grant(tmp_path):
    PolicyEngine().add_rule("chauncey", "back.copy", "export", "deny",
                            "critical")
    src = tmp_path / "dynasty" / "sealed.md"
    src.write_text("eyes-only bytes")
    # A pre-approved approval is already waiting — the explicit policy
    # deny still wins (B6/L3: no grant can override a deny).
    entry = ApprovalEngine().request_approval(
        "back.copy",
        "chauncey",
        "back.copy:eyes-only",
        "critical",
        details={
            "actor": "chauncey",
            "src": str(src),
            "dst": str(tmp_path / "out.md"),
            "purpose": "test",
        },
    )
    ApprovalEngine().approve(entry["id"], by="owner")
    with pytest.raises(BackGuardDenied, match="policy denied"):
        request_copy("chauncey", src, tmp_path / "out.md", "test")
    assert not (tmp_path / "out.md").exists()
    events = [e["event"] for e in _audit_events(tmp_path)]
    assert "back.copy.denied" in events


def test_archive_goes_through_the_same_gate(tmp_path):
    src = tmp_path / "dynasty" / "sealed.md"
    src.write_text("eyes-only bytes")
    with pytest.raises(ApprovalNeeded):
        request_archive("chauncey", src, tmp_path / "backup.tar.gz", "test")
    assert not (tmp_path / "backup.tar.gz").exists()


def test_audit_records_carry_no_content(tmp_path):
    secret_value = "s3cr3t-p@ssw0rd-value-zzz-12345"
    src = tmp_path / "notes.txt"
    src.write_text(secret_value)
    request_copy("chauncey", src, tmp_path / "copy.txt", "test")
    blob = (tmp_path / "home" / ".levi" / "cybrus" / "audit.jsonl").read_text()
    assert secret_value not in blob


# ---------------------------------------------------------------------------
# The bulk-read gate (B2)
# ---------------------------------------------------------------------------


def test_bulk_read_guard_denies_past_threshold(tmp_path):
    guard = BulkReadGuard("chauncey", store="vault", threshold=10,
                         window_seconds=300)
    for _ in range(10):
        assert guard.note_read() <= 10
    with pytest.raises(BulkReadDenied, match="back.bulk_read"):
        guard.note_read()
    events = [e["event"] for e in _audit_events(tmp_path)]
    assert "back.read.bulk_denied" in events


def test_bulk_read_granted_with_approval(tmp_path):
    try:
        bulk_read_secrets("chauncey", 25, "migration audit")
        pytest.fail("expected ApprovalNeeded")
    except ApprovalNeeded as exc:
        assert "levi cybrus approve" in str(exc)
        _approve(exc.approval_id)
    receipt = bulk_read_secrets("chauncey", 25, "migration audit")
    assert receipt["granted"] is True
    assert receipt["approval_id"]
    events = [e["event"] for e in _audit_events(tmp_path)]
    assert "back.read.bulk_granted" in events
    # The gate is authorization + audit, not a data pipe: the receipt
    # carries metadata only (actor, store, count, purpose, approval id).
    assert set(receipt) <= {
        "granted", "actor", "store", "count", "purpose",
        "approval_id", "ts",
    }


def test_vault_exposes_no_ungated_bulk_export():
    for name in ("get_all", "export_all", "dump", "export"):
        assert not hasattr(CredentialVault, name), (
            f"CredentialVault.{name} would be an ungated bulk path (B2)"
        )


# ---------------------------------------------------------------------------
# Backup manifests (B3)
# ---------------------------------------------------------------------------


def _make_archives(tmp_path, n=3):
    srcdir = tmp_path / "archives"
    srcdir.mkdir(exist_ok=True)
    paths = []
    for i in range(n):
        p = srcdir / f"backup-{i}.enc"
        p.write_bytes(bytes([i]) * 64)
        paths.append(p)
    return paths


def test_manifest_roundtrip(tmp_path):
    man = BackupManifest(tmp_path / "archives")
    paths = _make_archives(tmp_path)
    for p in paths:
        man.seal(p, "vault-nightly")
    result = man.verify()
    assert result["ok"] is True
    assert result["first_bad"] is None
    assert result["entries"] == 3
    assert result["head"]
    events = [e["event"] for e in _audit_events(tmp_path)]
    assert events.count("back.manifest.sealed") == 3


def test_manifest_detects_archive_tamper(tmp_path):
    man = BackupManifest(tmp_path / "archives")
    paths = _make_archives(tmp_path)
    for p in paths:
        man.seal(p, "vault-nightly")
    raw = bytearray(paths[1].read_bytes())
    raw[10] ^= 0xFF
    paths[1].write_bytes(bytes(raw))
    result = man.verify()
    assert result["ok"] is False
    assert result["first_bad"] == 1
    assert "altered" in result["reason"]


def test_manifest_detects_archive_deletion(tmp_path):
    man = BackupManifest(tmp_path / "archives")
    paths = _make_archives(tmp_path)
    for p in paths:
        man.seal(p, "vault-nightly")
    paths[2].unlink()
    result = man.verify()
    assert result["ok"] is False
    assert result["first_bad"] == 2
    assert "missing" in result["reason"]


def test_manifest_detects_chain_tamper(tmp_path):
    man = BackupManifest(tmp_path / "archives")
    for p in _make_archives(tmp_path):
        man.seal(p, "vault-nightly")
    lines = (man.path).read_text().splitlines()
    rec = json.loads(lines[1])
    rec["sha256"] = "0" * 64  # attacker rewrites a hash, keeps the file
    lines[1] = json.dumps(rec, sort_keys=True, separators=(",", ":"))
    man.path.write_text("\n".join(lines) + "\n")
    result = man.verify()
    assert result["ok"] is False
    assert result["first_bad"] == 1


def test_manifest_head_attestation_catches_truncation(tmp_path):
    man = BackupManifest(tmp_path / "archives")
    for p in _make_archives(tmp_path):
        man.seal(p, "vault-nightly")
    head = man.head()
    assert man.verify(expected_head=head)["ok"] is True
    # Attacker truncates the manifest to the first entry.
    lines = man.path.read_text().splitlines()
    man.path.write_text(lines[0] + "\n")
    # RED-1 R3/R4: the truncation anchor catches this WITHOUT needing
    # the externally supplied head — it fires before the head check.
    result = man.verify()
    assert result["ok"] is False
    assert "anchor" in result["reason"]
    result = man.verify(expected_head=head)
    assert result["ok"] is False
    assert "anchor" in result["reason"] or "head mismatch" in result["reason"]


def test_attest_current_detects_rollback(tmp_path):
    man = BackupManifest(tmp_path / "archives")
    paths = _make_archives(tmp_path, n=1)
    man.seal(paths[0], "vault-nightly")
    assert man.attest_current("vault-nightly", paths[0])["matches"] is True
    # An older blob is swapped in (same name, valid ciphertext, old data).
    paths[0].write_bytes(b"\x99" * 64)
    result = man.attest_current("vault-nightly", paths[0])
    assert result["matches"] is False
    events = [e["event"] for e in _audit_events(tmp_path)]
    assert "back.manifest.rollback_suspect" in events


def test_seal_rejects_nonfile(tmp_path):
    man = BackupManifest(tmp_path / "archives")
    with pytest.raises(Exception):
        man.seal(tmp_path / "nope.enc", "vault-nightly")


# ---------------------------------------------------------------------------
# RED-team: grants-store tampering (B1)
# ---------------------------------------------------------------------------


def test_grants_store_chained_on_save(tmp_path):
    from levi.cybrus import backguard as bg

    src = tmp_path / "dynasty" / "sealed.md"
    src.write_text("eyes-only bytes")
    try:
        request_copy("chauncey", src, tmp_path / "a.md", "test")
        pytest.fail("expected ApprovalNeeded")
    except ApprovalNeeded as exc:
        _approve(exc.approval_id)
    grant = issue_grant("chauncey", src, tmp_path / "a.md", "test")
    store = tmp_path / "home" / ".levi" / "cybrus" / "back_grants.json"
    records = json.loads(store.read_text())
    assert len(records) == 1
    assert records[0]["id"] == grant["id"]
    assert bg._verify_grants(records) is True


def test_grants_store_tamper_fails_closed(tmp_path):
    from levi.cybrus.backguard import BackGuardError

    src = tmp_path / "dynasty" / "sealed.md"
    src.write_text("eyes-only bytes")
    try:
        request_copy("chauncey", src, tmp_path / "a.md", "test")
        pytest.fail("expected ApprovalNeeded")
    except ApprovalNeeded as exc:
        _approve(exc.approval_id)
    grant = issue_grant("chauncey", src, tmp_path / "a.md", "test")
    request_copy("chauncey", src, tmp_path / "a.md", "test",
                 grant_id=grant["id"])
    # RED: attacker flips "used" back to false directly in the store.
    store = tmp_path / "home" / ".levi" / "cybrus" / "back_grants.json"
    records = json.loads(store.read_text())
    records[0]["used"] = False
    records[0]["used_at"] = None
    store.write_text(json.dumps(records, indent=2, sort_keys=True))
    # The chain no longer verifies: fail closed, no copy, audit flag.
    with pytest.raises(BackGuardError, match="integrity check"):
        request_copy("chauncey", src, tmp_path / "b.md", "test",
                     grant_id=grant["id"])
    assert not (tmp_path / "b.md").exists()
    events = [e["event"] for e in _audit_events(tmp_path)]
    assert "back.grants.tamper_suspect" in events


def test_expired_grant_refused(tmp_path):
    from datetime import datetime, timedelta, timezone

    from levi.cybrus import backguard as bg

    src = tmp_path / "dynasty" / "sealed.md"
    src.write_text("eyes-only bytes")
    try:
        request_copy("chauncey", src, tmp_path / "a.md", "test")
        pytest.fail("expected ApprovalNeeded")
    except ApprovalNeeded as exc:
        _approve(exc.approval_id)
    grant = issue_grant("chauncey", src, tmp_path / "a.md", "test")
    # RED: backdate the grant's expiry, re-chaining so the store verifies.
    store = tmp_path / "home" / ".levi" / "cybrus" / "back_grants.json"
    records = json.loads(store.read_text())
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    records[0]["expires_at"] = past
    bg._save_grants(records)  # re-chains under the module's own rules
    with pytest.raises(BackGuardDenied, match="expired"):
        request_copy("chauncey", src, tmp_path / "a.md", "test",
                     grant_id=grant["id"])
    assert not (tmp_path / "a.md").exists()


def test_grant_bound_to_actor(tmp_path):
    src = tmp_path / "dynasty" / "sealed.md"
    src.write_text("eyes-only bytes")
    try:
        request_copy("chauncey", src, tmp_path / "a.md", "test")
        pytest.fail("expected ApprovalNeeded")
    except ApprovalNeeded as exc:
        _approve(exc.approval_id)
    grant = issue_grant("chauncey", src, tmp_path / "a.md", "test")
    # RED: a different actor presents chauncey's grant.
    with pytest.raises(BackGuardDenied, match="actor mismatch"):
        request_copy("mallory", src, tmp_path / "a.md", "test",
                     grant_id=grant["id"])
    assert not (tmp_path / "a.md").exists()
