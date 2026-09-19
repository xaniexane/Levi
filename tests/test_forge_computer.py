"""Tests for the Forge computer (levi.forge.computer) — hermetic.

All machine state goes to a tmp dir via the ``LEVI_FORGE_HOME`` env var
(resolved lazily at call time, so no module patching is needed).
"""

import json

import pytest

from levi.forge import computer as _computer
from levi.forge.computer import (
    Machine,
    MachineError,
    OverwriteRefusedError,
    PathEscapeError,
    open_machine,
)
from levi.forge.rail import DeniedError, NeedsApprovalError, NotApprovedError


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_FORGE_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def m(home):
    return open_machine()


def run_approved(machine, tool, args, note="test"):
    """Propose → approve → run, returning the receipt dict."""
    pid = machine.propose(tool, args)
    machine.approve(pid, note)
    return machine.run(pid)


# -- registry ---------------------------------------------------------------


def test_registry_lists_ten_tools(m):
    tools = m.describe_tools()
    names = [t["name"] for t in tools]
    assert names == [
        "terminal.run",
        "fs.list",
        "fs.read",
        "fs.write",
        "fs.preview_write",
        "fs.overwrite",
        "fs.edit",
        "fs.mkdir",
        "fs.delete",
        "fs.restore",
    ]
    assert all("risk" in t and "args" in t for t in tools)


def test_unknown_tool_is_deny_closed(m):
    with pytest.raises(DeniedError):
        m.propose("rm.everything", {})
    denied = [p for p in m.rail.history() if p["status"] == "denied"]
    assert denied, "the refusal itself must be on the record"


# -- terminal -----------------------------------------------------------------


def test_terminal_run_captures_output(m):
    r = run_approved(m, "terminal.run", {"argv": ["echo", "hello"]})
    assert r["verified"] is True
    assert r["details"]["output"].strip() == "hello"
    assert r["details"]["returncode"] == 0
    assert r["receipt_id"]


def test_terminal_run_no_shell_ever(m):
    # ';' is a literal argument to echo, not a control operator.
    r = run_approved(m, "terminal.run", {"cmd": "echo a; echo b"})
    assert r["details"]["output"].strip() == "a; echo b"


def test_terminal_run_nonzero_exit_is_receipted_not_raised(m):
    r = run_approved(m, "terminal.run", {"argv": ["false"]})
    assert r["verified"] is False
    assert "exit 1" in r["outcome"]


def test_terminal_run_timeout(m):
    r = run_approved(m, "terminal.run", {"argv": ["sleep", "5"], "timeout": 0.3})
    assert r["verified"] is False
    assert "timed out" in r["outcome"]
    assert r["details"]["timed_out"] is True


def test_terminal_run_destructive_denied_at_plan(m):
    with pytest.raises(DeniedError):
        m.propose("terminal.run", {"argv": ["rm", "-rf", "/"]})
    with pytest.raises(DeniedError):
        m.propose("terminal.run", {"cmd": "mkfs.ext4 /dev/sda1"})


def test_terminal_run_needs_approval_for_do(m):
    with pytest.raises(NeedsApprovalError):
        m.do("terminal.run", {"argv": ["echo", "x"]})


def test_terminal_run_refuses_unapproved_execute(m):
    pid = m.propose("terminal.run", {"argv": ["echo", "x"]})
    m.permit(pid)  # MODERATE → awaiting explicit permission
    with pytest.raises(NeedsApprovalError):
        m.run(pid)  # never approved


def test_terminal_runs_in_workspace_by_default(m):
    r = run_approved(m, "terminal.run", {"argv": ["pwd"]})
    assert r["details"]["output"].strip() == str(m.workspace)


# -- filesystem ---------------------------------------------------------------


def test_fs_write_read_roundtrip(m):
    w = m.do("fs.write", {"path": "note.txt", "content": "levi was here"})
    assert w["verified"] is True
    r = m.do("fs.read", {"path": "note.txt"})
    assert r["details"]["content"] == "levi was here"


def test_fs_write_refuses_existing_without_preview(m):
    m.do("fs.write", {"path": "note.txt", "content": "one"})
    with pytest.raises(OverwriteRefusedError):
        m.do("fs.write", {"path": "note.txt", "content": "two"})


def test_fs_overwrite_requires_preview_and_approval(m):
    m.do("fs.write", {"path": "note.txt", "content": "one"})
    # no preview yet: refused at plan
    with pytest.raises(OverwriteRefusedError):
        m.propose(
            "fs.overwrite", {"path": "note.txt", "content": "two", "overwrite": True}
        )
    # preview with DIFFERENT content: still refused
    m.do("fs.preview_write", {"path": "note.txt", "content": "three"})
    with pytest.raises(OverwriteRefusedError):
        m.propose(
            "fs.overwrite", {"path": "note.txt", "content": "two", "overwrite": True}
        )
    # matching preview, but do() won't auto-approve HIGH
    pv = m.do("fs.preview_write", {"path": "note.txt", "content": "two"})
    assert "-one" in pv["details"]["diff"] and "+two" in pv["details"]["diff"]
    with pytest.raises(NeedsApprovalError):
        m.do("fs.overwrite", {"path": "note.txt", "content": "two", "overwrite": True})
    # explicit operator approval: executes
    r = run_approved(
        m, "fs.overwrite", {"path": "note.txt", "content": "two", "overwrite": True}
    )
    assert r["verified"] is True
    assert m.do("fs.read", {"path": "note.txt"})["details"]["content"] == "two"


def test_fs_overwrite_needs_explicit_flag(m):
    m.do("fs.write", {"path": "note.txt", "content": "one"})
    m.do("fs.preview_write", {"path": "note.txt", "content": "two"})
    with pytest.raises(MachineError):
        m.propose("fs.overwrite", {"path": "note.txt", "content": "two"})


def test_fs_edit_exact_once_match(m):
    m.do("fs.write", {"path": "a.txt", "content": "alpha beta alpha"})
    with pytest.raises(MachineError):
        m.propose(
            "fs.edit", {"path": "a.txt", "old_text": "alpha", "new_text": "omega"}
        )
    m.do("fs.preview_write", {"path": "a.txt", "content": "alpha beta omega"})
    # 'alpha beta' occurs exactly once
    m.do("fs.preview_write", {"path": "a.txt", "content": "omega beta alpha"})
    r = run_approved(
        m,
        "fs.edit",
        {"path": "a.txt", "old_text": "alpha beta", "new_text": "omega beta"},
    )
    assert r["verified"] is True
    assert (
        m.do("fs.read", {"path": "a.txt"})["details"]["content"] == "omega beta alpha"
    )


def test_fs_delete_goes_to_trash_and_restores(m):
    m.do("fs.write", {"path": "gone.txt", "content": "bye"})
    r = run_approved(m, "fs.delete", {"path": "gone.txt"})
    assert r["verified"] is True
    assert not (m.workspace / "gone.txt").exists()
    trash_name = r["details"]["trash_name"]
    back = m.do("fs.restore", {"name": trash_name})
    assert back["verified"] is True
    assert m.do("fs.read", {"path": "gone.txt"})["details"]["content"] == "bye"


def test_fs_list(m):
    m.do("fs.write", {"path": "x.txt", "content": "x"})
    m.do("fs.mkdir", {"path": "sub"})
    r = m.do("fs.list", {"path": "."})
    names = {e["name"] for e in r["details"]["entries"]}
    assert {"x.txt", "sub"} <= names


def test_paths_cannot_escape_workspace(m):
    with pytest.raises(PathEscapeError):
        m.propose("fs.read", {"path": "../../etc/passwd"})
    with pytest.raises(PathEscapeError):
        m.propose("fs.write", {"path": "/abs/path.txt", "content": "x"})
    with pytest.raises(PathEscapeError):
        m.propose("terminal.run", {"argv": ["pwd"], "cwd": ".."})


# -- receipts -----------------------------------------------------------------


def test_every_action_leaves_a_receipt(home, m):
    m.do("fs.write", {"path": "a.txt", "content": "a"})
    run_approved(m, "terminal.run", {"argv": ["true"]})
    log = home / "machine" / "receipts.jsonl"
    assert log.exists()
    receipts = [json.loads(ln) for ln in log.read_text().splitlines()]
    assert len(receipts) == 2
    assert all(r["verified"] for r in receipts)
    assert all(r["id"] and r["action_id"] and r["timestamp"] for r in receipts)


def test_failed_action_still_receipted(m):
    r = run_approved(m, "terminal.run", {"argv": ["false"]})
    assert r["verified"] is False
    hist = m.rail.history()
    assert any(p["status"] == "completed" and p["receipt_id"] for p in hist)


def test_denied_action_stays_denied(m):
    pid = m.propose("terminal.run", {"argv": ["echo", "x"]})
    m.deny(pid, "not today")
    with pytest.raises((NotApprovedError, Exception)):
        m.run(pid)
