"""The plan-approval gate: remodel runs only on owner-approved plans.

Hermetic: tmp rescue home, hand-built walks, real forge rail, no network.
"""

import pytest

from levi.rescue import audit, intake, plan, remodel
from levi.rescue.plan import PlanNotApprovedError


SITE = "https://tacos.example"


def _setup(tmp_path):
    inv = intake.issue_invitation(
        tmp_path, owner="M. Torres", business="Torres Tacos", site_url=SITE
    )
    intake.accept_invitation(tmp_path, inv.id)
    walk = {
        SITE: {
            "url": SITE,
            "status": 200,
            "title": "",
            "text": "# Torres Tacos\nCall 217-555-0100.",
            "links": [],
            "forms": [],
            "structure": "heading",
        }
    }
    report = audit.run_audit(tmp_path, inv.id, audit.DEFAULT_CHECKS, walk)
    assert [f.check_id for f in report.findings] == ["has-title"]
    p = plan.build_plan(tmp_path, report)
    return inv, walk, p


def _fix_title(item, page):
    page = dict(page)
    page["title"] = "Torres Tacos — Springfield"
    return page


def test_remodel_refused_on_draft_plan(tmp_path):
    _, walk, p = _setup(tmp_path)
    with pytest.raises(PlanNotApprovedError):
        remodel.run_remodel(tmp_path, p.id, walk, {"item-01": _fix_title})


def test_remodel_refused_on_denied_plan(tmp_path):
    _, walk, p = _setup(tmp_path)
    plan.deny_plan(tmp_path, p.id, owner="M. Torres", note="too pricey")
    with pytest.raises(PlanNotApprovedError):
        remodel.run_remodel(tmp_path, p.id, walk, {"item-01": _fix_title})


def test_approved_plan_remodels_and_verifies(tmp_path):
    inv, walk, p = _setup(tmp_path)
    plan.approve_plan(tmp_path, p.id, owner="M. Torres", note="do it")
    results = remodel.run_remodel(tmp_path, p.id, walk, {"item-01": _fix_title})
    assert len(results) == 1
    r = results[0]
    assert r.before_sha256 and r.after_sha256
    assert r.before_sha256 != r.after_sha256
    assert r.verified is True
    assert r.receipt["verified"] is True
    assert r.proposal_id  # every step rode the rail


def test_failed_transform_is_receipted_as_miss(tmp_path):
    _, walk, p = _setup(tmp_path)
    plan.approve_plan(tmp_path, p.id, owner="M. Torres")

    def _boom(item, page):
        raise RuntimeError("transform exploded")

    results = remodel.run_remodel(tmp_path, p.id, walk, {"item-01": _boom})
    assert results[0].verified is False
    assert results[0].receipt["verified"] is False  # the miss is on the record


def test_item_without_transform_is_skipped_honestly(tmp_path):
    _, walk, p = _setup(tmp_path)
    plan.approve_plan(tmp_path, p.id, owner="M. Torres")
    results = remodel.run_remodel(tmp_path, p.id, walk, {})
    assert results[0].verified is False
    assert "no transform" in results[0].note


def test_plan_items_carry_rail_proposals(tmp_path):
    _, _, p = _setup(tmp_path)
    assert all(i.proposal_id for i in p.items)
    previews = plan.preview_plan(tmp_path, p.id)
    assert len(previews) == len(p.items)
    assert all("action" in pv for pv in previews)
