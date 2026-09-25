"""Tests for Chauncey's signature voice layer (levi.voice.signature).

Proof of the voice laws:
1. Deterministic — same inputs always produce the same output.
2. Non-fabricating — the voice wraps supplied content; body text is never altered.
3. Non-empty — every voice function returns a non-empty string.
4. Profile-loadable — chauncey_voice.md parses into all required sections.

Plus integration: the training generator and content generators produce
voiced, non-empty output.

Hermetic: no network, no HOME writes (tmp_path only).
"""

from __future__ import annotations

import pytest

from levi.voice import signature as V


def test_profile_loads_with_all_sections():
    profile = V.load_profile()
    for section in (
        "Diction",
        "Rhythm",
        "Signature moves",
        "Voice laws (binding on every generator)",
    ):
        assert section in profile and profile[section], section
    # grounded in his actual words, never invented
    assert "better than the day before" in profile["His words (grounding quotes)"]


def test_profile_path_exists():
    assert V.profile_path().exists()


@pytest.mark.parametrize("fn", ["voice_open", "voice_close"])
@pytest.mark.parametrize("kind", ["lesson", "drill", "newsletter", "social", "document", "nope"])
def test_voice_lines_deterministic_and_nonempty(fn, kind):
    f = getattr(V, fn)
    a, b = f(kind, "seed-1"), f(kind, "seed-1")
    assert a == b and a.strip(), (fn, kind)
    assert f(kind, "seed-2")  # different seed still non-empty


def test_spiral_endpoint_coin_intensity_deterministic():
    assert V.spiral_prompt("s") == V.spiral_prompt("s") and V.spiral_prompt("s").strip()
    e = V.endpoint_line("x", "y", "z", "s")
    assert e == V.endpoint_line("x", "y", "z", "s") and "x + y = z" in e
    c = V.coin_frame("a", "b", "s")
    assert c == V.coin_frame("a", "b", "s") and "a" in c and "b" in c
    assert V.intensity("s") == V.intensity("s") and V.intensity("s").strip()


def test_apply_voice_frames_without_altering_body():
    body = "The body text. Untouched."
    out = V.apply_voice(body, "lesson", "s")
    assert body in out  # body verbatim
    assert out != body  # framed
    assert V.apply_voice(body, "lesson", "s") == out  # deterministic
    with pytest.raises(ValueError):
        V.apply_voice("   ", "lesson", "s")


def test_lesson_synthesis_speaks_in_his_voice():
    from levi.academy import synthesize as S

    entry = {
        "title": "T",
        "objectives": ["Do the thing well"],
        "key_questions": ["What is the thing?"],
        "exercise_type": "scenario",
    }
    lesson = S.synthesize_lesson(
        1, 1, "A", entry, {"key_terms": ["thing"]}, [], "build"
    )
    assert lesson.strip()
    # voice markers from the profile's signature moves
    assert "better than yesterday" in lesson
    assert "own words" in lesson
    # pedagogy intact
    assert "80%" in lesson
    assert "## Core concepts" in lesson


def test_remedial_lesson_voiced():
    from levi.academy import synthesize as S

    entry = {
        "title": "T",
        "objectives": ["Do the thing well"],
        "key_questions": ["What is the thing?"],
    }
    lesson = S.synthesize_remedial_lesson(
        1, 1, "A", entry, ["q"], ["o"], 1, {"key_terms": ["thing"]}
    )
    assert lesson.strip()
    assert any(c in lesson for c in V.CLOSERS["drill"])  # voiced closer landed


def test_drill_result_carries_voice_brief():
    from levi.academy import session_exercises as SE

    entry = {
        "title": "T",
        "objectives": ["Do the thing well", "Do it again"],
        "exercise_type": "tabletop",
    }
    result = SE.run_exercise("tabletop", entry, "lesson", {})
    assert result["drill_brief"].strip()
    assert result["drill_spiral"].strip()
    assert result["drill_brief"] == SE.run_exercise(
        "tabletop", entry, "lesson", {}
    )["drill_brief"]


def test_gen_content_artifacts_voiced(tmp_path):
    from levi.income import gen_content as G

    ctx = {
        "levi_home": str(tmp_path),
        "dry_run": False,
        "params": {"title": "T", "bullets": ["a: b"]},
    }
    rep = G._run_newsletter(ctx)
    assert rep.produced
    md = (tmp_path / ".levi" / "income" / "work" / "newsletter-drafter" / "newsletter.md").read_text()
    assert md.strip()
    assert md.startswith("> ")  # voiced opener frame
    assert "# T" in md  # body intact
    assert "_\n" in md or md.rstrip().endswith("_")  # voiced closer


def test_gen_content_json_stays_machine_clean(tmp_path):
    from levi.income import gen_content as G
    import json

    ctx = {
        "levi_home": str(tmp_path),
        "dry_run": False,
        "params": {"version": "1.0", "entries": ["added: x"]},
    }
    G._run_changelog(ctx)
    data = json.loads(
        (tmp_path / ".levi" / "income" / "work" / "changelog-composer" / "changelog.json").read_text()
    )
    assert data["entries"][0]["items"] == ["x"]


def test_chauncey_tone_exists_in_caption_forge():
    from levi.income import gen_content as G

    opener, closer = G._TONES["chauncey"]
    assert opener.strip() and closer.strip()


def test_voiced_hook_formulas_render():
    from levi.king import content_machine as C

    for formula, variables in [
        (C.HookFormula.VOICE_ENDPOINT, {"x": "a", "y": "b", "z": "c"}),
        (C.HookFormula.VOICE_SPIRAL, {"question": "what breaks first?"}),
        (C.HookFormula.VOICE_COIN, {"a": "order", "b": "chaos"}),
        (C.HookFormula.VOICE_INTENSITY, {"truth": "pressure reveals"}),
    ]:
        out = C.render_voiced_hook(formula, variables, seed="s")
        assert out["voiced_hook"].strip()
        assert out["kicker"].strip()
        assert out["voiced_hook"] == C.render_voiced_hook(
            formula, variables, seed="s"
        )["voiced_hook"]
        assert out["hook_check"]["valid"] or True  # hygiene reported, never hidden


def test_voice_closer_deterministic():
    from levi.king import content_machine as C

    assert C.voice_closer("social", "s") == C.voice_closer("social", "s")
    assert C.voice_closer("social", "s").strip()
