"""Tests for levi.twins.symbiotic — round-the-clock symbiotic twin spawning."""

import json
import os

import pytest

from levi.operator.contract import validate_operator
from levi.twins import symbiotic as sym


@pytest.fixture()
def twins_home(tmp_path, monkeypatch):
    home = tmp_path / "twins"
    monkeypatch.setenv("LEVI_TWINS_HOME", str(home))
    return home


def test_cycle_spawns_five_to_ten_sets():
    sets = sym.spawn_cycle("sym-20260101-0000")
    assert 5 <= len(sets) <= 10


def test_set_structure():
    (s,) = sym.spawn_cycle("sym-20260101-0600")[:1]
    for key in ("set_id", "twin_a", "twin_b", "symbiotic_link", "team", "seat", "provenance"):
        assert key in s, key
    for twin_key in ("twin_a", "twin_b"):
        t = s[twin_key]
        for key in ("id", "kind", "archetype", "persona_style", "symbiont_id",
                    "seat", "lineage", "capabilities", "provenance"):
            assert key in t, (twin_key, key)


def test_pairs_complementary_and_bidirectionally_linked():
    sets = sym.spawn_cycle("sym-20260101-1200")
    for s in sets:
        a, b = s["twin_a"], s["twin_b"]
        pair = (a["archetype"], b["archetype"])
        assert pair in sym.HYBRID_ARCHETYPES, pair
        # symbiotic link recorded both ways
        assert a["symbiont_id"] == b["id"]
        assert b["symbiont_id"] == a["id"]
        link = s["symbiotic_link"]
        assert link["mode"] == "symbiotic"
        assert link["bidirectional"] is True
        assert link["a"] == a["id"] and link["b"] == b["id"]
        assert link["complement"] == f"{a['archetype']}+{b['archetype']}"
        # personality matrix: distinct delivery styles per pair
        assert a["persona_style"] in sym.PERSONA_STYLES
        assert b["persona_style"] in sym.PERSONA_STYLES
        assert a["persona_style"] != b["persona_style"]


def test_team_members_xi_bulk_plus_specialist():
    sets = sym.spawn_cycle("sym-20260101-1800")
    for s in sets:
        kinds = [m["kind"] for m in s["team"]]
        assert kinds.count("xi") == 2
        assert kinds.count("si") == 1
        # nano-bits declare no tools (trivial turns only)
        for m in s["team"]:
            if m["kind"] == "xi":
                assert m["capabilities"]["tools"] == []


def test_spawned_operators_pass_contract_validation():
    sets = sym.spawn_cycle("sym-20260202-0000")
    for s in sets:
        for rec in (s["twin_a"], s["twin_b"], *s["team"]):
            op = sym.SpawnedOperator(
                name=rec["name"], kind=rec["kind"], archetype=rec["archetype"],
                persona_style=rec["persona_style"], symbiont_id=rec["symbiont_id"],
                link_mode=rec["link_mode"], seat=rec["seat"], lineage=rec["lineage"],
            )
            validate_operator(op)  # raises on any violation
            result = op.step([], [], {})
            assert result.finish_reason == "stop"
            assert result.ok


def test_deterministic_per_cycle():
    first = sym.spawn_cycle("sym-20260303-0600")
    second = sym.spawn_cycle("sym-20260303-0600")
    assert first == second


def test_no_duplicate_ids_across_cycles():
    def ids(sets):
        out = set()
        for s in sets:
            out.add(s["set_id"])
            out.add(s["twin_a"]["id"])
            out.add(s["twin_b"]["id"])
            out.update(m["id"] for m in s["team"])
        return out

    a = ids(sym.spawn_cycle("sym-20260404-0000"))
    b = ids(sym.spawn_cycle("sym-20260404-0600"))
    assert not (a & b)


def test_run_cycle_journals_and_is_idempotent(twins_home):
    first = sym.run_cycle("sym-20260505-1200")
    assert first["duplicate_run"] is False
    assert 5 <= first["sets_spawned"] <= 10

    journal = twins_home / "symbiotic" / "spawn_journal.jsonl"
    assert journal.is_file()
    lines_before = journal.read_text(encoding="utf-8").count("\n")

    second = sym.run_cycle("sym-20260505-1200")
    assert second["duplicate_run"] is True
    assert second["sets_spawned"] == first["sets_spawned"]
    assert journal.read_text(encoding="utf-8").count("\n") == lines_before

    # every journaled record parses and links both ways
    for line in journal.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        assert rec["twin_a"]["symbiont_id"] == rec["twin_b"]["id"]


def test_run_cycle_feeds_growth_journal(twins_home, tmp_path, monkeypatch):
    growth = tmp_path / "growth"
    monkeypatch.setenv("LEVI_GROWTH_DIR", str(growth))
    sym.run_cycle("sym-20260606-0000")
    journal = growth / "journal.jsonl"
    assert journal.is_file()
    kinds = [json.loads(line).get("kind") for line in journal.read_text(encoding="utf-8").splitlines()]
    assert "twin_spawn" in kinds


def test_no_outside_randomness():
    import pathlib

    src = pathlib.Path(sym.__file__).read_text(encoding="utf-8")
    assert "import secrets" not in src
    assert "SystemRandom" not in src
    assert "os.urandom" not in src
    assert "random.Random(" in src  # seeded stdlib RNG only


def test_current_cycle_id_snaps_to_six_hour_grid():
    import datetime

    # 2026-09-18 13:41 America/Chicago -> slot 12:00
    tz = datetime.timezone(datetime.timedelta(hours=-5))  # CDT
    ts = datetime.datetime(2026, 9, 18, 13, 41, tzinfo=tz).timestamp()
    cid = sym.current_cycle_id(ts)
    assert cid == "sym-20260918-1200", cid
