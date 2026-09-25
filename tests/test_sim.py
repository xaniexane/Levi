"""Hermetic tests for LEVI's bounded simulations (levi.sim).

* determinism: bounty-hunt twice with the same seed -> identical transcript
* zero-network: socket/urllib turned into landmines; both scenarios must
  complete without touching them
* sim labeling: "SIMULATION" appears in output
* soc-shift: scripted input completes and prints a grade
* shim hygiene: the bounty pipeline's real network functions are restored
  after a sim run
"""

import builtins
import contextlib
import hashlib
import io
import socket
import urllib.request

import pytest

from levi.bounty import content as content_mod
from levi.bounty import enum as enum_mod
from levi.bounty import probe as probe_mod
from levi.sim import SCENARIOS, run_scenario
from levi.sim.bounty_hunt import run as run_bounty_hunt
from levi.sim.soc_shift import run as run_soc_shift


def _capture(fn, *args, **kwargs):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(*args, **kwargs)
    return rc, buf.getvalue()


@pytest.fixture
def hermetic_env(tmp_path, monkeypatch):
    """Belt and braces: isolated HOME, no color/effects, deterministic tty."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.delenv("COLUMNS", raising=False)
    monkeypatch.delenv("LINES", raising=False)
    return tmp_path


def _landmines(monkeypatch):
    """Turn the real network stack into assertion landmines."""

    def _boom(*args, **kwargs):
        raise AssertionError("real network touched during simulation")

    monkeypatch.setattr(socket, "socket", _boom)
    monkeypatch.setattr(socket, "create_connection", _boom)
    monkeypatch.setattr(socket, "getaddrinfo", _boom)
    monkeypatch.setattr(urllib.request, "urlopen", _boom)


# -- determinism ------------------------------------------------------------


def test_bounty_hunt_deterministic(hermetic_env):
    rc1, out1 = _capture(run_bounty_hunt, 4242)
    rc2, out2 = _capture(run_bounty_hunt, 4242)
    assert rc1 == 0 and rc2 == 0
    h1 = hashlib.sha256(out1.encode()).hexdigest()
    h2 = hashlib.sha256(out2.encode()).hexdigest()
    assert h1 == h2, "same seed must produce an identical transcript"


def test_bounty_hunt_different_seeds_differ(hermetic_env):
    _, out1 = _capture(run_bounty_hunt, 4242)
    _, out2 = _capture(run_bounty_hunt, 777)
    assert (
        hashlib.sha256(out1.encode()).hexdigest()
        != hashlib.sha256(out2.encode()).hexdigest()
    )


# -- zero network -----------------------------------------------------------


def test_bounty_hunt_zero_network(hermetic_env, monkeypatch):
    _landmines(monkeypatch)
    rc, out = _capture(run_bounty_hunt, 7)
    assert rc == 0
    assert "SIMULATION" in out
    # the sim actually exercised the pipeline against the world
    assert "simtarget-7.test" in out
    assert "Coverage" in out


def test_soc_shift_zero_network(hermetic_env, monkeypatch):
    _landmines(monkeypatch)
    monkeypatch.setattr(builtins, "input", lambda *a, **k: "1")
    rc, out = _capture(run_soc_shift, 7)
    assert rc == 0
    assert "SIMULATION" in out


# -- labeling -----------------------------------------------------------------


@pytest.mark.parametrize("fn", [run_bounty_hunt, run_soc_shift])
def test_simulation_banner_present(hermetic_env, monkeypatch, fn):
    monkeypatch.setattr(builtins, "input", lambda *a, **k: "1")
    rc, out = _capture(fn, 99)
    assert rc == 0
    assert out.count("SIMULATION") >= 2, "banner at start AND end, minimum"
    assert ".test" in out or "simulated" in out.lower()


# -- soc-shift ----------------------------------------------------------------


def test_soc_shift_completes_with_grade(hermetic_env, monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda *a, **k: "1")  # always investigate
    rc, out = _capture(run_soc_shift, 1234)
    assert rc == 0
    assert "GRADE" in out
    assert "SHIFT REPORT" in out


def test_soc_shift_deterministic(hermetic_env, monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda *a, **k: "2")  # always escalate
    _, out1 = _capture(run_soc_shift, 555)
    _, out2 = _capture(run_soc_shift, 555)
    assert (
        hashlib.sha256(out1.encode()).hexdigest()
        == hashlib.sha256(out2.encode()).hexdigest()
    )


# -- shim hygiene ---------------------------------------------------------------


def test_shims_restored_after_run(hermetic_env):
    _capture(run_bounty_hunt, 31337)
    for mod, attr in [
        (enum_mod, "_fetch_text"),
        (enum_mod, "_resolve"),
        (probe_mod, "_tcp_open"),
        (probe_mod, "_http_get"),
        (probe_mod, "_tls_cert"),
        (content_mod, "wayback_urls"),
        (content_mod, "_fetch_text"),
    ]:
        fn = getattr(mod, attr)
        assert getattr(fn, "__module__", None) == mod.__name__, (
            f"{mod.__name__}.{attr} was not restored after the sim run"
        )


def test_sim_domain_never_real_looking(hermetic_env):
    from levi.sim.world import SimWorld

    for seed in (1, 4242, 999999, 2**31 - 1):
        w = SimWorld(seed)
        assert w.domain.endswith(".test"), w.domain
        assert "simtarget" in w.domain
        for host in w.hosts:
            assert host.fqdn.endswith(".test"), host.fqdn
            for ip in host.ips:
                assert ip.startswith("203.0.113."), ip  # TEST-NET-3 only


# -- dispatch -----------------------------------------------------------------


def test_run_scenario_dispatch(hermetic_env, monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda *a, **k: "1")
    assert set(SCENARIOS) == {"bounty-hunt", "soc-shift"}
    rc, _ = _capture(run_scenario, "bounty-hunt", 11)
    assert rc == 0
    rc, _ = _capture(run_scenario, "soc-shift", 11)
    assert rc == 0
    rc, out = _capture(run_scenario, "nope-not-real", 11)
    assert rc == 2
    assert "unknown simulation" in out
