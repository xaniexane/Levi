"""Tests for core/levi/monetize — the 12 income modules + shared ledger."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from levi.monetize import ledger, projects
from levi.monetize.projects import (
    business_plans,
    chatbot_service,
    data_scraping,
    kdp_publishing,
    lead_generation,
    newsletter,
    podcast_notes,
    print_on_demand,
    resume_service,
    social_media,
    whatsapp_automation,
    youtube_faceless,
)

REQUIRED_KEYS = {
    "slug",
    "name",
    "automation",
    "setup_hours",
    "days_to_first_dollar",
    "daily_time_min",
    "month3_range",
    "risk_band",
    "mechanism",
    "chauncey_gated",
}


def test_registry_has_twelve_projects():
    projs = projects.list_projects()
    assert len(projs) == 12
    slugs = [p["slug"] for p in projs]
    assert len(set(slugs)) == 12


def test_every_project_has_required_keys_and_gates():
    for p in projects.list_projects():
        missing = REQUIRED_KEYS - set(p)
        assert not missing, f"{p.get('slug')}: missing {missing}"
        assert p["automation"] in ("full", "semi")
        assert p["risk_band"] in ledger.RISK_BANDS
        assert len(p["chauncey_gated"]) >= 2, f"{p['slug']}: needs Chauncey-gated steps"
        lo, hi = p["month3_range"]
        assert 0 <= lo <= hi


def test_every_module_exposes_checklist():
    for slug in projects.BY_SLUG:
        mod = projects.get_module(slug)
        steps = mod.setup_checklist()
        assert len(steps) >= 3
        assert any(s["gated"] for s in steps), f"{slug}: no gated step in checklist"


def test_ledger_roundtrip(tmp_path):
    home = tmp_path / "home"
    rec = ledger.log_event("resume-service", "sale", 30, note="test", home=home)
    assert rec["project"] == "resume-service"
    assert rec["amount"] == 30.0
    ledger.log_event("resume-service", "expense", 5, home=home)
    events = ledger.read_events(home=home)
    assert len(events) == 2
    assert events[0]["kind"] == "expense"  # newest first
    summary = ledger.summarize(home=home)
    assert summary["net"] == 25.0
    assert summary["by_project"]["resume-service"] == 30.0
    # permissions
    path = ledger.default_path(home)
    assert (path.stat().st_mode & 0o777) == 0o600


def test_ledger_rejects_bad_input(tmp_path):
    home = tmp_path / "home"
    with pytest.raises(ValueError):
        ledger.log_event("x", "bogus", 10, home=home)
    with pytest.raises(ValueError):
        ledger.log_event("x", "sale", -5, home=home)
    with pytest.raises(ValueError):
        ledger.log_event("x", "sale", 5, risk_band="extreme", home=home)
    assert ledger.read_events(home=tmp_path / "nope") == []


def test_resume_ats_gap():
    resume = "Python developer with 5 years building APIs and databases."
    posting = "Senior Python developer needed: Kubernetes, APIs, databases, leadership."
    out = resume_service.ats_keyword_gap(resume, posting)
    assert 0 <= out["coverage"] <= 1
    gap_words = {g["keyword"] for g in out["gaps"]}
    assert "kubernetes" in gap_words
    q = resume_service.quote("standard")
    assert q["price"] == 30
    order = resume_service.create_order("A. Client", "premium")
    assert order["status"] == "draft"
    with pytest.raises(ValueError):
        resume_service.quote("diamond")


def test_social_media_calendar_and_capacity():
    cal = social_media.content_calendar("barbershop", 3, weeks=2)
    assert len(cal) == 6
    kinds = {c["kind"] for c in cal}
    assert {"promotional", "educational", "community"} <= kinds
    cap = social_media.capacity_check(10)
    assert cap["over_capacity"] is True
    cap = social_media.capacity_check(2)
    assert cap["over_capacity"] is False
    assert social_media.quote("growth")["monthly"] == 175


def test_print_on_demand_margin():
    m = print_on_demand.margin("tshirt")
    assert m["unit_profit"] == round(24.99 - 13.45, 2)
    assert m["margin_pct"] > 0
    fc = print_on_demand.catalog_forecast([{"product": "mug", "units": 10}])
    assert fc["total_units"] == 10
    assert fc["total_profit"] > 0
    brief = print_on_demand.design_brief("local pride", "tote", "skyline text design")
    assert brief["status"].startswith("brief")


def test_kdp_royalty_and_catalog():
    r = kdp_publishing.royalty(4.99)
    assert r["rate_band"] == "70%"
    r2 = kdp_publishing.royalty(1.99)
    assert r2["rate_band"] == "35%"
    cat = kdp_publishing.catalog_earnings(
        [{"title": "A", "price": 4.99, "ebook": True, "monthly_sales": 20}]
    )
    assert cat["catalog_monthly"] == round(round(4.99 * 0.70, 2) * 20, 2)  # 69.8
    sk = kdp_publishing.outline_skeleton("T", "beginners", chapters=5)
    assert len(sk["chapters"]) == 7  # intro + 5 + conclusion


def test_youtube_estimates():
    est = youtube_faceless.earnings_estimate(100_000)
    assert est["estimated_monthly"] == (50.0, 400.0)
    chk = youtube_faceless.monetization_check(500, 4000)
    assert chk["eligible"] is False
    chk = youtube_faceless.monetization_check(1200, 5000)
    assert chk["eligible"] is True
    sc = youtube_faceless.script_outline("macrodroid tutorial")
    assert len(sc["beats"]) == 5


def test_chatbot_flow_and_quote():
    flow = chatbot_service.build_flow("salon", [{"q": "Hours?", "a": "9-6 daily."}])
    assert flow["lead_capture"].startswith("End every path")
    assert len(flow["branches"]) == len(chatbot_service.MENU_OPTIONS) + 1
    q = chatbot_service.quote(setup=100, retainer=35)
    assert q["first_year_total"] == 100 + 35 * 12
    book = chatbot_service.retainer_book(5, 35)
    assert book["monthly_recurring"] == 175
    with pytest.raises(ValueError):
        chatbot_service.build_flow("salon", [])


def test_lead_generation_guards_and_roi():
    lead = lead_generation.record_lead("roofing", "J. Doe", "555-0100", "roof quote")
    assert lead["status"] == "new" and lead["delivered"] is False
    inv = lead_generation.invoice(lead, 40)
    assert inv["amount"] == 40 and "unpaid" in inv["status"]
    roi = lead_generation.campaign_roi(10, 40, ad_spend=50)
    assert roi["net"] == 350.0 and roi["profitable"] is True
    roi = lead_generation.campaign_roi(1, 40, ad_spend=50)
    assert roi["profitable"] is False


def test_newsletter_tiers():
    t = newsletter.monetization_tier(300)
    assert t["unlocked"] == [] and t["next_milestone"] == 500
    t = newsletter.monetization_tier(3000)
    assert len(t["unlocked"]) == 3
    q = newsletter.sponsor_quote(6000, 2)
    assert q["per_issue_range"] == (400, 1000)
    tpl = newsletter.issue_template("gig income")
    assert len(tpl["structure"]) == 6


def test_data_scraping_guards():
    # forbidden fields are refused outright
    g = data_scraping.guard_fields(["price", "password"])
    assert g["allowed"] is False
    g = data_scraping.guard_fields(["price", "title"])
    assert g["allowed"] is True
    # preflight refuses when field guard fails, before any network
    pf = data_scraping.preflight("https://example.com", ["price", "ssn"])
    assert pf["accepted"] is False
    # invalid URL rejected
    with pytest.raises(ValueError):
        data_scraping.robots_allows("not-a-url")
    q = data_scraping.quote(200, "simple")
    assert q["range"] == (15, 50)
    csv_text = data_scraping.to_csv(
        [{"price": "9.99", "title": "x"}], ["price", "title"]
    )
    assert "price,title" in csv_text.splitlines()[0]


def test_whatsapp_margin():
    m = whatsapp_automation.resell_margin("managed_basic", 90)
    assert m["monthly_margin"] == 51.0
    assert m["yearly_margin"] == 612.0
    with pytest.raises(ValueError):
        whatsapp_automation.resell_margin("managed_basic", 10)  # below resell band
    seq = whatsapp_automation.flow_sequence("clinic")
    assert len(seq["steps"]) == 6
    q = whatsapp_automation.quote("custom_api")
    assert "setup_fee" in q


def test_podcast_timestamps_and_quote():
    assert podcast_notes.format_timestamp(3661) == "1:01:01"
    assert podcast_notes.format_timestamp(90) == "0:01:30"
    lines = podcast_notes.chapter_list([{"seconds": 0, "label": "Intro"}])
    assert lines == ["0:00:00 — Intro"]
    q = podcast_notes.quote("standard", episodes=4)
    assert q["total"] == 100
    order = podcast_notes.create_order("P. Host", "Ep 12", "premium")
    assert order["price"] == 40


def test_business_plan_projections():
    p = business_plans.projections_3yr(100000, [0.5, 0.3])
    assert p["year_1"] == 100000 and p["year_2"] == 150000 and p["year_3"] == 195000
    assert "warning" in p
    with pytest.raises(ValueError):
        business_plans.projections_3yr(100000, [0.5])
    sk = business_plans.plan_skeleton("Acme")
    assert len(sk["sections"]) == 10
    deck = business_plans.pitch_deck_outline("Acme")
    assert len(deck["slides"]) == 12
    q = business_plans.quote("standard")
    assert q["price"] == 150
    assert len(business_plans.intake_form()) == 9


def test_cli_list_and_show():
    env = {"PYTHONPATH": "core", "PATH": "/usr/bin:/bin"}
    for cmd in (["list"], ["show", "kdp-publishing"], ["checklist", "newsletter"]):
        r = subprocess.run(
            [sys.executable, "-m", "levi.monetize", *cmd],
            capture_output=True,
            text=True,
            env=env,
            cwd=Path.cwd(),
        )
        assert r.returncode == 0, r.stderr
    r = subprocess.run(
        [sys.executable, "-m", "levi.monetize", "show", "nope"],
        capture_output=True,
        text=True,
        env=env,
        cwd=Path.cwd(),
    )
    assert r.returncode == 2


def test_total_month3_range_sanity():
    tot = projects.total_month3_range()
    assert tot["month3_conservative"] > 0
    assert tot["month3_ceiling"] >= tot["month3_conservative"]
