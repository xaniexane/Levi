"""Tests for levi.attention — addressed wake-signaling and the answer-tone ritual."""

from __future__ import annotations

import pytest

from levi.attention.ritual import RitualError, answer, confirm, probe
from levi.attention.signal import AttentionBus, validate_code


def test_only_addressed_wakes():
    bus = AttentionBus()
    bus.subscribe(("growth", "tick"), "growth-cycle")
    bus.subscribe(("mesh", "pair"), "fleet-node")
    assert bus.signal(("growth", "tick")) == ["growth-cycle"]
    assert bus.signal(("nobody", "home")) == []


def test_bad_codes_rejected():
    bus = AttentionBus()
    with pytest.raises(ValueError):
        bus.subscribe(("only-one",), "x")
    with pytest.raises(ValueError):
        bus.subscribe(("UPPER", "case"), "x")  # lowercase only
    with pytest.raises(ValueError):
        bus.signal(("a", "b", "c"))


def test_validate_code_roundtrip():
    assert validate_code(("mesh", "pair")) == ("mesh", "pair")


def test_audit_counts_silence():
    bus = AttentionBus()
    bus.subscribe(("news", "refresh"), "news-ingest")
    bus.signal(("news", "refresh"))
    bus.signal(("news", "refresh"))
    bus.signal(("void", "static"))
    audit = bus.audit()
    assert audit["signals"] == 3
    assert audit["matched"] == 2
    assert audit["ignored"] == 1
    assert audit["per_code"]["news:refresh"] == 2


def test_unsubscribe_stays_quiet():
    bus = AttentionBus()
    bus.subscribe(("news", "refresh"), "news-ingest")
    bus.unsubscribe(("news", "refresh"), "news-ingest")
    assert bus.signal(("news", "refresh")) == []


def test_ritual_full_ceremony():
    p = probe("node-alpha", ["store", "compute", "relay"])
    a = answer("node-beta", p, ["compute", "relay"], terms="credits-for-spare")
    s = confirm(p, a)
    assert s.shared == frozenset({"compute", "relay"})
    assert s.terms == "credits-for-spare"


def test_ritual_caps_normalized():
    p = probe("n1", [" Store ", "COMPUTE"])
    a = answer("n2", p, ["store"])
    assert confirm(p, a).shared == frozenset({"store"})


def test_ritual_answer_without_probe_refused():
    with pytest.raises(RitualError):
        answer("n2", "not-a-probe", ["compute"])


def test_ritual_confirm_without_answer_refused():
    p = probe("n1", ["compute"])
    with pytest.raises(RitualError):
        confirm(p, "not-an-answer")


def test_ritual_no_shared_capability_aborts_honestly():
    p = probe("node-gamma", ["store"])
    a = answer("node-delta", p, ["compute"])
    with pytest.raises(RitualError, match="no shared capability"):
        confirm(p, a)


def test_ritual_mismatched_initiator_refused():
    p1 = probe("node-a", ["compute"])
    p2 = probe("node-b", ["compute"])
    a = answer("node-c", p1, ["compute"])
    with pytest.raises(RitualError, match="not"):
        confirm(p2, a)


def test_ritual_empty_probe_refused():
    with pytest.raises(RitualError):
        probe("", ["compute"])
    with pytest.raises(RitualError):
        probe("n1", [])


def test_demo_cli():
    from levi.attention.__main__ import main

    assert main(["demo"]) == 0
