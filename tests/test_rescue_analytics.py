"""Analytics honesty: deterministic baselines, consent-gated, honest deltas.

Hermetic: tmp rescue home, hand-built walks, no network. Analytics is OF
the business's own site — consent first, no third-party anything.
"""

import pytest

from levi.rescue import analytics, audit, intake, plan, remodel, reveal
from levi.rescue.analytics import Baseline, baseline_from_walk, measure
from levi.rescue.intake import ConsentRefusedError


SITE = "https://tacos.example"


def _home_inv(tmp_path, **kw):
    inv = intake.issue_invitation(
        tmp_path, owner="M. Torres", business="Torres Tacos", site_url=SITE, **kw
    )
    return intake.accept_invitation(tmp_path, inv.id)


def _page(**over):
    p = {
        "url": SITE,
        "status": 200,
        "title": "Torres Tacos",
        "text": "# Torres Tacos\nBest tacos in town. Call 217-555-0100. " + "x" * 200,
        "links": [{"target": SITE + "/menu"}],
        "forms": [{"fields": ["name", "phone"]}],
        "structure": "heading",
    }
    p.update(over)
    return p


def _walk():
    return {
        SITE: _page(),
        SITE + "/menu": _page(
            url=SITE + "/menu",
            title="",
            text="Tacos $3. Al pastor. " + "y" * 200,
            links=[{"target": ""}],
            forms=[],
            structure="",
        ),
    }


# -- measurement -------------------------------------------------------------


def test_measure_is_deterministic_and_order_independent(tmp_path):
    walk = _walk()
    first = measure(walk)
    assert measure(walk) == first
    # reversed key order → identical numbers
    rev = {k: walk[k] for k in reversed(list(walk))}
    assert measure(rev) == first


def test_measure_known_walk(tmp_path):
    v = measure(_walk())
    assert v["reachability"] == 1.0
    assert v["title_coverage"] == 0.5  # one of two pages untitled
    assert v["heading_coverage"] == 0.5
    assert v["contact_presence"] == 1.0
    assert v["content_completeness"] == 1.0
    assert v["link_health"] == 0.5  # one dead link marker
    assert v["form_completeness"] == 1.0
    assert v["conversion_path"] == 2.0  # named-field form present
    assert v["median_page_weight_kb"] > 0
    assert v["max_page_weight_kb"] >= v["median_page_weight_kb"]


def test_measure_empty_walk_refused():
    with pytest.raises(ValueError):
        measure({})


def test_conversion_path_ladder(tmp_path):
    no_contact = {SITE: _page(text="x" * 250, forms=[])}
    assert measure(no_contact)["conversion_path"] == 0.0
    contact_only = {SITE: _page(text="Call 217-555-0100. " + "x" * 250, forms=[])}
    assert measure(contact_only)["conversion_path"] == 1.0


def test_empty_link_and_form_sets_score_healthy_not_zero(tmp_path):
    # no links at all → no evidence of broken links → link_health 1.0
    v = measure({SITE: _page(links=[], forms=[])})
    assert v["link_health"] == 1.0
    assert v["form_completeness"] == 1.0


# -- consent -----------------------------------------------------------------


def test_baseline_requires_consent(tmp_path):
    inv = intake.issue_invitation(
        tmp_path, owner="M. Torres", business="Torres Tacos", site_url=SITE
    )
    with pytest.raises(ConsentRefusedError):
        baseline_from_walk(tmp_path, inv.id, _walk())


def test_baseline_persists_and_reloads(tmp_path):
    inv = _home_inv(tmp_path)
    base = baseline_from_walk(tmp_path, inv.id, _walk())
    assert isinstance(base, Baseline)
    assert base.page_count == 2
    assert set(base.values) == set(analytics.METRICS)
    again = analytics.get_baseline(tmp_path, inv.id)
    assert again.values == base.values
    assert again.cost["provenance"] == "owner-stated"


# -- audit carries the baseline ----------------------------------------------


def test_audit_carries_baseline_and_reloads(tmp_path):
    inv = _home_inv(tmp_path)
    base = baseline_from_walk(tmp_path, inv.id, _walk())
    report = audit.run_audit(
        tmp_path, inv.id, audit.DEFAULT_CHECKS, _walk(), baseline=base
    )
    assert report.baseline["values"] == base.values
    again = audit.get_audit(tmp_path, report.id)
    assert again.baseline["values"] == base.values


def test_audit_without_baseline_stays_none(tmp_path):
    inv = _home_inv(tmp_path)
    report = audit.run_audit(tmp_path, inv.id, audit.DEFAULT_CHECKS, _walk())
    assert report.baseline is None


# -- plan states targets ------------------------------------------------------


def test_plan_items_state_numeric_targets(tmp_path):
    inv = _home_inv(tmp_path)
    base = baseline_from_walk(tmp_path, inv.id, _walk())
    report = audit.run_audit(
        tmp_path, inv.id, audit.DEFAULT_CHECKS, _walk(), baseline=base
    )
    p = plan.build_plan(tmp_path, report)
    assert p.items, "expected findings on the test walk"
    for item in p.items:
        t = item.target
        assert t, "item %r carries no target" % item.id
        assert t["metric"] in analytics.METRICS
        assert t["direction"] in ("at_least", "at_most")
        assert isinstance(t["target"], (int, float))
        assert t["before"] == base.values[t["metric"]]
        assert "TARGET" in item.preview


def test_plan_without_baseline_has_empty_before(tmp_path):
    inv = _home_inv(tmp_path)
    report = audit.run_audit(tmp_path, inv.id, audit.DEFAULT_CHECKS, _walk())
    p = plan.build_plan(tmp_path, report)
    for item in p.items:
        assert item.target.get("before") is None


# -- delta math ----------------------------------------------------------------


def test_metric_deltas_math():
    before = {"title_coverage": 0.5, "median_page_weight_kb": 400.0}
    after = {"title_coverage": 1.0, "median_page_weight_kb": 50.0}
    deltas = analytics.metric_deltas(before, after)
    by_m = {d["metric"]: d for d in deltas}
    t = by_m["title_coverage"]
    assert (t["before"], t["after"], t["delta"]) == (0.5, 1.0, 0.5)
    assert t["target_met"] is True  # at_least 1.0
    w = by_m["median_page_weight_kb"]
    assert w["delta"] == -350.0
    assert w["target_met"] is True  # at_most 100


def test_metric_deltas_honest_about_unmoved():
    before = {"contact_presence": 0.0, "title_coverage": 1.0}
    after = {"contact_presence": 0.0, "title_coverage": 1.0}
    deltas = analytics.metric_deltas(before, after)
    for d in deltas:
        assert d["delta"] == 0.0  # shipped, not smoothed away
    by_m = {d["metric"]: d for d in deltas}
    assert by_m["contact_presence"]["target_met"] is False
    assert by_m["title_coverage"]["target_met"] is True


# -- reveal carries before/after ----------------------------------------------


def _run_episode(tmp_path, costs=None):
    inv = _home_inv(tmp_path, costs=costs)
    walk = _walk()
    base = baseline_from_walk(tmp_path, inv.id, walk)
    report = audit.run_audit(
        tmp_path, inv.id, audit.DEFAULT_CHECKS, walk, baseline=base
    )
    p = plan.build_plan(tmp_path, report)
    plan.approve_plan(tmp_path, p.id, owner="M. Torres")

    def _fix(item, page):
        page = dict(page)
        page["title"] = page["title"] or "Torres Tacos — fixed"
        page["structure"] = "heading"
        if not any(
            "target" in str(link) and link.get("target") for link in page["links"]
        ):
            page["links"] = [{"target": SITE + "/menu"}]
        return page

    transforms = {i.id: _fix for i in p.items}
    results = remodel.run_remodel(tmp_path, p.id, walk, transforms)
    import json

    after_dir = tmp_path / "episodes" / inv.id / "after"
    # fixed pages merged over the full before-walk: the after-state is the
    # whole site, not just the pages the transforms touched
    merged = dict(walk)
    for r in results:
        page = json.loads((after_dir / ("%s.json" % r.item_id)).read_text())
        merged[page.get("url", SITE)] = page
    return inv, p, results, merged


def test_reveal_carries_before_after_and_deltas(tmp_path):
    _, p, results, after_walk = _run_episode(tmp_path)
    rv = reveal.build_reveal(tmp_path, p.id, results, after_walk=after_walk)
    assert rv.metrics_before and rv.metrics_after
    assert len(rv.metric_deltas) == len(analytics.METRICS)
    by_m = {d["metric"]: d for d in rv.metric_deltas}
    assert by_m["title_coverage"]["before"] == 0.5
    assert by_m["title_coverage"]["after"] == 1.0
    assert by_m["title_coverage"]["delta"] == 0.5
    assert by_m["title_coverage"]["target_met"] is True
    # unmoved metric still ships, honestly
    assert by_m["contact_presence"]["delta"] == 0.0
    assert "metrics" in rv.metrics_note
    again = reveal.get_reveal(tmp_path, rv.id)
    assert again.metric_deltas == rv.metric_deltas
    # the after-measurement never overwrote the before-baseline on disk
    before_on_disk = analytics.get_baseline(tmp_path, again.invitation_id)
    assert before_on_disk.values["title_coverage"] == 0.5


def test_reveal_without_baseline_is_honest(tmp_path):
    inv = _home_inv(tmp_path)
    walk = _walk()
    report = audit.run_audit(tmp_path, inv.id, audit.DEFAULT_CHECKS, walk)
    p = plan.build_plan(tmp_path, report)
    plan.approve_plan(tmp_path, p.id, owner="M. Torres")

    def _fix(item, page):
        return dict(page, title="fixed")

    results = remodel.run_remodel(tmp_path, p.id, walk, {i.id: _fix for i in p.items})
    import json

    after_dir = tmp_path / "episodes" / inv.id / "after"
    merged = dict(walk)
    for r in results:
        pg = json.loads((after_dir / ("%s.json" % r.item_id)).read_text())
        merged[pg.get("url", SITE)] = pg
    rv = reveal.build_reveal(tmp_path, p.id, results, after_walk=merged)
    assert rv.metric_deltas == []
    assert "predates analytics" in rv.metrics_note
    # the score delta still works
    assert rv.score_after >= rv.score_before


def test_catalog_targets_are_published():
    for _metric, (desc, direction, target, unit) in analytics.METRIC_CATALOG.items():
        assert desc and direction in ("at_least", "at_most")
        assert isinstance(target, (int, float)) and unit
    assert set(analytics.CHECK_TARGETS.values()) <= set(analytics.METRICS)
