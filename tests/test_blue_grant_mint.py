"""BLUE regression tests: grant-mint primitive + approval exact matching
(RED-1 batch A, MEDIUM + LOW, L2/L5).

Fail-closed: a deny (or any non-allow) decision never mints a grant —
``_issue_routing_grant`` raises ``PolicyDenied`` naming the remedy (L6).
Approval consumption is exact-match: human restriction metadata can
never be silently dropped. The legitimate path (allow → approval →
single-use grant) keeps working.
"""

import pytest

from levi.cybrus.approval import ApprovalEngine
from levi.cybrus.gateway import CybrusGateway, GatewayError, PolicyDenied
from levi.cybrus.policy import PolicyEngine


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


def _deny():
    return PolicyEngine().evaluate("intruder", "external.redbox", "route")


def _allow():
    PolicyEngine().add_rule("svc-a", "external.redbox", "route", "allow", "low")
    return PolicyEngine().evaluate("svc-a", "external.redbox", "route")


class TestDenyNeverMints:
    def test_direct_mint_on_deny_raises(self, home):
        gw = CybrusGateway()
        with pytest.raises(GatewayError):
            gw._issue_routing_grant("intruder", "redbox", "red test", _deny())

    def test_refusal_is_policy_denied_with_remedy(self, home):
        gw = CybrusGateway()
        with pytest.raises(PolicyDenied) as excinfo:
            gw._issue_routing_grant("intruder", "redbox", "red test", _deny())
        # L6: the refusal names the remedy, and the decision rides along.
        assert "route_external" in str(excinfo.value)
        assert excinfo.value.decision.decision == "deny"

    def test_non_allow_decision_refused_fail_closed(self, home):
        gw = CybrusGateway()

        class Maybe:
            decision = "maybe"
            risk = "low"

        with pytest.raises(GatewayError):
            gw._issue_routing_grant("intruder", "redbox", "red test", Maybe())

    def test_refused_mint_leaves_no_grant_record(self, home):
        from levi.cybrus import _paths

        gw = CybrusGateway()
        try:
            gw._issue_routing_grant("intruder", "redbox", "red test", _deny())
        except GatewayError:
            pass
        grants = _paths.load_json_store(_paths.store_path("grants")) or []
        assert grants == [], f"refused mint left grant records: {grants}"

    def test_allow_decision_still_mints(self, home):
        gw = CybrusGateway()
        grant = gw._issue_routing_grant("svc-a", "redbox", "legit", _allow())
        assert grant["actor"] == "svc-a"
        binding = gw.validate_grant(grant["token"])
        assert binding is not None and binding["actor"] == "svc-a"


class TestApprovalExactMatching:
    def _approved(self, details):
        entry = ApprovalEngine().request_approval(
            "route.external", "svc-a", "external.redbox", "high", details=details
        )
        return ApprovalEngine().approve(entry["id"], by="owner")

    def test_plain_request_cannot_drop_restriction(self, home):
        self._approved(
            {
                "actor": "svc-a",
                "destination": "redbox",
                "purpose": "t",
                "max_amount_usd": 50,
            }
        )
        got = ApprovalEngine().consume_approved(
            "route.external",
            {"actor": "svc-a", "destination": "redbox", "purpose": "t"},
        )
        assert got is None

    def test_tampered_restriction_value_cannot_consume(self, home):
        self._approved(
            {
                "actor": "svc-a",
                "destination": "redbox",
                "purpose": "t",
                "max_amount_usd": 50,
            }
        )
        # Same keys, different restriction value: still no match.
        got = ApprovalEngine().consume_approved(
            "route.external",
            {
                "actor": "svc-a",
                "destination": "redbox",
                "purpose": "t",
                "max_amount_usd": 9999,
            },
        )
        assert got is None

    def test_exact_details_consume_exactly_once(self, home):
        full = {
            "actor": "svc-a",
            "destination": "redbox",
            "purpose": "t",
            "max_amount_usd": 50,
        }
        self._approved(full)
        got = ApprovalEngine().consume_approved("route.external", dict(full))
        assert got is not None and got["status"] == "approved"
        assert ApprovalEngine().consume_approved("route.external", dict(full)) is None

    def test_gateway_pending_match_is_exact(self, home):
        eng = ApprovalEngine()
        details = {"actor": "svc-a", "destination": "redbox", "purpose": "t"}
        entry = eng.request_approval(
            "route.external", "svc-a", "external.redbox", "high", details=details
        )
        entries = eng.list_all()
        assert (
            CybrusGateway._match_approval(entries, "route.external", dict(details), "pending")
            is not None
        )
        # A plainer lookup must not reuse the pending restricted approval.
        assert (
            CybrusGateway._match_approval(
                entries,
                "route.external",
                {"actor": "svc-a", "destination": "redbox"},
                "pending",
            )
            is None
        )
