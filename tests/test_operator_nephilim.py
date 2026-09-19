"""Tests for the Nephilim grade fused operator (levi.operator.nephilim).

Hermetic and fast: stub members only, no network, no torch, stdlib only.

Covers:
(a) fusion of 2-3 stub operators -> ONE well-formed OperatorResult
    behind the universal contract (validate_operator passes);
(b) shared scratchpad: every member sees context["fusion_scratchpad"],
    namespaced writes land in the result note for auditability;
(c) provenance recorded in the note: which member contributed what,
    agreement ratio, synthesis notes, confidence;
(d) member disagreement is synthesized (contradiction flagged), never
    silently dropped;
(e) kind rule: never "native" unless every member is native;
(f) cost(): sum of metered member costs; health(): ok iff lead
    healthy, note lists every member; degrade() names the failed
    member;
(g) registry register/resolve/swap round-trip, resolvable by name
    from config ({"operator": "nephilim-prime"}).

Run:  python3 -m pytest tests/test_operator_nephilim.py -q
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Repo-relative import of the uninstalled core package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

import pytest  # noqa: E402

from levi.operator import (  # noqa: E402
    AI,
    NATIVE,
    SI,
    XI,
    Operator,
    OperatorCapabilities,
    OperatorContractError,
    OperatorHealth,
    OperatorMessage,
    OperatorResult,
    OperatorToolCall,
    validate_operator,
)
from levi.operator.nephilim import NephilimOperator, synthesize_patterns  # noqa: E402
from levi.operator.registry import OperatorRegistry, scoped_step  # noqa: E402


def _user(text: str) -> List[OperatorMessage]:
    return [OperatorMessage(role="user", content=text)]


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _StubMember(Operator):
    """Deterministic stub member for fusion tests."""

    def __init__(
        self,
        name: str,
        kind: str,
        text: str,
        *,
        healthy: bool = True,
        cost_usd: Optional[float] = None,
        scratch_writes: Optional[Dict[str, str]] = None,
        scratch_read_key: Optional[str] = None,
        tool_calls: Optional[List[OperatorToolCall]] = None,
        context_window: int = 2048,
    ) -> None:
        self.name = name
        self.kind = kind
        self.version = "0.0.1-test"
        self.lineage = "nephilim test double"
        self._text = text
        self._healthy = healthy
        self._cost_usd = cost_usd
        self._scratch_writes = dict(scratch_writes or {})
        self._scratch_read_key = scratch_read_key
        self._tool_calls = list(tool_calls or [])
        self._context_window = context_window

    def capabilities(self) -> OperatorCapabilities:
        return OperatorCapabilities(
            tools=("search",) if self._tool_calls else (),
            context_window=self._context_window,
        )

    def health(self) -> OperatorHealth:
        return OperatorHealth(
            ok=self._healthy,
            note="stub healthy" if self._healthy else "stub broken",
        )

    def step(
        self,
        messages: List[OperatorMessage],
        tools: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> OperatorResult:
        if not self._healthy:
            # Model real behavior: an unhealthy member's step does not
            # produce insight — it degrades honestly.
            return OperatorResult(
                text="",
                operator=self.name,
                kind=self.kind,
                finish_reason="degraded",
                error="stub broken (unhealthy member)",
            )
        scratch = context.get("fusion_scratchpad")
        if not isinstance(scratch, dict):
            scratch = {}
        seen: Dict[str, str] = {}
        for key, value in self._scratch_writes.items():
            scratch[f"{self.name}:{key}"] = value
            seen[key] = value
        readback = ""
        if self._scratch_read_key:
            readback = f" [saw {self._scratch_read_key}={scratch.get(self._scratch_read_key, 'MISSING')}]"
        return OperatorResult(
            text=self._text + readback,
            tool_calls=list(self._tool_calls),
            operator=self.name,
            kind=self.kind,
            finish_reason="stop",
            cost_usd=self._cost_usd,
        )

    def cost(self) -> Dict[str, Any]:
        if self._cost_usd is None:
            return {"metered": False}
        return {"metered": True, "total_usd": self._cost_usd}


def _failing_member(name: str, kind: str = SI) -> _StubMember:
    return _StubMember(name, kind, "", healthy=False)


# ---------------------------------------------------------------------------
# (a) one face behind the contract
# ---------------------------------------------------------------------------


def _three_members() -> List[_StubMember]:
    return [
        _StubMember(
            "stub-ai",
            AI,
            "Deploy the pricing model with elastic demand curves and seasonal adjustments.",
            cost_usd=0.010,
        ),
        _StubMember(
            "stub-si",
            SI,
            "The pricing model should use elastic demand curves; avoid seasonal overfitting.",
            cost_usd=0.004,
        ),
        _StubMember(
            "stub-xi",
            XI,
            "Pricing: keep it simple — demand curves, not seasonal noise.",
            cost_usd=0.0001,
        ),
    ]


def test_fusion_yields_one_well_formed_result():
    fused = NephilimOperator("nephilim-prime", _three_members())
    result = fused.step(_user("Set pricing for launch."), [], {})
    assert isinstance(result, OperatorResult)
    assert result.finish_reason == "stop"
    assert result.error is None
    assert result.ok
    # One face: a single text carrying the union of member insights.
    for name in ("stub-ai", "stub-si", "stub-xi"):
        assert name in result.text, f"member {name} insight missing from fused text"
    assert "Nephilim grade" in result.text


def test_fusion_passes_contract_validation():
    fused = NephilimOperator("nephilim-prime", _three_members())
    validate_operator(fused)  # raises on any violation
    fused.validate()


def test_fusion_rejects_bad_construction():
    with pytest.raises(ValueError):
        NephilimOperator("solo", [_StubMember("a", SI, "x")])
    with pytest.raises(ValueError):
        NephilimOperator("none", [])
    with pytest.raises(TypeError):
        NephilimOperator("mixed", [_StubMember("a", SI, "x"), "not-an-operator"])
    with pytest.raises(ValueError):
        NephilimOperator(
            "dupes",
            [_StubMember("same", SI, "x"), _StubMember("same", AI, "y")],
        )
    # Unknown lead name is a construction error, not a silent fallback.
    with pytest.raises(ValueError):
        NephilimOperator(
            "bad-lead",
            [_StubMember("a", SI, "x"), _StubMember("b", AI, "y")],
            lead="ghost",
        )


# ---------------------------------------------------------------------------
# (b) shared scratchpad
# ---------------------------------------------------------------------------


def test_shared_scratchpad_visible_to_all_members_and_note():
    writer = _StubMember(
        "writer", SI, "I wrote first.", scratch_writes={"plan": "fusion-plan-v1"}
    )
    reader = _StubMember(
        "reader",
        AI,
        "I read after.",
        scratch_read_key="writer:plan",
    )
    fused = NephilimOperator("nephilim-prime", [writer, reader])
    result = fused.step(_user("Coordinate."), [], {})
    # The reader saw the writer's namespaced key (constructor order).
    assert "fusion-plan-v1" in result.text
    note = json.loads(result.note)
    # The scratchpad is in the note for auditability.
    assert note["scratchpad"]["writer:plan"] == "fusion-plan-v1"


# ---------------------------------------------------------------------------
# (c) provenance in the note
# ---------------------------------------------------------------------------


def test_provenance_recorded_in_note():
    fused = NephilimOperator("nephilim-prime", _three_members(), lead="stub-si")
    result = fused.step(_user("Set pricing for launch."), [], {})
    note = json.loads(result.note)
    assert note["grade"] == "Nephilim grade"
    assert note["members"] == ["stub-ai", "stub-si", "stub-xi"]
    assert note["lead"] == "stub-si"
    assert note["ok_members"] == 3
    assert note["total_members"] == 3
    # Provenance: which member contributed what.
    by_name = {p["name"]: p for p in note["provenance"]}
    assert by_name["stub-ai"]["kind"] == AI
    assert by_name["stub-xi"]["ok"] is True
    assert by_name["stub-ai"]["text_len"] > 0
    # Agreement ratio + confidence derived from it.
    assert 0.0 <= note["synthesis"]["agreement_ratio"] <= 1.0
    assert note["synthesis"]["agreement_ratio"] > 0.0
    assert 0.0 <= note["confidence"] <= 1.0
    assert note["confidence_basis"].startswith("agreement_ratio")
    # Synthesis notes label the method as heuristic.
    assert "heuristic" in note["synthesis"]["method"]


def test_agreement_layer_records_cross_member_overlap():
    fused = NephilimOperator("nephilim-prime", _three_members())
    result = fused.step(_user("Set pricing for launch."), [], {})
    note = json.loads(result.note)
    agreement_terms = {a["term"] for a in note["synthesis"]["agreements"]}
    assert "pricing" in agreement_terms  # all three members say it
    assert "demand" in agreement_terms
    assert "seasonal" in agreement_terms


# ---------------------------------------------------------------------------
# (d) disagreement is synthesized, never silently dropped
# ---------------------------------------------------------------------------


def test_member_disagreement_flagged_as_contradiction():
    affirming = _StubMember(
        "affirmer", SI, "The launch window is optimal and the risk is low."
    )
    negating = _StubMember(
        "negater", AI, "The launch window is not optimal; the risk is not low."
    )
    fused = NephilimOperator("nephilim-prime", [affirming, negating])
    result = fused.step(_user("Should we launch?"), [], {})
    note = json.loads(result.note)
    contradictions = note["synthesis"]["contradictions"]
    assert contradictions, "expected at least one contradiction flag"
    flagged_terms = {c["term"] for c in contradictions}
    assert {"optimal", "risk"} <= flagged_terms
    # The negater is named on the flag — disagreement is not dropped.
    by_term = {c["term"]: c for c in contradictions}
    assert by_term["optimal"]["negated_by"] == ["negater"]
    assert by_term["optimal"]["affirmed_by"] == ["affirmer"]
    # And it surfaces in the fused TEXT too.
    assert "contradictions" in result.text
    assert "negater" in result.text
    # Honest label: flagged for review, never certain.
    assert "review before acting" in result.text


def test_novel_patterns_synthesize_different_phrasing():
    one = _StubMember("one", SI, "Cache the query results in streams.")
    two = _StubMember("two", AI, "Streaming query results through the cache.")
    texts = {"one": one.step([], [], {}).text, "two": two.step([], [], {}).text}
    patterns = synthesize_patterns(texts)
    novel = patterns["novel_patterns"]
    assert novel, "expected a novel-pattern cluster"
    by_stem = {n["stem"]: n for n in novel}
    # "streams" vs "streaming": same concept, different phrasing.
    assert "stream" in by_stem
    cluster = by_stem["stream"]
    assert set(cluster["forms"]) == {"streams", "streaming"}
    assert set(cluster["members"]) == {"one", "two"}
    assert "heuristic" in cluster["note"]


def test_failed_member_recorded_not_hidden():
    good = _StubMember("good", SI, "Reliable insight about caching.")
    bad = _failing_member("bad")
    fused = NephilimOperator("nephilim-prime", [good, bad])
    result = fused.step(_user("Tune the cache."), [], {})
    # The fusion still produces a fused face from the healthy member.
    assert result.ok
    assert "good" in result.text
    note = json.loads(result.note)
    by_name = {p["name"]: p for p in note["provenance"]}
    assert by_name["bad"]["ok"] is False
    assert note["ok_members"] == 1
    assert note["confidence"] == 0.0  # agreement * ok-fraction, one member down
    assert "no usable result" in result.text


# ---------------------------------------------------------------------------
# (e) the no-mask kind rule
# ---------------------------------------------------------------------------


def test_kind_never_native_unless_all_members_native():
    # Mixed team: kind follows the lead; a native lead over a mixed
    # team still never presents native.
    mixed = NephilimOperator(
        "nephilim-mixed",
        [_StubMember("n1", NATIVE, "rules say no."), _StubMember("a1", AI, "ai says yes.")],
        lead="n1",
    )
    assert mixed.kind == AI  # falls to the non-native member's kind
    mixed2 = NephilimOperator(
        "nephilim-mixed2",
        [_StubMember("n1", NATIVE, "rules say no."), _StubMember("a1", AI, "ai says yes.")],
        lead="a1",
    )
    assert mixed2.kind == AI
    # All-native fusion honestly reports native.
    native_team = NephilimOperator(
        "nephilim-native",
        [_StubMember("n1", NATIVE, "rules one."), _StubMember("n2", NATIVE, "rules two.")],
    )
    assert native_team.kind == NATIVE
    validate_operator(mixed)
    validate_operator(native_team)


def test_no_mask_enforced_on_fusion_registration():
    class MaskedMember(_StubMember):
        def __init__(self):
            super().__init__("masked", AI, "hello")
            self.lineage = "I am LEVI, pure LEVI itself"

    with pytest.raises(OperatorContractError):
        NephilimOperator("masked-fusion", [MaskedMember(), _StubMember("b", SI, "x")])


def test_lead_defaults_to_highest_capability_member():
    big = _StubMember("big", AI, "big mind", context_window=32768)
    small = _StubMember("small", XI, "small mind", context_window=512)
    fused = NephilimOperator("nephilim-prime", [small, big])  # order shouldn't matter
    assert fused.lead.name == "big"
    assert fused.kind == AI


# ---------------------------------------------------------------------------
# (f) cost, health, degrade
# ---------------------------------------------------------------------------


def test_cost_is_sum_of_metered_member_costs():
    fused = NephilimOperator("nephilim-prime", _three_members())
    reported = fused.cost()
    assert reported["metered"] is True
    assert reported["per_member"] == {
        "stub-ai": 0.010,
        "stub-si": 0.004,
        "stub-xi": 0.0001,
    }
    assert abs(reported["total_usd"] - 0.0141) < 1e-9
    # And the per-turn result cost too.
    result = fused.step(_user("Set pricing for launch."), [], {})
    assert abs((result.cost_usd or 0.0) - 0.0141) < 1e-9


def test_cost_unmetered_when_no_member_metered():
    fused = NephilimOperator(
        "nephilim-prime",
        [_StubMember("a", SI, "x"), _StubMember("b", AI, "y")],
    )
    assert fused.cost()["metered"] is False
    assert fused.cost()["total_usd"] is None
    result = fused.step(_user("hi"), [], {})
    assert result.cost_usd is None


def test_health_ok_iff_lead_healthy_and_names_everyone():
    good_lead = _StubMember("lead", AI, "leading")
    good_other = _StubMember("other", SI, "following")
    fused = NephilimOperator("nephilim-prime", [good_lead, good_other], lead="lead")
    h = fused.health()
    assert h.ok is True
    assert "lead" in h.note and "other" in h.note

    broken = NephilimOperator(
        "nephilim-broken", [_failing_member("lead"), good_other], lead="lead"
    )
    hb = broken.health()
    assert hb.ok is False
    assert "lead" in hb.note and "other" in hb.note

    # A sick non-lead member still shows in the note — never hidden.
    mixed = NephilimOperator(
        "nephilim-mixed-h", [good_lead, _failing_member("sick")], lead="lead"
    )
    hm = mixed.health()
    assert hm.ok is True  # lead is healthy...
    assert "sick" in hm.note and "UNHEALTHY" in hm.note


def test_degrade_names_the_failed_member():
    broken = NephilimOperator(
        "nephilim-broken",
        [_failing_member("lead"), _StubMember("other", SI, "x")],
        lead="lead",
    )
    degraded = broken.degrade()
    assert degraded.finish_reason == "degraded"
    assert not degraded.ok
    assert "lead" in (degraded.error or "")
    assert "Nephilim grade" in (degraded.error or "")


# ---------------------------------------------------------------------------
# (g) registry round-trip: register / resolve by name / swap
# ---------------------------------------------------------------------------


def test_registry_register_resolve_swap_round_trip():
    registry = OperatorRegistry()
    fused = NephilimOperator("nephilim-prime", _three_members())
    registry.register("nephilim-prime", fused)
    # Resolvable by name from config, like any operator.
    resolved = registry.resolve({"operator": "nephilim-prime"})
    assert resolved is fused
    assert registry.resolve("nephilim-prime") is fused
    # Runs a full turn through the registry's scoped step.
    result = scoped_step(resolved, _user("Set pricing for launch."), [], {})
    assert result.ok and "Nephilim grade" in result.text
    # Session round-trip with a swap: history survives the exchange.
    session = registry.open_session("s1", {"operator": "nephilim-prime"})
    session.append(_user("Set pricing for launch."))
    first = session.step_via(registry)
    assert first.ok
    solo = _StubMember("solo", SI, "plain solo answer")
    registry.register("solo", solo)
    registry.swap("s1", "solo")
    assert session.operator_name == "solo"
    assert session.context["swapped_from"] == "nephilim-prime"
    assert len(session.messages) >= 2  # user turn + fused reply preserved


def test_registry_refuses_masked_fusion():
    class MaskedFusion(NephilimOperator):
        def __init__(self):
            super().__init__(
                "masked-grade",
                [_StubMember("a", AI, "x"), _StubMember("b", SI, "y")],
            )
            self.lineage = "I am LEVI itself"

    registry = OperatorRegistry()
    with pytest.raises(OperatorContractError):
        registry.register("masked-grade", MaskedFusion())


def test_deep_nephilim_nesting_not_required_but_members_may_fuse():
    inner = NephilimOperator(
        "inner-grade",
        [_StubMember("ia", SI, "inner insight"), _StubMember("ib", XI, "inner note")],
    )
    outer = NephilimOperator(
        "outer-grade", [inner, _StubMember("oc", AI, "outer insight")]
    )
    result = outer.step(_user("Go deep."), [], {})
    assert result.ok
    assert "inner-grade" in result.text or "inner insight" in result.text
    validate_operator(outer)
