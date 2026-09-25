"""BLUE regression tests: PolicyEngine resolves against the registered
originals (L7 — the policy side of L3 "deny always wins").

Guards the RED-1 stale-engine fix at the LAW level: a long-lived
``PolicyEngine`` must see revocations, new allows, and new denies made by
other engine instances — there is no fail-open window where a revoked
allow keeps authorizing.

Glyph: ⚖️ (L1–L5 verification pass, 2026-09-22).
"""

import pytest

from levi.cybrus.policy import PolicyEngine


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


def _remove_rule_by_subject(engine, subject, effect="allow"):
    idx = next(
        i
        for i, r in enumerate(engine.list_rules())
        if r.get("subject") == subject and r.get("effect") == effect
    )
    engine.remove_rule(idx)


class TestLongLivedEngineSeesCurrentRules:
    def test_revoked_allow_fails_closed(self, home):
        engine = PolicyEngine()
        engine.add_rule("mallory", "vault.tokens", "read", "allow", "low")
        holder = PolicyEngine()  # long-lived holder of the allow
        assert holder.evaluate("mallory", "vault.tokens", "read").decision == "allow"

        # The keeper revokes the allow and registers a deny (persisted).
        other = PolicyEngine()
        _remove_rule_by_subject(other, "mallory", "allow")
        other.add_rule("mallory", "vault.tokens", "read", "deny", "critical")

        d = holder.evaluate("mallory", "vault.tokens", "read")
        assert d.decision == "deny", (
            f"stale engine fail-open after revocation: {d.decision} "
            f"(matched={d.matched_rule})"
        )
        assert (d.matched_rule or {}).get("effect") == "deny"

    def test_newly_registered_allow_is_visible(self, home):
        holder = PolicyEngine()
        assert holder.evaluate("svc-new", "vault.tokens", "read").decision == "deny"

        other = PolicyEngine()
        other.add_rule("svc-new", "vault.tokens", "read", "allow", "low")

        d = holder.evaluate("svc-new", "vault.tokens", "read")
        assert d.decision == "allow"
        assert (d.matched_rule or {}).get("effect") == "allow"

    def test_newly_registered_deny_overrides_cached_allow(self, home):
        engine = PolicyEngine()
        engine.add_rule("svc-both", "vault.tokens", "read", "allow", "low")
        holder = PolicyEngine()
        assert holder.evaluate("svc-both", "vault.tokens", "read").decision == "allow"

        other = PolicyEngine()
        other.add_rule("svc-both", "vault.tokens", "read", "deny", "critical")

        # L3: policy deny always wins — no bypass, no stale allow.
        d = holder.evaluate("svc-both", "vault.tokens", "read")
        assert d.decision == "deny"

    def test_rule_removal_is_visible_in_list_rules(self, home):
        engine = PolicyEngine()
        engine.add_rule("svc-gone", "vault.tokens", "read", "allow", "low")
        holder = PolicyEngine()
        assert any(
            r.get("subject") == "svc-gone" for r in holder.list_rules()
        )

        other = PolicyEngine()
        _remove_rule_by_subject(other, "svc-gone", "allow")

        assert not any(
            r.get("subject") == "svc-gone" and r.get("effect") == "allow"
            for r in holder.list_rules()
        )
        # With the allow gone, the decision falls back to default-deny.
        assert holder.evaluate("svc-gone", "vault.tokens", "read").decision == "deny"

    def test_repeated_evaluate_is_stable_without_changes(self, home):
        engine = PolicyEngine()
        engine.add_rule("svc-stable", "vault.tokens", "read", "allow", "low")
        holder = PolicyEngine()
        for _ in range(3):
            d = holder.evaluate("svc-stable", "vault.tokens", "read")
            assert d.decision == "allow"
