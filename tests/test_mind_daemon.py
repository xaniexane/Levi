"""Tests for the mind runner daemon skeleton (BRAINUX milestone 1.1).

Hermetic: every test points LEVI_MIND_HOME at a tmp dir. The only real
process spawned is the skeleton worker, which idles and heartbeats —
no network, no weights, no inference.
"""

from __future__ import annotations

import json

from pathlib import Path

import pytest

from levi.mind import config as mind_config
from levi.mind import daemon as mind_daemon
from levi.mind import guard
from levi.mind.__main__ import main as mind_main

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    mind_dir = tmp_path / "mind"
    monkeypatch.setenv("LEVI_MIND_HOME", str(mind_dir))
    return mind_dir


# --- config ----------------------------------------------------------------


def test_config_defaults_and_roundtrip(home: Path) -> None:
    cfg = mind_config.ensure(home)
    assert cfg["inference"]["mode"] == "local"
    assert cfg["network"]["remote_inference"] is False
    assert cfg["server"]["enabled"] is False
    assert (home / mind_config.CONFIG_FILE).exists()
    # Roundtrip preserves user edits and deep-merges with defaults.
    cfg["weights"]["bundle"] = "brain-0001.bundle"
    mind_config.save(cfg, home)
    reloaded = mind_config.load(home)
    assert reloaded["weights"]["bundle"] == "brain-0001.bundle"
    assert reloaded["server"]["host"] == "127.0.0.1"


def test_config_corrupt_fails_closed(home: Path) -> None:
    home.mkdir(parents=True, exist_ok=True)
    (home / mind_config.CONFIG_FILE).write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        mind_config.load(home)


# --- guard -----------------------------------------------------------------


def test_guard_local_on_defaults() -> None:
    report = guard.check(mind_config.DEFAULT_CONFIG)
    assert report.verdict is guard.Verdict.LOCAL
    assert report.allowed


@pytest.mark.parametrize(
    "patch",
    [
        {"network": {"remote_inference": True}},
        {"network": {"api_url": "https://cloud.example.com/v1"}},
        {"network": {"telemetry": True}},
        {"inference": {"mode": "remote"}},
        {"server": {"enabled": True, "host": "0.0.0.0"}},
        {"weights": {"registry": "https://weights.example.com"}},
    ],
)
def test_guard_refuses_network_paths(patch: dict) -> None:
    import copy

    base = copy.deepcopy(mind_config.DEFAULT_CONFIG)

    def _apply(b: dict, p: dict) -> None:
        for k, v in p.items():
            if isinstance(v, dict) and isinstance(b.get(k), dict):
                _apply(b[k], v)
            else:
                b[k] = v

    _apply(base, patch)
    report = guard.check(base)
    assert report.verdict is guard.Verdict.REFUSED, report.reasons
    assert not report.allowed
    assert report.reasons, "refusals must carry explicit reasons"


def test_guard_uncertain_on_non_mapping() -> None:
    report = guard.check("definitely not a config")
    assert report.verdict is guard.Verdict.UNCERTAIN
    assert not report.allowed


def test_guard_never_grants_on_absence() -> None:
    # An empty mapping is not positive local-only evidence.
    report = guard.check({})
    assert report.verdict is guard.Verdict.REFUSED
    assert not report.allowed


# --- daemon lifecycle ------------------------------------------------------


def test_start_stop_lifecycle(home: Path) -> None:
    code, result = mind_daemon.start(home)
    assert code == mind_daemon.EXIT_OK, result
    assert result["state"] == "running"
    pid = result["pid"]

    try:
        st = mind_daemon.status(home)
        assert st["state"] == "running", st
        assert st["pid"] == pid

        # Double start is idempotent, not a second worker.
        code2, result2 = mind_daemon.start(home)
        assert code2 == mind_daemon.EXIT_OK
        assert result2["pid"] == pid

        # Plain-speech, machine, and CLI views all agree.
        code3 = mind_main(["--home", str(home), "status"])
        assert code3 == mind_daemon.EXIT_OK
    finally:
        code_s, res_s = mind_daemon.stop(home)
        assert code_s == mind_daemon.EXIT_OK
        assert res_s["state"] == "stopped"

    assert mind_daemon.status(home)["state"] == "stopped"
    assert not (home / mind_config.PID_FILE).exists()


def test_stop_when_stopped_is_quiet(home: Path) -> None:
    code, result = mind_daemon.stop(home)
    assert code == mind_daemon.EXIT_OK
    assert result["state"] == "stopped"


def test_stale_pidfile_gets_its_own_state(home: Path) -> None:
    home.mkdir(parents=True, exist_ok=True)
    # A pid that is (near-certainly) not alive.
    dead_pid = 2**31 - 1
    (home / mind_config.PID_FILE).write_text(str(dead_pid), encoding="utf-8")
    st = mind_daemon.status(home)
    assert st["state"] == "stale", st
    assert "stale" in st["detail"]
    # The pidfile is cleaned; the next status reads "stopped".
    assert not (home / mind_config.PID_FILE).exists()
    assert mind_daemon.status(home)["state"] == "stopped"


def test_start_refused_with_network_path(home: Path) -> None:
    cfg = mind_config.ensure(home)
    cfg["network"]["api_url"] = "https://cloud.example.com/v1"
    mind_config.save(cfg, home)

    code, result = mind_daemon.start(home)
    assert code == mind_daemon.EXIT_REFUSED, result
    assert result["state"] == "stopped"
    assert not (home / mind_config.PID_FILE).exists(), "no worker may spawn on refusal"

    # CLI reports the same refusal with reasons in plain speech.
    code_cli = mind_main(["--home", str(home), "guard"])
    assert code_cli == mind_daemon.EXIT_REFUSED


def test_start_refused_on_corrupt_config_fails_closed(home: Path) -> None:
    home.mkdir(parents=True, exist_ok=True)
    (home / mind_config.CONFIG_FILE).write_text("{not json", encoding="utf-8")
    code, result = mind_daemon.start(home)
    assert code == mind_daemon.EXIT_REFUSED, result
    assert result["verdict"]["verdict"] == "uncertain"
    assert not (home / mind_config.PID_FILE).exists()


def test_guard_command_allowed_on_clean_config(home: Path, capsys) -> None:
    mind_config.ensure(home)
    code = mind_main(["--home", str(home), "guard"])
    assert code == mind_daemon.EXIT_OK
    out = capsys.readouterr().out
    assert "local" in out


def test_status_json_shape(home: Path, capsys) -> None:
    code, result = mind_daemon.start(home)
    assert code == mind_daemon.EXIT_OK
    try:
        code_cli = mind_main(["--home", str(home), "status", "--json"])
        assert code_cli == mind_daemon.EXIT_OK
        payload = json.loads(capsys.readouterr().out)
        assert payload["state"] == "running"
        assert isinstance(payload["pid"], int)
    finally:
        mind_daemon.stop(home)


def test_no_network_imports_in_mind_sources() -> None:
    # The skeleton must not import socket/http machinery at all. Scan the
    # package sources rather than sys.modules, which pytest itself pollutes.
    import re

    pkg = Path(mind_config.__file__).parent
    for path in sorted(pkg.glob("*.py")):
        src = path.read_text(encoding="utf-8")
        for match in re.finditer(r"^\s*(?:import|from)\s+([a-zA-Z0-9_.]+)", src, re.M):
            module = match.group(1)
            assert not module.startswith(("socket", "http", "urllib", "requests")), (
                f"{path.name} imports network module {module}"
            )
