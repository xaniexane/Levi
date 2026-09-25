"""Hub agent (Scout) tests — hermetic, no network, no real shell."""

import types

import pytest

from levi.hub import agent, hitl


@pytest.fixture()
def hubdir(monkeypatch, tmp_path):
    monkeypatch.setenv("LEVI_HUB_DIR", str(tmp_path / "hub"))
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_classify_routes():
    assert agent.classify("fetch https://example.com") == "fetch"
    assert agent.classify("run the tests") == "shell"
    assert agent.classify("remember the milk") == "note"
    assert agent.classify("how are you") == "heartbeat"
    assert agent.classify("find me a remote job") == "jobs"
    assert agent.classify("what is the demand for x") == "pulse"
    assert agent.classify("hello there") == "chat"


def test_web_fetch_rejects_non_http():
    res = agent.web_fetch("ftp://x")
    assert res["ok"] is False


def test_note_roundtrip(hubdir):
    assert agent.note("the sky is blue")["ok"] is True
    assert agent.note("  ")["ok"] is False


def test_heartbeat_reports_backend(hubdir):
    hb = agent.heartbeat()
    assert hb["ok"] and hb["sandbox_backend"]
    assert hb["label"] == "OBSERVED"


def test_shell_gated_without_approval(hubdir, monkeypatch):
    # force the degraded (subprocess) backend so the test is deterministic
    fake = types.SimpleNamespace(name="subprocess", isolation_level="NONE")
    monkeypatch.setattr(agent.sb_backends, "select_backend", lambda *a, **k: fake)
    with pytest.raises(hitl.ApprovalRequired):
        agent.shell("echo hello")


def test_shell_degraded_path_needs_explicit_ack(hubdir, monkeypatch):
    fake = types.SimpleNamespace(name="subprocess", isolation_level="NONE")
    monkeypatch.setattr(agent.sb_backends, "select_backend", lambda *a, **k: fake)
    # approved HITL but WITHOUT degraded_sandbox:true -> still refused
    req = hitl.request_approval("shell", {"command": "echo hi"})
    hitl.decide(req["id"], True)
    with pytest.raises(hitl.ApprovalRequired):
        agent.shell("echo hi", hitl_id=req["id"])
    # with the explicit ack -> runs, captured, honest about degradation
    req2 = hitl.request_approval(
        "shell", {"command": "echo hi", "degraded_sandbox": True}
    )
    hitl.decide(req2["id"], True)
    res = agent.shell("echo hi", hitl_id=req2["id"])
    assert res["ok"] and "hi" in res["stdout"]
    assert res["degraded"] is True and res["backend"] == "subprocess"


def test_run_blocks_shell_without_hitl(hubdir, monkeypatch):
    fake = types.SimpleNamespace(name="subprocess", isolation_level="NONE")
    monkeypatch.setattr(agent.sb_backends, "select_backend", lambda *a, **k: fake)
    res = agent.run("run echo hello", command="echo hello")
    assert res["ok"] is False and res["blocked"] == "approval_required"
