"""Hermetic tests for F7: registry ``check_all()`` in CI + daemon self-check.

- The CI workflow runs the registry contract check in the python job.
- The daemon supervisor catalog carries an ``interop-registry`` health
  entry whose check reports wiring validity (DOWN on broken wiring,
  never raising).
"""

import pytest
import yaml

import levi.interop.registry as reg
from levi.daemon.supervisor import (
    Supervisor,
    _check_interop_registry,
)


def _repo_root():
    import pathlib

    return pathlib.Path(__file__).resolve().parent.parent


def test_f7_ci_runs_registry_check_all():
    ci = _repo_root() / ".github" / "workflows" / "ci.yml"
    assert ci.exists(), "CI workflow must exist"
    wf = yaml.safe_load(ci.read_text(encoding="utf-8"))
    steps = wf["jobs"]["python"]["steps"]
    runs = [s.get("run", "") for s in steps if "run" in s]
    assert any("levi.interop.registry" in r and "check_all" in r for r in runs), (
        "CI python job must run the interop registry check_all contract check"
    )


def test_f7_check_reports_valid_wiring():
    ok, detail = _check_interop_registry()
    assert ok is True
    assert "wiring valid" in detail


def test_f7_check_reports_broken_wiring(monkeypatch):
    def _boom():
        raise reg.RegistryError("check_all: 1 invalid declaration(s)")

    monkeypatch.setattr(reg, "check_all", _boom)
    ok, detail = _check_interop_registry()
    assert ok is False
    assert "BROKEN" in detail


def test_f7_check_never_raises(monkeypatch):
    monkeypatch.setattr(
        reg, "check_all", lambda: (_ for _ in ()).throw(RuntimeError("weird"))
    )
    # the catalog wraps the check in _guarded; exercise the catalog path
    sup = Supervisor(home="/tmp/levi-f7-test")
    entry = next(e for e in sup.SERVICE_CATALOG if e["name"] == "interop-registry")
    ok, detail = entry["health"]()
    assert ok is False
    assert detail  # a reason, never silence


def test_f7_catalog_lists_interop_registry():
    entry = next(
        (e for e in Supervisor.SERVICE_CATALOG if e["name"] == "interop-registry"),
        None,
    )
    assert entry is not None
    assert entry["module"] == "levi.interop.registry"
