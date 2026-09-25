"""Tests for the LEVI Factory Bag (Santa's bag of firsts)."""

import pytest

from levi.factory.bag import Bag, CATEGORIES, PLAYBOOK


@pytest.fixture
def bag(tmp_path):
    return Bag(data_dir=tmp_path / "factory")


def test_queue_and_get(bag):
    item = bag.queue("skill", "room-sense", "Nanobit becomes the room")
    assert item.status == "queued"
    assert item.receipt
    assert bag.get(item.item_id).title == "room-sense"


def test_queue_rejects_unknown_category(bag):
    with pytest.raises(ValueError):
        bag.queue("nonsense", "x", "y")


def test_next_up_is_fifo(bag):
    a = bag.queue("skill", "first", "b1")
    bag.queue("find", "second", "b2")
    assert bag.next_up().item_id == a.item_id


def test_next_up_empty(bag):
    assert bag.next_up() is None


def test_draft_then_deliver(bag, tmp_path):
    from levi.factory import review as bag_review

    item = bag.queue(
        "method",
        "Room Sense Method",
        "Nanobit becomes the room: the teachable pattern",
    )
    draft = tmp_path / "d.md"
    draft.write_text(
        "DRAFT — needs a second pair of eyes before release.\n\n"
        "The Room Sense Method.\n\n"
        "Nanobit walks into a room and becomes the room: 3 sensors, 1 model, "
        "0 cloud calls. Chauncey approved the pattern on 2026-09-19 in "
        "Springfield.\n"
        "Teachable steps: name the pattern, say when to use it, run the "
        "steps, name the anti-pattern it replaces.\n",
        encoding="utf-8",
    )
    bag.mark_draft(item.item_id, str(draft), "drafted by night shift")
    assert bag.get(item.item_id).status == "draft"
    rec = bag_review.review_draft(
        item.item_id, str(draft), item.title, item.brief, home=bag.data_dir
    )
    assert rec["passed"]
    bag.deliver(item.item_id, "reviewed, shipped")
    got = bag.get(item.item_id)
    assert got.status == "delivered"
    assert "[delivery note]" in got.brief


def test_deliver_refuses_queued(bag):
    item = bag.queue("tool", "t", "b")
    with pytest.raises(ValueError):
        bag.deliver(item.item_id)


def test_receipts_chain(bag):
    a = bag.queue("skill", "a", "b")
    b = bag.queue("skill", "c", "d")
    assert a.receipt != b.receipt


def test_stats(bag):
    bag.queue("skill", "a", "b")
    item = bag.queue("find", "c", "d")
    bag.mark_draft(item.item_id, "/tmp/x.md")
    s = bag.stats()
    assert s["total"] == 2
    assert s["queued"] == 1
    assert s["draft"] == 1
    assert s["delivered"] == 0


def test_list_filters(bag):
    bag.queue("skill", "a", "b")
    bag.queue("find", "c", "d")
    assert len(bag.list(category="skill")) == 1
    assert len(bag.list(status="queued")) == 2


def test_eyes_only_flag(bag):
    item = bag.queue("method", "reveal", "sealed", eyes_only=True)
    assert bag.get(item.item_id).eyes_only is True


def test_persistence(tmp_path):
    b1 = Bag(data_dir=tmp_path / "factory")
    item = b1.queue("skill", "persist-me", "b")
    b2 = Bag(data_dir=tmp_path / "factory")
    assert b2.get(item.item_id).title == "persist-me"


def test_every_category_has_a_playbook():
    assert set(PLAYBOOK) == set(CATEGORIES)
