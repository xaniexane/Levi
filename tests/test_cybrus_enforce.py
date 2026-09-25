"""Invariant tests for the Cybrus choke point (levi.cybrus.enforce).

These are the PROOF gate for the choke-point laws (L1-L5 in
``enforce.py``'s docstring) — machine-checked invariants, honestly named:
nothing here is formally proven, only tested against the laws.

Hermetic: LEVI_HOME is monkeypatched to a tmp dir — no real HOME
writes, no network. Each test gets a fresh policy/rate-limit/approval
store.
"""

import inspect
import time

import pytest

from levi.cybrus import enforce
from levi.cybrus import gateway as gateway_mod
from levi.cybrus import rate_limits as rl
from levi.cybrus.approval import ApprovalEngine
from levi.cybrus.audit import AuditEngine
from levi.cybrus.enforce import (
    CallDenied,
    EnforceError,
    NotAuthenticated,
    cybrus_guarded,
    request_egress,
    route_service_call,
)
from levi.cybrus.gateway import (
    ApprovalRequired,
    CybrusGateway,
    PolicyDenied,
)
from levi.cybrus.policy import PolicyEngine
from levi.cybrus.rate_limits import RateLimitDenied
from levi.cybrus.router import RouteRefused, RouteRegistry
from levi.cybrus.tokens import TokenEngine


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


def _make_account(name, tier="starter"):
    """Create a real identity account; returns (name, password)."""
    from levi.cybrus import rate_limits as _rate_limits
    from levi.cybrus.factory import AccountFactory

    record, password = AccountFactory().generate(name, tier=tier)
    # BLUE (RED-1): the rate-limit tier store is separate from the
    # identity store — mirror the declared tier so gateway routes (which
    # now enforce SERVICE_CALL quota) exercise policy/approval semantics,
    # not quota denial.
    _rate_limits.set_tier(record["name"], tier)
    return record["name"], password


def _session_token(name, password):
    """A live session bearer token bound to ``name`` (label session:<name>)."""
    gw = CybrusGateway()
    _, plaintext = gw.auth(name, password)
    return plaintext


def _service_token():
    """A bearer api token carrying the service.call scope."""
    _, plaintext = TokenEngine().issue(
        scopes=["service.call"], ttl_seconds=3600, kind="api", label="svc token"
    )
    return plaintext


def _authed(name="svc-a", tier="starter"):
    """A caller with a valid session token and a rate-limit tier set."""
    name, password = _make_account(name)
    rl.set_tier(name, tier)
    return name, _session_token(name, password)


def _allow(subject, resource, action, effect="allow", risk="low"):
    return PolicyEngine().add_rule(subject, resource, action, effect, risk)


def _audit_events(home, event):
    return [r for r in AuditEngine().tail(200) if r["event"] == event]


# ---------------------------------------------------------------------------
# L1 — authentication: unauthenticated calls never proceed
# ---------------------------------------------------------------------------


class TestAuthentication:
    def test_no_credential_refused(self, home):
        with pytest.raises(NotAuthenticated):
            route_service_call("svc-a", "levi.knowledge", "search")
        refused = _audit_events(home, "call.refused")
        assert refused and refused[-1]["details"]["stage"] == "auth"

    def test_garbage_token_refused(self, home):
        name, _ = _make_account("svc-a")
        rl.set_tier(name, "starter")
        _allow(name, "service.levi.knowledge", "search")
        with pytest.raises(NotAuthenticated):
            route_service_call(name, "levi.knowledge", "search", credential="bogus")

    def test_session_token_bound_to_caller(self, home):
        name_a, token_a = _authed("svc-a")
        _allow("svc-b", "service.levi.knowledge", "search")
        rl.set_tier("svc-b", "starter")
        # svc-a's session token presented as svc-b: the label binding
        # (session:svc-a) does not match -> refused
        with pytest.raises(NotAuthenticated):
            route_service_call("svc-b", "levi.knowledge", "search", credential=token_a)

    def test_session_token_authenticates(self, home):
        name, token = _authed()
        _allow(name, "service.levi.knowledge", "search")
        out = route_service_call(name, "levi.knowledge", "search", credential=token)
        assert out["allowed"] is True
        assert out["ticket"]

    def test_service_token_with_scope_authenticates(self, home):
        name, _ = _make_account("svc-a")
        rl.set_tier(name, "starter")
        _allow(name, "service.levi.knowledge", "search")
        out = route_service_call(
            name, "levi.knowledge", "search", credential=_service_token()
        )
        assert out["allowed"] is True

    def test_service_token_without_scope_refused(self, home):
        name, _ = _make_account("svc-a")
        rl.set_tier(name, "starter")
        _allow(name, "service.levi.knowledge", "search")
        _, bare = TokenEngine().issue(
            scopes=["other.scope"], ttl_seconds=3600, kind="api"
        )
        with pytest.raises(NotAuthenticated):
            route_service_call(name, "levi.knowledge", "search", credential=bare)

    def test_api_key_authenticates(self, home):
        gw = CybrusGateway(vault_passphrase="test-master-pw")
        key_name, secret = gw.create_api_key("svc-a", ["service.call"])
        rl.set_tier("svc-a", "starter")
        _allow("svc-a", "service.levi.knowledge", "search")
        out = route_service_call(
            "svc-a",
            "levi.knowledge",
            "search",
            api_key=(key_name, secret),
            gateway=gw,
        )
        assert out["allowed"] is True

    def test_api_key_name_must_match_caller(self, home):
        gw = CybrusGateway(vault_passphrase="test-master-pw")
        key_name, secret = gw.create_api_key("svc-a", ["service.call"])
        rl.set_tier("svc-b", "starter")
        _allow("svc-b", "service.levi.knowledge", "search")
        with pytest.raises(NotAuthenticated):
            route_service_call(
                "svc-b",
                "levi.knowledge",
                "search",
                api_key=(key_name, secret),
                gateway=gw,
            )

    def test_both_credential_forms_rejected(self, home):
        with pytest.raises(EnforceError):
            route_service_call(
                "svc-a",
                "levi.knowledge",
                "search",
                credential="x",
                api_key=("n", "s"),
            )


# ---------------------------------------------------------------------------
# L1 — rate limits: over-limit calls never proceed (fail closed)
# ---------------------------------------------------------------------------


class TestRateLimits:
    def test_free_tier_cannot_cross_choke_point(self, home):
        # default tier is free -> SERVICE_CALL caps are (0,0): the very
        # first call is refused. This is the over-limit path.
        name, token = _authed("svc-free", tier="free")
        _allow(name, "service.levi.knowledge", "search")
        with pytest.raises(RateLimitDenied):
            route_service_call(name, "levi.knowledge", "search", credential=token)

    def test_starter_tier_crosses(self, home):
        name, token = _authed("svc-a", tier="starter")
        _allow(name, "service.levi.knowledge", "search")
        out = route_service_call(name, "levi.knowledge", "search", credential=token)
        assert out["allowed"] is True

    def test_rate_limit_checked_before_policy(self, home):
        # free tier + no policy rule at all: the denial must be the
        # rate-limit one (order: auth -> route -> rate-limit -> policy)
        name, token = _authed("svc-free", tier="free")
        with pytest.raises(RateLimitDenied):
            route_service_call(name, "levi.knowledge", "search", credential=token)


# ---------------------------------------------------------------------------
# L3 — policy deny always wins (even with an approval in hand)
# ---------------------------------------------------------------------------


class TestDenyWins:
    def test_deny_wins_over_approval(self, home):
        name, token = _authed("svc-x")
        _allow(name, "service.levi.knowledge", "search", effect="deny", risk="critical")
        # A human approval sitting on the ledger for the exact call...
        entry = ApprovalEngine().request_approval(
            "service.call",
            name,
            "service.levi.knowledge",
            "high",
            details={"caller": name, "callee": "levi.knowledge", "action": "search"},
        )
        ApprovalEngine().approve(entry["id"], by="tester")
        # ...does not move a deny.
        with pytest.raises(CallDenied) as exc_info:
            route_service_call(name, "levi.knowledge", "search", credential=token)
        assert exc_info.value.decision.decision == "deny"
        refused = _audit_events(home, "call.refused")
        assert refused and refused[-1]["details"]["stage"] == "policy"

    def test_default_deny_is_fail_closed(self, home):
        # no rule at all -> default-deny at critical
        name, token = _authed("svc-norule")
        with pytest.raises(CallDenied):
            route_service_call(name, "levi.knowledge", "search", credential=token)

    def test_high_risk_allow_gates_on_human(self, home):
        name, token = _authed("svc-hi")
        _allow(name, "service.levi.knowledge", "search", risk="high")
        with pytest.raises(ApprovalRequired) as exc_info:
            route_service_call(name, "levi.knowledge", "search", credential=token)
        approval_id = exc_info.value.approval_id
        assert approval_id
        # human approves -> retry succeeds
        ApprovalEngine().approve(approval_id, by="tester")
        out = route_service_call(name, "levi.knowledge", "search", credential=token)
        assert out["allowed"] is True
        # single-use: the consumed approval cannot authorize twice
        with pytest.raises(ApprovalRequired):
            route_service_call(name, "levi.knowledge", "search", credential=token)


# ---------------------------------------------------------------------------
# Routing: internal-only here; unknown/external refused
# ---------------------------------------------------------------------------


class TestRouting:
    def test_unregistered_destination_refused(self, home):
        name, token = _authed()
        with pytest.raises(RouteRefused):
            route_service_call(name, "nope.notreal", "search", credential=token)

    def test_qid_target_is_internal(self, home):
        name, token = _authed()
        _allow(name, "qid.*", "route")
        out = route_service_call(name, "3.42.7.0", "route", credential=token)
        assert out["allowed"] is True
        assert out["callee"] == "3.42.7.0"

    def test_external_destination_refused_here(self, home):
        name, token = _authed()
        RouteRegistry().add_external(
            provider="extapi", scope="test", approved_by="tester", reason="test"
        )
        with pytest.raises(EnforceError) as exc_info:
            route_service_call(name, "extapi", "fetch", credential=token)
        assert "request_egress" in str(exc_info.value)


# ---------------------------------------------------------------------------
# L2 — external egress only under a signed grant
# ---------------------------------------------------------------------------


class TestEgress:
    def _register(self):
        return RouteRegistry().add_external(
            provider="extapi", scope="test", approved_by="tester", reason="testing"
        )

    def test_egress_grant_flow(self, home):
        name, token = _authed("egress-svc")
        self._register()
        _allow(name, "external.*", "route", risk="high")
        with pytest.raises(ApprovalRequired) as exc_info:
            request_egress(
                name, "extapi", "sync catalog", credential=token
            )
        ApprovalEngine().approve(exc_info.value.approval_id, by="tester")
        grant = request_egress(name, "extapi", "sync catalog", credential=token)
        assert grant["actor"] == name
        assert grant["destination"] == "extapi"
        assert grant["token"]  # plaintext shown once
        assert grant["expires_at"] > time.time()
        # the grant validates: bound to (actor, destination, purpose)
        binding = CybrusGateway().validate_grant(grant["token"])
        assert binding["actor"] == name
        assert binding["destination"] == "extapi"
        assert binding["purpose"] == "sync catalog"

    def test_grant_expiry_enforced(self, home):
        name, token = _authed("egress-exp")
        self._register()
        _allow(name, "external.*", "route", risk="low")
        grant = request_egress(name, "extapi", "check", credential=token)
        assert CybrusGateway().validate_grant(grant["token"]) is not None
        # age the grant record past expiry (the token itself is still live)
        from levi.cybrus import _paths as p

        path = p.store_path("grants")
        with p.store_lock(path):
            grants = p.load_json_store(path)
            for g in grants:
                if g["grant_id"] == grant["grant_id"]:
                    g["expires_at"] = time.time() - 1
            p.save_json_store(path, grants)
        assert CybrusGateway().validate_grant(grant["token"]) is None

    def test_egress_deny_wins(self, home):
        name, token = _authed("egress-deny")
        self._register()
        _allow(name, "external.*", "route", effect="deny", risk="critical")
        with pytest.raises(PolicyDenied):
            request_egress(name, "extapi", "sync", credential=token)

    def test_egress_refuses_internal_destination(self, home):
        name, token = _authed("egress-int")
        with pytest.raises(EnforceError) as exc_info:
            request_egress(name, "levi.knowledge", "sync", credential=token)
        assert "route_service_call" in str(exc_info.value)

    def test_egress_refuses_unregistered_external(self, home):
        name, token = _authed("egress-unreg")
        with pytest.raises(RouteRefused):
            request_egress(name, "ghostapi", "sync", credential=token)

    def test_egress_requires_purpose(self, home):
        name, token = _authed("egress-purp")
        with pytest.raises(EnforceError):
            request_egress(name, "extapi", "  ", credential=token)

    def test_egress_over_limit_refused(self, home):
        name, token = _authed("egress-free", tier="free")
        self._register()
        _allow(name, "external.*", "route", risk="low")
        with pytest.raises(RateLimitDenied):
            request_egress(name, "extapi", "sync", credential=token)


# ---------------------------------------------------------------------------
# L4 — audit is metadata only, never payloads
# ---------------------------------------------------------------------------


class TestMetadataOnlyAudit:
    def test_audit_carries_no_payload_data(self, home):
        marker = "TOPSECRET_PAYLOAD_MARKER_9ZQ"
        name, token = _authed()
        _allow(name, "service.levi.knowledge", "search")

        @cybrus_guarded(service=name, callee="levi.knowledge")
        def search(secret_arg, other):
            return (secret_arg, other)

        search(marker, "plain", cybrus_credential=token)
        route_service_call(
            name, "levi.knowledge", "search",
            payload_ref="ref-abc-123", credential=token,
        )
        raw = (home / ".levi" / "cybrus" / "audit.jsonl").read_text()
        assert marker not in raw  # the payload never reached the log
        assert "ref-abc-123" in raw  # the reference did (metadata)

    def test_no_payload_parameter_exists(self):
        params = inspect.signature(route_service_call).parameters
        assert "payload" not in params
        assert "payload_ref" in params

    def test_routed_record_shape_is_metadata_only(self, home):
        name, token = _authed()
        _allow(name, "service.levi.knowledge", "search")
        route_service_call(
            name, "levi.knowledge", "search",
            payload_ref="ref-1", credential=token,
        )
        routed = _audit_events(home, "call.routed")
        assert routed
        allowed_keys = {
            "callee", "action", "payload_ref", "ticket",
            "risk", "auth", "approval_id", "device_id",
        }
        assert set(routed[-1]["details"]) <= allowed_keys


# ---------------------------------------------------------------------------
# The decorator: one line routes product code through the choke point
# ---------------------------------------------------------------------------


class TestDecorator:
    def test_refused_call_never_runs_body(self, home):
        name, _ = _make_account("svc-dec")
        rl.set_tier(name, "starter")
        _allow(name, "service.levi.knowledge", "search")
        ran = []

        @cybrus_guarded(service=name, callee="levi.knowledge")
        def search(query):
            ran.append(query)
            return f"result:{query}"

        with pytest.raises(NotAuthenticated):
            search("q")  # no cybrus_credential -> refused at the choke point
        assert ran == []

    def test_allowed_call_runs_body_transparently(self, home):
        name, token = _authed("svc-dec2")
        _allow(name, "service.levi.knowledge", "search")
        ran = []

        @cybrus_guarded(service=name, callee="levi.knowledge")
        def search(query):
            ran.append(query)
            return f"result:{query}"

        assert search("q", cybrus_credential=token) == "result:q"
        assert ran == ["q"]
        assert _audit_events(home, "call.routed")

    def test_decorator_carries_guard_metadata(self):
        @cybrus_guarded(service="s", callee="levi.knowledge", action="find")
        def f():
            pass

        assert f._cybrus_guarded == {
            "service": "s",
            "callee": "levi.knowledge",
            "action": "find",
        }


# ---------------------------------------------------------------------------
# gateway.route_internal: gated delegation (deliverable 2)
# ---------------------------------------------------------------------------


class TestRouteInternalWiring:
    def test_gated_route_internal_crosses_choke_point(self, home):
        name, token = _authed("svc-gw")
        _allow(name, "service.levi.knowledge", "route")
        gw = CybrusGateway()
        out = gw.route_internal("levi.knowledge", caller=name, credential=token)
        assert out["allowed"] is True
        assert out["ticket"]
        assert _audit_events(home, "call.routed")

    def test_gated_route_internal_refuses_unauthenticated(self, home):
        gw = CybrusGateway()
        with pytest.raises(NotAuthenticated):
            gw.route_internal("levi.knowledge", caller="svc-x", credential="bogus")

    def test_bare_route_internal_unchanged(self, home):
        gw = CybrusGateway()
        out = gw.route_internal("3.1.1.0", {"op": "ping"})
        assert out["allowed"] is True
        assert "ticket" not in out


# ---------------------------------------------------------------------------
# L6-L12 — the operating laws, built into the module (runtime-checked)
# ---------------------------------------------------------------------------


class TestOperatingLaws:
    def test_laws_declared_and_numbered(self):
        assert [lid for lid, _ in enforce.LAWS] == [f"L{i}" for i in range(1, 13)]
        for lid, _ in enforce.LAWS:
            assert lid in enforce.__doc__  # every law lives in the docstring too

    def test_nothing_thrown_away_state_only_grows(self, home):
        # L10: allowed AND refused calls only ever append — audit grows,
        # grant records are never deleted.
        name, token = _authed("svc-grow")
        _allow(name, "service.levi.knowledge", "search")
        audit_before = AuditEngine().count()
        grants_before = len(CybrusGateway()._load_store("grants"))
        route_service_call(name, "levi.knowledge", "search", credential=token)
        with pytest.raises(CallDenied):
            route_service_call(name, "levi.knowledge", "delete", credential=token)
        assert AuditEngine().count() > audit_before
        assert len(CybrusGateway()._load_store("grants")) >= grants_before

    def test_no_cancellation_registrations_untouched(self, home):
        # L9: a refused call changes no one else's registrations — policy
        # rules and external routes are exactly as they were.
        name, token = _authed("svc-nc")
        RouteRegistry().add_external(
            provider="extapi", scope="t", approved_by="t", reason="t"
        )
        _allow(name, "service.levi.knowledge", "search")
        rules_before = PolicyEngine().list_rules()
        routes_before = RouteRegistry().external_routes()
        with pytest.raises(CallDenied):
            route_service_call(name, "levi.knowledge", "nuke", credential=token)
        assert PolicyEngine().list_rules() == rules_before
        assert RouteRegistry().external_routes() == routes_before

    def test_honesty_posture(self, home):
        # L12: the backend posture is queryable and states its limits.
        posture = enforce.describe_posture()
        assert posture["organism"] == "levi"
        assert posture["organ"] == "levi.cybrus.enforce"
        assert posture["network"].startswith("none")
        assert posture["deletes_data"] is False
        assert posture["cancels_others"] is False
        assert posture["default_allow"] is False
        assert posture["deny_wins"] is True
        assert posture["blocks_on_human"] is False
        assert posture["laws"] == [f"L{i}" for i in range(1, 13)]

    def test_refusals_carry_their_remedy(self, home):
        # L6 (keeper's law): every refusal names the next step.
        name, token = _authed("svc-rem")
        _allow(name, "service.levi.knowledge", "search", risk="high")
        try:
            route_service_call(name, "levi.knowledge", "search")
            raise AssertionError("expected NotAuthenticated")
        except NotAuthenticated as exc:
            assert "credential" in str(exc)
        # L11 (forward-motion): the gate raises immediately with a
        # resumable id — no blocking wait; the caller moves on, retries.
        with pytest.raises(ApprovalRequired) as exc_info:
            route_service_call(name, "levi.knowledge", "search", credential=token)
        assert exc_info.value.approval_id
        # L7 (originals-first): unregistered destinations are refused with
        # the deliberate-registration remedy, never invented.
        with pytest.raises(RouteRefused) as exc_info:
            route_service_call(name, "ghost.nowhere", "x", credential=token)
        assert "register" in str(exc_info.value).lower()

    def test_no_invented_grants(self, home):
        # L7: a grant that was never minted validates to nothing.
        assert CybrusGateway().validate_grant("made-up-token") is None


# ---------------------------------------------------------------------------
# gateway.route_external still mints through the shared tail (no regress)
# ---------------------------------------------------------------------------


class TestGatewayGrantTail:
    def test_route_external_grant_shape_unchanged(self, home):
        name, password = _make_account("alice")
        gw = CybrusGateway()
        gw.auth(name, password)
        RouteRegistry().add_external(
            provider="extapi", scope="test", approved_by="tester", reason="test"
        )
        _allow(name, "external.*", "route", risk="low")
        grant = gw.route_external("extapi", name, "probe")
        for key in ("grant_id", "token", "token_id", "actor", "destination",
                    "purpose", "expires_at"):
            assert key in grant
        assert gw.validate_grant(grant["token"])["destination"] == "extapi"
