"""Unlock integration tests (🔑 lane): username+password + biometric ceremony
+ OAuth session → vault.

Hermetic: LEVI_HOME points at a tmp dir per test (autouse fixture), so
identity stores, vault blobs, sealed keeper keys, and the audit log are
isolated. The proof itself lives in ``unlock.check_invariants`` (law →
guard → prove); these tests wrap it and add focused behavioral checks.
"""

import pytest

from levi.cybrus import unlock
from levi.cybrus.biometric import (
    AuthResult,
    SimulatedPlatform,
    UnlockStrength,
)
from levi.cybrus.identity import IdentityStore
from levi.cybrus.oauth import OAuthLogin
from levi.cybrus.unlock import (
    UnlockDenied,
    check_invariants,
    enroll,
    is_enrolled,
    read_metering,
)

PW = "correct horse battery staple"


@pytest.fixture(autouse=True)
def _hermetic_home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    yield


def _founder(password: str = PW) -> str:
    store = IdentityStore()
    if not store.exists("chauncey"):
        store.create("chauncey", tier="founder")
    if not is_enrolled():
        enroll("chauncey", password)
    return "chauncey"


def _sim(n: int = 1) -> SimulatedPlatform:
    return SimulatedPlatform(
        enrolled={UnlockStrength.BIOMETRIC_STRONG},
        script=[AuthResult.success(UnlockStrength.BIOMETRIC_STRONG)] * n,
    )


# -- the proof ----------------------------------------------------------------


def test_proof_all_invariants_pass():
    results = check_invariants()
    failed = [r for r in results if not r["passed"]]
    assert results, "proof returned no checks"
    assert not failed, "failed invariants: %s" % failed
    laws = {r["law"] for r in results}
    for law in ("U1", "U2", "U3", "U4", "U5", "U6", "U7", "U8"):
        assert law in laws, f"law {law} not covered by proof"


# -- focused behavior ----------------------------------------------------------


def test_full_roundtrip():
    _founder()
    with unlock.unlock("chauncey", PW, platform=_sim()) as sess:
        assert sess.identity == "chauncey"
        assert sess.is_founder
        assert not sess.locked
        item_id = sess.vault.store_item("login", "site", username="u", password="p")
        assert sess.vault.get_item(item_id)["fields"]["username"] == "u"
    assert sess.locked


def test_wrong_password_denied_and_metered():
    _founder()
    with pytest.raises(UnlockDenied):
        unlock.unlock("chauncey", "nope", platform=_sim())
    assert any(
        r["ability"] == "unlock.auth" and r["decision"] == "refused"
        for r in read_metering(50)
    )


def test_unknown_identity_denied():
    with pytest.raises(UnlockDenied):
        unlock.unlock("ghost", PW, platform=_sim())


def test_no_hardware_refuses_and_revokes_token():
    _founder()
    cap = {}
    with pytest.raises(UnlockDenied):
        unlock.unlock("chauncey", PW, platform=None, _test_capture=cap)
    assert cap.get("token")
    assert OAuthLogin().validate(cap["token"]) is None


def test_nonfounder_fails_closed_at_key_release():
    _founder()
    store = IdentityStore()
    if not store.exists("limited-user"):
        store.create("limited-user", tier="starter")
    from levi.cybrus.factory import hash_password
    from levi.cybrus.rate_limits import set_tier

    # Bridge the rate limiter's declared tier stub via its own testing path.
    set_tier("limited-user", "starter")
    store.set_credential("limited-user", hash_password("limited-pw"))
    cap = {}
    with pytest.raises(UnlockDenied) as excinfo:
        unlock.unlock("limited-user", "limited-pw", platform=_sim(), _test_capture=cap)
    assert "founder-only" in str(excinfo.value).lower()
    assert OAuthLogin().validate(cap["token"]) is None


def test_scope_gate():
    _founder()
    with unlock.unlock("chauncey", PW, platform=_sim()) as sess:
        assert sess.has_scope("broker:")
        assert sess.has_scope("vault:read")
        assert not sess.has_scope("admin:")
        with pytest.raises(UnlockDenied):
            sess.require_scope("admin:")
        sess.require_scope("broker:")  # must not raise


def test_broker_filing_through_session():
    _founder()
    with unlock.unlock("chauncey", PW, platform=_sim()) as sess:
        item_id = sess.file_broker_credential("some-platform", "user1", "pass1")
        rec = sess.vault.get_item(item_id)
        assert rec["broker_created"] is True
        key_id = sess.file_broker_api_key("api-platform", "key-abc-123")
        assert sess.vault.get_item(key_id)["type"] == "api_key"


def test_broker_filing_needs_broker_scope():
    """A session whose token lacks broker: cannot file, even for the founder
    identity — the gate consults the token (U3), not the name."""
    _founder()
    limited_scopes = list(unlock.LIMITED_SESSION_SCOPES)
    sess = unlock.UnlockSession(
        identity="chauncey",
        token_id="tid",
        token="tok",
        scopes=limited_scopes,
        founder=True,
        vault=None,
        key_box=None,
        oauth=OAuthLogin(),
    )
    with pytest.raises(UnlockDenied):
        sess.file_broker_credential("p", "u", "pw")


def test_reenroll_refuses_and_preserves_blob():
    _founder()
    from levi.cybrus.unlock import _blob_path

    before = _blob_path().read_bytes()
    with pytest.raises(UnlockDenied):
        enroll("chauncey", "a-different-password")
    assert _blob_path().read_bytes() == before


def test_enroll_nonfounder_refused():
    store = IdentityStore()
    if not store.exists("plain-user"):
        store.create("plain-user", tier="starter")
    with pytest.raises(UnlockDenied):
        enroll("plain-user", "some-password")


def test_not_enrolled_unlock_denied():
    store = IdentityStore()
    if not store.exists("chauncey"):
        store.create("chauncey", tier="founder")
    from levi.cybrus.factory import hash_password

    store.set_credential("chauncey", hash_password(PW))
    assert not is_enrolled()
    with pytest.raises(UnlockDenied) as excinfo:
        unlock.unlock("chauncey", PW, platform=_sim())
    assert "not enrolled" in str(excinfo.value).lower()


def test_lock_is_idempotent_and_revokes():
    _founder()
    sess = unlock.unlock("chauncey", PW, platform=_sim())
    token = sess._token
    sess.lock()
    sess.lock()  # idempotent: must not raise
    assert sess.locked
    assert OAuthLogin().validate(token) is None
    with pytest.raises(UnlockDenied):
        _ = sess.vault  # locked sessions expose no vault


def test_metering_covers_gated_paths():
    _founder()
    with unlock.unlock("chauncey", PW, platform=_sim()):
        pass
    abilities = {r["ability"] for r in read_metering(200)}
    for need in ("unlock.auth", "unlock.oauth", "unlock.ceremony", "unlock.lock"):
        assert need in abilities, f"metering missing {need}"
