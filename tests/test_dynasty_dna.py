"""Dynasty DNA tests — base agent, privacy rails, and the Nth generation.

Hermetic: every test runs under a tmp LEVI_HOME via monkeypatch. No
network, no daemons, no writes to the real user HOME.
"""

from __future__ import annotations

import pytest

from levi.dynasty import receipts
from levi.dynasty.builder import ScopeViolation, check_tool_scope, list_tools
from levi.dynasty.dna import (
    AgentError,
    CommissionError,
    DynastyAgent,
    PrivacyLeak,
    WaveRegistry,
    assert_clean,
    scrub_text,
)


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    home = tmp_path / "levi-home"
    monkeypatch.setenv("LEVI_HOME", str(home))
    return home


class ProbeAgent(DynastyAgent):
    agent_id = "probe"
    display_name = "Probe"
    owns = "testing the bloodline"
    proficiency = {"general": 6, "testing": 9}
    specialties = ["probes the DNA"]
    attributes = [
        {
            "name": "null-echo",
            "assertion": "repeating a task twice returns the identical receipt payload hash",
        }
    ]

    def first_task(self):
        return self.do_task("wave.first_task", {"probe": "green"}, task="probe:first")


def _enrolled_probe(tmp_home):
    agent = ProbeAgent()
    agent.enroll()
    return agent


# -- DNA basics -----------------------------------------------------------


def test_agent_enroll_idempotent(tmp_home):
    agent = _enrolled_probe(tmp_home)
    first = agent.enroll()
    second = agent.enroll()
    assert first["registered_at"] == second["registered_at"]
    assert first["generation"] == 1
    assert first["commissioned_by"] == "keeper"


def test_agent_act_seals_receipt(tmp_home):
    agent = _enrolled_probe(tmp_home)
    receipt = agent.act({"shape": "echo", "text": "hello bloodline"})
    assert receipt["kind"] == "wave.task"
    assert receipt["payload"]["result"] == {"echo": "hello bloodline"}
    assert receipts.verify_chain() >= 1


def test_agent_first_task_green(tmp_home):
    agent = _enrolled_probe(tmp_home)
    receipt = agent.run_first_task()
    assert receipt["kind"] == "wave.first_task"
    record = agent.registry.get("probe")
    assert record["first_receipt"] == receipt["receipt_hash"]


def test_agent_attributes_validated(tmp_home):
    class BadAttr(DynastyAgent):
        agent_id = "badattr"
        attributes = [{"name": "half-formed"}]  # no assertion

    with pytest.raises(AgentError):
        BadAttr()


def test_scrub_redacts_markers_and_hashes():
    dirty = "Hybrid IP Protection Block " + "ab" * 32
    clean = scrub_text(dirty)
    assert "Hybrid IP Protection Block" not in clean
    assert "ab" * 32 not in clean


def test_scrub_keeps_hashes_when_asked():
    h = "cd" * 32
    assert h in scrub_text(f"hash {h}", redact_hashes=False)


def test_assert_clean_raises_privacy_leak():
    with pytest.raises(PrivacyLeak):
        assert_clean("contains keeper.key material", "unit test")


def test_ware_result_privacy_enforced(tmp_home):
    agent = _enrolled_probe(tmp_home)
    agent.wares.register("leaky", lambda: "keeper.key: deadbeef", "test")
    with pytest.raises(PrivacyLeak):
        agent.wares.invoke("leaky")


# -- the Nth generation: commissioning ------------------------------------


def test_commission_end_to_end(tmp_home):
    """An agent commissions new kin: enrolled, generation 2,
    receipt-chained from birth, fully working, rehydratable."""
    parent = _enrolled_probe(tmp_home)
    kin = parent.commission_kin(
        agent_id="probe_kin",
        display_name="Probe Kin",
        owns="second-generation testing",
        proficiency={"general": 5, "testing": 7},
        specialties=["second of the line"],
        attributes=[
            {
                "name": "birthmark",
                "assertion": "every kin answers its generation on demand",
            }
        ],
    )
    # enrolled with the line recorded
    record = kin.registry.get("probe_kin")
    assert record is not None
    assert record["generation"] == 2
    assert record["commissioned_by"] == "probe"
    assert record["attributes"][0]["name"] == "birthmark"
    # receipt-chained from birth
    assert record["first_receipt"]
    assert receipts.verify_chain() >= 1
    birth_kinds = [r["kind"] for r in _all_receipts()]
    assert "wave.commission" in birth_kinds
    # the child is a working agent
    assert kin.proficiency_in("testing") == 7
    assert kin.generation == 2
    echo = kin.act({"shape": "echo", "text": "second generation speaks"})
    assert echo["payload"]["result"] == {"echo": "second generation speaks"}
    # the line survives restarts: rehydrate from the registry
    reborn = WaveRegistry().rehydrate()
    assert [k.agent_id for k in reborn] == ["probe_kin"]
    assert reborn[0].generation == 2
    assert reborn[0].commissioned_by == "probe"


def _all_receipts():
    # receipts are read through the chain verifier's own reader
    import json
    from pathlib import Path
    import os

    home = Path(os.environ["LEVI_HOME"])
    out = []
    for path in sorted((home / "dynasty" / "receipts").glob("*.json")):
        out.append(json.loads(path.read_text(encoding="utf-8")))
    return out


def test_commission_third_generation(tmp_home):
    parent = _enrolled_probe(tmp_home)
    child = parent.commission_kin(
        agent_id="gen_two",
        display_name="Gen Two",
        owns="gen two",
        proficiency={"general": 5},
        attributes=[{"name": "a", "assertion": "b"}],
    )
    grandchild = child.commission_kin(
        agent_id="gen_three",
        display_name="Gen Three",
        owns="gen three",
        proficiency={"general": 5},
        attributes=[{"name": "a", "assertion": "b"}],
    )
    assert grandchild.registry.get("gen_three")["generation"] == 3
    assert grandchild.registry.get("gen_three")["commissioned_by"] == "gen_two"


def test_commission_refused_unenrolled_parent(tmp_home):
    outsider = ProbeAgent()  # never enrolled
    with pytest.raises(CommissionError):
        outsider.commission_kin(
            agent_id="stray",
            display_name="Stray",
            owns="nowhere",
            proficiency={"general": 5},
            attributes=[{"name": "a", "assertion": "b"}],
        )


def test_commission_refused_bad_ids(tmp_home):
    parent = _enrolled_probe(tmp_home)
    for bad in ("", "AB", "has space", "has-dash", "x" * 33, "../evil"):
        with pytest.raises(CommissionError):
            parent.commission_kin(
                agent_id=bad,
                display_name="Bad",
                owns="bad",
                proficiency={"general": 5},
                attributes=[{"name": "a", "assertion": "b"}],
            )


def test_commission_refused_duplicate_id(tmp_home):
    parent = _enrolled_probe(tmp_home)
    parent.commission_kin(
        agent_id="twin",
        display_name="Twin",
        owns="twin",
        proficiency={"general": 5},
        attributes=[{"name": "a", "assertion": "b"}],
    )
    with pytest.raises(CommissionError):
        parent.commission_kin(
            agent_id="twin",
            display_name="Twin Two",
            owns="twin",
            proficiency={"general": 5},
            attributes=[{"name": "a", "assertion": "b"}],
        )


def test_commission_refused_bad_profile(tmp_home):
    parent = _enrolled_probe(tmp_home)
    with pytest.raises(CommissionError):  # empty profile
        parent.commission_kin(
            agent_id="noprof",
            display_name="NoProf",
            owns="x",
            proficiency={},
            attributes=[{"name": "a", "assertion": "b"}],
        )
    with pytest.raises(CommissionError):  # all zero
        parent.commission_kin(
            agent_id="zeroprof",
            display_name="ZeroProf",
            owns="x",
            proficiency={"general": 0},
            attributes=[{"name": "a", "assertion": "b"}],
        )
    with pytest.raises(CommissionError):  # no unreplicable attribute
        parent.commission_kin(
            agent_id="noattr",
            display_name="NoAttr",
            owns="x",
            proficiency={"general": 5},
            attributes=[],
        )


# -- generational inheritance: the line carries on ----------------------


def test_inheritance_carries_on(tmp_home):
    """New kin don't start from zero: the child continues the parent's
    in-flight work with the parent's methods intact."""
    parent = _enrolled_probe(tmp_home)
    # (1) the work: two morsels opened, one completed, one in flight
    m1 = parent.plan_morsel({"shape": "echo", "text": "first"})
    m2 = parent.plan_morsel({"shape": "echo", "text": "second"})
    parent.complete_morsel(m2["id"], {"done": True})
    # (2) the methods: a custom ware and a rite
    parent.wares.register("shout", lambda s: s.upper(), "test")
    parent.define_rite("greet", [{"ware": "shout", "args": ["hi"]}])
    # (4) the routes: a proven approach
    parent.record_route("quick-echo", "answer echoes at once, then seal")
    # the parent does some work first so the lineage is real
    parent.act({"shape": "echo", "text": "parent works"})

    kin = parent.commission_kin(
        agent_id="heir",
        display_name="Heir",
        owns="carrying on",
        proficiency={"testing": 10, "shell": 7},  # overlay: wins + adds
        attributes=[{"name": "birthmark", "assertion": "the heir remembers"}],
    )

    # (2) proficiency: parent's base stands, the overlay wins and extends
    assert kin.proficiency_in("testing") == 10  # overlay wins over parent's 9
    assert kin.proficiency_in("general") == 6  # inherited base
    assert kin.proficiency_in("shell") == 7  # overlay adds
    assert "probes the DNA" in kin.specialties  # specialties union

    # (1) the work: the open morsel passed un-dropped; done one stayed home
    open_kin = kin.open_morsels()
    assert [m["id"] for m in open_kin] == [m1["id"]]
    assert open_kin[0]["inherited_from"] == "probe"
    receipt = kin.complete_morsel(m1["id"], {"continued": True})
    assert receipt["kind"] == "wave.morsel"
    assert kin.open_morsels() == []

    # (2) the methods: custom ware and rite work in the child's hands
    assert "shout" in kin.wares.list_wares()
    assert kin.wares.invoke("shout", "hello") == "HELLO"
    assert "greet" in kin.list_rites()
    rite_receipt = kin.perform_rite("greet")
    assert rite_receipt["kind"] == "wave.rite"
    assert rite_receipt["payload"]["steps"][0]["result"] == "HI"

    # (4) the routes: the child walks the working roads
    routes = kin.list_routes()
    assert [r["name"] for r in routes] == ["quick-echo"]
    assert routes[0]["inherited_from"] == "probe"

    # (3) the pattern of thinking: the keeper's signature, every generation
    deliberation = kin.reason("build the unbuilt thing")
    assert deliberation["pattern"] == "keeper-signature"
    assert set(deliberation) >= {"absorb", "reverse", "improve", "return"}

    # the birth receipt tells the whole inheritance story
    record = kin.registry.get("heir")
    inherited = record["inherited"]
    assert inherited["morsels"] == [m1["id"]]
    assert inherited["wares"] == ["shout"]
    assert inherited["rites"] == ["greet"]
    assert inherited["routes"] == ["quick-echo"]
    assert inherited["reasoning"] == "keeper-signature"
    assert inherited["lineage"]["parents"]["probe"]
    assert receipts.verify_chain() >= 1


def test_inheritance_grandchild_keeps_carrying(tmp_home):
    parent = _enrolled_probe(tmp_home)
    parent.wares.register("shout", lambda s: s.upper(), "test")
    parent.plan_morsel({"shape": "echo", "text": "long road"})
    child = parent.commission_kin(
        agent_id="gen2heir",
        display_name="Gen2 Heir",
        owns="carrying",
        proficiency={"general": 5},
        attributes=[{"name": "a", "assertion": "b"}],
    )
    grandchild = child.commission_kin(
        agent_id="gen3heir",
        display_name="Gen3 Heir",
        owns="still carrying",
        proficiency={"general": 5},
        attributes=[{"name": "a", "assertion": "b"}],
    )
    # the ware and the open morsel survive two hand-offs
    assert "shout" in grandchild.wares.list_wares()
    assert len(grandchild.open_morsels()) == 1
    assert grandchild.open_morsels()[0]["inherited_from"] == "gen2heir"
    assert grandchild.registry.get("gen3heir")["generation"] == 3


# -- purge regressions: DNA-level thread-safety (F-SW-1/2/3) ---------------


def test_purge_receipt_forgery_byte_flip_raises_receipt_error(tmp_home):
    """F-WC-1 (crew C): a byte-flipped receipt file that breaks UTF-8
    must raise the documented ReceiptError, never a raw
    UnicodeDecodeError."""
    from levi.dynasty.receipts import ReceiptError, _receipts_dir

    receipts.mint_receipt("purge.forge", {"ok": True}, task="forge")
    target = next(_receipts_dir().glob("*.json"))
    data = target.read_bytes()
    target.write_bytes(data[:10] + b"\xff\xfe" + data[12:])
    with pytest.raises(ReceiptError):
        receipts.mint_receipt("purge.after", {}, task="after")
    with pytest.raises(ReceiptError):
        receipts.verify_chain()


def test_purge_mint_thread_storm_gapless(tmp_home):
    """F-SW-1: 8 threads x 50 mints — no FileExistsError, gapless
    sequence, chain intact."""
    import threading

    errors = []
    minted = []
    lock = threading.Lock()

    def worker():
        try:
            for i in range(50):
                r = receipts.mint_receipt("purge.storm", {"i": i}, task="storm")
                with lock:
                    minted.append(r["seq"])
        except Exception as exc:  # noqa: BLE001
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert sorted(minted) == list(range(1, 401))
    assert receipts.verify_chain() == 400


def test_purge_keeper_key_concurrent_birth(tmp_home):
    """F-SW-2: key born under a thread storm — every receipt verifies,
    one key, no fork."""
    import threading
    from levi.dynasty import receipts as rmod

    errors = []

    def worker():
        try:
            rmod.mint_receipt("purge.keybirth", {}, task="birth")
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert rmod.verify_chain() == 16
    key = (tmp_home / "dynasty" / "keeper.key").read_bytes()
    assert len(key) == 32


def test_purge_sessions_multi_instance_no_clobber(tmp_home):
    """F-SW-3: two instances sharing one state file under a thread
    storm — no session lost from disk."""
    import threading

    from levi.dynasty.shell.sessions import SessionManager

    state = tmp_home / "dynasty" / "sessions.json"
    errors = []

    def worker(n):
        try:
            mgr = SessionManager(state)
            for i in range(25):
                mgr.create(f"w{n}-s{i}")
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    fresh = SessionManager(state)
    names = {s["name"] for s in fresh.list_sessions()}
    assert len(names) == 200


# -- commissioning through the Builder ------------------------------------


def test_builder_commission_tool_declared():
    assert "commission_agent" in list_tools()


def test_builder_commission_scope_ok():
    check_tool_scope("commission_agent", "new_kin")  # must not raise


def test_builder_commission_scope_rejects_malformed():
    for bad in ("", "AB", "has space", "../evil"):
        with pytest.raises(ScopeViolation):
            check_tool_scope("commission_agent", bad)
