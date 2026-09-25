"""Tests for levi.lwp.mirror_cascade — reverse-pattern cross-check (hermetic, pure)."""

import pytest

from levi.lwp.mirror_cascade import (
    MirrorCascade,
    reverse_crosscheck,
)


def test_report_shape():
    r = MirrorCascade().run("open a neighborhood shop")
    assert r.forward.name == "forward"
    assert r.reverse.name == "reverse"
    assert r.shadow.name == "shadow"
    assert len(r.synthesis) >= 4
    assert len(r.vetoes) >= 3
    assert r.fingerprint and len(r.fingerprint) == 12


def test_fingerprint_deterministic_and_seed_sensitive():
    a = MirrorCascade().run("same seed", "ctx")
    b = MirrorCascade().run("same seed", "ctx")
    c = MirrorCascade().run("other seed", "ctx")
    assert a.fingerprint == b.fingerprint
    assert a.fingerprint != c.fingerprint


def test_empty_seed_becomes_empty_label():
    r = MirrorCascade().run("")
    assert r.seed == "empty"


def test_rejects_non_str_seed_and_context():
    with pytest.raises(ValueError):
        MirrorCascade().run(123)
    with pytest.raises(ValueError):
        MirrorCascade().run("ok", context={"not": "str"})


def test_pressure_language_adds_veto():
    r = MirrorCascade().run("act now, only today, must buy this")
    assert any("Pressure language" in v for v in r.vetoes)


def test_absolute_claim_adds_veto():
    r = MirrorCascade().run("guaranteed results, risk free, no downside")
    assert any("Absolute-claim" in v for v in r.vetoes)


def test_quiet_seed_gets_no_language_vetoes():
    r = MirrorCascade().run("draft a plain checklist")
    assert not any("Pressure language" in v for v in r.vetoes)
    assert not any("Absolute-claim" in v for v in r.vetoes)


def test_local_operator_keyword_adds_synthesis_line():
    r = MirrorCascade().run("help the local clinic with booking")
    assert any("local operators" in s for s in r.synthesis)


def test_automation_keyword_adds_hitl_synthesis_line():
    r = MirrorCascade().run("build an ai bot for triage")
    assert any("HITL" in s for s in r.synthesis)


def test_context_retained_in_synthesis():
    r = MirrorCascade().run("seed", context="remember the june brief")
    assert any("june brief" in s for s in r.synthesis)


def test_format_renders_all_coils_and_sections():
    text = MirrorCascade().run("test seed").format()
    assert "FORWARD coil" in text
    assert "REVERSE coil" in text
    assert "SHADOW coil" in text
    assert "SYNTHESIS" in text
    assert "VETOES" in text
    assert "Fingerprint:" in text


def test_reverse_crosscheck_returns_formatted_str():
    text = reverse_crosscheck("test seed")
    assert isinstance(text, str)
    assert "Mirror Cascade" in text


# --- Documented-behavior: substring over-triggers (keyword-veto study 2026-09-22) ---
#
# Veto/synthesis matching is a raw substring test on the lowered seed
# (mirror_cascade.py: ``w in low``). Over-triggers are real and DOCUMENTED
# behavior, not bugs: the word lists are safety tripwires, conservative false
# positives are the design, and the lists grow only from production feedback
# with the triggering seed recorded. These tests LOCK that semantics — if
# matching ever moves to word-boundary or regex, these tests fail loudly and
# the change becomes a reviewed decision, not drift.


def test_overtrigger_ai_inside_said_adds_automation_line():
    # "said" contains "ai" — a seed with no automation intent still earns the
    # automation checklist line.
    r = MirrorCascade().run("what he said at the standup")
    assert any("Automation stays checklist-level" in s for s in r.synthesis)
    # ...but nothing else fires: serviceability line absent, no language vetoes.
    assert not any("local operators" in s for s in r.synthesis)
    assert len(r.vetoes) == 3


def test_overtrigger_bot_inside_bottom_adds_automation_line():
    # "bottom" contains "bot".
    r = MirrorCascade().run("the bottom line on costs")
    assert any("Automation stays checklist-level" in s for s in r.synthesis)
    assert not any("local operators" in s for s in r.synthesis)
    assert len(r.vetoes) == 3


def test_overtrigger_shop_inside_workshop_adds_serviceability_line():
    # "workshop" contains "shop".
    r = MirrorCascade().run("run a weekend workshop")
    assert any("Serviceability for local operators" in s for s in r.synthesis)
    assert not any("checklist-level" in s for s in r.synthesis)
    assert len(r.vetoes) == 3


def test_overtrigger_site_inside_website_adds_serviceability_line():
    # "website" contains "site".
    r = MirrorCascade().run("a corporate website redesign")
    assert any("Serviceability for local operators" in s for s in r.synthesis)
    assert not any("checklist-level" in s for s in r.synthesis)
    assert len(r.vetoes) == 3


# --- Documented-behavior: substring over-triggers, second pass ---
# (keyword-veto study 2026-09-22; same semantics as the first pass above —
# raw substring test ``w in low``. Each locks one more over-trigger with
# isolation: the owning list's line fires, the other list stays silent, and
# no pressure/absolute-claim vetoes appear.)


def test_overtrigger_local_inside_locally_adds_serviceability_line():
    # "locally" contains "local".
    r = MirrorCascade().run("serve it locally")
    assert any("Serviceability for local operators" in s for s in r.synthesis)
    assert not any("checklist-level" in s for s in r.synthesis)
    assert len(r.vetoes) == 3


def test_overtrigger_automat_inside_automatic_adds_automation_line():
    # "automatic" contains "automat".
    r = MirrorCascade().run("the automatic door")
    assert any("Automation stays checklist-level" in s for s in r.synthesis)
    assert not any("local operators" in s for s in r.synthesis)
    assert len(r.vetoes) == 3


def test_overtrigger_mobile_inside_automobile_adds_serviceability_line():
    # "automobile" contains "mobile".
    r = MirrorCascade().run("his antique automobile")
    assert any("Serviceability for local operators" in s for s in r.synthesis)
    assert not any("checklist-level" in s for s in r.synthesis)
    assert len(r.vetoes) == 3


def test_overtrigger_booking_inside_rebooking_adds_serviceability_line():
    # "rebooking" contains "booking".
    r = MirrorCascade().run("rebooking the flight")
    assert any("Serviceability for local operators" in s for s in r.synthesis)
    assert not any("checklist-level" in s for s in r.synthesis)
    assert len(r.vetoes) == 3


def test_overtrigger_clinic_inside_clinical_adds_serviceability_line():
    # "clinical" contains "clinic".
    r = MirrorCascade().run("clinical trial results")
    assert any("Serviceability for local operators" in s for s in r.synthesis)
    assert not any("checklist-level" in s for s in r.synthesis)
    assert len(r.vetoes) == 3
