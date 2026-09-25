"""cyberpulse form tests: master-pulse registration, sensing, heartbeat.

Proving bar: registration is fail-closed, the master never registers
itself, heartbeats are dry-run pure, and CyberPulse only claims signals
its sensors actually have.
"""

from levi.cyberpulse import FORM_NAME, CyberPulse, capabilities


def test_capabilities_are_honest_about_sensors():
    caps = capabilities()
    assert caps["form"] == FORM_NAME
    assert "only" in caps["honest_limit"]


def test_register_rejects_bad_names_as_data():
    cp = CyberPulse()
    for bad in ("", "   ", 42, None, ["x"]):
        r = cp.register_pulse(bad, {"module": "levi.nexus"})
        assert r["status"] == "rejected", bad
    # master may not register itself as a channel
    r = cp.register_pulse("cyberpulse", {"module": "levi.cyberpulse"})
    assert r["status"] == "rejected"


def test_register_rejects_bad_module_binding():
    cp = CyberPulse()
    r = cp.register_pulse("weird", {"module": 42})
    assert r["status"] == "rejected"


def test_register_ok_and_receipt_carries_channels():
    cp = CyberPulse()
    r = cp.register_pulse("vector", {"module": "levi.vector"})
    assert r["status"] == "registered"
    assert "vector" in r["channels"]


def test_probe_reports_honestly():
    cp = CyberPulse()
    p = cp.probe("observability")
    assert p["status"] == "present"
    cp.register_pulse("ghost", {"module": "levi.does_not_exist"})
    p = cp.probe("ghost")
    assert p["status"] == "absent"
    p = cp.probe("never-registered")
    assert p["status"] == "unknown"
    cp.register_pulse("meta-only")
    assert cp.probe("meta-only")["status"] == "unprobed"


def test_heartbeat_dry_run_purity():
    cp = CyberPulse()
    r = cp.heartbeat(dry_run=True)
    assert r["status"] == "dry-run"
    assert r["dry_run"] is True
    assert cp.history() == []  # nothing recorded on a dry run
    r2 = cp.heartbeat(dry_run=False)
    assert r2["status"] == "heartbeat"
    assert len(cp.history()) == 1


def test_heartbeat_always_carries_probes_and_receipt_reason():
    cp = CyberPulse()
    r = cp.heartbeat(dry_run=True)
    assert isinstance(r["probes"], list) and r["probes"]
    assert r["reason"]  # a receipt always carries a reason


def test_sense_without_store_is_honest(tmp_path):
    cp = CyberPulse()
    s = cp.sense()
    assert s["status"] == "no-store"  # never touches ~/.levi on its own
    s2 = cp.sense(trace_dir=tmp_path)  # empty dir: honest zero, no crash
    assert s2["status"] == "sensed"
    assert s2["recent_traces"] == 0


def test_sense_reads_traces_from_given_store(tmp_path):
    from levi.observability.schema import TurnTrace
    from levi.observability.store import TraceStore

    store = TraceStore(tmp_path)
    trace = TurnTrace(
        turn_id="t1",
        ts="2026-09-17T00:00:00Z",
        session_id="s",
        route="r",
        persona_id="p",
        provider="rules",
        outcome="success",
    )
    store.append(trace)
    cp = CyberPulse()
    s = cp.sense(trace_dir=tmp_path)
    assert s["status"] == "sensed"
    assert s["recent_traces"] == 1
    assert s["outcomes"] == {"success": 1}
