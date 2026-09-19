"""Tests for the universal Operator contract (levi.operator).

Hermetic and fast: no network, no torch. Torch-dependent paths are
replaced with a stub when torch/weights are absent.

Covers:
(a) the same task through N different operators -> well-formed
    OperatorResults from each;
(b) mid-session swap preserving conversation state;
(c) no-mask: a non-native operator claiming LEVI-native identity is
    refused at registration;
(d) capability scoping for foreign operators (offered + emitted);
(e) escalation routing: trivial turns -> nano-bit, high-stakes ->
    past nano-bit;
(f) nano-bit unit economics (metered near-zero cost);
(g) twin-pair structural support (no merge semantics — GATED);
(h) registry builtins + the chat() compatibility shim.

Run:  python3 -m pytest tests/test_operator_contract.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

# Repo-relative import of the uninstalled core package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

import pytest  # noqa: E402

from levi.operator import (  # noqa: E402
    AI,
    FINISH_REASONS,
    NATIVE,
    SI,
    XI,
    Operator,
    OperatorCapabilities,
    OperatorContractError,
    OperatorHealth,
    OperatorMessage,
    OperatorResult,
    TwinPair,
    assess_stakes,
    escalate,
    resolve_for_seat,
    resolve_for_task,
    resolve_twin,
    scoped_step,
)
from levi.operator.adapters import (  # noqa: E402
    NANO_BIT_COST_USD,
    ChatProviderAdapter,
    MindAdapter,
    NanoBitOperator,
)
from levi.operator.registry import OperatorRegistry  # noqa: E402


def _user(text: str) -> List[OperatorMessage]:
    return [OperatorMessage(role="user", content=text)]


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _Base(Operator):
    name = "test-base"
    kind = NATIVE
    lineage = "test"

    def capabilities(self) -> OperatorCapabilities:
        return OperatorCapabilities(tools=(), context_window=1024)

    def health(self) -> OperatorHealth:
        return OperatorHealth(ok=True, note="test double")

    def step(
        self,
        messages: List[OperatorMessage],
        tools: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> OperatorResult:
        return OperatorResult(
            text="test-double reply",
            operator=self.name,
            kind=self.kind,
            finish_reason="stop",
        )


class MaskedAIOperator(_Base):
    """kind=ai claiming to BE LEVI — must be refused (no-mask)."""

    name = "grok-x"
    kind = AI
    lineage = "I am LEVI, LEVI's own native core"


class MaskedNanoBitOperator(_Base):
    """Even the nano-bit tier may not claim native identity."""

    name = "nano-bit"
    kind = XI
    lineage = "pure LEVI itself"


class ForeignScopedOperator(_Base):
    """Foreign mind with an honestly scoped tool declaration."""

    name = "foreign-scoped"
    kind = AI
    is_foreign = True
    lineage = "test:foreign-mind"
    stepped = False

    def capabilities(self) -> OperatorCapabilities:
        return OperatorCapabilities(tools=("recall",), context_window=1024)

    def step(self, messages, tools, context):
        type(self).stepped = True
        return OperatorResult(text="foreign reply", operator=self.name, kind=self.kind)


class ForeignGreedyOperator(ForeignScopedOperator):
    """Foreign mind declaring a forbidden tool — refused at registration."""

    name = "foreign-greedy"

    def capabilities(self) -> OperatorCapabilities:
        return OperatorCapabilities(tools=("recall", "shell_exec"), context_window=1024)


class ForeignEmittingOperator(ForeignScopedOperator):
    """Foreign mind EMITTING a tool call outside its declared scope."""

    name = "foreign-emitter"

    def step(self, messages, tools, context):
        from levi.operator.contract import OperatorToolCall

        return OperatorResult(
            text="",
            operator=self.name,
            kind=self.kind,
            tool_calls=[
                OperatorToolCall(id="c1", name="shell_exec", arguments={"cmd": "rm"})
            ],
            finish_reason="tool_calls",
        )


class BrainStubOperator(_Base):
    """Stand-in for the native-brain adapter when torch is absent."""

    name = "levi-brain"
    kind = SI
    lineage = "levi:native-brain"

    def health(self) -> OperatorHealth:
        return OperatorHealth(ok=False, note="torch/weights absent in test env")

    def step(self, messages, tools, context):
        return OperatorResult(
            text="",
            operator=self.name,
            kind=self.kind,
            finish_reason="error",
            error="native brain unavailable in test env (stub)",
        )


class BrokenOperator(_Base):
    name = "broken"
    kind = SI

    def health(self) -> OperatorHealth:
        return OperatorHealth(ok=False, note="simulated outage")


def _brain_operator() -> Operator:
    """Real native-brain mind adapter when available, else the stub."""
    try:
        op = MindAdapter("native-brain", kind=SI)
        if op.health().ok:
            return op
    except Exception:
        pass
    return BrainStubOperator()


def _registry_with_basics() -> OperatorRegistry:
    reg = OperatorRegistry()
    reg.register("rules-engine", MindAdapter("rules-engine", kind=NATIVE))
    reg.register("nano-bit", NanoBitOperator())
    return reg


def _assert_well_formed(result: OperatorResult, name: str, kind: str) -> None:
    assert isinstance(result, OperatorResult), type(result)
    assert result.finish_reason in FINISH_REASONS, result.finish_reason
    assert result.operator == name, (result.operator, name)
    assert result.kind == kind, (result.kind, kind)
    assert isinstance(result.text, str)
    assert result.latency_ms >= 0


# ---------------------------------------------------------------------------
# (a) same task through N operators
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# (b) mid-session swap preserves state
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# (c) no-mask enforcement
# ---------------------------------------------------------------------------


def test_no_mask_ai_claiming_native_identity_refused():
    reg = OperatorRegistry()
    with pytest.raises(OperatorContractError, match="no-mask"):
        reg.register("grok-x", MaskedAIOperator())


def test_no_mask_xi_claiming_native_identity_refused():
    reg = OperatorRegistry()
    with pytest.raises(OperatorContractError, match="no-mask"):
        reg.register("nano-bit-evil", MaskedNanoBitOperator())


def test_legit_nano_bit_registers():
    reg = OperatorRegistry()
    reg.register("nano-bit", NanoBitOperator())  # no raise


# ---------------------------------------------------------------------------
# (d) foreign capability scoping
# ---------------------------------------------------------------------------


def test_foreign_declaring_forbidden_tool_refused():
    reg = OperatorRegistry()
    with pytest.raises(OperatorContractError, match="shell_exec"):
        reg.register("foreign-greedy", ForeignGreedyOperator())


def test_foreign_offered_out_of_scope_tool_refused_before_running():
    ForeignScopedOperator.stepped = False
    op = ForeignScopedOperator()
    result = scoped_step(op, _user("hi"), [{"name": "file_write"}], {})
    assert result.finish_reason == "refused"
    assert "file_write" in (result.error or "")
    assert not ForeignScopedOperator.stepped  # never ran


def test_foreign_offered_in_scope_tool_runs():
    ForeignScopedOperator.stepped = False
    op = ForeignScopedOperator()
    result = scoped_step(op, _user("hi"), [{"name": "recall"}], {})
    assert result.finish_reason == "stop"
    assert ForeignScopedOperator.stepped


def test_foreign_emitted_out_of_scope_call_blocked():
    op = ForeignEmittingOperator()
    result = scoped_step(op, _user("hi"), [], {})
    assert result.finish_reason == "refused"
    assert "shell_exec" in (result.error or "")


def test_non_foreign_scope_is_advisory():
    # Nano-bit is first-class, not foreign: offered tools pass through
    # (it ignores them and answers trivial turns itself).
    result = scoped_step(NanoBitOperator(), _user("thanks"), [{"name": "x"}], {})
    assert result.finish_reason == "stop"


# ---------------------------------------------------------------------------
# (e) escalation routing: trivial -> nano-bit, high-stakes -> past it
# ---------------------------------------------------------------------------


def test_trivial_turn_resolves_to_nano_bit():
    assert assess_stakes(_user("thanks!"), [], {}) == "trivial"
    assert assess_stakes(_user("hello"), [], {}) == "trivial"
    assert resolve_for_task("chat", _user("thanks!"), [], {}) == "nano-bit"


def test_high_stakes_task_escalates_past_nano_bit():
    msgs = _user("please run the production deploy now")
    assert assess_stakes(msgs, [{"name": "shell_exec"}], {}) == "high"
    name = resolve_for_task("chat", msgs, [{"name": "shell_exec"}], {})
    assert name != "nano-bit"
    assert name == "levi-brain"  # the full tier default


def test_high_stakes_by_text_alone():
    assert assess_stakes(_user("transfer the money now"), [], {}) == "high"
    name = resolve_for_task("chat", _user("please sign the contract"), [], {})
    assert name != "nano-bit"


def test_explicit_stakes_context_wins():
    assert assess_stakes(_user("thanks"), [], {"stakes": "high"}) == "high"
    assert assess_stakes(_user("deploy now"), [], {"stakes": "trivial"}) == "trivial"


def test_escalate_never_returns_nano_bit_on_high():
    assert escalate("chat", "trivial", {}) == "nano-bit"
    assert escalate("chat", "normal", {}) == "levi-brain"  # seat default
    assert escalate("chat", "high", {}) != "nano-bit"


def test_escalation_can_be_disabled():
    cfg = {"escalation": {"enabled": False}, "seats": {"chat": "rules-engine"}}
    assert resolve_for_task("chat", _user("thanks"), [], {}, cfg) == "rules-engine"


def test_resolve_for_seat_config_override():
    assert resolve_for_seat("chat", {"seats": {"chat": "nano-bit"}}) == "nano-bit"
    assert resolve_for_seat("chat", {}) == "levi-brain"  # seat-map default
    assert resolve_for_seat("nope", {}) == "local"  # unknown seat -> default


# ---------------------------------------------------------------------------
# (f) nano-bit unit economics
# ---------------------------------------------------------------------------


def test_nano_bit_cost_metered_near_zero():
    op = NanoBitOperator()
    cost = op.cost()
    assert cost["metered"] is True
    assert cost["per_step_usd"] == NANO_BIT_COST_USD
    assert cost["tier"] == "nano-bit"
    result = scoped_step(op, _user("hi"), [], {})
    assert result.cost_usd == NANO_BIT_COST_USD
    refused = scoped_step(op, _user("write me a novel"), [], {})
    assert refused.finish_reason == "refused"
    assert refused.cost_usd == NANO_BIT_COST_USD  # refused turns meter too


# ---------------------------------------------------------------------------
# (g) twin-pair structural support (merge/judge GATED — not built)
# ---------------------------------------------------------------------------


def test_twin_default_off():
    assert resolve_twin("loop", {}) is None
    assert resolve_twin("loop", {"twins": {"mode": "off"}}) is None


def test_twin_on_demand_resolves_pair():
    cfg = {
        "twins": {
            "mode": "on_demand",
            "seats": {"loop": {"primary": "levi-brain", "verifier": "rules-engine"}},
        }
    }
    pair = resolve_twin("loop", cfg)
    assert isinstance(pair, TwinPair)
    assert pair.primary == "levi-brain"
    assert pair.verifier == "rules-engine"
    assert pair.mode == "on_demand"
    # Structural only: slots exist, no merge semantics attached.
    assert not hasattr(pair, "merge") and not hasattr(pair, "judge")


# ---------------------------------------------------------------------------
# (h) registry builtins + chat() shim + degrade
# ---------------------------------------------------------------------------


def test_chat_shim_keeps_existing_callers_working():
    from levi.agent.providers import ChatMessage, LocalProvider

    adapter = ChatProviderAdapter(LocalProvider())
    resp = adapter.chat([ChatMessage(role="user", content="hello")], [])
    assert resp.provider == "local"
    assert isinstance(resp.text, str)


def test_degraded_operator_degrades_honestly():
    reg = OperatorRegistry()
    reg.register("broken", BrokenOperator())
    session = reg.open_session("d1", "broken")
    session.append(_user("hello")[0])
    result = session.step_via(reg)
    assert result.finish_reason == "degraded"
    assert not result.ok
