"""Proof tests for Orkut-style squares (join gates, scrap wall, testimonials).

Laws: join gate closed by default, scrap wall members-only,
testimonials signed and retractable.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from levi.boards import squares  # noqa: E402


@pytest.fixture(autouse=True)
def _home(tmp_path, monkeypatch):
    monkeypatch.setattr(squares, "_home", lambda: tmp_path / "squares")
    (tmp_path / "squares").mkdir()
    yield


def test_create_square_founder_is_moderator():
    r = squares.create_square("retro-computing", "old machines", "chauncey")
    assert r["members"] == ["chauncey"]
    assert squares.is_member("retro-computing", "chauncey")


def test_create_rejects_bad_mode_and_dupes():
    with pytest.raises(squares.SquareError):
        squares.create_square("s", "d", "x", join_mode="secret-handshake")
    squares.create_square("s", "d", "x")
    with pytest.raises(squares.SquareError):
        squares.create_square("s", "d", "x")


def test_approval_mode_gate():
    squares.create_square("club", "d", "chauncey", join_mode="approval")
    assert squares.request_join("club", "sam") == "pending"
    assert not squares.is_member("club", "sam")
    squares.approve_join("club", "sam", "chauncey")
    assert squares.is_member("club", "sam")


def test_approve_requires_moderator():
    squares.create_square("club", "d", "chauncey", join_mode="approval")
    squares.request_join("club", "sam")
    with pytest.raises(squares.SquareError):
        squares.approve_join("club", "sam", "sam")  # not a moderator


def test_open_mode_joins_immediately():
    squares.create_square("plaza", "d", "chauncey", join_mode="open")
    assert squares.request_join("plaza", "sam") == "joined"
    assert squares.is_member("plaza", "sam")


def test_invite_mode_needs_vouch():
    squares.create_square("inner", "d", "chauncey", join_mode="invite")
    assert squares.request_join("inner", "sam") == "invited-needed"
    assert not squares.is_member("inner", "sam")
    squares.invite("inner", "sam", "chauncey")
    assert squares.request_join("inner", "sam") == "joined"


def test_scrap_wall_members_only():
    squares.create_square("club", "d", "chauncey", join_mode="open")
    with pytest.raises(squares.SquareError):
        squares.write_scrap("club", "outsider", "hello")
    squares.request_join("club", "sam")
    s = squares.write_scrap("club", "sam", "first!")
    assert s["author"] == "sam"
    assert squares.scraps("club")[0]["text"] == "first!"


def test_testimonial_signed_and_retractable():
    squares.create_square("club", "d", "chauncey", join_mode="open")
    squares.request_join("club", "sam")
    t = squares.leave_testimonial("club", "sam", "chauncey", "runs a tight square")
    assert t["author"] == "sam" and t["subject"] == "chauncey"
    assert len(squares.testimonials("club", "chauncey")) == 1
    # Only the author can withdraw.
    with pytest.raises(squares.SquareError):
        squares.withdraw_testimonial("club", t["id"], "chauncey")
    squares.withdraw_testimonial("club", t["id"], "sam")
    assert squares.testimonials("club", "chauncey") == []  # removed, not hidden


def test_testimonial_requires_members():
    squares.create_square("club", "d", "chauncey", join_mode="open")
    with pytest.raises(squares.SquareError):
        squares.leave_testimonial("club", "ghost", "chauncey", "hi")


def test_get_square_hides_internals():
    squares.create_square("club", "d", "chauncey", join_mode="approval")
    squares.request_join("club", "sam")
    face = squares.get_square("club")
    assert "pending" not in face and "invites" not in face
    assert face["member_count"] == 1
