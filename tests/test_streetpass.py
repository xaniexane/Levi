"""Tests for core/levi/streetpass — the StreetPass honest inversion.

Laws under proof:
1. Opt-in only — only declared fields on the wire.
2. Local only — non-local beacon targets refused.
3. Signed presence — foreign/unsigned tokens dropped.
4. Ephemeral — expired neighbors swept.
5. Declared identity only — unknown fields ignored.
"""

import os
import secrets
import socket
import time

import pytest

from levi.streetpass import HOME_DIRNAME, PresenceToken, StreetPassError
from levi.streetpass.beacon import (
    DEFAULT_PORT,
    Beacon,
    Listener,
    load_or_create_key,
    sign_token,
    verify_token,
)


def fresh_key() -> bytes:
    return secrets.token_bytes(32)


def test_roundtrip_signed_token():
    key = fresh_key()
    wire = sign_token(key, "Rex", ["chess", "synths"])
    tok = verify_token(key, wire)
    assert isinstance(tok, PresenceToken)
    assert tok.name == "Rex"
    assert sorted(tok.tags) == ["chess", "synths"]


def test_foreign_key_rejected():
    wire = sign_token(fresh_key(), "Rex", ["chess"])
    assert verify_token(fresh_key(), wire) is None


def test_tampered_token_rejected():
    key = fresh_key()
    wire = sign_token(key, "Rex", ["chess"])
    body, sig = wire.rsplit(".", 1)
    tampered = body.replace("Rex", "Mallory") + "." + sig
    assert verify_token(key, tampered) is None


def test_malformed_tokens_rejected():
    key = fresh_key()
    assert verify_token(key, "") is None
    assert verify_token(key, "not-a-token") is None
    assert verify_token(key, "{}.deadbeef") is None


def test_expired_token_rejected():
    key = fresh_key()
    wire = sign_token(key, "Rex", [], ttl=1.0, now=time.time() - 120)
    assert verify_token(key, wire) is None


def test_future_token_rejected():
    key = fresh_key()
    wire = sign_token(key, "Rex", [], now=time.time() + 3600)
    assert verify_token(key, wire) is None


def test_only_declared_fields_on_wire():
    key = fresh_key()
    wire = sign_token(key, "Rex", ["chess"])
    body, _sig = wire.rsplit(".", 1)
    import json

    payload = json.loads(body)
    assert set(payload.keys()) <= {"name", "tags", "issued", "ttl"}


def test_unknown_fields_ignored_not_stored():
    key = fresh_key()
    import json

    extra = json.dumps({"name": "Rex", "tags": [], "issued": time.time(),
                        "ttl": 300, "ssn": "000-00-0000"},
                       separators=(",", ":"), sort_keys=True)
    import hashlib
    import hmac

    sig = hmac.new(key, extra.encode(), hashlib.sha256).hexdigest()
    tok = verify_token(key, extra + "." + sig)
    assert tok is not None
    assert not hasattr(tok, "ssn")


def test_nonlocal_target_refused():
    key = fresh_key()
    with pytest.raises(StreetPassError):
        Beacon(key, "Rex", target="8.8.8.8")
    with pytest.raises(StreetPassError):
        Beacon(key, "Rex", target="example.com")
    # loopback and private are fine
    Beacon(key, "Rex", target="127.0.0.1")
    Beacon(key, "Rex", target="192.168.1.255")


def test_empty_name_refused():
    key = fresh_key()
    with pytest.raises(StreetPassError):
        sign_token(key, "   ", [])


def test_expiry_sweeps_neighbors():
    key = fresh_key()
    lis = Listener(key, port=0)  # port 0: no thread started, direct inject
    expired = sign_token(key, "Ghost", [], ttl=60, now=time.time() - 3600)
    # direct path: expired tokens never verify, so neighbor set stays empty
    assert verify_token(key, expired) is None
    assert lis.neighbors() == []


def test_shared_tags_optin_matching():
    key = fresh_key()
    lis = Listener(key)
    tok = PresenceToken("Rex", ("chess", "synths"), time.time(), 300.0)
    assert lis.shared_tags(tok, ["chess", "go"]) == ["chess"]
    assert lis.shared_tags(tok, ["go"]) == []


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _udp_available() -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.sendto(b"probe", ("127.0.0.1", 9))
        return True
    except OSError:
        return False


requires_udp = pytest.mark.skipif(
    not _udp_available(),
    reason="sandbox blocks UDP sockets; live-socket tests need a real network",
)


@requires_udp
def test_loopback_beacon_listener_end_to_end():
    key = fresh_key()
    port = _free_port()
    lis = Listener(key, port=port, bind="127.0.0.1")
    lis.start()
    try:
        beacon = Beacon(key, "Rex", ["chess"], target="127.0.0.1",
                        port=port, interval=60.0, ttl=120.0)
        beacon.announce()
        deadline = time.time() + 5
        found = []
        while time.time() < deadline and not found:
            found = lis.neighbors()
            time.sleep(0.05)
        assert [n.name for n in found] == ["Rex"]
        assert sorted(found[0].tags) == ["chess"]
    finally:
        lis.stop()


@requires_udp
def test_listener_ignores_foreign_beacon():
    port = _free_port()
    lis = Listener(fresh_key(), port=port, bind="127.0.0.1")
    lis.start()
    try:
        stranger = Beacon(fresh_key(), "Mallory", ["chess"],
                          target="127.0.0.1", port=port, ttl=120.0)
        stranger.announce()
        time.sleep(0.4)
        assert lis.neighbors() == []
    finally:
        lis.stop()


def test_load_or_create_key_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    k1 = load_or_create_key()
    k2 = load_or_create_key()
    assert k1 == k2 and len(k1) == 32
    keyfile = tmp_path / ".levi" / HOME_DIRNAME / "key"
    assert keyfile.stat().st_mode & 0o777 == 0o600
    assert os.stat(keyfile.parent).st_mode & 0o777 == 0o700
