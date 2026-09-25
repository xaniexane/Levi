"""Tests for revival batch B04 — cognition engines 1.

microworld, scripttalk, strips, rete, activation, microtheory,
framebench, metactl. Each module gets >=3 meaningful tests against its
real mechanism, on toy inputs.
"""

import json

import pytest

from levi.revival import activation as act_mod
from levi.revival import framebench as fb_mod
from levi.revival import metactl as mc_mod
from levi.revival import microworld as mw_mod
from levi.revival import microtheory as mt_mod
from levi.revival import rete as rete_mod
from levi.revival import scripttalk as st_mod
from levi.revival import strips as stp_mod


# ----------------------------------------------------------------------
# microworld — grounded blocks world
# ----------------------------------------------------------------------


def test_microworld_move_and_stack_ground_words():
    w = mw_mod.Microworld()
    w.ask("move A onto B")
    w.ask("stack C on A")
    assert w.support("A") == "B"
    assert w.support("C") == "A"
    assert w.support("B") == "table"
    desc = w.describe()
    assert "A (red) on B" in desc


def test_microworld_what_did_you_do_answers_from_history():
    w = mw_mod.Microworld()
    w.ask("pick up D")
    w.ask("put D on the table")
    telling = w.ask("what did you do")
    assert "picked up D" in telling
    assert "put D" in telling
    assert len(w.history()) == 2
    assert w.history()[0].op == "pick"


def test_microworld_ungroundable_words_raise_honestly():
    w = mw_mod.Microworld()
    with pytest.raises(mw_mod.GroundError):
        w.ask("move Z onto B")  # no such block
    with pytest.raises(mw_mod.GroundError):
        w.ask("teleport A onto B")  # no such verb
    with pytest.raises(mw_mod.GroundError):
        w.ask("move A onto B onto C")  # malformed


def test_microworld_failed_move_is_atomic():
    w = mw_mod.Microworld()
    w.ask("move A onto B")  # B now occupied
    with pytest.raises(mw_mod.GroundError):
        w.ask("move C onto B")  # B not clear
    assert w.support("C") == "table"  # restored, not left dangling
    assert w.holding() is None


def test_microworld_origin_tag():
    assert mw_mod.ORIGIN == "levi-revival/microworld"


# ----------------------------------------------------------------------
# scripttalk — engine/script split
# ----------------------------------------------------------------------


def test_scripttalk_demo_greets_and_reflects():
    s = st_mod.demo()
    assert "bench is warm" in s.respond("hello")
    reply = s.respond("I want to build my kite")
    assert "kite" in reply  # captured group reassembled
    assert "your" in reply  # pronoun reflection flipped my -> your


def test_scripttalk_teach_adds_rule_at_runtime():
    s = st_mod.demo()
    s.respond("hello")  # turn 1 is the greeting by design; rules fire after
    note = s.teach("synth", "* synth *", ["Synths! Tell me about (2)."])
    assert "learned" in note
    reply = s.respond("I love my synth rig")
    assert reply.startswith("Synths! Tell me about")
    assert len(s.taught) == 1


def test_scripttalk_memory_stash_resurfaces():
    s = st_mod.demo()
    s.respond("hello")  # turn 1: greeting
    s.respond("I want to build a guitar")  # turn 2: stashed (remember)
    assert s.stashed(), "salient fragment should be stashed"
    s.respond("the weather is fine")  # turn 3
    surfacing = s.respond("ok")  # turn 4: resurface
    assert "Earlier you mentioned" in surfacing


def test_scripttalk_scripts_are_hot_swappable_data(tmp_path):
    path = tmp_path / "script.json"
    st_mod.ScriptTalk.save_script(st_mod.DEMO_SCRIPT, path)
    loaded = st_mod.ScriptTalk.load_script(path)
    assert loaded == json.loads(path.read_text())
    s2 = st_mod.ScriptTalk(loaded, name="reloaded")
    assert "bench is warm" in s2.respond("hello")
    s2.swap_script({"greetings": ["hi."], "keywords": {}}, name="tiny")
    assert s2.respond("hello") == "hi."


def test_scripttalk_origin_tag():
    assert st_mod.ORIGIN == "levi-revival/scripttalk"


# ----------------------------------------------------------------------
# strips — operators, goal-stack planner, MACROPs, PLANEX
# ----------------------------------------------------------------------


def _sussman():
    return stp_mod.Planner(stp_mod.blocks_operators())


def test_strips_plans_around_clobbered_subgoal():
    planner = _sussman()
    plan = planner.plan(stp_mod.sussman_start(), ["on(A,B)", "on(B,C)"])
    # simulate honestly: every step's preconditions must hold
    world = set(stp_mod.sussman_start())
    for op in plan.steps:
        assert op.applicable(world), f"{op.name} fired without preconditions"
        world = op.apply(world)
    assert "on(A,B)" in world and "on(B,C)" in world
    # the plan had to tear down on(A,B) (unstack) and rebuild it
    assert "unstack(A,B)" in plan.names()


def test_strips_no_plan_is_honest():
    planner = _sussman()
    with pytest.raises(stp_mod.NoPlan):
        planner.plan(stp_mod.sussman_start(), ["on(Zzz,Q)"])


def test_strips_macrop_generalizes_and_instantiates():
    planner = _sussman()
    plan = planner.plan(stp_mod.sussman_start(), ["on(A,B)", "on(B,C)"])
    macro = planner.learn_macro("tower2", plan)
    assert macro.name == "tower2"
    assert macro.from_plan == tuple(plan.names())
    assert macro.variables, "generalization should introduce variables"
    for fact in list(macro.pre) + list(macro.add) + list(macro.delete):
        assert "?v" in fact or "(" not in fact  # no raw constants left
    binding = {
        v: c for v, c in zip(macro.variables, ["X", "Y", "Z", "W"], strict=False)
    }
    ground = macro.instantiate(binding)
    for fact in list(ground.pre) + list(ground.add) + list(ground.delete):
        assert "?v" not in fact  # fully grounded again


def test_strips_planex_replans_on_failure():
    planner = _sussman()
    goals = ["on(A,B)", "on(B,C)"]
    plan = planner.plan(stp_mod.sussman_start(), goals)

    def fault(i, world):
        if i == len(plan.steps) - 1:
            # knock the tower down at the last step: A comes off B, so A
            # lands on the table and B is clear again (a fault that left
            # A in limbo would be unrecoverable by any planner)
            world.discard("on(A,B)")
            world.add("ontable(A)")
            world.add("clear(B)")
        return world

    world, events = stp_mod.Planex(planner).execute(
        plan, stp_mod.sussman_start(), goals, fault=fault
    )
    kinds = [e.kind for e in events]
    assert "add-fail" in kinds, "supervisor must notice the missing add-list"
    assert "replanned" in kinds, "supervisor must replan, not shrug"
    assert all(g in world for g in goals), "recovery must reach the goals"
    assert events[-1].kind == "done"


def test_strips_origin_tag():
    assert stp_mod.ORIGIN == "levi-revival/strips"


# ----------------------------------------------------------------------
# rete — incremental discrimination network
# ----------------------------------------------------------------------


def _red_on_net():
    r = rete_mod.Rete()
    r.add_rule("red-on", [("on", "?x", "?y"), ("color", "?x", "red")])
    return r


def test_rete_fires_only_on_genuine_matches():
    r = _red_on_net()
    r.assert_fact("on", "A", "B")
    r.assert_fact("color", "A", "blue")
    assert r.conflict_set() == [], "partial match must not reach terminal"
    r.assert_fact("on", "C", "D")
    r.assert_fact("color", "C", "red")
    conflicts = r.conflict_set()
    assert len(conflicts) == 1
    assert conflicts[0] == ("red-on", {"?x": "C", "?y": "D"})


def test_rete_retraction_removes_conflicts():
    r = _red_on_net()
    r.assert_fact("on", "A", "B")
    r.assert_fact("color", "A", "red")
    assert len(r.conflict_set()) == 1
    assert r.retract_fact("color", "A", "red") is True
    assert r.conflict_set() == [], "-token must drain the terminal"
    assert r.retract_fact("color", "A", "red") is False


def test_rete_conflict_resolution_is_pluggable():
    r = rete_mod.Rete()
    r.add_rule("specific", [("on", "?x", "?y"), ("color", "?x", "red")])
    r.add_rule("general", [("on", "?x", "?y")])
    r.assert_fact("on", "A", "B")
    r.assert_fact("color", "A", "red")
    assert len(r.conflict_set()) == 2
    picked = r.fire(rete_mod.SpecificityPolicy())
    assert picked[0] == "specific", "more conditions should win"
    # recency: newer fact's rule wins
    r2 = rete_mod.Rete()
    r2.add_rule("old", [("seen", "?x")])
    r2.add_rule("new", [("seen", "?x"), ("fresh", "?x")])
    r2.assert_fact("seen", "a")
    r2.assert_fact("seen", "b")
    r2.assert_fact("fresh", "b")
    picked2 = r2.fire(rete_mod.RecencyPolicy())
    assert picked2[0] == "new"


def test_rete_alpha_nodes_are_shared():
    r = rete_mod.Rete()
    r.add_rule("r1", [("color", "?x", "red")])
    r.add_rule("r2", [("color", "?y", "red"), ("on", "?y", "?z")])
    assert r.stats()["alpha_nodes"] == 2, "shared pattern => shared alpha"
    assert r.stats()["rules"] == 2


def test_rete_origin_tag():
    assert rete_mod.ORIGIN == "levi-revival/rete"


# ----------------------------------------------------------------------
# activation — ACT-R style memory
# ----------------------------------------------------------------------


def test_activation_rehearsed_chunk_wins_retrieval():
    d = act_mod.DeclarativeStore(threshold=-100.0)
    hot = d.encode("fact", {"q": "capital?", "a": "paris"}, at=0.0)
    d.encode("fact", {"q": "other?", "a": "rome"}, at=0.0)  # the cold rival
    for t in (1.0, 2.0, 3.0):
        d.rehearse(hot.id, t)
    chunk, a, latency = d.retrieve(at=10.0)
    assert chunk.id == hot.id, "recency x frequency must win"
    assert latency > 0


def test_activation_forgetting_emerges_without_deletion():
    # threshold sits between a fresh chunk's base level (ln(1) = 0 for a
    # single use one time-unit old) and a long-decayed one (ln(1e-3))
    d = act_mod.DeclarativeStore(threshold=-0.5)
    c = d.encode("fact", {"q": "old news"}, at=0.0)
    assert d.retrievable(c.id, at=1.0) is True
    assert d.retrievable(c.id, at=1e6) is False, "decay must sink it"
    assert d.retrieve(at=1e6) is None, "silence is forgetting"
    assert c.id in d.chunks, "nothing was ever deleted"


def test_activation_spreading_from_context():
    def fresh_store():
        d = act_mod.DeclarativeStore(threshold=-100.0, noise_scale=0.0)
        synth = d.encode("note", {"topic": "synth"}, at=0.0)
        garden = d.encode("note", {"topic": "garden"}, at=0.0)
        return d, synth, garden

    # each retrieval gets a pristine store: retrieval-as-use is the
    # documented mechanism, so re-querying the same store at the same
    # timestamp would (honestly) let the first winner dominate
    d, synth, _ = fresh_store()
    got, _, _ = d.retrieve(context={"topic": "synth"}, at=5.0)
    assert got.id == synth.id
    d2, _, garden2 = fresh_store()
    got2, _, _ = d2.retrieve(context={"topic": "garden"}, at=5.0)
    assert got2.id == garden2.id


def test_activation_score_has_quality_floor():
    d = act_mod.DeclarativeStore()
    c = d.encode("fact", {"q": "zzz-unrelated"}, at=0.0)
    s = d.score(c, {"q": "capital of france", "__kind": "fact"}, at=1e6)
    assert s == 0.0, "below-floor blends must score zero"
    assert d.rank({"q": "capital of france", "__kind": "fact"}, at=1e6) == []


def test_activation_procedural_stays_separate():
    d = act_mod.DeclarativeStore(threshold=-100.0)
    d.encode("fact", {"q": "2+2", "a": "4"}, at=0.0)
    pm = act_mod.ProceduralMemory()
    pm.add_rule(
        "answer-math",
        condition=lambda buf: buf.get("need") == "answer",
        # the production consumes the need it serves, so it fires once
        action=lambda buf, dec, at: buf.update(
            {
                "said": dec.retrieve({"q": buf["q"]}, at=at)[0].slots["a"],
                "need": "answered",
            }
        ),
    )
    bufs = {"need": "answer", "q": "2+2"}
    trace = pm.run(bufs, d, at=5.0)
    assert trace == ["answer-math"]
    assert bufs["said"] == "4"
    assert pm.step({"need": "nap"}, d) is None


def test_activation_origin_tag():
    assert act_mod.ORIGIN == "levi-revival/activation"


# ----------------------------------------------------------------------
# microtheory — local contexts
# ----------------------------------------------------------------------


def _kb_with_birds():
    kb = mt_mod.KnowledgeBase()
    birds = kb.mt("birds")
    birds.tell(("isa", "tweety", "bird"))
    birds.tell_rule(
        ("can", "?x", "fly"), (("isa", "?x", "bird"),), name="birds-fly", default=True
    )
    penguins = kb.mt("penguins")
    penguins.tell(("isa", "tweety", "penguin"))
    penguins.tell_rule(
        ("cannot", "?x", "fly"),
        (("isa", "?x", "penguin"),),
        name="penguins-grounded",
        default=True,
    )
    return kb


def test_microtheory_contradictory_defaults_coexist():
    kb = _kb_with_birds()
    assert kb.ask(("can", "tweety", "fly"), "birds").fact == ("can", "tweety", "fly")
    assert kb.ask(("cannot", "tweety", "fly"), "penguins").fact == (
        "cannot",
        "tweety",
        "fly",
    )
    assert kb.ask(("cannot", "tweety", "fly"), "birds") is None
    assert kb.ask(("can", "tweety", "fly"), "penguins") is None


def test_microtheory_explanations_cite_sources():
    kb = _kb_with_birds()
    lines = kb.explain(("can", "tweety", "fly"), "birds")
    text = "\n".join(lines)
    assert "birds-fly" in text
    assert "mt:birds" in text
    assert "given in mt:birds" in text  # the isa fact's provenance


def test_microtheory_abduction_assumes_and_checks():
    kb = mt_mod.KnowledgeBase()
    mt = kb.mt("sky")
    mt.tell(("isa", "tweety", "animal"))  # tweety becomes a known constant
    mt.tell_rule(
        ("can", "?x", "fly"), (("isa", "?x", "bird"),), name="birds-fly", default=True
    )
    assert kb.ask(("can", "tweety", "fly"), "sky") is None
    sets = kb.abduce(("can", "tweety", "fly"), "sky", [("isa", "?x", "bird")])
    assert sets and sets[0] == [("isa", "tweety", "bird")]
    with mt.problem_store() as store:  # ephemeral: gone after the question
        store.assume(("isa", "tweety", "bird"))
        assert (
            kb.ask(("can", "tweety", "fly"), "sky", extra=store.assumptions) is not None
        )
    assert store.assumptions == set()
    assert kb.ask(("can", "tweety", "fly"), "sky") is None  # nothing leaked


def test_microtheory_forward_and_fast_paths():
    kb = _kb_with_birds()
    kb.mt("birds").tell(("subclass", "bird", "animal"))
    derived = kb.forward("birds")
    assert ("can", "tweety", "fly") in derived
    assert kb.subclass_walk("tweety", "birds") == {"bird", "animal"}


def test_microtheory_origin_tag():
    assert mt_mod.ORIGIN == "levi-revival/microtheory"


# ----------------------------------------------------------------------
# framebench — frames + rules on one bench
# ----------------------------------------------------------------------


def _car_bench():
    wb = fb_mod.Workbench()
    wb.frame("vehicle")
    wb.set_slot("vehicle", "wheels", 4)
    wb.frame("car", parents=("vehicle",))
    wb.set_slot("car", "fuel", "petrol")
    return wb


def test_framebench_inheritance_and_explain():
    wb = _car_bench()
    assert wb.get_slot("car", "wheels") == 4
    lines = wb.explain_slot("car", "wheels")
    assert any("inherited from vehicle" in ln for ln in lines)
    own = wb.explain_slot("car", "fuel")
    assert any("set directly" in ln for ln in own)


def test_framebench_if_needed_daemon_computes():
    wb = _car_bench()
    wb.add_daemon(
        "car",
        "range",
        "if_needed",
        lambda fr, slot: 500 if fr.slots.get("fuel") == "petrol" else 0,
    )
    assert wb.get_slot("car", "range") == 500
    assert any("if_needed" in ln for ln in wb.explain_slot("car", "range"))
    with pytest.raises(KeyError):
        wb.get_slot("car", "color")


def test_framebench_if_added_daemon_and_messages():
    wb = _car_bench()
    seen = []
    wb.add_daemon(
        "car", "fuel", "if_added", lambda fr, slot, val: seen.append(val) or "logged"
    )
    wb.def_method(
        "car",
        "describe",
        lambda fr: (
            f"a {fr.slots.get('fuel')} car on {fr.slots.get('wheels', '?')} wheels"
        ),
    )
    wb.set_slot("car", "fuel", "diesel")
    assert seen == ["diesel"]
    assert wb.send("car", "describe") == "a diesel car on ? wheels"
    with pytest.raises(KeyError):
        wb.send("car", "fly")


def test_framebench_forward_and_backward_rules_share_facts():
    wb = _car_bench()
    wb.assert_fact(("needs", "car", "fuel"))
    wb.add_rule(
        "fuel-supply",
        (("needs", "?x", "fuel"),),
        ("has", "?x", "fuel"),
        direction="forward",
    )
    derived = wb.forward()
    assert ("has", "car", "fuel") in derived
    wb.add_rule(
        "wheel-count",
        (("isa", "?x", "car"),),
        ("wheels", "?x", 4),
        direction="backward",
    )
    wb.assert_fact(("isa", "mycar", "car"))  # the individual, told plainly
    proof = wb.prove(("wheels", "mycar", 4))
    assert proof is not None and any("wheel-count" in ln for ln in proof)
    assert wb.prove(("wings", "mycar", 2)) is None
    assert "car" in wb.inspect()


def test_framebench_origin_tag():
    assert fb_mod.ORIGIN == "levi-revival/framebench"


# ----------------------------------------------------------------------
# metactl — meta-level control
# ----------------------------------------------------------------------


def _ctl():
    mc = mc_mod.MetaController()
    mc.object_rule(
        "arith",
        "double",
        lambda p: isinstance(p.get("n"), (int, float)),
        lambda p: (p.update(n=p["n"] * 2), "doubled"),
    )
    mc.object_rule(
        "guess",
        "bump",
        lambda p: p.get("n", 0) < 10,
        lambda p: (p.update(n=p["n"] + 1), "bumped"),
    )
    mc.meta_rule(
        "small-numbers", lambda p, m: p.get("n", 0) <= 100, ("disable", "arith")
    )
    mc.meta_rule(
        "big-numbers",
        lambda p, m: p.get("n", 0) > 100,
        ("disable", "guess"),
        ("strategy", "all_match"),
    )
    return mc


def test_metactl_meta_disables_group_per_problem():
    mc = _ctl()
    prob, trace = mc.solve({"n": 3}, goal=lambda p: p["n"] >= 10)
    assert prob["n"] >= 10
    decisions = trace.meta_decisions()
    assert any("disabled group 'arith'" in d for d in decisions)
    obj_steps = [ln for ln in trace.lines if ln.startswith("OBJ")]
    assert obj_steps and all("[guess]" in ln for ln in obj_steps)


def test_metactl_meta_switches_strategy():
    mc = _ctl()
    prob, trace = mc.solve({"n": 150}, goal=lambda p: p["n"] >= 300)
    assert prob["n"] >= 300
    assert any("strategy -> 'all_match'" in d for d in trace.meta_decisions())


def test_metactl_can_disable_a_single_rule():
    mc = mc_mod.MetaController()
    mc.object_rule(
        "guess",
        "bump",
        lambda p: p.get("n", 0) < 10,
        lambda p: (p.update(n=p["n"] + 1), "bumped"),
    )
    mc.meta_rule(
        "no-bumping", lambda p, m: p.get("frozen"), ("disable_rule", ("guess", "bump"))
    )
    prob, trace = mc.solve({"n": 3, "frozen": True}, goal=lambda p: p["n"] >= 10)
    assert prob["n"] == 3, "the only rule was disabled by name"
    assert any("disabled rule 'bump'" in d for d in trace.meta_decisions())
    assert any("done: False" in ln for ln in trace.lines)


def test_metactl_origin_tag():
    assert mc_mod.ORIGIN == "levi-revival/metactl"
