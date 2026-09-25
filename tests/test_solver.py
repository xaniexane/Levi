"""Hermetic tests for the sequential solver (7 steps + modes-as-lenses).

The solver is a pure function: no I/O, no policy access. Cognitive modes
are presentation lenses only — tests assert they never change the facts.
"""

import pytest

from levi.agent.solver import (
    SOLVER_STEPS,
    SOLVER_SKILLS,
    CognitiveMode,
    ModeStyler,
    get_template,
    solve,
    wants_solve,
)

STEP_TITLES = [
    "DEFINE",
    "DECOMPOSE",
    "PLAN",
    "EXECUTE",
    "CHECK",
    "INTEGRATE",
    "REFLECT",
]


def test_seven_steps_template():
    steps = get_template()
    assert len(steps) == 7
    assert [s.title for s in steps] == STEP_TITLES
    assert len(SOLVER_STEPS) == 7


def test_solve_marks_all_seven_steps():
    out = solve("migrate the schema")
    for title in STEP_TITLES:
        assert title in out
    assert "## Sequential Problem Solving" in out
    assert "migrate the schema" in out


def test_solve_rejects_blank():
    with pytest.raises(ValueError, match="must not be empty"):
        solve("  ")


def test_solve_truncates_long_problem():
    out = solve("x" * 900)
    assert "x" * 900 not in out


def test_wants_solve_true():
    assert wants_solve("solve this routing bug")
    assert wants_solve("walk me through the deploy")
    assert wants_solve("break it down for me")


def test_wants_solve_false():
    assert not wants_solve("how are you today")
    assert not wants_solve("")
    assert not wants_solve(None)  # type: ignore[arg-type]


def test_modes_are_lenses_not_facts():
    # Same problem, different modes: identical 7-step factual core.
    normal = solve("check the pipeline", mode="normal")
    adhd = solve("check the pipeline", mode="adhd")
    dream = solve("check the pipeline", mode="dream")
    for out in (normal, adhd, dream):
        for title in STEP_TITLES:
            assert title in out
    # Only presentation differs.
    assert adhd != normal
    assert dream != normal
    assert "ADHD lens" in adhd
    assert "Dream lens" in dream


def test_coerce_unknown_mode_to_normal():
    assert CognitiveMode.coerce("telepathy") is CognitiveMode.NORMAL
    assert CognitiveMode.coerce("adhd") is CognitiveMode.ADHD
    assert CognitiveMode("normal") is CognitiveMode.NORMAL


def test_mode_describe():
    for m in CognitiveMode:
        assert CognitiveMode(m).describe()


def test_mode_styler_never_alters_facts():
    styler = ModeStyler("hyperfocus")
    text = "The database holds 42 rows."
    out = styler.style(text)
    assert "42 rows" in out  # facts survive styling


def test_mode_styler_modes():
    assert "Focus lens" in ModeStyler("focus").style("x")
    assert "HyperFocus" in ModeStyler("hyperfocus").style("x")
    assert "ADHD lens" in ModeStyler("adhd").style("x")
    assert ModeStyler("nope").mode is CognitiveMode.NORMAL
    styler = ModeStyler("normal")
    assert styler.set("adhd") is CognitiveMode.ADHD
    assert styler.mode is CognitiveMode.ADHD


def test_solver_skills_registered():
    ids = {s.id for s in SOLVER_SKILLS}
    assert {"agent_solve", "agent_mode_style"} <= ids
    for s in SOLVER_SKILLS:
        assert s.risk_level.name == "INFO"
        assert s.requires_confirmation is False


def test_skill_solve_handler():
    h = next(s for s in SOLVER_SKILLS if s.id == "agent_solve").handler
    out = h({"problem": "fix the leak"})
    assert "DEFINE" in out
    assert "needs a problem statement" in h({})


def test_skill_style_handler():
    h = next(s for s in SOLVER_SKILLS if s.id == "agent_mode_style").handler
    assert "ADHD lens" in h({"mode": "adhd", "text": "a\n\nb"})
