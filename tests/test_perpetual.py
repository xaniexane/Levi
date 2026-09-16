"""Hermetic tests for the Perpetual Engine.

No network, no daemons, no real HOME writes: every test passes an explicit
tmp home. Deterministic: supervisor tests drive tick() manually.
"""

import json
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from levi.archive.record import ArchiveRecord, Provenance
from levi.perpetual import hunt, pulse as pulse_mod, supervise
from levi.revival.otp import ChildSpec, Supervisor


def _rec(i, rating="load-bearing"):
    return ArchiveRecord(
        id="arch-test-software-widget-%d" % i,
        title="Widget %d" % i,
        era="Acme, 1987-1991",
        kind="software",
        summary="A forgotten widget system.",
        mechanism="Did X before anyone else.",
        decline="Killed by neglect.",
        revival_recipe="Rebuild the mechanism with modern IPC.",
        levi_application="Use for local tool sandboxing.",
        sources=["https://example.com/widget-%d" % i],
        rating=rating,
        status="dead",
        provenance=Provenance(found_date="2026-09-16",
                             research_slug="test-slug",
                             notes="fixture"),
    )


# ------------------------------------------------------- supervision


def _failer(stop_event, attempts, fail_times):
    attempts.append(1)
    if len(attempts) <= fail_times:
        raise RuntimeError("boom %d" % len(attempts))
    stop_event.wait(30)


def _sleeper(stop_event):
    stop_event.wait(30)


def test_supervisor_restarts_crashed_child(tmp_path):
    attempts = []
    sup = Supervisor(
        [ChildSpec("svc", _failer, args=(attempts, 2),
                   max_restarts=5, restart_window=60.0)],
        strategy="one_for_one",
    ).start(start_monitor=False)
    try:
        for _ in range(40):
            sup.tick()
            time.sleep(0.02)
            if len(attempts) >= 3:
                break
        assert len(attempts) >= 3  # crashed twice, third run alive
        st = sup.status()
        assert st["children"]["svc"]["state"] == "running"
        assert st["children"]["svc"]["restarts"] == 2
        assert len(sup.crash_reports()) == 2
    finally:
        sup.shutdown()


def test_supervisor_gives_up_on_restart_intensity(tmp_path):
    attempts = []
    sup = Supervisor(
        [ChildSpec("doomed", _failer, args=(attempts, 999),
                   max_restarts=1, restart_window=600.0)],
        strategy="one_for_one",
    ).start(start_monitor=False)
    try:
        for _ in range(60):
            sup.tick()
            time.sleep(0.02)
            if sup.gave_up:
                break
        assert sup.gave_up == "doomed"
        st = sup.status()
        assert st["children"]["doomed"]["state"] == "defunct"
    finally:
        sup.shutdown()


def test_crash_reports_persist_and_load(tmp_path):
    attempts = []
    sup = Supervisor(
        [ChildSpec("svc", _failer, args=(attempts, 1),
                   max_restarts=5, restart_window=60.0)],
    ).start(start_monitor=False)
    try:
        for _ in range(30):
            sup.tick()
            time.sleep(0.02)
            if sup.crash_reports():
                break
        assert sup.crash_reports()
        written = supervise.persist_crash_reports(sup, home=tmp_path)
        assert written == 1
        loaded = supervise.load_crash_reports(home=tmp_path)
        assert len(loaded) == 1
        assert loaded[0]["child"] == "svc"
        assert loaded[0]["exc_type"] == "RuntimeError"
        assert "boom" in loaded[0]["message"]
        # Second persist with since=newest writes nothing new.
        newest = max(r.at for r in sup.crash_reports())
        assert supervise.persist_crash_reports(sup, home=tmp_path,
                                               since=newest) == 0
    finally:
        sup.shutdown()


def test_alive_marker_fresh_stale_missing(tmp_path):
    now = 1_700_000_000.0
    assert supervise.read_alive_marker(home=tmp_path, now=now)["running"] is False
    supervise.write_alive_marker(home=tmp_path, now=now)
    fresh = supervise.read_alive_marker(home=tmp_path, now=now + 10)
    assert fresh["running"] is True
    stale = supervise.read_alive_marker(home=tmp_path, now=now + 10_000)
    assert stale["running"] is False
    assert stale["reason"] == "stale"


def test_service_overview_lists_configured_services(tmp_path):
    ov = supervise.service_overview(home=tmp_path)
    assert ov["services"] == ["levi-automation", "levi-growth", "levi-heartbeat"]
    assert ov["strategy"] == "one_for_one"
    assert ov["alive"]["running"] is False


def test_build_supervisor_specs_are_valid():
    sup = supervise.build_supervisor()
    st = sup.status()
    assert set(st["children"]) == {"levi-heartbeat", "levi-growth",
                                   "levi-automation"}


# ------------------------------------------------------- hunt


def test_plan_next_hunt_picks_first_uncovered_theme():
    plan = hunt.plan_next_hunt(hunt.HuntState())
    assert plan.theme.id == "dead-protocols"  # waves 1-3 are covered
    assert "Q-Codes" in plan.exclusions
    assert not plan.deeper_vein
    assert plan.wave_id == "wave-001"


def test_plan_next_hunt_never_repeats_covered_ground():
    now = datetime.now(timezone.utc)
    state = hunt.HuntState(waves=[
        hunt.HuntWave(id="wave-001", theme_id="dead-protocols",
                      planned_at=now.isoformat(), status="completed",
                      completed_at=now.isoformat(), findings_count=30),
    ])
    plan = hunt.plan_next_hunt(state)
    assert plan.theme.id == "lost-interfaces"


def test_plan_returns_open_wave_instead_of_stacking():
    state = hunt.HuntState(waves=[
        hunt.HuntWave(id="wave-007", theme_id="dead-protocols",
                      planned_at="2026-09-01T00:00:00+00:00",
                      status="in-progress"),
    ])
    plan = hunt.plan_next_hunt(state)
    assert plan.wave_id == "wave-007"


def test_record_hunt_happy_path(tmp_path):
    now = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    state = hunt.HuntState()
    plan = hunt.plan_next_hunt(state, now=now)
    result = hunt.record_hunt(state, plan.wave_id,
                              [_rec(1, "load-bearing"),
                               _rec(2, "inspirational")],
                              research_slug="test-slug",
                              home=tmp_path, now=now)
    assert result["findings"] == 2
    assert result["build_queued"] == 1  # inspirational is not queued
    pending = Path(result["pending_file"])
    assert pending.exists()
    assert len(pending.read_text().strip().splitlines()) == 2
    # state persisted and marked completed
    reloaded = hunt.load_state(home=tmp_path)
    assert reloaded.waves[0].status == "completed"
    assert reloaded.waves[0].findings_count == 2
    assert reloaded.next_due != ""
    queue = hunt.read_build_queue(home=tmp_path)
    assert len(queue) == 1
    assert queue[0]["record_id"] == "arch-test-software-widget-1"
    assert queue[0]["status"] == "queued"


def test_record_hunt_refuses_empty_findings(tmp_path):
    state = hunt.HuntState()
    plan = hunt.plan_next_hunt(state)
    with pytest.raises(ValueError):
        hunt.record_hunt(state, plan.wave_id, [], research_slug="s",
                         home=tmp_path)


def test_record_hunt_refuses_duplicate_ids(tmp_path):
    state = hunt.HuntState()
    plan = hunt.plan_next_hunt(state)
    with pytest.raises(ValueError, match="duplicate record id"):
        hunt.record_hunt(state, plan.wave_id, [_rec(1), _rec(1)],
                         research_slug="s", home=tmp_path)
    # nothing half-recorded
    assert hunt.pending_waves(home=tmp_path) == []


def test_record_hunt_refuses_double_complete(tmp_path):
    state = hunt.HuntState()
    plan = hunt.plan_next_hunt(state)
    hunt.record_hunt(state, plan.wave_id, [_rec(1)], research_slug="s",
                     home=tmp_path)
    with pytest.raises(ValueError, match="already completed"):
        hunt.record_hunt(state, plan.wave_id, [_rec(2)], research_slug="s",
                         home=tmp_path)


def test_record_hunt_refuses_malformed_record_dict(tmp_path):
    # from_dict raises on malformed input before record_hunt is reached.
    with pytest.raises(ValueError):
        ArchiveRecord.from_dict({"id": "bogus", "title": ""})


def test_record_hunt_refuses_bad_slug(tmp_path):
    state = hunt.HuntState()
    plan = hunt.plan_next_hunt(state)
    with pytest.raises(ValueError, match="research_slug"):
        hunt.record_hunt(state, plan.wave_id, [_rec(1)],
                         research_slug="UPPER BAD", home=tmp_path)


# ------------------------------------------------------- pulse


def test_pulse_degrades_honestly_on_empty_home(tmp_path):
    snap = pulse_mod.read_pulse(home=tmp_path)
    assert snap["engine_running"] is False
    assert snap["archive"]["status"] == "not-initialized"
    assert snap["hunts"]["waves_completed"] == 0
    assert snap["build_queue_depth"] == 0
    text = pulse_mod.format_pulse(snap)
    assert "NOT RUNNING" in text
    assert "not initialized yet" in text


def test_pulse_reflects_hunt_and_queue(tmp_path):
    now = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    state = hunt.HuntState()
    plan = hunt.plan_next_hunt(state, now=now)
    hunt.record_hunt(state, plan.wave_id, [_rec(1)], research_slug="s",
                     home=tmp_path, now=now)
    supervise.write_alive_marker(home=tmp_path, now=now.timestamp())
    snap = pulse_mod.read_pulse(home=tmp_path, now=now.timestamp())
    assert snap["engine_running"] is True
    assert snap["hunts"]["waves_completed"] == 1
    assert snap["hunts"]["last_wave"] == plan.wave_id
    assert snap["build_queue_depth"] == 1
    text = pulse_mod.format_pulse(snap)
    assert "ALIVE" in text
    assert plan.wave_id in text


def test_pulse_never_raises_on_corrupt_crash_file(tmp_path):
    crash_dir = tmp_path / ".levi" / "perpetual" / "crashes"
    crash_dir.mkdir(parents=True)
    (crash_dir / "crash-x.json").write_text("{not json")
    snap = pulse_mod.read_pulse(home=tmp_path)
    assert snap["crashes_total"] == 0


# ------------------------------------------------------- hard-route law


def _costly_rec():
    r = _rec(9)
    return ArchiveRecord(
        id=r.id, title=r.title, era=r.era, kind=r.kind, summary=r.summary,
        mechanism=r.mechanism, decline=r.decline,
        revival_recipe="Rebuild it, or just call the vendor's paid API.",
        levi_application=r.levi_application, sources=r.sources,
        rating=r.rating, status=r.status, provenance=r.provenance,
    )


def test_hard_route_review_flags_costly_recipe():
    flagged = hunt.hard_route_review([_rec(1), _costly_rec()])
    assert len(flagged) == 1
    assert flagged[0]["record_id"] == "arch-test-software-widget-9"
    assert "paid api" in flagged[0]["signals"]


def test_hard_route_review_clean_record_passes():
    assert hunt.hard_route_review([_rec(1)]) == []


def test_build_queue_marks_hard_route_items(tmp_path):
    now = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    n = hunt.queue_for_build([_rec(1), _costly_rec()], "wave-001",
                             home=tmp_path, now=now)
    assert n == 2
    queue = hunt.read_build_queue(home=tmp_path)
    by_id = {q["record_id"]: q for q in queue}
    assert by_id["arch-test-software-widget-1"]["hard_route"] is False
    costly = by_id["arch-test-software-widget-9"]
    assert costly["hard_route"] is True
    assert "clean-room" in costly["hard_route_note"]


def test_record_hunt_reports_hard_route_flags(tmp_path):
    state = hunt.HuntState()
    plan = hunt.plan_next_hunt(state)
    result = hunt.record_hunt(state, plan.wave_id, [_rec(1), _costly_rec()],
                              research_slug="s", home=tmp_path)
    assert len(result["hard_route_flagged"]) == 1
    assert (result["hard_route_flagged"][0]["record_id"]
            == "arch-test-software-widget-9")


def test_hunt_plan_instructions_carry_hard_route_law():
    plan = hunt.plan_next_hunt(hunt.HuntState())
    assert "HARD-ROUTE LAW" in plan.instructions
    assert "clean-room recreation" in plan.instructions
    assert hunt.HARD_ROUTE_LAW.startswith("HARD-ROUTE LAW")


# ------------------------------------------------------- CLI smoke


def _run_cli(tmp_path, *argv):
    env = dict(__import__("os").environ)
    env["PYTHONPATH"] = "core"
    return subprocess.run(
        [sys.executable, "-m", "levi.perpetual", "--home", str(tmp_path), *argv],
        cwd=str(Path(__file__).resolve().parents[1]),
        env=env, capture_output=True, text=True, timeout=60,
    )


def test_cli_pulse_and_services(tmp_path):
    r = _run_cli(tmp_path, "pulse")
    assert r.returncode == 0, r.stderr
    assert "perpetual engine" in r.stdout
    r = _run_cli(tmp_path, "services")
    assert r.returncode == 0, r.stderr
    assert "levi-heartbeat" in r.stdout


def test_cli_hunt_plan_and_record(tmp_path):
    r = _run_cli(tmp_path, "hunt-plan")
    assert r.returncode == 0, r.stderr
    assert "HUNT PLAN wave-001" in r.stdout
    findings = tmp_path / "findings.jsonl"
    findings.write_text("\n".join([
        json.dumps(_rec(1).to_dict()), json.dumps(_rec(2).to_dict())]) + "\n")
    r = _run_cli(tmp_path, "hunt-record", "wave-001", str(findings),
                 "--slug", "test-slug")
    assert r.returncode == 0, r.stderr
    assert '"findings": 2' in r.stdout
    # recording the same wave again is refused
    r = _run_cli(tmp_path, "hunt-record", "wave-001", str(findings),
                 "--slug", "test-slug")
    assert r.returncode == 2
