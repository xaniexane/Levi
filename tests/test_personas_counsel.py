"""Tests for levi.personas.counsel — the board counsel stances.

Proof of the law: every text field of every stance passes check_no_mask
(no borrowed identity, no provider branding). Stances modulate critique
angle only; reviews are deterministic and always return full sections.

Hermetic: pure function tests, no I/O.
"""

from __future__ import annotations

import pytest

from levi.bot.persona import check_no_mask
from levi.personas.counsel import (
    COUNSEL_LAW,
    STANCES,
    UnknownStance,
    get_stance,
    list_stances,
    review,
    verify_no_mask,
)


def test_law_no_mask_on_every_text_field():
    assert check_no_mask(COUNSEL_LAW) == []
    assert verify_no_mask() == []


def test_three_original_stances():
    assert list_stances() == ["builder", "contrarian", "keeper"]
    for stance_id in list_stances():
        stance = get_stance(stance_id)
        assert stance.name and stance.stake and stance.doctrine
        assert stance.triggers and stance.standing_flags and stance.next_step_hint


def test_unknown_stance_refused_never_guessed():
    with pytest.raises(UnknownStance):
        review("oracle-of-doom", "do the thing")


def test_review_is_deterministic():
    proposal = "We should delete the old vault and rewrite it free eventually"
    first = review("keeper", proposal)
    second = review("keeper", proposal)
    assert first.render() == second.render()


def test_keeper_triggers_fire():
    report = review("keeper", "Plan: delete the old vault, rewrite it, offer it free.")
    triggers = {c.trigger for c in report.triggered}
    assert {"delete", "rewrite", "free"} <= triggers
    for check in report.triggered:
        assert check.question.endswith("?")


def test_contrarian_attacks_absolutes():
    report = review("contrarian", "This will always work and never fail, guaranteed.")
    triggers = {c.trigger for c in report.triggered}
    assert {"always", "never", "guarantee"} <= triggers


def test_builder_attacks_vagueness():
    report = review("builder", "Eventually we will integrate the framework, someday.")
    triggers = {c.trigger for c in report.triggered}
    assert {"eventually", "integrat", "someday"} <= triggers


def test_no_triggers_still_returns_full_sections():
    report = review("builder", "Add a button to the settings page.")
    assert report.triggered == []
    assert len(report.standing_flags) == 2
    assert report.next_step
    rendered = report.render()
    assert "Triggered checks:" in rendered
    assert "Standing flags:" in rendered
    assert "Next step:" in rendered
    assert report.stance_name == "The Builder"


def test_empty_proposal_still_gets_standing_review():
    report = review("contrarian", "")
    assert report.standing_flags
    assert report.next_step


def test_stances_dont_leak_identity():
    # The law in code: counsel is critique angle, never a persona claim.
    for stance in STANCES.values():
        joined = " ".join(stance.text_fields()).lower()
        assert "i am" not in joined
        assert "i'm" not in joined
