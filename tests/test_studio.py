"""Proof tests for the Omega Studio consent kit (core/levi/studio/).

Law -> guard -> prove: the laws are deny-by-default, deny-overrides-allow,
append-only audited consent, and tamper-evident trails. These tests are the
proof — they must stay green.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from levi.studio import (  # noqa: E402
    AuditTrail,
    ConsentError,
    ConsentGate,
    Policy,
    PolicyError,
)

POLICY = """
package consent

default allow = false

allow {
  input.action == "read"
  input.risk == "low"
}

allow {
  input.role in ["admin", "owner"]
}

deny {
  input.side_effects == true
  input.actor_trust == "untrusted"
}
"""


# ---------------------------------------------------------------- policy


def test_policy_allow_match():
    p = Policy.from_rego(POLICY)
    assert p.decide({"action": "read", "risk": "low"}) == "allow"


def test_policy_deny_overrides_allow():
    p = Policy.from_rego(POLICY)
    assert p.decide({
        "action": "read", "risk": "low",
        "side_effects": True, "actor_trust": "untrusted",
    }) == "deny"


def test_policy_default_deny_when_nothing_matches():
    p = Policy.from_rego(POLICY)
    assert p.decide({"action": "write", "risk": "high", "role": "user"}) == "deny"


def test_policy_in_operator_and_numeric():
    p = Policy.from_rego(POLICY)
    assert p.decide({"role": "admin"}) == "allow"
    assert p.decide({"role": "intern"}) == "deny"


def test_policy_unparseable_is_refused_never_guessed():
    with pytest.raises(PolicyError):
        Policy.from_rego("allow { input.x =+ 1 }")
    with pytest.raises(PolicyError):
        Policy.from_rego("allow { input.x === 1 }")
    with pytest.raises(PolicyError):
        Policy.from_rego("permit { input.x == 1 }")


def test_policy_missing_field_is_false_not_permit():
    p = Policy.from_rego(POLICY)
    # No 'action'/'risk' fields at all: no allow rule can match.
    assert p.decide({}) == "deny"


def test_policy_non_dict_input_is_deny():
    p = Policy.from_rego(POLICY)
    assert p.decide("read") == "deny"
    assert p.decide(None) == "deny"


def test_policy_bool_int_no_crosstalk():
    p = Policy.from_rego('package c\nallow { input.n == 1 }')
    assert p.decide({"n": True}) == "deny"  # True == 1 in Python; strict eq says no
    assert p.decide({"n": 1}) == "allow"


def test_policy_deterministic():
    p = Policy.from_rego(POLICY)
    data = {"action": "read", "risk": "low"}
    assert p.decide(data) == p.decide(data) == "allow"


# ---------------------------------------------------------------- audit


def _trail(tmp_path):
    return AuditTrail.open(tmp_path / "audit")


def test_audit_append_and_verify_clean(tmp_path):
    t = _trail(tmp_path)
    t.append("consent.requested", {"action": "write"})
    t.append("consent.granted", {"by": "chauncey"})
    ok, findings = t.verify()
    assert ok, findings
    assert "2 record(s)" in findings[0]


def test_audit_tamper_detected(tmp_path):
    t = _trail(tmp_path)
    t.append("consent.requested", {"action": "write", "actor": "agent"})
    p = tmp_path / "audit" / "trail.jsonl"
    rec = json.loads(p.read_text().splitlines()[0])
    rec["payload"]["actor"] = "mallory"
    p.write_text(json.dumps(rec) + "\n")
    ok, findings = t.verify()
    assert not ok
    assert "bad MAC" in findings[0]


def test_audit_truncation_detected(tmp_path):
    t = _trail(tmp_path)
    t.append("a", {})
    t.append("b", {})
    p = tmp_path / "audit" / "trail.jsonl"
    p.write_text(p.read_text().splitlines()[1] + "\n")  # drop record 1
    ok, findings = t.verify()
    assert not ok
    assert "broken chain link" in findings[0]


def test_audit_reorder_detected(tmp_path):
    t = _trail(tmp_path)
    t.append("a", {})
    t.append("b", {})
    p = tmp_path / "audit" / "trail.jsonl"
    lines = p.read_text().splitlines()
    p.write_text("\n".join(reversed(lines)) + "\n")
    ok, _ = t.verify()
    assert not ok


def test_audit_empty_verifies_cleanly_not_as_tamper(tmp_path):
    t = _trail(tmp_path)
    ok, findings = t.verify()
    assert ok and "0 record(s)" in findings[0]


def test_audit_key_owner_only_posix(tmp_path):
    import os

    t = _trail(tmp_path)
    t.append("x", {})
    if os.name == "posix":
        import stat

        mode = stat.S_IMODE(os.stat(tmp_path / "audit" / "key.bin").st_mode)
        assert mode == 0o600


# ---------------------------------------------------------------- consent


def _gate(tmp_path, ttl=900):
    return ConsentGate(Policy.from_rego(POLICY), tmp_path / "gate", ttl_seconds=ttl)


def test_consent_request_pending_when_policy_allows(tmp_path):
    g = _gate(tmp_path)
    req = g.request("read", "agent", "notes.md", {"risk": "low"})
    assert req.status == "pending"
    assert req.policy_decision == "allow"


def test_consent_policy_deny_short_circuits(tmp_path):
    g = _gate(tmp_path)
    req = g.request("write", "agent", "prod.db",
                    {"side_effects": True, "actor_trust": "untrusted"})
    assert req.status == "denied"
    assert "policy" in req.reason


def test_consent_approve_grants_and_consumes_once(tmp_path):
    g = _gate(tmp_path)
    req = g.request("read", "agent", "notes.md", {"risk": "low"})
    g.approve(req.id, "chauncey")
    assert g.is_granted(req.id)
    assert g.consume(req.id) is True
    assert g.is_granted(req.id) is False  # consumed: no silent re-use
    assert g.consume(req.id) is False


def test_consent_deny_needs_reason(tmp_path):
    g = _gate(tmp_path)
    req = g.request("read", "agent", "notes.md", {"risk": "low"})
    with pytest.raises(ConsentError):
        g.deny(req.id, "chauncey", "")
    g.deny(req.id, "chauncey", "not today")
    assert not g.is_granted(req.id)


def test_consent_undecided_is_denied(tmp_path):
    g = _gate(tmp_path)
    req = g.request("read", "agent", "notes.md", {"risk": "low"})
    assert not g.is_granted(req.id)  # pending != granted


def test_consent_unknown_id_is_denied(tmp_path):
    g = _gate(tmp_path)
    assert not g.is_granted("cr_nope")


def test_consent_expiry_counts_as_denied(tmp_path):
    g = ConsentGate(Policy.from_rego(POLICY), tmp_path / "gate", ttl_seconds=1)
    req = g.request("read", "agent", "notes.md", {"risk": "low"})
    # Force expiry without sleeping.
    req.expires_at = "2000-01-01T00:00:00+00:00"
    assert g.get(req.id).status == "expired"
    assert not g.is_granted(req.id)
    with pytest.raises(ConsentError):
        g.approve(req.id, "chauncey")


def test_consent_everything_audited(tmp_path):
    g = _gate(tmp_path)
    req = g.request("read", "agent", "notes.md", {"risk": "low"})
    g.approve(req.id, "chauncey")
    g.consume(req.id)
    ok, findings = g.verify_audit()
    assert ok, findings
    events = [r["event"] for r in g.audit.read()]
    assert events == ["consent.requested", "consent.granted", "consent.consumed"]
