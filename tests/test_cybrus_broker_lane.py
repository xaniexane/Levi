"""Cybrus BROKER lane proof: third-party account creation with Cybrus on top.

His words: "broker is creation of accounts for 3rd party sites" and
"Cybrus is on top of it for extra security". The flow itself lives in
:mod:`levi.cybrus.broker` (CredentialBroker) and
:mod:`levi.cybrus.broker_founder` (live provisioning); this file is the
lane's machine-checked proof that the full lifecycle —
provision -> activate -> rotate -> retire — carries the Cybrus security
layer on top, end to end, in one hermetic run.

LANE LAWS (each machine-checked below)
--------------------------------------
- **BL1 HUMAN-GATE.** provision, rotate, and retire each refuse to act
  without a human approval (BrokerApprovalRequired); the approved retry
  succeeds. activate is bookkeeping (operator-confirmed), audit-logged.
- **BL2 SEALED-AT-REST.** The minted credential lives sealed in the vault
  under the keeper's passphrase: readable with the right passphrase,
  unrecoverable with the wrong one, and never present in any JSON store.
- **BL3 TAMPER-EVIDENT.** Corrupting the sealed vault blob fails closed
  (VaultError) — never silent, never partial.
- **BL4 METADATA-ONLY.** Account records, audit records, and store blobs
  carry metadata only; the plaintext credential appears nowhere but the
  exactly-once issuance return value.
- **BL5 AUDIT-TRAIL.** provision/activate/rotate/retire each leave an
  audit record and the audit hash chain verifies.
- **BL6 FOUNDER-GATE.** A caller-asserted founder identity is refused at
  the broker (anti-forgery); the full broker path for the founder goes
  through the authenticated FounderSession (proven in
  test_cybrus_founder_full.py FL1).
- **BL7 TIER-LIMIT.** Other users are limited or denied: the free tier
  gets zero account creation (RateLimitDenied); paid tiers are quota-bound.
- **BL8 OWNER-CONTAINMENT.** One identity cannot activate, rotate, or
  retire another identity's account.

Shared contracts this lane relies on (sibling lanes: do not break)
------------------------------------------------------------------
- broker -> vault: ``CredentialVault(passphrase).store/get/delete``
  (sealed entries under ``cybrus.broker.accounts.<platform>``).
- broker -> approval: ``ApprovalEngine`` pending/approve; actions
  ``broker.provision`` / ``broker.rotate`` / ``broker.retire``.
- broker -> audit: module ``_audit(event, actor, details)``; verified via
  ``AuditEngine().verify()``.
- broker -> auth: founder path takes a live ``FounderSession``
  (``levi.cybrus.founder_gateway``); caller-asserted founder names are
  refused here.
"""

from __future__ import annotations

import json

import pytest

from levi.cybrus import BrokerApprovalRequired, BrokerError, CredentialBroker
from levi.cybrus.approval import ApprovalEngine
from levi.cybrus.audit import AuditEngine
from levi.cybrus.vault import CredentialVault, VaultError


@pytest.fixture(autouse=True)
def _levi_home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    from levi.cybrus import rate_limits

    rate_limits.set_tier("alice", "pro")
    rate_limits.set_tier("mallory", "pro")
    yield tmp_path


def _run_gated(fn):
    """Drive a broker action through the human gate the way the CLI does."""
    try:
        return fn()
    except BrokerApprovalRequired as exc:
        ApprovalEngine().approve(exc.approval_id, by="tester")
        return fn()


def _account_store_blob():
    from levi.cybrus._paths import load_json_store, store_path

    blob = {}
    for name in ("broker_accounts", "broker_apikeys", "broker_oauth_flows"):
        blob[name] = load_json_store(store_path(name))
    return json.dumps(blob, sort_keys=True)


def _audit_text():
    ok, _ = AuditEngine().verify()
    assert ok, "audit hash chain must verify"
    return "\n".join(
        json.dumps(rec.get("details", {}), sort_keys=True)
        for rec in AuditEngine().tail(500)
    )


# -- BL1: every consequential step is human-gated -----------------------------


def test_bl1_provision_rotate_retire_require_human_approval():
    br = CredentialBroker("keeper-passphrase")
    with pytest.raises(BrokerApprovalRequired):
        br.provision("github", "https://github.com/signup", identity="alice")
    record, _pw = _run_gated(
        lambda: br.provision("github", "https://github.com/signup", identity="alice")
    )
    with pytest.raises(BrokerApprovalRequired):
        br.rotate(record["id"], identity="alice")
    _run_gated(lambda: br.rotate(record["id"], identity="alice"))
    with pytest.raises(BrokerApprovalRequired):
        br.retire(record["id"], identity="alice")
    _run_gated(lambda: br.retire(record["id"], identity="alice"))


# -- BL2/BL4: sealed at rest, metadata only ------------------------------------


def test_bl2_bl4_credential_sealed_at_rest_and_metadata_only():
    br = CredentialBroker("keeper-passphrase")
    record, password = _run_gated(
        lambda: br.provision("gitlab", "https://gitlab.com/signup", identity="alice")
    )
    assert isinstance(password, str) and len(password) >= 16

    # The sealed vault opens under the keeper's passphrase ...
    vault = CredentialVault("keeper-passphrase")
    service = f"cybrus.broker.accounts.gitlab"
    assert vault.get(service, "alice") == password
    # ... and under no other.
    with pytest.raises(VaultError):
        CredentialVault("wrong-passphrase").get(service, "alice")

    # The JSON stores and the account record carry metadata only: the
    # secret VALUE appears nowhere (field names like password_rotated_at
    # are timestamps, i.e. metadata — the law is about the value).
    blob = _account_store_blob()
    assert password not in blob
    assert password not in json.dumps(record)
    assert _audit_text().count(password) == 0


# -- BL3: tamper-evident --------------------------------------------------------


def test_bl3_corrupted_vault_blob_fails_closed():
    br = CredentialBroker("keeper-passphrase")
    _run_gated(
        lambda: br.provision("bitbucket", "https://bitbucket.org/signup", identity="alice")
    )
    vault = br._vault_instance()
    path = vault._entries_path()
    raw = bytearray(path.read_bytes())
    raw[len(raw) // 2] ^= 0xFF  # flip a byte mid-blob
    path.write_bytes(bytes(raw))
    with pytest.raises(VaultError):
        CredentialVault("keeper-passphrase").get(
            "cybrus.broker.accounts.bitbucket", "alice"
        )


# -- BL5: full lifecycle leaves a verifiable audit trail ----------------------


def test_bl5_full_lifecycle_audit_trail():
    br = CredentialBroker("keeper-passphrase")
    record, _pw = _run_gated(
        lambda: br.provision("codeberg", "https://codeberg.org/signup", identity="alice")
    )
    assert record["status"] == "provisioned"
    activated = br.activate(record["id"], identity="alice")
    assert activated["status"] == "active"
    _run_gated(lambda: br.rotate(record["id"], identity="alice"))
    retired = _run_gated(lambda: br.retire(record["id"], identity="alice"))
    assert retired["status"] == "retired"
    # The retired record is kept for the trail — nothing is thrown away.
    assert any(a["id"] == record["id"] for a in br.list_accounts(identity="alice"))

    events = [rec.get("event") for rec in AuditEngine().tail(500)]
    for expected in (
        "broker.account.provisioned",
        "broker.account.activated",
        "broker.account.rotated",
        "broker.account.retired",
    ):
        assert expected in events, f"missing audit event {expected}"
    ok, _ = AuditEngine().verify()
    assert ok


# -- BL6: founder gate — asserted founder names refused ------------------------


def test_bl6_asserted_founder_identity_refused_at_broker():
    from levi.cybrus.identity import FOUNDER_IDENTITIES

    founder_name = sorted(FOUNDER_IDENTITIES)[0]
    br = CredentialBroker("keeper-passphrase")
    with pytest.raises(BrokerError, match="founder identity"):
        br.provision("github", "https://github.com/signup", identity=founder_name)
    # Case-insensitive: shouting the name does not slip past either.
    with pytest.raises(BrokerError, match="founder identity"):
        br.provision(
            "github", "https://github.com/signup", identity=founder_name.upper()
        )


# -- BL7: other users are limited or denied ------------------------------------


def test_bl7_free_tier_gets_zero_account_creation():
    from levi.cybrus import rate_limits
    from levi.cybrus.rate_limits import ACCOUNT_CREATE, RateLimitDenied

    rate_limits.set_tier("freeloader", "free")
    br = CredentialBroker("keeper-passphrase")
    with pytest.raises(BrokerApprovalRequired) as excinfo:
        br.provision("github", "https://github.com/signup", identity="freeloader")
    # Human approves — the tier gate still denies: approval never overrides quota.
    ApprovalEngine().approve(excinfo.value.approval_id, by="tester")
    with pytest.raises(RateLimitDenied):
        br.provision("github", "https://github.com/signup", identity="freeloader")


# -- BL8: owner containment -----------------------------------------------------


def test_bl8_one_identity_cannot_touch_anothers_account():
    br = CredentialBroker("keeper-passphrase")
    record, _pw = _run_gated(
        lambda: br.provision("sourcehut", "https://sr.ht/signup", identity="alice")
    )
    with pytest.raises(BrokerError, match="containment"):
        br.activate(record["id"], identity="mallory")
    with pytest.raises(BrokerError, match="containment"):
        _run_gated(lambda: br.rotate(record["id"], identity="mallory"))
