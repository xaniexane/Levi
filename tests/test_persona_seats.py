"""Tests for levi.persona.seats — operator-seat frames."""

import pytest

from levi.interop.registry import Registry
from levi.persona.seats import (
    MODULE_NAME,
    PROVIDES,
    SeatError,
    all_seats,
    get,
    provisional_notice,
    register_capabilities,
    render,
    suggest,
    twin_facets,
)


def test_five_seats_canon_order():
    assert [s.id for s in all_seats()] == [
        "levi",
        "echo-alpha",
        "echo-omega",
        "demandpulse",
        "rex",
    ]


def test_twin_canon_one_individual_two_faces():
    facets = twin_facets()
    assert [s.id for s in facets] == ["echo-alpha", "echo-omega"]
    assert all(s.facet_of == "Echo" for s in facets)
    assert get("echo-alpha").name == "Alpha"
    assert get("echo-omega").name == "Omega"


def test_seat_roles():
    assert "face" in get("levi").role
    assert "builder" in get("echo-alpha").role
    assert "daemon" in get("echo-omega").role
    assert "coach" in get("demandpulse").role
    assert "teacher" in get("rex").role


def test_all_provisional():
    for seat in all_seats():
        assert "provisional" in seat.status.lower()
    notice = provisional_notice()
    assert "provisional" in notice.lower()
    # the open question is recorded, never presumed answered
    assert "grounded" in notice and "outer-space" in notice


def test_suggest_routes():
    assert suggest("build me an app")[0][0] == "echo-alpha"
    assert suggest("run this every night and watch it")[0][0] == "echo-omega"
    assert suggest("teach me the lesson")[0][0] == "rex"
    assert suggest("coach me through my morning routine")[0][0] == "demandpulse"


def test_suggest_deterministic():
    first = suggest("verify and review this batch")
    assert first == suggest("verify and review this batch")
    # every seat always ranked, scores non-increasing
    assert len(first) == 5
    scores = [score for _, score in first]
    assert scores == sorted(scores, reverse=True)


def test_render_shows_status():
    card = render("echo-alpha")
    assert "Alpha" in card
    assert "Echo" in card
    assert "provisional" in card.lower()


def test_unknown_seat_raises():
    with pytest.raises(SeatError):
        get("sauron")


def test_register_capabilities():
    reg = Registry()
    register_capabilities(reg)
    assert MODULE_NAME in reg.modules()
    assert PROVIDES[0] in reg.declaration(MODULE_NAME)["provides"]
    reg.check_all()  # must not raise
