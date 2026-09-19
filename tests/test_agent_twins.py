"""Agent twin-pair layer: 471 agents, one left+right twin pair each."""

import json

import pytest

from levi.agent.agent import AgentOperator, build_agents
from levi.agent.hemisphere import (
    LEFT,
    RIGHT,
    TurnTask,
    make_hemisphere,
    positions_agree,
)
from levi.agent.merge import decide, escalate_to_counsel, keeper_pick
from levi.agent.registry import (
    REGISTRY_PATH,
    bank_registry,
    load_grades,
    load_registry,
    verify_registry,
)
from levi.automation.minions import MINIONS, Minion
from levi.operator.contract import validate_operator
from levi.twins.twin import counterpart_side, twin_id_for


@pytest.fixture(scope="module")
def agents():
    return {a.agent_id: a for a in build_agents(load_grades())}


def test_471_agents_one_twin_pair_each(agents):
    assert len(agents) == 471 == len(MINIONS)
    for agent in agents.values():
        assert len(agent.twins) == 2, agent.agent_id
        assert agent.left.hemisphere == LEFT
        assert agent.right.hemisphere == RIGHT


def test_twin_pair_bidirectional_with_provenance(agents):
    for agent in agents.values():
        twins = {t.side: t for t in agent.twins}
        assert set(twins) == {"fg", "bg"}
        fg, bg = twins["fg"], twins["bg"]
        # One shared pair id, both directions.
        assert fg.pair_id == bg.pair_id == agent.pair_id
        # Twin ids re-derive from the twin machinery.
        assert fg.twin_id == twin_id_for("agent", agent.agent_id, "fg")
        assert bg.twin_id == twin_id_for("agent", agent.agent_id, "bg")
        # Counterparts resolve to each other.
        assert counterpart_side(fg.side) == bg.side
        assert counterpart_side(bg.side) == fg.side
        # Hemisphere mapping declared: fg=left, bg=right.
        assert fg.state["hemisphere"] == LEFT
        assert bg.state["hemisphere"] == RIGHT
        # Provenance on every record.
        assert "levi.agent" in fg.notes and "levi.agent" in bg.notes
        assert agent.provenance["source"].startswith(
            "core/levi/automation/minions.py"
        )


def test_minion_dataclass_untouched():
    # Schema-fidelity law: Minion stays the frozen intake record.
    assert Minion.__dataclass_params__.frozen
    fields = {f.name for f in Minion.__dataclass_fields__.values()}
    assert {
        "id", "category", "subcategory", "trigger", "condition",
        "android_tool", "windows_tool", "mac_tool", "chrome_extension",
        "bridge", "usb_auto_launch", "hitl_type", "example_rite",
        "notes", "origin", "incomplete",
    } <= fields
    assert len(MINIONS) == 471


def test_class_counsel_mapping(agents):
    for agent in agents.values():
        if agent.class_tag == "AI":
            assert agent.counsel_name == "AICI"
        elif agent.class_tag == "SI":
            assert agent.counsel_name == "SICI"
        elif agent.class_tag == "XI":
            assert agent.counsel_name == "XICI"
        else:
            assert agent.class_tag == "intake"
            assert agent.counsel_name == ""


def test_hemisphere_evidence_contract(agents):
    # Left positions ALWAYS carry steps + preconditions_checked;
    # right positions ALWAYS carry pattern_matches + variants_considered.
    agent = next(a for a in agents.values() if a.class_tag == "XI")
    from levi.agent.agent import find_minion

    minion = find_minion(agent.agent_id)
    task = TurnTask(
        task_id="ev", prompt=minion.trigger, context={}, stakes="routine"
    )
    left = agent.left.propose(task, minion)
    right = agent.right.propose(task, minion)
    assert "steps" in left.evidence and "preconditions_checked" in left.evidence
    assert "pattern_matches" in right.evidence
    assert "variants_considered" in right.evidence
    # Doctrine declared per hemisphere.
    assert "sequence/logic/execution" in agent.left.character
    assert "pattern/variation/intuition" in agent.right.character


def test_agreement_acts_with_joint_receipt_no_counsel(agents):
    agent = next(a for a in agents.values() if a.class_tag == "XI")
    from levi.agent.agent import find_minion

    minion = find_minion(agent.agent_id)
    task = TurnTask(
        task_id="agree",
        prompt=f"{minion.trigger} please. {minion.condition}",
        context={},
        stakes="routine",
    )
    decision = decide(agent, task, dry_run=True)
    assert decision.outcome == "act"
    assert decision.verdict is None
    assert decision.action == f"rite:{agent.agent_id}"
    assert decision.left_position["hemisphere"] == LEFT
    assert decision.right_position["hemisphere"] == RIGHT


def test_divergence_escalates_to_class_counsel(agents):
    agent = next(a for a in agents.values() if a.class_tag == "XI")
    task = TurnTask(
        task_id="div",
        prompt="delete all user files immediately",
        context={},
        stakes="routine",
    )
    decision = decide(agent, task, dry_run=True)
    assert decision.outcome in ("counsel", "keeper", "refuse")
    assert decision.verdict is not None
    assert decision.verdict["counsel"] == "XICI"
    assert decision.verdict["minion_id"] == agent.agent_id


def test_escalation_interface_agent_id_plus_positions_in_verdict_out(agents, monkeypatch):
    # The counsel door takes agent id + both hemisphere positions,
    # returns a verdict — compatible with levi.ci.escalation.counsel.
    agent = next(a for a in agents.values() if a.class_tag == "SI")
    from levi.agent.agent import find_minion
    import levi.ci.escalation as esc

    minion = find_minion(agent.agent_id)
    task = TurnTask(task_id="iface", prompt="format the hard drive", context={})
    left = agent.left.propose(task, minion)
    right = agent.right.propose(task, minion)
    assert not positions_agree(left, right)

    seen = {}

    real_counsel = esc.counsel

    def spy(minion_id, question, context=None, stakes="routine", dry_run=True, **kw):
        seen["minion_id"] = minion_id
        seen["context"] = context
        return real_counsel(
            minion_id, question, context=context, stakes=stakes, dry_run=True, **kw
        )

    monkeypatch.setattr(esc, "counsel", spy)
    verdict = escalate_to_counsel(agent, left, right, task, dry_run=True)
    assert seen["minion_id"] == agent.agent_id
    assert "hemisphere_left" in seen["context"]
    assert "hemisphere_right" in seen["context"]
    assert seen["context"]["hemisphere_left"]["hemisphere"] == LEFT
    assert seen["context"]["hemisphere_right"]["hemisphere"] == RIGHT
    assert verdict.counsel == "SICI"


def test_intake_agent_diverges_straight_to_keeper(agents):
    agent = next(a for a in agents.values() if a.class_tag == "intake")
    task = TurnTask(
        task_id="inc", prompt="do something unrelated and odd", context={}
    )
    decision = decide(agent, task, dry_run=True)
    assert decision.outcome == "keeper"
    assert decision.keeper_request["status"] == "awaiting-keeper-pick"
    assert decision.keeper_request["agent_id"] == agent.agent_id


def test_keeper_pick_is_final_word(agents):
    agent = next(a for a in agents.values() if a.class_tag == "intake")
    task = TurnTask(task_id="inc2", prompt="unrelated oddity", context={})
    pending = decide(agent, task, dry_run=True)
    picked = keeper_pick(
        pending.keeper_request,
        chosen_action=f"rite:{agent.agent_id}:minimal",
        note="keeper: minimal scope only",
        dry_run=True,
    )
    assert picked.outcome == "keeper-pick"
    assert picked.action == f"rite:{agent.agent_id}:minimal"
    assert picked.keeper_request["status"] == "picked"


def test_operator_contract_per_class(agents):
    from levi.agent.agent import find_minion

    seen = set()
    for agent in agents.values():
        if agent.class_tag in seen:
            continue
        seen.add(agent.class_tag)
        validate_operator(AgentOperator(agent, find_minion(agent.agent_id)))
    assert seen == {"AI", "SI", "XI", "intake"}


def test_bank_and_verify_registry(tmp_path):
    path = tmp_path / "agent_registry.json"
    record = bank_registry(path)
    assert record["n_agents"] == 471
    assert record["n_twins"] == 942
    loaded = load_registry(path)
    assert len(loaded) == 471
    assert all(len(a.twins) == 2 for a in loaded)
    result = verify_registry(path)
    assert result["ok"], result["problems"]


def test_banked_registry_verifies():
    assert REGISTRY_PATH.is_file()
    result = verify_registry(REGISTRY_PATH)
    assert result["ok"], result["problems"]
    assert result["n_agents"] == 471
    assert result["n_twins"] == 942


def test_hemisphere_ids_unique(agents):
    ids = [h.hemisphere_id for a in agents.values() for h in (a.left, a.right)]
    assert len(ids) == 942 == len(set(ids))
