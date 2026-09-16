"""Tests for levi.digest (local-first mailing-list manager).

Hermetic: every test runs with an isolated LEVI_HOME in tmp_path.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from levi.digest import lists


@pytest.fixture()
def home(tmp_path, monkeypatch):
    h = tmp_path / "levi-home"
    h.mkdir()
    monkeypatch.setenv("LEVI_HOME", str(h))
    return h


# ---------------------------------------------------------------- subscribe flow


def test_create_subscribe_confirm_post_flow(home):
    lists.create_list("club", "owner@example.com", description="the club")
    token = lists.subscribe("club", "fan@example.com")
    assert isinstance(token, str) and token
    email = lists.confirm("club", token)
    assert email == "fan@example.com"
    msg_id, status = lists.post("club", "fan@example.com", "hello", "first post body")
    assert status == "posted"
    digest = lists.compile_digest("club")
    assert "hello" in digest
    assert "first post body" in digest


def test_moderated_hold_approve_flow(home):
    lists.create_list("board", "owner@example.com", moderated=True)
    msg_id, status = lists.post(
        "board", "someone@example.com", "pitch", "please approve"
    )
    assert status == "held"
    # not yet in the digest
    assert "pitch" not in lists.compile_digest("board")
    msg = lists.approve("board", msg_id, "owner@example.com")
    assert msg["status"] == "posted"
    assert msg["approved_by"] == "owner@example.com"
    assert "pitch" in lists.compile_digest("board")


def test_reject_logs_reason(home):
    lists.create_list("board", "owner@example.com", moderated=True)
    msg_id, status = lists.post("board", "spam@example.com", "junk", "buy stuff")
    assert status == "held"
    lists.reject("board", msg_id, "owner@example.com", reason="spam")
    digest = lists.compile_digest("board")
    assert "junk" not in digest
    import json

    rejected = json.loads((home / "digest" / "board" / "rejected.json").read_text())
    assert rejected[0]["reason"] == "spam"
    assert rejected[0]["moderator"] == "owner@example.com"


def test_approve_unknown_id_raises(home):
    lists.create_list("board", "owner@example.com", moderated=True)
    with pytest.raises(KeyError):
        lists.approve("board", "nope", "owner@example.com")
    with pytest.raises(KeyError):
        lists.reject("board", "nope", "owner@example.com")


# ---------------------------------------------------------------- unsubscribe


def test_unsubscribe_removes_member(home):
    lists.create_list("club", "owner@example.com")
    token = lists.subscribe("club", "fan@example.com")
    lists.confirm("club", token)
    assert lists.unsubscribe("club", "fan@example.com") is True
    assert lists.unsubscribe("club", "fan@example.com") is False


def test_unsubscribe_clears_pending_token(home):
    lists.create_list("club", "owner@example.com")
    token = lists.subscribe("club", "fan@example.com")
    assert lists.unsubscribe("club", "fan@example.com") is False  # not a member
    with pytest.raises(ValueError):
        lists.confirm("club", token)  # pending token gone too


# ---------------------------------------------------------------- digests


def test_digest_buckets_by_day(home):
    lists.create_list("log", "owner@example.com")
    day1 = datetime(2026, 9, 14, 10, 0, tzinfo=timezone.utc)
    day2 = datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc)
    lists.post("log", "a@example.com", "first", "day one", posted_at=day1)
    lists.post("log", "b@example.com", "second", "day two", posted_at=day2)
    digest = lists.compile_digest("log")
    assert "--- 2026-09-14 ---" in digest
    assert "--- 2026-09-15 ---" in digest
    assert "Messages: 2" in digest
    assert digest.index("first") < digest.index("second")


def test_digest_weekly_buckets(home):
    lists.create_list("log", "owner@example.com")
    lists.post(
        "log",
        "a@example.com",
        "weekly-one",
        "w1",
        posted_at=datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc),
    )
    lists.post(
        "log",
        "b@example.com",
        "weekly-two",
        "w2",
        posted_at=datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc),
    )
    digest = lists.compile_digest("log", period="weekly")
    assert "--- 2026-W37 ---" in digest
    assert "--- 2026-W38 ---" in digest


def test_digest_bad_period_raises(home):
    lists.create_list("log", "owner@example.com")
    with pytest.raises(ValueError):
        lists.compile_digest("log", period="monthly")


# ---------------------------------------------------------------- archive search


def test_archive_search_finds_keyword(home):
    lists.create_list("log", "owner@example.com")
    lists.post("log", "a@example.com", "harvest moon", "the barn is full")
    lists.post("log", "b@example.com", "rain", "nothing here")
    hits = lists.archive_search("log", "HARVEST")
    assert len(hits) == 1
    assert hits[0]["subject"] == "harvest moon"
    hits = lists.archive_search("log", "a@example.com")
    assert len(hits) == 1
    assert lists.archive_search("log", "zzz-no-match") == []


# ---------------------------------------------------------------- validation


def test_bad_list_names_raise(home):
    with pytest.raises(ValueError):
        lists.create_list("bad name!", "owner@example.com")
    with pytest.raises(ValueError):
        lists.create_list("x" * 41, "owner@example.com")
    lists.create_list("ok-list_1", "owner@example.com")
    with pytest.raises(ValueError):
        lists.create_list("ok-list_1", "owner@example.com")  # exists


def test_bad_emails_raise(home):
    lists.create_list("club", "owner@example.com")
    for bad in ["nope", "a@b", "@nodomain.", "has space@example.com"]:
        with pytest.raises(ValueError):
            lists.subscribe("club", bad)


def test_unknown_and_expired_tokens_raise(home):
    lists.create_list("club", "owner@example.com")
    with pytest.raises(ValueError):
        lists.confirm("club", "bogus-token")
    # expired: craft a stale pending token file manually
    stale = datetime.now(timezone.utc) - timedelta(hours=25)
    import json

    d = home / "digest" / "club" / "pending" / "oldtoken.json"
    d.write_text(
        json.dumps({"email": "late@example.com", "created": stale.isoformat()})
    )
    with pytest.raises(ValueError):
        lists.confirm("club", "oldtoken")
    assert not d.exists()
