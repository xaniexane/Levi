"""Social stub connector input-validation tests (hermetic, stdlib-only)."""

from __future__ import annotations

import pytest

import levi.plugins.social_stub as stub
from levi.plugins.registry import get_connector


@pytest.fixture()
def conn():
    return get_connector("social-stub")


@pytest.fixture(autouse=True)
def _clear_outbox():
    stub.OUTBOX.clear()
    yield
    stub.OUTBOX.clear()


def _publish(conn, confirm=True, **params):
    base = {"platform": "x", "caption": "hello world"}
    base.update(params)
    return conn.execute("publish", base, confirm=confirm)


def test_publish_still_records(conn):
    res = _publish(conn, hashtags=["one", "two"])
    assert res.ok is True
    assert stub.OUTBOX[0]["hashtags"] == ["one", "two"]
    assert stub.OUTBOX[0]["loopback"] is True


def test_publish_rejects_bad_platform(conn):
    for bad in ("", "has space", "a" * 33, "../x", "x!"):
        res = _publish(conn, platform=bad)
        assert res.ok is False, bad
    assert stub.OUTBOX == []


def test_publish_rejects_string_hashtags(conn):
    # A bare string used to become a per-character tag list.
    res = _publish(conn, hashtags="#one #two")
    assert res.ok is False
    assert stub.OUTBOX == []


def test_publish_rejects_too_many_hashtags(conn):
    res = _publish(conn, hashtags=[f"t{i}" for i in range(31)])
    assert res.ok is False
    assert stub.OUTBOX == []


def test_publish_rejects_oversized_caption(conn):
    res = _publish(conn, caption="x" * 10_001)
    assert res.ok is False
    assert stub.OUTBOX == []


def test_publish_rejects_blank_caption(conn):
    res = _publish(conn, caption="   ")
    assert res.ok is False
    assert stub.OUTBOX == []
