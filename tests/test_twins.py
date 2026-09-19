"""Tests for the Twin Lattice (SER-21 twin architecture)."""

import json
import os
import time

import pytest

from levi.twins import agents as twin_agents
from levi.twins import daemons as twin_daemons
from levi.twins import shells as twin_shells
from levi.twins.lattice import TwinLattice
from levi.twins.twin import Twin, twin_id_for


@pytest.fixture
def lat(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_TWINS_HOME", str(tmp_path / "twins"))
    return TwinLattice()


def test_twin_id_format():
    assert twin_id_for("agent", "echo", "fg") == "agent:echo:fg"
    with pytest.raises(ValueError):
        twin_id_for("nope", "echo", "fg")
    with pytest.raises(ValueError):
        twin_id_for("agent", "echo", "sideways")


def test_register_and_heartbeat_roundtrip(lat):
    tw = lat.register("agent", "echo", "fg", state={"load": 0.5})
    assert tw.pair_id == "agent:echo:bg"
    time.sleep(0.01)
    lat.heartbeat(tw.twin_id, {"load": 0.9})
    again = lat.get(tw.twin_id)
    assert again.state["load"] == 0.9
    assert again.age_since_heartbeat() < 5


def test_register_idempotent(lat):
    a = lat.register("agent", "echo", "fg")
    b = lat.register("agent", "echo", "fg", state={"x": 1})
    assert a.twin_id == b.twin_id
    assert lat.get(a.twin_id).state["x"] == 1
    assert len(lat.list()) == 1


def test_ensure_pair(lat):
    pair = lat.ensure_pair("daemon", "levi-daemon")
    assert {t.side for t in pair} == {"fg", "bg"}
    assert lat.ensure_pair("daemon", "levi-daemon") is not None
    assert len(lat.list(kind="daemon")) == 2


def test_stale_detection(lat):
    tw = lat.register("agent", "kai", "fg")
    assert not lat.stale(60)
    tw.last_heartbeat = time.time() - 120
    assert [t.twin_id for t in lat.stale(60)] == [tw.twin_id]


def test_promote_refuses_fresh_fg(lat):
    lat.ensure_pair("agent", "kai")
    with pytest.raises(ValueError):
        lat.promote("agent:kai:bg", 300.0)


def test_promote_swaps_on_stale_fg(lat):
    lat.ensure_pair("agent", "kai")
    fg = lat.get("agent:kai:fg")
    fg.last_heartbeat = time.time() - 600
    lat.heartbeat("agent:kai:bg", {"shadowing": True})
    ev = lat.promote("agent:kai:bg", 300.0)
    assert ev["promoted"] == "agent:kai:fg"
    assert ev["demoted"] == "agent:kai:bg"
    new_fg = lat.get("agent:kai:fg")
    assert new_fg.side == "fg"
    assert new_fg.state["shadowing"] is True
    assert new_fg.promoted_at is not None
    new_bg = lat.get("agent:kai:bg")
    assert new_bg.side == "bg"


def test_promote_refuses_stale_bg(lat):
    lat.ensure_pair("agent", "kai")
    for tid in ("agent:kai:fg", "agent:kai:bg"):
        lat.get(tid).last_heartbeat = time.time() - 600
    with pytest.raises(ValueError):
        lat.promote("agent:kai:bg", 300.0)


def test_check_failover_auto(lat):
    lat.ensure_pair("daemon", "d1")
    lat.get("daemon:d1:fg").last_heartbeat = time.time() - 600
    lat.heartbeat("daemon:d1:bg")
    ev = lat.check_failover("daemon", "d1", 300.0)
    assert ev is not None and ev["promoted"] == "daemon:d1:fg"


def test_check_failover_noop_when_healthy(lat):
    lat.ensure_pair("daemon", "d1")
    assert lat.check_failover("daemon", "d1", 300.0) is None


def test_persistence_across_instances(tmp_path, monkeypatch):
    home = str(tmp_path / "twins")
    monkeypatch.setenv("LEVI_TWINS_HOME", home)
    a = TwinLattice()
    a.register("agent", "echo", "fg", state={"load": 0.2})
    b = TwinLattice()
    tw = b.get("agent:echo:fg")
    assert tw is not None and tw.state["load"] == 0.2


def test_agent_twins_swarm(lat):
    out = twin_agents.ensure_agent_twins(lat)
    assert set(out) == set(twin_agents.SWARM)
    assert len(lat.list(kind="agent")) == 2 * len(twin_agents.SWARM)


def test_dispatch_candidates_sorted(lat):
    twin_agents.ensure_agent_twins(lat)
    for name in twin_agents.SWARM:
        twin_agents.agent_status(lat, name, "idle", load=0.5)
    twin_agents.agent_status(lat, "echo", "busy", load=0.9)
    twin_agents.agent_status(lat, "kai", "idle", load=0.1)
    cands = twin_agents.dispatch_candidates(lat)
    assert cands[0].subject == "kai"
    assert cands[-1].subject == "echo"


def test_daemon_twins(lat):
    pair = twin_daemons.ensure_daemon_twins(lat)
    assert len(pair) == 2
    twin_daemons.daemon_pulse(lat, state_update={"mode": "watch"})
    assert lat.get("daemon:levi-daemon:fg").state["mode"] == "watch"


def test_six_shells_three_pairs(lat):
    out = twin_shells.ensure_shell_twins(lat)
    assert len(out) == twin_shells.SHELL_SLOTS == 6
    assert twin_shells.SHELL_PAIRS == ((0, 1), (2, 3), (4, 5))
    for fg_slot, bg_slot in twin_shells.SHELL_PAIRS:
        fg = lat.get(f"shell:shell-{fg_slot}:fg")
        bg = lat.get(f"shell:shell-{bg_slot}:bg")
        assert fg is not None and bg is not None
        assert fg.pair_id == bg.twin_id
        assert bg.pair_id == fg.twin_id


def test_shell_report_and_history_bound(lat):
    twin_shells.ensure_shell_twins(lat)
    for i in range(30):
        twin_shells.shell_report(lat, 0, cwd="/tmp", last_cmd=f"cmd{i}")
    tw = lat.get("shell:shell-0:fg")
    assert tw.state["cwd"] == "/tmp"
    assert len(tw.state["history"]) == twin_shells.HISTORY_KEEP
    assert tw.state["history"][-1] == "cmd29"


def test_shell_report_bad_slot(lat):
    with pytest.raises(ValueError):
        twin_shells.shell_report(lat, 6)


def test_shell_failover(lat):
    twin_shells.ensure_shell_twins(lat)
    lat.get("shell:shell-0:fg").last_heartbeat = time.time() - 600
    lat.heartbeat("shell:shell-1:bg")
    ev = twin_shells.check_shell_failover(lat, 0, 300.0)
    assert ev is not None
    assert ev["promoted"] == "shell:shell-0:fg"
    assert lat.get("shell:shell-0:fg").side == "fg"


def test_collect_drops(lat):
    twin_shells.ensure_shell_twins(lat)
    d = twin_shells.drops_dir(lat)
    with open(os.path.join(d, "shell-2.json"), "w") as fh:
        json.dump({"slot": 2, "cwd": "/home/x", "last_cmd": "ls", "jobs": []}, fh)
    n = twin_shells.collect_drops(lat)
    assert n == 1
    tw = lat.get("shell:shell-2:fg")
    assert tw.state["cwd"] == "/home/x"
    assert not os.path.exists(os.path.join(d, "shell-2.json"))


def test_hook_script_mentions_slot():
    script = twin_shells.hook_script(3)
    assert "shell-3" in script
    assert "PROMPT_COMMAND" in script
    with pytest.raises(ValueError):
        twin_shells.hook_script(9)


def test_counts(lat):
    twin_agents.ensure_agent_twins(lat)
    twin_daemons.ensure_daemon_twins(lat)
    twin_shells.ensure_shell_twins(lat)
    counts = lat.counts()
    assert counts["agent"] == 2 * len(twin_agents.SWARM)
    assert counts["daemon"] == 2
    assert counts["shell"] == 6


def test_twin_serialization():
    tw = Twin(
        twin_id="agent:echo:fg",
        kind="agent",
        subject="echo",
        side="fg",
        pair_id="agent:echo:bg",
        state={"load": 1.0},
        notes="hi",
    )
    back = Twin.from_dict(json.loads(json.dumps(tw.to_dict())))
    assert back.twin_id == tw.twin_id
    assert back.state == {"load": 1.0}
    assert back.notes == "hi"


# -- triads ------------------------------------------------------------
def test_triads_bind_all_agents(lat):
    from levi.twins import triads as twin_triads

    out = twin_triads.ensure_triads(lat)
    assert set(out) == set(twin_agents.SWARM)
    for agent, parts in out.items():
        assert len(parts["agent"]) == 2
        assert len(parts["daemon"]) == 2
        assert len(parts["shell"]) == 2
        for tw in parts["daemon"]:
            assert tw.state["bound_agent"] == agent
        for tw in parts["shell"]:
            assert tw.state["bound_agent"] == agent
            assert tw.state["os"] is True


def test_triad_subjects(lat):
    from levi.twins import triads as twin_triads

    twin_triads.ensure_triads(lat)
    triad = twin_triads.get_triad(lat, "echo")
    assert {t.subject for t in triad["daemon"]} == {"echo-daemon"}
    assert {t.subject for t in triad["shell"]} == {"os-echo"}


def test_triads_idempotent(lat):
    from levi.twins import triads as twin_triads

    twin_triads.ensure_triads(lat)
    before = len(lat.list())
    twin_triads.ensure_triads(lat)
    assert len(lat.list()) == before


# -- convergence: the three Ones ----------------------------------------
def test_ones_self_paired(lat):
    from levi.twins import convergence as conv

    ones = conv.ensure_ones(lat)
    assert set(ones) == {"agent", "daemon", "shell"}
    for kind, tw in ones.items():
        assert tw.twin_id == f"one:{kind}:fg"
        assert tw.pair_id == tw.twin_id  # the One pairs with itself


def test_seed_stable_and_private(lat, tmp_path):
    from levi.twins import convergence as conv

    s1 = conv.ensure_seed(lat)
    s2 = conv.ensure_seed(lat)
    assert s1 == s2 and len(s1) == 64
    mode = oct(os.stat(conv.seed_path(lat)).st_mode & 0o777)
    assert mode == "0o600"


def test_camouflage_deterministic():
    from levi.twins import convergence as conv

    members = [f"agent:{a}:fg" for a in ("echo", "kai", "titan")]
    m1 = conv.derive_camouflage("ab" * 32, members)
    m2 = conv.derive_camouflage("ab" * 32, members)
    m3 = conv.derive_camouflage("cd" * 32, members)
    assert m1 == m2
    assert m1["order"] != m3["order"]
    assert set(m1["order"]) == set(members)
    assert set(m1["roles"]) == set(members)
    assert set(m1["roles"].values()) <= {"live", "shadow"}


def test_seal_and_verify(lat):
    from levi.twins import convergence as conv

    twin_triads_ensure(lat)
    conv.seal_camouflage(lat)
    assert conv.verify_camouflage(lat) is True
    # tamper with the stored map -> seal breaks
    tw = lat.get("seal:camouflage:fg")
    tw.state["map"]["roles"] = {"forged": "live"}
    assert conv.verify_camouflage(lat) is False
    # wrong seed -> seal breaks
    assert conv.verify_camouflage(lat, "ff" * 32) is False


def test_converge_attaches_members(lat):
    from levi.twins import convergence as conv

    twin_triads_ensure(lat)
    result = conv.converge(lat)
    assert result["sealed"] is True
    assert result["member_counts"]["agent"] == 2 * len(twin_agents.SWARM)
    # every agent twin converges into the One Agent
    one = lat.get("one:agent:fg")
    assert set(one.state["members"]) == {t.twin_id for t in lat.list(kind="agent")}


def twin_triads_ensure(lat):
    from levi.twins import triads as twin_triads

    return twin_triads.ensure_triads(lat)


# -- outward infinity ---------------------------------------------------
def test_register_agent_joins_swarm(lat):
    from levi.twins import triads as twin_triads

    triad = twin_triads.register_agent(lat, "Nova")
    assert len(triad["agent"]) == 2
    assert {t.subject for t in triad["daemon"]} == {"nova-daemon"}
    assert {t.subject for t in triad["shell"]} == {"os-nova"}
    with pytest.raises(ValueError):
        twin_triads.register_agent(lat, "   ")


def test_external_shell_lifecycle(lat):
    pair = twin_shells.ensure_external_shell(lat, "termux-1234")
    assert {t.side for t in pair} == {"fg", "bg"}
    assert pair[0].subject == "ext-termux-1234"
    tw = twin_shells.shell_report_external(
        lat, "termux-1234", cwd="/data", last_cmd="ls"
    )
    assert tw.state["cwd"] == "/data"
    assert tw.state["history"] == ["ls"]
    assert tw.state["external"] is True


def test_collect_external_drops(lat):
    d = twin_shells.drops_dir(lat)
    with open(os.path.join(d, "ext-phone-999.json"), "w") as fh:
        json.dump(
            {"ext_id": "phone-999", "cwd": "/sdcard", "last_cmd": "pwd", "jobs": []}, fh
        )
    assert twin_shells.collect_drops(lat) == 1
    tw = lat.get("shell:ext-phone-999:fg")
    assert tw is not None and tw.state["cwd"] == "/sdcard"


def test_prune_external_only(lat):
    twin_shells.ensure_shell_twins(lat)  # fleet must survive
    twin_shells.ensure_external_shell(lat, "old-shell")
    old = time.time() - 30 * 86400
    for tid in ("shell:ext-old-shell:fg", "shell:ext-old-shell:bg"):
        lat.get(tid).last_heartbeat = old
    n = twin_shells.prune_external(lat, 7 * 86400)
    assert n == 2
    assert lat.get("shell:ext-old-shell:fg") is None
    # fleet untouched
    assert lat.get("shell:shell-0:fg") is not None


def test_lattice_remove(lat):
    lat.register("agent", "echo", "fg")
    assert lat.remove("agent:echo:fg") is True
    assert lat.remove("agent:echo:fg") is False
    assert lat.get("agent:echo:fg") is None


def test_hook_auto_script():
    script = twin_shells.hook_script_auto()
    assert "ext-" in script
    assert "PROMPT_COMMAND" in script
    assert "HOSTNAME" in script


def test_verify_never_crashes_on_bad_seed(lat, tmp_path):
    from levi.twins import convergence as conv

    twin_triads_ensure(lat)
    conv.converge(lat)
    assert conv.verify_camouflage(lat) is True
    # binary garbage seed -> False, not UnicodeDecodeError
    with open(conv.seed_path(lat), "wb") as fh:
        fh.write(b"\xcd\xff\x00garbage")
    assert conv.verify_camouflage(lat) is False
    # non-hex text seed -> False, not ValueError
    with open(conv.seed_path(lat), "w") as fh:
        fh.write("not-hex-at-all")
    assert conv.verify_camouflage(lat) is False
    # corrupt seed file -> ensure_seed raises, never mints a second truth
    with pytest.raises(RuntimeError):
        conv.ensure_seed(lat)


def test_verify_catches_stale_members(lat):
    from levi.twins import convergence as conv
    from levi.twins import triads as twin_triads

    twin_triads_ensure(lat)
    conv.converge(lat)
    assert conv.verify_camouflage(lat) is True
    # a new twin joins without re-converging -> arrangement is stale
    twin_triads.register_agent(lat, "nova")
    assert conv.verify_camouflage(lat) is False
    # re-converge re-seals the new truth
    conv.converge(lat)
    assert conv.verify_camouflage(lat) is True


def test_converge_deterministic_seal(lat):
    from levi.twins import convergence as conv

    twin_triads_ensure(lat)
    conv.converge(lat)
    tag1 = lat.get("seal:camouflage:fg").state["hmac"]
    conv.converge(lat)
    tag2 = lat.get("seal:camouflage:fg").state["hmac"]
    assert tag1 == tag2


# -- evolution: Mandella + Echo, the defense mechanism --------------------
def _converged(lat):
    from levi.twins import convergence as conv
    from levi.twins import triads as twin_triads

    twin_triads.ensure_triads(lat)
    conv.converge(lat)
    return conv


def test_evolve_refuses_when_not_adding_up(lat):
    from levi.twins import evolution as evo

    _converged(lat)
    tw = lat.get("seal:camouflage:fg")
    tw.state["map"]["roles"] = {"forged": "live"}
    with pytest.raises(evo.LatticeDoesNotAddUp):
        evo.evolve(lat)
    with pytest.raises(ValueError):
        evo.evolve(lat, ops=("dance",))


def test_evolve_full_pipeline(lat):
    from levi.twins import evolution as evo

    _converged(lat)
    report = evo.evolve(lat)
    assert [r["op"] for r in report["ops"]] == ["mutate", "transform", "upgrade"]
    assert report["generation"] > 0
    assert report["sealed"] is True
    assert report["version"] == 1
    ledger = lat.get("evolution:ledger:fg")
    assert len(ledger.state["history"]) == 3
    # transform actually rotated pairs
    assert any(
        e["op"] == "transform" and e["detail"].startswith("rotated ")
        for e in ledger.state["history"]
    )


def test_evolve_deterministic_defense(tmp_path, monkeypatch):
    """Same creator seed + same ops = same skin. The defense is
    reproducible by the creator, and only by the creator."""
    from levi.twins import convergence as conv
    from levi.twins import evolution as evo
    from levi.twins import triads as twin_triads

    tags = []
    for i in (1, 2):
        monkeypatch.setenv("LEVI_TWINS_HOME", str(tmp_path / f"a{i}"))
        lat = TwinLattice()
        with open(conv.seed_path(lat), "w") as fh:
            fh.write("ab" * 32)
        twin_triads.ensure_triads(lat)
        conv.converge(lat)
        evo.evolve(lat, ops=("mutate", "transform"))
        tags.append(lat.get("seal:camouflage:fg").state["hmac"])
    assert tags[0] == tags[1]


def test_riem_promotes_on_second_shedding(lat):
    from levi.twins import evolution as evo

    _converged(lat)
    first = evo.evolve(lat, ops=("mutate",))
    assert first["proposals"] == 0  # composted, not yet corroborated
    second = evo.evolve(lat, ops=("mutate",))
    assert second["proposals"] > 0  # corroboration=2 -> genome proposal
    ledger = lat.get("evolution:ledger:fg")
    kinds = {p["kind"] for p in ledger.state["genome_proposals"]}
    assert kinds <= {"guard-rule", "checklist-item", "procedural-memory"}
    assert all(p["applied"] is False for p in ledger.state["genome_proposals"])


def test_rotate_swaps_roles(lat):
    _converged(lat)
    before = lat.get("agent:echo:fg")
    assert before.side == "fg"
    event = lat.rotate("agent:echo:fg")
    after_fg = lat.get("agent:echo:fg")
    after_bg = lat.get("agent:echo:bg")
    assert after_fg.side == "fg" and after_bg.side == "bg"
    assert after_fg.rotated_at is not None
    assert event["now_fg"] == "agent:echo:fg"
    # the twin now holding the fg id is the one that was bg
    assert after_fg.pair_id == "agent:echo:bg"
