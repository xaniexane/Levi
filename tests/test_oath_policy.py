"""Policy-gate tests for LEVI Oath (core/levi/oath/policy.py).

Pure logic: no gpg, no network, no HOME writes beyond a tmp dir.  Covers
the enforcement order — trust gate (hard requirement, no override),
deny-closed permissions, risk-ceiling inheritance — plus rate limiting.
"""

import inspect
import socket

import pytest

from levi.oath.commands import CommandDefinition
from levi.oath.contacts import Contact
from levi.oath.policy import (
    check_command,
    check_pipeline,
    trust_gate,
    trust_meets_floor,
)
from levi.oath.trust import TRUSTED, UNTRUSTED, UNVERIFIED, VERIFIED


@pytest.fixture
def no_network(monkeypatch):
    def _blocked(self, addr, *a, **k):
        raise RuntimeError("network disabled in tests")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    yield


@pytest.fixture
def hermetic_home(tmp_path, monkeypatch):
    home = tmp_path / "oath-home"
    monkeypatch.setenv("LEVI_OATH_HOME", str(home))
    return home


def _contact(**kw) -> Contact:
    base = dict(name="carol", email="carol@example.com", trust_floor=VERIFIED,
                tier_ceiling="write", grants={}, max_missions_per_hour=10)
    base.update(kw)
    return Contact(**base)


def _cmd(name: str, tier: str) -> CommandDefinition:
    return CommandDefinition(name=name, argv=["/bin/true"], args={}, tier=tier)


# ---------------------------------------------------------------------------
# gate 1 — trust (hard requirement, no override)
# ---------------------------------------------------------------------------

def test_trust_gate_hard_floor(hermetic_home, no_network):
    contact = _contact()
    assert trust_gate(contact, UNVERIFIED).allowed is False
    assert trust_gate(contact, UNTRUSTED).allowed is False
    assert trust_gate(contact, VERIFIED).allowed is True
    assert trust_gate(contact, TRUSTED).allowed is True


def test_trust_gate_floor_can_be_raised_not_lowered(hermetic_home, no_network):
    contact = _contact(trust_floor=TRUSTED)
    assert trust_gate(contact, VERIFIED).allowed is False
    assert trust_gate(contact, TRUSTED).allowed is True
    with pytest.raises(ValueError):
        _contact(trust_floor="UNVERIFIED")


def test_trust_gate_has_no_override_parameter(hermetic_home, no_network):
    params = inspect.signature(trust_gate).parameters
    assert "override" not in params
    assert "skip" not in params


def test_trust_ordering(hermetic_home, no_network):
    assert trust_meets_floor(TRUSTED, VERIFIED)
    assert trust_meets_floor(VERIFIED, VERIFIED)
    assert not trust_meets_floor(UNTRUSTED, VERIFIED)
    assert not trust_meets_floor(UNVERIFIED, VERIFIED)
    assert not trust_meets_floor("BOGUS", VERIFIED)


# ---------------------------------------------------------------------------
# gate 2 — deny-closed permissions
# ---------------------------------------------------------------------------

def test_deny_closed_no_grants(hermetic_home, no_network):
    decision = check_command(_contact(), _cmd("disk-usage", "read"))
    assert decision.allowed is False
    assert decision.gate == "permission"
    assert "denied" in decision.reason


def test_grant_letter_must_match_tier(hermetic_home, no_network):
    contact = _contact(grants={"disk-usage": ["r"]})
    assert check_command(contact, _cmd("disk-usage", "read")).allowed is True
    # an r grant does not cover a write-tier command of the same name
    assert check_command(contact, _cmd("disk-usage", "write")).allowed is False
    contact2 = _contact(grants={"backup": ["w"]})
    assert check_command(contact2, _cmd("backup", "write")).allowed is True


def test_grant_is_per_command(hermetic_home, no_network):
    contact = _contact(grants={"a": ["r"]})
    assert check_command(contact, _cmd("b", "read")).allowed is False


# ---------------------------------------------------------------------------
# gate 3 — risk-ceiling inheritance
# ---------------------------------------------------------------------------

def test_ceiling_blocks_above_ceiling(hermetic_home, no_network):
    contact = _contact(grants={"pipe": ["x"]}, tier_ceiling="write")
    decision = check_command(contact, _cmd("pipe", "execute"))
    assert decision.allowed is False
    assert decision.gate == "risk-ceiling"


def test_ceiling_allows_at_ceiling(hermetic_home, no_network):
    contact = _contact(grants={"pipe": ["x"]}, tier_ceiling="execute")
    assert check_command(contact, _cmd("pipe", "execute")).allowed is True


def test_dangerous_needs_explicit_d_grant(hermetic_home, no_network):
    # ceiling alone is not enough, even at dangerous
    contact = _contact(grants={"nuke": ["x"]}, tier_ceiling="dangerous")
    decision = check_command(contact, _cmd("nuke", "dangerous"))
    assert decision.allowed is False
    assert decision.gate == "permission"
    # explicit d grant on that exact command authorises it
    contact2 = _contact(grants={"nuke": ["d"]}, tier_ceiling="dangerous")
    assert check_command(contact2, _cmd("nuke", "dangerous")).allowed is True


def test_builtin_ai_stage_needs_x_grant(hermetic_home, no_network):
    from levi.oath.commands import CommandRegistry

    registry = CommandRegistry()
    ai = registry.get("ai")
    assert ai.tier == "execute"
    assert check_command(_contact(grants={"ai": ["r"]}, tier_ceiling="execute"), ai).allowed is False
    assert check_command(_contact(grants={"ai": ["x"]}, tier_ceiling="execute"), ai).allowed is True


def test_check_pipeline_reports_first_denial(hermetic_home, no_network):
    from levi.oath.commands import CommandRegistry

    registry = CommandRegistry()
    contact = _contact(grants={"ai": ["x"]}, tier_ceiling="execute")
    stages = [
        {"kind": "cmd", "name": "nope", "args": {}, "raw": "cmd:nope"},
        {"kind": "ai", "name": "ai", "args": {"prompt": "hi"}, "raw": "ai:hi"},
    ]
    decisions = check_pipeline(contact, stages, registry)
    assert decisions[0].allowed is False  # unknown command -> deny
    assert decisions[1].allowed is True


# ---------------------------------------------------------------------------
# rate limiting
# ---------------------------------------------------------------------------

def test_rate_limit(hermetic_home, no_network):
    from levi.oath.daemon import check_rate_limit, record_mission_use

    contact = _contact(max_missions_per_hour=2)
    now = 1_700_000_000.0
    assert check_rate_limit(contact, now=now).allowed is True
    record_mission_use(contact, now=now)
    record_mission_use(contact, now=now + 10)
    decision = check_rate_limit(contact, now=now + 20)
    assert decision.allowed is False
    assert decision.gate == "rate-limit"
    # budget refills after an hour
    assert check_rate_limit(contact, now=now + 3700).allowed is True


def test_rate_limit_zero_means_none(hermetic_home, no_network):
    from levi.oath.daemon import check_rate_limit

    contact = _contact(max_missions_per_hour=0)
    assert check_rate_limit(contact).allowed is False
