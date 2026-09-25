"""Hub auth tests — hermetic, no network."""

import pytest

from levi.hub import auth


@pytest.fixture()
def hubdir(monkeypatch, tmp_path):
    monkeypatch.setenv("LEVI_HUB_DIR", str(tmp_path / "hub"))
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_register_login_verify_logout(hubdir):
    r = auth.register("chauncey", "correct-horse-9")
    assert r["ok"] and r["username"] == "chauncey"
    login = auth.login("chauncey", "correct-horse-9", label="test")
    assert login["ok"] and login["token"]
    user = auth.verify_token(login["token"])
    assert user and user["username"] == "chauncey"
    out = auth.logout(login["token"])
    assert out["revoked"] == 1
    assert auth.verify_token(login["token"]) is None


def test_wrong_password_rejected(hubdir):
    auth.register("chauncey", "correct-horse-9")
    with pytest.raises(ValueError):
        auth.login("chauncey", "wrong")
    with pytest.raises(ValueError):
        auth.login("nobody", "whatever")


def test_duplicate_and_weak_rejected(hubdir):
    auth.register("chauncey", "correct-horse-9")
    with pytest.raises(ValueError):
        auth.register("chauncey", "another-pass-1")
    with pytest.raises(ValueError):
        auth.register("newuser", "short")


def test_bad_token_verifies_none(hubdir):
    assert auth.verify_token("") is None
    assert auth.verify_token("bogus") is None
