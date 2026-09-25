"""Flagship acceptance: scan-mind + blackboard + rule-reflex (+ dictionary)
running one task, end to end.

Hermetic: LEVI_GTPM_DIR is pointed at tmp_path; the demo makes no network
calls (a socket-blocking guard proves it).
"""

import json
import socket

import pytest

from levi.gtpm import flagship
from levi.gtpm.adapters import gtpm_dir


@pytest.fixture(autouse=True)
def _hermetic(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_GTPM_DIR", str(tmp_path / "gtpm"))


def _block_network():
    real = socket.socket

    def _raise(*a, **k):
        raise AssertionError("network access attempted during flagship demo")

    socket.socket = _raise  # type: ignore[assignment]
    return real


def test_demo_runs_offline_and_receipts():
    real = _block_network()
    try:
        summary = flagship.run_demo()
    finally:
        socket.socket = real  # type: ignore[assignment]
    assert summary["task"].startswith("house-watch")
    assert summary["dictionary_computed"] == [42]
    assert summary["board_winner"]["content"]["action"] == "recheck"
    assert summary["watchdog_ok"] is True
    assert summary["scan_faults"] == []
    log = gtpm_dir() / "receipts.jsonl"
    lines = log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == summary["receipts_written"]
    kinds = {json.loads(line)["kind"] for line in lines}
    assert {"board", "arbitration", "firing", "scan", "demo"} <= kinds


def test_demo_determinism_across_runs(tmp_path):
    """Same task twice → same decisions (timestamps may differ, logic may not)."""
    import runpy  # noqa: F401  (kept out; decisions compared directly)

    first = flagship.run_demo()
    second = flagship.run_demo()
    for key in (
        "dictionary_computed",
        "staged_acts",
        "proposals",
        "scan_commits",
        "board_winner",
    ):
        assert first[key] == second[key], key
    # Latch holds in cycle 2, one-shot fires exactly once across both cycles.
    assert first["scan_commits"].count("drift_latched") == 2
    assert first["scan_commits"].count("announce_drift") == 1
    assert first["scan_commits"].count("plan_response") == 1
    # The interlock never fired (offline stayed enforced); gate approved low risk.
    assert "halt_all" not in first["scan_commits"]


def test_demo_honesty_low_confidence_only_proposes():
    summary = flagship.run_demo()
    assert "recheck" in summary["staged_acts"]
    assert "tune" in summary["proposals"]
    assert "tune" not in summary["staged_acts"]


def test_tick_as_scan_reference():
    receipt = flagship.tick_as_scan(
        ["nightly-backup", "health-check"],
        flagship.build_program(),
        {"offline_enforced": True, "drift": False, "health_ok": True},
    )
    assert receipt["kind"] == "scan"
    assert receipt["due_entries"] == ["nightly-backup", "health-check"]
    assert receipt["watchdog_ok"] is True


def test_cli_entrypoint(capsys):
    from levi.gtpm.__main__ import main

    assert main(["demo"]) == 0
    out = capsys.readouterr().out
    assert "house-watch" in out
    assert main(["bogus"]) == 2
