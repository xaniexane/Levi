"""Hermetic, fast tests for the Legion bot product package.

All filesystem state goes through tmp dirs (LEVI_HOME, LEVI_CYBRUS_DIR);
no network, no real money, no rails touched.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from levi.legion import product, team, packs, sitelift_link, sale  # noqa: E402


@pytest.fixture(autouse=True)
def _hermetic(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("LEVI_CYBRUS_DIR", str(tmp_path / "cybrus"))


# ---------------------------------------------------------------------------
# product.py — white-label validation + one-face router
# ---------------------------------------------------------------------------


def test_whitelabel_rejects_blank_business_name():
    with pytest.raises(product.LegionError):
        product.configure("   ")


def test_whitelabel_rejects_bad_tone():
    with pytest.raises(product.LegionError):
        product.configure("Bella's", tone="sassy")


def test_whitelabel_rejects_bad_business_type():
    with pytest.raises(product.LegionError):
        product.configure("Bella's", business_type="spaceship")


def test_whitelabel_rejects_bad_brand_color():
    with pytest.raises(product.LegionError):
        product.configure("Bella's", brand_colors={"primary": "red"})


def test_whitelabel_rejects_long_greeting():
    with pytest.raises(product.LegionError):
        product.configure("Bella's", greeting="x" * 281)


def test_whitelabel_no_mask_on_face_copy():
    wl = product.configure(
        "Bella's", tone="warm", business_type="salon",
        brand_colors={"primary": "#A14B2A"},
    )
    assert wl.face_name == "Bella's assistant"
    assert "Legion bot" in wl.identity_statement
    assert wl.to_dict()["business_name"] == "Bella's"
    assert product.WhiteLabel.from_dict(wl.to_dict()).face_name == wl.face_name


def test_router_routes_to_crew_roles():
    router = product.build_router("Bella's assistant", ["booker", "cashier"])
    hit = router.route("I want to book an appointment Thursday")
    assert hit is not None and hit.role == "booker"
    hit2 = router.route("how much does the menu cost")
    assert hit2 is not None and hit2.role == "cashier"
    assert router.route("purple elephants") is None
    assert "Bella's assistant" in router.fallback_response


def test_router_rejects_duplicate_intents_and_empty_crew():
    with pytest.raises(product.LegionError):
        product.RouterConfig(
            face_name="x",
            routes=[
                product.FaceRoute("a", ["a"], "r1"),
                product.FaceRoute("a", ["b"], "r2"),
            ],
        )
    with pytest.raises(product.LegionError):
        product.build_router("x", [])


def test_router_roundtrip():
    router = product.build_router("X", ["booker"])
    assert product.RouterConfig.from_dict(router.to_dict()).face_name == "X"


# ---------------------------------------------------------------------------
# team.py — deterministic assembly
# ---------------------------------------------------------------------------


def test_assemble_team_deterministic_and_named():
    prof = team.BusinessProfile(
        business_type="restaurant", size="small",
        needs=["booking", "contact", "pricing", "reviews"],
        business_name="Bella's Bistro",
    )
    t1 = team.assemble_team(prof)
    t2 = team.assemble_team(prof)
    assert t1.to_dict() == t2.to_dict()
    roles = [m.role for m in t1.crew]
    assert set(roles) == {"booker", "receptionist", "cashier", "marketer"}
    assert t1.face_role == "receptionist"
    assert all(m.seat_key for m in t1.crew)
    assert len(t1.handoff_rules) >= 3
    # same-category needs share one role: covered once, deterministically
    prof2 = team.BusinessProfile(
        business_type="generic", size="small", needs=["contact", "reception"],
    )
    crew2 = team.assemble_team(prof2).crew
    assert [m.role for m in crew2] == ["receptionist"]
    assert team.assemble_team(prof2).to_dict() == team.assemble_team(prof2).to_dict()


def test_profile_rejects_unknown_need():
    with pytest.raises(team.LegionError):
        team.BusinessProfile(business_type="generic", needs=["teleportation"])


def test_default_needs_apply():
    prof = team.BusinessProfile(business_type="salon")
    t = team.assemble_team(prof)
    assert t.needs_covered == ["booking", "pricing", "gallery", "contact"]


def test_operator_registry_seam_resolves():
    r = team.resolve_operator_seat("agent.default")
    assert r["resolved"] is True
    assert r["operator"] == "local"  # registry default
    r2 = team.resolve_operator_seat("agent.default", {"operator": "levi-brain"})
    assert r2["operator"] == "levi-brain"  # config override swaps the operator
    assert team.OPERATOR_REGISTRY_PENDING is False


def test_operator_registry_never_breaks_assembly():
    r = team.resolve_operator_seat("agent.default", {"seats": "not-a-dict"})
    assert isinstance(r, dict) and "resolved" in r


# ---------------------------------------------------------------------------
# packs.py — data-driven specialist packs
# ---------------------------------------------------------------------------


def test_packs_load_and_have_shape():
    for name in packs.pack_names():
        p = packs.get_pack(name)
        for key in ("vocabulary", "extra_needs", "faqs", "tasks", "escalations"):
            assert isinstance(p[key], list) and p[key], f"{name}.{key}"
        assert all(n in team.NEED_TO_CATEGORY for n in p["extra_needs"])
        # no hardcoded business names — packs are patterns
        blob = json.dumps(p).lower()
        assert "bella" not in blob and "example inc" not in blob


def test_unknown_pack_refused():
    with pytest.raises(packs.LegionError):
        packs.get_pack("spaceship")


def test_pack_merge_into_profile():
    profile = {"business_type": "restaurant", "needs": ["booking"]}
    merged = packs.merge_pack_into_profile(profile, "restaurant")
    assert profile["needs"] == ["booking"]  # untouched
    assert "pricing" in merged["needs"] and "reviews" in merged["needs"]
    assert merged["needs"].count("booking") == 1


# ---------------------------------------------------------------------------
# sitelift_link.py — report -> proposed crew
# ---------------------------------------------------------------------------


def test_fixture_and_failed_checks():
    fx = sitelift_link.fixture_report(
        failed=["t-booking", "f-contact", "t-pricing"],
    )
    fails = sitelift_link.failed_checks(fx)
    assert {f["check_id"] for f in fails} == {"t-booking", "f-contact", "t-pricing"}
    with pytest.raises(sitelift_link.LegionError):
        sitelift_link.fixture_report(failed=["nope"])


def test_propose_team_from_report():
    fx = sitelift_link.fixture_report(
        site="sample-restaurant-site",
        failed=["t-booking", "f-contact", "t-pricing", "t-proof"],
    )
    proposal = sitelift_link.propose_team(fx, business_name="Sample Bistro")
    assert proposal["failed_checks"] == 4
    assert proposal["unmapped"] == []
    assert proposal["business_type"] == "restaurant"
    assert proposal["business_type_source"] == "detected-hint"
    assert proposal["suggested_pack"] == "restaurant"
    roles = {m["role"] for m in proposal["team"]["crew"]}
    assert {"booker", "receptionist", "cashier", "marketer"} <= roles


def test_propose_team_accepts_liftreport_object_and_json():
    from levi.services.site_lift import LiftReport
    fx = sitelift_link.fixture_report(failed=["t-faq"])
    rep = LiftReport.from_dict(fx)
    p1 = sitelift_link.propose_team(rep)
    p2 = sitelift_link.propose_team(json.dumps(fx))
    assert p1["report_id"] == p2["report_id"] == "lift_fixture_1"
    assert any(g["need"] == "faq" for g in p1["gaps"])


def test_propose_team_rejects_bad_report():
    with pytest.raises(sitelift_link.LegionError):
        sitelift_link.propose_team({"not": "a report"})
    with pytest.raises(sitelift_link.LegionError):
        sitelift_link.propose_team("not json")


# ---------------------------------------------------------------------------
# sale.py — paper money seam
# ---------------------------------------------------------------------------


def test_quote_math():
    q = sale.quote_legion(business_type="restaurant", packs=["restaurant"])
    assert q.packs == ["restaurant"]
    assert q.base_lifetime == round(q.base_monthly * sale.LIFETIME_MONTHS, 2)
    addon = q.pack_addons["restaurant"]
    assert addon == round(q.base_lifetime * sale.PACK_ADDON_FRACTION, 2)
    assert q.total_usd == round(q.base_lifetime + addon, 2)
    assert q.total_usd > 0
    assert q.seat_cap == 490  # flagship tier: the legion crew is the product
    assert any("QUOTE" in line for line in q.rationale)
    assert sale.LegionQuote.from_dict(q.to_dict()).quote_id == q.quote_id


def test_quote_with_giant_anchor_sits_below_giant():
    q = sale.quote_legion(giant_price=100.0)
    assert q.base_monthly < 100.0  # ~30-60% below, never at or above


def test_checkout_is_plan_and_preview_only():
    q = sale.quote_legion()
    rec = sale.plan_checkout(q, buyer="Sample Buyer")
    assert rec.status == "paper-quote"
    assert rec.amount_minor == int(round(q.total_usd * 100))
    assert "paper" in rec.preview
    assert "does NOT execute" in rec.preview
    # audit trail written, no authorization, no execution attempted
    cybrus_dir = Path(os.environ["LEVI_CYBRUS_DIR"]) / "money"
    audit = (cybrus_dir / "money_audit.jsonl").read_text()
    assert "planned" in audit
    assert "executed" not in audit


def test_split_paper_math_and_label():
    s = sale.split_paper(100.0)
    assert s["kind"] == "paper-split"
    assert s["keeper_usd"] == 70.0 and s["pool_usd"] == 30.0
    assert "never recorded income" in s["law"]


def test_license_record_shape_and_unpaid_lock():
    q = sale.quote_legion(packs=["salon"])
    rec = sale.plan_checkout(q)
    lic = sale.issue_license(q, rec, business_name="Sample Salon")
    assert lic.status == "paper-unpaid"
    assert lic.buyer == ""  # blank until a real sale
    assert lic.terms == {"lifetime": True, "copies": 1, "transferable": False}
    assert lic.price_usd == q.total_usd
    assert lic.packs == ["salon"]
    # persisted and listed back
    found = sale.list_licenses()
    assert any(l.license_id == lic.license_id for l in found)
    # the seam cannot mark paid
    with pytest.raises(sale.SaleError):
        sale.LicenseRecord(
            license_id="x", product="Legion bot", business_name="x",
            buyer="", price_usd=1.0, packs=[], terms={},
            quote_id="x", checkout_record_id="x", status="paid",
        )
    # checkout/quote mismatch refused
    q2 = sale.quote_legion()
    rec2 = sale.plan_checkout(q2)
    with pytest.raises(sale.SaleError):
        sale.issue_license(q2, sale.plan_checkout(sale.quote_legion()),
                           business_name="x")


def test_end_to_end_paper_flow():
    """The full product flow, all paper: configure -> team -> pack ->
    sitelift offer -> quote -> checkout -> license."""
    wl = product.configure("Sample Bistro", business_type="restaurant", tone="warm")
    prof = team.BusinessProfile(
        business_type=wl.business_type, size="small",
        needs=["booking", "contact", "pricing", "reviews"],
        business_name=wl.business_name,
    )
    crew = team.assemble_team(prof)
    router = product.build_router(wl.face_name, [m.role for m in crew.crew])
    assert router.route("book a table") is not None
    pack = packs.get_pack("restaurant")
    fx = sitelift_link.fixture_report(
        site="sample-bistro-site",
        failed=["t-booking", "f-contact"],
    )
    proposal = sitelift_link.propose_team(fx, business_name=wl.business_name)
    assert len(proposal["team"]["crew"]) >= 2
    q = sale.quote_legion(business_type="restaurant", packs=["restaurant"])
    checkout = sale.plan_checkout(q)
    split = sale.split_paper(q.total_usd)
    lic = sale.issue_license(q, checkout, business_name=wl.business_name)
    assert lic.status == "paper-unpaid"
    assert split["kind"] == "paper-split"
