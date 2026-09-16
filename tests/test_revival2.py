"""Hermetic tests for wave-2 revival top-ten (Part B): LEVI-native syntheses.

Modules: notes, ecco, interlisp, inferno, eros, linkbase, mumps, goap,
eurisko, groove.

Hermetic: no network (groove transports are local-only by design),
deterministic, all persistence under tmp_path. Stdlib only.
"""

import pytest

# NOTE: imported via the canonical ``levi.revival`` path (not
# ``core.levi.revival``) so the test shares module instances with the
# modules under test — eros/inferno import their siblings as
# ``from levi.revival import ...``, and telescript's HMAC secret is
# per-module-instance.
from levi.revival import (
    ecco,
    eros,
    eurisko,
    goap,
    groove,
    inferno,
    interlisp,
    linkbase,
    mumps,
    notes,
    telescript,
)


# ===========================================================================
# notes — LEVI's local-first memory sync
# ===========================================================================


def test_notes_bidirectional_sync(tmp_path):
    a = notes.Replica(str(tmp_path / "a"), "a")
    b = notes.Replica(str(tmp_path / "b"), "b")
    a.put("d1", "hello")
    rep = a.sync_with(b)
    assert rep["sent"] == ["d1"] and not rep["conflicts"]
    assert b.get("d1") == "hello"
    b.put("d2", "world")
    rep = b.sync_with(a)
    assert a.get("d2") == "world"


def test_notes_concurrent_edits_become_explicit_conflicts(tmp_path):
    a = notes.Replica(str(tmp_path / "a"), "a")
    b = notes.Replica(str(tmp_path / "b"), "b")
    a.put("d1", "v1")
    a.sync_with(b)
    a.put("d1", "A-edit")
    b.put("d1", "B-edit")
    rep = a.sync_with(b)
    assert rep["conflicts"] == ["d1"]
    assert len(a.conflicts()) == 1  # both versions preserved, human decides
    a.resolve_conflict("d1", "a")  # pick a side explicitly
    assert a.get("d1") == "A-edit"
    assert not a.conflicts()


def test_notes_tombstones_sync_deletion(tmp_path):
    a = notes.Replica(str(tmp_path / "a"), "a")
    b = notes.Replica(str(tmp_path / "b"), "b")
    a.put("d1", "x")
    a.sync_with(b)
    a.delete("d1")
    a.sync_with(b)
    assert "d1" not in b.list_docs()
    assert "d1" in b.list_docs(include_deleted=True)


def test_notes_self_sync_refused(tmp_path):
    a = notes.Replica(str(tmp_path / "a"), "a")
    with pytest.raises(ValueError):
        a.sync_with(a)


# ===========================================================================
# ecco — LEVI's outline-and-columns memory model
# ===========================================================================


def test_ecco_outline_and_typed_columns(tmp_path):
    s = ecco.Store(str(tmp_path / "e"))
    n = s.outline.add_node("Buy milk")
    s.add_folder("Groceries")
    f = s.folder("Groceries")
    f.define_column("qty", "number")
    s.file_node(n.node_id, "Groceries")
    f.set_cell(n.node_id, "qty", 3)
    assert f.get_cell(n.node_id, "qty") == 3


def test_ecco_multi_membership(tmp_path):
    s = ecco.Store(str(tmp_path / "e"))
    n = s.outline.add_node("Kyoto")
    s.add_folder("Japan 2027")
    s.add_folder("Decide")
    s.file_node(n.node_id, "Japan 2027")
    s.file_node(n.node_id, "Decide")  # one memory, many views
    assert s.view("Japan 2027")[0]["text"] == "Kyoto"
    assert s.view("Decide")[0]["text"] == "Kyoto"


def test_ecco_mistyped_values_rejected(tmp_path):
    s = ecco.Store(str(tmp_path / "e"))
    n = s.outline.add_node("x")
    s.add_folder("F")
    f = s.folder("F")
    f.define_column("qty", "number")
    s.file_node(n.node_id, "F")
    with pytest.raises(ecco.TypeMismatch):
        f.set_cell(n.node_id, "qty", "three")  # never silently coerced
    with pytest.raises(ecco.UnknownColumn):
        f.set_cell(n.node_id, "nope", 1)


def test_ecco_query_and_persistence(tmp_path):
    s = ecco.Store(str(tmp_path / "e"))
    n1 = s.outline.add_node("a")
    n2 = s.outline.add_node("b")
    s.add_folder("F")
    f = s.folder("F")
    f.define_column("qty", "number")
    s.file_node(n1.node_id, "F")
    s.file_node(n2.node_id, "F")
    f.set_cell(n1.node_id, "qty", 1)
    f.set_cell(n2.node_id, "qty", 5)
    assert len(s.query("F", lambda r: r["qty"] > 2)) == 1
    s.save()
    s2 = ecco.Store(str(tmp_path / "e"))
    assert len(s2.view("F")) == 2


# ===========================================================================
# interlisp — LEVI's self-instrumentation (DWIM + Masterscope)
# ===========================================================================


def test_dwim_corrects_and_reports():
    corrected, fixes = interlisp.correct_tokens(
        "delte teh note", ["delete", "the", "note"]
    )
    assert corrected == "delete the note"
    assert ("delte", "delete") in fixes  # corrections always reported


def test_dwim_refuses_wild_guesses():
    assert interlisp.dwim("zzzzzz", ["delete", "create"]) is None
    assert interlisp.dwim("", ["delete"]) is None


def test_masterscope_indexes_and_queries(tmp_path):
    (tmp_path / "m.py").write_text(
        "import os\ndef plan():\n    return guarded_call()\n"
        "def guarded_call():\n    return 1\n",
        encoding="utf-8",
    )
    ms = interlisp.Masterscope(tmp_path)
    assert ms.index_tree() == 1
    defs = ms.definitions("m")
    assert "plan" in defs["functions"]
    assert "os" in ms.imports_of("m")
    assert ms.references("guarded_call") == ["m.plan"]
    impact = ms.what_uses("m", "guarded_call")
    assert impact["referenced_by"] == ["m.plan"]


def test_masterscope_skips_broken_files(tmp_path):
    (tmp_path / "bad.py").write_text("def broken(:\n", encoding="utf-8")
    (tmp_path / "good.py").write_text("x = 1\n", encoding="utf-8")
    ms = interlisp.Masterscope(tmp_path)
    assert ms.index_tree() == 2
    assert len(ms.failed) == 1  # recorded, never half-ingested


# ===========================================================================
# inferno — LEVI's skill-confinement namespaces (built on plan9)
# ===========================================================================


def test_inferno_mount_call_unmount():
    with inferno.AppNamespace("app") as ns:
        ns.mount("echo", lambda t, p: ("echo", t, p))
        # payload round-trips through the 9P-style channel (tuples -> lists)
        assert ns.call("echo", "ping", {"x": 1}) == ["echo", "ping", {"x": 1}]
    with pytest.raises(inferno.UnknownService):
        ns.call("echo", "ping")  # unmounted on exit


def test_inferno_unmounted_names_denied():
    with inferno.AppNamespace("app") as ns:
        with pytest.raises(inferno.UnknownService):
            ns.call("email", "read")  # deny-closed: never mounted


def test_inferno_child_shadows_parent():
    with inferno.AppNamespace("app") as ns:
        ns.mount("svc", lambda t, p: "parent")
        child = ns.child("sub")
        assert child.call("svc", "x") == "parent"  # inherited up the stack
        child.mount("svc", lambda t, p: "child")
        assert child.call("svc", "x") == "child"  # inner shadows outer
        assert ns.call("svc", "x") == "parent"  # parent unaffected


def test_inferno_double_mount_refused():
    with inferno.AppNamespace("app") as ns:
        ns.mount("svc", lambda t, p: None)
        with pytest.raises(inferno.MountConflict):
            ns.mount("svc", lambda t, p: None)


# ===========================================================================
# eros — LEVI's least-privilege delegation (built on telescript)
# ===========================================================================


def _factory():
    root = telescript.issue("root", "root", ["flight.*", "cal.read"])
    return eros.Factory("f1", root)


def test_eros_mint_attenuates():
    f = _factory()
    token = f.mint("subagent", ["flight.search", "cal.read"])
    cap = telescript.verify(token)
    assert set(cap.actions) == {"flight.search", "cal.read"}


def test_eros_mint_beyond_root_refused():
    f = _factory()
    with pytest.raises(eros.AttenuationRefused):
        f.mint("subagent", ["email.read"])  # root never granted email


def test_eros_derive_and_seal():
    f = _factory()
    sub = f.mint("subagent", ["flight.search", "cal.read"])
    sub2 = f.derive(sub, "sub2", ["flight.search"])  # strictly weaker
    assert set(telescript.verify(sub2).actions) == {"flight.search"}
    with pytest.raises(eros.AttenuationRefused):
        f.derive(sub, "sub3", ["flight.book", "email.read"])
    f.seal(sub)
    assert f.is_sealed(sub)
    with pytest.raises(eros.SealedCapability):
        f.derive(sub, "sub3", ["flight.search"])  # invoke-only now


def test_eros_meter_bounds_invocations():
    f = _factory()
    token = f.mint("subagent", ["flight.search"])
    m = eros.Meter(token, 2)
    assert m.call("flight.search", lambda: "ok") == "ok"
    assert m.call("flight.search", lambda: "ok") == "ok"
    assert m.remaining == 0
    with pytest.raises(eros.MeterExhausted):
        m.call("flight.search", lambda: "ok")


def test_eros_invoke_checks_action():
    f = _factory()
    token = f.mint("subagent", ["flight.search"])
    assert eros.invoke(token, "flight.search", lambda: 7) == 7
    with pytest.raises(telescript.CapabilityError):
        eros.invoke(token, "email.read", lambda: 7)


# ===========================================================================
# linkbase — LEVI's memory link layer
# ===========================================================================


def test_linkbase_bidirectional(tmp_path):
    lb = linkbase.LinkBase(str(tmp_path / "lb"))
    lb.register_doc("a", "A")
    lb.register_doc("b", "B")
    lb.add_link("a", "b", note="see also")
    assert lb.neighbors("b") == ["a"]  # traversable both ways
    assert lb.links_to("b")[0].note == "see also"


def test_linkbase_rename_auto_updates(tmp_path):
    lb = linkbase.LinkBase(str(tmp_path / "lb"))
    lb.register_doc("a")
    lb.register_doc("b")
    lb.add_link("a", "b")
    assert lb.rename_doc("b", "b2") == 1  # no dangling links
    assert lb.neighbors("b2") == ["a"]


def test_linkbase_delete_quarantines_never_drops(tmp_path):
    lb = linkbase.LinkBase(str(tmp_path / "lb"))
    lb.register_doc("a")
    lb.register_doc("b")
    lb.add_link("a", "b")
    quarantined = lb.delete_doc("a")
    assert len(quarantined) == 1
    assert lb.dangling()  # kept for repair, not silently dropped
    lb.register_doc("c")
    repaired = lb.repair_dangling(quarantined[0].link_id, "c")
    assert {repaired.src, repaired.dst} == {"b", "c"}


def test_linkbase_generic_links_scan(tmp_path):
    lb = linkbase.LinkBase(str(tmp_path / "lb"))
    lb.register_doc("glossary")
    lb.define_generic("LEVI", "glossary")
    hits = lb.scan_text("LEVI is great, LEVI!")
    assert hits[0]["target"] == "glossary"
    assert hits[0]["positions"] == [0, 15]  # every occurrence is a live link


def test_linkbase_self_links_and_unknown_docs_refused(tmp_path):
    lb = linkbase.LinkBase(str(tmp_path / "lb"))
    lb.register_doc("a")
    with pytest.raises(linkbase.LinkbaseError):
        lb.add_link("a", "a")
    with pytest.raises(linkbase.UnknownDocument):
        lb.add_link("a", "ghost")


# ===========================================================================
# mumps — LEVI's persistent-global substrate
# ===========================================================================


def test_mumps_set_get_survives_restart(tmp_path):
    g = mumps.Globals(str(tmp_path / "g"))
    g.set("person", "1960-05-01", "mom", "birthday")
    assert g.get("person", "mom", "birthday") == "1960-05-01"
    g2 = mumps.Globals(str(tmp_path / "g"))  # journal replay
    assert g2.get("person", "mom", "birthday") == "1960-05-01"
    g2.snapshot()
    g3 = mumps.Globals(str(tmp_path / "g"))  # snapshot reload
    assert g3.get("person", "mom", "birthday") == "1960-05-01"


def test_mumps_data_and_order(tmp_path):
    g = mumps.Globals(str(tmp_path / "g"))
    assert g.data("person", "nobody") == 0
    g.set("person", "x", "mom", "birthday")
    assert g.data("person", "mom") == 10  # descendants only
    g.set("person", "herself", "mom")
    assert g.data("person", "mom") == 11  # value AND descendants
    g.set("n", 1, 2)
    g.set("n", 2, 10)
    g.set("n", 3, "a")
    assert g.order("n") == 2  # numbers collate before strings
    assert g.order("n", 2) == 10
    assert g.order("n", "a") is None


def test_mumps_kill_removes_subtree(tmp_path):
    g = mumps.Globals(str(tmp_path / "g"))
    g.set("t", 1, "a", "b")
    g.set("t", 2, "a", "c")
    g.kill("t", "a")
    assert g.data("t", "a") == 0
    assert list(g.traverse("t")) == []


def test_mumps_non_jsonable_rejected(tmp_path):
    g = mumps.Globals(str(tmp_path / "g"))
    with pytest.raises(TypeError):
        g.set("t", object(), "a")  # must be JSON-serializable
    assert g.get("t", "missing", default="dflt") == "dflt"  # $GET never raises


# ===========================================================================
# goap — planning over LEVI's tool surface
# ===========================================================================


def _actions():
    return [
        goap.Action("get_key", effects={"has_key": True}),
        goap.Action(
            "open_door", preconditions={"has_key": True}, effects={"door_open": True}
        ),
        goap.Action(
            "walk_thru",
            preconditions={"door_open": True},
            effects={"inside": True},
            cost=2.0,
        ),
        goap.Action(
            "teleport",
            preconditions={"inside": True},
            effects={"inside": True},
            cost=99.0,
        ),
    ]


def test_goap_plans_cheapest_sequence():
    p = goap.plan({}, {"inside": True}, _actions())
    assert p == ["get_key", "open_door", "walk_thru"]


def test_goap_unreachable_goal_is_honest():
    with pytest.raises(goap.NoPlan):
        goap.plan({}, {"fly": True}, _actions())  # says so, not hallucinates


def test_goap_empty_plan_when_already_there():
    assert goap.plan({"inside": True}, {"inside": True}, _actions()) == []


def test_goap_replans_when_world_moves():
    pl = goap.Planner(_actions(), {"inside": True})
    pl.set_world({})
    assert pl.next_action() == "get_key"
    pl.mark_done("get_key", {"has_key": True})
    assert pl.next_action() == "open_door"
    pl.update_world({"has_key": False})  # the world moved
    assert pl.next_action() == "get_key"  # plan moved too
    assert pl.replans == 1


def test_goap_callable_preconditions():
    acts = [
        goap.Action(
            "go", preconditions=lambda w: w.get("ready"), effects={"done": True}
        )
    ]
    with pytest.raises(goap.NoPlan):
        goap.plan({}, {"done": True}, acts)
    assert goap.plan({"ready": True}, {"done": True}, acts) == ["go"]


# ===========================================================================
# eurisko — LEVI's heuristic discovery for the growth loop
# ===========================================================================


def _pool(seed=7):
    pool = eurisko.DiscoveryPool(
        judge=lambda prob, cand: 1.0 if cand == 42 else 0.0, seed=seed
    )
    pool.seed_heuristic(eurisko.Heuristic("const42", lambda p: 42))
    pool.seed_heuristic(eurisko.Heuristic("const0", lambda p: 0))
    return pool


def test_eurisko_credit_flows_to_winners():
    pool = _pool()
    pool.assigner.run_round(problem=None)
    board = dict((n, s) for n, s, _ in pool.assigner.leaderboard())
    assert board["const42"] > board["const0"]


def test_eurisko_meta_breeds_and_culls():
    pool = _pool()
    pool.add_meta(eurisko.MetaHeuristic("mut", kind="mutate"))
    out = pool.evolve(problem=None, generations=2)
    assert pool.assigner.rounds == 6
    assert out["leaderboard"][0][0] == "const42"  # the earner stays on top


def test_eurisko_no_judge_refused():
    pool = eurisko.DiscoveryPool(judge=None)
    pool.seed_heuristic(eurisko.Heuristic("h", lambda p: 1))
    with pytest.raises(eurisko.DiscoveryError):
        pool.assigner.run_round(problem=None)  # no judge, no scores


def test_eurisko_heuristic_starts_neutral():
    h = eurisko.Heuristic("new", lambda p: 0)
    assert h.score == 0.5  # prior: neutral, not dead


# ===========================================================================
# groove — LEVI's pairwise workspace sync (local-only)
# ===========================================================================


def test_groove_sync_fast_forwards(tmp_path):
    a = groove.Workspace("a", str(tmp_path / "a"))
    b = groove.Workspace("b", str(tmp_path / "b"))
    a.write("d1", "hello")
    eng = groove.SyncEngine()
    rep = eng.sync(a, b)
    assert rep["pushed"] == ["d1"]
    assert b.read("d1").content == "hello"


def test_groove_concurrent_edits_conflict_explicitly(tmp_path):
    a = groove.Workspace("a", str(tmp_path / "a"))
    b = groove.Workspace("b", str(tmp_path / "b"))
    a.write("d1", "v1")
    groove.SyncEngine().sync(a, b)
    a.write("d1", "from A")
    b.write("d1", "from B")
    rep = groove.SyncEngine().sync(a, b)
    assert rep["conflicts"] == ["d1"]  # never auto-merged
    assert len(a.conflicts()) == 1 and len(b.conflicts()) == 1


def test_groove_resolve_supersedes_honestly(tmp_path):
    a = groove.Workspace("a", str(tmp_path / "a"))
    b = groove.Workspace("b", str(tmp_path / "b"))
    a.write("d1", "v1")
    eng = groove.SyncEngine()
    eng.sync(a, b)
    a.write("d1", "from A")
    b.write("d1", "from B")
    eng.sync(a, b)
    w = a.resolve_conflict("d1", "merged", merged_content="both")
    assert w.content == "both"
    rep = eng.sync(a, b)
    assert b.read("d1").content == "both"  # resolution propagates
    assert not a.conflicts()


def test_groove_deletion_tombstone_syncs(tmp_path):
    a = groove.Workspace("a", str(tmp_path / "a"))
    b = groove.Workspace("b", str(tmp_path / "b"))
    a.write("d1", "v1")
    eng = groove.SyncEngine()
    eng.sync(a, b)
    a.delete("d1")
    eng.sync(a, b)
    assert b.read("d1").deleted  # the tombstone carries a version


def test_groove_version_vectors_dominate():
    assert groove.dominates({"a": 2}, {"a": 1})
    assert not groove.dominates({"a": 1}, {"b": 1})  # concurrent, not dominated
