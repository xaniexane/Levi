"""Unified supervisor tests (hermetic, stdlib-only).

LEVI_HOME and LEVI_OATH_HOME are pointed at tmp dirs for every test, so the
real ``~/.levi`` is never touched.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from levi.daemon import supervisor as sup_mod
from levi.daemon.supervisor import Supervisor

EXPECTED_SERVICES = {
    "control-daemon": "levi.daemon.control",
    "automation-engine": "levi.daemon.automation",
    "daemon-kernel": "levi.daemon.kernel",
    "heartbeat": "levi.daemon.heartbeat",
    "perpetual": "levi.perpetual.supervise",
    "galaxy-services": "levi.galaxy.service",
    "oath-trust": "levi.oath",
    "agent-server": "levi.agent.server",
}

REQUIRED_KEYS = {"name", "module", "summary", "start_hint", "health"}


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "levi-home"))
    monkeypatch.setenv("LEVI_OATH_HOME", str(tmp_path / "oath-home"))
    return tmp_path / "levi-home"


@pytest.fixture()
def sup(home):
    return Supervisor(home=home)


# -- catalog integrity ------------------------------------------------------


def test_catalog_has_all_expected_services(sup):
    entries = sup.list_services()
    assert len(entries) == len(EXPECTED_SERVICES)
    by_name = {e["name"]: e for e in entries}
    for name, module in EXPECTED_SERVICES.items():
        assert name in by_name, f"missing service {name}"
        assert by_name[name]["module"] == module


def test_catalog_entries_have_required_shape(sup):
    entries = sup.list_services()
    names = [e["name"] for e in entries]
    assert len(set(names)) == len(names), "service names must be unique"
    for entry in entries:
        assert REQUIRED_KEYS <= set(entry), f"{entry['name']} missing keys"
        assert entry["summary"].strip(), f"{entry['name']} needs a summary"
        assert entry["start_hint"].strip(), f"{entry['name']} needs a start hint"
        assert callable(entry["health"]), f"{entry['name']} health not callable"


def test_catalog_modules_all_importable(sup):
    for entry in sup.list_services():
        mod = importlib.import_module(entry["module"])
        assert mod is not None, f"{entry['module']} failed to import"


def test_list_services_hides_internal_binding_key(sup):
    for entry in sup.list_services():
        assert "_check_fn" not in entry


# -- stable API -------------------------------------------------------------


def test_service_status_shape_and_up(sup):
    st = sup.service_status("heartbeat")
    assert st["name"] == "heartbeat"
    assert st["module"] == "levi.daemon.heartbeat"
    assert st["status"] == "up"
    assert st["ok"] is True
    assert st["detail"].strip()
    assert st["checked_at"].strip()


def test_all_services_report_up_against_tmp_home(sup):
    statuses = sup.all_status()
    assert set(statuses) == set(EXPECTED_SERVICES)
    for name, st in statuses.items():
        assert st["ok"] is True, f"{name} down: {st['detail']}"
        assert st["status"] == "up"


def test_unknown_service_never_raises(sup):
    st = sup.service_status("definitely-not-a-service")
    assert st["status"] == "unknown"
    assert st["ok"] is False
    assert "definitely-not-a-service" in st["detail"]


def test_supervise_once_pulse_shape(sup, home):
    report = sup.supervise_once()
    assert report["total"] == len(EXPECTED_SERVICES)
    assert report["up"] == len(EXPECTED_SERVICES)
    assert report["down"] == 0
    assert report["home"] == str(home)
    assert report["ran_at"].strip()
    assert set(report["services"]) == set(EXPECTED_SERVICES)


def test_health_check_exception_becomes_down_not_raise(sup):
    def boom():
        raise RuntimeError("simulated failure")

    sup._entries[0]["health"] = sup_mod._guarded(boom)
    st = sup.service_status(sup._entries[0]["name"])
    assert st["ok"] is False
    assert st["status"] == "down"
    assert "RuntimeError" in st["detail"]


def test_module_level_api_uses_env_home(home, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(home))
    entries = sup_mod.list_services()
    assert len(entries) == len(EXPECTED_SERVICES)
    st = sup_mod.service_status("daemon-kernel")
    assert st["ok"] is True
    report = sup_mod.supervise_once()
    assert report["up"] == report["total"] == len(EXPECTED_SERVICES)


def test_pulse_is_hermetic_no_real_home_writes(sup, tmp_path, monkeypatch):
    # Point every known home override at tmp; the pulse must not create
    # anything under the real user home.
    real_home = Path.home()
    before = set(real_home.iterdir()) if real_home.exists() else set()
    sup.supervise_once()
    after = set(real_home.iterdir()) if real_home.exists() else set()
    assert after == before, "pulse wrote to the real home directory"


# -- foreground entrypoint --------------------------------------------------


def _run_daemon_cli(home: Path, *argv: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["LEVI_HOME"] = str(home)
    env["LEVI_OATH_HOME"] = str(home / "oath")
    env["PYTHONPATH"] = str(Path(sup_mod.__file__).resolve().parents[2])
    return subprocess.run(
        [sys.executable, "-m", "levi.daemon", "--home", str(home), *argv],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )


def test_cli_pulse(tmp_path, monkeypatch):
    home = tmp_path / "cli-home"
    proc = _run_daemon_cli(home, "pulse")
    assert proc.returncode == 0, proc.stderr
    assert "8/8 up" in proc.stdout


def test_cli_list_and_status(tmp_path, monkeypatch):
    home = tmp_path / "cli-home"
    proc = _run_daemon_cli(home, "list")
    assert proc.returncode == 0, proc.stderr
    for name in EXPECTED_SERVICES:
        assert name in proc.stdout

    proc = _run_daemon_cli(home, "status", "oath-trust")
    assert proc.returncode == 0, proc.stderr
    assert "UP" in proc.stdout

    proc = _run_daemon_cli(home, "status", "--json")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert set(payload) == set(EXPECTED_SERVICES)
