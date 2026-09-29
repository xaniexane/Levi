"""Tests for levi.fairplay.audit — the sly-trade detector.

Law-guard-prove: the laws live in the module docstring; these tests are the
guard gate. Every pattern must be detected from a declared offer, every sly
finding must carry an honest alternative, and auditing must never mutate.
"""

import copy

from levi.fairplay.audit import (
    SEVERITY_CAUTION,
    SEVERITY_CLEAN,
    SEVERITY_SLY,
    audit_offer,
)


def honest_offer():
    return {
        "name": "Local Legends",
        "paid_random_draws": True,
        "odds_published": True,
        "pity_ceiling_declared": True,
        "worst_case_spend_declared": True,
        "progress_expiry": "never",
        "sale_is_license": False,
        "license_revocable": False,
        "eol_covenant": True,
        "paid_power": False,
        "server_only_inventory": False,
        "inventory_exportable": True,
        "marketing_language": ["published odds", "earn by playing"],
    }


def patterns(report):
    return {f.pattern: f for f in report.findings}


def test_honest_offer_verdict_honest():
    report = audit_offer(honest_offer())
    assert report.verdict() == "honest"
    assert report.sly_count() == 0
    assert report.caution_count() == 0


def test_opaque_odds_flagged_sly():
    offer = honest_offer()
    offer["odds_published"] = False
    report = audit_offer(offer)
    assert report.verdict() == "predatory"
    assert patterns(report)["opaque-odds"].severity == SEVERITY_SLY


def test_missing_odds_claim_flagged():
    # Absence of the claim is treated as "not claimed", honestly.
    offer = honest_offer()
    del offer["odds_published"]
    report = audit_offer(offer)
    assert "opaque-odds" in patterns(report)


def test_odds_without_worst_case_is_caution():
    offer = honest_offer()
    offer["worst_case_spend_declared"] = False
    report = audit_offer(offer)
    assert patterns(report)["no-worst-case"].severity == SEVERITY_CAUTION
    assert report.verdict() == "risky"


def test_time_fenced_grind_flagged_sly():
    offer = honest_offer()
    offer["progress_expiry"] = "season"
    report = audit_offer(offer)
    finding = patterns(report)["time-fenced-grind"]
    assert finding.severity == SEVERITY_SLY
    assert "ownedtrack" in finding.honest_alternative


def test_revocable_license_without_covenant_flagged_sly():
    offer = honest_offer()
    offer.update(sale_is_license=True, license_revocable=True, eol_covenant=False)
    report = audit_offer(offer)
    assert patterns(report)["revocable-license"].severity == SEVERITY_SLY


def test_revocable_license_with_covenant_is_caution():
    offer = honest_offer()
    offer.update(sale_is_license=True, license_revocable=True, eol_covenant=True)
    report = audit_offer(offer)
    assert patterns(report)["covenanted-license"].severity == SEVERITY_CAUTION


def test_pay_to_win_flagged_sly():
    offer = honest_offer()
    offer["paid_power"] = True
    report = audit_offer(offer)
    assert patterns(report)["pay-to-win"].severity == SEVERITY_SLY


def test_vanishing_inventory_flagged_sly():
    offer = honest_offer()
    offer.update(server_only_inventory=True, inventory_exportable=False)
    report = audit_offer(offer)
    finding = patterns(report)["vanishing-inventory"]
    assert finding.severity == SEVERITY_SLY
    assert "library" in finding.honest_alternative


def test_euphemism_language_flagged_caution():
    offer = honest_offer()
    offer["marketing_language"] = ["exciting surprise mechanics for engagement"]
    report = audit_offer(offer)
    finding = patterns(report)["euphemism"]
    assert finding.severity == SEVERITY_CAUTION
    assert "surprise mechanics" in finding.evidence


def test_every_sly_finding_carries_honest_alternative():
    offer = {
        "name": "Predator Royale",
        "paid_random_draws": True,
        "odds_published": False,
        "progress_expiry": "season",
        "sale_is_license": True,
        "license_revocable": True,
        "paid_power": True,
        "server_only_inventory": True,
        "marketing_language": ["surprise mechanics"],
    }
    report = audit_offer(offer)
    assert report.verdict() == "predatory"
    sly = [f for f in report.findings if f.severity == SEVERITY_SLY]
    assert len(sly) >= 4
    for finding in report.findings:
        assert finding.honest_alternative, finding.pattern


def test_audit_never_mutates_the_offer():
    offer = honest_offer()
    snapshot = copy.deepcopy(offer)
    audit_offer(offer)
    assert offer == snapshot


def test_empty_offer_gets_nothing_to_flag():
    report = audit_offer({})
    assert patterns(report)["nothing-to-flag"].severity == SEVERITY_CLEAN
    assert report.verdict() == "honest"


def test_summary_counts():
    offer = honest_offer()
    offer["paid_power"] = True
    offer["progress_expiry"] = "event"
    summary = audit_offer(offer).summary()
    assert summary["verdict"] == "predatory"
    assert summary["sly"] == 2
    assert summary["offer"] == "Local Legends"


def test_unknown_fields_ignored():
    offer = honest_offer()
    offer["blockchain_synergy"] = "moon"
    report = audit_offer(offer)
    assert report.verdict() == "honest"
