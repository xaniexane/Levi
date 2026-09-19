"""Tests for levi.founders.chat_profiles — LEVI-native chat profiles (hermetic)."""

import json

from levi.founders import chat_profiles as cp


def test_seven_profiles():
    assert len(cp.PROFILES) == 7
    for pid in ("levi", "mentor", "workbench", "careful", "edge", "register", "care"):
        assert pid in cp.PROFILES


def test_get_profile_case_insensitive():
    assert cp.get_profile("EDGE").id == "edge"
    assert cp.get_profile("  levi ") is not None
    assert cp.get_profile("nope") is None


def test_validate_clean():
    assert cp.validate() == []


def test_no_provider_branding():
    blob = json.dumps(cp.to_dict()).lower()
    for brand in ("gemini", "copilot", "claude", "grok", "openai", "anthropic"):
        assert brand not in blob


def test_modes_valid():
    valid = {"companion", "mentor", "builder", "challenger", "quiet"}
    for p in cp.list_profiles():
        assert p.mode in valid
        assert p.starters, p.id
        assert p.guardrails, p.id


def test_profiles_json_parseable():
    data = json.loads(cp.profiles_json())
    assert set(data["profiles"]) == set(cp.PROFILES)
    assert len(data["seeds"]) == 4


def test_seeds():
    seed = cp.get_seed("morning_status")
    assert seed is not None and seed.opener
    assert cp.get_seed("nope") is None
    assert {s.id for s in cp.list_seeds()} == set(cp.SEEDS)


def test_format_profiles_lists_all():
    text = cp.format_profiles()
    for p in cp.list_profiles():
        assert p.label in text
