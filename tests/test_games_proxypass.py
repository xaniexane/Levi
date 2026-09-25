"""Hermetic tests for the StreetPass proxypass revival."""

import json

import pytest

from levi.games import proxypass
from levi.games.proxypass import (
    ProxypassError,
    collect,
    drop,
    make_packet,
    verify_packet,
)

KEY = "circle-key-one"


def _packet(handle="wren", payload=None, key=KEY, now=1_000_000, ttl=3600):
    return make_packet(
        handle, payload or {"challenge": "mancala"}, key=key, ttl_seconds=ttl, now=now
    )


def test_round_trip_signed(tmp_path):
    drop(_packet(), tmp_path)
    report = collect(tmp_path, keys=[KEY], now=1_000_010)
    assert len(report.encounters) == 1
    enc = report.encounters[0]
    assert enc.handle == "wren"
    assert enc.payload == {"challenge": "mancala"}
    assert enc.signed is True


def test_bad_signature_dropped(tmp_path):
    pkt = _packet(key="other-key")
    drop(pkt, tmp_path)
    report = collect(tmp_path, keys=[KEY], now=1_000_010)
    assert report.encounters == []
    assert report.bad_signature == 1


def test_unsigned_dropped_by_default(tmp_path):
    drop(_packet(key=None), tmp_path)
    report = collect(tmp_path, keys=[KEY], now=1_000_010)
    assert report.encounters == []
    assert report.bad_signature == 1


def test_unsigned_allowed_when_opted_in(tmp_path):
    drop(_packet(key=None), tmp_path)
    report = collect(tmp_path, keys=[KEY], allow_unsigned=True, now=1_000_010)
    assert len(report.encounters) == 1
    assert report.encounters[0].signed is False


def test_blocklist_drops_silently(tmp_path):
    drop(_packet(handle="griefer"), tmp_path)
    report = collect(tmp_path, keys=[KEY], blocklist=["griefer"], now=1_000_010)
    assert report.encounters == []
    assert report.blocked == 1


def test_rate_limit_throttles(tmp_path):
    for _ in range(3):
        drop(_packet(handle="chatty"), tmp_path)
    report = collect(
        tmp_path, keys=[KEY], rate_limit=2, window_seconds=3600, now=1_000_010
    )
    assert len(report.encounters) == 2
    assert report.throttled == 1


def test_idempotent_collect(tmp_path):
    drop(_packet(), tmp_path)
    first = collect(tmp_path, keys=[KEY], now=1_000_010)
    second = collect(tmp_path, keys=[KEY], now=1_000_020)
    assert len(first.encounters) == 1
    assert second.encounters == []


def test_expired_packet_dropped_and_forgotten(tmp_path):
    pkt = _packet(ttl=60, now=1_000_000)
    target = drop(pkt, tmp_path)
    report = collect(tmp_path, keys=[KEY], now=1_000_000 + 61)
    assert report.encounters == []
    assert report.expired == 1
    assert not target.exists()  # the drop dir forgets dead packets


def test_packet_is_anonymous_by_design():
    pkt = _packet()
    assert set(pkt) >= {
        "schema",
        "packet_id",
        "handle",
        "payload",
        "created_ts",
        "expires_ts",
        "tag",
    }
    assert "device" not in json.dumps(pkt).lower()


def test_handle_length_enforced():
    with pytest.raises(ProxypassError):
        make_packet("x" * 33, {})


def test_payload_size_enforced():
    with pytest.raises(ProxypassError):
        make_packet("wren", {"blob": "x" * 5000})


def test_non_json_payload_refused():
    with pytest.raises(ProxypassError):
        make_packet("wren", {"blob": object()})


def test_verify_packet_reports():
    pkt = _packet()
    assert verify_packet(pkt, [KEY]) == (True, "signed")
    assert verify_packet(pkt, ["nope"]) == (False, "bad signature")
    assert verify_packet(_packet(key=None), [KEY]) == (False, "unsigned")
    assert verify_packet({"nope": 1}, [KEY])[0] is False


def test_missing_dropdir_collects_nothing(tmp_path):
    report = collect(tmp_path / "nope", keys=[KEY])
    assert report.encounters == []
