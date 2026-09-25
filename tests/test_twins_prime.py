"""Tests for prime waves, the XI organism track, and the intelligence catalog.

Covers levi.twins.symbiotic wave logic + levi.twins.prime +
levi.twins.intelligence_types.
"""

import json
import pathlib

import pytest

from levi.operator.contract import validate_operator
from levi.twins import intelligence_types as it
from levi.twins import prime
from levi.twins import symbiotic as sym


@pytest.fixture()
def twins_home(tmp_path, monkeypatch):
    home = tmp_path / "twins"
    monkeypatch.setenv("LEVI_TWINS_HOME", str(home))
    return home


def _journal_records(home):
    p = home / "symbiotic" / "spawn_journal.jsonl"
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()]


def test_wave_alternation_deterministic_from_journal_state(twins_home):
    s1 = sym.run_cycle("sym-20270101-0000")
    s2 = sym.run_cycle("sym-20270101-0600")
    s3 = sym.run_cycle("sym-20270101-1200")
    s4 = sym.run_cycle("sym-20270101-1800")
    assert (s1["wave"], s1["wave_parity"]) == (1, "standard")
    assert (s2["wave"], s2["wave_parity"]) == (2, "prime")
    assert (s3["wave"], s3["wave_parity"]) == (3, "standard")
    assert (s4["wave"], s4["wave_parity"]) == (4, "prime")
    # every journal record carries its wave
    for rec in _journal_records(twins_home):
        assert rec["wave"] in (1, 2, 3, 4)
        assert rec["wave_parity"] in ("standard", "prime")
        assert rec["wave_parity"] == ("prime" if rec["wave"] % 2 == 0 else "standard")


def test_prime_organism_only_on_prime_waves(twins_home):
    s1 = sym.run_cycle("sym-20270202-0000")
    s2 = sym.run_cycle("sym-20270202-0600")
    assert s1["prime_organism_id"] is None
    assert s1["prime_intelligence_type"] is None
    assert s2["prime_organism_id"] is not None
    assert s2["prime_intelligence_type"] is not None
    primes = [r for r in _journal_records(twins_home) if r["record_kind"] == "prime_organism"]
    assert len(primes) == 1
    assert primes[0]["wave"] == 2
    assert primes[0]["wave_parity"] == "prime"


def test_odd_sets_flagged_xi_track_exactly(twins_home):
    sym.run_cycle("sym-20270303-0000")
    sets = [r for r in _journal_records(twins_home) if r["record_kind"] == "set"]
    assert len(sets) >= 5
    for s in sets:
        assert s["xi_organism_track"] == (s["set_index"] % 2 == 1), s["set_index"]
    assert any(s["xi_organism_track"] for s in sets)
    assert any(not s["xi_organism_track"] for s in sets)


def test_prime_organism_passes_operator_contract():
    for prime_index, wave in ((1, 2), (2, 4), (3, 6)):
        rec = prime.spawn_prime_organism("sym-20270404-0000", wave=wave, prime_index=prime_index)
        for orec in rec["operators"]:
            op = prime.organism_from_record(orec)
            validate_operator(op)  # raises on any violation
            result = op.step([], [], {})
            assert result.ok
            assert result.finish_reason == "stop"


def test_supra_manifest_has_all_four_keys():
    entry = it.get("echo_mirror")
    manifest = prime.build_supra_manifest(entry)
    for key in ("tools", "engines", "methods", "morals"):
        assert key in manifest, key
    assert len(manifest["tools"]) >= 1
    assert len(manifest["engines"]) >= 1
    assert len(manifest["methods"]) >= 1
    morals = manifest["morals"]
    assert isinstance(morals["charter"], list) and len(morals["charter"]) >= 5
    assert morals["bound"] is True
    assert morals["amendments"] == "keeper-only"


def test_prime_form_duo_on_odd_prime_waves_single_on_even():
    duo = prime.spawn_prime_organism("sym-20270505-0000", wave=2, prime_index=1)
    assert duo["prime_form"] == "duo"
    assert len(duo["operators"]) == 2
    a, b = duo["operators"]
    assert a["symbiont_id"] == b["id"]
    assert b["symbiont_id"] == a["id"]
    assert duo["symbiotic_link"]["bidirectional"] is True
    single = prime.spawn_prime_organism("sym-20270505-0600", wave=4, prime_index=2)
    assert single["prime_form"] == "single"
    assert len(single["operators"]) == 1
    assert "symbiotic_link" not in single


def test_catalog_entries_carry_provenance():
    entries = it.catalog()
    assert len(entries) >= 6 + 3  # unattempted moat + documented
    pools = it.pools()
    assert set(pools) == {"unattempted", "documented"}
    for e in entries:
        for key in ("id", "pool", "name", "description", "provenance"):
            assert key in e, (e.get("id"), key)
        prov = e["provenance"]
        assert "studied_from" in prov and "changed" in prov, e["id"]
        if e["pool"] == "unattempted":
            assert prov["studied_from"] is None  # LEVI-native from birth
        else:
            assert prov["studied_from"]  # documented: studied reference named
            assert prov["changed"]


def test_choose_type_moat_first_and_deterministic():
    first_prime = it.choose_type(12345, 1)
    assert first_prime["pool"] == "unattempted"
    second_prime = it.choose_type(12345, 2)
    assert second_prime["pool"] == "documented"
    assert it.choose_type(999, 3) == it.choose_type(999, 3)


def test_services_dual_market_with_stub_quotes():
    for type_id in [e["id"] for e in it.catalog()]:
        services = prime.services_for(type_id)
        markets = {s["market"] for s in services}
        assert markets == {"human", "post_llm"}, type_id
        for s in services:
            assert s["name"] and s["description"]
            q = s["quote"]
            assert q["quote_via"] == "price_advisor"
            assert q["settlement_via"] == "cybrus"
            assert "STUB" in q["status"]
            assert q["pricing_model"] in ("genesis_lifetime", "metered_per_call")


def test_services_have_no_payment_wiring():
    src = pathlib.Path(prime.__file__).read_text(encoding="utf-8")
    for token in ("stripe", "charge_card", "card_number", "cvv", "def charge"):
        assert token not in src.lower(), token


def test_prime_spawn_deterministic():
    r1 = prime.spawn_prime_organism("sym-20270606-0000", wave=2, prime_index=1)
    r2 = prime.spawn_prime_organism("sym-20270606-0000", wave=2, prime_index=1)
    assert r1 == r2


def test_prime_wave_rerun_idempotent(twins_home):
    first = sym.run_cycle("sym-20270707-0600")  # wave 1 standard
    second = sym.run_cycle("sym-20270707-1200")  # wave 2 prime
    assert second["wave_parity"] == "prime"
    journal = twins_home / "symbiotic" / "spawn_journal.jsonl"
    lines_before = journal.read_text(encoding="utf-8").count("\n")

    again = sym.run_cycle("sym-20270707-1200")
    assert again["duplicate_run"] is True
    assert again["wave"] == second["wave"] == 2
    assert again["wave_parity"] == "prime"
    assert again["prime_organism_id"] == second["prime_organism_id"]
    assert journal.read_text(encoding="utf-8").count("\n") == lines_before

    # a fresh third cycle continues the wave count, not restarts it
    third = sym.run_cycle("sym-20270707-1800")
    assert (third["wave"], third["wave_parity"]) == (3, "standard")
    assert first["wave"] == 1


def test_growth_hook_sees_wave_and_prime(twins_home, tmp_path, monkeypatch):
    growth = tmp_path / "growth"
    monkeypatch.setenv("LEVI_GROWTH_DIR", str(growth))
    sym.run_cycle("sym-20270808-0000")  # wave 1
    sym.run_cycle("sym-20270808-0600")  # wave 2 prime
    kinds = [
        json.loads(line)
        for line in (growth / "journal.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    spawns = [k for k in kinds if k.get("kind") == "twin_spawn"]
    assert [s["wave"] for s in spawns] == [1, 2]
    assert spawns[1]["wave_parity"] == "prime"
    assert spawns[1]["prime_organism_id"] is not None


def test_no_outside_randomness_in_new_modules():
    for mod in (prime, it):
        src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
        assert "import secrets" not in src
        assert "SystemRandom" not in src
        assert "os.urandom" not in src
    assert "random.Random(" in pathlib.Path(prime.__file__).read_text(encoding="utf-8")
    assert "random.Random(" in pathlib.Path(it.__file__).read_text(encoding="utf-8")
