"""Twin-behavior guard for the omega/levi/dweller SI-team workers + AI bridges.

Extends the item-9 guard contract beyond alpha (see tests/test_alpha_twin_guard.py):
the native SI cores share a module-level CORES singleton registry
(core/levi/si_team/si/__init__.py), so the load contract must be verified here —
repeated consults deterministic, no cross-call leakage, class-level rule sets
unmutated, fresh result dicts per call, AI bridges stateless.

Hermetic: stdlib only, no network, no torch, no weights shipped.
Verification only — zero source changes.
"""

from __future__ import annotations

import pytest

from levi.si_team import counsel
from levi.si_team.ai import bridge_label
from levi.si_team.ai import dweller as ai_dweller
from levi.si_team.ai import levi as ai_levi
from levi.si_team.ai import omega as ai_omega
from levi.si_team.si import get_core, list_cores

AI_MODULES = {
    "omega": ai_omega,
    "levi": ai_levi,
    "dweller": ai_dweller,
}

TASKS = {
    "omega": "judge this plan",
    "levi": "who are you",
    "dweller": "batch the labor",
}

FALLBACK_TASK = "xylophone quasar zebrafinch"


# ----------------------------------------------------------------------------
# Repeated calls: deterministic and task-dependent


@pytest.mark.parametrize("role", ["omega", "levi", "dweller"])
def test_core_reason_repeated_calls_deterministic(role):
    core = get_core(role)
    first = core.reason(TASKS[role])
    for _ in range(3):
        again = core.reason(TASKS[role])
        assert again["answer"] == first["answer"], role
        assert again["rule_tag"] == first["rule_tag"], role
        assert again["substrate_used"] == "rules-engine", role


@pytest.mark.parametrize("role", ["omega", "levi", "dweller"])
def test_core_reason_is_task_dependent(role):
    core = get_core(role)
    matched = core.reason(TASKS[role])
    fallback = core.reason(FALLBACK_TASK)
    assert matched["rule_tag"] != "fallback", role
    assert fallback["rule_tag"] == "fallback", role
    assert fallback["answer"] != matched["answer"], role
    assert f"[{role.upper()}]" in fallback["answer"], role


@pytest.mark.parametrize("role", ["omega", "levi", "dweller"])
def test_consult_receipts_repeat_exactly(role):
    first = counsel.consult(role, TASKS[role])
    second = counsel.consult(role, TASKS[role])
    assert first == second  # frozen dataclass: equality is the whole receipt
    assert first.answer


@pytest.mark.parametrize("role", ["omega", "levi", "dweller"])
def test_consult_receipts_are_fresh_objects(role):
    first = counsel.consult(role, TASKS[role])
    second = counsel.consult(role, TASKS[role])
    assert first is not second
    first.limits.append("mutation probe")
    assert "mutation probe" not in second.limits


# ----------------------------------------------------------------------------
# No cross-call leakage: answers stay inside their role


@pytest.mark.parametrize("role", ["omega", "levi", "dweller"])
def test_core_answer_never_claims_another_roles_voice(role):
    # Levi legitimately NAMES the crew (it routes to them); none may claim
    # to BE another role or answer in another role's labeled voice.
    others = [r for r in ("omega", "levi", "dweller") if r != role]
    core = get_core(role)
    answer = core.reason(TASKS[role])["answer"].lower()
    for other in others:
        assert f"i am {other}" not in answer, (role, other)
        assert f"[{other}]" not in answer, (role, other)


def test_rules_do_not_bleed_across_roles():
    # "batch" is a dweller rule keyword; omega must NOT fire a rule on it —
    # it must report its own honest fallback, not borrow another role's voice.
    omega = get_core("omega")
    result = omega.reason("batch the labor")
    assert result["rule_tag"] == "fallback"
    assert "[OMEGA]" in result["answer"]


@pytest.mark.parametrize("role", ["omega", "levi", "dweller"])
def test_core_singleton_survives_consults(role):
    before = get_core(role)
    counsel.consult(role, TASKS[role])
    assert get_core(role) is before
    assert list_cores() == ["levi", "alpha", "omega", "dweller"]


# ----------------------------------------------------------------------------
# Class-level rule sets unmutated by repeated calls


@pytest.mark.parametrize("role", ["omega", "levi", "dweller"])
def test_class_rules_unmutated_by_load(role):
    core = get_core(role)
    before = [(tuple(kw), fn.__name__) for kw, fn in core.rules]
    tasks = [TASKS[role], FALLBACK_TASK, "another probe", TASKS[role]]
    for _ in range(10):
        for task in tasks:
            core.reason(task)
            counsel.consult(role, task)
    after = [(tuple(kw), fn.__name__) for kw, fn in core.rules]
    assert after == before, role
    # class attribute itself: same list object, not swapped under us
    assert core.rules is type(core).rules, role


# ----------------------------------------------------------------------------
# Result dicts are fresh per call


@pytest.mark.parametrize("role", ["omega", "levi", "dweller"])
def test_result_dicts_independent_objects(role):
    core = get_core(role)
    first = core.reason(TASKS[role])
    second = core.reason(TASKS[role])
    assert first is not second
    first["limits"].append("mutation probe")
    first["answer"] = "rewritten"
    assert second["limits"] and "mutation probe" not in second["limits"]
    assert second["answer"] != "rewritten"
    # keys are the documented contract
    assert set(second) == {"answer", "substrate_used", "rule_tag", "limits"}


# ----------------------------------------------------------------------------
# Weights honesty per call (hermetic via LEVI_HOME)


@pytest.mark.parametrize("role", ["omega", "levi", "dweller"])
def test_missing_weights_reported_honestly(tmp_path, monkeypatch, role):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    core = get_core(role)
    result = core.reason(TASKS[role])
    assert core.weights_present() is False
    assert any("no SI weights yet" in limit for limit in result["limits"]), role


def test_present_weights_stops_the_missing_weight_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    core = get_core("dweller")
    weight_file = core.weights_dir() / "dummy.bin"
    weight_file.parent.mkdir(parents=True)
    weight_file.write_bytes(b"not-real-weights")
    assert core.weights_present() is True
    result = core.reason(TASKS["dweller"])
    assert not any("no SI weights yet" in limit for limit in result["limits"])


# ----------------------------------------------------------------------------
# AI bridges under load: stateless, labels stable


@pytest.mark.parametrize("role", ["omega", "levi", "dweller"])
def test_ai_bridge_label_stable(role):
    mod = AI_MODULES[role]
    first = mod.AI_BRIDGE_LABEL
    for _ in range(3):
        assert mod.AI_BRIDGE_LABEL == first == bridge_label(role)


@pytest.mark.parametrize("role", ["omega", "levi", "dweller"])
def test_mcp_tools_lists_are_fresh_per_call(role):
    mod = AI_MODULES[role]
    first = mod.to_mcp_tools()
    names = [t["name"] for t in first]
    assert names, role
    # mutate the returned list: the next call must be unaffected
    first.append({"name": "poison"})
    first[0]["description"] = "poison"
    second = mod.to_mcp_tools()
    assert [t["name"] for t in second] == names, role
    assert "poison" not in second[0]["description"], role
    assert "AI counterpart bridge" in second[0]["description"], role


@pytest.mark.parametrize("role", ["omega", "levi", "dweller"])
def test_chat_adapter_repeatable_and_independent(role):
    mod = AI_MODULES[role]
    adapter = mod.chat_adapter()
    request = adapter["build_request"]([{"role": "user", "content": "hello"}])
    again = adapter["build_request"]([{"role": "user", "content": "hello"}])
    assert again == request
    # parse one response, then another: no state carried over
    parsed = adapter["parse_response"](
        {"choices": [{"message": {"role": "assistant", "content": "one"}}]}
    )
    assert parsed["content"] == "one", role
    parsed2 = adapter["parse_response"](
        {"choices": [{"message": {"role": "assistant", "content": "two"}}]}
    )
    assert parsed2["content"] == "two", role
    assert parsed["content"] == "one", role


def test_ai_bridge_names_never_claim_the_si():
    for role, mod in AI_MODULES.items():
        text = mod.AI_BRIDGE_LABEL + " ".join(
            t["description"] for t in mod.to_mcp_tools()
        )
        assert "claims nothing" in text, role
        assert "SI core is authoritative" in text, role
