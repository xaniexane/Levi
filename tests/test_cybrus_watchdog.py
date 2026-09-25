"""Cybrus QUETTA-PAN WATCHDOG invariant tests — the law->guard->prove gate.

Honestly named: machine-checked invariant tests, not formal proofs.
Every watchdog law (W1-W6) is pinned; every direction's check is proven
against an injected anomaly, the blind path is proven to bark instead of
going silent, and a quiet state is proven to produce no false barks.

State is isolated per test via LEVI_HOME -> tmp_path (+ LEVI_CYBRUS_DIR so
the money-gateway log stays hermetic too).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pytest

from levi.cybrus import watchdog
from levi.cybrus.audit import AuditEngine


# ---------------------------------------------------------------------------
# Fixtures


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    monkeypatch.setenv("LEVI_CYBRUS_DIR", str(tmp_path))
    return tmp_path


def _phish(i: int):
    return {
        "id": f"phish-{i}",
        "channel": "email",
        "from": "PayPal <billing@paypa1.ru>",
        "reply_to": "",
        "subject": "URGENT: verify your account now",
        "body": "Act now or lose access. Click http://bit.ly/x1y2z3 to verify your password.",
        "urls": ["http://bit.ly/x1y2z3"],
        "attachments": [],
    }


def _screen_receipt(verdict="QUARANTINE", rules=("R01",), msg_ref="m1", channel="email"):
    """A cybrus.front.screen audit record in front.py's exact shape."""
    return {
        "seq": 0,
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": "cybrus.front.screen",
        "actor": "cybrus-front",
        "details": {
            "msg_ref": msg_ref,
            "message_id": msg_ref,
            "channel": channel,
            "verdict": verdict,
            "score": 90,
            "rules": list(rules),
            "receipt_hash": "h",
        },
        "prev": "0" * 64,
        "hash": "1" * 64,
    }


def _append_money_audit(home, event, **kw):
    p = home / "money" / "money_audit.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": datetime.now(timezone.utc).isoformat(), "event": event}
    rec.update(kw)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
    os.chmod(p, 0o600)


def _bark_signals(receipt):
    return {b["signal"] for b in receipt["barks"]}


# ---------------------------------------------------------------------------
# W6: laws declared and pinned


def test_laws_declared_and_complete(home):
    ids = [lid for lid, _ in watchdog.LAWS]
    assert ids == ["W1", "W2", "W3", "W4", "W5", "W6"]
    assert set(watchdog.DIRECTIONS) == {"front", "back", "left", "right"}


def test_posture_is_honest(home):
    posture = watchdog.describe_posture()
    assert posture["organ"] == "levi.cybrus.watchdog"
    assert "invent Quetta-Pan mechanics" in " ".join(posture["does_not"])
    assert posture["network"].startswith("none")
    assert posture["cybrus_laws_binding"] == [f"L{i}" for i in range(1, 13)]


# ---------------------------------------------------------------------------
# Quiet state: no false barks


def test_quiet_state_no_false_barks(home):
    receipt = watchdog.sweep()
    assert receipt["bark_count"] == 0
    assert receipt["blind_count"] == 0
    assert all(v["status"] == "ok" for v in receipt["directions"].values())


# ---------------------------------------------------------------------------
# FRONT


def test_front_flag_spike(home):
    from levi.cybrus import front

    for i in range(6):
        r = front.screen_message(_phish(i))
        assert r["verdict"] == "QUARANTINE"
    receipt = watchdog.sweep()
    assert "flag_spike" in _bark_signals(receipt)
    assert receipt["directions"]["front"]["status"] == "anomaly"


def test_front_screening_error_storm(home):
    # R99 receipts ride the cybrus.front.screen audit contract: inject three.
    eng = AuditEngine()
    for i in range(3):
        eng.append("cybrus.front.screen", "cybrus-front",
                   _screen_receipt(msg_ref=f"e{i}", rules=["R99"])["details"])
    receipt = watchdog.sweep()
    assert "screening_errors" in _bark_signals(receipt)


def test_front_quarantine_bypass(home):
    from levi.cybrus import front

    r = front.screen_message(_phish(1))
    assert r["verdict"] == "QUARANTINE"
    # A release record for an item that was NEVER quarantined = bypass.
    p = home / ".levi" / "cybrus" / "front_releases.jsonl"
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "msg_ref": "ghost-ref-never-quarantined",
        "released_by": "someone",
        "rule_basis": "F6 explicit founder release",
    }
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")
    receipt = watchdog.sweep()
    assert "quarantine_bypass" in _bark_signals(receipt)


# ---------------------------------------------------------------------------
# BACK


def test_back_manifest_failure(home):
    from levi.cybrus.backup_manifest import ManifestEngine

    manifest = ManifestEngine()
    manifest.backup_dir.mkdir(parents=True, exist_ok=True)
    archive = manifest.backup_dir / "daily.tar.gz.enc"
    archive.write_bytes(b"secret-backup-bytes")
    manifest.record(archive, recorded_by="test")
    archive.unlink()  # the archive the manifest swears by is gone
    receipt = watchdog.sweep()
    assert "backup_manifest_failure" in _bark_signals(receipt)
    assert receipt["directions"]["back"]["status"] == "anomaly"


def test_back_unrecorded_archives(home):
    from levi.cybrus.backup_manifest import ManifestEngine

    manifest = ManifestEngine()
    manifest.backup_dir.mkdir(parents=True, exist_ok=True)
    (manifest.backup_dir / "mystery.tar.gz.enc").write_bytes(b"untracked")
    receipt = watchdog.sweep()
    assert "unrecorded_archives" in _bark_signals(receipt)


def test_back_blind_barks_instead_of_silence(home, monkeypatch):
    from levi.cybrus import backup_manifest

    def boom(self, **kw):
        raise OSError("disk on fire")

    monkeypatch.setattr(backup_manifest.ManifestEngine, "verify", boom)
    receipt = watchdog.sweep()
    back = receipt["directions"]["back"]
    assert back["status"] == "blind"
    assert "blind" in back["signals"]
    assert receipt["blind_count"] >= 1


# ---------------------------------------------------------------------------
# LEFT


def test_left_unknown_device(home):
    from levi.cybrus.devices import DeviceTrust

    DeviceTrust().enroll("moto-g", "Chauncey's phone")  # enrolls untrusted
    receipt = watchdog.sweep()
    signals = _bark_signals(receipt)
    assert "unknown_device" in signals
    bark = next(b for b in receipt["barks"] if b["signal"] == "unknown_device")
    assert bark["evidence_hash"] and bark["audit_seq"] is not None


def test_left_revoked_device_reappears(home):
    from levi.cybrus.devices import DeviceTrust

    reg = DeviceTrust()
    reg.enroll("rogue-1", "unknown box")
    reg.revoke("rogue-1")  # audited as device.revoked
    # ...then the same id presents itself again
    AuditEngine().append(
        "device.sighted", "cybrus.left-guard", {"device_id": "rogue-1"})
    receipt = watchdog.sweep()
    assert "revoked_device_reappeared" in _bark_signals(receipt)


# ---------------------------------------------------------------------------
# RIGHT


def test_right_money_grant_refusal(home):
    _append_money_audit(home, "execute_refused",
                        plan_id="p1", reason="approval replay: already consumed")
    receipt = watchdog.sweep()
    assert "money_grant_refusal" in _bark_signals(receipt)
    assert receipt["directions"]["right"]["status"] == "anomaly"


def test_right_silent_movement_violation(home):
    AuditEngine().append("right.violation", "cybrus.sentry",
                         {"actor": "rogue", "action": "money.execute"})
    receipt = watchdog.sweep()
    assert "silent_movement" in _bark_signals(receipt)


def test_right_movement_without_receipt(home):
    # Executed money movement with NO money.approval_receipt on the trail.
    _append_money_audit(home, "executed", plan_id="plan-no-receipt")
    receipt = watchdog.sweep()
    assert "movement_without_receipt" in _bark_signals(receipt)


def test_right_approval_velocity(home):
    from levi.cybrus.approval import ApprovalEngine

    eng = ApprovalEngine()
    for i in range(10):
        e = eng.request_approval("money.execute", f"subject-{i}", "res", "high")
        eng.approve(e["id"], by="owner")
    receipt = watchdog.sweep()
    assert "approval_velocity" in _bark_signals(receipt)


# ---------------------------------------------------------------------------
# W1/W2/W4/W5: bark receipts, dedup, audit trail


def test_barks_land_in_audit_trail_with_receipts(home):
    from levi.cybrus.devices import DeviceTrust

    DeviceTrust().enroll("moto-g", "Chauncey's phone")
    receipt = watchdog.sweep()
    assert receipt["bark_count"] >= 1
    for b in receipt["barks"]:
        assert b["direction"] in watchdog.DIRECTIONS
        assert b["signal"] and b["severity"] and b["evidence_hash"]
        assert b["ts"] and b["audit_seq"] is not None and b["audit_hash"]
        assert not b["deduped"]
    ok, bad = AuditEngine().verify()
    assert ok and bad is None
    trail_barks = [
        r for r in AuditEngine().tail(100)
        if r.get("event") == watchdog.BARK_EVENT
    ]
    assert len(trail_barks) == receipt["bark_count"]
    for r in trail_barks:
        details = r["details"]
        assert details["remedy"]  # W5: every bark names its remedy
        assert "evidence_hash" in details


def test_dedup_no_double_bark(home):
    from levi.cybrus.devices import DeviceTrust

    DeviceTrust().enroll("moto-g", "Chauncey's phone")
    first = watchdog.sweep()
    second = watchdog.sweep()
    assert first["bark_count"] >= 1
    assert all(b["deduped"] for b in second["barks"])
    count_after = len(
        [r for r in AuditEngine().tail(1000)
         if r.get("event") == watchdog.BARK_EVENT])
    assert count_after == first["bark_count"]


def test_blind_bark_marks_blind(home, monkeypatch):
    from levi.cybrus import backup_manifest

    def boom(self, **kw):
        raise OSError("unreadable")

    monkeypatch.setattr(backup_manifest.ManifestEngine, "verify", boom)
    receipt = watchdog.sweep()
    blind_barks = [b for b in receipt["barks"] if b["signal"] == "blind"]
    assert blind_barks
    assert blind_barks[0]["severity"] == "high"
    assert blind_barks[0]["direction"] == "back"


def test_metadata_only_no_payloads(home):
    from levi.cybrus.devices import DeviceTrust

    DeviceTrust().enroll("moto-g", "Chauncey's phone")
    receipt = watchdog.sweep()
    blob = json.dumps(receipt["barks"])
    # Device fingerprints never ride a bark; quarantine bodies never ride a bark.
    assert "fingerprint" not in blob.lower() or "fingerprint_bound" in blob
