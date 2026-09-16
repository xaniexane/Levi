"""Hermetic tests for cybrus governance: policy, approval, audit, devices.

Stdlib-only, no network, no HOME writes: ``LEVI_HOME`` is pointed at
``tmp_path``. The four governance modules are loaded directly from their
file paths so the tests are independent of the sibling engine modules'
landing order on the shared branch.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

CYBRUS_DIR = Path(__file__).resolve().parents[1] / "core" / "levi" / "cybrus"


def load(name):
    spec = importlib.util.spec_from_file_location(
        f"cybrus_governance_{name}", CYBRUS_DIR / f"{name}.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclasses resolves annotations via sys.modules
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture()
def policy(home):
    return load("policy")


@pytest.fixture()
def approval(home):
    return load("approval")


@pytest.fixture()
def audit(home):
    return load("audit")


@pytest.fixture()
def devices(home):
    return load("devices")


@pytest.fixture()
def qid(home):
    return load("qid")


@pytest.fixture()
def tokens_mod(home):
    return load("tokens")


@pytest.fixture()
def gateway(home):
    return load("gateway")


# ---------------------------------------------------------------------------
# policy
# ---------------------------------------------------------------------------

class TestRiskCeiling:
    def test_strictest_wins(self, policy):
        assert policy.risk_of("low", "high") == "high"
        assert policy.risk_of("medium", "low", "critical") == "critical"

    def test_single_and_empty(self, policy):
        assert policy.risk_of("medium") == "medium"
        assert policy.risk_of() == "low"

    def test_unknown_level_rejected(self, policy):
        with pytest.raises(ValueError):
            policy.risk_of("low", "extreme")


class TestPolicyEngine:
    def test_seed_allow(self, policy):
        engine = policy.PolicyEngine()
        d = engine.evaluate("owner", "vault.tokens", "read")
        assert d.decision == "allow"
        assert d.risk == "high"  # seed: vault.* is high-risk

    def test_seed_deny(self, policy):
        engine = policy.PolicyEngine()
        d = engine.evaluate("anyone", "system.kernel", "execute")
        assert d.decision == "deny"
        assert d.risk == "critical"

    def test_default_deny(self, policy):
        engine = policy.PolicyEngine()
        d = engine.evaluate("stranger", "unknown.thing", "frobnicate")
        assert d.decision == "deny"
        assert d.matched_rule is None
        assert "default-deny" in d.reason

    def test_deny_wins_over_allow(self, policy):
        engine = policy.PolicyEngine()
        engine.add_rule("*", "system.*", "execute", "allow", "low")
        d = engine.evaluate("owner", "system.kernel", "execute")
        assert d.decision == "deny"
        assert d.risk == "critical"  # strictest of the matched denies

    def test_strictest_risk_among_allows(self, policy):
        engine = policy.PolicyEngine()
        engine.add_rule("owner", "notes.*", "read", "allow", "low")
        engine.add_rule("owner", "notes.*", "read", "allow", "medium")
        d = engine.evaluate("owner", "notes.diary", "read")
        assert d.decision == "allow"
        assert d.risk == "medium"

    def test_add_rule_validation(self, policy):
        engine = policy.PolicyEngine()
        with pytest.raises(ValueError):
            engine.add_rule("a", "b", "c", "maybe", "low")
        with pytest.raises(ValueError):
            engine.add_rule("a", "b", "c", "allow", "extreme")

    def test_remove_rule(self, policy):
        engine = policy.PolicyEngine()
        n = len(engine.list_rules())
        engine.remove_rule(0)
        assert len(engine.list_rules()) == n - 1

    def test_needs_approval(self, policy):
        engine = policy.PolicyEngine()
        high = engine.evaluate("owner", "vault.tokens", "write")
        assert engine.needs_approval(high) is True
        low = engine.evaluate("owner", "anything", "read")
        assert engine.needs_approval(low) is False
        denied = engine.evaluate("anyone", "system.kernel", "execute")
        assert engine.needs_approval(denied) is False  # denied, not gated

    def test_rules_persist(self, policy, home):
        engine = policy.PolicyEngine()
        engine.add_rule("owner", "lab.*", "*", "allow", "medium")
        engine2 = policy.PolicyEngine()
        d = engine2.evaluate("owner", "lab.bench", "use")
        assert d.decision == "allow" and d.risk == "medium"


# ---------------------------------------------------------------------------
# approval
# ---------------------------------------------------------------------------

class TestApprovalEngine:
    def test_request_then_check_blocked(self, approval):
        engine = approval.ApprovalEngine()
        entry = engine.request_approval("vault.open", "owner", "vault.main", "high")
        assert entry["status"] == "pending"
        assert engine.check(entry["id"]) is False  # high-risk blocked

    def test_approve_unblocks(self, approval):
        engine = approval.ApprovalEngine()
        entry = engine.request_approval("vault.open", "owner", "vault.main", "high")
        engine.approve(entry["id"])
        assert engine.check(entry["id"]) is True

    def test_deny_stays_blocked(self, approval):
        engine = approval.ApprovalEngine()
        entry = engine.request_approval("vault.open", "owner", "vault.main", "high")
        engine.deny(entry["id"], reason="not now")
        assert engine.check(entry["id"]) is False
        with pytest.raises(ValueError):
            engine.approve(entry["id"])  # denied can never be approved

    def test_unknown_id_check_false(self, approval):
        engine = approval.ApprovalEngine()
        assert engine.check("deadbeef" * 4) is False

    def test_prefix_resolution(self, approval):
        engine = approval.ApprovalEngine()
        entry = engine.request_approval("a", "s", "r", "high")
        engine.approve(entry["id"][:8])
        assert engine.check(entry["id"]) is True

    def test_pending_expiry(self, approval):
        engine = approval.ApprovalEngine()
        entry = engine.request_approval(
            "vault.open", "owner", "vault.main", "high", ttl_seconds=-1
        )
        assert entry["status"] == "pending"  # as created...
        assert engine.check(entry["id"]) is False  # ...but already expired
        pendings = engine.pending()
        assert all(p["id"] != entry["id"] for p in pendings)
        all_entries = engine.list_all()
        expired = [e for e in all_entries if e["id"] == entry["id"]][0]
        assert expired["status"] == "expired"
        with pytest.raises(ValueError):
            engine.approve(entry["id"])  # expired can never be approved

    def test_gate_helper(self, approval):
        engine = approval.ApprovalEngine()
        allowed, aid = engine.gate("read", "owner", "notes", "low")
        assert allowed is True and aid is None
        allowed, aid = engine.gate("vault.open", "owner", "vault.main", "critical")
        assert allowed is False and aid
        assert engine.check(aid) is False
        engine.approve(aid)
        assert engine.check(aid) is True


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------

class TestAuditEngine:
    def test_append_and_verify_ok(self, audit):
        engine = audit.AuditEngine()
        engine.append("policy.evaluated", "owner", {"decision": "allow"})
        engine.append("approval.granted", "owner", {"id": "abc"})
        ok, bad = engine.verify()
        assert ok is True and bad is None

    def test_chain_links(self, audit, home):
        engine = audit.AuditEngine()
        first = engine.append("a", "owner")
        second = engine.append("b", "owner")
        assert second["prev"] == first["hash"]
        assert second["seq"] == first["seq"] + 1

    def test_tamper_detected_at_right_index(self, audit, home):
        engine = audit.AuditEngine()
        engine.append("one", "owner", {"note": "aaaa"})
        engine.append("two", "owner", {"note": "bbbb"})
        engine.append("three", "owner", {"note": "cccc"})
        ok, _ = engine.verify()
        assert ok is True
        # Flip a byte inside record 1's details (JSON stays parseable).
        path = next((home / ".levi" / "cybrus").glob("audit.jsonl"))
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 3
        lines[1] = lines[1].replace("bbbb", "bbbc")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        engine2 = audit.AuditEngine()
        ok, bad = engine2.verify()
        assert ok is False
        assert bad == 1

    def test_tail(self, audit):
        engine = audit.AuditEngine()
        for i in range(5):
            engine.append(f"event-{i}", "owner")
        tail = engine.tail(2)
        assert [r["event"] for r in tail] == ["event-3", "event-4"]

    def test_file_is_owner_only(self, audit, home):
        engine = audit.AuditEngine()
        engine.append("x", "owner")
        path = next((home / ".levi" / "cybrus").glob("audit.jsonl"))
        assert oct(path.stat().st_mode & 0o777) == "0o600"

    def test_verify_empty_log(self, audit):
        engine = audit.AuditEngine()
        assert engine.verify() == (True, None)


# ---------------------------------------------------------------------------
# devices
# ---------------------------------------------------------------------------

class TestDeviceTrust:
    def test_enroll_defaults_untrusted(self, devices):
        trust = devices.DeviceTrust()
        rec = trust.enroll("dev-1", "Chauncey's phone")
        assert rec["trust"] == "untrusted"
        assert trust.is_trusted("dev-1") is False

    def test_set_trust_levels(self, devices):
        trust = devices.DeviceTrust()
        trust.enroll("dev-1", "phone")
        trust.set_trust("dev-1", "known")
        assert trust.get("dev-1")["trust"] == "known"
        assert trust.is_trusted("dev-1") is False
        trust.set_trust("dev-1", "trusted")
        assert trust.is_trusted("dev-1") is True

    def test_unknown_level_rejected(self, devices):
        trust = devices.DeviceTrust()
        trust.enroll("dev-1", "phone")
        with pytest.raises(ValueError):
            trust.set_trust("dev-1", "supertrusted")

    def test_duplicate_enroll_rejected(self, devices):
        trust = devices.DeviceTrust()
        trust.enroll("dev-1", "phone")
        with pytest.raises(ValueError):
            trust.enroll("dev-1", "phone again")

    def test_revoke(self, devices):
        trust = devices.DeviceTrust()
        trust.enroll("dev-1", "phone")
        assert trust.revoke("dev-1") is True
        assert trust.get("dev-1") is None
        assert trust.list() == []
        with pytest.raises(KeyError):
            trust.revoke("dev-1")

    def test_list(self, devices):
        trust = devices.DeviceTrust()
        trust.enroll("dev-1", "phone")
        trust.enroll("dev-2", "laptop")
        assert len(trust.list()) == 2

    def test_trust_at_least(self, devices):
        trust = devices.DeviceTrust()
        trust.enroll("dev-1", "phone")
        trust.set_trust("dev-1", "known")
        assert trust.trust_at_least("dev-1", "untrusted") is True
        assert trust.trust_at_least("dev-1", "known") is True
        assert trust.trust_at_least("dev-1", "trusted") is False
        assert trust.trust_at_least("nope", "untrusted") is False


# ---------------------------------------------------------------------------
# governance integration: policy high-risk + approval pending = blocked
# ---------------------------------------------------------------------------

class TestGovernanceIntegration:
    def test_high_risk_allow_requires_approval(self, policy, approval):
        pe = policy.PolicyEngine()
        ae = approval.ApprovalEngine()
        decision = pe.evaluate("owner", "vault.main", "open")
        assert decision.decision == "allow"
        assert pe.needs_approval(decision) is True
        allowed, aid = ae.gate("vault.open", "owner", "vault.main", decision.risk)
        assert allowed is False and aid is not None
        assert ae.check(aid) is False  # blocked while pending
        ae.approve(aid)
        assert ae.check(aid) is True  # unblocked after human approval

    def test_denied_action_never_reaches_gate(self, policy):
        pe = policy.PolicyEngine()
        decision = pe.evaluate("owner", "system.kernel", "execute")
        assert decision.decision == "deny"
        assert pe.needs_approval(decision) is False

# ---------------------------------------------------------------------------
# QID addressing ("QID = address of thought")
# ---------------------------------------------------------------------------

class TestQID:
    def test_parse_format_roundtrip(self, qid):
        parsed = qid.QID.parse("3.42.7.0")
        assert (parsed.shell, parsed.form, parsed.logic_state, parsed.recursion) == (3, 42, 7, 0)
        assert str(parsed) == "3.42.7.0"

    def test_boundaries_accepted(self, qid):
        lo = qid.QID.parse("1.1.1.0")
        hi = qid.QID.parse(f"21.315.13.{10**30}")
        assert str(lo) == "1.1.1.0"
        assert str(hi) == f"21.315.13.{10**30}"

    def test_out_of_range_rejected(self, qid):
        for bad in (
            "0.1.1.0", "22.1.1.0",      # shell 1..21
            "1.0.1.0", "1.316.1.0",      # form 1..315
            "1.1.0.0", "1.1.14.0",       # logic_state 1..13
            "1.1.1.-1", f"1.1.1.{10**30 + 1}",  # recursion 0..10^30
        ):
            with pytest.raises(ValueError):
                qid.QID.parse(bad)

    def test_malformed_rejected(self, qid):
        for bad in ("3.42.7", "1.2.3.4.5", "a.b.c.d", "", "   ", "3.4.5.x"):
            with pytest.raises(ValueError):
                qid.QID.parse(bad)
        with pytest.raises(ValueError):
            qid.QID.parse(None)

    def test_spec_tables_not_invented(self, qid):
        # The canonical SER-18/SER-13 name tables live in the master spec,
        # which is not present in this build — the module must NOT invent
        # them. Tables are empty by default; names resolve to None.
        assert qid.PHASE_NAMES == []
        assert qid.STATE_NAMES == []
        parsed = qid.QID.parse("3.42.7.0")
        assert parsed.phase_name() is None
        assert parsed.state_name() is None

    def test_spec_table_registration_validates_counts(self, qid):
        with pytest.raises(ValueError):
            qid.register_spec_tables(["only-one"], ["x"] * 13)
        with pytest.raises(ValueError):
            qid.register_spec_tables(["p"] * 18, ["s"] * 12)
        qid.register_spec_tables([f"phase-{i}" for i in range(18)],
                                 [f"state-{i}" for i in range(13)])
        parsed = qid.QID.parse("1.2.3.0")
        assert parsed.phase_name() == "phase-0"
        assert parsed.state_name() == "state-2"


# ---------------------------------------------------------------------------
# token kinds: session / api / revenue (paper-only)
# ---------------------------------------------------------------------------

class TestTokenKinds:
    def test_default_kind_is_api(self, tokens_mod):
        eng = tokens_mod.TokenEngine()
        tid, token = eng.issue(["read"])
        payload = eng.validate(token)
        assert payload["kind"] == "api"
        assert payload["paper"] is False

    def test_unknown_kind_rejected(self, tokens_mod):
        eng = tokens_mod.TokenEngine()
        with pytest.raises(tokens_mod.TokenError):
            eng.issue(["read"], kind="bogus")

    def test_revenue_token_carries_memo_basis_and_paper_label(self, tokens_mod):
        eng = tokens_mod.TokenEngine()
        tid, token = eng.issue(
            ["revenue.track"],
            kind="revenue",
            memo="paper ledger entry for hunt find #42",
            basis="estimated value from the demand-scoring model, advisory only",
        )
        payload = eng.validate(token)
        assert payload["kind"] == "revenue"
        assert payload["memo"] == "paper ledger entry for hunt find #42"
        assert "advisory only" in payload["basis"]
        assert payload["paper"] is True  # labeled paper: no real money

    def test_revenue_requires_memo_and_basis(self, tokens_mod):
        eng = tokens_mod.TokenEngine()
        with pytest.raises(tokens_mod.TokenError):
            eng.issue(["revenue.track"], kind="revenue")
        with pytest.raises(tokens_mod.TokenError):
            eng.issue(["revenue.track"], kind="revenue", memo="x")
        with pytest.raises(tokens_mod.TokenError):
            eng.issue(["revenue.track"], kind="revenue", basis="y")

    def test_session_kind(self, tokens_mod):
        eng = tokens_mod.TokenEngine()
        tid, token = eng.issue(["cybrus.session"], kind="session")
        assert eng.validate(token)["kind"] == "session"


# ---------------------------------------------------------------------------
# gateway helpers
# ---------------------------------------------------------------------------

def _make_account(name="alice", tier="starter"):
    """Create a real identity account via the factory; returns (name, password)."""
    from levi.cybrus.factory import AccountFactory

    record, password = AccountFactory().generate(name, tier=tier)
    return record["name"], password


def _allow_external(policy_module, subject="alice"):
    """Seed a policy rule allowing high-risk external routing for tests."""
    from levi.cybrus.policy import PolicyEngine

    PolicyEngine().add_rule(subject, "external.*", "route", "allow", "high")


# ---------------------------------------------------------------------------
# gateway auth
# ---------------------------------------------------------------------------

class TestGatewayAuth:
    def test_auth_success_issues_session_token(self, gateway, home):
        name, password = _make_account()
        gw = gateway.CybrusGateway()
        token_id, plaintext = gw.auth(name, password)
        assert token_id and plaintext
        from levi.cybrus.tokens import TokenEngine

        payload = TokenEngine().validate(plaintext)
        assert payload is not None
        assert payload["kind"] == "session"
        assert payload["id"] == token_id

    def test_auth_wrong_password_fails_closed(self, gateway, home):
        name, password = _make_account()
        gw = gateway.CybrusGateway()
        with pytest.raises(gateway.GatewayAuthError):
            gw.auth(name, "wrong-password")

    def test_auth_unknown_identity_fails_closed(self, gateway, home):
        gw = gateway.CybrusGateway()
        with pytest.raises(gateway.GatewayAuthError):
            gw.auth("ghost", "whatever")


# ---------------------------------------------------------------------------
# route_external — the sole external gateway (control plane only)
# ---------------------------------------------------------------------------

class TestRouteExternal:
    def test_denied_without_auth(self, gateway, home):
        gw = gateway.CybrusGateway()
        with pytest.raises(gateway.GatewayAuthError):
            gw.route_external("api.example.com", "alice", "test purpose")

    def test_denied_by_default_policy(self, gateway, home):
        name, password = _make_account()
        gw = gateway.CybrusGateway()
        gw.auth(name, password)
        with pytest.raises(gateway.PolicyDenied):
            gw.route_external("api.example.com", name, "test purpose")

    def test_high_risk_requires_approval_then_succeeds(self, gateway, home):
        name, password = _make_account()
        _allow_external(None, subject=name)
        gw = gateway.CybrusGateway()
        gw.auth(name, password)

        with pytest.raises(gateway.ApprovalRequired) as excinfo:
            gw.route_external("api.example.com", name, "fetch public data")
        approval_id = excinfo.value.approval_id
        assert approval_id

        gw.approve(approval_id)
        grant = gw.route_external("api.example.com", name, "fetch public data")
        assert grant["grant_id"]
        assert grant["token"]
        assert grant["destination"] == "api.example.com"

        binding = gw.validate_grant(grant["token"])
        assert binding is not None
        assert binding["actor"] == name
        assert binding["destination"] == "api.example.com"
        assert binding["purpose"] == "fetch public data"

    def test_grant_is_short_lived(self, gateway, home):
        import time as _time

        name, password = _make_account()
        _allow_external(None, subject=name)
        gw = gateway.CybrusGateway()
        gw.auth(name, password)
        try:
            gw.route_external("api.example.com", name, "p")
        except gateway.ApprovalRequired as exc:
            gw.approve(exc.approval_id)
        grant = gw.route_external("api.example.com", name, "p",
                                  grant_ttl_seconds=120)
        assert grant["expires_at"] - _time.time() <= 120
        # force expiry -> grant no longer validates
        import json as _json

        store_path = gateway._paths().store_path("grants")
        grants = _json.loads(store_path.read_text())
        for entry in grants:
            if entry["grant_id"] == grant["grant_id"]:
                entry["expires_at"] = _time.time() - 1
        store_path.write_text(_json.dumps(grants))
        assert gw.validate_grant(grant["token"]) is None

    def test_unknown_grant_token_rejected(self, gateway, home):
        gw = gateway.CybrusGateway()
        assert gw.validate_grant("not-a-real-token") is None

    def test_approval_is_single_use(self, gateway, home):
        name, password = _make_account()
        _allow_external(None, subject=name)
        gw = gateway.CybrusGateway()
        gw.auth(name, password)
        try:
            gw.route_external("api.example.com", name, "p")
        except gateway.ApprovalRequired as exc:
            gw.approve(exc.approval_id)
        gw.route_external("api.example.com", name, "p")  # consumes the approval
        with pytest.raises(gateway.ApprovalRequired):
            gw.route_external("api.example.com", name, "p")  # needs a NEW approval


# ---------------------------------------------------------------------------
# authorize_execution — policy -> approval -> audit -> decision
# ---------------------------------------------------------------------------

class TestAuthorizeExecution:
    def test_low_risk_allow_authorizes(self, gateway, home):
        from levi.cybrus.policy import PolicyEngine

        PolicyEngine().add_rule("owner", "notes.*", "read", "allow", "low")
        gw = gateway.CybrusGateway()
        result = gw.authorize_execution("owner", "read", "notes.diary")
        assert result["authorized"] is True
        assert result["approval_id"] is None

    def test_high_risk_requires_approval_then_authorizes(self, gateway, home):
        gw = gateway.CybrusGateway()
        result = gw.authorize_execution("owner", "read", "vault.tokens")
        assert result["authorized"] is False
        assert result["approval_id"]
        gw.approve(result["approval_id"])
        again = gw.authorize_execution("owner", "read", "vault.tokens")
        assert again["authorized"] is True

    def test_policy_deny_wins_even_with_approval(self, gateway, home):
        from levi.cybrus.approval import ApprovalEngine

        eng = ApprovalEngine()
        entry = eng.request_approval(
            "execute",
            "owner",
            "system.kernel",
            "critical",
            details={"actor": "owner", "action": "execute",
                     "resource": "system.kernel"},
        )
        eng.approve(entry["id"])  # a human approved it...
        gw = gateway.CybrusGateway()
        result = gw.authorize_execution("owner", "execute", "system.kernel")
        assert result["authorized"] is False  # ...but policy deny still wins
        assert result["decision"].decision == "deny"


# ---------------------------------------------------------------------------
# named API keys (vault-stored)
# ---------------------------------------------------------------------------

class TestApiKeys:
    def test_create_validate_get_list_revoke(self, gateway, home):
        gw = gateway.CybrusGateway(vault_passphrase="test-master-pw")
        name, secret = gw.create_api_key("ci-key", ["read", "write"])
        assert name == "ci-key" and secret

        assert gw.get_api_key("ci-key") == secret
        meta = gw.validate_api_key("ci-key", secret)
        assert meta == {"name": "ci-key", "scopes": ["read", "write"]}
        assert gw.validate_api_key("ci-key", "wrong") is None

        keys = gw.list_api_keys()
        assert len(keys) == 1 and keys[0]["name"] == "ci-key"
        assert "secret" not in str(keys)  # metadata only, never secrets

        gw.revoke_api_key("ci-key")
        assert gw.validate_api_key("ci-key", secret) is None
        with pytest.raises(KeyError):
            gw.get_api_key("ci-key")

    def test_duplicate_name_rejected(self, gateway, home):
        gw = gateway.CybrusGateway(vault_passphrase="test-master-pw")
        gw.create_api_key("dup", ["read"])
        with pytest.raises(gateway.GatewayError):
            gw.create_api_key("dup", ["read"])

    def test_revoke_unknown_rejected(self, gateway, home):
        gw = gateway.CybrusGateway(vault_passphrase="test-master-pw")
        with pytest.raises(KeyError):
            gw.revoke_api_key("nope")

    def test_vault_must_be_unlocked(self, gateway, home):
        gw = gateway.CybrusGateway()
        with pytest.raises(gateway.GatewayError):
            gw.create_api_key("x", ["read"])


# ---------------------------------------------------------------------------
# route_internal — logged, metadata only
# ---------------------------------------------------------------------------

class TestRouteInternal:
    def test_route_by_qid(self, gateway, qid, home):
        gw = gateway.CybrusGateway()
        decision = gw.route_internal(qid.QID.parse("3.42.7.0"), {"op": "ping"})
        assert decision["allowed"] is True
        assert decision["qid"] == "3.42.7.0"

    def test_route_by_named_target(self, gateway, home):
        gw = gateway.CybrusGateway()
        decision = gw.route_internal("memory.write", {"bytes": 12})
        assert decision["target"] == "memory.write"
        assert decision["qid"] is None

    def test_route_internal_is_audited(self, gateway, home):
        from levi.cybrus.audit import AuditEngine

        gw = gateway.CybrusGateway()
        gw.route_internal("3.1.1.0", {"op": "ping"})
        last = AuditEngine().tail(1)[0]
        assert last["event"] == "route.internal"


# ---------------------------------------------------------------------------
# CLI approve/deny authentication (round-3 hardening)
#
# The CLI gate must not be anonymously self-approvable: approve/deny require
# --identity plus a getpass password verified through gateway.auth(); the
# verified identity is recorded in the decision's ``by`` field and in the
# audit log. Programmatic ApprovalEngine.approve() keeps its API.
# ---------------------------------------------------------------------------

def _cli(argv):
    """Run the cybrus CLI, translating SystemExit into a return code."""
    import importlib

    cli = importlib.import_module("levi.cybrus.__main__")
    try:
        return cli.main(argv)
    except SystemExit as exc:
        return exc.code


@pytest.fixture()
def cli_identity(home, monkeypatch):
    """An identity with a real credential; getpass answered from a queue."""
    name, password = _make_account("approver", tier="founder")
    answers = []

    def fake_getpass(prompt=""):
        assert answers, f"unexpected password prompt: {prompt!r}"
        return answers.pop(0)

    monkeypatch.setattr("getpass.getpass", fake_getpass)
    return name, password, answers


class TestCliApprovalAuth:
    def test_approve_requires_identity(self, approval, cli_identity):
        engine = approval.ApprovalEngine()
        entry = engine.request_approval("vault.open", "owner", "vault.main", "high")
        rc = _cli(["approve", entry["id"]])
        assert rc == 2  # argparse: --identity is required
        assert engine.check(entry["id"]) is False  # still pending

    def test_deny_requires_identity(self, approval, cli_identity):
        engine = approval.ApprovalEngine()
        entry = engine.request_approval("vault.open", "owner", "vault.main", "high")
        rc = _cli(["deny", entry["id"]])
        assert rc == 2
        assert engine.check(entry["id"]) is False

    def test_approve_wrong_credential_rejected(self, approval, cli_identity):
        name, _password, answers = cli_identity
        engine = approval.ApprovalEngine()
        entry = engine.request_approval("vault.open", "owner", "vault.main", "high")
        answers.append("wrong-password")
        rc = _cli(["approve", entry["id"], "--identity", name])
        assert rc == 2
        assert engine.check(entry["id"]) is False  # still pending

    def test_approve_unknown_identity_rejected(self, approval, cli_identity):
        _name, _password, answers = cli_identity
        engine = approval.ApprovalEngine()
        entry = engine.request_approval("vault.open", "owner", "vault.main", "high")
        answers.append("whatever")
        rc = _cli(["approve", entry["id"], "--identity", "ghost"])
        assert rc == 2
        assert engine.check(entry["id"]) is False

    def test_approve_authenticated_records_verified_identity(
        self, approval, cli_identity, home
    ):
        from levi.cybrus.audit import AuditEngine

        name, password, answers = cli_identity
        engine = approval.ApprovalEngine()
        entry = engine.request_approval("vault.open", "owner", "vault.main", "high")
        answers.append(password)
        rc = _cli(["approve", entry["id"], "--identity", name])
        assert rc == 0
        decided = engine.list_all()[0]
        assert decided["status"] == "approved"
        assert decided["decided_by"] == name  # the verified identity, not "owner"
        receipt = AuditEngine().tail(1)[0]
        assert receipt["event"] == "approval.approved"
        assert receipt["actor"] == name
        assert receipt["details"]["id"] == entry["id"][:8]

    def test_deny_authenticated_records_verified_identity(
        self, approval, cli_identity, home
    ):
        from levi.cybrus.audit import AuditEngine

        name, password, answers = cli_identity
        engine = approval.ApprovalEngine()
        entry = engine.request_approval("token.issue", "owner", "token.api", "high")
        answers.append(password)
        rc = _cli(["deny", entry["id"], "--identity", name, "--reason", "not now"])
        assert rc == 0
        decided = engine.list_all()[0]
        assert decided["status"] == "denied"
        assert decided["decided_by"] == name
        assert decided["reason"] == "not now"
        receipt = AuditEngine().tail(1)[0]
        assert receipt["event"] == "approval.denied"
        assert receipt["actor"] == name

    def test_cli_scope_required_for_token_issue(self, cli_identity):
        # argparse/engine mismatch fix: --scope is required, the engine
        # rejects empty scopes — the CLI must fail at parse time, clearly.
        rc = _cli(["token", "issue"])
        assert rc == 2

    def test_cli_scope_required_for_apikey_create(self, cli_identity):
        rc = _cli(["apikey", "create", "no-scopes"])
        assert rc == 2

    def test_account_set_password_flow(self, cli_identity, home):
        from levi.cybrus import gateway as gateway_mod
        from levi.cybrus.gateway import CybrusGateway
        from levi.cybrus.identity import IdentityStore

        name, password, answers = cli_identity
        # changing an existing credential requires proving the current one
        answers.append("wrong-current")
        assert _cli(["account", "set-password", name]) == 2
        # correct current + new + confirm
        answers.extend([password, "new-long-password-12345", "new-long-password-12345"])
        assert _cli(["account", "set-password", name]) == 0
        assert IdentityStore().get_credential(name) is not None
        CybrusGateway().auth(name, "new-long-password-12345")  # new works
        with pytest.raises(gateway_mod.GatewayAuthError):
            CybrusGateway().auth(name, password)  # old is dead


# ---------------------------------------------------------------------------
# TOCTOU / replay: single-winner semantics under concurrency (round-3)
# ---------------------------------------------------------------------------

class TestSingleWinnerConcurrency:
    def test_consume_approved_single_winner(self, approval, home):
        import threading

        engine = approval.ApprovalEngine()
        entry = engine.request_approval(
            "execute", "owner", "vault.main", "high", details={"actor": "owner"}
        )
        engine.approve(entry["id"])
        winners = []

        def worker():
            eng = approval.ApprovalEngine()
            won = eng.consume_approved("execute", {"actor": "owner"})
            if won is not None:
                winners.append(won["id"])

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(winners) == 1  # exactly one consumer wins the approval

    def test_token_rotate_single_winner(self, tokens_mod, home):
        import threading

        tid, _tok = tokens_mod.TokenEngine().issue(["read"])
        results, failures = [], []

        def worker():
            try:
                results.append(tokens_mod.TokenEngine().rotate(tid))
            except tokens_mod.TokenError:
                failures.append(1)

        threads = [threading.Thread(target=worker) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(results) == 1  # one successor minted...
        assert len(failures) == 5  # ...the rest fail closed, no second token

    def test_consume_then_check_stays_consumed(self, approval, home):
        # consume_approved marks consumed_at; a later check() still reports
        # approved (the gate predicate), but no second consume is possible.
        engine = approval.ApprovalEngine()
        entry = engine.request_approval(
            "execute", "owner", "vault.main", "high", details={"actor": "owner"}
        )
        engine.approve(entry["id"])
        assert engine.consume_approved("execute", {"actor": "owner"}) is not None
        assert engine.check(entry["id"]) is True
        assert engine.consume_approved("execute", {"actor": "owner"}) is None
