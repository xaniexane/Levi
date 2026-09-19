"""Tests for revival wave 18 — cost-cutting (frugal compute, storage, deployment)."""

from datetime import datetime, timedelta, timezone

import pytest

from levi.revival import arm_hosts, carbon_scheduler, crypt_backup, laptop_server
from levi.revival import offpeak_scheduling as ops
from levi.revival import restic, sneakernet


def _now():
    return datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# sneakernet — drive rotation
# ---------------------------------------------------------------------------


def _pool():
    pool = sneakernet.RotationPool()
    for i in range(3):
        pool.add_drive(f"usb-{i}", capacity_bytes=10**9)
    return pool


def test_sneakernet_full_rotation_cycle():
    pool = _pool()
    now = _now()
    pool.dock("usb-0")
    pool.write_copy("usb-0", {"a.txt": b"hello"}, now)
    moved = pool.rotate(now)
    assert moved["usb-0"] == "transit"
    assert moved["usb-1"] == "onsite"  # oldest offsite comes home docked
    # second hand: write a fresh copy to the docked drive, then rotate
    pool.write_copy("usb-1", {"b.txt": b"world"}, now + timedelta(hours=12))
    moved2 = pool.rotate(now + timedelta(days=1))
    assert moved2["usb-0"] == "offsite"
    assert moved2["usb-1"] == "transit"
    status = pool.status(now + timedelta(days=1))
    assert status["drives"] == 3
    assert status["offsite_freshest_days"] is not None


def test_sneakernet_verify_and_quarantine():
    pool = _pool()
    now = _now()
    pool.dock("usb-0")
    files = {"a.txt": b"hello"}
    pool.write_copy("usb-0", files, now)
    assert pool.verify("usb-0", files) is True
    assert pool.verify("usb-0", {"a.txt": b"tampered"}) is False
    pool.quarantine("usb-0")
    with pytest.raises(sneakernet.RotationError):
        pool.dock("usb-0")


def test_sneakernet_overdue_and_capacity_guard():
    pool = _pool()
    now = _now()
    pool.dock("usb-0")
    pool.write_copy("usb-0", {"a.txt": b"x" * 100}, now)
    pool.rotate(now)
    pool.write_copy("usb-1", {"a.txt": b"x" * 100}, now + timedelta(hours=1))
    pool.rotate(now + timedelta(days=1))  # usb-0 now offsite
    late = pool.overdue(now + timedelta(days=10), threshold_days=5.0)
    assert "usb-0" in late
    assert pool.overdue(now + timedelta(days=2), threshold_days=5.0) == []
    # capacity guard
    pool2 = _pool()
    pool2.dock("usb-2")
    with pytest.raises(sneakernet.RotationError):
        pool2.write_copy("usb-2", {"big": b"y" * (10**9 + 1)}, now)
    # cannot rotate without a fresh copy
    with pytest.raises(sneakernet.RotationError):
        pool2.rotate(now)


# ---------------------------------------------------------------------------
# crypt_backup — blinded manifests + tier economics
# ---------------------------------------------------------------------------


def test_crypt_backup_blinded_manifest_roundtrip():
    m = crypt_backup.BlindedManifest(key=b"0" * 32)
    entry = m.add("docs/secret.txt", b"payload")
    assert entry.blob_name != "docs/secret.txt"
    assert len(entry.blob_name) == 64  # opaque hex, no path leaks
    assert m.resolve(entry.blob_name) == "docs/secret.txt"
    assert m.verify("docs/secret.txt", b"payload") is True
    assert m.verify("docs/secret.txt", b"changed") is False
    # deterministic for a fixed key
    m2 = crypt_backup.BlindedManifest(key=b"0" * 32)
    assert m2.add("docs/secret.txt", b"payload").blob_name == entry.blob_name
    m.remove("docs/secret.txt")
    assert m.file_count == 0


def test_crypt_backup_cheapest_tier_and_report():
    backup = crypt_backup.BackupSet(base_tb=2.0, monthly_change_tb=0.1)
    econ = crypt_backup.TierEconomics(backup)
    econ.add_tier(crypt_backup.StorageTier("cheap-object", 6.0))  # $6/TB-month
    econ.add_tier(crypt_backup.StorageTier("owned", 0.0))
    econ.add_tier(crypt_backup.StorageTier("pricey", 23.0))
    tier, cost = econ.cheapest(month=1)
    assert tier.name == "owned" and cost == 0.0
    report = econ.report(year=1)
    # 6 $/TB-mo * sum of stored TB over 12 months (2.0 + 0.1*(m-1))
    assert report["cheap-object"] == pytest.approx(6.0 * 30.6, rel=0.001)
    assert report["owned"] == 0.0
    assert econ.stored_tb(3) == pytest.approx(2.2)


def test_crypt_backup_breakeven():
    backup = crypt_backup.BackupSet(base_tb=1.0)
    econ = crypt_backup.TierEconomics(backup)
    tier = crypt_backup.StorageTier("cheap-object", 6.0)  # $6/TB-month
    months = econ.breakeven_months(buy_price_dollars=120.0, buy_tb=4.0, tier=tier)
    assert months == pytest.approx(20.0)  # 120 / (6*1) = 20 months
    # outgrows the drive -> never breaks even
    growing = crypt_backup.BackupSet(base_tb=1.0, monthly_change_tb=1.0)
    econ2 = crypt_backup.TierEconomics(growing)
    assert econ2.breakeven_months(120.0, 4.0, tier) is None
    with pytest.raises(crypt_backup.BackupError):
        crypt_backup.StorageTier("bad", -1.0)


# ---------------------------------------------------------------------------
# restic — dedup vault
# ---------------------------------------------------------------------------


def test_restic_dedup_collapses_identical_data():
    vault = restic.DedupVault()
    now = _now()
    data = b"A" * 20000
    s1 = vault.snapshot("first", {"f.bin": data}, taken_at=now)
    s2 = vault.snapshot(
        "second",
        {"f.bin": data},
        taken_at=now + timedelta(hours=1),
        parent_id=s1.snap_id,
    )
    stats = vault.stats()
    assert stats["snapshots"] == 2.0
    assert stats["stored_bytes"] < stats["logical_bytes"]  # second copy deduped
    assert stats["dedup_ratio"] > 1.5
    assert s2.parent_id == s1.snap_id


def test_restic_restore_roundtrip_and_verify():
    vault = restic.DedupVault()
    files = {"a.txt": b"hello world" * 500, "b.txt": b"\x00\x01\x02" * 300}
    snap = vault.snapshot("docs", files, taken_at=_now())
    assert vault.verify(snap.snap_id) is True
    assert vault.restore(snap.snap_id) == files
    with pytest.raises(restic.VaultError):
        vault.restore("nope")


def test_restic_prune_and_forget_gc_chunks():
    vault = restic.DedupVault()
    base = _now()
    ids = []
    for i in range(5):
        s = vault.snapshot(
            f"snap-{i}",
            {"f.txt": f"content-{i}".encode() * 1000},
            taken_at=base + timedelta(days=i),
        )
        ids.append(s.snap_id)
    removed = vault.prune(restic.RetentionPolicy(keep_last=2))
    assert len(removed) == 3
    assert len(vault.list_snapshots()) == 2
    chunks_before = vault.stats()["chunks"]
    vault.forget(ids[-1])
    assert vault.stats()["snapshots"] == 1.0
    assert vault.stats()["chunks"] <= chunks_before  # orphaned chunks collected
    # chunker is content-defined: insertion shifts only local chunks
    chunks_a = restic.chunk_data(b"x" * 100000)
    chunks_b = restic.chunk_data(b"INSERT" + b"x" * 100000)
    assert len(chunks_a) > 1 and abs(len(chunks_a) - len(chunks_b)) <= 2


# ---------------------------------------------------------------------------
# offpeak_scheduling — TOU placement
# ---------------------------------------------------------------------------


def _tariff():
    return ops.Tariff(
        name="tou",
        windows=[
            ops.Window("off-peak", 22, 24, 0.05),
            ops.Window("off-peak2", 0, 6, 0.05),
            ops.Window("shoulder", 6, 16, 0.12),
            ops.Window("peak", 16, 22, 0.25),
        ],
    )


def test_offpeak_preemptible_job_lands_in_cheapest_hours():
    sched = ops.Nightshift(_tariff())
    job = ops.Job("train", watts=400.0, duration_hours=3.0, preemptible=True)
    p = sched.schedule(job)
    hours = {h for h, _ in p.slices}
    assert hours <= set(range(0, 6)) | {22, 23}
    assert p.cost_dollars == pytest.approx(0.4 * 3 * 0.05)


def test_offpeak_savings_report_beats_peak_baseline():
    sched = ops.Nightshift(_tariff())
    jobs = [
        ops.Job("train", watts=400.0, duration_hours=4.0, preemptible=True),
        ops.Job("transcode", watts=150.0, duration_hours=2.0, preemptible=True),
    ]
    placements = [sched.schedule(j) for j in jobs]
    report = sched.savings_report(jobs, placements)
    assert report["savings_pct"] > 25.0  # the studied 25–45% band
    assert report["saved_dollars"] > 0


def test_offpeak_rigid_job_and_deadline():
    sched = ops.Nightshift(_tariff())
    rigid = ops.Job("inference", watts=200.0, duration_hours=2.5, preemptible=False)
    p = sched.schedule(rigid)
    assert len(p.slices) == 3  # rounded up, contiguous whole hours
    hours = [h for h, _ in p.slices]
    assert hours == [hours[0], (hours[0] + 1) % 24, (hours[0] + 2) % 24]
    # deadline respected
    sched2 = ops.Nightshift(_tariff())
    early = ops.Job("quick", watts=100.0, duration_hours=1.0, deadline_hour=6)
    p2 = sched2.schedule(early)
    assert all(h < 6 for h, _ in p2.slices)
    # impossible placement raises honestly
    sched3 = ops.Nightshift(_tariff())
    huge = ops.Job("huge", watts=100.0, duration_hours=30.0, preemptible=True)
    with pytest.raises(ops.ScheduleError):
        sched3.schedule(huge)


# ---------------------------------------------------------------------------
# carbon_scheduler — greenhour shifting
# ---------------------------------------------------------------------------


def _forecast():
    # dirty afternoon, clean night
    return carbon_scheduler.CarbonForecast(
        [500.0] * 6 + [150.0] * 6 + [600.0] * 6 + [120.0] * 6
    )


def test_carbon_shift_avoids_dirty_hours():
    g = carbon_scheduler.Greenhour(_forecast())
    job = carbon_scheduler.ElasticJob(
        "batch", kwh=2.0, earliest_start=0, deadline_hour=24
    )
    shift = g.shift(job)
    hours = [h for h, _ in shift.slices]
    assert all(18 <= h <= 23 for h in hours)  # the 120 g/kWh night window
    assert shift.grams_co2 == pytest.approx(2.0 * 120.0)
    report = g.report([job], [shift])
    assert report["cut_pct"] > 30.0
    assert report["avoided_grams"] > 0


def test_carbon_rigid_job_takes_cleanest_block():
    g = carbon_scheduler.Greenhour(_forecast())
    job = carbon_scheduler.ElasticJob(
        "rigid",
        kwh=2.0,
        earliest_start=0,
        deadline_hour=24,
        pausable=False,
        max_power_kw=1.0,
    )
    shift = g.shift(job)
    hours = [h for h, _ in shift.slices]
    assert hours == sorted(hours)  # contiguous
    assert len(hours) == 2
    # cleanest 2h block is inside the 120 g/kWh night window (hours 18-23)
    assert all(18 <= h <= 23 for h in hours)


def test_carbon_baseline_and_horizon_guard():
    g = carbon_scheduler.Greenhour(_forecast())
    job = carbon_scheduler.ElasticJob("batch", kwh=1.0, earliest_start=0)
    base = g.baseline([job])
    assert base["grams_co2"] == pytest.approx(500.0)  # hour 0 is dirty
    late = carbon_scheduler.ElasticJob(
        "late", kwh=1.0, earliest_start=20, deadline_hour=99
    )
    with pytest.raises(carbon_scheduler.CarbonError):
        g.shift(late)
    with pytest.raises(carbon_scheduler.CarbonError):
        carbon_scheduler.CarbonForecast([])


# ---------------------------------------------------------------------------
# arm_hosts — wattledger
# ---------------------------------------------------------------------------


def test_arm_wattledger_rule_of_thumb():
    ledger = arm_hosts.Wattledger()  # no price -> $1/watt-year rule
    sbc = arm_hosts.Host(
        "sbc", idle_watts=4.0, active_watts=9.0, utilization=0.2, capex_dollars=90.0
    )
    tower = arm_hosts.Host(
        "tower", idle_watts=55.0, active_watts=140.0, utilization=0.2, capex_dollars=0.0
    )
    assert ledger.avg_watts(sbc) == pytest.approx(5.0)
    assert ledger.yearly_energy_cost(sbc) == pytest.approx(5.0)  # $1/watt-year
    assert ledger.yearly_energy_cost(tower) == pytest.approx(72.0)
    ranked = ledger.compare([tower, sbc])
    assert ranked[0][0].name == "sbc"  # 90 + 5*5 = 115 < 72*5 = 360


def test_arm_tco_and_payback():
    ledger = arm_hosts.Wattledger(dollars_per_kwh=0.15)
    sbc = arm_hosts.Host(
        "sbc", idle_watts=4.0, active_watts=9.0, utilization=0.2, capex_dollars=90.0
    )
    tower = arm_hosts.Host(
        "tower", idle_watts=55.0, active_watts=140.0, utilization=0.2
    )
    months = ledger.payback_months(sbc, tower)
    assert months is not None and months < 24  # thirsty tower pays back fast
    # identical hosts never pay back
    assert ledger.payback_months(tower, tower) is None
    report = ledger.report([sbc, tower])
    assert report[0]["tco_dollars"] <= report[1]["tco_dollars"]
    with pytest.raises(arm_hosts.HostError):
        arm_hosts.Host("bad", idle_watts=10.0, active_watts=5.0)


def test_arm_exact_price_path():
    ledger = arm_hosts.Wattledger(dollars_per_kwh=0.12)
    h = arm_hosts.Host("box", idle_watts=10.0, active_watts=10.0, utilization=1.0)
    # 10W * 8.76 kWh/W-yr * $0.12 = $10.512
    assert ledger.yearly_energy_cost(h) == pytest.approx(10.512)
    assert ledger.tco(h, years=2.0) == pytest.approx(21.024)


# ---------------------------------------------------------------------------
# laptop_server — secondlife scoring
# ---------------------------------------------------------------------------


def _laptop(**kw):
    base = dict(
        name="thinkpad",
        age_years=5.0,
        battery=laptop_server.BatteryHealth.GOOD,
        idle_watts=8.0,
        active_watts=25.0,
    )
    base.update(kw)
    return laptop_server.Laptop(**base)


def test_laptop_suitability_scores_and_blockers():
    sl = laptop_server.Secondlife()
    suit = sl.suitability(_laptop())
    assert suit.viable is True
    assert suit.score >= 50
    assert suit.strengths  # reasons are explicit
    swollen = sl.suitability(_laptop(battery=laptop_server.BatteryHealth.SWOLLEN))
    assert swollen.viable is False
    assert any("swollen" in b for b in swollen.blockers)
    bad_disk = sl.suitability(_laptop(storage_healthy=False))
    assert bad_disk.blockers  # suspect storage vetoes regardless of score


def test_laptop_zero_capex_and_energy():
    sl = laptop_server.Secondlife(dollars_per_kwh=0.12)
    lap = _laptop()
    assert sl.CAPEX_DOLLARS == 0.0
    avg = sl.avg_watts(lap)
    assert avg == pytest.approx(8.0 + 17.0 * 0.25)
    assert sl.yearly_energy_cost(lap) == pytest.approx(avg * 8.76 * 0.12)
    cmp = sl.compare_vs_new(lap, new_host_capex=90.0, new_host_avg_watts=5.0)
    assert cmp["laptop_tco_dollars"] < cmp["new_host_tco_dollars"]
    assert cmp["laptop_saves_dollars"] > 0


def test_laptop_setup_plan_includes_blocker_first():
    sl = laptop_server.Secondlife()
    plan = sl.setup_plan(_laptop(battery=laptop_server.BatteryHealth.SWOLLEN))
    assert plan[0]["phase"] == "blocker"
    phases = [s["phase"] for s in plan]
    assert "power" in phases and "data" in phases
    good_plan = sl.setup_plan(_laptop())
    assert good_plan[0]["phase"] != "blocker"
    with pytest.raises(laptop_server.SecondlifeError):
        laptop_server.Laptop(
            name="",
            age_years=1.0,
            battery=laptop_server.BatteryHealth.GOOD,
            idle_watts=5.0,
            active_watts=10.0,
        )
