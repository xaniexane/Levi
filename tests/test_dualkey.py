"""Tests for levi.dualkey -- dual-key consent gates."""

import pytest

from levi.dualkey import DualKeyGate, GateRegistry, check


def test_both_keys_open_the_gate():
    gate = DualKeyGate("cloud-escalation")
    verdict = gate.check(standing=True, requested=True)
    assert verdict.allowed is True
    assert verdict.reason == "both keys turned"


@pytest.mark.parametrize(
    "standing,requested,fragment",
    [
        (True, False, "no per-action permission"),
        (False, True, "standing policy forbids"),
        (False, False, "denied"),
    ],
)
def test_one_key_alone_denies(standing, requested, fragment):
    verdict = DualKeyGate("x").check(standing, requested)
    assert verdict.allowed is False
    assert fragment in verdict.reason


def test_receipt_shape():
    verdict = DualKeyGate("sync-export", "off-machine copies").check(True, True)
    r = verdict.receipt()
    assert r == {
        "gate": "sync-export",
        "allowed": True,
        "standing_key": True,
        "request_key": True,
        "reason": "both keys turned",
        "at": verdict.at,
    }


def test_registry_unknown_gate_raises():
    reg = GateRegistry()
    with pytest.raises(KeyError):
        reg.check("nope", True, True)


def test_registry_duplicate_register_raises():
    reg = GateRegistry()
    reg.register(DualKeyGate("a"))
    with pytest.raises(ValueError):
        reg.register(DualKeyGate("a"))


def test_registry_audit_trail():
    reg = GateRegistry()
    reg.register(DualKeyGate("g", "desc"))
    reg.check("g", True, False)
    trail = reg.audit_trail()
    assert len(trail) == 1
    assert trail[0]["allowed"] is False
    assert reg.gates() == {"g": "desc"}


def test_default_check_bool_and_mapping():
    ok = check("cloud-escalation", True, requested=True)
    assert ok.allowed is True
    denied = check("cloud-escalation", {"allowed": True}, requested=False)
    assert denied.allowed is False
    missing_key = check("sync-export", {}, requested=True)
    assert missing_key.allowed is False
