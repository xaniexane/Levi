"""Tests for levi.revival batch B05 — cognition engines 2 (hermetic)."""

from __future__ import annotations

import pytest

from levi.revival import (
    alloy,
    teachback,
    substrata,
    viable,
    unify,
    deltasweep,
    protos,
    appdict,
)


# ---------------------------------------------------------------------------
# alloy — rules + frames + procedural attachments in one shell
# ---------------------------------------------------------------------------


def test_alloy_forward_chains_rules_over_slots():
    kb = alloy.demo()
    assert kb.frames["server"].read("alert", kb) == "thrashing"
    assert kb.frames["server"].read("escalate", kb) == "page-ops"
    assert kb.fired == ["thrashing", "page-ops"]


def test_alloy_if_needed_computes_lazily():
    kb = alloy.demo()
    assert kb.frames["mem"].read("pressure", kb) == pytest.approx(14.8 / 16.0)
    # cached after first read — the slot now holds data
    assert "pressure" in kb.frames["mem"].slots


def test_alloy_if_added_reacts_to_writes():
    kb = alloy.demo()
    assert kb.notes == ["ALERT: thrashing"]


def test_alloy_noop_writes_do_not_rearm_rules():
    kb = alloy.demo()
    fired_once = list(kb.fired)
    kb.run()  # second run: nothing new should fire
    assert kb.fired == fired_once


# ---------------------------------------------------------------------------
# teachback — entailment meshes + the teachback test
# ---------------------------------------------------------------------------


def test_teachback_complete_derivation_understands():
    report = teachback.demo()
    assert report.understands
    assert report.gaps == []


def test_teachback_missing_foundation_is_a_gap():
    mesh = teachback.demo_mesh()
    tb = teachback.Teachback(
        learner="l",
        topic="fractions",
        steps=[
            teachback.Step("division", ["sharing"]),
            teachback.Step("fractions", ["division", "sharing"]),
        ],
    )
    report = teachback.check(mesh, tb)
    assert not report.understands
    kinds = {g.kind for g in report.gaps}
    assert "missing-foundation" in kinds
    assert any("sharing" in g.detail for g in report.gaps)


def test_teachback_unsupported_leap_is_a_gap():
    mesh = teachback.demo_mesh()
    tb = teachback.Teachback(
        learner="l",
        topic="fractions",
        steps=[
            teachback.Step("sharing"),
            teachback.Step("division", ["sharing"]),
            teachback.Step("fractions", ["ratios"]),  # not a licensed derivation
        ],
    )
    report = teachback.check(mesh, tb)
    assert not report.understands
    assert any(g.kind == "unsupported-leap" for g in report.gaps)


def test_teachback_unknown_topic_is_a_gap():
    mesh = teachback.demo_mesh()
    tb = teachback.Teachback(
        learner="l",
        topic="fractions",
        steps=[
            teachback.Step("sharing"),
            teachback.Step("division", ["sharing"]),
            teachback.Step("fractions", ["division", "alchemy"]),
        ],
    )
    report = teachback.check(mesh, tb)
    assert any(g.kind == "unknown-topic" and "alchemy" in g.detail for g in report.gaps)


# ---------------------------------------------------------------------------
# substrata — layered reactive control, subsumption by wires
# ---------------------------------------------------------------------------


def test_substrata_higher_layer_subsumes_lower():
    stack = substrata.demo_stack()
    avoid = stack._by_name("avoid")
    avoid.sense(substrata.Reading("bump", 1.0))
    cmd = stack.tick()
    assert cmd is not None and str(cmd) == "wheels:reverse-turn"
    # avoid commanded even though wander also wanted the motors
    assert any(t.startswith("avoid ->") for t in stack.trace)
    assert any(t.startswith("wander ->") for t in stack.trace)


def test_substrata_bottom_layer_works_alone():
    stack = substrata.demo_stack()
    cmd = stack.tick()  # no stimuli: wander meanders
    assert cmd is not None and cmd.motor == "wheels"
    assert stack.trace[-1].startswith("wander ->")


def test_substrata_single_item_buffer_forbids_stale_input():
    layer = substrata.AvoidLayer()
    layer.sense(substrata.Reading("bump", 0.1))
    layer.sense(substrata.Reading("bump", 0.9))  # overwrites
    assert layer.take().value == pytest.approx(0.9)
    assert layer.take() is None  # consumed — nothing stale remains


def test_substrata_suppression_holds_for_ticks():
    stack = substrata.demo_stack()
    stack._by_name("avoid").sense(substrata.Reading("bump", 1.0))
    stack.tick()  # avoid fires, suppresses wander+seek
    wander = stack._by_name("wander")
    assert wander.suppressed_for > 0


# ---------------------------------------------------------------------------
# viable — five functions + audit channel, recursive diagnosis
# ---------------------------------------------------------------------------


def test_viable_healthy_org_has_no_gaps():
    org = viable.demo_healthy()
    assert viable.diagnose(org) == []
    assert viable.is_viable(org)


def test_viable_names_the_missing_function_and_path():
    org = viable.demo_broken()
    gaps = viable.diagnose(org)
    by_fn = {(g.path, g.function) for g in gaps}
    assert ("levi-lab", "coordination") in by_fn
    assert ("levi-lab", "audit") in by_fn
    assert not viable.is_viable(org)


def test_viable_recursion_checks_child_units():
    org = viable.demo_healthy()
    vision = org.children[0]
    vision.functions["intelligence"] = None
    gaps = viable.diagnose(org)
    assert any(
        g.path == "levi-lab/vision-team" and g.function == "intelligence" for g in gaps
    )


def test_viable_rejects_unknown_function():
    with pytest.raises(ValueError):
        viable.Unit("x").set("telepathy", "nobody")


# ---------------------------------------------------------------------------
# unify — terms, occurs-check, backtracking, first-arg indexing
# ---------------------------------------------------------------------------


def test_unify_facts_answer_queries():
    e = unify.demo_kb()
    sols = e.query("?- parent(tom, Who).")
    assert sorted(s["Who"] for s in sols) == ["bob", "liz"]


def test_unify_recursive_rule_backtracks_all_solutions():
    e = unify.demo_kb()
    sols = e.query("?- ancestor(tom, Who).")
    assert sorted(s["Who"] for s in sols) == ["ann", "bob", "jim", "liz"]


def test_unify_occurs_check_rejects_cyclic_binding():
    e = unify.Engine()
    x = unify.V("X")
    assert e._unify(x, unify.T("f", [x]), {}, []) is False


def test_unify_ground_first_arg_dispatches_not_scans():
    e = unify.demo_kb()  # 4 facts + 2 rules = 6 clauses
    goal = unify._Parser("?- parent(tom, X).").query()[0]
    narrowed = e._candidates(goal, {})
    assert len(narrowed) < len(e.clauses)  # discriminator pruned the store
    # …while a variable first argument still sees every parent clause
    goal2 = unify._Parser("?- parent(Who, ann).").query()[0]
    assert len(e._candidates(goal2, {})) == 4  # all 4 parent/2 facts


def test_unify_no_solution_yields_empty():
    e = unify.demo_kb()
    assert e.query("?- parent(zed, Who).") == []


# ---------------------------------------------------------------------------
# deltasweep — two-phase sweep learns XOR
# ---------------------------------------------------------------------------


def test_deltasweep_learns_xor():
    net, _ = deltasweep.demo(epochs=8000)
    for x, y in deltasweep.XOR:
        assert net.predict(x)[0] == pytest.approx(y[0], abs=0.15)


def test_deltasweep_error_falls_over_training():
    net, history = deltasweep.demo(epochs=2000)
    assert history[0] > history[-1]
    assert history[-1] < 0.05


def test_deltasweep_forward_shapes_and_bounds():
    net = deltasweep.MLP([2, 4, 1], seed=7)
    acts = net.forward([0.0, 1.0])
    assert [len(a) for a in acts] == [2, 4, 1]
    # sigmoid outputs only — acts[0] is the raw input, not an activation
    assert all(0.0 < v < 1.0 for layer in acts[1:] for v in layer)


def test_deltasweep_weight_array_is_three_dimensional():
    net = deltasweep.MLP([2, 3, 1], seed=1)
    assert len(net.W) == 2
    assert len(net.W[0]) == 3 and len(net.W[0][0]) == 2
    assert len(net.W[1]) == 1 and len(net.W[1][0]) == 3


# ---------------------------------------------------------------------------
# protos — cloning, unified slots, parent chains
# ---------------------------------------------------------------------------


def test_protos_clone_inherits_and_overrides():
    w = protos.demo_world()
    assert w["cub"].get("legs") == 4
    assert w["cub"].get("kind") == "fox cub"
    assert w["cub"].call("describe") == "a fox cub with 4 legs"


def test_protos_slots_unify_data_and_behavior():
    w = protos.demo_world()
    assert w["fox"].get("energy") == 10  # data slot, pre-hunt
    assert "caught the critter" in w["fox"].call("hunt", w["critter"])
    assert w["fox"].get("energy") == 15  # data slot, mutated by hunt
    with pytest.raises(TypeError):
        w["fox"].call("energy")  # data is not behavior


def test_protos_clone_mutation_does_not_touch_parent():
    w = protos.demo_world()
    w["cub"].call("eat", w["berry"])
    assert w["cub"].get("energy") == 7
    assert w["critter"].get("energy") == 10


def test_protos_lineage_and_missing_slot():
    w = protos.demo_world()
    assert w["cub"].lineage() == ["cub", "fox", "critter"]
    with pytest.raises(AttributeError):
        w["cub"].get("nope")


# ---------------------------------------------------------------------------
# appdict — published dictionaries + validating dispatcher
# ---------------------------------------------------------------------------


def test_appdict_dictionary_is_machine_readable():
    d = appdict.make_dispatcher().apps["notes"].dictionary()
    assert d["app"] == "notes"
    assert set(d["nouns"]) == {"note"}
    assert set(d["verbs"]) == {"create", "list", "delete"}
    assert d["verbs"]["create"]["params"] == ["title", "body"]


def test_appdict_scripts_speak_nouns_and_verbs():
    d = appdict.make_dispatcher()
    note = d.run(
        {
            "app": "notes",
            "verb": "create",
            "noun": "note",
            "args": {"title": "levi", "body": "synthetic"},
        }
    )
    assert note["id"] == 1 and note["title"] == "levi"
    notes = d.run({"app": "notes", "verb": "list", "noun": "note", "args": {}})
    assert len(notes) == 1
    assert (
        d.run({"app": "notes", "verb": "delete", "noun": "note", "args": {"id": 1}})
        is True
    )


def test_appdict_timer_roundtrip():
    d = appdict.make_dispatcher()
    d.run({"app": "timer", "verb": "start", "noun": "timer", "args": {"name": "t"}})
    status = d.run(
        {"app": "timer", "verb": "status", "noun": "timer", "args": {"name": "t"}}
    )
    assert status["running"] is True and status["elapsed"] >= 0
    stopped = d.run(
        {"app": "timer", "verb": "stop", "noun": "timer", "args": {"name": "t"}}
    )
    assert stopped["running"] is False


def test_appdict_refuses_off_dictionary_commands():
    d = appdict.make_dispatcher()
    with pytest.raises(appdict.DictionaryError):
        d.run({"app": "notes", "verb": "launch", "noun": "note", "args": {}})
    with pytest.raises(appdict.DictionaryError):
        d.run(
            {
                "app": "notes",
                "verb": "create",
                "noun": "missile",
                "args": {"title": "x"},
            }
        )
    with pytest.raises(appdict.DictionaryError):
        d.run(
            {
                "app": "notes",
                "verb": "create",
                "noun": "note",
                "args": {"title": "x", "payload": "y"},
            }
        )
    with pytest.raises(appdict.DictionaryError):
        d.run({"app": "toaster", "verb": "toast", "noun": "bread", "args": {}})
