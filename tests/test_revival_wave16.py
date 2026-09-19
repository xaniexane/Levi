"""Tests for revival wave 16 — cost-cutting (a): frugal compute, storage, deployment."""

import sys
import time
from datetime import datetime, time as dtime, timedelta
from pathlib import Path

import pytest

from levi.revival import owned_inference as oi
from levi.revival import sqlite_litestream as litestream
from levi.revival import sqlite_replication as repl
from levi.revival import static_deploy as sd
from levi.revival import single_binary_deploy as sbd
from levi.revival import idle_zero as iz
from levi.revival import cron_scale_zero as cron
from levi.revival import uucp_batching as uucp


def _fleet():
    fleet = oi.Fleet()
    rig = oi.Rig(
        name="rig-a",
        watts=300.0,
        memory_gb=24.0,
        purchase_usd=2400.0,
        service_years=4.0,
        electricity_usd_per_kwh=0.15,
    )
    fleet.add_rig(rig)
    fleet.add_model(
        oi.ModelProfile(
            name="levi-small-4bit", params_b=8.0, quant_bits=4.0, measured_tok_s=60.0
        )
    )
    fleet.add_model(
        oi.ModelProfile(
            name="levi-big-4bit", params_b=70.0, quant_bits=4.0, measured_tok_s=12.0
        )
    )
    return fleet


# --- owned_inference -----------------------------------------------------------


def test_owned_inference_cost_law_scales_with_throughput():
    rig = oi.Rig(
        name="r",
        watts=300.0,
        memory_gb=24.0,
        purchase_usd=1200.0,
        service_years=4.0,
        electricity_usd_per_kwh=0.12,
    )
    fast = oi.ModelProfile(
        name="fast", params_b=1.0, quant_bits=4.0, measured_tok_s=100.0
    )
    slow = oi.ModelProfile(
        name="slow", params_b=1.0, quant_bits=4.0, measured_tok_s=25.0
    )
    assert rig.usd_per_token(slow) == pytest.approx(4 * rig.usd_per_token(fast))


def test_owned_inference_fit_check_includes_overhead():
    assert oi.ModelProfile(
        name="m", params_b=8.0, quant_bits=4.0, measured_tok_s=50.0
    ).fits(24.0)  # 4GB + 2GB overhead
    assert not oi.ModelProfile(
        name="m", params_b=70.0, quant_bits=8.0, measured_tok_s=10.0
    ).fits(24.0)


def test_owned_inference_cheapest_plan_and_break_even():
    fleet = _fleet()
    comp = fleet.cheapest_plan("rig-a", 10_000_000, api_usd_per_1m=2.00)
    assert comp is not None
    assert comp.model_name == "levi-small-4bit"  # the 70B model does not fit 24GB
    assert comp.owned_cheaper_by > 0
    months = fleet.break_even_months("rig-a", 2.00, 50_000_000)
    assert months is not None and months > 0
    # API cheaper than owned -> no break-even
    assert fleet.break_even_months("rig-a", 0.0001, 50_000_000) is None


# --- sqlite_litestream ----------------------------------------------------------


def test_litestream_poll_ships_only_new_frames_and_resumes():
    wal = litestream.Wal()
    rep = litestream.Replicator(wal)
    for i in range(3):
        wal.append(f"row-{i}".encode())
    batch = rep.poll()
    assert [f.frame_id for f in batch] == [1, 2, 3]
    assert rep.poll() == []  # nothing new: cursor held
    wal.append(b"row-3")
    assert [f.frame_id for f in rep.poll()] == [4]
    # crash recovery: new replicator with the same checkpoint ships nothing new
    rep2 = litestream.Replicator(wal, checkpoint=rep.checkpoint)
    assert rep2.pending() == []


def test_litestream_verify_rejects_gaps_and_corruption():
    wal = litestream.Wal()
    rep = litestream.Replicator(wal)
    for i in range(4):
        wal.append(f"p{i}".encode())
    shipped = rep.poll()
    rep.verify_shipped(shipped)  # contiguous: fine
    with pytest.raises(litestream.GapError):
        rep.verify_shipped([shipped[0], shipped[2]])  # hole at frame 2
    bad = litestream.Frame(frame_id=99, payload=b"x")
    bad.checksum = "tampered"
    with pytest.raises(litestream.GapError):
        rep.verify_shipped([bad])


def test_litestream_restore_replays_snapshot_plus_frames():
    wal = litestream.Wal()
    rep = litestream.Replicator(wal)
    for i in range(5):
        wal.append(f"v{i}".encode())
    shipped = rep.poll()
    snapshot = [b"v0", b"v1"]
    restored = rep.restore(snapshot, [f for f in shipped if f.frame_id > 2])
    assert restored.latest_id() == 5
    with pytest.raises(litestream.GapError):
        rep.restore(snapshot, [f for f in shipped if f.frame_id > 3])  # gap at 3


def test_litestream_checkpoint_roundtrip_and_prune():
    cp = litestream.Checkpoint(shipped_upto=42)
    cp2 = litestream.Checkpoint.from_json(cp.to_json())
    assert cp2.shipped_upto == 42
    wal = litestream.Wal()
    plan = litestream.ReplicationPlan(retention_frames=5)
    rep = litestream.Replicator(wal, plan=plan)
    for _i in range(20):
        wal.append(b"x")
    rep.poll()
    removed = rep.prune()
    assert removed == 15
    assert wal.latest_id() == 20  # ids are stable; old frames dropped


# --- sqlite_replication ----------------------------------------------------------


def test_replication_elects_leader_and_commits_write():
    cluster = repl.Cluster(["a", "b", "c"])
    cluster.tick(10)
    leader = cluster.leader()
    assert leader is not None
    entry = cluster.write("SET k v")
    assert entry.committed
    assert cluster.divergence() == {
        nid: (entry.term, entry.index) for nid in ("a", "b", "c")
    }


def test_replication_survives_leader_failure_and_catches_up():
    cluster = repl.Cluster(["a", "b", "c"])
    cluster.tick(10)
    first = cluster.leader().node_id
    cluster.write("SET k 1")
    cluster.kill(first)
    cluster.tick(10)
    new_leader = cluster.leader()
    assert new_leader is not None and new_leader.node_id != first
    cluster.revive(first)  # dead node must catch up before serving
    idx = cluster.nodes[first].last_index
    assert idx == cluster.leader().last_index
    # write with no live leader is honestly rejected
    for nid in ("a", "b", "c"):
        cluster.kill(nid)
    with pytest.raises(RuntimeError):
        cluster.write("SET k 2")


def test_replication_read_routing_prefers_followers():
    cluster = repl.Cluster(["a", "b", "c"])
    cluster.tick(10)
    leader_id = cluster.leader().node_id
    routed = {cluster.route_read(f"key-{i}") for i in range(20)}
    assert routed != {leader_id}  # reads spread across followers
    assert routed <= {"a", "b", "c"}


# --- static_deploy ---------------------------------------------------------------


def test_static_deploy_build_and_delta_plan():
    site = sd.Site(
        name="demo",
        pages=[
            sd.Page(path="index.html", title="Home", body="hello"),
            sd.Page(path="about.html", title="About", body="about us"),
        ],
    )
    built = site.build()
    assert len(built) == 2
    old_manifest = sd.Manifest.from_build(built)
    site.pages[0].body = "hello world"  # modify
    site.pages.append(sd.Page(path="new.html", title="New", body="new page"))
    site.pages = [p for p in site.pages if p.path != "about.html"]  # delete
    plan = sd.DeltaPlan.diff(old_manifest, sd.Manifest.from_build(site.build()))
    actions = {t.path: t.action for t in plan.transfers}
    assert actions == {
        "index.html": "modify",
        "new.html": "add",
        "about.html": "delete",
    }
    assert plan.upload_bytes > 0
    assert plan.summary()["modify"] == 1


def test_static_deploy_noop_and_unsafe_paths():
    site = sd.Site(name="demo", pages=[sd.Page(path="i.html", title="T", body="b")])
    m = sd.Manifest.from_build(site.build())
    assert sd.DeltaPlan.diff(m, m).is_noop
    bad = sd.Site(name="x", pages=[sd.Page(path="../evil.html", title="T", body="b")])
    with pytest.raises(ValueError):
        bad.build()
    dup = sd.Site(
        name="x",
        pages=[
            sd.Page(path="a.html", title="T", body="b"),
            sd.Page(path="a.html", title="T2", body="c"),
        ],
    )
    with pytest.raises(ValueError):
        dup.build()


def test_static_deploy_tls_config_and_script():
    cfg = sd.tls_config("demo", "example.com")
    assert "example.com" in cfg and "file_server" in cfg
    plan = sd.DeltaPlan(transfers=[sd.Transfer("a.html", "add", 10)])
    script = sd.deploy_script("demo", plan, "user@host:/var/www/demo")
    assert "user@host" in script and "a.html" in script


# --- single_binary_deploy -----------------------------------------------------------


def _fake_binary(tmp_path: Path) -> Path:
    src = tmp_path / "app.bin"
    src.write_bytes(b"#!/bin/sh\necho hi\n")
    return src


def test_single_binary_promote_and_rollback(tmp_path):
    mgr = sbd.ReleaseManager(tmp_path / "releases-root")
    src = _fake_binary(tmp_path)
    mgr.install("1.0.0", src)
    mgr.install("1.0.1", src)
    assert mgr.promote("1.0.0") is None
    assert mgr.current_version() == "1.0.0"
    assert mgr.promote("1.0.1") == "1.0.0"
    assert mgr.current_version() == "1.0.1"
    assert mgr.rollback() == "1.0.0"
    assert mgr.current_version() == "1.0.0"
    assert len(mgr.history()) == 3
    with pytest.raises(ValueError):
        mgr.promote("9.9.9")  # not installed


def test_single_binary_unit_file_renders(tmp_path):
    spec = sbd.ServiceSpec(
        name="web", args=["--port", "8080"], env={"MODE": "prod"}, memory_max="256M"
    )
    text = sbd.unit_file(spec, tmp_path)
    assert "ExecStart=" in text and "MemoryMax=256M" in text
    assert 'Environment="MODE=prod"' in text and "Restart=always" in text
    with pytest.raises(ValueError):
        sbd.unit_file(sbd.ServiceSpec(name="bad name!"), tmp_path)


def test_single_binary_prune_keeps_live_and_newest(tmp_path):
    mgr = sbd.ReleaseManager(tmp_path / "root2")
    src = _fake_binary(tmp_path)
    for v in ("1.0.0", "1.0.1", "1.0.2", "1.0.3"):
        mgr.install(v, src)
    mgr.promote("1.0.1")
    removed = mgr.prune(keep=1)
    assert "1.0.1" in mgr.installed()  # live is never pruned
    assert mgr.installed() == ["1.0.1", "1.0.3"]  # live + newest 1
    assert sorted(removed) == ["1.0.0", "1.0.2"]


# --- idle_zero ---------------------------------------------------------------------


def test_idle_zero_callable_worker_serve_and_reap():
    sup = iz.IdleZeroSupervisor(idle_timeout_s=60.0)
    sup.register("echo", lambda payload: f"got:{payload}")
    assert sup.serve("echo", "hi") == "got:hi"
    assert sup.resident_workers() == ["echo"]
    stats = sup.stats()
    assert stats["echo"]["serves"] == 1 and stats["echo"]["cold_starts"] == 1
    reaped = sup.reap(now=time.monotonic() + 3600)
    assert reaped == ["echo"]
    assert sup.resident_workers() == []
    assert sup.stats()["total_reaps"] == 1
    # serving again after reap is a cold start again
    assert sup.serve("echo", "again") == "got:again"
    assert sup.stats()["echo"]["cold_starts"] == 2
    sup.shutdown()


def test_idle_zero_subprocess_worker_roundtrip():
    sup = iz.IdleZeroSupervisor(idle_timeout_s=60.0)
    code = (
        "import sys\n"
        "for line in sys.stdin:\n"
        "    sys.stdout.write('pong:' + line)\n"
        "    sys.stdout.flush()\n"
    )
    sup.register("ponger", [sys.executable, "-c", code])
    try:
        assert sup.serve("ponger", "ping") == "pong:ping"
        assert sup.resident_workers() == ["ponger"]
        assert sup.reap(now=time.monotonic() + 3600) == ["ponger"]
    finally:
        sup.shutdown()


def test_idle_zero_rejects_unknown_and_bad_specs():
    sup = iz.IdleZeroSupervisor()
    with pytest.raises(KeyError):
        sup.serve("nope", "x")
    with pytest.raises(ValueError):
        sup.register("bad", "not-a-callable-or-argv")
    sup.register("ok", lambda p: p)
    with pytest.raises(ValueError):
        sup.register("ok", lambda p: p)  # duplicate
    sup.shutdown()


# --- cron_scale_zero -----------------------------------------------------------------


def test_cron_next_after_every_five_minutes():
    expr = cron.CronExpr("*/5 * * * *")
    nxt = expr.next_after(datetime(2026, 9, 16, 10, 2))
    assert nxt == datetime(2026, 9, 16, 10, 5)
    upcoming = expr.upcoming(datetime(2026, 9, 16, 10, 2), 3)
    assert upcoming == [
        datetime(2026, 9, 16, 10, 5),
        datetime(2026, 9, 16, 10, 10),
        datetime(2026, 9, 16, 10, 15),
    ]


def test_cron_weekday_and_range_semantics():
    # 2026-09-16 is a Wednesday (weekday() == 2)
    assert datetime(2026, 9, 16).weekday() == 2
    expr = cron.CronExpr("0 2 * * 2")  # 02:00 on Wednesdays
    assert expr.next_after(datetime(2026, 9, 16, 3, 0)) == datetime(2026, 9, 23, 2, 0)
    with pytest.raises(ValueError):
        cron.CronExpr("0 0 * *")  # only 4 fields
    with pytest.raises(ValueError):
        cron.CronExpr("61 * * * *")  # minute out of range


def test_cron_ledger_idempotency(tmp_path):
    ledger = cron.RunLedger(tmp_path / "runs.jsonl")
    rec = ledger.start("nightly", datetime(2026, 9, 16, 2, 0))
    assert rec.run_id == "nightly-2026-09-16T02:00:00"
    with pytest.raises(cron.DuplicateRunError):
        ledger.start("nightly", datetime(2026, 9, 16, 2, 0))  # same watermark
    ledger.finish(rec.run_id, ok=True)
    assert len(ledger.runs_for("nightly")) == 1


def test_cron_savings_and_quiet_windows():
    model = cron.CostModel(
        always_on_watts=150.0,
        run_watts=150.0,
        sleep_watts=8.0,
        electricity_usd_per_kwh=0.20,
        run_minutes=10.0,
    )
    s = model.savings(runs_per_day=4)
    assert s["saved_usd"] > 0 and s["saved_pct"] > 90
    fires = [
        datetime(2026, 9, 16, 2, 0),
        datetime(2026, 9, 16, 2, 10),
        datetime(2026, 9, 16, 8, 0),
    ]
    windows = cron.quiet_windows(fires, min_gap=timedelta(hours=1))
    assert len(windows) == 1
    assert windows[0][2] == timedelta(hours=5, minutes=50)


# --- uucp_batching ---------------------------------------------------------------------


def _open_window():
    return uucp.DialWindow(start=dtime(0, 0), end=dtime(23, 59), name="test")


def test_uucp_enqueue_flush_and_ack(tmp_path):
    spool = uucp.Spool(tmp_path / "spool")
    j1 = spool.enqueue("mail", {"to": "a"})
    j2 = spool.enqueue("mail", {"to": "b"})
    assert len(spool) == 2
    seen = []
    report = spool.flush(
        lambda job: seen.append(job["job_id"]) or "ACK", _open_window()
    )
    assert report.acked == 2 and report.failed == 0
    assert set(report.acks) == {j1.job_id, j2.job_id}
    assert len(spool) == 0  # queue drained, acks on disk
    assert (spool.acked / f"{j1.job_id}.ack").exists()


def test_uucp_closed_window_flushes_nothing_and_backoff_dead_letters(tmp_path):
    spool = uucp.Spool(tmp_path / "spool2", max_attempts=2, backoff_base_s=10_000)
    spool.enqueue("news", {"item": 1}, job_id="job-1")
    closed = uucp.DialWindow(start=dtime(2, 0), end=dtime(2, 30), name="nightly")
    at = datetime(2026, 9, 16, 12, 0)
    assert not closed.is_open(at)
    report = spool.flush(lambda job: "ACK", closed, at=at)
    assert report.attempted == 0 and len(spool) == 1

    def fail(job):
        raise ConnectionError("line down")

    window = _open_window()
    r1 = spool.flush(fail, window)
    assert r1.failed == 1 and r1.dead_lettered == 0 and len(spool) == 1
    # backoff not elapsed -> skipped, not re-attempted
    r2 = spool.flush(fail, window)
    assert r2.attempted == 0
    # force backoff elapsed by aging the failure timestamp
    spool._last_failure_at["job-1"] -= 100_000
    r3 = spool.flush(fail, window)
    assert r3.dead_lettered == 1 and len(spool) == 0
    assert [j.job_id for j in spool.dead_letters()] == ["job-1"]
    rej = spool.requeue_dead("job-1")
    assert rej.attempts == 0 and len(spool) == 1


def test_uucp_dial_window_midnight_wrap_and_rate_card():
    w = uucp.DialWindow(start=dtime(23, 0), end=dtime(1, 0))
    assert w.is_open(datetime(2026, 9, 16, 23, 30))
    assert w.is_open(datetime(2026, 9, 17, 0, 30))
    assert not w.is_open(datetime(2026, 9, 16, 12, 0))
    assert w.next_open(datetime(2026, 9, 16, 12, 0)) == datetime(2026, 9, 16, 23, 0)
    card = uucp.BatchRateCard(warm_usd_per_1k=1.0, batch_usd_per_1k=0.6)
    cmp = card.compare(1000)
    assert cmp["saved_usd"] == pytest.approx(400.0)
    assert cmp["discount_pct"] == pytest.approx(40.0)
