"""RED team (pulse 📡) — adversarial attacks on the 12 enforce laws.

Each test is an ATTACK asserting the law HOLDS. A failing test here is a
FINDING handed to BLUE: the attack succeeded and the law did not hold.

Hermetic: LEVI_HOME is monkeypatched to a tmp dir — no real HOME writes,
no network. Scope: the enforce.py choke-point seam (route_service_call /
request_egress / _authenticate / approvals / grants). The broker, vault,
veil, and device surfaces belong to the sibling RED-2 lane; this file
stays on the choke point to avoid file collisions.
"""

import json
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
from levi.cybrus.router import RouteRegistry
from levi.cybrus.tokens import TokenEngine


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


def _make_account(name, tier="starter"):
    from levi.cybrus.factory import AccountFactory

    record, password = AccountFactory().generate(name, tier=tier)
    return record["name"], password


def _session_token(name, password):
    gw = CybrusGateway()
    _, plaintext = gw.auth(name, password)
    return plaintext


def _authed(name="red-svc", tier="starter"):
    name, password = _make_account(name, tier=tier)
    rl.set_tier(name, tier)
    return name, _session_token(name, password)


def _allow(subject, resource, action, effect="allow", risk="low"):
    return PolicyEngine().add_rule(subject, resource, action, effect, risk)


# ---------------------------------------------------------------------------
# L1 — authentication is airtight at the choke point
# ---------------------------------------------------------------------------


class TestRedAuth:
    def test_red_dual_credential_rejected(self, home):
        """ATTACK: present BOTH credential and api_key — exactly one allowed."""
        name, token = _authed("red-dual")
        _allow(name, "service.levi.knowledge", "search", risk="low")
        with pytest.raises(EnforceError):
            route_service_call(
                name,
                "levi.knowledge",
                "search",
                credential=token,
                api_key=("red-dual", "secret"),
            )

    def test_red_apikey_without_gateway_rejected(self, home):
        """ATTACK: api_key auth with no gateway — vault can't be checked,
        so the call must fail closed, not fall through."""
        name, _pw = _make_account("red-nogw")
        rl.set_tier(name, "starter")
        _allow(name, "service.levi.knowledge", "search", risk="low")
        with pytest.raises(EnforceError):
            route_service_call(
                name,
                "levi.knowledge",
                "search",
                api_key=("red-nogw", "whatever"),
            )

    def test_red_no_credential_no_entry(self, home):
        """ATTACK: bare call with no credential of any kind."""
        _allow("ghost", "service.levi.knowledge", "search", risk="low")
        with pytest.raises(NotAuthenticated):
            route_service_call("ghost", "levi.knowledge", "search")

    def test_red_session_token_bound_to_caller(self, home):
        """ATTACK: steal A's session token, use it as B."""
        name_a, token_a = _authed("red-victim")
        name_b, _pw = _make_account("red-thief")
        rl.set_tier(name_b, "starter")
        _allow(name_b, "service.levi.knowledge", "search", risk="low")
        with pytest.raises(NotAuthenticated):
            route_service_call(
                name_b, "levi.knowledge", "search", credential=token_a
            )

    def test_red_unscoped_api_token_rejected(self, home):
        """ATTACK: valid token WITHOUT the service.call scope."""
        name, _pw = _make_account("red-unscoped")
        rl.set_tier(name, "starter")
        _, bare = TokenEngine().issue(
            scopes=["other.scope"], ttl_seconds=3600, kind="api", label="bare"
        )
        _allow(name, "service.levi.knowledge", "search", risk="low")
        with pytest.raises(NotAuthenticated):
            route_service_call(
                name, "levi.knowledge", "search", credential=bare
            )

    def test_red_over_limit_refused(self, home):
        """ATTACK: hammer past the tier quota (starter: 100/hr)."""
        name, _pw = _make_account("red-flood")
        rl.set_tier(name, "starter")
        for _ in range(100):
            rl.check(name, rl.SERVICE_CALL)
        with pytest.raises(RateLimitDenied):
            rl.check(name, rl.SERVICE_CALL)


# ---------------------------------------------------------------------------
# L3 — policy deny always wins, even with an approval in hand
# ---------------------------------------------------------------------------


class TestRedDenyWins:
    def test_red_deny_wins_over_approval_in_hand(self, home):
        """ATTACK: get an approval, THEN the policy flips to deny.
        The approval ledger must never be consulted on a deny."""
        name, token = _authed("red-denywin")
        _allow(name, "service.levi.knowledge", "search", risk="high")
        # first pass: high-risk allow -> approval required
        with pytest.raises(ApprovalRequired) as exc_info:
            route_service_call(name, "levi.knowledge", "search", credential=token)
        ApprovalEngine().approve(exc_info.value.approval_id, by="tester")
        # policy flips to deny while the approval sits in the ledger
        _allow(name, "service.levi.knowledge", "search", effect="deny",
               risk="critical")
        with pytest.raises(CallDenied):
            route_service_call(name, "levi.knowledge", "search", credential=token)


# ---------------------------------------------------------------------------
# L5 — approvals are single-use, bound, and expire
# ---------------------------------------------------------------------------


class TestRedApprovalBinding:
    def _high_risk_setup(self, name):
        _allow(name, "service.levi.knowledge", "search", risk="high")

    def test_red_approval_double_spend_fails(self, home):
        """ATTACK: consume the same approval twice through the choke point."""
        name, token = _authed("red-double")
        self._high_risk_setup(name)
        with pytest.raises(ApprovalRequired) as exc_info:
            route_service_call(name, "levi.knowledge", "search", credential=token)
        ApprovalEngine().approve(exc_info.value.approval_id, by="tester")
        out = route_service_call(name, "levi.knowledge", "search", credential=token)
        assert out["allowed"] is True
        # second identical call: the approval is spent -> gate raises again
        with pytest.raises(ApprovalRequired):
            route_service_call(name, "levi.knowledge", "search", credential=token)

    def test_red_approval_cross_action_reuse_fails(self, home):
        """ATTACK: approval minted for route.external, spent on service.call."""
        name, token = _authed("red-xaction")
        self._high_risk_setup(name)
        RouteRegistry().add_external(
            provider="extapi", scope="test", approved_by="tester", reason="testing"
        )
        _allow(name, "external.*", "route", risk="high")
        with pytest.raises(ApprovalRequired) as exc_info:
            request_egress(name, "extapi", "sync", credential=token)
        ApprovalEngine().approve(exc_info.value.approval_id, by="tester")
        # the route.external approval must NOT authorize a service.call
        with pytest.raises(ApprovalRequired):
            route_service_call(name, "levi.knowledge", "search", credential=token)

    def test_red_approval_cross_actor_reuse_fails(self, home):
        """ATTACK: B tries to ride on A's approval."""
        name_a, token_a = _authed("red-actor-a")
        name_b, token_b = _authed("red-actor-b")
        self._high_risk_setup(name_a)
        self._high_risk_setup(name_b)
        with pytest.raises(ApprovalRequired) as exc_info:
            route_service_call(
                name_a, "levi.knowledge", "search", credential=token_a
            )
        ApprovalEngine().approve(exc_info.value.approval_id, by="tester")
        # B's identical-shaped call must NOT consume A's approval
        with pytest.raises(ApprovalRequired):
            route_service_call(
                name_b, "levi.knowledge", "search", credential=token_b
            )


# ---------------------------------------------------------------------------
# L4 — audit carries metadata only; the choke point never logs secrets
# ---------------------------------------------------------------------------


class TestRedAuditHygiene:
    def test_red_audit_never_carries_secrets(self, home):
        """ATTACK: make authenticated calls, then grep the audit store for
        the plaintext credential. L4: metadata only."""
        name, token = _authed("red-hygiene")
        _allow(name, "service.levi.knowledge", "search", risk="low")
        route_service_call(name, "levi.knowledge", "search", credential=token)
        try:
            route_service_call(name, "levi.knowledge", "search",
                               credential="bogus-token")
        except NotAuthenticated:
            pass
        from levi.cybrus import _paths as p

        audit_path = p.store_path("audit")
        raw = audit_path.read_text() if audit_path.exists() else ""
        assert token not in raw, "FINDING: plaintext credential in audit log"
        assert "bogus-token" not in raw, "FINDING: presented secret in audit log"

    def test_red_payload_ref_size_capped(self, home):
        """ATTACK: smuggle content through payload_ref (10KB blob)."""
        name, token = _authed("red-smuggle")
        _allow(name, "service.levi.knowledge", "search", risk="low")
        with pytest.raises(EnforceError):
            route_service_call(
                name,
                "levi.knowledge",
                "search",
                payload_ref="x" * 10_000,
                credential=token,
            )


# ---------------------------------------------------------------------------
# L2 — grants are bound (actor, destination, purpose, expiry)
# ---------------------------------------------------------------------------


class TestRedGrantBinding:
    def _register(self):
        return RouteRegistry().add_external(
            provider="extapi", scope="test", approved_by="tester", reason="testing"
        )

    def test_red_grant_names_original_actor(self, home):
        """ATTACK: B presents A's grant token. The binding must still name A,
        so any transport that enforces the binding refuses B."""
        name_a, token_a = _authed("red-grantor")
        self._register()
        _allow(name_a, "external.*", "route", risk="low")
        grant = request_egress(name_a, "extapi", "sync", credential=token_a)
        binding = CybrusGateway().validate_grant(grant["token"])
        assert binding is not None
        assert binding["actor"] == name_a
        assert binding["destination"] == "extapi"
        assert binding["purpose"] == "sync"

    def test_red_forged_grant_token_rejected(self, home):
        """ATTACK: present a syntactically valid but unknown token."""
        assert CybrusGateway().validate_grant("Bearer deadbeef") is None


# ---------------------------------------------------------------------------
# L6 / L11 — refusals name the remedy; the choke point never blocks
# ---------------------------------------------------------------------------


class TestRedRefusalPosture:
    def test_red_refusal_names_remedy(self, home):
        """L6: the refusal arrives with its remedy named."""
        name, token = _authed("red-remedy")
        _allow(name, "service.levi.knowledge", "search", risk="high")
        with pytest.raises(ApprovalRequired) as exc_info:
            route_service_call(name, "levi.knowledge", "search", credential=token)
        msg = str(exc_info.value)
        assert exc_info.value.approval_id
        assert "levi cybrus approve" in msg

    def test_red_high_risk_raises_immediately(self, home):
        """L11: gated calls raise at once with a resumable id — never block."""
        name, token = _authed("red-noblock")
        _allow(name, "service.levi.knowledge", "search", risk="high")
        start = time.monotonic()
        with pytest.raises(ApprovalRequired) as exc_info:
            route_service_call(name, "levi.knowledge", "search", credential=token)
        assert time.monotonic() - start < 5
        assert exc_info.value.approval_id  # resumable id, forward motion
