"""Tests for levi.customizations.profiles: named runtime profiles."""

import json

import pytest

from levi.customizations.profiles import (
    Profile,
    ProfileError,
    STANCES,
    activate,
    build_profile,
    deactivate,
    list_profiles,
    read_active,
)


@pytest.fixture()
def root(tmp_path):
    return tmp_path / "customizations"


def test_build_profile_defaults():
    p = build_profile("night-owl")
    assert p.name == "night-owl"
    assert p.quiet_hours == (22, 7)
    assert p.persona_stance == "plain"
    assert p.brief_lines == 16
    assert p.cadence_overrides == {}
    assert p.daemons_enabled == []


def test_build_profile_round_trip(root):
    p = build_profile(
        "deep-work",
        quiet_hours=(9, 17),
        cadence_overrides={"heartbeat": 120},
        persona_stance="sharp",
        brief_lines=8,
        daemons_enabled=["heartbeat", "janitor"],
    )
    path = activate(p, root=root)
    assert path.exists()
    back = read_active(root=root)
    assert back == p


def test_read_active_none_when_unset(root):
    assert read_active(root=root) is None


def test_deactivate(root):
    assert deactivate(root=root) is False
    activate(build_profile("x"), root=root)
    assert deactivate(root=root) is True
    assert read_active(root=root) is None


def test_activate_refuses_non_profile(root):
    with pytest.raises(ProfileError):
        activate({"name": "x"}, root=root)


def test_read_active_refuses_corrupt_json(root):
    (root).mkdir(parents=True, exist_ok=True)
    (root / "active.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ProfileError):
        read_active(root=root)


def test_deny_closed_bad_name():
    with pytest.raises(ProfileError):
        build_profile("")
    with pytest.raises(ProfileError):
        build_profile("has spaces!")


def test_deny_closed_bad_hours():
    with pytest.raises(ProfileError):
        build_profile("x", quiet_hours=(25, 7))
    with pytest.raises(ProfileError):
        build_profile("x", quiet_hours=(7, 7))
    with pytest.raises(ProfileError):
        build_profile("x", quiet_hours=(7,))


def test_deny_closed_bad_stance():
    with pytest.raises(ProfileError):
        build_profile("x", persona_stance="gandalf")
    assert "plain" in STANCES


def test_deny_closed_bad_brief_lines():
    with pytest.raises(ProfileError):
        build_profile("x", brief_lines=3)
    with pytest.raises(ProfileError):
        build_profile("x", brief_lines=True)


def test_deny_closed_bad_cadence():
    with pytest.raises(ProfileError):
        build_profile("x", cadence_overrides={"heartbeat": 0})
    with pytest.raises(ProfileError):
        build_profile("x", cadence_overrides={"heartbeat": "hourly"})


def test_deny_closed_duplicate_daemons():
    with pytest.raises(ProfileError):
        build_profile("x", daemons_enabled=["janitor", "janitor"])


def test_quiet_hours_wrap_is_legal():
    p = build_profile("x", quiet_hours=(23, 7))
    assert p.quiet_hours == (23, 7)


def test_list_profiles_names_active(root):
    activate(build_profile("first"), root=root)
    activate(build_profile("second"), root=root)
    names = list_profiles(root=root)
    assert "second" in names


def test_from_dict_round_trip():
    p = build_profile("rt", quiet_hours=(1, 5), persona_stance="playful")
    data = json.loads(json.dumps(p.to_dict()))
    assert Profile.from_dict(data) == p
