"""Hermetic tests for the NeighborOS full build (spec systems 1, 2, 5–8,
moats, PWA shell, rail registry, tiers).

No HOME writes: stores are constructed on tmp_path. No network, no
randomness (invite codes passed explicitly). All example data synthetic.
"""

import json

import pytest

from levi.neighbor import (
    academy,
    admin,
    lift,
    liquidity,
    monetize,
    pay,
    policies as policies_mod,
    post,
    pwa,
    rails,
    supply,
    twins,
    waitlist,
    work,
)
from levi.neighbor.store import Store

NOW = "2026-09-23T08:00:00+00:00"


def _store(tmp_path):
    return Store(tmp_path / "neighbor")


def _policies(store):
    return policies_mod.load_policies(store)


def _set_stage(store, stage):
    path = store.base / "policies.json"
    store.ensure_policies()
    cfg = json.loads(path.read_text())
    cfg["gates"]["stage"] = stage
    path.write_text(json.dumps(cfg))
    return cfg


def _complete_checklist(store, stage):
    """Mark the operator's checklist for a stage complete (operator's own list)."""
    path = store.base / "policies.json"
    store.ensure_policies()
    cfg = json.loads(path.read_text())
    for item in cfg["gates"]["checklists"].get(stage, []):
        item["done"] = True
    path.write_text(json.dumps(cfg))


def _worker(store, **kw):
    return work.register_worker(
        store,
        name=kw.get("name", "Bob W"),
        contact=kw.get("contact", "bob@example.com"),
        categories=kw.get("categories", ["plumbing"]),
        home_cell=kw.get("cell", "springfield-test"),
        now=NOW,
    )


def _publish(store, **kw):
    gig = post.draft_gig(
        title=kw.get("title", "Fix leaky faucet"),
        category=kw.get("category", "plumbing"),
        description=kw.get("description", "drips all night"),
        requester=kw.get("requester", "Ann H"),
        requester_contact=kw.get("contact", "ann@example.com"),
        neighborhood_cell=kw.get("cell", "springfield-test"),
        estimate=kw.get("estimate", 120.0),
    )
    return post.publish_gig(store, gig, confirm=True, now=NOW)


# -- waitlist -------------------------------------------------------------
def test_waitlist_full_flow(tmp_path):
    store = _store(tmp_path)
    e = waitlist.add_to_waitlist(
        store, "Carol C", "carol@example.com", "worker", "springfield-test", now=NOW
    )
    assert e["status"] == "waitlisted"
    with pytest.raises(ValueError):
        waitlist.add_to_waitlist(store, "X", "x", "emperor", "cell")
    m = waitlist.mint_invite(store, e["id"], operator="keeper", code="INVITE-1", now=NOW)
    assert m["status"] == "invited" and m["invite_code"] == "INVITE-1"
    with pytest.raises(ValueError):
        # duplicate code refused (law L1)
        e2 = waitlist.add_to_waitlist(
            store, "Dan D", "dan@example.com", "worker", "springfield-test", now=NOW
        )
        waitlist.mint_invite(store, e2["id"], operator="keeper", code="INVITE-1")
    with pytest.raises(ValueError):
        waitlist.mint_invite(store, e["id"], operator="")
    r = waitlist.redeem_invite(store, "INVITE-1", now=NOW)
    assert r["status"] == "onboarded"
    with pytest.raises(ValueError):
        waitlist.redeem_invite(store, "INVITE-1")  # already redeemed — refused
    with pytest.raises(KeyError):
        waitlist.redeem_invite(store, "NOPE")
    depth = waitlist.waitlist_depth(store, "springfield-test")
    assert depth["total"] == 1 and depth["by_role"]["worker"] == 1
    assert waitlist.check_laws(store)["ok"]


def test_waitlist_decline_recorded_not_deleted(tmp_path):
    store = _store(tmp_path)
    e = waitlist.add_to_waitlist(store, "Eve", "e@x.com", "customer", "cell-a", now=NOW)
    waitlist.decline(store, e["id"], now=NOW)
    recs = [r for r in store.read_all("waitlist") if r["id"] == e["id"]]
    assert len(recs) == 2 and recs[-1]["status"] == "declined"


# -- admin gates ------------------------------------------------------------
def test_admin_default_stage_waitlist_only(tmp_path):
    store = _store(tmp_path)
    assert admin.stage(store) == "waitlist_only"
    cl = admin.stage_checklist(store, "recruiting")
    assert cl["total"] == 2 and not cl["complete"]


def test_admin_advance_blocked_by_checklist(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(PermissionError):
        admin.advance_stage(store, operator="keeper")
    with pytest.raises(ValueError):
        admin.advance_stage(store, operator="keeper", confirm=True, now=NOW)
    _complete_checklist(store, "recruiting")
    res = admin.advance_stage(store, operator="keeper", confirm=True, now=NOW)
    assert res["to"] == "recruiting"
    assert admin.stage(store) == "recruiting"
    hist = admin.stage_history(store)
    assert len(hist) == 1 and hist[0]["operator"] == "keeper"


def test_admin_override_is_logged(tmp_path):
    store = _store(tmp_path)
    admin.override_stage(
        store, "soft_launch", operator="keeper", reason="founder call",
        confirm=True, now=NOW,
    )
    assert admin.stage(store) == "soft_launch"
    hist = admin.stage_history(store)
    assert any("OVERRIDE" in h["note"] for h in hist)
    with pytest.raises(ValueError):
        admin.override_stage(store, "moon", operator="keeper", reason="x", confirm=True)
    with pytest.raises(ValueError):
        admin.override_stage(store, "recruiting", operator="", reason="x", confirm=True)
    assert admin.check_laws(store)["ok"]


def test_launch_readiness_scores(tmp_path):
    store = _store(tmp_path)
    r = admin.launch_readiness(store, "springfield-test")
    assert r["score"] == 0.0  # nothing yet — honest zero
    waitlist.add_to_waitlist(store, "W1", "w1@x", "worker", "springfield-test", now=NOW)
    _worker(store)
    r = admin.launch_readiness(store, "springfield-test")
    assert 0 < r["score"] < 100
    assert set(r["components"]) == {"waitlist_depth", "worker_supply", "gate_checklist"}


def test_nudges_pull_only(tmp_path):
    store = _store(tmp_path)
    admin.queue_nudge(store, "recruiting", "go recruit", cell="springfield-test", now=NOW)
    pulled = admin.pull_nudges(store, now=NOW)
    assert len(pulled) == 1
    assert admin.pull_nudges(store) == []  # pulled once, marked read


# -- twins ------------------------------------------------------------------
def test_twins_health_reminders_roi(tmp_path):
    store = _store(tmp_path)
    twins.register_property(
        store, "prop-1", "123 Main St", "Ann H", "springfield-test", now=NOW
    )
    with pytest.raises(ValueError):
        twins.register_property(store, "prop-1", "x", "y", "cell", now=NOW)
    twins.set_system(store, "prop-1", "water_heater", 40, install_year=2014, now=NOW)
    twins.set_system(store, "prop-1", "roof", 85, install_year=2020, now=NOW)
    with pytest.raises(ValueError):
        twins.set_system(store, "prop-1", "hvac", 101)
    twins.log_maintenance(store, "prop-1", "water_heater", "flushed tank", cost=120.0, now=NOW)

    t = twins.load_twin(store, "prop-1")
    h = twins.health_score(t)
    assert h["score"] == 62.5 and h["flagged"] == ["water_heater"]

    rems = twins.reminders(store, "prop-1", current_year=2026)
    levels = {r["system"]: r["level"] for r in rems}
    assert levels["water_heater"] == "overdue"  # 12y vs 11y lifespan
    assert levels.get("roof") in ("plan", None)  # 6y vs 25y — no reminder yet
    assert all("installed" in r["message"] for r in rems)  # law L3: cites sources

    roi = twins.roi_suggestions(store, "prop-1")
    assert roi and roi[0]["arithmetic"].startswith("$")
    assert all(s["payback_years"] > 0 for s in roi)

    res = twins.export_twin(store, "prop-1")
    assert res["path"].endswith(".export.json")
    assert twins.check_laws(store)["ok"]


def test_twins_health_deterministic(tmp_path):
    store = _store(tmp_path)
    twins.register_property(store, "p", "a", "o", "cell", now=NOW)
    twins.set_system(store, "p", "hvac", 70, install_year=2018, now=NOW)
    t = twins.load_twin(store, "p")
    assert twins.health_score(t) == twins.health_score(t)


# -- supply -------------------------------------------------------------------
def test_supply_referral_flow(tmp_path):
    store = _store(tmp_path)
    s = supply.register_supplier(
        store, "Springfield Supply", "555-0100", ["plumbing"], "springfield-test", now=NOW
    )
    gig = _publish(store)
    r = supply.refer(
        store, s["id"], ["water heater 40gal"], gig_id=gig["id"],
        quoted_amount=850.0, referred_by="keeper", now=NOW,
    )
    assert r["outcome"] == "open" and r["quoted_amount"] == 850.0
    with pytest.raises(ValueError):
        supply.refer(store, s["id"], ["x"])  # untraceable — refused (law L2)
    supply.close_referral(store, r["id"], "fulfilled", rating=5, now=NOW)
    rating = supply.supplier_rating(store, s["id"])
    assert rating == {"supplier_id": s["id"], "ratings_count": 1, "average": 5.0}
    with pytest.raises(ValueError):
        supply.close_referral(store, r["id"], "maybe")
    assert supply.check_laws(store)["ok"]


# -- academy --------------------------------------------------------------------
def test_academy_completion_becomes_claim(tmp_path):
    store = _store(tmp_path)
    w = _worker(store)
    c = academy.create_course(
        store, "Water Heaters 101", "plumbing",
        ["anatomy", "safety", "install"], "Prof. P", now=NOW,
    )
    with pytest.raises(ValueError):
        academy.complete(store, c["id"], w["id"], passed=True)  # no enrollment (law L2)
    academy.enroll(store, c["id"], w["id"], now=NOW)
    with pytest.raises(KeyError):
        academy.enroll(store, c["id"], "worker-9999")
    res = academy.complete(store, c["id"], w["id"], passed=True, now=NOW)
    assert res["status"] == "passed"
    worker = work.latest_worker(store, w["id"])
    claims = [x for x in worker["credentials"] if x["type"] == "academy_completion"]
    assert len(claims) == 1
    assert claims[0]["issuer"] == c["id"] and claims[0]["verified_by_us"] is False
    assert claims[0]["asserted_by"]  # provenance (law L1)
    # failed completion → no credential
    c2 = academy.create_course(store, "X", "plumbing", ["a"], "P", now=NOW)
    academy.enroll(store, c2["id"], w["id"], now=NOW)
    academy.complete(store, c2["id"], w["id"], passed=False, now=NOW)
    worker = work.latest_worker(store, w["id"])
    assert len([x for x in worker["credentials"] if x["type"] == "academy_completion"]) == 1
    assert len(academy.course_roster(store, c["id"])) == 1
    assert academy.check_laws(store)["ok"]


# -- crews ----------------------------------------------------------------------
def test_crew_flow(tmp_path):
    store = _store(tmp_path)
    _set_stage(store, "soft_launch")
    lead = _worker(store, name="Lead L")
    m1 = _worker(store, name="Mem M")
    crew = work.create_crew(store, "Crew A", lead["id"], [m1["id"]], now=NOW)
    assert crew["members"] == [lead["id"], m1["id"]]
    with pytest.raises(KeyError):
        work.create_crew(store, "Crew B", lead["id"], ["worker-9999"])
    m2 = _worker(store, name="Mem N")
    crew = work.add_crew_member(store, crew["id"], m2["id"], now=NOW)
    assert len(crew["members"]) == 3
    # history is append-only: two snapshots
    assert len([c for c in store.read_all("crews") if c["id"] == crew["id"]]) == 2

    gig = _publish(store)
    with pytest.raises(PermissionError):
        work.crew_claim(store, gig["id"], crew["id"])
    claimed = work.crew_claim(store, gig["id"], crew["id"], confirm=True, now=NOW)
    assert claimed["status"] == "accepted"
    assert claimed["crew_id"] == crew["id"]
    assert claimed["worker_id"] == lead["id"]


def test_crew_claim_gate_refused(tmp_path):
    store = _store(tmp_path)  # waitlist_only default — dispatch refused
    lead = _worker(store)
    crew = work.create_crew(store, "Crew", lead["id"], [], now=NOW)
    gig = _publish(store)
    with pytest.raises(PermissionError):
        work.crew_claim(store, gig["id"], crew["id"], confirm=True)


# -- tiers / revenue --------------------------------------------------------------
def test_tiers_and_revenue(tmp_path):
    store = _store(tmp_path)
    policies = _policies(store)
    ts = monetize.tiers(policies)
    assert {t["id"] for t in ts} >= {
        "free_worker", "pro_worker", "home_plus", "business", "property_manager"
    }
    with pytest.raises(KeyError):
        monetize.tier_by_id(policies, "nope")
    s = monetize.subscribe(store, "pro_worker", "Bob W", operator="keeper", now=NOW)
    assert s["monthly_price"] == 29.0 and s["status"] == "active"
    r = monetize.revenue_report(store)
    assert r["streams"]["subscriptions"] == 29.0
    assert r["concentrations"]["subscriptions"] == 1.0
    assert r["flags"] == ["subscriptions"]  # 100% concentration — flagged
    monetize.cancel_subscription(store, s["id"], now=NOW)
    r = monetize.revenue_report(store)
    assert r["streams"]["subscriptions"] == 0.0


def test_revenue_includes_platform_fees(tmp_path):
    store = _store(tmp_path)
    _set_stage(store, "soft_launch")
    gig = _publish(store, estimate=120.0)
    worker = _worker(store)
    lift.offer(store, gig["id"], worker["id"], operator="keeper", confirm=True, now=NOW)
    lift.accept_offer(store, gig["id"], worker["id"], now=NOW)
    work.check_in(store, gig["id"], worker["id"], now=NOW)
    work.check_out(store, gig["id"], worker["id"], now=NOW)
    work.sign_off(store, gig["id"], "Ann H", 5, final_amount=120.0, now=NOW)
    entry = pay.settle(
        store, gig["id"], 120.0, rail="cash", rail_reference="handoff-1",
        confirm=True, now=NOW,
    )
    assert entry["verified"]
    r = monetize.revenue_report(store)
    assert r["streams"]["platform_fees"] == entry["fee"]
    assert r["total"] == r["streams"]["platform_fees"]


# -- rails --------------------------------------------------------------------------
def test_rail_registry_and_settle_validation(tmp_path):
    store = _store(tmp_path)
    known = {r["name"] for r in rails.declared_rails(store)}
    assert {"cash", "bank-transfer", "stripe"} <= known
    rails.declare_rail(
        store, "venmo", "Venmo (external plug-in)",
        "Operator's Venmo rail; reference is the payment note id.",
        operator="keeper", now=NOW,
    )
    assert "venmo" in {r["name"] for r in rails.declared_rails(store)}
    with pytest.raises(ValueError):
        rails.declare_rail(store, "venmo", "dup", "x", operator="keeper")
    with pytest.raises(ValueError):
        rails.declare_rail(
            store, "bad", "Bad", "uses secret api key abc123", operator="keeper"
        )  # law L1: no secrets
    with pytest.raises(ValueError):
        rails.assert_rail(store, "unregistered-rail")
    assert rails.check_laws(store)["ok"]


def test_settle_refuses_unregistered_rail(tmp_path):
    store = _store(tmp_path)
    _set_stage(store, "soft_launch")
    gig = _publish(store)
    worker = _worker(store)
    lift.offer(store, gig["id"], worker["id"], operator="keeper", confirm=True, now=NOW)
    lift.accept_offer(store, gig["id"], worker["id"], now=NOW)
    work.check_in(store, gig["id"], worker["id"], now=NOW)
    work.check_out(store, gig["id"], worker["id"], now=NOW)
    work.sign_off(store, gig["id"], "Ann H", 5, final_amount=100.0, now=NOW)
    with pytest.raises(pay.SettlementRefused):
        pay.settle(
            store, gig["id"], 100.0, rail="teleport-money", rail_reference="x",
            confirm=True, now=NOW,
        )


# -- liquidity -------------------------------------------------------------------------
def test_liquidity_report_and_nudges(tmp_path):
    store = _store(tmp_path)
    _publish(store, category="plumbing")
    _publish(store, category="plumbing")
    _worker(store, categories=["plumbing"])
    rep = liquidity.liquidity_report(store, "springfield-test")
    plumbing = next(r for r in rep["categories"] if r["category"] == "plumbing")
    assert plumbing["open_jobs"] == 2 and plumbing["active_workers"] == 1
    assert plumbing["state"] == "hot"  # 2.0/worker >= hot_above 2.0
    assert plumbing["thin_data"] is False
    assert liquidity.priority_dispatch(store, "springfield-test") == ["plumbing"]
    assert liquidity.queue_recruiting_nudges(store, "springfield-test", "keeper") == []
    # make it cold: many workers, no jobs in another category
    _worker(store, name="E", categories=["electrical"])
    _worker(store, name="F", categories=["electrical"])
    _worker(store, name="G", categories=["electrical"])
    rep = liquidity.liquidity_report(store, "springfield-test")
    elec = next(r for r in rep["categories"] if r["category"] == "electrical")
    assert elec["state"] == "cold"
    nudges = liquidity.queue_recruiting_nudges(store, "springfield-test", "keeper", now=NOW)
    assert len(nudges) == 1 and nudges[0]["kind"] == "recruiting"
    pulled = admin.pull_nudges(store, now=NOW)
    assert len(pulled) == 1
    assert liquidity.check_laws(store)["ok"]


# -- PWA -------------------------------------------------------------------------------
def test_pwa_export(tmp_path):
    store = _store(tmp_path)
    _publish(store)
    _worker(store)
    res = pwa.export_pwa(store)
    import pathlib

    d = pathlib.Path(res["dir"])
    for f in ("index.html", "manifest.json", "sw.js", "snapshot.json"):
        assert (d / f).exists(), f
    html = (d / "index.html").read_text()
    assert "http://" not in html and "https://" not in html  # law L1: fully static
    assert "NeighborOS" in html  # branding from operator config
    snap = json.loads((d / "snapshot.json").read_text())
    assert all("seq" not in g for g in snap["gigs"])  # readable state (law L2)
    assert snap["gigs"] and snap["workers"]
    assert pwa.check_laws(store)["ok"]


def test_pwa_white_label_branding(tmp_path):
    store = _store(tmp_path)
    path = store.base / "policies.json"
    store.ensure_policies()
    cfg = json.loads(path.read_text())
    cfg["branding"] = {"app_name": "LoganFix", "tagline": "logan's crew"}
    path.write_text(json.dumps(cfg))
    res = pwa.export_pwa(store)
    import pathlib

    html = (pathlib.Path(res["dir"]) / "index.html").read_text()
    assert "LoganFix" in html


# -- CLI smoke ---------------------------------------------------------------------------
def test_cli_pwa_and_rails_smoke(tmp_path, capsys):
    from levi.neighbor import cli

    d = str(tmp_path / "neighbor")
    assert cli.main(["--dir", d, "pwa"]) == 0
    out = capsys.readouterr().out
    assert "PWA shell exported" in out
    assert cli.main(["--dir", d, "rails", "list"]) == 0
    assert "cash" in capsys.readouterr().out
    assert cli.main(["--dir", d, "waitlist", "depth", "--cell", "x"]) == 0
