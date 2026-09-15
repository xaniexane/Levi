"""Review queue: pending packs, approve/deny, audit decisions, permissions."""

import os
import stat

import pytest

from levi.king.review import ReviewError, ReviewQueue


def _q(tmp_path):
    return ReviewQueue(data_dir=tmp_path / "king")


def _pack():
    return {
        "platform": "x",
        "title": "t",
        "caption": "A clean caption #lwp",
        "hashtags": ["#lwp"],
    }


def test_queue_approve_flow(tmp_path):
    q = _q(tmp_path)
    item = q.queue_pack(_pack())
    assert item["status"] == "pending"
    assert q.pending_count() == 1
    decided = q.approve(item["id"], note="looks good")
    assert decided["status"] == "approved"
    assert decided["note"] == "looks good"
    assert q.pending_count() == 0
    assert q.get(item["id"])["status"] == "approved"


def test_deny_flow(tmp_path):
    q = _q(tmp_path)
    item = q.queue_pack(_pack())
    decided = q.deny(item["id"], note="off-brand")
    assert decided["status"] == "denied"
    assert q.summary()["denied"] == 1


def test_double_decision_raises(tmp_path):
    q = _q(tmp_path)
    item = q.queue_pack(_pack())
    q.approve(item["id"])
    with pytest.raises(ReviewError):
        q.approve(item["id"])
    with pytest.raises(ReviewError):
        q.deny(item["id"])


def test_unknown_id_raises(tmp_path):
    q = _q(tmp_path)
    with pytest.raises(ReviewError):
        q.approve("rev.nope")


def test_decisions_audit_log(tmp_path):
    q = _q(tmp_path)
    q.log_decision("deny", "denied last scene (engine pass-through)")
    q.log_decision("social-post", "rev.abc via social-stub: ok")
    assert len(q.decisions) == 2
    assert q.decisions[0]["action"] == "deny"


def test_persistence_roundtrip(tmp_path):
    q = _q(tmp_path)
    item = q.queue_pack(_pack())
    q.approve(item["id"])
    q2 = ReviewQueue(data_dir=tmp_path / "king")
    assert q2.summary()["approved"] == 1
    assert q2.get(item["id"])["caption"] == "A clean caption #lwp"


def test_review_file_is_owner_only(tmp_path):
    q = _q(tmp_path)
    q.queue_pack(_pack())
    mode = stat.S_IMODE(os.stat(q.path).st_mode)
    assert mode == 0o600, f"review.json mode is {oct(mode)}, expected 0o600"


def test_corrupt_review_starts_clean(tmp_path):
    d = tmp_path / "king"
    d.mkdir()
    (d / "review.json").write_text("[broken", encoding="utf-8")
    q = ReviewQueue(data_dir=d)
    assert q.summary()["pending"] == 0
