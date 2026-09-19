"""Tests for Site Lift tailored teams: packs, matching, offer assembly."""

import os
from types import SimpleNamespace

import pytest

from levi.services.site_lift import (
    LiftError,
    load_report,
    run_lift_program,
    save_report,
)
from levi.services.site_teams import (
    KNOWN_CHECK_IDS,
    PACK_ORDER,
    TEAM_PACKS,
    TeamError,
    get_pack,
    list_packs,
    validate_packs,
)
from levi.services.site_team_match import (
    TeamOffer,
    assemble_offer,
    failed_findings,
    load_offer,
    match_report,
    quote_pack,
    recommend_pack,
    report_hash,
    save_offer,
)

# A site missing almost everything the crew cares about: no contact
# path, no CTA, no booking, no pricing, no FAQ, no proof. (One page, so
# f-pages fails too — and c-goal-* will fail in the crown.)
BARE_PAGE = "<html><head></head><body><p>open soon</p><img src='x.jpg'></body></html>"


_SITE_SEQ = 0


def _report(tmp_path):
    global _SITE_SEQ
    _SITE_SEQ += 1
    d = tmp_path / f"site{_SITE_SEQ}"
    d.mkdir()
    (d / "index.html").write_text(BARE_PAGE)
    return run_lift_program(d, provider="levi", report_id=f"test_team_report_{_SITE_SEQ}")


# --- pack loading / validation -------------------------------------------


def test_five_packs_in_deterministic_order():
    packs = list_packs()
    assert [p["id"] for p in packs] == list(PACK_ORDER)
    assert set(TEAM_PACKS) == set(PACK_ORDER)


def test_pack_roles_have_shape_and_checklists():
    for pack in list_packs():
        for role in pack["roles"]:
            assert role["checklist"], f"{pack['id']}/{role['id']}: empty checklist"
            assert role["escalation"].strip(), f"{pack['id']}/{role['id']}: empty escalation"
            assert role["purpose"].strip(), f"{pack['id']}/{role['id']}: empty purpose"
            assert set(role["covers"]) <= set(KNOWN_CHECK_IDS)


def test_get_pack_unknown_raises():
    with pytest.raises(TeamError):
        get_pack("nightclub")


def test_validate_packs_rejects_bad_covers():
    bad = dict(TEAM_PACKS)
    bad_pack = dict(TEAM_PACKS["generic"])
    bad_role = dict(TEAM_PACKS["generic"]["roles"][0])
    bad_role["covers"] = ["t-booking", "f-nope-not-real"]
    bad_pack["roles"] = [bad_role] + bad_pack["roles"][1:]
    bad = dict(TEAM_PACKS, generic=bad_pack)
    with pytest.raises(TeamError):
        validate_packs(bad)


def test_no_business_names_hardcoded():
    blob = " ".join(p["title"] for p in list_packs())
    for name in ("Easy Touch", "Massage", "Springfield", "Jontae"):
        assert name not in blob


# --- matching -------------------------------------------------------------


def test_failed_findings_are_measured_and_deduped(tmp_path):
    findings = failed_findings(_report(tmp_path))
    ids = [f.check_id for f in findings]
    # no c-reg: duplicates — each base id appears once
    assert len(ids) == len(set(ids))
    assert "f-cta" in ids and "t-booking" in ids
    # attested checks never become crew findings
    assert not any(i.startswith(("s-", "c-showcase")) for i in ids)


def test_recommend_pack_deterministic_tie_break(tmp_path):
    # every pack covers the same six gaps on the bare site -> most
    # specific pack (restaurant) wins the tie by PACK_ORDER
    assert recommend_pack(_report(tmp_path)) == "restaurant"
    assert recommend_pack(_report(tmp_path)) == recommend_pack(_report(tmp_path))


def test_match_assigns_roles_and_unmatched(tmp_path):
    m = match_report(_report(tmp_path))
    assert m.pack_id == "restaurant"
    by_role = {rc.role_id: [f.check_id for f in rc.findings] for rc in m.coverage}
    assert "t-booking" in by_role["booker"]
    assert "t-faq" in by_role["faq-answerer"] and "t-pricing" in by_role["faq-answerer"]
    assert "t-proof" in by_role["review-responder"]
    # honest gap: site-build checks have no crew
    unmatched_ids = [f.check_id for f in m.unmatched]
    assert "f-meta-desc" in unmatched_ids
    assert "t-gallery" in unmatched_ids
    # NOTHING silently dropped: every failed finding is either covered
    # or unmatched
    covered = {f.check_id for rc in m.coverage for f in rc.findings}
    all_failed = {f.check_id for f in failed_findings(_report(tmp_path))}
    assert covered | set(unmatched_ids) == all_failed


def test_match_explicit_pack_override(tmp_path):
    m = match_report(_report(tmp_path), pack_id="shop")
    assert m.pack_id == "shop"
    by_role = {rc.role_id: rc for rc in m.coverage}
    assert "t-booking" in [f.check_id for f in by_role["order-tracker"].findings]


def test_match_unknown_pack_raises(tmp_path):
    with pytest.raises(TeamError):
        match_report(_report(tmp_path), pack_id="nightclub")


# --- offer assembly -------------------------------------------------------


def test_assemble_offer_deterministic(tmp_path):
    report = _report(tmp_path)
    m = match_report(report)
    o1 = assemble_offer(report, m)
    o2 = assemble_offer(report, m)
    assert o1.offer_id == o2.offer_id
    assert o1.offer_id.startswith("team_restaurant_")
    assert o1.report_hash == report_hash(report)
    assert o2.report_hash == o1.report_hash
    # per-role install checklist + escalation ride along
    for role in o1.roles:
        assert role["install_checklist"]
        assert role["escalation"].strip()
    # unmatched findings ride along with the honest note
    assert any("no crew covers this" in u["note"] for u in o1.unmatched)
    # paper quote present and labeled
    assert o1.quote is not None
    assert o1.quote["recommended_usd"] > 0
    assert "not a charge" in o1.quote["note"]


def test_assemble_offer_no_quote(tmp_path):
    report = _report(tmp_path)
    o = assemble_offer(report, match_report(report), quote=False)
    assert o.quote is None


def test_quote_pack_deterministic_and_paper(tmp_path):
    q1 = quote_pack("salon", giant_price=199.0)
    q2 = quote_pack("salon", giant_price=199.0)
    assert q1 == q2
    assert q1["recommended_usd"] <= 199.0  # never at or above the giant
    assert "not a charge" in q1["note"]
    with pytest.raises(TeamError):
        quote_pack("salon", strategy="moon")


def test_save_load_offer_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    report = _report(tmp_path)
    offer = assemble_offer(report, match_report(report))
    p = save_offer(offer)
    assert p.exists()
    back = load_offer(offer.offer_id)
    assert back is not None
    assert back.offer_id == offer.offer_id
    assert back.report_hash == offer.report_hash
    assert load_offer("nope_missing") is None


# --- CLI wiring -----------------------------------------------------------


def test_cli_teams_subcommand(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    report = _report(tmp_path)
    save_report(report, home=tmp_path / "home")
    # the saved report must be loadable from the CLI's default home
    from levi.services import cli as svc_cli

    args = SimpleNamespace(
        service_cmd="teams",
        report_id=report.report_id,
        pack=None,
        no_quote=False,
        giant_price=None,
        strategy="volume",
    )
    svc_cli.cmd_service(args)
    out = capsys.readouterr().out
    assert "team pack:" in out
    assert "restaurant" in out
    assert "offer: team_restaurant_" in out
    assert "no crew covers these" in out


def test_cli_teams_unknown_report(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    from levi.services import cli as svc_cli

    args = SimpleNamespace(
        service_cmd="teams",
        report_id="ghost_report",
        pack=None,
        no_quote=False,
        giant_price=None,
        strategy="volume",
    )
    svc_cli.cmd_service(args)
    assert "Unknown lift report" in capsys.readouterr().out
