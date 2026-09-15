"""Stage ordering and route classification for the bloodstream turn."""
from levi.factory.pipeline import SoftwareFactory

from levi.bloodstream.stages import BehaviorKind, RouteKind
from levi.bloodstream.turn import run_turn

FULL_ORDER = ["companion_ei", "persona", "governor", "route", "policy",
              "memory", "trace"]
SPECIAL_ORDER = ["companion_ei", "persona", "memory", "trace"]


def test_model_route_exact_stage_order(ctx):
    result = run_turn("what is recursion in one sentence", ctx)
    assert result.ok
    assert result.route is RouteKind.MODEL
    assert result.stage_names() == FULL_ORDER
    # risk 1 → auto-approved → a verified receipt exists
    assert result.policy_receipt_id
    assert result.promotion_eligible
    policy_stage = next(s for s in result.stages if s.stage == "policy")
    assert policy_stage.decision == "executed"
    assert policy_stage.detail["auto_approved"] is True


def test_special_behavior_skips_governor_and_policy(ctx_for):
    ctx = ctx_for(persona_id="interrogation")
    result = run_turn("why is the sky blue", ctx)
    assert result.ok
    assert result.route is RouteKind.SPECIAL
    assert result.behavior is BehaviorKind.INTERROGATION
    assert result.stage_names() == SPECIAL_ORDER
    assert result.policy_receipt_id is None  # nothing consequential ran


def test_factory_route_is_gated_without_confirm(ctx, data_dir):
    result = run_turn("build me a todo app", ctx)
    assert result.route is RouteKind.FACTORY
    assert result.awaiting_permission is True
    assert result.policy_receipt_id is None
    assert result.stage_names() == FULL_ORDER
    # the factory executor must NOT have run
    assert SoftwareFactory(data_dir=data_dir / "factory").list() == []


def test_factory_route_executes_with_confirm(ctx_for, data_dir):
    ctx = ctx_for(confirm=lambda proposal: True)
    result = run_turn("build me a todo app", ctx)
    assert result.route is RouteKind.FACTORY
    assert result.awaiting_permission is False
    assert result.policy_receipt_id
    assert result.promotion_eligible
    projects = SoftwareFactory(data_dir=data_dir / "factory").list()
    assert len(projects) == 1


def test_organ_route_echo(ctx):
    result = run_turn("what if we painted the whole office green", ctx)
    assert result.ok
    assert result.route is RouteKind.ORGAN
    assert result.policy_receipt_id  # organs still walk the gate
    assert "echo" in result.reply.lower()


def test_organ_route_mandella(ctx):
    result = run_turn("should I take the job offer or stay put", ctx)
    assert result.ok
    assert result.route is RouteKind.ORGAN
    assert "mandella" in result.reply.lower()
