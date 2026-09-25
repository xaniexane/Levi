"""Hermetic tests for Wave Pulse engine selection (levi.demand.engines).

No network, no HOME writes (LEVI_HOME pointed at tmp_path), no randomness.
"""

import json

import pytest

from levi.demand import engines, studio
from levi.demand.studio import (
    GRADE_THRESHOLD,
    ContentBrief,
    ContentSignal,
    extract_patterns,
    generate_brief,
    load_engine_prompt,
    render_brief,
    save_brief,
    save_signals,
)


def _sig(**kw):
    base = dict(id="e1", platform="facebook", text="alpha beta gamma delta epsilon")
    base.update(kw)
    return ContentSignal(**base)


def _graded_pair(sid="w1", grade=90.0):
    from levi.demand.studio import GradeResult

    s = _sig(id=sid, metrics={"likes": 500, "views": 2000})
    g = GradeResult(
        signal_id=sid,
        grade=grade,
        attention=80.0,
        propagation=70.0,
        conversation=60.0,
        originality=90.0,
        velocity_mult=1.0,
        coverage=1.0,
        basis="test",
    )
    return (s, g)


# --- engine registry --------------------------------------------------------


def test_list_engines_includes_facebook_elite_viral():
    assert "facebook-elite-viral" in engines.list_engines()
    assert "facebook-elite-viral" in studio.list_engines()


def test_engine_info_metadata():
    info = engines.engine_info("facebook-elite-viral")
    assert info["label"] == "Facebook Elite Viral Engine"
    assert "Facebook" in info["platforms"]
    assert "X" in info["platforms"]


def test_unknown_engine_raises_keyerror():
    with pytest.raises(KeyError):
        engines.engine_info("nope")
    with pytest.raises(KeyError):
        engines.load_engine_prompt("nope")


def test_engine_prompt_loads_verbatim():
    text = load_engine_prompt("facebook-elite-viral")
    assert text.startswith("FACEBOOK ELITE VIRAL ENGINE")
    for marker in (
        "FACEBOOK ELITE VIRAL ENGINE",
        "Content Lanes",
        "≥ 8.9",
        "Top 3 Selection",
        "Daily Strategy Block",
        "Begin generation immediately",
    ):
        assert marker in text


# --- brief generation with engine selection ---------------------------------


def test_brief_without_engine_is_backwards_compatible():
    graded = [_graded_pair()]
    pat = extract_patterns(graded, min_grade=GRADE_THRESHOLD)
    brief = generate_brief("comedy", graded, pat)
    assert isinstance(brief, ContentBrief)
    assert brief.engine is None
    text = render_brief(brief)
    assert "WAVE PULSE BRIEF — comedy" in text
    assert "ENGINE:" not in text


def test_brief_with_engine_embeds_spec_and_honesty_note():
    graded = [_graded_pair()]
    pat = extract_patterns(graded, min_grade=GRADE_THRESHOLD)
    brief = generate_brief("comedy", graded, pat, engine="facebook-elite-viral")
    assert brief.engine == "facebook-elite-viral"
    # honesty: the engine's self-gate is flagged as unmeasured
    assert any("self-scored" in r for r in brief.risk_flags)
    assert any("REWRITE" in r for r in brief.risk_flags)
    text = render_brief(brief)
    assert "ENGINE: Facebook Elite Viral Engine (facebook-elite-viral)" in text
    assert "FACEBOOK ELITE VIRAL ENGINE" in text
    assert "self-scored targets, not measured outcomes" in text


def test_generate_brief_rejects_unknown_engine():
    graded = [_graded_pair()]
    pat = extract_patterns(graded, min_grade=GRADE_THRESHOLD)
    with pytest.raises(KeyError):
        generate_brief("comedy", graded, pat, engine="bogus")


def test_save_brief_roundtrips_engine(monkeypatch, tmp_path):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    graded = [_graded_pair()]
    pat = extract_patterns(graded, min_grade=GRADE_THRESHOLD)
    brief = generate_brief("comedy", graded, pat, engine="facebook-elite-viral")
    bp = save_brief(brief, "engtest")
    payload = json.loads(bp.read_text(encoding="utf-8"))
    assert payload["engine"] == "facebook-elite-viral"
    assert payload["hypothesis"] is True


# --- CLI --------------------------------------------------------------------


def test_cli_engines_lists(capsys):
    from levi.demand.__main__ import _studio_main

    assert _studio_main(["engines"]) == 0
    out = capsys.readouterr().out
    assert "facebook-elite-viral" in out
    assert "Facebook Elite Viral Engine" in out


def test_cli_brief_with_engine(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    from levi.demand.__main__ import _studio_main

    save_signals([_sig(id="c1"), _sig(id="c2")], "clieng")
    rc = _studio_main(
        ["brief", "--name", "clieng", "--niche", "comedy",
         "--engine", "facebook-elite-viral"]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "WAVE PULSE BRIEF — comedy" in out
    assert "ENGINE: Facebook Elite Viral Engine" in out
    assert "saved:" in out


def test_cli_brief_rejects_bad_engine_choice():
    from levi.demand.__main__ import _studio_main

    with pytest.raises(SystemExit):
        _studio_main(["brief", "--name", "x", "--niche", "y", "--engine", "bogus"])
