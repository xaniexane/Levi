"""Tests: sandbox-tested upgrade paths (B1–B5), U7 approve gating,
and the guarded quetta_loop import (fail-closed, never bare ImportError).

Laws checked:
  B1 ISOLATED   the sandbox never writes outside its own run dir.
  B2 OFFLINE    proxies scrubbed; python socket guard blocks TCP/UDP
                (proven by a real connect attempt); non-python binaries
                need unshare -n or are rejected.
  B3 RECEIPTED  every run writes a JSON receipt.
  B4 NO-SHELL   string checks are rejected, never executed.
  B5 HONEST     untestable is a failure, never a pass.
  U7            approvals require sandbox_ok=True; the checkpoint shows
                simulated + sandbox-tested outcomes together.
"""

import json
import sys
from pathlib import Path

import pytest

from levi.hicomb import sandbox_test
from levi.hicomb import qp_compat
from levi.hicomb.self_upgrade import PROPOSED, SelfUpgradeLoop
from levi.hicomb.qp_compat import (
    QuettaPanUnavailable,
    quetta_loop_available,
    require_quetta_loop,
)


@pytest.fixture()
def root(tmp_path):
    return tmp_path / "sbx"


# ------------------------------------------------------------ B4: no shell
def test_string_check_rejected_never_executed(root):
    with pytest.raises(ValueError, match="no shell"):
        sandbox_test.derive_checks({"checks": ["echo pwned"]})


def test_malformed_argv_rejected(root):
    with pytest.raises(ValueError, match="argv"):
        sandbox_test.derive_checks({"checks": [["ok"], "not-a-list"]})


# ------------------------------------------------------------ B5: honest
def test_empty_change_is_untestable_not_passing(root):
    res = sandbox_test.test_projection("p1", {}, "empty", root)
    assert res.ok is False
    assert any("untestable" in n for n in res.notes)


def test_change_with_no_executable_shape_is_untestable(root):
    res = sandbox_test.test_projection("p2", {"vibes": "good"}, "vibes", root)
    assert res.ok is False


# ------------------------------------------------------------ happy paths
def test_module_smoke_passes(root):
    res = sandbox_test.test_projection("p3", {"module": "pollen"}, "pollen tweak", root)
    assert res.ok is True, res.as_dict()
    assert any(c["name"] == "smoke:pollen" and c["ok"] for c in res.checks)


def test_explicit_check_pass_and_capture(root):
    res = sandbox_test.test_projection(
        "p4",
        {"checks": [{"name": "echo-hi",
                     "argv": [sys.executable, "-c", "print('hi-ho')"]}]},
        "echo", root)
    assert res.ok is True
    assert "hi-ho" in res.checks[0]["detail"]


def test_failing_check_fails_fast(root):
    res = sandbox_test.test_projection(
        "p5",
        {"checks": [
            {"name": "boom",
             "argv": [sys.executable, "-c", "raise SystemExit(3)"]},
            {"name": "never-runs",
             "argv": [sys.executable, "-c", "print('x')"]},
        ]},
        "boom", root)
    assert res.ok is False
    names = [c["name"] for c in res.checks]
    assert names == ["boom"]  # fail fast: second check never ran


def test_candidate_files_staged_in_sandbox_only(root):
    res = sandbox_test.test_projection(
        "p6",
        {"files": {"sub/hello.txt": "hello sandbox"},
         "checks": [{"name": "cat",
                     "argv": [sys.executable, "-c",
                              "print(open('sub/hello.txt').read())"]}]},
        "files", root)
    assert res.ok is True
    assert "hello sandbox" in res.checks[0]["detail"]


def test_path_traversal_in_files_rejected(root):
    res = sandbox_test.test_projection(
        "p7", {"files": {"../escape.txt": "x"}}, "traversal", root)
    assert res.ok is False
    assert any("traversal" in c["detail"] for c in res.checks)


# ------------------------------------------------------------ B1/B2/B3
def test_sandbox_writes_stay_inside_run_dir(root):
    res = sandbox_test.test_projection(
        "p8",
        {"checks": [{"name": "write",
                     "argv": [sys.executable, "-c",
                              "open('made_here.txt','w').write('x')"]}]},
        "write", root)
    assert res.ok is True
    run_dir = root / res.sandbox_dir.split("/")[-1]
    assert (run_dir / "made_here.txt").exists()
    # nothing leaked next to the run dir
    assert not (root / "made_here.txt").exists()


def test_proxies_scrubbed_from_sandbox_env(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://proxy:9999")
    monkeypatch.setenv("http_proxy", "http://proxy:9999")
    env = sandbox_test._sandbox_env()
    assert "HTTP_PROXY" not in env and "http_proxy" not in env
    assert env["PYTHONDONTWRITEBYTECODE"] == "1"


def test_every_run_writes_a_receipt(root):
    sandbox_test.test_projection("p9", {"module": "pollen"}, "rcpt", root)
    receipt = root / "receipts" / "p9.json"
    assert receipt.exists()
    body = json.loads(receipt.read_text(encoding="utf-8"))
    assert body["ok"] is True and body["projection_id"] == "p9"
    assert any("isolation:" in n for n in body["notes"])
    assert any("socket guard" in n for n in body["notes"])


def test_socket_guard_blocks_network_in_sandbox(root):
    """B2(a): a Python check that tries TCP gets OSError from the
    sitecustomize guard — the sandbox is provably offline for Python."""
    probe = (
        "import socket; "
        "socket.create_connection(('127.0.0.1', 9), timeout=2)"
    )
    res = sandbox_test.test_projection(
        "pnet", {"checks": [[sys.executable, "-c", probe]]},
        "network attempt", root)
    assert not res.ok, "a network attempt must fail the sandbox"
    detail = res.checks[0]["detail"]
    assert "network disabled" in detail, f"guard did not fire: {detail!r}"
    # The guard hook itself lives inside the sandbox dir (B1).
    assert (Path(res.sandbox_dir) / "_nethooks" / "sitecustomize.py").is_file()


def test_non_python_check_rejected_without_netns(root, monkeypatch):
    """B2(b): without a network namespace, non-Python executables are
    rejected outright — never run unprotected."""
    import levi.hicomb.sandbox_test as st_mod

    monkeypatch.setattr(st_mod, "_netns_available", lambda: False)
    res = st_mod.test_projection(
        "pbin", {"checks": [["/bin/echo", "hi"]]},
        "binary check", root)
    assert not res.ok
    assert "rejected" in res.checks[0]["detail"]
    assert "network-namespace" in res.checks[0]["detail"]


def test_tested_outcome_text_pass_and_fail(root):
    ok_res = sandbox_test.test_projection("pa", {"module": "pollen"}, "t", root)
    txt = sandbox_test.tested_outcome_text(ok_res)
    assert "SANDBOX-TESTED OUTCOME: PASS" in txt
    bad_res = sandbox_test.test_projection(
        "pb",
        {"checks": [{"name": "nope",
                     "argv": [sys.executable, "-c", "raise SystemExit(1)"]}]},
        "t", root)
    txt = sandbox_test.tested_outcome_text(bad_res)
    assert "SANDBOX-TESTED OUTCOME: FAIL" in txt
    assert "Not approvable" in txt


# ------------------------------------------------------------ U7: gating
@pytest.fixture()
def loop(tmp_path):
    return SelfUpgradeLoop(store_dir=tmp_path / "ide")


def _propose(loop, change=None):
    return loop.propose_projection(
        title="tweak", change=change or {"module": "pollen"},
        projected_outcome="SIMULATED OUTCOME: faster")


def test_approve_refused_without_sandbox_test(loop):
    p = _propose(loop)
    res = loop.decide(p.id, approve=True)
    assert res["ok"] is False
    assert "no sandbox test run yet" in res["error"]


def test_deny_allowed_without_sandbox_test(loop):
    p = _propose(loop)
    res = loop.decide(p.id, approve=False, reason="no")
    assert res["ok"] is True


def test_approve_refused_after_failed_sandbox_test(loop):
    p = _propose(loop, change={"checks": [
        {"name": "boom",
         "argv": [sys.executable, "-c", "raise SystemExit(2)"]}]})
    st = loop.sandbox_test_projection(p.id)
    assert st["ok"] is True and st["sandbox_ok"] is False
    res = loop.decide(p.id, approve=True)
    assert res["ok"] is False
    assert "sandbox test failed" in res["error"]
    # ...but deny routes to the remix store
    assert loop.decide(p.id, approve=False, reason="broken")["ok"] is True
    assert len(loop.denied_paths.list()) == 1


def test_approve_works_after_passed_sandbox_test(loop):
    p = _propose(loop)
    st = loop.sandbox_test_projection(p.id)
    assert st["sandbox_ok"] is True
    dec = loop.decide(p.id, approve=True, reason="tested green")
    assert dec["ok"] is True
    assert loop.apply_projection(p.id)["ok"] is True


def test_checkpoint_shows_both_outcomes(loop):
    p = _propose(loop)
    before = loop.checkpoint(p.id)
    assert before["ok"] and before["approvable"] is False
    assert before["sandbox_ok"] is None
    loop.sandbox_test_projection(p.id)
    cp = loop.checkpoint(p.id)
    assert cp["approvable"] is True
    assert "SIMULATED OUTCOME" in cp["projected_outcome"]
    assert "SANDBOX-TESTED OUTCOME: PASS" in cp["tested_outcome"]
    assert cp["status"] == PROPOSED


def test_sandbox_test_runs_under_snapshot_stage(loop):
    p = _propose(loop)
    loop.sandbox_test_projection(p.id)
    snaps = list((loop.store_dir / ".snapshots").glob("*.json"))
    stages = set()
    for s in snaps:
        try:
            stages.add(json.loads(s.read_text(encoding="utf-8"))["stage"])
        except (KeyError, ValueError):
            pass
    assert "sandbox-test" in stages


# ------------------------------------------------------------ qp guard
def test_quetta_loop_present_in_this_checkout():
    assert quetta_loop_available() is True
    assert require_quetta_loop() is not None


def test_require_fails_closed_naming_module_when_absent(monkeypatch):
    monkeypatch.setattr(qp_compat, "QuettaPanLoop", None)
    monkeypatch.setattr(qp_compat, "_IMPORT_ERROR",
                        ImportError("No module named 'levi.hicomb.quetta_loop'"))
    assert quetta_loop_available() is False
    with pytest.raises(QuettaPanUnavailable, match="levi.hicomb.quetta_loop"):
        require_quetta_loop()

# ------------------------------------- wave 8: sandbox isolation hardening
def test_projection_id_traversal_rejected(root):
    for evil in ("../escape", "..", "a/b", "a\\b", "", "p/../../x"):
        with pytest.raises(ValueError, match="bad projection_id"):
            sandbox_test.test_projection(evil, {"module": "pollen"}, "t", root)
    # nothing escaped the sandbox root
    assert not (root.parent / "escape").exists()


def test_absolute_files_key_rejected_never_staged(root, tmp_path):
    outside = tmp_path / "must_not_exist.txt"
    res = sandbox_test.test_projection(
        "pabs", {"files": {str(outside): "x"}}, "abs", root)
    assert res.ok is False
    assert any("traversal" in c["detail"] for c in res.checks)
    assert not outside.exists()


def test_derive_checks_rejects_bad_module_name():
    for bad in ("../pollen", "a/b", "not-a-module", "a.b", "a b"):
        with pytest.raises(ValueError, match="plain module name"):
            sandbox_test.derive_checks({"module": bad})
    # empty module name simply declares no module (untestable, not an error)
    assert sandbox_test.derive_checks({"module": ""}) == []


def test_same_projection_twice_gets_distinct_run_dirs(root):
    r1 = sandbox_test.test_projection("pdup", {"module": "pollen"}, "t", root)
    r2 = sandbox_test.test_projection("pdup", {"module": "pollen"}, "t", root)
    assert r1.sandbox_dir != r2.sandbox_dir
    assert Path(r1.sandbox_dir).is_dir() and Path(r2.sandbox_dir).is_dir()
