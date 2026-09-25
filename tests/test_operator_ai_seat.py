"""Tests for the AI seat (levi.operator.ai_brain) and the honest-boundary
law (levi.operator.honesty).

Ruling (Chauncey, 2026-09-22): "None — I'm fully training it." No
external AI provider — the ai seat is his own trained brain. The
honest-boundary law now means "can do now" vs. "needs more training."

Covered:

- contract validation for the ai operator (kind ai, his own, no-mask)
- training-state honesty (present-but-honest; nothing invented)
- degraded path: unrunnable brain degrades, never fakes, never raises
- healthy path via stub provider: honest envelope note rides along
- per-turn boundary declaration: can-do-now vs needs-more-training
- escalation routing: trivial -> nano-bit (XI-first); normal -> seat
  default (offline); high+depth -> ai seat when healthy
- fusion grade label honesty: AI+SI+XI only with an AI member seated
- no provider/key plumbing anywhere in the ai seat

Hermetic and fast: stdlib only. The real brain is never needed —
unrunnable-here IS the honest state under test.

Run:  python3 -m pytest tests/test_operator_ai_seat.py -q
"""

from __future__ import annotations

import pytest

from levi.agent.providers import ChatResponse
from levi.operator.ai_brain import AI_SEAT_NAME, AiBrainOperator
from levi.operator.contract import (
    AI,
    Operator,
    OperatorCapabilities,
    OperatorHealth,
    OperatorMessage,
    OperatorResult,
    claims_native_identity,
    validate_operator,
)
from levi.operator.honesty import (
    CAN_DO_NOW,
    HONEST_BOUNDARY_LAW,
    NEEDS_MORE_TRAINING,
    BoundaryDeclaration,
    declare_boundary,
    route_turn,
)
from levi.operator.legion import (
    LEGION_OPERATOR_NAMES,
    legion_manifest,
    register_legion_operators,
)
from levi.operator.nephilim import NephilimOperator, grade_label
from levi.operator.registry import OperatorRegistry


def _msgs(text: str):
    return [OperatorMessage(role="user", content=text)]


class _StubBrainProvider:
    """Test double for the native brain provider."""

    def __init__(self, available: bool = True, text: str = "stub brain reply"):
        self._available = available
        self._text = text

    def is_available(self) -> bool:
        return self._available

    def chat(self, messages, tools):
        return ChatResponse(text=self._text, provider="stub")


class _StubOperator(Operator):
    def __init__(self, name: str, kind: str):
        self._name = name
        self._kind = kind

    @property
    def name(self):
        return self._name

    @property
    def kind(self):
        return self._kind

    version = "0.0.1"
    lineage = "test double"
    is_foreign = False

    def capabilities(self) -> OperatorCapabilities:
        return OperatorCapabilities(
            tools=(), streaming=False, memory_access=False,
            context_window=128, tool_use_loop=False, notes="stub",
        )

    def health(self) -> OperatorHealth:
        return OperatorHealth(ok=True, note="stub healthy")

    def step(self, messages, tools, context) -> OperatorResult:
        return OperatorResult(
            text="stub", operator=self._name, kind=self._kind,
            finish_reason="stop",
        )


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------


def test_ai_seat_contract_validates():
    op = AiBrainOperator()
    validate_operator(op)
    assert op.name == AI_SEAT_NAME == "ai"
    assert op.kind == AI
    assert op.is_foreign is False  # his own brain — not foreign
    assert not claims_native_identity(op)


def test_ai_seat_never_wires_provider_keys():
    import pathlib

    src = pathlib.Path("core/levi/operator/ai_brain.py").read_text()
    for banned in (
        "LEVI_OPENAI_API_KEY",
        "LEVI_ANTHROPIC_API_KEY",
        "api_key",
        "API_KEY",
    ):
        assert banned not in src, f"ai seat must not plumb keys ({banned})"


# ---------------------------------------------------------------------------
# Training-state honesty
# ---------------------------------------------------------------------------


def test_training_state_is_present_but_honest(tmp_path):
    op = AiBrainOperator(weights_dir=str(tmp_path))  # no records here
    st = op.training_state()
    assert st["seat"] == "ai"
    assert st["architecture"] == "tiny-gpt"
    assert st["runnable"] is False
    assert st["why_not_runnable"]  # the reason is stated, not hidden
    assert st["records"] == {}
    assert "more training" in st["needs_more_training"].lower()
    # Nothing invented for missing records:
    assert st["params"] is None
    assert st["held_out_loss"] is None


def test_training_state_reads_real_records():
    op = AiBrainOperator()  # real weights dir; eval.json present locally
    st = op.training_state()
    # In this checkout the records exist (gitignored build artifacts);
    # if a future checkout lacks them, the operator must say so.
    if st["records"]:
        assert st["params"] == 3271168
        assert st["held_out_loss"] is not None
    assert isinstance(st["runnable"], bool)
    assert "Narrow envelope" in st["envelope_now"]


def test_health_declares_training_state():
    op = AiBrainOperator()
    h = op.health()
    # No torch in this env -> not runnable -> ok=False, honestly.
    assert h.ok is False
    assert "not runnable" in h.note
    assert "more training" in h.note.lower()


# ---------------------------------------------------------------------------
# step(): degraded path never fakes, never raises
# ---------------------------------------------------------------------------


def test_step_degraded_when_brain_unrunnable():
    op = AiBrainOperator(provider=_StubBrainProvider(available=False))
    res = op.step(_msgs("write an essay about grief"), [], {})
    assert res.finish_reason == "degraded"
    assert res.text == ""  # nothing faked
    assert "needs more training" in (res.error or "").lower()
    assert "ai seat" in (res.error or "")


def test_step_degraded_when_provider_raises():
    class _Boom:
        def is_available(self):
            return True

        def chat(self, messages, tools):
            raise RuntimeError("boom")

    op = AiBrainOperator(provider=_Boom())
    res = op.step(_msgs("hi"), [], {})  # must not raise
    assert res.finish_reason == "degraded"
    assert res.text == ""


def test_step_healthy_carries_envelope_note():
    op = AiBrainOperator(provider=_StubBrainProvider(text="hello there"))
    res = op.step(_msgs("hi"), [], {})
    assert res.finish_reason == "stop"
    assert res.text == "hello there"
    assert "his own model" in res.note
    assert "more training" in res.note.lower()


# ---------------------------------------------------------------------------
# Per-turn boundary declaration
# ---------------------------------------------------------------------------


def test_boundary_trivial_is_can_do_now():
    d = declare_boundary(_msgs("hi"), [], {}, ai_healthy=False)
    assert isinstance(d, BoundaryDeclaration)
    assert d.verdict == CAN_DO_NOW
    assert d.stakes == "trivial"
    assert d.law == HONEST_BOUNDARY_LAW


def test_boundary_depth_without_healthy_ai_needs_training():
    d = declare_boundary(
        _msgs("write a moving essay about grief and healing"),
        [], {}, ai_healthy=False,
    )
    assert d.verdict == NEEDS_MORE_TRAINING
    assert "needs more training" in d.reason.lower()
    assert "not faked" in d.reason.lower()


def test_boundary_depth_with_healthy_ai_is_can_do_now():
    d = declare_boundary(
        _msgs("write a moving essay about grief and healing"),
        [], {}, ai_healthy=True,
    )
    assert d.verdict == CAN_DO_NOW
    assert "ai seat" in d.reason


def test_boundary_normal_deterministic_is_can_do_now():
    d = declare_boundary(
        _msgs("list the files in the plan in order"), [], {}, ai_healthy=False
    )
    assert d.verdict == CAN_DO_NOW
    assert "offline" in d.reason.lower()


# ---------------------------------------------------------------------------
# Escalation routing
# ---------------------------------------------------------------------------


def _legion_registry():
    reg, manifest = register_legion_operators()
    assert not manifest["skipped"], manifest["skipped"]
    return reg


def test_route_trivial_goes_nano_bit_xi_first():
    rt = route_turn("agent.default", _msgs("thanks"), [], {}, _legion_registry())
    assert rt.operator_name == "nano-bit"
    assert rt.declaration.verdict == CAN_DO_NOW
    assert rt.declaration.routed_to == "nano-bit"
    assert rt.stakes == "trivial"


def test_route_normal_stays_offline_seat_default():
    rt = route_turn(
        "agent.default", _msgs("summarize the build plan from yesterday in order"),
        [], {}, _legion_registry(),
    )
    assert rt.operator_name == "local"  # agent.default seat, offline
    assert rt.declaration.verdict == CAN_DO_NOW
    assert rt.stakes == "normal"


def test_route_high_depth_with_healthy_ai_seat():
    reg = _legion_registry()
    reg.register("ai", AiBrainOperator(provider=_StubBrainProvider()), replace=True)
    rt = route_turn(
        "agent.default",
        _msgs("delete the production database and write an essay explaining why"),
        [], {}, reg,
    )
    assert rt.stakes == "high"
    assert rt.operator_name == "ai"
    assert rt.declaration.verdict == CAN_DO_NOW


def test_route_high_depth_without_healthy_ai_declares_honestly():
    reg = _legion_registry()  # ai seat present but unrunnable here
    rt = route_turn(
        "agent.default",
        _msgs("delete the production database and write an essay explaining why"),
        [], {}, reg,
    )
    assert rt.stakes == "high"
    assert rt.operator_name == "local"  # honest fallback, not faked
    assert rt.declaration.verdict == NEEDS_MORE_TRAINING
    assert rt.declaration.routed_to == "local"


def test_route_high_deterministic_stays_on_seat_operator():
    # High-stakes deterministic work does not need the trained brain;
    # the twin verifier (not the ai seat) is the safety mechanism.
    reg = _legion_registry()
    reg.register("ai", AiBrainOperator(provider=_StubBrainProvider()), replace=True)
    rt = route_turn(
        "agent.default", _msgs("delete the production database"), [], {}, reg
    )
    assert rt.stakes == "high"
    assert rt.operator_name == "local"
    assert rt.declaration.verdict == CAN_DO_NOW


# ---------------------------------------------------------------------------
# Fusion grade-label honesty
# ---------------------------------------------------------------------------


def test_grade_label_computed_from_members():
    ai = _StubOperator("ai", "ai")
    si = _StubOperator("s", "si")
    xi = _StubOperator("x", "xi")
    assert grade_label([ai, si, xi]) == "AI+SI+XI"
    assert grade_label([si, xi]) == "SI+XI"
    assert grade_label([xi]) == "XI"
    assert grade_label([si]) == "SI"


def test_fusion_label_matches_reality_with_ai_seated():
    reg = _legion_registry()
    fused = reg.resolve("nephilim-fused")
    assert isinstance(fused, NephilimOperator)
    assert "ai" in fused.member_names  # his own trained brain is the AI member
    assert fused.grade_label == "AI+SI+XI"
    assert "AI+SI+XI" in fused.lineage


def test_fusion_label_without_ai_member():
    fused = NephilimOperator(
        "test-fused",
        [_StubOperator("s", "si"), _StubOperator("x", "xi")],
    )
    assert fused.grade_label == "SI+XI"
    assert "SI+XI" in fused.lineage
    assert "AI+SI+XI" not in fused.lineage


# ---------------------------------------------------------------------------
# Legion placement
# ---------------------------------------------------------------------------


def test_ai_seat_on_levi():
    assert "ai" in LEGION_OPERATOR_NAMES
    reg = _legion_registry()
    op = reg.resolve("ai")
    assert isinstance(op, AiBrainOperator)
    assert op.kind == AI
    assert legion_manifest(reg)["ai"] is True


def test_no_provider_adapters_in_fusion_members():
    reg = _legion_registry()
    fused = reg.resolve("nephilim-fused")
    assert "openai" not in fused.member_names
    assert "anthropic" not in fused.member_names
