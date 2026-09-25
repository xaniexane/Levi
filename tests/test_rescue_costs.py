"""Cost pillar: stated spend in, draft targets, attested savings out.

Hermetic: tmp rescue home, no network. Every money figure is the
owner's stated spend, labeled "owner-stated" — nothing invented,
nothing silently estimated.
"""

import pytest

from levi.rescue import analytics, audit, intake, plan, remodel, reveal
from levi.rescue.analytics import (
    cost_baseline,
    cost_savings,
    propose_cost_targets,
)
from levi.rescue.plan import PlanNotApprovedError


SITE = "https://tacos.example"

COSTS = [
    {"name": "VPS hosting", "category": "hosting", "amount_usd_monthly": 40},
    {"name": "Zapier", "category": "saas", "amount_usd_monthly": 49.99},
    {
        "name": "Zapier",
        "category": "saas",
        "amount_usd_monthly": 49.99,
        "note": "second workspace",
    },
    {"name": "Reservation widget", "category": "saas", "amount_usd_monthly": 89},
    {"name": "Card processing", "category": "fees", "amount_usd_monthly": 120},
]


def _home_inv(tmp_path, costs=COSTS):
    inv = intake.issue_invitation(
        tmp_path, owner="M. Torres", business="Torres Tacos", site_url=SITE, costs=costs
    )
    return intake.accept_invitation(tmp_path, inv.id)


def _page(**over):
    p = {
        "url": SITE,
        "status": 200,
        "title": "",
        "text": "Welcome. " + "x" * 250,
        "links": [],
        "forms": [],
        "structure": "",
    }
    p.update(over)
    return p


# -- validation ---------------------------------------------------------------


def test_validate_costs_labels_owner_stated(tmp_path):
    items = intake.validate_costs(COSTS)
    assert len(items) == 5
    assert all(i["provenance"] == "owner-stated" for i in items)
    assert items[1]["amount_usd_monthly"] == 49.99


def test_validate_costs_rejects_bad_figures():
    with pytest.raises(ValueError):
        intake.validate_costs(
            [{"name": "x", "category": "saas", "amount_usd_monthly": -5}]
        )
    with pytest.raises(ValueError):
        intake.validate_costs(
            [{"name": "x", "category": "yachts", "amount_usd_monthly": 5}]
        )
    with pytest.raises(ValueError):
        intake.validate_costs([{"category": "saas", "amount_usd_monthly": 5}])
    with pytest.raises(ValueError):
        intake.validate_costs(
            [{"name": "x", "category": "saas", "amount_usd_monthly": "lots"}]
        )


def test_invitation_carries_stated_spend(tmp_path):
    inv = _home_inv(tmp_path)
    assert len(inv.costs) == 5
    again = intake.get_invitation(tmp_path, inv.id)
    assert again.costs == inv.costs


# -- baseline math --------------------------------------------------------------


def test_cost_baseline_math():
    items = intake.validate_costs(COSTS)
    base = cost_baseline(items)
    assert base["total_monthly_usd"] == round(40 + 49.99 + 49.99 + 89 + 120, 2)
    assert base["by_category"]["saas"] == round(49.99 + 49.99 + 89, 2)
    assert base["provenance"] == "owner-stated"


def test_cost_savings_math_and_labels():
    before = cost_baseline(intake.validate_costs(COSTS))
    after = cost_baseline(
        intake.validate_costs(
            [
                {
                    "name": "VPS hosting",
                    "category": "hosting",
                    "amount_usd_monthly": 40,
                },
                {
                    "name": "Card processing",
                    "category": "fees",
                    "amount_usd_monthly": 120,
                },
            ]
        )
    )
    s = cost_savings(before, after)
    assert s["before_monthly_usd"] == before["total_monthly_usd"]
    assert s["after_monthly_usd"] == 160.0
    assert s["savings_monthly_usd"] == round(before["total_monthly_usd"] - 160, 2)
    assert s["savings_annual_usd"] == round(s["savings_monthly_usd"] * 12, 2)
    assert s["provenance"] == "owner-stated"


# -- draft targets --------------------------------------------------------------


def test_propose_cost_targets(tmp_path):
    targets = propose_cost_targets(intake.validate_costs(COSTS))
    by_id = {t["id"]: t for t in targets}
    # Zapier → LEVI-native workflow engine exists in-repo
    zap = by_id["cost-02"]
    assert zap["action"] == "replace"
    assert zap["levi_equivalent"] == "levi.automation.flows"
    assert zap["target_usd"] == 0.0
    # duplicate Zapier line → consolidate
    dup = by_id["cost-03"]
    assert dup["action"] == "consolidate"
    assert dup["target_usd"] == 0.0
    # big SaaS line → review
    widget = by_id["cost-04"]
    assert widget["action"] == "review"
    # fees line → review
    fees = by_id["cost-05"]
    assert fees["action"] == "review"
    # hosting with no equivalent → rehost: the keeper's word is that
    # even hosting cost rates get attacked
    host = by_id["cost-01"]
    assert host["action"] == "rehost"
    assert host["target_usd"] == 40.0  # owner sets the cut on approval
    assert "right-size" in host["rationale"]
    for t in targets:
        assert t["status"] == "proposed"
        assert t["provenance"] == "owner-stated"


def test_replace_only_when_module_importable(tmp_path, monkeypatch):
    import levi.rescue.analytics as an

    monkeypatch.setattr(an, "_module_available", lambda m: False)
    targets = propose_cost_targets(intake.validate_costs(COSTS))
    zap = targets[1]
    # module "missing" → no replace promised; falls to review (saas ≥ 50? no,
    # 49.99) → keep. Either way, never "replace".
    assert zap["action"] in ("keep", "review")


def test_plan_carries_cost_targets(tmp_path):
    inv = _home_inv(tmp_path)
    walk = {SITE: _page()}
    base = analytics.baseline_from_walk(tmp_path, inv.id, walk)
    report = audit.run_audit(
        tmp_path, inv.id, audit.DEFAULT_CHECKS, walk, baseline=base
    )
    p = plan.build_plan(tmp_path, report)
    assert len(p.cost_targets) == 5
    assert {t["action"] for t in p.cost_targets} >= {"replace", "consolidate"}
    again = plan.get_plan(tmp_path, p.id)
    assert again.cost_targets == p.cost_targets
    # baseline carries the money side
    assert (
        report.baseline["cost"]["total_monthly_usd"]
        == cost_baseline(inv.costs)["total_monthly_usd"]
    )


# -- attestation + reveal ---------------------------------------------------------


def _run_episode(tmp_path):
    inv = _home_inv(tmp_path)
    walk = {SITE: _page()}
    base = analytics.baseline_from_walk(tmp_path, inv.id, walk)
    report = audit.run_audit(
        tmp_path, inv.id, audit.DEFAULT_CHECKS, walk, baseline=base
    )
    p = plan.build_plan(tmp_path, report)
    plan.approve_plan(tmp_path, p.id, owner="M. Torres")

    def _fix(item, page):
        return dict(page, title="Torres Tacos")

    results = remodel.run_remodel(tmp_path, p.id, walk, {i.id: _fix for i in p.items})
    import json

    after_dir = tmp_path / "episodes" / inv.id / "after"
    merged = {}
    for r in results:
        pg = json.loads((after_dir / ("%s.json" % r.item_id)).read_text())
        merged[pg.get("url", SITE)] = pg
    return inv, p, results, merged


def test_attest_costs_gating(tmp_path):
    inv = _home_inv(tmp_path)
    walk = {SITE: _page()}
    base = analytics.baseline_from_walk(tmp_path, inv.id, walk)
    report = audit.run_audit(
        tmp_path, inv.id, audit.DEFAULT_CHECKS, walk, baseline=base
    )
    p = plan.build_plan(tmp_path, report)
    # unapproved plan → refused
    with pytest.raises(PlanNotApprovedError):
        reveal.attest_costs(
            tmp_path,
            p.id,
            "M. Torres",
            [{"name": "VPS", "category": "hosting", "amount_usd_monthly": 40}],
        )
    plan.approve_plan(tmp_path, p.id, owner="M. Torres")
    # wrong owner → refused
    with pytest.raises(ValueError):
        reveal.attest_costs(
            tmp_path,
            p.id,
            "R. Impostor",
            [{"name": "VPS", "category": "hosting", "amount_usd_monthly": 40}],
        )
    # bad figures → refused, never silently repaired
    with pytest.raises(ValueError):
        reveal.attest_costs(
            tmp_path,
            p.id,
            "M. Torres",
            [{"name": "VPS", "category": "hosting", "amount_usd_monthly": -1}],
        )


def test_reveal_carries_verified_savings(tmp_path):
    _, p, results, after_walk = _run_episode(tmp_path)
    # owner cancels Zapier + the widget, keeps the rest
    attested = reveal.attest_costs(
        tmp_path,
        p.id,
        "M. Torres",
        [
            {"name": "VPS hosting", "category": "hosting", "amount_usd_monthly": 40},
            {"name": "Card processing", "category": "fees", "amount_usd_monthly": 120},
        ],
    )
    assert attested["attested_by"] == "M. Torres"
    rv = reveal.build_reveal(tmp_path, p.id, results, after_walk=after_walk)
    assert (
        rv.cost_before["total_monthly_usd"]
        == cost_baseline(intake.validate_costs(COSTS))["total_monthly_usd"]
    )
    assert rv.cost_after["total_monthly_usd"] == 160.0
    assert rv.savings["savings_monthly_usd"] == round(
        rv.cost_before["total_monthly_usd"] - 160.0, 2
    )
    assert rv.savings["provenance"] == "owner-stated"
    assert "$" in rv.cost_note
    again = reveal.get_reveal(tmp_path, rv.id)
    assert again.savings == rv.savings


def test_reveal_without_attestation_is_honest(tmp_path):
    _, p, results, after_walk = _run_episode(tmp_path)
    rv = reveal.build_reveal(tmp_path, p.id, results, after_walk=after_walk)
    assert rv.savings == {}
    assert "not yet attested" in rv.cost_note
    assert rv.cost_before is not None  # baseline spend still on the record


def test_reveal_without_cost_baseline_is_honest(tmp_path):
    inv = _home_inv(tmp_path, costs=[])
    walk = {SITE: _page()}
    base = analytics.baseline_from_walk(tmp_path, inv.id, walk)
    assert base.cost["total_monthly_usd"] == 0.0
    report = audit.run_audit(
        tmp_path, inv.id, audit.DEFAULT_CHECKS, walk, baseline=base
    )
    p = plan.build_plan(tmp_path, report)
    assert p.cost_targets == []
    plan.approve_plan(tmp_path, p.id, owner="M. Torres")

    def _fix(item, page):
        return dict(page, title="t")

    results = remodel.run_remodel(tmp_path, p.id, walk, {i.id: _fix for i in p.items})
    rv = reveal.build_reveal(tmp_path, p.id, results, after_walk=walk)
    assert rv.cost_before["total_monthly_usd"] == 0.0
    assert rv.savings == {}
    assert "not yet attested" in rv.cost_note


# -- hosting: the keeper's word — even hosting cost rates ----------------------

HOSTING_COSTS = [
    {"name": "VPS hosting", "category": "hosting", "amount_usd_monthly": 40},
    {"name": "Managed WordPress host", "category": "hosting", "amount_usd_monthly": 29},
    {"name": "Image CDN", "category": "hosting", "amount_usd_monthly": 10},
    {"name": "Database hosting", "category": "hosting", "amount_usd_monthly": 35},
    {"name": "Domain", "category": "fees", "amount_usd_monthly": 1.25},
]


def test_hosting_lines_get_rehost_proposals():
    targets = propose_cost_targets(intake.validate_costs(HOSTING_COSTS))
    by_id = {t["id"]: t for t in targets}
    vps = by_id["cost-01"]
    assert vps["action"] == "rehost"
    assert vps["target_usd"] == 40.0  # owner sets the cut, never invented
    assert "right-size" in vps["rationale"]
    assert "shop cheaper providers" in vps["rationale"]
    # three hosting bills on the record → consolidation play named
    assert "consolidate" in vps["rationale"]
    assert vps["provenance"] == "owner-stated"
    assert vps["status"] == "proposed"
    cdn = by_id["cost-03"]
    assert cdn["action"] == "rehost"
    assert cdn["target_usd"] == 10.0


def test_hosting_consolidation_duplicate_names():
    costs = intake.validate_costs(
        [
            {"name": "VPS hosting", "category": "hosting", "amount_usd_monthly": 40},
            {
                "name": "VPS Hosting",
                "category": "hosting",
                "amount_usd_monthly": 40,
                "note": "staging box",
            },
        ]
    )
    targets = propose_cost_targets(costs)
    assert targets[0]["action"] == "rehost"
    assert targets[1]["action"] == "consolidate"
    assert targets[1]["target_usd"] == 0.0
    assert "duplicate" in targets[1]["rationale"]


def test_database_hosting_replace_is_static_local_first():
    # "Database hosting" matches the datastore equivalent fragment and the
    # module imports — the honest LEVI-native answer to a database meter.
    targets = propose_cost_targets(intake.validate_costs(HOSTING_COSTS))
    db = {t["id"]: t for t in targets}["cost-04"]
    assert db["action"] == "replace"
    assert db["levi_equivalent"] == "levi.forge.datastore"
    assert db["target_usd"] == 0.0


def test_hosting_savings_math():
    before = analytics.cost_baseline(intake.validate_costs(HOSTING_COSTS))
    after = analytics.cost_baseline(
        intake.validate_costs(
            [
                {
                    "name": "VPS hosting",
                    "category": "hosting",
                    "amount_usd_monthly": 12,
                },
                {"name": "Domain", "category": "fees", "amount_usd_monthly": 1.25},
            ]
        )
    )
    h = analytics.hosting_savings(before, after)
    assert h["before_monthly_usd"] == round(40 + 29 + 10 + 35, 2)
    assert h["after_monthly_usd"] == 12.0
    assert h["savings_monthly_usd"] == round(40 + 29 + 10 + 35 - 12, 2)
    assert h["savings_annual_usd"] == round(h["savings_monthly_usd"] * 12, 2)
    assert h["provenance"] == "owner-stated"


def test_hosting_savings_empty_without_hosting_spend():
    costs = [{"name": "Domain", "category": "fees", "amount_usd_monthly": 1.25}]
    before = analytics.cost_baseline(intake.validate_costs(costs))
    after = analytics.cost_baseline(intake.validate_costs(costs))
    assert analytics.hosting_savings(before, after) == {}


def _run_episode_with_costs(tmp_path, costs):
    inv = intake.issue_invitation(
        tmp_path, owner="M. Torres", business="Torres Tacos", site_url=SITE, costs=costs
    )
    inv = intake.accept_invitation(tmp_path, inv.id)
    walk = {SITE: _page()}
    base = analytics.baseline_from_walk(tmp_path, inv.id, walk)
    report = audit.run_audit(
        tmp_path, inv.id, audit.DEFAULT_CHECKS, walk, baseline=base
    )
    p = plan.build_plan(tmp_path, report)
    plan.approve_plan(tmp_path, p.id, owner="M. Torres")

    def _fix(item, page):
        return dict(page, title="Torres Tacos")

    results = remodel.run_remodel(tmp_path, p.id, walk, {i.id: _fix for i in p.items})
    import json

    after_dir = tmp_path / "episodes" / inv.id / "after"
    merged = {}
    for r in results:
        pg = json.loads((after_dir / ("%s.json" % r.item_id)).read_text())
        merged[pg.get("url", SITE)] = pg
    return inv, p, results, merged


def test_reveal_carries_hosting_savings(tmp_path):
    _, p, results, after_walk = _run_episode(tmp_path)
    # owner right-sizes the host: $40 → $12
    reveal.attest_costs(
        tmp_path,
        p.id,
        "M. Torres",
        [
            {"name": "VPS hosting", "category": "hosting", "amount_usd_monthly": 12},
            {"name": "Card processing", "category": "fees", "amount_usd_monthly": 120},
        ],
    )
    rv = reveal.build_reveal(tmp_path, p.id, results, after_walk=after_walk)
    h = rv.hosting_savings
    assert h["before_monthly_usd"] == 40.0
    assert h["after_monthly_usd"] == 12.0
    assert h["savings_monthly_usd"] == 28.0
    assert h["savings_annual_usd"] == 336.0
    assert h["provenance"] == "owner-stated"
    assert "hosting" in rv.cost_note
    assert "$28.00/mo" in rv.cost_note
    again = reveal.get_reveal(tmp_path, rv.id)
    assert again.hosting_savings == h


def test_reveal_no_hosting_spend_is_honest(tmp_path):
    costs = [
        {"name": "Reservation widget", "category": "saas", "amount_usd_monthly": 89},
        {"name": "Card processing", "category": "fees", "amount_usd_monthly": 120},
    ]
    _, p, results, after_walk = _run_episode_with_costs(tmp_path, costs)
    reveal.attest_costs(tmp_path, p.id, "M. Torres", costs)
    rv = reveal.build_reveal(tmp_path, p.id, results, after_walk=after_walk)
    assert rv.hosting_savings == {}
    assert "no hosting spend" in rv.cost_note
    # total savings still carried honestly
    assert rv.savings["savings_monthly_usd"] == 0.0


# -- hosting combos: recovered hybrid cost-cutting method ---------------------

COMBO_COSTS = [
    {
        "name": "Vercel Pro site hosting",
        "category": "hosting",
        "amount_usd_monthly": 20,
    },
    {
        "name": "Docker registry + swarm hosting",
        "category": "hosting",
        "amount_usd_monthly": 18,
    },
    {"name": "Always-on worker VPS", "category": "hosting", "amount_usd_monthly": 15},
    {"name": "Bare metal colo server", "category": "hosting", "amount_usd_monthly": 95},
    {"name": "Neon managed Postgres", "category": "hosting", "amount_usd_monthly": 24},
]


def test_each_hosting_combo_fires_on_the_right_line():
    targets = propose_cost_targets(intake.validate_costs(COMBO_COSTS))
    by_name = {t["item"]: t for t in targets}
    expect = {
        "Vercel Pro site hosting": ("static-first-rebuild", "static-first rebuild"),
        "Docker registry + swarm hosting": ("de-containerize", "de-containerize"),
        "Always-on worker VPS": ("schedule-dont-idle", "schedule, don't idle"),
        "Bare metal colo server": ("downsize-the-iron", "downsize the iron"),
        "Neon managed Postgres": ("de-manage-the-database", "de-manage the database"),
    }
    for name, (action, combo_label) in expect.items():
        t = by_name[name]
        assert t["action"] == action, name
        assert t["combo"] == combo_label, name
        # rationale names the combo, no invented savings numbers
        assert combo_label in t["rationale"], name
        assert "Draft only" in t["rationale"], name
        # target stays the stated amount — the owner sets the cut
        stated = {c["name"]: c["amount_usd_monthly"] for c in COMBO_COSTS}[name]
        assert t["target_usd"] == stated, name
        assert (
            "$" not in t["rationale"]
            or "owner-stated" in t["rationale"]
            or "$0" not in t["rationale"]
        ), name
        assert t["provenance"] == "owner-stated", name
        assert t["status"] == "proposed", name


def test_combo_actions_are_registered():
    assert {
        "static-first-rebuild",
        "de-containerize",
        "schedule-dont-idle",
        "downsize-the-iron",
        "de-manage-the-database",
    } <= set(analytics.COST_ACTIONS)


def test_wordpress_host_gets_static_first_not_generic_rehost():
    targets = propose_cost_targets(intake.validate_costs(HOSTING_COSTS))
    wp = {t["id"]: t for t in targets}["cost-02"]
    assert wp["action"] == "static-first-rebuild"
    assert wp["combo"] == "static-first rebuild"
    assert wp["target_usd"] == 29.0  # owner sets the cut, never invented


def test_levi_equivalent_outranks_combo_for_database():
    # "Database hosting" matches the datastore equivalent — "replace" wins
    # over the de-manage-the-database pattern (honest-import routing first).
    targets = propose_cost_targets(intake.validate_costs(HOSTING_COSTS))
    db = {t["id"]: t for t in targets}["cost-04"]
    assert db["action"] == "replace"
    assert db["combo"] == ""


def test_plain_hosting_lines_still_get_generic_rehost():
    targets = propose_cost_targets(intake.validate_costs(HOSTING_COSTS))
    by_id = {t["id"]: t for t in targets}
    vps = by_id["cost-01"]
    assert vps["action"] == "rehost"
    assert vps["combo"] == ""
    assert "right-size" in vps["rationale"]
    cdn = by_id["cost-03"]
    assert cdn["action"] == "rehost"


def test_no_hosting_lines_means_no_combo_actions():
    costs = intake.validate_costs(
        [
            {
                "name": "Reservation widget",
                "category": "saas",
                "amount_usd_monthly": 89,
            },
            {"name": "Card processing", "category": "fees", "amount_usd_monthly": 120},
            {"name": "Domain", "category": "fees", "amount_usd_monthly": 1.25},
        ]
    )
    targets = propose_cost_targets(costs)
    assert len(targets) == 3
    for t in targets:
        assert t["action"] in (
            "keep",
            "review",
            "replace",
            "consolidate",
            "drop",
            "rehost",
        )
        assert t["combo"] == ""
        assert t["status"] == "proposed"
        assert t["provenance"] == "owner-stated"


def test_empty_costs_produce_empty_targets():
    assert propose_cost_targets(intake.validate_costs([])) == []


def test_combos_flow_through_plan_and_reveal(tmp_path):
    # combo entries survive plan build → reveal receipt with hosting savings
    costs = COMBO_COSTS[:3] + [
        {"name": "Domain", "category": "fees", "amount_usd_monthly": 1.25}
    ]
    inv = intake.issue_invitation(
        tmp_path, owner="M. Torres", business="Torres Tacos", site_url=SITE, costs=costs
    )
    inv = intake.accept_invitation(tmp_path, inv.id)
    walk = {SITE: _page()}
    base = analytics.baseline_from_walk(tmp_path, inv.id, walk)
    report = audit.run_audit(
        tmp_path, inv.id, audit.DEFAULT_CHECKS, walk, baseline=base
    )
    p = plan.build_plan(tmp_path, report)
    actions = {t["action"] for t in p.cost_targets}
    assert actions >= {"static-first-rebuild", "de-containerize", "schedule-dont-idle"}
    plan.approve_plan(tmp_path, p.id, owner="M. Torres")
    # owner deploys the combos: three hosting bills down to one cheap box
    reveal.attest_costs(
        tmp_path,
        p.id,
        "M. Torres",
        [
            {"name": "One small box", "category": "hosting", "amount_usd_monthly": 6},
            {"name": "Domain", "category": "fees", "amount_usd_monthly": 1.25},
        ],
    )

    def _fix(item, page):
        return dict(page, title="t")

    results = remodel.run_remodel(tmp_path, p.id, walk, {i.id: _fix for i in p.items})
    import json

    after_dir = tmp_path / "episodes" / inv.id / "after"
    merged = {}
    for r in results:
        pg = json.loads((after_dir / ("%s.json" % r.item_id)).read_text())
        merged[pg.get("url", SITE)] = pg
    rv = reveal.build_reveal(tmp_path, p.id, results, after_walk=merged)
    h = rv.hosting_savings
    assert h["before_monthly_usd"] == round(20 + 18 + 15, 2)
    assert h["after_monthly_usd"] == 6.0
    assert h["savings_monthly_usd"] == round(20 + 18 + 15 - 6, 2)
    assert h["provenance"] == "owner-stated"
