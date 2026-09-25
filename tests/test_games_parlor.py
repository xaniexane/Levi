"""Tests for levi.games.parlor — the third place that cannot be starved."""

import json
import os

import pytest

from levi.games.parlor import (
    MANIFEST,
    Parlor,
    ParlorError,
    ParlorStore,
    covenant_text,
)


def make_parlor():
    p = Parlor()
    p.register_handle("bit")
    p.register_handle("pix")
    return p


# -- handles ---------------------------------------------------------------


def test_register_ok():
    p = Parlor()
    h = p.register_handle("bit_01")
    assert h.name == "bit_01"
    assert [x.name for x in p.list_handles()] == ["bit_01"]


def test_register_bad_names():
    p = Parlor()
    for bad in ["", "a", "has space", "way-too-long-handle-name-here", "-lead", "!x"]:
        with pytest.raises(ParlorError):
            p.register_handle(bad)


def test_register_duplicate_case_insensitive():
    p = Parlor()
    p.register_handle("Bit")
    with pytest.raises(ParlorError):
        p.register_handle("bit")


def test_unregister_ok_and_unknown():
    p = make_parlor()
    p.unregister_handle("bit")
    assert [x.name for x in p.list_handles()] == ["pix"]
    with pytest.raises(ParlorError):
        p.unregister_handle("ghost")


def test_unregister_blocked_with_posts():
    p = make_parlor()
    p.post("bit", "hello board")
    with pytest.raises(ParlorError):
        p.unregister_handle("bit")


# -- bulletin board ----------------------------------------------------------


def test_post_ok_and_chronological():
    p = make_parlor()
    p.post("bit", "first")
    p.post("pix", "second")
    board = p.board()
    assert [x.text for x in board] == ["first", "second"]  # newest last, no ranking
    assert board[0].handle == "bit"


def test_post_unknown_handle_empty_too_long():
    p = make_parlor()
    with pytest.raises(ParlorError):
        p.post("ghost", "hi")
    with pytest.raises(ParlorError):
        p.post("bit", "   ")
    with pytest.raises(ParlorError):
        p.post("bit", "x" * 501)


def test_board_limit():
    p = make_parlor()
    for i in range(5):
        p.post("bit", "post %d" % i)
    assert len(p.board(limit=2)) == 2
    assert p.board(limit=2)[-1].text == "post 4"


def test_delete_own_post_ok_others_fail():
    p = make_parlor()
    post = p.post("bit", "mine")
    with pytest.raises(ParlorError):
        p.delete_post(post.id, "pix")  # not the author
    p.delete_post(post.id, "bit")
    assert p.board() == []
    with pytest.raises(ParlorError):
        p.delete_post(999, "bit")


# -- game nights -------------------------------------------------------------


def test_schedule_and_rsvp():
    p = make_parlor()
    n = p.schedule_night("Friday Nim", "nim", "2026-09-25T20:00:00", "bit")
    assert n.id == 1
    assert n.rsvps == {"bit": True}  # host auto-RSVPs
    p.rsvp(1, "pix")
    assert n.rsvps["pix"] is True
    p.rsvp(1, "pix", attending=False)
    assert n.rsvps["pix"] is False


def test_schedule_bad_host_and_bad_time():
    p = make_parlor()
    with pytest.raises(ParlorError):
        p.schedule_night("x", "nim", "2026-09-25T20:00:00", "ghost")
    with pytest.raises(ParlorError):
        p.schedule_night("x", "nim", "not-a-time", "bit")
    with pytest.raises(ParlorError):
        p.schedule_night("   ", "nim", "2026-09-25T20:00:00", "bit")


def test_rsvp_unknown_night_and_handle():
    p = make_parlor()
    p.schedule_night("x", "nim", "2026-09-25T20:00:00", "bit")
    with pytest.raises(ParlorError):
        p.rsvp(999, "bit")
    with pytest.raises(ParlorError):
        p.rsvp(1, "ghost")


def test_cancel_only_by_host_and_upcoming():
    p = make_parlor()
    n1 = p.schedule_night("a", "nim", "2026-09-25T20:00:00", "bit")
    n2 = p.schedule_night("b", "tictactoe", "2026-09-26T20:00:00", "pix")
    with pytest.raises(ParlorError):
        p.cancel_night(n1.id, "pix")
    p.cancel_night(n1.id, "bit")
    assert n1.cancelled
    assert [n.id for n in p.upcoming_nights()] == [n2.id]
    with pytest.raises(ParlorError):
        p.rsvp(n1.id, "pix")  # cancelled nights take no RSVPs


# -- portable state ----------------------------------------------------------


def test_export_import_round_trip():
    p = make_parlor()
    p.post("bit", "hello")
    n = p.schedule_night("a", "nim", "2026-09-25T20:00:00", "bit")
    p.rsvp(n.id, "pix")
    data = p.to_dict()
    assert data["format_version"] == 1
    q = Parlor.from_dict(json.loads(json.dumps(data)))
    assert [h.name for h in q.list_handles()] == ["bit", "pix"]
    assert [x.text for x in q.board()] == ["hello"]
    assert q.nights[n.id].rsvps == {"bit": True, "pix": True}


def test_import_deny_closed():
    for bad in [
        "not a dict",
        {"handles": "nope"},
        {"posts": [{"text": "x"}]},
        {"handles": [{"name": "!!bad!!"}]},
        {"nights": [{"title": "t"}]},
    ]:
        with pytest.raises(ParlorError):
            Parlor.from_dict(bad)


def test_store_round_trip_owner_only(tmp_path):
    store = ParlorStore(tmp_path / "parlor.json")
    p = make_parlor()
    p.post("bit", "hello")
    store.save(p)
    loaded = store.load()
    assert [h.name for h in loaded.list_handles()] == ["bit", "pix"]
    assert [x.text for x in loaded.board()] == ["hello"]
    assert oct(os.stat(store.path).st_mode & 0o777) == "0o600"


def test_store_load_missing_is_empty_parlor(tmp_path):
    store = ParlorStore(tmp_path / "parlor.json")
    assert store.load().list_handles() == []


# -- charter + covenant -------------------------------------------------------


def test_manifest_is_honest_by_default():
    assert MANIFEST.name == "parlor"
    assert MANIFEST.has_paid_randomness is False
    assert MANIFEST.has_streak_punishment is False
    assert MANIFEST.has_fomo_timers is False
    assert MANIFEST.has_pay_for_hints is False
    assert MANIFEST.requires_network is False
    assert MANIFEST.progress_portable is True
    assert MANIFEST.odds_declared is True
    assert MANIFEST.hints_free is True
    assert MANIFEST.has_sunset_plan is True


def test_covenant_names_the_four_kills():
    text = covenant_text()
    for phrase in ["nothing to buy", "No feed", "smallness", "No acquisition"]:
        assert phrase in text
