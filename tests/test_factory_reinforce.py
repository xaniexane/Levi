"""Factory reinforcement tests — review gate and night-shift throughput."""

from __future__ import annotations

import pytest

from levi.factory import bag as bagmod
from levi.factory import review as bag_review
from levi.factory.bag import (
    NIGHT_SHIFT_DEEP_QUEUE,
    NIGHT_SHIFT_MAX_BATCH,
    Bag,
    night_shift_batch_size,
)


@pytest.fixture
def bag(tmp_path):
    return Bag(data_dir=tmp_path / "factory")


CLEAN_DRAFT = """DRAFT — needs a second pair of eyes before release.

Service offering: Wren site lifts.

The promise: Wren audits a small-business website in 5 days and ships a
written lift plan. Price: $300 standard, $600 premium, one-time. Chauncey
approved the price shape on 2026-09-19 in Springfield.

Pipeline: analyze, quote, deliver, paid, showcase. Receipt: the plan, the
invoice, and the showcase entry.
"""


def _drafted(bag, tmp_path, title="Wren site lifts", brief=None, body=CLEAN_DRAFT):
    brief = (
        brief
        if brief is not None
        else (
            "a service offering sheet for Wren site lifts: the promise, the "
            "pipeline, the price shape, and the receipt it leaves"
        )
    )
    item = bag.queue("service", title, brief)
    path = tmp_path / f"{item.item_id}.md"
    path.write_text(body, encoding="utf-8")
    bag.mark_draft(item.item_id, str(path), "night shift")
    return item


# ------------------------------------------------------------------ review
def test_review_passes_clean_draft(bag, tmp_path):
    item = _drafted(bag, tmp_path)
    rec = bag_review.review_draft(
        item.item_id,
        bag.get(item.item_id).draft_path,
        item.title,
        item.brief,
        home=bag.data_dir,
    )
    assert rec["passed"] is True
    assert all(c["passed"] for c in rec["checklist"].values())
    assert rec["notes"] == []
    stored = bag_review.load_review(bag.data_dir, item.item_id)
    assert stored and stored["passed"] is True


def test_review_fails_missing_banner(bag, tmp_path):
    body = CLEAN_DRAFT.replace(
        "DRAFT — needs a second pair of eyes before release.\n\n", ""
    )
    item = _drafted(bag, tmp_path, body=body)
    rec = bag_review.review_draft(
        item.item_id,
        bag.get(item.item_id).draft_path,
        item.title,
        item.brief,
        home=bag.data_dir,
    )
    assert rec["passed"] is False
    assert rec["checklist"]["banner"]["passed"] is False


def test_review_fails_filler(bag, tmp_path):
    body = (
        "DRAFT — needs a second pair of eyes before release.\n\n"
        "In today's ever-evolving landscape, we delve into the tapestry of "
        "service offerings.\n\n"
        "Wren site lifts: 5 days, $300 standard, $600 premium. Chauncey "
        "approved the promise, the pipeline, the price shape, the receipt.\n"
    )
    item = _drafted(bag, tmp_path, body=body)
    rec = bag_review.review_draft(
        item.item_id,
        bag.get(item.item_id).draft_path,
        item.title,
        item.brief,
        home=bag.data_dir,
    )
    assert rec["passed"] is False
    assert rec["checklist"]["no_filler"]["passed"] is False
    assert "delve" in rec["checklist"]["no_filler"]["note"]


def test_review_fails_vague_draft(bag, tmp_path):
    body = (
        "DRAFT — needs a second pair of eyes before release.\n\n"
        "Wren site lifts are a service offering with a promise and a pipeline "
        "and a price shape and a receipt.\n"
    )
    item = _drafted(bag, tmp_path, body=body)
    rec = bag_review.review_draft(
        item.item_id,
        bag.get(item.item_id).draft_path,
        item.title,
        item.brief,
        home=bag.data_dir,
    )
    assert rec["passed"] is False
    assert rec["checklist"]["concrete_specifics"]["passed"] is False


def test_review_missing_file(bag, tmp_path):
    item = bag.queue("skill", "x", "y")
    rec = bag_review.review_draft(
        item.item_id, str(tmp_path / "nope.md"), home=bag.data_dir
    )
    assert rec["passed"] is False
    assert bag_review.load_review(bag.data_dir, "unknown") is None


# ------------------------------------------------------------------ gate
def test_deliver_refuses_unreviewed(bag, tmp_path):
    item = _drafted(bag, tmp_path)
    with pytest.raises(ValueError, match="unreviewed"):
        bag.deliver(item.item_id)


def test_deliver_refuses_failed_review(bag, tmp_path):
    item = _drafted(bag, tmp_path, body="no banner here, just words\n")
    rec = bag_review.review_draft(
        item.item_id,
        bag.get(item.item_id).draft_path,
        item.title,
        item.brief,
        home=bag.data_dir,
    )
    assert rec["passed"] is False
    with pytest.raises(ValueError, match="failed review"):
        bag.deliver(item.item_id)


def test_deliver_after_passing_review(bag, tmp_path):
    item = _drafted(bag, tmp_path)
    rec = bag_review.review_draft(
        item.item_id,
        bag.get(item.item_id).draft_path,
        item.title,
        item.brief,
        home=bag.data_dir,
    )
    assert rec["passed"] is True
    delivered = bag.deliver(item.item_id, "shipped")
    assert delivered.status == "delivered"


# -------------------------------------------------------------- throughput
def test_batch_constants():
    assert NIGHT_SHIFT_MAX_BATCH == 3
    assert NIGHT_SHIFT_DEEP_QUEUE == 6


def test_batch_size_rule():
    assert night_shift_batch_size(0) == 1
    assert night_shift_batch_size(5) == 1
    assert night_shift_batch_size(6) == 3
    assert night_shift_batch_size(20) == 3


def test_new_categories_have_playbooks():
    assert "drill" in bagmod.CATEGORIES
    assert "field-guide" in bagmod.CATEGORIES
    assert bagmod.PLAYBOOK["drill"]
    assert bagmod.PLAYBOOK["field-guide"]
    assert set(bagmod.PLAYBOOK) == set(bagmod.CATEGORIES)
