"""Hermetic tests for the Download Play guest-kit revival."""

import json

import pytest

from levi.games import guestplay
from levi.games.guestplay import GuestPlayError, build_kit, open_kit


def _kit(ttl=3600, now=1_000_000):
    return build_kit(
        "mancala",
        rules={"variant": "kalah", "seeds": 4},
        data={"board.txt": b"pits:6", "notes.txt": b"guest rules apply"},
        ttl_seconds=ttl,
        now=now,
    )


def _open(kit, token, path, now=1_000_000):
    return open_kit(kit, token, path, now=now)


def test_round_trip(tmp_path):
    kit, token = _kit()
    session = _open(kit, token, tmp_path / "session")
    try:
        assert session.game_id == "mancala"
        assert session.rules == {"variant": "kalah", "seeds": 4}
        assert sorted(session.files) == ["board.txt", "notes.txt"]
        assert session.read("board.txt") == b"pits:6"
    finally:
        session.close()
    # No residue: the guest's machine keeps nothing afterward.
    assert not (tmp_path / "session").exists()


def test_wrong_token_refused(tmp_path):
    kit, _token = _kit()
    with pytest.raises(GuestPlayError):
        open_kit(kit, "wrong-token", tmp_path / "s")


def test_tampered_kit_refused(tmp_path):
    kit, token = _kit()
    env = json.loads(kit.decode("utf-8"))
    sealed = env["sealed"]
    # Flip one character of the sealed payload.
    bad = ("A" if sealed[10] != "A" else "B") + sealed[11:]
    env["sealed"] = bad
    with pytest.raises(GuestPlayError):
        open_kit(json.dumps(env).encode("utf-8"), token, tmp_path / "s")


def test_garbage_is_not_a_kit(tmp_path):
    with pytest.raises(GuestPlayError):
        open_kit(b"not a kit", "token", tmp_path / "s")


def test_expired_kit_refused(tmp_path):
    kit, token = _kit(ttl=60, now=1_000_000)
    with pytest.raises(GuestPlayError) as ei:
        open_kit(kit, token, tmp_path / "s", now=1_000_000 + 61)
    assert "expired" in str(ei.value).lower()
    # The failed open leaves no half-unpacked session behind.
    assert not (tmp_path / "s").exists()


def test_nonempty_session_dir_refused(tmp_path):
    kit, token = _kit()
    d = tmp_path / "s"
    d.mkdir()
    (d / "precious.txt").write_text("mine")
    with pytest.raises(GuestPlayError):
        open_kit(kit, token, d)
    assert (d / "precious.txt").read_text() == "mine"


def test_unsafe_data_name_refused_at_build():
    with pytest.raises(GuestPlayError):
        build_kit("mancala", {}, {"../evil.txt": b"x"})
    with pytest.raises(GuestPlayError):
        build_kit("mancala", {}, {"/abs.txt": b"x"})


def test_token_is_bearer_secret():
    _kit_bytes, token = _kit()
    assert token and len(token) >= 24
    _kit2, token2 = _kit()
    assert token != token2  # possession is per-session


def test_session_close_is_idempotent(tmp_path):
    kit, token = _kit()
    session = _open(kit, token, tmp_path / "s")
    session.close()
    session.close()  # no error
    with pytest.raises(GuestPlayError):
        session.read("board.txt")


def test_context_manager_closes(tmp_path):
    kit, token = _kit()
    with _open(kit, token, tmp_path / "s") as session:
        assert session.read("notes.txt") == b"guest rules apply"
    assert not (tmp_path / "s").exists()


def test_unknown_file_refused(tmp_path):
    kit, token = _kit()
    session = _open(kit, token, tmp_path / "s")
    try:
        with pytest.raises(GuestPlayError):
            session.read("nope.txt")
    finally:
        session.close()
