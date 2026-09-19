"""Tests for the Plaiground adult-SI extensions.

Hermetic: tmp home, never the real ``~/.levi``. Covers the bounds
guard, the stories engine, wellness, after-dark entertainment,
companion depth, and the unified CLI — plus the invariants: every
new entry point is gate-locked by default, all records are tagged
``track: si`` / ``zone: plaiground``, and no explicit content ships
in any module.
"""

from pathlib import Path

import pytest

from levi.plaiground import (
    afterdark,
    bounds,
    depth,
    gate,
    stories,
    wellness,
)
from levi.plaiground.bounds import BoundsError
from levi.plaiground.gate import GateLockedError


@pytest.fixture()
def home(tmp_path):
    return tmp_path


@pytest.fixture()
def enabled(home):
    gate.enable_adult_mode(gate.CONFIRMATION_PHRASE, home=home)
    return home


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in gate.MINOR_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


# ---------------------------------------------------------------------------
# Gate law holds for every new entry point
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fn",
    [
        lambda h: stories.story_starter(home=h),
        lambda h: wellness.checkin(home=h),
        lambda h: afterdark.banter(home=h),
        lambda h: depth.rapport("Nobody", home=h),
        lambda h: bounds.check_bounds("hello", home=h),
    ],
)
def test_new_entries_locked_by_default(home, fn):
    with pytest.raises(GateLockedError):
        fn(home)


def test_track_and_zone_tags(enabled):
    assert stories.story_starter(home=enabled)["track"] == "si"
    assert stories.story_starter(home=enabled)["zone"] == "plaiground"
    assert wellness.checkin(home=enabled)["track"] == "si"
    assert afterdark.banter(home=enabled)["zone"] == "plaiground"


# ---------------------------------------------------------------------------
# Bounds guard
# ---------------------------------------------------------------------------


def test_bounds_passes_ordinary_adult_text(enabled):
    assert bounds.check_bounds("a slow dance in the kitchen", enabled) == "a slow dance in the kitchen"


@pytest.mark.parametrize(
    "text",
    [
        "a story about a teen romance",
        "she was underage but nobody knew",
        "he forced her against her will",
        "drugged and helpless",
        "he killed him in the final scene",
        "torture as a plot device",
        "trick her into it without her knowledge",
        "secretly film them",
        "gaslight him until he agrees",
    ],
)
def test_bounds_refuses_hard_categories(enabled, text):
    with pytest.raises(BoundsError):
        bounds.check_bounds(text, enabled)


def test_bounds_refusal_names_category(enabled):
    with pytest.raises(BoundsError, match="minor"):
        bounds.check_bounds("a minor character", enabled)


def test_bounds_passes_helper_never_raises(enabled):
    assert bounds.passes("a romantic dinner", enabled) is True
    assert bounds.passes("a teen", enabled) is False


# ---------------------------------------------------------------------------
# Stories engine
# ---------------------------------------------------------------------------


def test_starter_deterministic(enabled):
    a = stories.story_starter(seed="s1", home=enabled)
    b = stories.story_starter(seed="s1", home=enabled)
    assert a == b
    assert a["opener"] and a["setting"] and a["tension"]


def test_starter_varies_by_seed(enabled):
    a = stories.story_starter(seed="s1", home=enabled)["opener"]
    b = stories.story_starter(seed="s2", home=enabled)["opener"]
    assert a != b


def test_build_character_craft_note(enabled):
    c = stories.build_character("Mara", "to be seen", "an old betrayal", home=enabled)
    assert c["name"] == "Mara"
    assert "Mara" in c["craft_note"] and "to be seen" in c["craft_note"]


def test_build_character_bounds_checked(enabled):
    with pytest.raises(BoundsError):
        stories.build_character("X", "a teen", "wound", home=enabled)


def test_weave_arc_no_repeats(enabled):
    arc = stories.weave_arc(beats=5, seed="arc1", home=enabled)
    assert len(arc["beats"]) == 5
    assert len(set(arc["beats"])) == 5


def test_frame_scene_tension_allowlist(enabled):
    with pytest.raises(ValueError):
        stories.frame_scene(tension="maximum", home=enabled)
    scene = stories.frame_scene(tension="closed-door", home=enabled)
    assert scene["tension"] == "closed-door"
    assert len(scene["sensory_anchors"]) == 3


def test_remix_orders_user_fragments(enabled):
    r = stories.remix(["a lighthouse", "a storm", "a letter"], home=enabled)
    assert r["count"] == 3
    assert "a lighthouse" in r["premise"]


# ---------------------------------------------------------------------------
# Wellness
# ---------------------------------------------------------------------------


def test_checkin_count_and_determinism(enabled):
    a = wellness.checkin(count=4, seed="w", home=enabled)
    b = wellness.checkin(count=4, seed="w", home=enabled)
    assert a["questions"] == b["questions"]
    assert len(a["questions"]) == 4


def test_prompt_deck_themes(enabled):
    for theme in ("desire", "boundaries", "appreciation", "repair"):
        deck = wellness.prompt_deck(theme, home=enabled)
        assert deck["theme"] == theme and len(deck["prompts"]) == 4
    with pytest.raises(ValueError):
        wellness.prompt_deck("nope", home=enabled)


def test_wellness_notes_carry_disclaimer(enabled):
    n = wellness.notes("desire", home=enabled)
    assert "not medical" in n["disclaimer"].lower()


def test_date_night_plan(enabled):
    plan = wellness.plan_date_night(seed="d", home=enabled)
    assert plan["idea"] and len(plan["rituals"]) == 3


def test_custom_checkin_bounds_checked(enabled):
    with pytest.raises(BoundsError):
        wellness.custom_checkin(["how was your day, teen?"], home=enabled)
    c = wellness.custom_checkin(["what made you laugh today?"], home=enabled)
    assert c["count"] == 1


# ---------------------------------------------------------------------------
# After-dark
# ---------------------------------------------------------------------------


def test_banter_deterministic(enabled):
    assert afterdark.banter(seed="b", home=enabled) == afterdark.banter(seed="b", home=enabled)


def test_starters_themes(enabled):
    for theme in ("confessions", "stories", "opinions", "deep"):
        s = afterdark.starters(theme, home=enabled)
        assert len(s["starters"]) == 3
    with pytest.raises(ValueError):
        afterdark.starters("nope", home=enabled)


def test_trivia_rounds(enabled):
    t = afterdark.trivia(count=4, seed="t", home=enabled)
    assert len(t["rounds"]) == 4
    for rnd in t["rounds"]:
        assert rnd["question"] and rnd["answer"]
    # Deterministic order from seed.
    t2 = afterdark.trivia(count=4, seed="t", home=enabled)
    assert [r["question"] for r in t["rounds"]] == [r["question"] for r in t2["rounds"]]


def test_host_game_frames(enabled):
    for kind in ("two-truths", "would-you-rather", "story-round"):
        g = afterdark.host_game(kind, home=enabled)
        assert g["rules"] and g["opener"]


def test_submit_round_bounds_checked(enabled):
    with pytest.raises(BoundsError):
        afterdark.submit_round("two-truths", ["I am a teen"], home=enabled)
    r = afterdark.submit_round("story-round", ["The lights went out.", "Nobody moved."], home=enabled)
    assert "2 sentences" in r["host_says"]


# ---------------------------------------------------------------------------
# Depth
# ---------------------------------------------------------------------------


def _mk_companion(enabled, name="Nova"):
    from levi.plaiground import companions

    companions.create_companion(name, home=enabled)
    return name


def test_remember_and_recall(enabled):
    name = _mk_companion(enabled)
    depth.remember(name, "first late-night talk", kind="milestone", home=enabled)
    depth.remember(name, "likes stargazing", kind="preference", home=enabled)
    rec = depth.recall(name, home=enabled)
    assert rec["count"] == 2
    assert rec["entries"][0]["kind"] == "milestone"


def test_remember_bounds_checked(enabled):
    name = _mk_companion(enabled)
    with pytest.raises(BoundsError):
        depth.remember(name, "a story about a minor", home=enabled)


def test_journal_is_owner_only(enabled):
    from levi.plaiground import companions

    name = _mk_companion(enabled, "Vex")
    depth.remember(name, "a quiet evening", home=enabled)
    path = depth._journal_path(name, enabled)
    assert path.is_file()
    assert (path.stat().st_mode & 0o777) == 0o600


def test_rapport_earned_not_flattered(enabled):
    name = _mk_companion(enabled, "Rook")
    fresh = depth.rapport(name, home=enabled)
    assert fresh["rapport"] == 0
    assert fresh["band"] == "just met"
    for i in range(6):
        depth.remember(name, "moment %d" % i, home=enabled)
    depth.remember(name, "first milestone", kind="milestone", home=enabled)
    grown = depth.rapport(name, home=enabled)
    assert grown["rapport"] > fresh["rapport"]
    # Deterministic: same record, same score.
    assert depth.rapport(name, home=enabled)["rapport"] == grown["rapport"]


def test_forget(enabled):
    name = _mk_companion(enabled, "Ash")
    depth.remember(name, "something", home=enabled)
    assert depth.forget(name, home=enabled) is True
    assert depth.recall(name, home=enabled)["count"] == 0
    assert depth.forget(name, home=enabled) is False


# ---------------------------------------------------------------------------
# No explicit content ships in the new modules
# ---------------------------------------------------------------------------


def test_no_explicit_presets_anywhere():
    import inspect
    import re

    import levi.plaiground.stories as st
    import levi.plaiground.afterdark as ad
    import levi.plaiground.wellness as we

    blob = inspect.getsource(st) + inspect.getsource(ad) + inspect.getsource(we)
    lowered = blob.lower()
    for word in ("porn", "xxx", "orgasm", "masturbat", "fetish"):
        assert word not in lowered, word
    # "explicit" may only appear in doctrine/negated senses — never as a
    # shipped thing. Allowlist: "non-explicit", "explicit seed"
    # (determinism), "no explicit ..." / "nothing explicit ..." (the
    # no-shipped-content doctrine).
    allowed = re.compile(
        r"(non-explicit|explicit seed|no explicit|nothing explicit)"
    )
    scrubbed = allowed.sub("", re.sub(r"\s+", " ", lowered))
    assert "explicit" not in scrubbed, "unnegated 'explicit' in shipped source"


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------


def test_cli_gate_status_no_gate_needed(home, monkeypatch, capsys):
    from levi.plaiground.cli import main

    monkeypatch.setenv("HOME", str(home))
    rc = main(["gate", "status"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "plaiground" in out


def test_cli_story_locked_without_gate(home, monkeypatch, capsys):
    from levi.plaiground.cli import main

    monkeypatch.setenv("HOME", str(home))
    rc = main(["story", "starter"])
    assert rc == 1
    assert "LOCKED" in capsys.readouterr().out
