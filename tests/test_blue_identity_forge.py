"""BLUE regression tests: forged caller identity (RED-1 batch A, CRITICAL,
L1).

Fail-closed: a bearer service token can authenticate an ordinary caller,
but it can NEVER act as a founder identity — the founder name confers
quota exemption, so wearing it is privilege escalation. Founder callers
need a bound credential (session token or named api key). The broker
refuses asserted founder identities outright: it cannot verify them.
The legitimate paths — ordinary service tokens, bound session tokens,
ordinary broker identities — keep working.
"""

import pytest

from levi.cybrus import enforce
from levi.cybrus import rate_limits as rl
from levi.cybrus.audit import AuditEngine
from levi.cybrus.broker import BrokerError, CredentialBroker
from levi.cybrus.enforce import NotAuthenticated, route_service_call
from levi.cybrus.factory import AccountFactory
from levi.cybrus.policy import PolicyEngine
from levi.cybrus.tokens import TokenEngine


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


def _lowpriv_service_token(label="svc-lowpriv"):
    _, plaintext = TokenEngine().issue(
        scopes=["service.call"], ttl_seconds=3600, kind="api", label=label
    )
    return plaintext


def _bypass_events():
    return [r for r in AuditEngine().tail(500) if r["event"] == "ratelimit.bypass"]


class TestBearerTokenCannotWearFounder:
    def test_unbound_service_token_refused_as_founder(self, home):
        with pytest.raises(NotAuthenticated):
            enforce._authenticate("chauncey", credential=_lowpriv_service_token())

    def test_unlabeled_service_token_refused_as_founder(self, home):
        _, bare = TokenEngine().issue(
            scopes=["service.call"], ttl_seconds=3600, kind="api"
        )
        with pytest.raises(NotAuthenticated):
            enforce._authenticate("chauncey", credential=bare)

    def test_founder_name_case_variants_refused(self, home):
        with pytest.raises(NotAuthenticated):
            enforce._authenticate("Chauncey", credential=_lowpriv_service_token())

    def test_no_bypass_events_on_forge_attempt(self, home):
        PolicyEngine().add_rule(
            "chauncey", "service.levi.knowledge", "search", "allow", "low"
        )
        for _ in range(3):
            with pytest.raises(NotAuthenticated):
                route_service_call(
                    "chauncey",
                    "levi.knowledge",
                    "search",
                    credential=_lowpriv_service_token(),
                )
        assert _bypass_events() == []

    def test_label_bound_api_token_honored_for_founder(self, home):
        # An api token whose label IS the founder was explicitly bound at
        # issuance — the binding is honored.
        token = _lowpriv_service_token(label="chauncey")
        out = enforce._authenticate("chauncey", credential=token)
        assert out == {"method": "service_token", "subject": "chauncey"}


class TestOrdinaryCallersUnaffected:
    def test_unbound_service_token_still_authenticates_ordinary_caller(
        self, home
    ):
        record, _ = AccountFactory().generate("svc-ordinary")
        name = record["name"]
        rl.set_tier(name, "starter")
        PolicyEngine().add_rule(name, "service.levi.knowledge", "search", "allow", "low")
        out = route_service_call(
            name, "levi.knowledge", "search", credential=_lowpriv_service_token()
        )
        assert out["allowed"] is True

    def test_bound_session_token_still_authenticates_founder(self, home):
        from levi.cybrus.gateway import CybrusGateway
        from levi.cybrus.identity import IdentityStore

        record, password = AccountFactory().generate("chauncey")
        assert record["name"] == "chauncey"
        _, session = CybrusGateway().auth("chauncey", password)
        out = enforce._authenticate("chauncey", credential=session)
        assert out == {"method": "session", "subject": "chauncey"}


class TestBrokerRefusesFounderIdentity:
    def _approved_provision(self, broker, identity, platform, username):
        from levi.cybrus.approval import ApprovalEngine

        details = {"identity": identity, "platform": platform, "username": username}
        entry = ApprovalEngine().request_approval(
            "broker.provision", identity, f"thirdparty.{platform}", "high",
            details=details,
        )
        ApprovalEngine().approve(entry["id"], by="owner")
        return broker.provision(
            platform, "https://example.com/signup",
            identity=identity, username=username,
        )

    def test_provision_as_founder_refused(self, home):
        broker = CredentialBroker(vault_passphrase="blue-test-master-pw")
        with pytest.raises(BrokerError):
            self._approved_provision(broker, "chauncey", "acme", "mallory-acct")
        assert _bypass_events() == []

    def test_constructor_default_founder_refused_at_use(self, home):
        broker = CredentialBroker(
            vault_passphrase="blue-test-master-pw", identity="chauncey"
        )
        with pytest.raises(BrokerError):
            broker.provision("acme", "https://example.com/signup")

    def test_list_paths_refuse_founder_filter(self, home):
        broker = CredentialBroker(vault_passphrase="blue-test-master-pw")
        with pytest.raises(BrokerError):
            broker.list_accounts(identity="chauncey")
        with pytest.raises(BrokerError):
            broker.list_keys(identity="chauncey")

    def test_ordinary_identity_still_provisions(self, home):
        from levi.cybrus.approval import ApprovalEngine

        rl.set_tier("alice", "pro")
        broker = CredentialBroker(vault_passphrase="blue-test-master-pw")
        details = {
            "identity": "alice",
            "platform": "acme",
            "username": "alice.a",
        }
        entry = ApprovalEngine().request_approval(
            "broker.provision", "alice", "thirdparty.acme", "high", details=details
        )
        ApprovalEngine().approve(entry["id"], by="owner")
        record, password = broker.provision(
            "acme", "https://example.com/signup",
            identity="alice", username="alice.a",
        )
        assert record["identity"] == "alice"
        assert len(password) > 0
