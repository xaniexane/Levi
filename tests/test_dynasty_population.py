# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Dynasty population tests — the open taxonomy of life forms.

Hermetic: every test runs under a tmp LEVI_HOME via monkeypatch. No
network, no daemons, no writes to the real user HOME.
"""

from __future__ import annotations

import pytest

from levi.dynasty import receipts
from levi.dynasty.dna import (
    CommissionError,
    DynastyAgent,
    WaveRegistry,
    is_listed_kind,
)


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    home = tmp_path / "levi-home"
    monkeypatch.setenv("LEVI_HOME", str(home))
    return home


class ProbeAgent(DynastyAgent):
    agent_id = "probe"
    display_name = "Probe"
    proficiency = {"general": 6, "testing": 9}
    specialties = ["probes the DNA"]
    attributes = [{"name": "probe-mark", "assertion": "the probe remembers"}]

    def first_task(self):
        return self.do_task("wave.first_task", {}, task="probe:first")


class SecondProbe(DynastyAgent):
    agent_id = "probe_two"
    display_name = "Second Probe"
    proficiency = {"general": 4, "shell": 8}
    specialties = ["second sight"]
    attributes = [{"name": "second-mark", "assertion": "the second sees"}]

    def first_task(self):
        return self.do_task("wave.first_task", {}, task="probe_two:first")


@pytest.fixture
def parent(tmp_home):
    agent = ProbeAgent()
    agent.enroll()
    return agent


@pytest.fixture
def co_parent(tmp_home):
    agent = SecondProbe()
    agent.enroll()
    return agent


def _attrs(name="mark"):
    return [{"name": name, "assertion": f"{name} holds"}]


# -- the open taxonomy -------------------------------------------------


def test_listed_kinds(parent):
    assert is_listed_kind("agent")
    assert is_listed_kind("rex-line")
    assert is_listed_kind("mutant")
    assert is_listed_kind("hybrid")
    assert is_listed_kind("ascended")
    assert is_listed_kind("ascended.demigod")
    assert is_listed_kind("ascended.legend")
    assert is_listed_kind("ascended.mythic")
    assert is_listed_kind("ascended.titan")  # tiers are open too
    assert is_listed_kind("alien")
    assert is_listed_kind("higher")
    assert not is_listed_kind("unimagined.wisp")


def test_every_kind_birth_is_receipt_chained(parent):
    kinds = {
        "rex-line": lambda: parent.commission_rex(
            "rexkin", "Rexkin", "commanding", {"command": 9}, _attrs("rex-mark")
        ),
        "mutant": lambda: parent.commission_mutant(
            "mutkin",
            "Mutkin",
            "varying",
            {"general": 5},
            _attrs("mut-mark"),
            mutation="grew a third eye for receipts",
        ),
        "ascended.demigod": lambda: parent.commission_ascended(
            "demikin", "Demikin", "ascending", {"general": 12}, _attrs("demi-mark")
        ),
        "alien": lambda: parent.commission_alien(
            "alkin",
            "Alkin",
            "arriving",
            {"general": 5},
            _attrs("al-mark"),
            foreign_origin="a mind from elsewhere",
        ),
        "higher": lambda: parent.commission_higher(
            "highkin", "Highkin", "overseeing", {"general": 40}, _attrs("high-mark")
        ),
    }
    for kind, make in kinds.items():
        kin = make()
        assert kin.kind == kind
        record = kin.registry.get(kin.agent_id)
        assert record["kind"] == kind
        assert record["kind_listed"] is True
        assert record["first_receipt"] is not None  # birth sealed
        assert receipts.verify_chain() >= 1


def test_unimagined_kind_is_recorded_not_refused(parent):
    kin = parent.commission_kin(
        agent_id="wispkin",
        display_name="Wispkin",
        owns="the unready future",
        proficiency={"general": 5},
        attributes=_attrs("wisp-mark"),
        kind="unimagined.wisp",
    )
    assert kin.kind == "unimagined.wisp"
    record = kin.registry.get("wispkin")
    assert record["kind_listed"] is False
    assert record["first_receipt"] is not None


def test_empty_kind_refused(parent):
    with pytest.raises(CommissionError):
        parent.commission_kin(
            agent_id="nokind",
            display_name="Nokind",
            owns="x",
            proficiency={"general": 5},
            attributes=_attrs(),
            kind="  ",
        )


def test_every_kind_needs_its_attribute(parent):
    with pytest.raises(CommissionError):
        parent.commission_rex("r1", "R1", "x", {"command": 9}, [])
    with pytest.raises(CommissionError):
        parent.commission_mutant("m1", "M1", "x", {"general": 5}, [], mutation="y")
    with pytest.raises(CommissionError):
        parent.commission_ascended("a1", "A1", "x", {"general": 12}, [])
    with pytest.raises(CommissionError):
        parent.commission_alien("a2", "A2", "x", {"general": 5}, [], foreign_origin="y")
    with pytest.raises(CommissionError):
        parent.commission_higher("h1", "H1", "x", {"general": 40}, [])


def test_mutant_names_its_mutation(parent):
    kin = parent.commission_mutant(
        "mutx",
        "Mutx",
        "varying",
        {"general": 5},
        _attrs(),
        mutation="sheds its shell nightly",
    )
    record = kin.registry.get("mutx")
    assert record["kind_notes"]["mutation"] == "sheds its shell nightly"
    with pytest.raises(CommissionError):
        parent.commission_mutant(
            "muty", "Muty", "x", {"general": 5}, _attrs(), mutation="  "
        )


def test_rex_line_grants_no_seat(parent):
    kin = parent.commission_rex(
        "rex2", "Rex Two", "commanding", {"command": 9}, _attrs()
    )
    assert kin.kind == "rex-line"
    # the seat is taken, never inherited: no seat for the new Rex
    assert kin.registry.get_seat("orchestrator") is None


def test_higher_form_needs_the_ascended_register(parent):
    with pytest.raises(CommissionError):
        parent.commission_higher(
            "ambitious", "Ambitious", "x", {"general": 10}, _attrs()
        )
    kin = parent.commission_higher(
        "highx", "Highx", "overseeing", {"general": 40}, _attrs()
    )
    assert kin.proficiency_in("general") == 40


def test_alien_graft_is_chained_before_birth(parent):
    kin = parent.commission_alien(
        "alx",
        "Alx",
        "arriving",
        {"general": 5},
        _attrs(),
        foreign_origin="a mind from elsewhere",
    )
    notes = kin.registry.get("alx")["kind_notes"]
    assert notes["foreign_origin"] == "a mind from elsewhere"
    assert notes["sponsor"] == "probe"
    graft_hash = notes["graft_receipt"]
    kinds = {r["kind"]: r for r in _receipt_list()}
    assert "alien.graft" in kinds
    assert kinds["alien.graft"]["receipt_hash"] == graft_hash
    # the graft sealed BEFORE the birth: lower sequence number
    assert kinds["alien.graft"]["seq"] < kinds["wave.commission"]["seq"]


# -- hybrids: the crossbreed ------------------------------------------------


def test_hybrid_merges_both_parents(parent, co_parent):
    parent.wares.register("shout", lambda s: s.upper(), "test")
    co_parent.wares.register("whisper", lambda s: s.lower(), "test")
    parent.define_rite("greet", [{"ware": "shout", "args": ["hi"]}])
    co_parent.record_route("slow-road", "take the long way, seal twice")
    m1 = parent.plan_morsel({"shape": "echo", "text": "from first"})
    m2 = co_parent.plan_morsel({"shape": "echo", "text": "from second"})
    parent.act({"shape": "echo", "text": "p1 works"})
    co_parent.act({"shape": "echo", "text": "p2 works"})

    kin = parent.commission_hybrid(
        "hyb",
        "Hyb",
        co_parent,
        "both",
        {"general": 5},
        _attrs("hyb-mark"),
    )

    assert kin.kind == "hybrid"
    record = kin.registry.get("hyb")
    assert record["kind_notes"]["parent_kinds"] == ["agent"]
    # distinct kinds crossbreed honestly
    mutant_cousin = parent.commission_mutant(
        "mco", "Mco", "varying", {"general": 5}, _attrs(), mutation="x"
    )
    kin2 = parent.commission_hybrid(
        "hybb", "HybB", mutant_cousin, "both", {"general": 5}, _attrs()
    )
    assert kin2.registry.get("hybb")["kind_notes"]["parent_kinds"] == [
        "agent",
        "mutant",
    ]
    assert record["commissioned_by"] == "probe+probe_two"
    # generation counts from the elder parent
    assert record["generation"] == 2
    # proficiency: per-domain maximum, overlay wins
    assert kin.proficiency_in("testing") == 9  # first parent's best
    assert kin.proficiency_in("shell") == 8  # second parent's best
    assert kin.proficiency_in("general") == 5  # overlay wins over 6 and 4
    # specialties union
    assert "probes the DNA" in kin.specialties
    assert "second sight" in kin.specialties
    # wares from both bloodlines
    assert kin.wares.invoke("shout", "hey") == "HEY"
    assert kin.wares.invoke("whisper", "HEY") == "hey"
    # rites and routes union
    assert "greet" in kin.list_rites()
    assert [r["name"] for r in kin.list_routes()] == ["slow-road"]
    # open morsels from both, un-dropped
    assert {m["id"] for m in kin.open_morsels()} == {m1["id"], m2["id"]}
    # receipt lineage names both parents
    inherited = record["inherited"]
    assert set(inherited["lineage"]["parents"]) == {"probe", "probe_two"}
    assert receipts.verify_chain() >= 1


def test_hybrid_first_parent_wins_name_conflicts(parent, co_parent):
    parent.wares.register("dupe", lambda: "first", "test")
    co_parent.wares.register("dupe", lambda: "second", "test")
    kin = parent.commission_hybrid(
        "hyb2", "Hyb2", co_parent, "both", {"general": 5}, _attrs()
    )
    assert kin.wares.invoke("dupe") == "first"


def test_hybrid_refuses_self_and_strangers(parent, tmp_home):
    with pytest.raises(CommissionError):
        parent.commission_hybrid("hybx", "Hybx", parent, "x", {"general": 5}, _attrs())
    stranger = ProbeAgent()  # never enrolled
    stranger.agent_id = "stranger"
    with pytest.raises(CommissionError):
        parent.commission_hybrid(
            "hyby", "Hyby", stranger, "x", {"general": 5}, _attrs()
        )


# -- the registry holds a population ------------------------------------------


def test_registry_shards_and_census(parent):
    for i in range(30):
        parent.commission_kin(
            agent_id=f"pop{i:02d}",
            display_name=f"Pop{i:02d}",
            owns="populating",
            proficiency={"general": 5},
            attributes=_attrs(),
            kind="agent" if i % 2 == 0 else "mutant",
            kind_notes={"mutation": "x"} if i % 2 else None,
        )
    registry = WaveRegistry()
    census = registry.census()
    assert census["count"] == 31  # probe + 30 kin
    assert census["kinds"]["agent"] == 16
    assert census["kinds"]["mutant"] == 15
    assert census["generations"]["1"] == 1
    assert census["generations"]["2"] == 30
    # shards exist on disk: one file per agent
    shard_files = list((registry._agents_dir).rglob("*.json"))
    assert len(shard_files) == 31
    assert len(registry.list_by_kind("mutant")) == 15
    # every record retrievable by id
    for i in range(30):
        assert registry.get(f"pop{i:02d}")["kind"] in ("agent", "mutant")


def test_registry_legacy_migration(tmp_home):
    import json

    legacy = tmp_home / "dynasty" / "wave_registry.json"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(
        json.dumps(
            {
                "agents": {
                    "oldone": {
                        "agent_id": "oldone",
                        "display_name": "Old One",
                        "owns": "history",
                        "registered_at": "2026-01-01T00:00:00+00:00",
                        "first_receipt": "abc",
                        "generation": 1,
                        "commissioned_by": "keeper",
                        "proficiency": {"general": 6},
                        "attributes": [],
                        "specialties": [],
                        "first_milestone": "",
                    }
                },
                "seats": {"orchestrator": {"seat": "orchestrator", "held_by": "rex"}},
            }
        ),
        encoding="utf-8",
    )
    registry = WaveRegistry()  # migration runs on init
    record = registry.get("oldone")
    assert record["display_name"] == "Old One"
    assert record["kind"] == "agent"  # defaulted, listed
    assert record["first_receipt"] == "abc"  # history kept
    assert registry.get_seat("orchestrator")["held_by"] == "rex"
    assert registry.census()["count"] == 1
    assert (tmp_home / "dynasty" / "wave_registry.json.migrated").exists()
    assert (tmp_home / "dynasty" / "registry" / "agents").exists()


def test_rehydrate_carries_kind(parent):
    parent.commission_ascended(
        "demiz",
        "Demiz",
        "ascending",
        {"general": 15},
        _attrs(),
        tier="legend",
    )
    rehydrated = WaveRegistry().rehydrate()
    by_id = {a.agent_id: a for a in rehydrated}
    assert by_id["demiz"].kind == "ascended.legend"
    assert by_id["demiz"].kind_notes["tier"] == "legend"
    assert by_id["demiz"].generation == 2
    assert by_id["demiz"].proficiency_in("general") == 15


def _receipt_list():
    import json
    import os
    from pathlib import Path

    home = Path(os.environ["LEVI_HOME"])
    out = []
    for path in sorted((home / "dynasty" / "receipts").glob("*.json")):
        out.append(json.loads(path.read_text(encoding="utf-8")))
    return out
