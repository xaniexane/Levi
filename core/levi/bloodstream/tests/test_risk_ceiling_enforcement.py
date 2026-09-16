"""The interpenetration risk-ceiling law, as an engine.

These tests PROVE the binding law:

1. ``effective_ceiling`` — low-risk + high-risk components inherit the HIGH
   ceiling; the strictest (maximum) always wins; unknown/unrated components
   default deny-closed to the highest caution.
2. ``run_composite_gated`` — the gate denies a composite when the presented
   authorization is below the inherited ceiling (with an explicit reason
   naming the ceiling and the component that raised it), and allows it when
   the authorization meets the ceiling.
"""

from levi.bloodstream.composites import effective_ceiling
from levi.bloodstream.gate import run_composite_gated
from levi.interop import risks
from levi.policy.gates import PolicyEngine, RiskLevel


class _Part:
    def __init__(self, **attrs):
        for k, v in attrs.items():
            setattr(self, k, v)


# ---------------------------------------------------------------------------
# effective_ceiling — the pure composition function
# ---------------------------------------------------------------------------


def test_low_plus_high_inherits_high():
    out = effective_ceiling(
        [
            {"name": "file_read", "risk": RiskLevel.LOW},
            {"name": "shell_exec", "risk": RiskLevel.HIGH},
        ]
    )
    assert out["ceiling"] is RiskLevel.HIGH
    assert out["contributions"]["file_read"] is RiskLevel.LOW
    assert out["contributions"]["shell_exec"] is RiskLevel.HIGH


def test_strictest_always_wins_regardless_of_order():
    levels = [RiskLevel.INFO, RiskLevel.LOW, RiskLevel.MODERATE, RiskLevel.CRITICAL]
    assert effective_ceiling(levels)["ceiling"] is RiskLevel.CRITICAL
    assert effective_ceiling(list(reversed(levels)))["ceiling"] is RiskLevel.CRITICAL
    assert effective_ceiling([RiskLevel.LOW, RiskLevel.LOW])["ceiling"] is RiskLevel.LOW


def test_mixed_component_forms():
    out = effective_ceiling(
        [
            "moderate",  # bare name string that IS a level name
            1,  # bare int
            {"module": "rag", "risk": "high"},  # mapping, module alias
            _Part(risk_level=2),  # attribute object: skill-style
            _Part(risk_ceiling=RiskLevel.CRITICAL),  # specialist-style
        ]
    )
    assert out["ceiling"] is RiskLevel.CRITICAL


def test_empty_components_have_info_ceiling():
    out = effective_ceiling([])
    assert out["ceiling"] is RiskLevel.INFO
    assert out["contributions"] == {}


def test_unknown_component_defaults_to_highest_caution_deny_closed():
    out = effective_ceiling(
        [
            {"name": "file_read", "risk": RiskLevel.LOW},
            {"name": "mystery_plugin"},  # unrated: no risk information at all
        ]
    )
    assert out["ceiling"] is risks.highest_caution()
    assert out["ceiling"] is RiskLevel.CRITICAL


def test_unparseable_risk_defaults_to_highest_caution():
    out = effective_ceiling(
        [
            {"name": "known", "risk": RiskLevel.LOW},
            {"name": "broken", "risk": "extreme"},  # not a real level
        ]
    )
    assert out["ceiling"] is RiskLevel.CRITICAL


def test_ceiling_ordering_comes_from_risks_single_source():
    # effective_ceiling must not carry its own copy of the rules: the ceiling
    # of every level pair equals risks.ceiling of the same pair.
    levels = [
        RiskLevel.INFO,
        RiskLevel.LOW,
        RiskLevel.MODERATE,
        RiskLevel.HIGH,
        RiskLevel.CRITICAL,
    ]
    for i, a in enumerate(levels):
        for b in levels[i:]:
            assert effective_ceiling([a, b])["ceiling"] is risks.ceiling([a, b])


# ---------------------------------------------------------------------------
# run_composite_gated — enforcement on the execution path
# ---------------------------------------------------------------------------


def _composite_args(**over):
    kwargs = dict(
        engine=PolicyEngine(),
        name="ops",
        components=[
            {"name": "skill:file_read", "risk": RiskLevel.LOW},
            {"name": "skill:shell_exec", "risk": RiskLevel.HIGH},
        ],
        description="ops composite",
        reason="test",
        execute=lambda: "did the thing",
        verify=lambda: True,
    )
    kwargs.update(over)
    return kwargs


def test_gate_denies_when_authorization_below_inherited_ceiling():
    called = []
    out = run_composite_gated(
        **_composite_args(
            authorization_level=RiskLevel.LOW,
            execute=lambda: called.append(True) or "x",
        )
    )
    assert out.approved is False
    assert out.executed is False
    assert out.receipt is None
    assert called == []  # nothing ever ran
    assert out.ceiling is RiskLevel.HIGH
    # the denial reason names the ceiling AND the component that raised it
    assert "HIGH" in out.error
    assert "skill:shell_exec" in out.error
    assert "LOW" in out.error  # and the insufficient authorization presented


def test_gate_allows_when_authorization_meets_inherited_ceiling():
    called = []
    out = run_composite_gated(
        **_composite_args(
            authorization_level=RiskLevel.HIGH,
            execute=lambda: called.append(True) or "x",
        )
    )
    assert out.approved is True
    assert out.executed is True
    assert out.verified is True
    assert out.receipt_id
    assert called == [True]
    assert out.ceiling is RiskLevel.HIGH
    # the proposal itself ran at the inherited ceiling's risk level
    assert out.proposal.risk_level is RiskLevel.HIGH


def test_gate_allows_when_authorization_exceeds_ceiling():
    out = run_composite_gated(**_composite_args(authorization_level=RiskLevel.CRITICAL))
    assert out.approved is True
    assert out.executed is True
    assert out.receipt_id


def test_gate_unknown_component_raises_ceiling_and_denies():
    # A mystery component defaults deny-closed to CRITICAL; a HIGH
    # authorization is no longer enough — the act must not run.
    called = []
    out = run_composite_gated(
        **_composite_args(
            components=[
                {"name": "skill:file_read", "risk": RiskLevel.LOW},
                {"name": "mystery_plugin"},  # unrated
            ],
            authorization_level=RiskLevel.HIGH,
            execute=lambda: called.append(True) or "x",
        )
    )
    assert out.ceiling is RiskLevel.CRITICAL
    assert out.approved is False
    assert out.executed is False
    assert called == []
    assert "mystery_plugin" in out.error
    assert "CRITICAL" in out.error


def test_gate_denied_outcome_still_goes_through_plan_and_preview():
    out = run_composite_gated(**_composite_args(authorization_level=RiskLevel.INFO))
    assert out.approved is False
    assert out.proposal.id  # a proposal was planned
    assert out.preview  # and previewed — the denial is auditable


def test_gate_low_risk_composite_auto_approves_under_engine_ceiling():
    # All-LOW composite: the engine's standing LOW ceiling is sufficient —
    # no explicit authorization needed.
    out = run_composite_gated(
        **_composite_args(
            components=[{"name": "skill:file_read", "risk": RiskLevel.LOW}],
        )
    )
    assert out.ceiling is RiskLevel.LOW
    assert out.approved is True
    assert out.executed is True
    assert out.receipt_id


def test_gate_human_channel_approves_at_inherited_ceiling():
    # No explicit authorization level: the engine's standing LOW ceiling is
    # below the inherited HIGH ceiling, so the human channel decides — and
    # the human sees the inherited ceiling in the proposal.
    seen = []
    out = run_composite_gated(
        **_composite_args(confirm=lambda p: seen.append(p) or True)
    )
    assert out.approved is True
    assert out.executed is True
    assert out.receipt_id
    assert seen and seen[0].id == out.proposal.id
    assert out.proposal.risk_level is RiskLevel.HIGH
    assert "HIGH" in seen[0].reason  # the ceiling is named for the human


def test_gate_high_composite_without_human_channel_awaits_permission():
    # No explicit authorization, no human channel: the inherited HIGH
    # ceiling exceeds the engine's standing ceiling — the act does not run.
    out = run_composite_gated(**_composite_args())
    assert out.awaiting_permission is True
    assert out.executed is False
    assert out.ceiling is RiskLevel.HIGH
    assert out.receipt is None


def test_gate_dry_run_never_executes_but_computes_ceiling():
    called = []
    out = run_composite_gated(
        **_composite_args(
            authorization_level=RiskLevel.HIGH,
            dry_run=True,
            execute=lambda: called.append(True) or "x",
        )
    )
    assert out.approved is True
    assert out.executed is False
    assert called == []
    assert out.ceiling is RiskLevel.HIGH
    assert out.receipt_id
