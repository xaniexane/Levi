"""Proof for core/levi/signals/claim_grade.py laws.

Law 1: grades never self-upgrade — OBSERVED requires named provenance.
Law 2: INFERRED always carries the 'signal, not verdict' caveat.
Law 3: every card names provenance and what would change the grade.
Law 4: UNVERIFIED is the deny-closed default.
Law 5: the claim is quoted verbatim, never paraphrased.
"""

import pytest

from levi.signals.claim_grade import (
    INFERRED,
    OBSERVED,
    SIGNAL_NOT_VERDICT,
    UNVERIFIED,
    GradeError,
    grade_claim,
    render_card,
)


def test_observed_requires_full_provenance():
    card = grade_claim(
        "X attributes this account to Germany",
        observed_via="AboutAccountQuery (user session)",
        method="read X's own account-location field",
        what_would_change="X changing the field or the account disputing it",
    )
    assert card.grade == OBSERVED
    assert card.caveat == ""


def test_half_provenance_fails_closed():
    with pytest.raises(GradeError):
        grade_claim("some claim", observed_via="someone")
    with pytest.raises(GradeError):
        grade_claim("some claim", method="somehow")


def test_inferred_carries_structural_caveat():
    card = grade_claim(
        "this account is probably behind a VPN",
        basis="ASN/datacenter IP heuristic",
        observed_via="session metadata",
        what_would_change="a residential ASN on the same account",
    )
    assert card.grade == INFERRED
    assert SIGNAL_NOT_VERDICT in card.caveat
    rendered = render_card(card)
    assert "signal, not verdict" in rendered.lower()


def test_observed_and_heuristic_cannot_mix():
    with pytest.raises(GradeError):
        grade_claim(
            "a claim",
            observed_via="someone",
            method="somehow",
            basis="some heuristic",
        )


def test_no_provenance_is_unverified_never_a_guess():
    card = grade_claim("the moon is haunted")
    assert card.grade == UNVERIFIED
    assert "no provenance" in card.caveat.lower()
    rendered = render_card(card)
    assert UNVERIFIED in rendered


def test_empty_claim_fails_closed():
    with pytest.raises(GradeError):
        grade_claim("   ")


def test_claim_quoted_verbatim():
    claim = '  the account  POSTS from "Berlin" — exactly!  '
    card = grade_claim(claim)
    assert card.claim == claim
    assert claim in render_card(card)


def test_what_would_change_is_named():
    card = grade_claim(
        "some claim",
        observed_via="direct read",
        method="query",
        what_would_change="a second independent observation",
    )
    assert "a second independent observation" in render_card(card)


def test_receipt_binds_grade():
    a = grade_claim("same words", observed_via="x", method="y")
    b = grade_claim("same words")
    assert a.receipt != b.receipt  # same words, different grade -> different receipt
    assert a.grade == OBSERVED
    assert b.grade == UNVERIFIED
