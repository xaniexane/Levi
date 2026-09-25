"""Hub HITL tests — hermetic, no network."""

import pytest

from levi.hub import hitl


@pytest.fixture()
def hubdir(monkeypatch, tmp_path):
    monkeypatch.setenv("LEVI_HUB_DIR", str(tmp_path / "hub"))
    return tmp_path


def test_request_approve_flow(hubdir):
    req = hitl.request_approval("alpha.create", {"dest": "/tmp/x"})
    assert req["status"] == "pending"
    assert hitl.pending()
    out = hitl.decide(req["id"], True, note="go")
    assert out["status"] == "approved"
    assert hitl.is_approved(req["id"])
    assert hitl.pending() == []


def test_reject_flow(hubdir):
    req = hitl.request_approval("shell", {"command": "rm -rf /"})
    out = hitl.decide(req["id"], False, note="absolutely not")
    assert out["status"] == "rejected"
    assert not hitl.is_approved(req["id"])


def test_double_decide_rejected(hubdir):
    req = hitl.request_approval("x", {})
    hitl.decide(req["id"], True)
    with pytest.raises(ValueError):
        hitl.decide(req["id"], True)


def test_require_gate(hubdir):
    with pytest.raises(hitl.ApprovalRequired):
        hitl.require(None)
    req = hitl.request_approval("x", {})
    with pytest.raises(hitl.ApprovalRequired):
        hitl.require(req["id"])  # pending, not approved
    hitl.decide(req["id"], True)
    hitl.require(req["id"])  # no raise
