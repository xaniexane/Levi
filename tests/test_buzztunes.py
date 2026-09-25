"""Tests for Buzz Tunes — levi.buzztunes.

Laws under test:
  L1 provider-universal: engine runs on fake AND local providers;
      grep-gate: no provider SDK imports in the module tree.
  L2 clean-room: provenance declared; no GPL/target-derived code markers.
  L3 honest receipts: every action emits a receipt to the append-only log.
  L4 money 70/30 fail-closed: split math; charge plans through
      levi.cybrus.money.MoneyGateway and raises for human approval
      (nothing moves without it); approved charge executes through the
      gateway and fails closed with no rail/plug-in; the module holds
      no rails of its own.
  L5 thread surface: agents reach queues only via ListeningThread;
      the engine exposes no agent-inject backdoor.
Plus: M3U round-trip / EXTINF metadata / malformed tolerance;
  stack check (all WIRED imports resolve); KFX2 four phases + receipts;
  demand scores from real signals; curator pool x10 + genome learning;
  thread journey round against the real EchoverseEngine; CLI smoke.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from levi.buzztunes import engine as E
from levi.buzztunes import m3u as M
from levi.buzztunes import money as MO
from levi.buzztunes import providers as P
from levi.buzztunes import stack as S
from levi.buzztunes import threads as T
from levi.buzztunes.cli import cmd_buzztunes
from levi.buzztunes.curation import curate, PHASES
from levi.buzztunes.demand import DemandLog, demand_score
from levi.buzztunes.receipts import ReceiptLog

MODULE_DIR = Path(__file__).resolve().parent.parent / "core" / "levi" / "buzztunes"

BANNED_IMPORTS = ("yt_dlp", "pytube", "googleapiclient", "spotipy",
                  "requests", "aiohttp", "urllib3")


def _engine(tmp_path) -> E.BuzzEngine:
    return E.BuzzEngine(tmp_path / "store")


# ---------------------------------------------------------------- L1

def test_l1_engine_runs_on_fake_and_local(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "Nova Ray - Static Bloom.mp3").write_bytes(b"fake-audio")
    (lib / "notes.txt").write_bytes(b"not audio")
    reg = P.ProviderRegistry()
    reg.register(P.FakeProvider())
    reg.register(P.LocalFileProvider(lib))
    eng = E.BuzzEngine(tmp_path / "s1", registry=reg)

    fake_hits = reg.get("fake").search("frequencies")
    assert fake_hits and all(t.provider == "fake" for t in fake_hits)
    local_hits = reg.get("local").search("static")
    assert len(local_hits) == 1
    assert local_hits[0].artist == "Nova Ray"
    assert local_hits[0].title == "Static Bloom"

    eng.queue_add(fake_hits[0])
    eng.queue_add(local_hits[0])
    assert len(eng.queue_list()) == 2
    res = eng.play(fake_hits[0].id)
    assert res["now_playing"]["id"] == fake_hits[0].id


def test_l1_grep_gate_no_provider_sdks():
    for path in MODULE_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for banned in BANNED_IMPORTS:
            assert banned not in text, f"{path.name} mentions {banned}"


def test_l1_unknown_provider_refuses(tmp_path):
    eng = _engine(tmp_path)
    with pytest.raises(KeyError):
        eng.registry.get("youtube")


# ---------------------------------------------------------------- L2

def test_l2_clean_room_provenance():
    import levi.buzztunes as pkg
    doc = pkg.__doc__
    assert "clean-room" in doc.lower()
    assert "no Metrolist code" in doc
    assert "no Bloome code" in doc
    assert "GPL" in doc


# ---------------------------------------------------------------- L3

def test_l3_every_action_emits_receipt(tmp_path):
    eng = _engine(tmp_path)
    track = P.FakeProvider().resolve("fake:001")
    eng.queue_add(track)
    eng.play(track.id)
    eng.skip(track.id)
    eng.complete("fake:002")
    eng.curate("static")
    actions = [r["action"] for r in eng.receipts.read_all()]
    assert "queue.add" in actions
    assert "play" in actions
    assert "skip" in actions
    assert "complete" in actions
    assert "kfx2.absorb" in actions and "kfx2.return" in actions
    assert all(r["receipt_id"].startswith("bt-") for r in eng.receipts.read_all())


def test_l3_receipt_log_append_only(tmp_path):
    log = ReceiptLog(tmp_path)
    log.emit("a")
    log.emit("b")
    assert log.count() == 2
    assert [r["action"] for r in log.read_all()] == ["a", "b"]


# ---------------------------------------------------------------- L4

def test_l4_split_70_30():
    assert MO.split_70_30(100) == {"creator_cents": 70, "platform_cents": 30,
                                   "total_cents": 100}
    assert MO.split_70_30(1) == {"creator_cents": 0, "platform_cents": 1,
                                 "total_cents": 1}
    assert MO.split_70_30(0)["total_cents"] == 0
    with pytest.raises(ValueError):
        MO.split_70_30(-5)


def test_l4_charge_plans_and_raises_for_approval(tmp_path, monkeypatch):
    """No approval -> MoneyApprovalRequired, nothing moves (gateway-routed)."""
    from levi.cybrus.money import MoneyApprovalRequired, MoneyGateway

    monkeypatch.setenv("LEVI_CYBRUS_DIR", str(tmp_path / "cybrus"))
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    with pytest.raises(MoneyApprovalRequired) as excinfo:
        MO.charge("cust-1", 500, memo="album", identity="cust-1")
    assert excinfo.value.approval_id
    # planned and approval requested — never executed
    events = [e["event"] for e in MoneyGateway().audit_log(limit=200)]
    assert "planned" in events
    assert "approval_requested" in events
    assert "execute_refused" not in events


def test_l4_charge_purpose_carries_70_30_split(tmp_path, monkeypatch):
    """The 70/30 split rides along as plan metadata for the approver."""
    from levi.cybrus.money import MoneyApprovalRequired, MoneyGateway

    monkeypatch.setenv("LEVI_CYBRUS_DIR", str(tmp_path / "cybrus"))
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    with pytest.raises(MoneyApprovalRequired) as excinfo:
        MO.charge("cust-9", 1000, memo="album", identity="cust-9")
    plan = MoneyGateway().plan_from_approval(
        excinfo.value.approval_id, expected_operation="charge"
    )
    assert "creator=700" in plan.purpose
    assert "platform=300" in plan.purpose


def test_l4_charge_full_ceremony_fails_closed(tmp_path, monkeypatch):
    """Approved approval + no rail/plug-in -> NoRailConfigured; consumed."""
    from levi.cybrus.approval import ApprovalEngine
    from levi.cybrus.money import (
        MoneyApprovalRequired,
        MoneyRefused,
        NoRailConfigured,
    )

    monkeypatch.setenv("LEVI_CYBRUS_DIR", str(tmp_path / "cybrus"))
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    try:
        MO.charge("cust-9", 1000, memo="album", identity="cust-9")
    except MoneyApprovalRequired as req:
        approval_id = req.approval_id
    else:  # pragma: no cover - the raise is the contract
        pytest.fail("charge without approval_id must raise MoneyApprovalRequired")
    ApprovalEngine().approve(approval_id, by="chauncey")
    # honest boundary: no rail registered, no payment plug-in wired
    with pytest.raises(NoRailConfigured):
        MO.charge(
            "cust-9",
            1000,
            memo="album",
            identity="cust-9",
            approval_id=approval_id,
        )
    # the approval was consumed atomically: a replay is refused
    with pytest.raises(MoneyRefused):
        MO.charge(
            "cust-9",
            1000,
            memo="album",
            identity="cust-9",
            approval_id=approval_id,
        )


def test_l4_module_holds_no_rails():
    """The module is a gateway adapter: no private rail state may exist."""
    assert not hasattr(MO, "register_rail")
    assert not hasattr(MO, "MoneyRail")
    assert not hasattr(MO, "_rail")
    st = MO.rail_status()
    assert st["mode"] == "paper-only"
    assert st["via"] == "cybrus"
    assert st["law"] == "Cybrus alone handles money."


# ---------------------------------------------------------------- L5

def test_l5_no_agent_backdoor_on_engine(tmp_path):
    eng = _engine(tmp_path)
    assert not hasattr(eng, "agent_inject")
    assert not hasattr(eng, "agent_curate")


def test_l5_thread_is_the_surface(tmp_path):
    eng = _engine(tmp_path)
    store = T.ThreadStore(eng, tmp_path / "threads")
    th = store.create("late night")
    th.join("chauncey")
    tracks = P.FakeProvider().search("", limit=3)
    r = th.add_curation("Quetta-Pan¹", tracks)
    assert r["action"] == "thread.curate"
    assert len(th.shared_queue()) == 3
    assert th.members == ["chauncey"]


# ---------------------------------------------------------------- M3U

SAMPLE_M3U = """#EXTM3U
#EXTINF:187,The Frequencies - Midnight Static
/home/music/midnight_static.mp3
#EXTINF:-1,Night Cartographer - Low Orbit Lullaby
./low_orbit.mp3
#EXTINF:badline
/home/music/broken.mp3
#EXTINF:200,Missing Comma
# some comment
https://example.com/stream/signal-bloom.mp3

garbage without extinf
"""


def test_m3u_parse_extinf_and_paths(tmp_path):
    parsed = M.parse_m3u(SAMPLE_M3U, base_dir="/home/music")
    assert len(parsed) == 5  # bad EXTINF skipped, but its media line still plays
    t0 = parsed.tracks[0]
    assert t0.title == "Midnight Static"
    assert t0.artist == "The Frequencies"
    assert t0.duration == 187.0
    assert t0.ref == "/home/music/midnight_static.mp3"
    t1 = parsed.tracks[1]
    assert t1.duration is None  # -1 -> unknown
    assert t1.ref == "/home/music/low_orbit.mp3"  # relative resolved
    t2 = parsed.tracks[2]
    assert t2.ref == "/home/music/broken.mp3"
    assert t2.duration is None  # orphaned by the bad EXTINF above it
    assert t2.title == "broken"
    t3 = parsed.tracks[3]
    assert t3.provider == "url"
    assert t3.ref.startswith("https://")
    assert "signal-bloom" in t3.title


def test_m3u_malformed_tolerance():
    parsed = M.parse_m3u(SAMPLE_M3U)
    reasons = [s["reason"] for s in parsed.skipped]
    assert any("comma" in r for r in reasons)  # bad EXTINF line
    assert any("directive" in r for r in reasons)  # stray comment
    assert len(parsed.tracks) == 5  # parse survived


def test_m3u_round_trip(tmp_path):
    tracks = P.FakeProvider().search("", limit=4)
    text = M.write_m3u(tracks)
    assert text.startswith("#EXTM3U")
    parsed = M.parse_m3u(text)
    assert len(parsed) == 4
    for orig, back in zip(tracks, parsed.tracks):
        assert back.title == orig.title
        assert back.artist == orig.artist
        assert back.duration == orig.duration
        assert back.ref == orig.ref


def test_m3u8_bom(tmp_path):
    p = tmp_path / "list.m3u8"
    p.write_bytes(b"\xef\xbb\xbf#EXTM3U\n#EXTINF:10,A - B\nsong.mp3\n")
    parsed = M.read_playlist(p)
    assert len(parsed) == 1
    assert parsed.tracks[0].title == "B"


def test_engine_m3u_import_export(tmp_path):
    eng = _engine(tmp_path)
    pl = tmp_path / "in.m3u"
    pl.write_text(SAMPLE_M3U, encoding="utf-8")
    res = eng.import_m3u(pl)
    assert len(res["parsed"]) == 5
    out = tmp_path / "out.m3u"
    r = eng.export_m3u(out)
    assert r["details"]["tracks"] == 5
    back = M.read_playlist(out)
    assert len(back) == 5


# ---------------------------------------------------------------- stack

def test_stack_all_wired_resolve():
    report = S.check_stack()
    wired = [r for r in report if r["status"] == "WIRED"]
    assert len(wired) == 5  # REIM RIEM Echo Mandella Echoverse
    for row in wired:
        assert row["check"] == "ok", f"{row['component']}: {row['check']}"
    missing = [r for r in report if r["status"] == "MISSING"]
    assert any("playback" in r["component"].lower() for r in missing)
    assert any("provider" in r["component"].lower() for r in missing)


def test_stack_curator_pool_x10(tmp_path):
    pool = S.CuratorPool(tmp_path / "cur")
    assert len(pool) == 10
    assert pool.names()[0] == "Quetta-Pan¹"
    assert pool.names()[9] == "Quetta-Pan¹⁰"
    assert len(set(pool.names())) == 10


def test_stack_genome_suppresses_repeat_failures(tmp_path):
    pool = S.CuratorPool(tmp_path / "cur2")
    c = pool.get(0)
    assert c.consult("pick-x", "curation") == "unknown"
    c.learn("pick-x", "curation", success=False, tried_what="queued pick-x")
    c.learn("pick-x", "curation", success=False, tried_what="queued pick-x")
    assert c.consult("pick-x", "curation") == "suppress"
    assert c.compost.count() >= 2


def test_stack_echo_and_mandella_real(tmp_path):
    pool = S.CuratorPool(tmp_path / "cur3")
    c = pool.get(2)
    echo_res = c.explore_variants("midnight static", cycles=1)
    assert isinstance(echo_res, dict)
    stake = c.stake("curate midnight static")
    assert "recommended" in stake or "options" in stake or isinstance(stake, dict)


# ---------------------------------------------------------------- KFX2 + demand

def test_kfx2_four_phases_with_receipts(tmp_path):
    log = DemandLog(tmp_path / "d")
    receipts = ReceiptLog(tmp_path / "r")
    tracks = P.FakeProvider().search("", limit=6)
    log.record("play", "fake:001")
    log.record("skip", "fake:002")
    res = curate(tracks, seed="night drive", demand_log=log,
                 receipts=receipts)
    assert len(res["queue"]) == len(tracks)
    assert res["queue"][0].meta["kfx2_fingerprint"]
    actions = [r["action"] for r in receipts.read_all()]
    for phase in PHASES:
        assert f"kfx2.{phase}" in actions
    # skipped track ranks below played track
    order = [t.id for t in res["queue"]]
    assert order.index("fake:001") < order.index("fake:002")


def test_demand_scores_from_real_signals_only(tmp_path):
    log = DemandLog(tmp_path)
    assert demand_score("fake:001", log.events()) == 0.0
    log.record("play", "fake:001")
    log.record("complete", "fake:001")
    log.record("skip", "fake:002")
    assert demand_score("fake:001", log.events()) == 2.0
    assert demand_score("fake:002", log.events()) == -2.0


# ---------------------------------------------------------------- threads + journey

def test_thread_journey_round_real_echoverse(tmp_path):
    eng = _engine(tmp_path)
    store = T.ThreadStore(eng, tmp_path / "t")
    th = store.create("drive")
    res = th.journey_round("night drive synths")
    assert len(res.get("optionalPaths", [])) > 0
    th.journey_skip("too slow", note="dragged the vibe")
    assert th.journey.status()["vault"] >= 1


# ---------------------------------------------------------------- CLI

def test_cli_smoke(tmp_path, capsys):
    import argparse
    args = argparse.Namespace(store=str(tmp_path / "cli"), buzztunes_cmd="providers")
    assert cmd_buzztunes(args) == 0
    out = capsys.readouterr().out
    assert "fake" in out

    args = argparse.Namespace(store=str(tmp_path / "cli"),
                              buzztunes_cmd="curate", query="static",
                              provider="fake", curator=0)
    assert cmd_buzztunes(args) == 0
    out = capsys.readouterr().out
    assert "curation" in out

    args = argparse.Namespace(store=str(tmp_path / "cli"),
                              buzztunes_cmd="stack")
    assert cmd_buzztunes(args) == 0
    assert "WIRED" in capsys.readouterr().out

    args = argparse.Namespace(store=str(tmp_path / "cli"),
                              buzztunes_cmd="laws")
    assert cmd_buzztunes(args) == 0
    assert "L1" in capsys.readouterr().out
