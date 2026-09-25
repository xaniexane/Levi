"""Proof for GenEX laws: append-only, hash chain, conservation, determinism."""

import pytest

from levi.genex import GenexLedger
from levi.genex.ledger import GenexError


def _ledger():
    return GenexLedger()


def test_append_only_no_mutation_api():
    led = _ledger()
    # Law 1: there is simply no way to mutate or delete an entry.
    assert not hasattr(led, "update")
    assert not hasattr(led, "delete")
    assert not hasattr(led, "remove")
    e = led.issue("GOLD", "alice", 100)
    assert len(led.history()) == 1
    assert led.history()[0]["hash"] == e.hash


def test_hash_chain_verifies():
    led = _ledger()
    led.issue("GOLD", "alice", 100, at="2026-09-22T00:00:00Z")
    led.transfer("GOLD", "alice", "bob", 40, at="2026-09-22T01:00:00Z")
    led.retire("GOLD", "bob", 10, at="2026-09-22T02:00:00Z")
    result = led.verify_chain()
    assert result == {"ok": True, "entries": 3}


def test_chain_detects_tamper():
    led = _ledger()
    led.issue("GOLD", "alice", 100)
    # Tamper with the stored entry object directly.
    entry = led._entries[0]
    object.__setattr__(entry, "amount", 999)
    result = led.verify_chain()
    assert not result["ok"]
    assert result["seq"] == 0


def test_conservation_across_ops():
    led = _ledger()
    led.issue("GOLD", "alice", 100)
    led.transfer("GOLD", "alice", "bob", 40)
    led.transfer("GOLD", "bob", "carol", 15)
    led.retire("GOLD", "carol", 5)
    # Law 3: sum of balances == issued - retired.
    balances = led.holders("GOLD")
    assert sum(balances.values()) == led.total_supply("GOLD") == 95
    assert balances == {"alice": 60, "bob": 25, "carol": 10}


def test_no_overdraft():
    led = _ledger()
    led.issue("GOLD", "alice", 10)
    with pytest.raises(GenexError):
        led.transfer("GOLD", "alice", "bob", 11)
    with pytest.raises(GenexError):
        led.retire("GOLD", "alice", 11)
    # Failed ops leave no trace.
    assert len(led.history()) == 1


def test_invalid_amounts_refused():
    led = _ledger()
    for bad in (0, -5, 1.5, "10", True):
        with pytest.raises(GenexError):
            led.issue("GOLD", "alice", bad)


def test_determinism_same_ops_same_hashes():
    def build():
        led = _ledger()
        led.issue("GOLD", "alice", 100, at="t0")
        led.transfer("GOLD", "alice", "bob", 40, at="t1")
        return [e["hash"] for e in led.history()]

    assert build() == build()
