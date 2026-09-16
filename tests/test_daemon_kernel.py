"""Daemon kernel hardening tests (hermetic, stdlib-only)."""

from __future__ import annotations

import json

import pytest

from levi.daemon.kernel import DaemonKernel, KernelError, KernelState


@pytest.fixture()
def kernel(tmp_path):
    return DaemonKernel(path=tmp_path / "kernel.json")


def test_emit_validates_inputs(kernel):
    with pytest.raises(ValueError, match="non-empty string"):
        kernel.emit("")
    with pytest.raises(ValueError, match="non-empty string"):
        kernel.emit(None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="dict or None"):
        kernel.emit("tick", payload="nope")  # type: ignore[arg-type]
    ev = kernel.emit("tick", {"n": 1})
    assert ev.kind == "tick" and ev.payload == {"n": 1}


def test_on_validates_handler(kernel):
    with pytest.raises(ValueError, match="callable"):
        kernel.on("tick", "not-a-handler")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="non-empty string"):
        kernel.on("", lambda ev: None)
    seen = []
    kernel.on("tick", seen.append)
    kernel.emit("tick")
    assert len(seen) == 1


def test_register_tool_validates(kernel):
    with pytest.raises(ValueError, match="non-empty string"):
        kernel.register_tool("", "desc")
    with pytest.raises(ValueError, match="non-empty string"):
        kernel.register_tool("name", "  ")
    kernel.register_tool("demo.tool", "Does demo things")
    assert kernel.tool_registry()["demo.tool"] == "Does demo things"


def test_charge_rejects_nonfinite_and_garbage(kernel):
    with pytest.raises(ValueError, match="finite"):
        kernel.charge(float("nan"))
    with pytest.raises(ValueError, match="finite"):
        kernel.charge(float("inf"))
    with pytest.raises(ValueError, match="must be a number"):
        kernel.charge("lots")  # type: ignore[arg-type]
    # Budget enforcement still works after the rejections.
    assert kernel.charge(10, "test") is True
    assert kernel.charge(10**9, "test") is False


def test_nan_charge_cannot_poison_budget():
    # Regression: NaN used to slip past the budget check and poison
    # cost_units_session, disabling all future budget enforcement.
    import pathlib
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        kk = DaemonKernel(path=pathlib.Path(td) / "k.json")
        with pytest.raises(ValueError):
            kk.charge(float("nan"))
        assert kk.state.cost_units_session == 0.0
        assert kk.charge(10**9) is False


def test_from_dict_degrades_per_field():
    st = KernelState.from_dict(
        {
            "safety": "bogus",
            "cycle": "not-an-int",
            "cost_units_session": float("nan"),
            "cost_budget": -5,
            "last_event_id": 123,
        }
    )
    assert st.safety == "normal"
    assert st.cycle == 0
    assert st.cost_units_session == 0.0
    assert st.cost_budget == 100.0
    assert st.last_event_id == ""
    assert KernelState.from_dict(None).safety == "normal"  # type: ignore[arg-type]


def test_corrupt_state_file_resets_cleanly(tmp_path):
    path = tmp_path / "kernel.json"
    path.write_text("{bad json")
    k = DaemonKernel(path=path)
    assert k.state.cycle == 0
    assert k.state.cost_budget == 100.0


def test_persist_failure_is_domain_error(kernel, tmp_path, monkeypatch):
    kernel.emit("tick")  # creates the file
    path = kernel.path
    path.unlink()
    path.mkdir()  # a directory where the file should be
    with pytest.raises(KernelError, match="cannot persist"):
        kernel.emit("tick2")
