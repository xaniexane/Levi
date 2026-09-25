"""Tests for levi.ei.routing — EI-routed persona selection (TRACK 2).

EIState stubs are constructed directly (no personas package, no I/O).
"""

from levi.ei.five_d import EIState
from levi.ei.routing import suggest_lens, route_for_text

AVAILABLE = ["friend", "protector", "trickster", "mentor", "archivist", "challenger"]


def test_high_intensity_suggests_protector():
    state = EIState(user_tone="distress", user_intensity=0.9)
    assert suggest_lens(state, AVAILABLE) == "protector"


def test_steadying_tone_suggests_protector_even_at_moderate_intensity():
    state = EIState(user_tone="fear", user_intensity=0.3)
    assert suggest_lens(state, AVAILABLE) == "protector"


def test_playful_tone_suggests_trickster():
    state = EIState(user_tone="playful", user_intensity=0.4)
    assert suggest_lens(state, AVAILABLE) == "trickster"


def test_learning_tone_suggests_mentor():
    for tone in ("learning", "exploratory", "confusion"):
        state = EIState(user_tone=tone, user_intensity=0.3)
        assert suggest_lens(state, AVAILABLE) == "mentor", tone


def test_reflective_tone_suggests_archivist():
    for tone in ("reflective", "archival"):
        state = EIState(user_tone=tone, user_intensity=0.3)
        assert suggest_lens(state, AVAILABLE) == "archivist", tone


def test_adversarial_tone_suggests_challenger():
    for tone in ("adversarial", "pushback", "debate"):
        state = EIState(user_tone=tone, user_intensity=0.4)
        assert suggest_lens(state, AVAILABLE) == "challenger", tone


def test_neutral_defaults_to_friend():
    assert suggest_lens(EIState(), AVAILABLE) == "friend"
    assert (
        suggest_lens(EIState(user_tone=None, user_intensity=0.0), AVAILABLE) == "friend"
    )
    assert (
        suggest_lens(EIState(user_tone="collaborative", user_intensity=0.4), AVAILABLE)
        == "friend"
    )


def test_unknown_tone_defaults_to_friend():
    state = EIState(user_tone="mystery-nonsense-tone", user_intensity=0.2)
    assert suggest_lens(state, AVAILABLE) == "friend"


def test_unknown_id_falls_back_to_friend():
    # "trickster" suggestion is not offered; "friend" is -> friend.
    state = EIState(user_tone="playful", user_intensity=0.4)
    assert suggest_lens(state, ["friend", "mentor"]) == "friend"


def test_unknown_id_without_friend_falls_back_to_available_zero():
    state = EIState(user_tone="playful", user_intensity=0.4)
    assert suggest_lens(state, ["mentor", "challenger"]) == "mentor"


def test_empty_available_fail_closed():
    # Never crashes; fail closed to the safe default.
    state = EIState(user_tone="playful", user_intensity=0.4)
    assert suggest_lens(state, []) == "friend"
    assert suggest_lens(EIState(), []) == "friend"


def test_suggestion_used_when_available():
    state = EIState(user_tone="playful", user_intensity=0.4)
    assert suggest_lens(state, AVAILABLE) == "trickster"


def test_route_for_text_smoke():
    lens, state = route_for_text("Can you help me plan my week?", ["friend", "mentor"])
    assert lens in ("friend", "mentor")
    assert isinstance(state, EIState)
    assert state.user_tone is not None


def test_route_for_text_distressed():
    lens, state = route_for_text(
        "I can't breathe, everything is falling apart", AVAILABLE
    )
    assert lens == "protector"
    assert state.user_intensity >= 0.7
