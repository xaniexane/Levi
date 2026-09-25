"""BLUE regression tests: stale PolicyEngine fail-open after revocation
(RED-1 batch A, confirmation of RED-3 finding 18, L7).

Fail-closed: every evaluate() resolves against the registered
originals on disk — a long-lived engine sees revocations and newly
registered denies on its very next decision. The legitimate path
(default-deny, deny-wins, strictest-risk) is unchanged.
"""

import pytest

from levi.cybrus.policy import PolicyEngine


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


def _revoke_allow_and_deny(subject="mallory", resource="vault.tokens", action="read"):
    other = PolicyEngine()
    idx = next(
        i
        for i, r in enumerate(other.list_rules())
        if r.get("subject") == subject and r.get("effect") == "allow"
    )
    other.remove_rule(idx)
    other.add_rule(subject, resource, action, "deny", "critical")


class TestStaleEngineSeesRevocation:
    def test_long_lived_engine_denies_after_revoke(self, home):
        engine = PolicyEngine()
        engine.add_rule("mallory", "vault.tokens", "read", "allow", "low")
        holder = PolicyEngine()  # long-lived holder of the allow
        assert holder.evaluate("mallory", "vault.tokens", "read").decision == "allow"

        _revoke_allow_and_deny()

        d = holder.evaluate("mallory", "vault.tokens", "read")
        assert d.decision == "deny"
        assert (d.matched_rule or {}).get("effect") == "deny"

    def test_long_lived_engine_sees_new_allow(self, home):
        holder = PolicyEngine()
        assert holder.evaluate("mallory", "vault.tokens", "read").decision == "deny"
        PolicyEngine().add_rule("mallory", "vault.tokens", "read", "allow", "low")
        d = holder.evaluate("mallory", "vault.tokens", "read")
        assert d.decision == "allow"
        assert (d.matched_rule or {}).get("effect") == "allow"

    def test_long_lived_engine_sees_deny_wins(self, home):
        holder = PolicyEngine()
        holder.add_rule("mallory", "vault.tokens", "read", "allow", "low")
        assert holder.evaluate("mallory", "vault.tokens", "read").decision == "allow"
        # A deny registered elsewhere beats the remembered allow.
        PolicyEngine().add_rule("mallory", "vault.tokens", "read", "deny", "high")
        d = holder.evaluate("mallory", "vault.tokens", "read")
        assert d.decision == "deny"

    def test_list_rules_is_current(self, home):
        holder = PolicyEngine()
        holder.add_rule("mallory", "vault.tokens", "read", "allow", "low")
        assert any(r["subject"] == "mallory" for r in holder.list_rules())
        _revoke_allow_and_deny()
        rules = holder.list_rules()
        assert not any(
            r.get("subject") == "mallory" and r.get("effect") == "allow"
            for r in rules
        )
        assert any(
            r.get("subject") == "mallory" and r.get("effect") == "deny"
            for r in rules
        )


class TestLegitimateSemanticsUnchanged:
    def test_default_deny_and_deny_wins(self, home):
        eng = PolicyEngine()
        d = eng.evaluate("nobody", "vault.tokens", "read")
        assert d.decision == "deny" and d.matched_rule is None
        eng.add_rule("mallory", "vault.tokens", "read", "allow", "low")
        eng.add_rule("mallory", "vault.tokens", "read", "deny", "high")
        assert eng.evaluate("mallory", "vault.tokens", "read").decision == "deny"

    def test_strictest_risk_ceiling(self, home):
        eng = PolicyEngine()
        eng.add_rule("mallory", "vault.tokens", "read", "allow", "low")
        eng.add_rule("mallory", "vault.*", "read", "allow", "high")
        d = eng.evaluate("mallory", "vault.tokens", "read")
        assert d.decision == "allow" and d.risk == "high"
