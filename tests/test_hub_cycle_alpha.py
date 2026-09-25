"""Hub orchestrator + alpha-lab tests — hermetic."""

import pytest

from levi.hub import alpha as alpha_lab
from levi.hub import hitl, orchestrator


@pytest.fixture()
def hubdir(monkeypatch, tmp_path):
    monkeypatch.setenv("LEVI_HUB_DIR", str(tmp_path / "hub"))
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_cycle_actually_runs(hubdir, monkeypatch):
    # keep discover honest but offline: no scans exist in a fresh HOME
    receipt = orchestrator.run_cycle("test cycle")
    assert receipt["ok"] is True
    stages = receipt["cycle"]
    for stage in ("discover", "evaluate", "execute", "optimize"):
        assert stage in stages
    assert receipt["overseer"] and receipt["execution_engine"]
    assert receipt["label"] == "INFERENCE"


def test_execute_queues_hitl_for_empty_buffer(hubdir):
    evaluation = {"ranked": [{"item": "job review buffer is empty", "weight": 1}]}
    out = orchestrator.execute(evaluation)
    assert out["queued"] and out["queued"][0]["hitl_id"]
    assert hitl.pending()


def test_alpha_design_and_preview(hubdir):
    d = alpha_lab.design("todo list web app")
    assert d["ok"] and d["blueprint"]
    assert d["label"] == "INFERENCE"
    p = alpha_lab.preview("todo list web app")
    assert p["ok"] and p["files"]


def test_alpha_create_gated_then_materializes(hubdir, tmp_path):
    dest = tmp_path / "build1"
    blocked = alpha_lab.create("todo list web app", str(dest))
    assert blocked["ok"] is False and blocked["blocked"] == "approval_required"
    assert not dest.exists()
    hitl_id = blocked["hitl_id"]
    hitl.decide(hitl_id, True, note="test")
    done = alpha_lab.create(
        "todo list web app", str(dest), approve=True, hitl_id=hitl_id
    )
    assert done["ok"] is True
    assert (dest / "manifest.json").exists()
    assert done["manifest"]["hitl_id"] == hitl_id


def test_alpha_create_refuses_without_approved_hitl(hubdir, tmp_path):
    dest = tmp_path / "build2"
    with pytest.raises(hitl.ApprovalRequired):
        alpha_lab.create("todo list web app", str(dest), approve=True, hitl_id=None)
