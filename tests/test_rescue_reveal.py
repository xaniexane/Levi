"""Reveal completeness: before/after diff verified, or no reveal ships.

Hermetic: tmp rescue home, hand-built walks, real forge rail, no network.
"""

import json

import pytest

from levi.rescue import audit, intake, plan, remodel, reveal
from levi.rescue.reveal import IncompleteReceiptError


SITE = "https://tacos.example"


def _page(**over):
    p = {
        "url": SITE,
        "status": 200,
        "title": "",
        "text": "Welcome to our page.",
        "links": [],
        "forms": [],
        "structure": "",
    }
    p.update(over)
    return p


def _run_episode(tmp_path):
    inv = intake.issue_invitation(
        tmp_path, owner="M. Torres", business="Torres Tacos", site_url=SITE
    )
    intake.accept_invitation(tmp_path, inv.id)
    walk = {SITE: _page()}
    report = audit.run_audit(tmp_path, inv.id, audit.DEFAULT_CHECKS, walk)
    p = plan.build_plan(tmp_path, report)
    plan.approve_plan(tmp_path, p.id, owner="M. Torres")

    def _fix(item, page):
        # Each transform applies independently to the before-state, so each
        # one produces a fully-fixed page (later merges take one per URL).
        page = dict(page)
        page["title"] = "Torres Tacos — Springfield"
        page["text"] = "# Torres Tacos\nCall 217-555-0100."
        page["structure"] = "heading"
        return page

    transforms = {i.id: _fix for i in p.items}
    results = remodel.run_remodel(tmp_path, p.id, walk, transforms)
    after_dir = tmp_path / "episodes" / inv.id / "after"
    # one after-page per item id; collapse to a single after-walk per URL
    # (transforms apply independently, each producing a fully-fixed page)
    merged = {}
    for r in results:
        page = json.loads((after_dir / ("%s.json" % r.item_id)).read_text())
        merged[page.get("url", SITE)] = page
    return inv, p, results, merged


def test_reveal_refused_when_results_missing(tmp_path):
    _, p, results, _ = _run_episode(tmp_path)
    with pytest.raises(IncompleteReceiptError):
        reveal.build_reveal(tmp_path, p.id, results[:-1])


def test_reveal_refused_when_hash_missing(tmp_path):
    _, p, results, _ = _run_episode(tmp_path)
    bad = [r for r in results]
    bad[0].after_sha256 = ""
    with pytest.raises(IncompleteReceiptError):
        reveal.build_reveal(tmp_path, p.id, bad)


def test_complete_reveal_verifies_and_scores(tmp_path):
    inv, p, results, after_walk = _run_episode(tmp_path)
    rv = reveal.build_reveal(tmp_path, p.id, results, after_walk=after_walk)
    assert rv.score_before < rv.score_after  # the remodel moved the needle
    assert rv.score_after == 100
    assert len(rv.items) == len(p.items)
    for it in rv.items:
        assert it.before_sha256 and it.after_sha256
        assert it.before_sha256 != it.after_sha256
        assert it.verified is True
    assert rv.status == reveal.STATUS_OPEN


def test_owner_acceptance_closes_episode(tmp_path):
    _, p, results, after_walk = _run_episode(tmp_path)
    rv = reveal.build_reveal(tmp_path, p.id, results, after_walk=after_walk)
    done = reveal.approve_reveal(tmp_path, rv.id, owner="M. Torres", note="looks great")
    assert done.status == reveal.STATUS_ACCEPTED
    assert done.accepted_at
    again = reveal.get_reveal(tmp_path, rv.id)
    assert again.status == reveal.STATUS_ACCEPTED


def test_clean_audit_reveals_nothing_to_fix(tmp_path):
    inv = intake.issue_invitation(
        tmp_path, owner="M. Torres", business="Torres Tacos", site_url=SITE
    )
    intake.accept_invitation(tmp_path, inv.id)
    walk = {
        SITE: _page(
            title="Torres Tacos",
            text="# Torres Tacos\nCall 217-555-0100.",
            structure="heading",
        )
    }
    report = audit.run_audit(tmp_path, inv.id, audit.DEFAULT_CHECKS, walk)
    assert report.score == 100
    p = plan.build_plan(tmp_path, report)
    plan.approve_plan(tmp_path, p.id, owner="M. Torres")
    results = remodel.run_remodel(tmp_path, p.id, walk, {})
    rv = reveal.build_reveal(tmp_path, p.id, results)
    assert rv.items == []
    assert rv.score_before == rv.score_after == 100
