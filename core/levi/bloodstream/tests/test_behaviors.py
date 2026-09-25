"""interrogation ⊥ no_hero — at most one special behavior per turn.

The two behaviors are structurally distinct and must never collapse into
each other in one turn. On a (misconfigured) both-flags persona,
interrogation takes precedence and the conflict is recorded in the trace —
never mixed, never silent.
"""

from levi.persona.lattice import Persona

from levi.bloodstream.stages import BehaviorKind, RouteKind
from levi.bloodstream.turn import run_turn


def test_interrogation_persona(ctx_for):
    ctx = ctx_for(persona_id="interrogation")
    result = run_turn("why is the sky blue", ctx)
    assert result.behavior is BehaviorKind.INTERROGATION
    assert result.route is RouteKind.SPECIAL


def test_no_hero_persona(ctx_for):
    ctx = ctx_for(persona_id="no_hero")
    result = run_turn("why is the sky blue", ctx)
    assert result.behavior is BehaviorKind.NO_HERO
    assert result.route is RouteKind.SPECIAL


def test_normal_persona_has_no_special_behavior(ctx):
    result = run_turn("why is the sky blue", ctx)
    assert result.behavior is BehaviorKind.NONE
    assert result.route is RouteKind.MODEL


def test_conflict_both_flags_interrogation_wins_and_is_recorded(ctx_for, monkeypatch):
    conflict = Persona(
        id="conflict",
        display_name="Conflict",
        description="test persona with both flags set",
        reasoning_bias="test",
        communication_style="test",
        requires_explicit_answer_request=True,
        no_hero_mode=True,
    )

    class StubLattice:
        def __init__(self, *args, **kwargs):
            pass

        def set_active(self, persona_id):
            return True

        def current(self):
            return conflict

    monkeypatch.setattr("levi.bloodstream.turn.PersonaLattice", StubLattice)
    result = run_turn("why is the sky blue", ctx_for())
    assert result.behavior is BehaviorKind.INTERROGATION
    assert result.behavior is not BehaviorKind.NO_HERO
    persona_stage = next(s for s in result.stages if s.stage == "persona")
    assert persona_stage.detail["behavior_conflict"] is True
    assert (
        persona_stage.detail["conflict_resolution"] == "interrogation takes precedence"
    )


def test_sequential_turns_keep_behaviors_separate(ctx_for):
    r1 = run_turn("why is the sky blue", ctx_for(persona_id="interrogation"))
    r2 = run_turn("why is the sky blue", ctx_for(persona_id="no_hero"))
    assert r1.behavior is BehaviorKind.INTERROGATION
    assert r2.behavior is BehaviorKind.NO_HERO
