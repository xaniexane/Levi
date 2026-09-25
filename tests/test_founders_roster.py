"""Founders' Roster tests — 490 seats, one draw, one truth.

Covers: seat count (19 founders + the live 471-agent catalog), hierarchy
invariants, non-empty role/first_purpose/provenance on every seat, the
seeded nature draw's determinism, AI/SI fluidity (free ai<->si switching,
mssi reserved for Levi), deny-open unknown keys, and validation that
rejects malformed seats.

Run:  python3 -m pytest tests/test_founders_roster.py -q
"""

from __future__ import annotations

import dataclasses
import random

import pytest

from levi.automation.minions import MINIONS
from levi.founders import roster as R
from levi.founders.roster import (
    DRAW_SEED,
    SEATS,
    current_nature,
    eligible_mentors,
    get_founder,
    get_seat,
    is_seasoned,
    mark_seasoned,
    reseat,
    reset_seasoned,
    seats_by_authority,
    seats_by_kind,
    seats_by_origin,
    switch_nature,
    validate_mentor_graph,
    validate_roster,
    validate_seat,
)


@pytest.fixture(autouse=True)
def _restore_ledger():
    yield
    reseat()
    reset_seasoned()


# -- count and shape -------------------------------------------------------------


def test_seat_count_is_19_founders_plus_live_catalog():
    assert len(SEATS) == 19 + len(MINIONS) == 490
    by_kind = seats_by_kind()
    assert len(by_kind["founder"]) == 19
    assert len(by_kind["agent"]) == len(MINIONS) == 471


def test_keys_unique_and_founders_known():
    assert len(set(SEATS)) == len(SEATS)
    assert set(s.key for s in seats_by_kind()["founder"]) == {
        "demandpulse",
        "nexus-network",
        "alpha",
        "omega",
        "levi",
        "echo",
        "mandella",
        "reim",
        "riem",
        "cyberpulse",
        "uniforge",
        "omnipulse",
        "cybrus",
        "cortex",
        "vector",
        "oracle",
        "hypercube",
        "eli",
        "ser-18-core",
    }


def test_agent_seats_resolve_against_live_catalog():
    agent_keys = {s.key for s in seats_by_kind()["agent"]}
    catalog_ids = {m.id for m in MINIONS}
    assert agent_keys == catalog_ids
    for s in seats_by_kind()["agent"]:
        assert s.kind == "agent"
        assert s.authority_rank == 3
        assert s.minion_id == s.key
        assert s.provenance == ("minions.py:%s" % s.key,)
        assert s.category  # catalog category carried through


# -- hierarchy invariants --------------------------------------------------------


def test_authority_ranks():
    ranks = {s.authority_rank for s in SEATS.values()}
    assert ranks <= {0, 1, 2, 3}
    rank0 = {s.key for s in SEATS.values() if s.authority_rank == 0}
    rank1 = {s.key for s in SEATS.values() if s.authority_rank == 1}
    assert rank0 == {"alpha", "omega"}
    assert rank1 == {"levi"}
    for s in seats_by_kind()["founder"]:
        assert s.authority_rank in (0, 1, 2)


def test_origin_order_canon():
    assert get_seat("demandpulse").origin_order == 0
    assert get_seat("nexus-network").origin_order == 1
    assert get_seat("alpha").origin_order == 2
    assert get_seat("omega").origin_order == 2
    assert get_seat("levi").origin_order == 3
    head = [s.key for s in seats_by_origin()[:5]]
    assert head == ["demandpulse", "nexus-network", "alpha", "omega", "levi"]
    tail = seats_by_origin()[-len(MINIONS) :]
    assert all(s.kind == "agent" for s in tail)


def test_seats_by_authority_order():
    ordered = seats_by_authority()
    assert {s.key for s in ordered[:2]} == {"alpha", "omega"}
    assert ordered[2].key == "levi"
    assert all(s.authority_rank == 2 for s in ordered[3 : 3 + 16])
    assert all(s.authority_rank == 3 for s in ordered[19:])


# -- every seat is evidenced ------------------------------------------------------


def test_every_seat_has_role_purpose_provenance():
    for key, s in SEATS.items():
        assert s.role, key
        assert s.first_purpose, key
        assert s.provenance, key


def test_validation_accepts_the_whole_roster():
    assert validate_roster() == []


def test_founder_provenance_names_its_sources():
    echo = get_founder("echo")
    assert any("cycle.py" in p for p in echo.provenance)
    assert any("lexicon" in p for p in echo.provenance)


# -- the one draw: seeded, deterministic ------------------------------------------


def _expected_draw():
    """Recompute the draw independently: same seed, same canonical order."""
    rng = random.Random(DRAW_SEED)
    expected = {}
    for key in R._SEAT_KEYS:
        expected[key] = "mssi" if key == "levi" else rng.choice(("ai", "si"))
    for m in MINIONS:
        expected[m.id] = rng.choice(("ai", "si"))
    return expected


def test_one_draw_matches_expected_seed_walk():
    expected = _expected_draw()
    assert len(expected) == 490
    for key, nature in expected.items():
        assert SEATS[key].nature == nature, key


def test_reload_reproduces_identical_natures():
    import importlib

    first = {k: s.nature for k, s in SEATS.items()}
    reloaded = importlib.reload(R)
    second = {k: s.nature for k, s in reloaded.SEATS.items()}
    assert first == second


def test_exactly_one_mssi_and_it_is_levi():
    mssi = [k for k, s in SEATS.items() if s.nature == "mssi"]
    assert mssi == ["levi"]
    assert current_nature("levi") == "mssi"


def test_the_18_originals_seat_ai_or_si_only():
    for s in seats_by_kind()["founder"]:
        if s.key == "levi":
            continue
        assert s.nature in ("ai", "si"), s.key


# -- fluidity: ai/si switchable, mssi reserved ------------------------------------


def test_switch_ai_si_freely_founder_and_agent():
    assert switch_nature("echo", "ai") == "ai"
    assert current_nature("echo") == "ai"
    assert switch_nature("echo", "si") == "si"
    agent_key = MINIONS[0].id
    other = "si" if current_nature(agent_key) == "ai" else "ai"
    assert switch_nature(agent_key, other) == other


def test_switch_to_mssi_rejected_for_everyone_else():
    for bad in ("mssi", "multi-substrate", "multi_substrate", "MSSI"):
        with pytest.raises(ValueError):
            switch_nature("echo", bad)
        with pytest.raises(ValueError):
            switch_nature(MINIONS[0].id, bad)


def test_levi_nature_not_switchable():
    with pytest.raises(ValueError):
        switch_nature("levi", "ai")
    with pytest.raises(ValueError):
        switch_nature("levi", "si")


def test_switch_rejects_garbage_nature():
    with pytest.raises(ValueError):
        switch_nature("echo", "hybrid")


def test_reseat_restores_initial_draw():
    switch_nature("echo", "ai" if current_nature("echo") == "si" else "si")
    reseat()
    assert current_nature("echo") == get_seat("echo").nature


# -- deny-open unknown keys ---------------------------------------------------------


def test_unknown_keys_raise_never_guess():
    for fn in (get_seat, get_founder, current_nature):
        with pytest.raises(KeyError):
            fn("not-a-seat")
    with pytest.raises(KeyError):
        switch_nature("not-a-seat", "ai")
    with pytest.raises(KeyError):
        get_founder(MINIONS[0].id)  # real seat, not a founder


# -- validation rejects bad data ----------------------------------------------------


def test_validation_rejects_bad_founder():
    echo = get_founder("echo")
    assert validate_seat(dataclasses.replace(echo, role=""))
    assert validate_seat(dataclasses.replace(echo, first_purpose=""))
    assert validate_seat(dataclasses.replace(echo, provenance=()))
    assert validate_seat(dataclasses.replace(echo, authority_rank=3))
    assert validate_seat(dataclasses.replace(echo, authority_rank=9))
    assert validate_seat(dataclasses.replace(echo, nature="mssi"))
    assert validate_seat(dataclasses.replace(get_seat("levi"), nature="ai"))
    assert validate_seat(
        dataclasses.replace(echo, authority_rank=0)
    )  # rank 0 is Alpha & Omega only
    assert validate_seat(dataclasses.replace(get_seat("levi"), authority_rank=0))


def test_validation_rejects_bad_agent():
    agent = get_seat(MINIONS[0].id)
    assert validate_seat(dataclasses.replace(agent, authority_rank=2))
    assert validate_seat(dataclasses.replace(agent, nature="mssi"))
    assert validate_seat(dataclasses.replace(agent, minion_id="no-such-minion"))
    assert validate_seat(dataclasses.replace(agent, kind="founder"))
    assert validate_seat(dataclasses.replace(agent, first_purpose=""))


# -- the cascade -----------------------------------------------------------------


def test_mentor_bonds_at_the_top():
    for k in ("alpha", "omega"):
        s = get_seat(k)
        assert s.mentor is None
        assert s.mentees == ()
    levi = get_seat("levi")
    assert levi.mentor is None
    assert set(levi.mentees) == {k for k in SEATS if get_seat(k).kind == "founder"} - {
        "levi"
    }
    assert len(levi.mentees) == 18
    for k in levi.mentees:
        # Alpha/Omega are Levi's mentees on the plan but unmentored themselves:
        # they are the source, first and last.
        if k in ("alpha", "omega"):
            assert get_seat(k).mentor is None
        else:
            assert get_seat(k).mentor == "levi"


def test_every_agent_has_exactly_one_resolving_mentor():
    for s in seats_by_kind()["agent"]:
        assert s.mentor is not None, s.key
        assert s.mentor in SEATS, s.key
        assert s.mentor != s.key
        assert s.key in get_seat(s.mentor).mentees


def test_no_mentor_cycles():
    for key in SEATS:
        seen = set()
        cur = key
        while True:
            mentor = get_seat(cur).mentor
            assert mentor not in seen, "cycle through %r" % key
            if mentor is None:
                break
            seen.add(mentor)
            cur = mentor


def test_wave_partition_and_cascade_rule():
    waves = {}
    for s in seats_by_kind()["agent"]:
        waves.setdefault(s.wave, []).append(s.key)
    assert set(waves) == {"A", "B", "C", "D"}
    assert sum(len(v) for v in waves.values()) == 471
    assert len(waves["A"]) == 122 and len(waves["B"]) == 81
    assert len(waves["C"]) == 116 and len(waves["D"]) == 152
    sixteen = {k for k in SEATS if get_seat(k).kind == "founder"} - {
        "levi",
        "alpha",
        "omega",
    }
    assert len(sixteen) == 16
    for key in waves["A"]:
        assert get_seat(key).mentor in sixteen
    for key in waves["B"]:
        assert get_seat(get_seat(key).mentor).wave == "A"
    for key in waves["C"]:
        assert get_seat(get_seat(key).mentor).wave == "B"
    for key in waves["D"]:
        assert get_seat(get_seat(key).mentor).wave == "C"


def test_mentor_load_caps():
    from collections import Counter

    loads = Counter()
    for s in seats_by_kind()["agent"]:
        loads[s.mentor] += 1
    assert (
        max(loads[m] for m in loads if get_seat(m).wave == "founders") <= 8
    )  # wave A cap
    assert max(loads[m] for m in loads if get_seat(m).wave == "A") <= 1  # wave B cap
    assert max(loads[m] for m in loads if get_seat(m).wave == "B") <= 2  # wave C cap
    assert max(loads[m] for m in loads if get_seat(m).wave == "C") <= 2  # wave D cap


def test_mentor_graph_validation_accepts_roster():
    assert validate_mentor_graph() == []
    assert validate_roster() == []


def test_validation_rejects_mentor_problems():
    agent = get_seat(MINIONS[0].id)
    bad = dict(SEATS)
    bad[agent.key] = dataclasses.replace(agent, mentor="no-such-seat")
    assert validate_mentor_graph(bad)
    bad = dict(SEATS)
    bad[agent.key] = dataclasses.replace(agent, mentor=agent.key)
    assert validate_mentor_graph(bad)
    # a cycle: levi mentored by echo, who is mentored by levi
    bad = dict(SEATS)
    bad["levi"] = dataclasses.replace(get_seat("levi"), mentor="echo")
    assert validate_mentor_graph(bad)
    # alpha takes a mentee
    bad = dict(SEATS)
    bad["alpha"] = dataclasses.replace(get_seat("alpha"), mentees=(agent.key,))
    assert validate_mentor_graph(bad)


# -- seasoned: the mastery gate -----------------------------------------------------


def test_everyone_unseasoned_at_seating_no_free_passes():
    assert all(s.seasoned is False for s in SEATS.values())
    assert all(not is_seasoned(k) for k in SEATS)
    for s in seats_by_kind()["founder"]:  # founders earn it like everyone else
        assert not is_seasoned(s.key)


def test_eligible_mentors_empty_then_grows():
    assert eligible_mentors() == []
    assert mark_seasoned("echo") is True
    assert mark_seasoned(MINIONS[0].id) is True
    assert eligible_mentors() == ["echo", MINIONS[0].id]  # seating order
    assert is_seasoned("echo")


def test_mark_seasoned_unknown_key_raises():
    with pytest.raises(KeyError):
        mark_seasoned("not-a-seat")
    with pytest.raises(KeyError):
        is_seasoned("not-a-seat")


def test_reset_seasoned_restores_unseasoned():
    mark_seasoned("echo")
    reset_seasoned()
    assert eligible_mentors() == []
    assert not is_seasoned("echo")


if __name__ == "__main__":
    import sys
    import traceback

    failures = 0
    for name, fn in sorted(
        [(k, v) for k, v in globals().items() if k.startswith("test_") and callable(v)]
    ):
        try:
            fn()
        except Exception:
            failures += 1
            print("FAIL", name)
            traceback.print_exc()
        finally:
            reseat()
    print("failures:", failures)
    sys.exit(1 if failures else 0)
