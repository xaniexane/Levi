"""Tests for the telegraph office (store-and-forward, identity, directory).

Hermetic: every test runs with an isolated LEVI_HOME in tmp_path.
"""

from __future__ import annotations


import pytest

from levi.telegraph import envelopes, identity, directory


@pytest.fixture()
def home(tmp_path, monkeypatch):
    h = tmp_path / "levi-home"
    h.mkdir()
    monkeypatch.setenv("LEVI_HOME", str(h))
    return h


# ---------------------------------------------------------------- envelopes


def test_seal_and_poll_roundtrip(home):
    env = envelopes.new_envelope("node-a", "node-b", "note", "hello", grade=2)
    envelopes.seal(env)
    assert envelopes.outbox_pending("node-a") == 1
    spool = home / "telegraph" / "spool"
    summary = envelopes.poll(str(spool), "node-b")
    assert summary["carried"] == 1
    assert envelopes.outbox_pending("node-a") == 0
    inbox = envelopes.read_inbox("node-b")
    assert len(inbox) == 1
    assert inbox[0]["body"] == "hello"
    assert inbox[0]["hops"] == ["node-b"]
    assert envelopes.ack("node-b", inbox[0]["id"])
    assert envelopes.read_inbox("node-b") == []


def test_poll_leaves_other_recipients_alone(home):
    envelopes.seal(envelopes.new_envelope("node-a", "node-c", "note", "not yours"))
    spool = home / "telegraph" / "spool"
    summary = envelopes.poll(str(spool), "node-b")
    assert summary["carried"] == 0
    assert summary["skipped_not_mine"] == 1
    assert envelopes.read_inbox("node-b") == []
    assert envelopes.outbox_pending("node-a") == 1


def test_grades_move_first(home):
    for grade, body in [(7, "low"), (1, "urgent"), (4, "mid")]:
        envelopes.seal(
            envelopes.new_envelope("node-a", "node-b", "note", body, grade=grade)
        )
    spool = home / "telegraph" / "spool"
    envelopes.poll(str(spool), "node-b")
    bodies = [e["body"] for e in envelopes.read_inbox("node-b")]
    assert bodies == ["urgent", "mid", "low"]


def test_loop_envelope_is_refused_and_dropped(home):
    env = envelopes.new_envelope("node-a", "node-b", "note", "loop", grade=0)
    env["hops"] = ["node-b"]  # node-b already handled it
    envelopes.seal(env)
    spool = home / "telegraph" / "spool"
    summary = envelopes.poll(str(spool), "node-b")
    assert summary["refused_loop"] == 1
    assert summary["carried"] == 0
    assert envelopes.read_inbox("node-b") == []
    assert envelopes.outbox_pending("node-a") == 0  # poisoned: dropped


def test_expired_envelope_is_refused(home):
    env = envelopes.new_envelope("node-a", "node-b", "note", "stale", expires_in_s=-1)
    envelopes.seal(env)
    spool = home / "telegraph" / "spool"
    summary = envelopes.poll(str(spool), "node-b")
    assert summary["refused_expired"] == 1
    assert summary["carried"] == 0


def test_bad_envelope_inputs_rejected(home):
    with pytest.raises(ValueError):
        envelopes.new_envelope("bad node!", "node-b", "note", "x")
    with pytest.raises(ValueError):
        envelopes.new_envelope("node-a", "node-b", "telegram", "x")
    with pytest.raises(ValueError):
        envelopes.new_envelope("node-a", "node-b", "note", "", grade=99)
    with pytest.raises(ValueError):
        envelopes.new_envelope("node-a", "node-b", "note", "x", grade=10)


def test_multi_hop_route_builds_hop_trail(home, tmp_path):
    # a -> b -> c via two polls: the bang-path trail stays visible.
    env = envelopes.new_envelope("node-a", "node-c", "note", "relay me")
    envelopes.seal(env)
    spool = home / "telegraph" / "spool"
    # node-b polls: not its mail, left alone.
    assert envelopes.poll(str(spool), "node-b")["carried"] == 0
    # A forward leg: a seal to b, b polls, re-seals onward to c, c polls.
    env2 = envelopes.new_envelope("node-a", "node-b", "echo", "fwd to c")
    envelopes.seal(env2)
    envelopes.poll(str(spool), "node-b")
    got = envelopes.read_inbox("node-b")
    assert got and got[0]["hops"] == ["node-b"]


def test_poll_missing_drop_dir_is_empty_summary(home):
    summary = envelopes.poll(str(home / "nope"), "node-b")
    assert summary == {
        "carried": 0,
        "skipped_not_mine": 0,
        "refused_loop": 0,
        "refused_expired": 0,
    }


# ---------------------------------------------------------------- identity


def test_register_card_and_answerback(home):
    card = identity.register_card(
        "levi-home", "LEVI-HOME-01", capabilities=["telegraph", "agent"]
    )
    assert identity.answerback("levi-home") == "LEVI-HOME-01"
    assert card["capabilities"] == ["telegraph", "agent"]
    with pytest.raises(KeyError):
        identity.answerback("unknown-node")


def test_double_register_refused_without_replace(home):
    identity.register_card("n", "AB-1")
    with pytest.raises(ValueError):
        identity.register_card("n", "AB-2")
    card = identity.register_card("n", "AB-2", replace=True)
    assert card["answerback"] == "AB-2"


def test_handshake_verified_unknown_quarantined(home):
    identity.register_card("levi-phone", "LEVI-PHONE-01")
    ok = identity.handshake("levi-home", "levi-phone", "LEVI-PHONE-01")
    assert ok["verdict"] == "verified"
    unk = identity.handshake("levi-home", "stranger", "WHOEVER")
    assert unk["verdict"] == "unknown"
    bad = identity.handshake("levi-home", "levi-phone", "FAKE-AB")
    assert bad["verdict"] == "quarantined"
    assert "no" in bad["detail"].lower() or "spoof" in bad["detail"].lower()


def test_answerback_length_capped(home):
    with pytest.raises(ValueError):
        identity.register_card("n", "X" * 41)


# ---------------------------------------------------------------- directory


def test_register_lookup_browse_unregister(home):
    directory.register(
        "Moe's printer", "printer", "Bldg. 1", "levi-home", address="desk"
    )
    got = directory.lookup("Moe's printer", "printer", "Bldg. 1")
    assert got and got["node"] == "levi-home"
    rows = directory.browse()
    assert len(rows) == 1
    assert directory.unregister("Moe's printer", "printer", "Bldg. 1", "levi-home")
    assert directory.lookup("Moe's printer", "printer", "Bldg. 1") is None


def test_name_conflict_refused_never_overwritten(home):
    directory.register("shared", "service", "home", "node-a")
    with pytest.raises(ValueError) as ei:
        directory.register("SHARED", "service", "home", "node-b")
    assert "conflict" in str(ei.value).lower()
    got = directory.lookup("shared", "service", "home")
    assert got["node"] == "node-a"  # original owner kept


def test_own_reregister_updates(home):
    directory.register("mine", "svc", "z", "node-a", address="old")
    directory.register("mine", "svc", "z", "node-a", address="new")
    assert directory.lookup("mine", "svc", "z")["address"] == "new"
    assert len(directory.browse()) == 1


def test_unregister_other_node_noop(home):
    directory.register("mine", "svc", "z", "node-a")
    assert not directory.unregister("mine", "svc", "z", "node-b")
    assert directory.lookup("mine", "svc", "z") is not None


def test_browse_filters(home):
    directory.register("a", "svc", "z1", "n1")
    directory.register("b", "svc", "z2", "n1")
    directory.register("c", "other", "z1", "n1")
    assert len(directory.browse(kind="svc")) == 2
    assert len(directory.browse(zone="z1")) == 2
    assert len(directory.browse(kind="svc", zone="z2")) == 1


def test_cli_smoke(home):
    from levi.telegraph.__main__ import main

    assert main(["register-card", "--node", "cli-a", "--answerback", "CLI-A-01"]) == 0
    assert (
        main(
            [
                "send",
                "--src",
                "cli-a",
                "--dst",
                "cli-b",
                "--body",
                "smoke test",
                "--grade",
                "0",
            ]
        )
        == 0
    )
    assert (
        main(["poll", "--drop", str(home / "telegraph" / "spool"), "--node", "cli-b"])
        == 0
    )
    assert main(["inbox", "--node", "cli-b"]) == 0
    assert (
        main(
            ["handshake", "--me", "cli-a", "--peer", "cli-a", "--presented", "CLI-A-01"]
        )
        == 0
    )
    assert (
        main(
            [
                "register",
                "--name",
                "cli-svc",
                "--kind",
                "svc",
                "--zone",
                "lab",
                "--node",
                "cli-a",
            ]
        )
        == 0
    )
    assert main(["names"]) == 0
    envs = envelopes.read_inbox("cli-b")
    assert main(["ack", "--node", "cli-b", "--id", envs[0]["id"]]) == 0
    assert (
        main(
            [
                "unregister",
                "--name",
                "cli-svc",
                "--kind",
                "svc",
                "--zone",
                "lab",
                "--node",
                "cli-a",
            ]
        )
        == 0
    )
