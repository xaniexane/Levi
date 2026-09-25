"""BLUE regression tests: external-route quota bypass (RED-1 batch A,
L5).

Fail-closed: ``CybrusGateway.route_external`` enforces the same
``SERVICE_CALL`` quota as ``route_service_call`` — a free-tier actor is
denied with ``QuotaExceeded`` before any grant can be minted, and policy
approval cannot be used to launder past the quota gate. The legitimate
path — starter-tier actors with quota and an allow still route — is
unchanged.
"""

import pytest

from levi.cybrus import rate_limits as rl
from levi.cybrus.factory import AccountFactory
from levi.cybrus.gateway import CybrusGateway
from levi.cybrus.policy import PolicyEngine
from levi.cybrus.rate_limits import RateLimitDenied


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


def _sessioned_gateway(actor: str) -> CybrusGateway:
    """A gateway with *actor* holding a live session."""
    record, password = AccountFactory().generate(actor)
    gw = CybrusGateway()
    gw.auth(record["name"], password)
    return gw


def _allow_external(actor: str, destination: str = "https://api.example.com"):
    PolicyEngine().add_rule(actor, f"external.{destination}", "route", "allow", "low")


class TestExternalRouteEnforcesQuota:
    def test_free_tier_denied_before_grant(self, home):
        gw = _sessioned_gateway("free-actor")
        rl.set_tier("free-actor", "free")
        _allow_external("free-actor")
        with pytest.raises(RateLimitDenied):
            gw.route_external("https://api.example.com", "free-actor", "a purpose")

    def test_policy_allow_cannot_launder_past_quota(self, home):
        # Even with a policy allow AND a human approval in hand, the quota
        # gate fires first.
        from levi.cybrus.approval import ApprovalEngine

        gw = _sessioned_gateway("free-actor-2")
        rl.set_tier("free-actor-2", "free")
        _allow_external("free-actor-2")
        details = {
            "actor": "free-actor-2",
            "destination": "https://api.example.com",
            "purpose": "a purpose",
        }
        entry = ApprovalEngine().request_approval(
            "route.external",
            "free-actor-2",
            "external.https://api.example.com",
            "low",
            details=details,
        )
        ApprovalEngine().approve(entry["id"], by="owner")
        with pytest.raises(RateLimitDenied):
            gw.route_external("https://api.example.com", "free-actor-2", "a purpose")

    def test_denied_call_audits_denial(self, home):
        from levi.cybrus.audit import AuditEngine

        gw = _sessioned_gateway("free-actor-3")
        rl.set_tier("free-actor-3", "free")
        _allow_external("free-actor-3")
        with pytest.raises(RateLimitDenied):
            gw.route_external("https://api.example.com", "free-actor-3", "a purpose")
        denials = [
            r
            for r in AuditEngine().tail(200)
            if r["event"] == "ratelimit.denied" and r["actor"] == "free-actor-3"
        ]
        assert len(denials) == 1


class TestLegitimateExternalRouteUnchanged:
    def test_starter_tier_routes_with_allow(self, home):
        gw = _sessioned_gateway("svc-actor")
        rl.set_tier("svc-actor", "starter")
        _allow_external("svc-actor")
        grant = gw.route_external("https://api.example.com", "svc-actor", "a purpose")
        assert grant["destination"] == "https://api.example.com"

    def test_high_risk_still_requires_approval(self, home):
        from levi.cybrus.gateway import ApprovalRequired

        gw = _sessioned_gateway("svc-actor-2")
        rl.set_tier("svc-actor-2", "starter")
        PolicyEngine().add_rule(
            "svc-actor-2", "external.https://risk.example.com", "route",
            "allow", "high",
        )
        with pytest.raises(ApprovalRequired):
            gw.route_external("https://risk.example.com", "svc-actor-2", "a purpose")
