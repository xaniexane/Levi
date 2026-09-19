"""Dynasty Phase 0 tests — builder scope, registry, receipts, roster, shell, snapshot.

Hermetic: every test runs under a tmp LEVI_HOME via monkeypatch. No
network, no daemons, no writes to the real user HOME.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    home = tmp_path / "levi-home"
    monkeypatch.setenv("LEVI_HOME", str(home))
    return home


# -- builder scope ------------------------------------------------------


def test_builder_file_write_in_scope_ok(tmp_home):
    from levi.dynasty.builder import check_tool_scope

    check_tool_scope("file_write", "core/levi/dynasty/shell/x.py")  # must not raise


def test_builder_file_write_outside_scope_rejected(tmp_home):
    from levi.dynasty.builder import ScopeViolation, check_tool_scope

    with pytest.raises(ScopeViolation):
        check_tool_scope("file_write", "core/levi/academy/y.py")


def test_builder_file_write_traversal_rejected(tmp_home):
    from levi.dynasty.builder import ScopeViolation, check_tool_scope

    with pytest.raises(ScopeViolation):
        check_tool_scope("file_write", "core/levi/dynasty/shell/../../evil.py")


def test_builder_unknown_tool_rejected(tmp_home):
    from levi.dynasty.builder import ScopeViolation, check_tool_scope

    with pytest.raises(ScopeViolation):
        check_tool_scope("launch_missiles", "core/levi/dynasty/shell/x.py")


# -- registry -----------------------------------------------------------


def test_registry_register_idempotent(tmp_home):
    from levi.dynasty.registry import register_builder

    first = register_builder()
    second = register_builder()
    assert first["agent_id"] == second["agent_id"] == "dynasty-builder"


def test_registry_seeded_facts_and_status(tmp_home):
    from levi.dynasty.registry import register_builder

    record = register_builder()
    assert record["seeded_facts"], "seeded facts must be non-empty"
    assert record["status"] == "serving"


# -- receipts -----------------------------------------------------------


def test_receipts_chain_two_receipts(tmp_home):
    from levi.dynasty.receipts import mint_receipt, verify_chain

    mint_receipt("test", {"n": 1}, task="first")
    mint_receipt("test", {"n": 2}, task="second")
    assert verify_chain() == 2


def test_receipts_tamper_breaks_chain(tmp_home):
    from levi.dynasty.receipts import ReceiptError, mint_receipt, verify_chain

    mint_receipt("test", {"n": 1}, task="first")
    mint_receipt("test", {"n": 2}, task="second")
    receipts_dir = Path(os.environ["LEVI_HOME"]) / "dynasty" / "receipts"
    receipt_files = sorted(receipts_dir.glob("*.json"))
    assert len(receipt_files) == 2
    with receipt_files[0].open("ab") as fh:
        fh.write(b"X")  # tamper: a single appended byte
    with pytest.raises(ReceiptError):
        verify_chain()


# -- roster -------------------------------------------------------------


def test_roster_has_eleven_agents():
    from levi.dynasty.roster import WAVE_ROSTER

    assert len(WAVE_ROSTER) == 11


def test_roster_signoff_gate():
    from levi.dynasty.roster import check_signoff

    assert check_signoff(["a"]) is False
    assert check_signoff(["a", "a"]) is False
    assert check_signoff(["a", "b"]) is True


# -- shell --------------------------------------------------------------


def test_shell_session_round_trip(tmp_path):
    from levi.dynasty.shell.sessions import SessionManager

    mgr = SessionManager(state_file=tmp_path / "sessions.json")
    created = mgr.create("alpha")
    assert created["name"] == "alpha"
    assert created["status"] == "alive"
    names = [s["name"] for s in mgr.list_sessions()]
    assert names == ["alpha"]
    killed = mgr.kill("alpha")
    assert killed["status"] == "dead"


def test_shell_duplicate_session_rejected(tmp_path):
    from levi.dynasty.shell.sessions import SessionError, SessionManager

    mgr = SessionManager(state_file=tmp_path / "sessions.json")
    mgr.create("alpha")
    with pytest.raises(SessionError):
        mgr.create("alpha")


def test_shell_runner_echo():
    from levi.dynasty.shell.runner import CommandRunner

    result = CommandRunner().run(["echo", "hi"])
    assert "hi" in result["stdout"]
    assert result["returncode"] == 0


def test_shell_runner_refuses_rm_rf_root():
    from levi.dynasty.shell.runner import CommandRunner, RefusedCommand

    with pytest.raises(RefusedCommand):
        CommandRunner().run(["rm", "-rf", "/"])


def test_shell_hooks_round_trip():
    from levi.dynasty.shell.hooks import AutomationHooks

    hooks = AutomationHooks()
    hooks.register("greet", ["echo", "hooked"], schedule_note="demo")
    names = [h["name"] for h in hooks.list_hooks()]
    assert names == ["greet"]
    result = hooks.run("greet")
    assert "hooked" in result["stdout"]
    hooks.remove("greet")
    assert hooks.list_hooks() == []


# -- snapshot -----------------------------------------------------------


def test_snapshot_dynasty_day0(tmp_path, tmp_home):
    from levi.dynasty.snapshot import STAGE_NAME, capture_dynasty_day0

    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "plan.md").write_text("# plan\n", encoding="utf-8")

    snap1 = capture_dynasty_day0(docs_dir=docs_dir, repo_root=ROOT, home=str(tmp_home))
    assert snap1.name == STAGE_NAME == "dynasty-day0"
    assert snap1.payload_hash, "payload hash must be non-empty"

    # Adding a doc changes the sealed payload hash — proving the docs
    # hashes actually live inside the payload.
    (docs_dir / "more.md").write_text("# more\n", encoding="utf-8")
    snap2 = capture_dynasty_day0(docs_dir=docs_dir, repo_root=ROOT, home=str(tmp_home))
    assert snap2.payload_hash != snap1.payload_hash
