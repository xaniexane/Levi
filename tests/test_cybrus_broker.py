"""Hermetic tests for the Cybrus credential broker (third-party platforms).

``LEVI_HOME`` is monkeypatched to ``tmp_path`` for every test — no network,
no daemons, no user HOME writes. The broker itself performs no network
calls; the "operator" side of every flow (browser signup, console key copy,
OAuth code exchange) is simulated by handing the resulting values straight
to the broker, exactly as the CLI would.
"""

from __future__ import annotations

import json
import time

import pytest

from levi.cybrus import (
    BrokerApprovalRequired,
    BrokerError,
    CredentialBroker,
    OAuthVault,
)
from levi.cybrus.approval import ApprovalEngine
from levi.cybrus.audit import AuditEngine


@pytest.fixture(autouse=True)
def _levi_home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    # The broker enforces tier quotas on automated retrieval (anti-spam).
    # These hermetic tests exercise the flows, not the quotas — the test
    # identities get a paid tier so retrieval is allowed. Quota behavior
    # itself is covered in tests/test_cybrus_rate_limits.py.
    from levi.cybrus import rate_limits

    rate_limits.set_tier("alice", "pro")
    rate_limits.set_tier("bob", "pro")
    yield tmp_path


def _run_gated(fn):
    """Drive a broker action through the human gate the way the CLI does:
    first call raises :class:`BrokerApprovalRequired` with a pending id, a
    verified human approves it, the retry succeeds."""
    try:
        return fn()
    except BrokerApprovalRequired as exc:
        approval_id = exc.approval_id
        pending = ApprovalEngine().pending()
        assert any(e["id"] == approval_id for e in pending)
        ApprovalEngine().approve(approval_id, by="tester")
        return fn()


def _audit_blob():
    ok, _ = AuditEngine().verify()
    assert ok, "audit chain must verify"
    return "\n".join(
        json.dumps(rec.get("details", {}), sort_keys=True)
        for rec in AuditEngine().tail(500)
    )


def _store_blob():
    from levi.cybrus._paths import load_json_store, store_path

    blob = {}
    for name in ("broker_accounts", "broker_apikeys", "broker_oauth_flows"):
        blob[name] = load_json_store(store_path(name))
    return json.dumps(blob, sort_keys=True)


# -- provisioning: the human gate --------------------------------------------


def test_provision_requires_human_approval():
    br = CredentialBroker("master-pw")
    with pytest.raises(BrokerApprovalRequired) as excinfo:
        br.provision("github", "https://github.com/signup", identity="alice")
    pending = ApprovalEngine().pending()
    assert any(
        e["id"] == excinfo.value.approval_id and e["action"] == "broker.provision"
        for e in pending
    )
    # nothing was provisioned and no password exists anywhere
    assert br.list_accounts() == []


def test_provision_denied_stays_blocked_with_fresh_request():
    br = CredentialBroker("master-pw")
    try:
        br.provision("github", "https://github.com/signup", identity="alice")
    except BrokerApprovalRequired as exc:
        first_id = exc.approval_id
    ApprovalEngine().deny(first_id, reason="not yet", by="tester")
    # denied approvals can never be consumed — a fresh pending is requested
    with pytest.raises(BrokerApprovalRequired) as excinfo:
        br.provision("github", "https://github.com/signup", identity="alice")
    assert excinfo.value.approval_id != first_id
    assert br.list_accounts() == []


def test_provision_lifecycle():
    br = CredentialBroker("master-pw")
    record, password = _run_gated(
        lambda: br.provision(
            "github", "https://github.com/signup", identity="alice", username="alice.gh"
        )
    )
    assert len(password) == 24
    assert record["status"] == "provisioned"
    assert record["platform"] == "github"
    assert record["username"] == "alice.gh"

    # duplicate provisioning for the same platform/username is refused
    with pytest.raises(BrokerError):
        _run_gated(
            lambda: br.provision(
                "github", "https://github.com/signup", identity="alice", username="alice.gh"
            )
        )

    listed = br.list_accounts(identity="alice")
    assert len(listed) == 1 and listed[0]["id"] == record["id"]
    assert br.list_accounts(identity="bob") == []

    # activate: operator confirms the signup completed on the site
    activated = br.activate(record["id"], identity="alice")
    assert activated["status"] == "active"
    assert activated["activated_at"] is not None
    with pytest.raises(BrokerError):
        br.activate(record["id"], identity="alice")  # already active
    with pytest.raises(BrokerError):
        br.activate(record["id"], identity="bob")  # containment

    # rotate: gated, new password differs, shown once
    _, new_password = _run_gated(lambda: br.rotate(record["id"], identity="alice"))
    assert new_password != password
    assert len(new_password) == 24

    # retire: gated, vault entry deleted, record kept for the trail
    retired = _run_gated(lambda: br.retire(record["id"], identity="alice"))
    assert retired["status"] == "retired"
    assert retired["retired_at"] is not None
    from levi.cybrus.vault import CredentialVault

    with pytest.raises(KeyError):
        CredentialVault("master-pw").get("cybrus.broker.accounts.github", "alice.gh")
    with pytest.raises(BrokerError):
        _run_gated(lambda: br.rotate(record["id"], identity="alice"))


def test_provision_rejects_bad_input():
    br = CredentialBroker("master-pw")
    with pytest.raises(BrokerError):
        br.provision("bad platform!", "https://x.example/signup", identity="alice")
    with pytest.raises(BrokerError):
        br.provision("github", "not-a-url", identity="alice")
    with pytest.raises(BrokerError):
        CredentialBroker("")


# -- external API keys --------------------------------------------------------


def test_apikey_store_retrieve_round_trip():
    br = CredentialBroker("master-pw")
    meta = _run_gated(
        lambda: br.store_key(
            "openai",
            "prod-key",
            "sk-SECRET-KEY-MATERIAL",
            identity="alice",
            scopes=["models.read"],
            retrieval_method="console",
        )
    )
    assert meta["platform"] == "openai"
    assert meta["retrieval_method"] == "console"
    assert "sk-SECRET-KEY-MATERIAL" not in json.dumps(meta)

    with pytest.raises(BrokerError):
        br.store_key("openai", "bad method!", "x", identity="alice")
    with pytest.raises(BrokerError):
        _run_gated(
            lambda: br.store_key(
                "openai", "prod-key", "other", identity="alice", retrieval_method="api"
            )
        )  # duplicate label

    retrieved = _run_gated(
        lambda: br.retrieve_key("prod-key", identity="alice", requester="alice")
    )
    assert retrieved == "sk-SECRET-KEY-MATERIAL"

    listed = br.list_keys(identity="alice")
    assert len(listed) == 1
    assert "sk-SECRET-KEY-MATERIAL" not in json.dumps(listed)


def test_apikey_containment_no_cross_identity():
    br = CredentialBroker("master-pw")
    _run_gated(
        lambda: br.store_key("openai", "k1", "alice-secret", identity="alice")
    )
    with pytest.raises(BrokerError):
        _run_gated(
            lambda: br.retrieve_key("k1", identity="alice", requester="bob")
        )
    with pytest.raises(BrokerError):
        _run_gated(lambda: br.revoke_key("k1", identity="bob"))
    with pytest.raises(BrokerError):
        _run_gated(lambda: br.retrieve_key("nope", identity="alice"))


def test_apikey_retrieve_is_gated():
    br = CredentialBroker("master-pw")
    _run_gated(lambda: br.store_key("openai", "k1", "s3cr3t", identity="alice"))
    # retrieval without an approval on record stays blocked
    with pytest.raises(BrokerApprovalRequired) as excinfo:
        br.retrieve_key("k1", identity="alice")
    assert ApprovalEngine().pending()
    ApprovalEngine().approve(excinfo.value.approval_id, by="tester")
    assert br.retrieve_key("k1", identity="alice") == "s3cr3t"


def test_apikey_revoke():
    br = CredentialBroker("master-pw")
    _run_gated(lambda: br.store_key("openai", "k1", "s3cr3t", identity="alice"))
    revoked = _run_gated(lambda: br.revoke_key("k1", identity="alice"))
    assert revoked["status"] == "revoked"
    with pytest.raises(BrokerError):
        _run_gated(lambda: br.retrieve_key("k1", identity="alice"))


# -- OAuth2 flow state machine -------------------------------------------------


def _started_flow(br):
    return _run_gated(
        lambda: br.oauth_start(
            "github",
            client_id="client-123",
            authorize_url="https://github.com/login/oauth/authorize",
            redirect_uri="https://levi.local/oauth/callback",
            identity="alice",
            scopes=["repo", "read:user"],
        )
    )


def test_oauth_start_builds_pkce_authorization_url():
    br = CredentialBroker("master-pw")
    result = _started_flow(br)
    url = result["authorization_url"]
    assert url.startswith("https://github.com/login/oauth/authorize?")
    assert "response_type=code" in url
    assert "client_id=client-123" in url
    assert "code_challenge=" in url
    assert "code_challenge_method=S256" in url
    assert f"state={result['state']}" in url
    assert "scope=repo+read%3Auser" in url or "scope=repo%20read%3Auser" in url.replace(
        "+", "%20"
    ) or "scope=" in url
    # the PKCE verifier is in the vault (encrypted at rest), never the flow store
    from levi.cybrus.vault import CredentialVault

    verifier = CredentialVault("master-pw").get(
        "cybrus.broker.oauth.github", f"{result['flow_id'][:8]}.verifier"
    )
    assert len(verifier) > 32
    flows = json.loads(_store_blob())["broker_oauth_flows"]
    assert verifier not in json.dumps(flows)
    status = br.oauth_status(identity="alice")
    assert len(status) == 1 and status[0]["status"] == "initiated"
    assert status[0]["needs_refresh"] is False


def test_oauth_callback_verifies_state_and_captures_code():
    br = CredentialBroker("master-pw")
    result = _started_flow(br)
    flow_id = result["flow_id"]
    # wrong state → CSRF fail-closed, no transition
    with pytest.raises(BrokerError):
        br.oauth_callback(flow_id, "authcode-1", "tampered-state", identity="alice")
    assert br.oauth_status()[0]["status"] == "initiated"
    # correct state → authorized; the code lands encrypted in the vault
    out = br.oauth_callback(flow_id, "authcode-1", result["state"], identity="alice")
    assert out["status"] == "authorized"
    from levi.cybrus.vault import CredentialVault

    code = CredentialVault("master-pw").get(
        "cybrus.broker.oauth.github", f"{flow_id[:8]}.code"
    )
    assert code == "authcode-1"
    assert "authcode-1" not in _store_blob()
    # containment: another identity cannot drive the flow
    with pytest.raises(BrokerError):
        br.oauth_callback(flow_id, "authcode-2", result["state"], identity="bob")


def test_oauth_complete_stores_tokens_and_clears_scratch():
    br = CredentialBroker("master-pw")
    result = _started_flow(br)
    flow_id = result["flow_id"]
    br.oauth_callback(flow_id, "authcode-1", result["state"], identity="alice")

    # token store is human-gated
    with pytest.raises(BrokerApprovalRequired):
        br.oauth_complete(flow_id, identity="alice", access_token="tok")
    meta = _run_gated(
        lambda: br.oauth_complete(
            flow_id,
            identity="alice",
            access_token="ACCESS-TOKEN-XYZ",
            refresh_token="REFRESH-TOKEN-XYZ",
            expires_in=3600,
        )
    )
    assert meta["status"] == "active"
    assert meta["refresh_due_at"] is not None
    # tokens land in the shared OAuthVault, readable by the owning identity
    record = OAuthVault("master-pw").get_token("github", "alice", requester="alice")
    assert record["access_token"] == "ACCESS-TOKEN-XYZ"
    assert record["refresh_token"] == "REFRESH-TOKEN-XYZ"
    # single-use scratch secrets are wiped from the vault
    from levi.cybrus.vault import CredentialVault

    vault = CredentialVault("master-pw")
    for suffix in ("verifier", "code"):
        with pytest.raises(KeyError):
            vault.get("cybrus.broker.oauth.github", f"{flow_id[:8]}.{suffix}")


def test_oauth_illegal_transitions_fail_closed():
    br = CredentialBroker("master-pw")
    result = _started_flow(br)
    flow_id = result["flow_id"]
    # complete before the callback → illegal
    with pytest.raises(BrokerError):
        _run_gated(
            lambda: br.oauth_complete(flow_id, identity="alice", access_token="tok")
        )
    # refresh before tokens exist → illegal
    with pytest.raises(BrokerError):
        _run_gated(
            lambda: br.oauth_refresh(flow_id, identity="alice", new_access_token="tok")
        )
    # callback twice → illegal
    br.oauth_callback(flow_id, "code-1", result["state"], identity="alice")
    with pytest.raises(BrokerError):
        br.oauth_callback(flow_id, "code-2", result["state"], identity="alice")
    # abandon mid-flight works; everything after is dead
    abandoned = br.oauth_abandon(flow_id, identity="alice")
    assert abandoned["status"] == "abandoned"
    with pytest.raises(BrokerError):
        _run_gated(
            lambda: br.oauth_complete(flow_id, identity="alice", access_token="tok")
        )


def test_oauth_refresh_cycle_and_scheduling():
    br = CredentialBroker("master-pw")
    result = _started_flow(br)
    flow_id = result["flow_id"]
    br.oauth_callback(flow_id, "code-1", result["state"], identity="alice")
    meta = _run_gated(
        lambda: br.oauth_complete(
            flow_id,
            identity="alice",
            access_token="tok-1",
            refresh_token="ref-1",
            expires_in=3600,
        )
    )
    # refresh_due_at ≈ expires_in - safety margin (300s)
    assert abs(meta["refresh_due_at"] - (time.time() + 3300)) < 30
    assert br.flow_needs_refresh(flow_id, identity="alice") is False

    refreshed = _run_gated(
        lambda: br.oauth_refresh(
            flow_id,
            identity="alice",
            new_access_token="tok-2",
            expires_in=7200,
        )
    )
    assert refreshed["status"] == "refreshed"
    assert refreshed["refresh_count"] == 1
    record = OAuthVault("master-pw").get_token("github", "alice", requester="alice")
    assert record["access_token"] == "tok-2"
    assert record["refresh_token"] == "ref-1"  # kept when not replaced
    # refresh is repeatable
    refreshed2 = _run_gated(
        lambda: br.oauth_refresh(
            flow_id, identity="alice", new_access_token="tok-3", expires_in=7200
        )
    )
    assert refreshed2["refresh_count"] == 2

    # backdate the scheduling data → the driver predicate fires
    from levi.cybrus._paths import load_json_store, save_json_store, store_path

    path = store_path("broker_oauth_flows")
    flows = load_json_store(path)
    for f in flows:
        if f["id"] == flow_id:
            f["refresh_due_at"] = time.time() - 10
    save_json_store(path, flows)
    assert br.flow_needs_refresh(flow_id, identity="alice") is True
    status = br.oauth_status(identity="alice")
    assert status[0]["needs_refresh"] is True


def test_oauth_token_store_and_refresh_are_gated():
    br = CredentialBroker("master-pw")
    result = _started_flow(br)
    flow_id = result["flow_id"]
    br.oauth_callback(flow_id, "code-1", result["state"], identity="alice")
    with pytest.raises(BrokerApprovalRequired) as excinfo:
        br.oauth_complete(flow_id, identity="alice", access_token="tok")
    assert excinfo.value.approval_id
    # flow is still authorized — the blocked attempt changed nothing
    assert br.oauth_status()[0]["status"] == "authorized"


# -- no plaintext leaks --------------------------------------------------------


def test_no_secret_ever_in_stores_audit_or_stdout(capsys):
    br = CredentialBroker("master-pw")
    secrets_ = {
        "pw": None,
        "key": "KEY-MATERIAL-UNIQUE-998877",
        "access": "ACCESS-UNIQUE-112233",
        "refresh": "REFRESH-UNIQUE-445566",
        "code": "AUTHCODE-UNIQUE-778899",
    }
    _, pw = _run_gated(
        lambda: br.provision(
            "acme", "https://acme.example/signup", identity="alice", username="alice.a"
        )
    )
    secrets_["pw"] = pw
    _run_gated(
        lambda: br.store_key("acme", "main", secrets_["key"], identity="alice")
    )
    result = _started_flow(br)
    flow_id = result["flow_id"]
    br.oauth_callback(flow_id, secrets_["code"], result["state"], identity="alice")
    _run_gated(
        lambda: br.oauth_complete(
            flow_id,
            identity="alice",
            access_token=secrets_["access"],
            refresh_token=secrets_["refresh"],
            expires_in=3600,
        )
    )
    _run_gated(lambda: br.retrieve_key("main", identity="alice"))

    stores_blob = _store_blob()
    audit_blob = _audit_blob()
    for name, value in secrets_.items():
        assert value not in stores_blob, f"{name} leaked into a JSON store"
        assert value not in audit_blob, f"{name} leaked into the audit log"

    # the raw vault blob holds ciphertext, never the plaintext values
    from levi.cybrus._paths import cybrus_dir

    raw = (cybrus_dir() / "vault" / "entries.enc").read_bytes()
    for name, value in secrets_.items():
        assert value.encode("utf-8") not in raw, f"{name} in vault blob plaintext"

    # flow records carry no secret-shaped keys at all
    for flow in json.loads(stores_blob)["broker_oauth_flows"]:
        assert not (set(flow) & {"verifier", "code", "access_token", "refresh_token"})


def test_cli_broker_parsers_wire():
    from levi.cybrus.__main__ import main

    with pytest.raises(SystemExit) as excinfo:
        main(["broker", "--help"])
    assert excinfo.value.code == 0
    with pytest.raises(SystemExit) as excinfo:
        main(["broker", "oauth-start", "--help"])
    assert excinfo.value.code == 0


def test_broker_status_overview():
    br = CredentialBroker("master-pw")
    st = br.status(identity="alice")
    assert st == {
        "accounts": 0,
        "api_keys": 0,
        "oauth_flows": 0,
        "oauth_by_status": {},
        "oauth_refresh_due": 0,
    }
    _run_gated(
        lambda: br.provision("acme", "https://acme.example/signup", identity="alice")
    )
    _run_gated(lambda: br.store_key("acme", "k", "sekret", identity="alice"))
    _started_flow(br)
    st = br.status(identity="alice")
    assert st["accounts"] == 1
    assert st["api_keys"] == 1
    assert st["oauth_flows"] == 1
    assert st["oauth_by_status"] == {"initiated": 1}
    assert st["oauth_refresh_due"] == 0
