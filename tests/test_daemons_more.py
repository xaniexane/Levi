"""Tests for the five new worker daemons: gardener, sentinel, courier,
archivist, midwife. Hermetic: every daemon is bound to a tmp home, so the
real ~/.levi is never touched.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from levi.daemon.supervisor import Supervisor

NEW_DAEMONS = {
    "gardener": "levi.daemon.gardener",
    "sentinel": "levi.daemon.sentinel",
    "courier": "levi.daemon.courier",
    "archivist": "levi.daemon.archivist",
    "midwife": "levi.daemon.midwife",
}


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# registry wiring
# ---------------------------------------------------------------------------


def test_supervisor_catalog_lists_new_daemons(tmp_path):
    sup = Supervisor(home=tmp_path)
    by_name = {e["name"]: e for e in sup.list_services()}
    for name, module in NEW_DAEMONS.items():
        assert name in by_name, f"missing service {name}"
        assert by_name[name]["module"] == module
        assert by_name[name]["summary"].strip()
        assert by_name[name]["start_hint"].strip()


def test_new_daemon_health_checks_pass_against_tmp_home(tmp_path):
    sup = Supervisor(home=tmp_path)
    for name in NEW_DAEMONS:
        st = sup.service_status(name)
        assert st["ok"] is True, f"{name} down: {st['detail']}"
        assert st["status"] == "up"


def test_unified_tick_workers_runs_all_five(tmp_path):
    from levi.daemon.unified import UnifiedDaemon, WORKER_DAEMONS

    assert set(WORKER_DAEMONS) == set(NEW_DAEMONS)
    daemon = UnifiedDaemon(path=tmp_path / ".levi")
    results = daemon.tick_workers(home=tmp_path)
    assert set(results) == set(NEW_DAEMONS)
    for name, res in results.items():
        assert res["ok"] is True, f"{name} tick failed: {res}"


# ---------------------------------------------------------------------------
# gardener
# ---------------------------------------------------------------------------


def _write_cache_entry(cache_dir: Path, name: str, expires_at):
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / name).write_text(
        json.dumps({"value": 1, "expires_at": expires_at}), encoding="utf-8"
    )


def test_gardener_prunes_stale_and_rotates_logs(tmp_path):
    from levi.daemon.gardener import Gardener

    cache_dir = tmp_path / ".levi" / "cache"
    log_dir = tmp_path / ".levi" / "logs"
    now = datetime.now(timezone.utc)
    _write_cache_entry(cache_dir, "stale.json", _iso(now - timedelta(hours=1)))
    _write_cache_entry(cache_dir, "fresh.json", _iso(now + timedelta(hours=1)))
    log_dir.mkdir(parents=True, exist_ok=True)
    big = log_dir / "app.log"
    big.write_bytes(b"x" * 500)

    g = Gardener(home=tmp_path, max_log_bytes=100, generations=2)
    report = g.tick()

    assert "stale.json" in report.pruned
    assert (cache_dir / "stale.json").exists() is False
    assert (cache_dir / "fresh.json").exists()  # untouched
    assert "app.log" in report.rotated
    assert big.exists() and big.stat().st_size == 0  # rotated, fresh log started
    gens = list(log_dir.glob("app.log.*"))
    assert len(gens) == 1
    assert report.bytes_reclaimed > 0
    assert report.errors == []


def test_gardener_never_touches_forbidden_dirs(tmp_path):
    from levi.daemon.gardener import Gardener, FORBIDDEN

    memory_dir = tmp_path / ".levi" / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    precious = memory_dir / "keep.json"
    precious.write_text(json.dumps({"value": 1}), encoding="utf-8")

    # Even pointed at a forbidden root, the gardener refuses.
    g = Gardener(home=tmp_path, cache_dir=memory_dir, log_dir=memory_dir)
    report = g.tick()
    assert precious.exists()
    assert report.pruned == [] and report.rotated == []
    assert "memory" in FORBIDDEN


def test_gardener_dry_run_changes_nothing(tmp_path):
    from levi.daemon.gardener import Gardener

    cache_dir = tmp_path / ".levi" / "cache"
    now = datetime.now(timezone.utc)
    _write_cache_entry(cache_dir, "stale.json", _iso(now - timedelta(hours=1)))
    report = Gardener(home=tmp_path).tick(dry_run=True)
    assert "stale.json" in report.pruned
    assert (cache_dir / "stale.json").exists()  # still there


# ---------------------------------------------------------------------------
# sentinel
# ---------------------------------------------------------------------------


def _action_line(**kw):
    base = {
        "id": "a1",
        "at": _iso(datetime.now(timezone.utc)),
        "actor": "test-actor",
        "action": "test-action",
        "risk": "LOW",
        "approved": True,
    }
    base.update(kw)
    return json.dumps(base)


def test_sentinel_raises_on_unapproved_consequential_act(tmp_path):
    from levi.daemon.sentinel import Sentinel

    log_path = tmp_path / ".levi" / "action_log.jsonl"
    journal = tmp_path / ".levi" / "bus.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "\n".join(
            [
                _action_line(id="v1", action="wipe_drive", risk="HIGH", approved=False),
                _action_line(id="ok1", action="read_file", risk="LOW", approved=False),
                _action_line(id="ok2", action="deploy", risk="HIGH", approved=True),
                _action_line(
                    id="v2", action="pay_vendor", risk="MEDIUM", approved=False
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    s = Sentinel(home=tmp_path, journal_path=journal)
    report = s.tick()

    assert report.scanned == 4
    ids = {v.action_id for v in report.violations}
    assert ids == {"v1", "v2"}  # HIGH + MEDIUM unapproved; LOW and approved pass
    # The log itself is untouched (read-only watchdog).
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 4
    # A signal went out on the bus for each violation.
    topics = [
        json.loads(line)["topic"]
        for line in journal.read_text(encoding="utf-8").splitlines()
    ]
    assert topics.count("sentinel.policy_violation") == 2

    # Second tick: watermark holds, nothing re-judged.
    again = s.tick()
    assert again.scanned == 0 and again.violations == []


def test_sentinel_never_blocks_and_handles_missing_log(tmp_path):
    from levi.daemon.sentinel import Sentinel

    s = Sentinel(home=tmp_path, journal_path=tmp_path / ".levi" / "bus.jsonl")
    report = s.tick()  # no action log at all
    assert report.scanned == 0 and report.violations == [] and report.errors == []


# ---------------------------------------------------------------------------
# courier
# ---------------------------------------------------------------------------


def test_courier_delivers_sealed_envelope_with_receipt(tmp_path):
    from levi.daemon.courier import Courier

    c = Courier(home=tmp_path, journal_path=tmp_path / ".levi" / "bus.jsonl")
    env = c.seal("echo", "mandella", {"task": "cross-check this"})
    assert env.verify()
    c.send(env)

    report = c.tick()
    assert report.delivered == [env.id]
    assert report.quarantined == []
    assert report.errors == []

    inbox_file = (
        tmp_path / ".levi" / "courier" / "inbox" / "mandella" / f"{env.id}.json"
    )
    assert inbox_file.exists()
    receipt_file = tmp_path / ".levi" / "courier" / "receipts" / f"{env.id}.json"
    receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
    assert receipt["tampered"] is False and receipt["delivered_at"]

    got = c.collect("mandella")
    assert len(got) == 1 and got[0].payload == {"task": "cross-check this"}
    assert got[0].verify()


def test_courier_quarantines_tampered_envelope(tmp_path):
    from levi.daemon.courier import Courier

    c = Courier(home=tmp_path, journal_path=tmp_path / ".levi" / "bus.jsonl")
    env = c.seal("echo", "reim", {"task": "original"})
    c.send(env)
    # Tamper with the outbox file before delivery.
    outbox_file = tmp_path / ".levi" / "courier" / "outbox" / f"{env.id}.json"
    raw = json.loads(outbox_file.read_text(encoding="utf-8"))
    raw["payload"]["task"] = "forged"
    outbox_file.write_text(json.dumps(raw), encoding="utf-8")

    report = c.tick()
    assert report.delivered == []
    assert report.quarantined == [env.id]
    dead = tmp_path / ".levi" / "courier" / "dead" / f"{env.id}.json"
    assert dead.exists()
    inbox = tmp_path / ".levi" / "courier" / "inbox" / "reim"
    assert not inbox.exists() or list(inbox.glob("*.json")) == []


def test_courier_refuses_to_carry_bad_envelope(tmp_path):
    from levi.daemon.courier import Courier, Envelope

    c = Courier(home=tmp_path)
    bad = Envelope(id="x", sender="a", recipient="b", payload={}, checksum="nope")
    with pytest.raises(ValueError):
        c.send(bad)
    with pytest.raises(ValueError):
        c.seal("", "b", {})


# ---------------------------------------------------------------------------
# archivist
# ---------------------------------------------------------------------------


def test_archivist_snapshots_and_chain_verifies(tmp_path):
    from levi.daemon.archivist import Archivist

    data = tmp_path / "data"
    data.mkdir()
    (data / "note.txt").write_text("hello", encoding="utf-8")

    a = Archivist(home=tmp_path, roots=[data])
    r1 = a.tick()
    assert r1.files == 1 and r1.chain_ok and r1.errors == []
    assert r1.snapshot
    snap_file = tmp_path / ".levi" / "archivist" / "snapshots" / r1.snapshot
    assert snap_file.exists()

    r2 = a.tick()
    assert r2.chain_ok
    ok, detail = a.verify_chain()
    assert ok, detail
    assert "2 receipt(s)" in detail


def test_archivist_detects_tampered_chain(tmp_path):
    from levi.daemon.archivist import Archivist

    data = tmp_path / "data"
    data.mkdir()
    (data / "note.txt").write_text("hello", encoding="utf-8")
    a = Archivist(home=tmp_path, roots=[data])
    a.tick()
    # Corrupt the receipt log.
    receipts = tmp_path / ".levi" / "archivist" / "receipts.jsonl"
    lines = receipts.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["manifest_hash"] = "0" * 64
    receipts.write_text(json.dumps(rec) + "\n", encoding="utf-8")

    ok, detail = a.verify_chain()
    assert ok is False
    assert "broken" in detail


# ---------------------------------------------------------------------------
# midwife
# ---------------------------------------------------------------------------

CATALOG = {
    "agent": {"scout-twin"},
    "specialist": {"research", "memory"},
    "organ": {"echo"},
    "seat": {"field-crew-3"},
}

GOOD_BLUEPRINT = {
    "name": "field-scout-01",
    "parts": {
        "agent": "scout-twin",
        "specialist": ["research", "memory"],
        "organ": ["echo"],
        "seat": "field-crew-3",
    },
}


def test_midwife_accepts_complete_blueprint(tmp_path):
    from levi.daemon.midwife import Midwife

    verdict = Midwife(home=tmp_path, catalog=CATALOG).validate(GOOD_BLUEPRINT)
    assert verdict.ok is True
    assert verdict.missing == [] and verdict.unhealthy == []


def test_midwife_refuses_missing_and_unhealthy_parts(tmp_path):
    from levi.daemon.midwife import Midwife

    bad = {
        "name": "broken-01",
        "parts": {
            "agent": "ghost-agent",
            "specialist": ["research"],
            "organ": ["echo"],
            "seat": "field-crew-3",
            "rocket": ["x"],  # unknown part type
        },
    }
    m = Midwife(home=tmp_path, catalog=CATALOG, health={"research": False})
    verdict = m.validate(bad)
    assert verdict.ok is False
    assert "agent:ghost-agent" in verdict.missing
    assert "specialist:research" in verdict.unhealthy
    assert "rocket" in verdict.unknown_types


def test_midwife_refuses_malformed_blueprint(tmp_path):
    from levi.daemon.midwife import Midwife

    m = Midwife(home=tmp_path, catalog=CATALOG)
    v1 = m.validate({"name": "no-parts"})
    assert v1.ok is False and v1.errors
    v2 = m.validate("not-a-dict")  # type: ignore[arg-type]
    assert v2.ok is False


def test_midwife_tick_judges_pending_blueprints(tmp_path):
    from levi.daemon.midwife import Midwife

    m = Midwife(home=tmp_path, catalog=CATALOG)
    bp_dir = tmp_path / ".levi" / "midwife" / "blueprints"
    bp_dir.mkdir(parents=True)
    (bp_dir / "good.json").write_text(json.dumps(GOOD_BLUEPRINT), encoding="utf-8")
    (bp_dir / "bad.json").write_text(
        json.dumps({"name": "bad", "parts": {"agent": "ghost"}}), encoding="utf-8"
    )

    report = m.tick()
    assert report["judged"] == 2
    assert report["accepted"] == 1
    assert report["refused"] == 1
    verdicts = tmp_path / ".levi" / "midwife" / "verdicts"
    assert (verdicts / "field-scout-01.json").exists()
    bad_verdict = json.loads((verdicts / "bad.json").read_text(encoding="utf-8"))
    assert bad_verdict["ok"] is False


def test_midwife_fails_closed_without_catalog(tmp_path):
    from levi.daemon.midwife import Midwife

    # No catalog injected and registries unavailable against tmp home:
    # unknown parts must refuse, never pass.
    m = Midwife(
        home=tmp_path,
        catalog={t: set() for t in ("agent", "specialist", "organ", "seat")},
    )
    verdict = m.validate(GOOD_BLUEPRINT)
    assert verdict.ok is False
    assert verdict.missing  # everything unknown -> refused
