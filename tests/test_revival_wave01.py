"""Tests for revival wave 01 — typed links, liveness, presence, modeling,
live objects, minimal OS, contracts.

Seven original, from-scratch LEVI mechanisms. At least three meaningful
tests per module: construct, exercise the core mechanism, cover an edge.
"""

import pytest

from core.levi.revival import typed_links
from core.levi.revival import live_system
from core.levi.revival import presence_spaces
from core.levi.revival import category_tiles
from core.levi.revival import live_objects
from core.levi.revival import minimal_os
from core.levi.revival import contracts


# ---------------------------------------------------------------------------
# typed_links — relation algebra over typed links
# ---------------------------------------------------------------------------


def _arg_web():
    web = typed_links.LinkWeb()
    web.add_anchor("claim", "Levi runs local-first", kind="claim")
    web.add_anchor("ev1", "benchmark log", kind="evidence")
    web.add_anchor("ev2", "design doc", kind="evidence")
    web.add_anchor("obj", "cloud is cheaper", kind="claim")
    web.link("ev1", typed_links.SUPPORTS, "claim")
    web.link("ev2", typed_links.ELABORATES, "ev1")
    web.link("obj", typed_links.REFUTES, "claim")
    return web


def test_typed_links_rejects_unknown_relation_and_anchor():
    web = typed_links.LinkWeb()
    web.add_anchor("a", "A")
    with pytest.raises(typed_links.UnknownRelation):
        web.link("a", "vibes-with", "a")
    with pytest.raises(typed_links.UnknownAnchor):
        web.link("a", typed_links.SUPPORTS, "ghost")
    with pytest.raises(typed_links.DuplicateAnchor):
        web.add_anchor("a", "A again")


def test_typed_links_composition_derives_implied_support():
    web = _arg_web()
    derived = web.derive()
    implied = {(d.source, d.rel, d.target) for d in derived}
    # ev2 elaborates ev1, ev1 supports claim -> ev2 (indirectly) supports claim
    assert ("ev2", typed_links.SUPPORTS, "claim") in implied
    assert all(d.implied and d.rule for d in derived)


def test_typed_links_conflicts_and_cycles():
    web = _arg_web()
    # obj refutes claim while ev1 supports it — stance reads the tension.
    assert web.net_stance("obj", "claim") == "refutes"
    assert web.net_stance("ev1", "claim") == "supports"
    # A direct both-ways conflict is reported with its reason.
    web.add_anchor("x", "X")
    web.add_anchor("y", "Y")
    web.add_anchor("z", "Z")
    web.link("x", typed_links.SUPPORTS, "y")
    web.link("x", typed_links.REFUTES, "y")
    assert ("x", "y", "support and refutation both present") in web.conflicts()
    # So is a derived conflict: x supports z, z refutes y, yet x supports y.
    web.link("x", typed_links.SUPPORTS, "z")
    web.link("z", typed_links.REFUTES, "y")
    assert web.net_stance("x", "y") == "contested"
    assert ("x", "y", "support and refutation both present") in web.conflicts()
    # Circular support is reported as a cycle.
    web.link("y", typed_links.SUPPORTS, "x")
    cycles = web.support_cycles()
    assert any("x" in c and "y" in c for c in cycles)


def test_typed_links_browser_renders_argument_skeleton():
    web = _arg_web()
    window = web.browser("claim")
    text = window.render()
    assert "Levi runs local-first" in text
    assert "benchmark log" in text  # supporter shown
    assert "cloud is cheaper" in text  # refuter shown
    metrics = window.metrics()
    assert metrics["support_span"] >= 1
    assert metrics["contested"] is True  # obj refutes the root


# ---------------------------------------------------------------------------
# live_system — tagged heap, hot patching, inspection
# ---------------------------------------------------------------------------


def test_live_system_define_and_call():
    img = live_system.LiveSystem()
    img.define("double", lambda n: n * 2, doc="doubles")
    assert img.call("double", 21) == 42
    assert img.definitions() == ["double"]
    with pytest.raises(live_system.UnknownDefinition):
        img.call("triple", 1)
    with pytest.raises(live_system.NotCallableDefinition):
        img.define("nope", 42)


def test_live_system_hot_patch_keeps_history():
    img = live_system.LiveSystem()
    img.define("greet", lambda: "v1")
    assert img.call("greet") == "v1"
    img.redefine("greet", lambda: "v2")  # patched while running
    assert img.call("greet") == "v2"
    assert img.history("greet") == 2
    img.rollback("greet", 1)
    assert img.call("greet") == "v1"
    assert img.history("greet") == 3  # rollback is itself a version
    with pytest.raises(live_system.UnknownDefinition):
        img.redefine("ghost", lambda: 1)


def test_live_system_tagged_bindings_and_gc():
    img = live_system.LiveSystem()
    assert img.bind("answer", 42) == "integer"
    assert img.bind("words", ["a", "b"]) == "list"
    assert img.bind("nothing", None) == "null"
    assert img.lookup("answer") == 42
    assert img.bindings() == {"answer": "integer", "words": "list", "nothing": "null"}
    img.unbind("answer")
    assert img.gc() == 1  # the released cell is swept
    with pytest.raises(live_system.UnknownBinding):
        img.lookup("answer")


def test_live_system_inspect_snapshots_everything():
    img = live_system.LiveSystem()
    img.define("f", lambda: 1, doc="one")
    img.bind("x", "hello")
    snap = img.inspect()
    assert snap["definitions"]["f"]["version"] == 1
    assert snap["definitions"]["f"]["doc"] == "one"
    assert snap["bindings"]["x"] == "string"
    assert snap["heap"]["live"] >= 1
    assert live_system.tag_of(lambda: 1) == "function"
    assert live_system.tag_of({"a": 1}) == "map"


# ---------------------------------------------------------------------------
# presence_spaces — persistent artifacts + presence + history
# ---------------------------------------------------------------------------


def _space():
    spaces = presence_spaces.Spaces(idle_after=3)
    spaces.create_space("lobby", "the gathering place")
    spaces.join("lobby", "chauncey")
    spaces.join("lobby", "levi")
    return spaces


def test_presence_roster_and_idle():
    spaces = _space()
    roster = {r["person"]: r["status"] for r in spaces.roster("lobby")}
    assert roster == {"chauncey": "here", "levi": "here"}
    spaces.tick(2)
    spaces.heartbeat("lobby", "chauncey")
    spaces.tick(2)  # levi now silent 4 ticks > idle_after 3
    roster = {r["person"]: r["status"] for r in spaces.roster("lobby")}
    assert roster["chauncey"] == "here"
    assert roster["levi"] == "idle"
    spaces.leave("lobby", "levi")
    assert [r["person"] for r in spaces.roster("lobby")] == ["chauncey"]
    with pytest.raises(presence_spaces.NotPresent):
        spaces.heartbeat("lobby", "levi")


def test_presence_notes_keep_revision_history():
    spaces = _space()
    nid = spaces.post_note("lobby", "chauncey", "plans", "draft one")
    spaces.revise_note("lobby", nid, "levi", "draft two")
    rev = spaces.revise_note("lobby", nid, "chauncey", "draft three")
    assert rev == 3
    history = spaces.note_history("lobby", nid)
    assert [r.text for r in history] == ["draft one", "draft two", "draft three"]
    assert [r.number for r in history] == [1, 2, 3]


def test_presence_forum_threads_and_events():
    spaces = _space()
    tid = spaces.open_thread("lobby", "levi", "tonight's build")
    assert spaces.reply("lobby", tid, "chauncey", "ship it") == 1
    assert spaces.reply("lobby", tid, "levi", "shipped") == 2
    thread = spaces.thread("lobby", tid)
    assert thread.topic == "tonight's build"
    assert [p.author for p in thread.posts] == ["chauncey", "levi"]
    kinds = {e.kind for e in spaces.events("lobby")}
    assert {"space", "join", "thread", "reply"} <= kinds
    with pytest.raises(presence_spaces.UnknownArtifact):
        spaces.thread("lobby", "thread-999")


def test_presence_games_are_rule_checked_and_persistent():
    spaces = _space()
    gid = spaces.start_game("lobby", "chauncey", "tally", "lunch vote")
    spaces.move("lobby", gid, "chauncey", {"option": "tacos"})
    state = spaces.move("lobby", gid, "levi", {"option": "tacos"})
    assert state["votes"] == {"tacos": 2}
    with pytest.raises(presence_spaces.IllegalMove):
        spaces.move("lobby", gid, "levi", "not-a-valid-move")
    # story game enforces alternation
    sid = spaces.start_game("lobby", "levi", "story", "tale")
    spaces.move("lobby", sid, "levi", "once upon a tick")
    with pytest.raises(presence_spaces.IllegalMove):
        spaces.move("lobby", sid, "levi", "twice in a row")
    with pytest.raises(presence_spaces.SpaceError):
        spaces.start_game("lobby", "levi", "chess", "nope")


# ---------------------------------------------------------------------------
# category_tiles — data/formula/presentation separation
# ---------------------------------------------------------------------------


def _shop_model():
    model = category_tiles.CategoryModel()
    model.define("Sales")
    model.define("Costs")
    model.define("Profit", formula="sum Sales minus sum Costs")
    model.record("Sales", 100, Region="North")
    model.record("Sales", 50, Region="South")
    model.record("Costs", 60, Region="North")
    model.record("Costs", 20, Region="South")
    return model


def test_category_tiles_data_addressed_by_meaning():
    model = _shop_model()
    assert model.value("Sales") == 150
    assert model.value("Sales", Region="North") == 100
    assert model.dimensions("Sales") == {"Region"}
    cells = model.cells("Costs", Region="South")
    assert list(cells.values()) == [20]


def test_category_tiles_formula_layer_is_plain_english():
    model = _shop_model()
    assert model.value("Profit") == 70  # (100+50) - (60+20)
    model.define("Doubled", formula="Sales times 2")
    assert model.value("Doubled") == 300
    model.define("AvgSale", formula="average Sales")
    assert model.value("AvgSale") == 75
    model.define("Flat", formula="100 plus 23")
    assert model.value("Flat") == 123
    with pytest.raises(category_tiles.TileError):
        model.record("Profit", 1, Region="North")  # computed tiles hold no data


def test_category_tiles_formula_cycles_raise():
    model = category_tiles.CategoryModel()
    model.define("A", formula="sum B")
    model.define("B", formula="sum A")
    with pytest.raises(category_tiles.FormulaError):
        model.value("A")
    with pytest.raises(category_tiles.UnknownTile):
        model.value("Ghost")
    with pytest.raises(category_tiles.DuplicateTile):
        model.define("A")


def test_category_tiles_view_is_computed_presentation():
    model = _shop_model()
    view = model.view()
    text = view.render()
    assert "Profit" in text and "= sum Sales minus sum Costs" in text
    assert "70" in text
    summary = view.summary()
    assert summary == {"Sales": 150, "Costs": 80, "Profit": 70}
    rows = view.rows()
    kinds = {r["tile"]: r["kind"] for r in rows}
    assert kinds == {"Sales": "data", "Costs": "data", "Profit": "computed"}


# ---------------------------------------------------------------------------
# live_objects — persistent objects, replaceable classes
# ---------------------------------------------------------------------------


def _store():
    return live_objects.ObjectStore(live_objects.standard_registry())


def test_live_objects_create_query_dispatch():
    store = _store()
    pid = store.create("Printer", name="hall", pages=0)
    assert store.call(pid, "print_page", "hello") == "[hall] page 1: hello"
    assert store.get(pid).get("pages") == 1
    nid = store.create("Note", text="four score and seven")
    assert store.call(nid, "word_count") == 4
    assert [o.object_id for o in store.query(class_name="Printer")] == [pid]
    assert [o.object_id for o in store.query("Note", text="four score and seven")] == [
        nid
    ]
    with pytest.raises(live_objects.UnknownClass):
        store.create("Toaster")
    with pytest.raises(live_objects.UnknownMethod):
        store.call(pid, "brew_coffee")


def test_live_objects_class_replace_changes_behavior_live():
    store = _store()
    pid = store.create("Printer", name="hall", pages=0)

    def loud_print(obj, store, text):
        return f"[{obj.get('name')}] PAGE {obj.get('pages', 0) + 1}: {text.upper()}"

    store.registry.replace(
        "Printer",
        live_objects.ClassSpec(
            "Printer", 2, {"print_page": loud_print}, "louder printer"
        ),
        store=store,
    )
    # Same object, same identity — new implementation underneath.
    assert store.call(pid, "print_page", "hello") == "[hall] PAGE 1: HELLO"
    assert store.registry.history("Printer") == [
        "Printer v1: ['print_page']",
        "Printer v2: ['print_page']",
    ]


def test_live_objects_replace_with_migration_reshapes_attrs():
    store = _store()
    nid = store.create("Note", text="old note")

    def v2_preview(obj, store, width=40):
        return f"v2:{obj.get('body', '')[:width]}"

    store.registry.replace(
        "Note",
        live_objects.ClassSpec("Note", 2, {"preview": v2_preview}, "renamed attr"),
        migrate=lambda attrs: {"body": attrs.pop("text", "")},
        store=store,
    )
    obj = store.get(nid)
    assert obj.get("body") == "old note"
    assert obj.get("text") is None
    assert store.call(nid, "preview") == "v2:old note"


def test_live_objects_snapshot_restore_round_trip(tmp_path):
    store = _store()
    pid = store.create("Printer", name="hall", pages=3)
    text = store.export_json()
    fresh = live_objects.ObjectStore(live_objects.standard_registry())
    assert fresh.restore(store.snapshot()) == 1
    assert fresh.get(pid).get("pages") == 3
    assert fresh.import_json(text) == 1
    # Version mismatch raises instead of silently misbehaving.
    other = live_objects.ObjectStore(live_objects.standard_registry())
    other.registry.replace(
        "Printer", live_objects.ClassSpec("Printer", 9, {}, "future"), store=other
    )
    with pytest.raises(live_objects.VersionMismatch):
        other.restore(store.snapshot())
    # Explicit file persistence, nothing hidden.
    path = str(tmp_path / "shelf.json")
    store.save(path)
    loaded = live_objects.ObjectStore(live_objects.standard_registry())
    assert loaded.load(path) == 1


# ---------------------------------------------------------------------------
# minimal_os — the fourteen-method machine
# ---------------------------------------------------------------------------


def test_minimal_os_api_surface_is_pinned():
    public = [
        name
        for name in dir(minimal_os.MiniKernel)
        if not name.startswith("_") and callable(getattr(minimal_os.MiniKernel, name))
    ]
    assert sorted(public) == sorted(minimal_os.API_SURFACE)
    assert len(minimal_os.API_SURFACE) <= 16
    assert minimal_os.MiniKernel().version() == "levi-minikern 1.0"


def test_minimal_os_cooperative_tasks():
    kernel = minimal_os.MiniKernel()
    log = []

    def worker(tag, n):
        for i in range(n):
            log.append((tag, i))
            yield

    a = kernel.spawn("a", worker, "a", 2)
    b = kernel.spawn("b", worker, "b", 3)
    assert kernel.run() == 4  # each task needs a final step to observe StopIteration
    assert log == [("a", 0), ("b", 0), ("a", 1), ("b", 1), ("b", 2)]
    states = {t["pid"]: t["state"] for t in kernel.tasks()}
    assert states[a] == "done" and states[b] == "done"
    with pytest.raises(minimal_os.KernelError):
        kernel.kill(a)  # already done — killing it again is an honest error
    with pytest.raises(minimal_os.UnknownTask):
        kernel.kill(999)
    with pytest.raises(minimal_os.NotAGenerator):
        kernel.spawn("bad", lambda: 42)


def test_minimal_os_ports_pass_messages():
    kernel = minimal_os.MiniKernel()
    kernel.open_port("inbox")
    assert kernel.recv("inbox") is None
    kernel.send("inbox", "hello")
    kernel.send("inbox", "world")
    assert kernel.recv("inbox") == "hello"
    assert kernel.recv("inbox") == "world"
    kernel.close_port("inbox")
    with pytest.raises(minimal_os.UnknownPort):
        kernel.send("inbox", "x")
    with pytest.raises(minimal_os.DuplicatePort):
        kernel.open_port("dup")
        kernel.open_port("dup")


def test_minimal_os_vfs_round_trip():
    kernel = minimal_os.MiniKernel()
    kernel.write("/notes/todo.txt", "ship wave 01")
    kernel.write("/notes/done.txt", "wave 00")
    assert kernel.read("notes/todo.txt") == "ship wave 01"  # slash optional
    assert kernel.listdir("/notes") == ["done.txt", "todo.txt"]
    kernel.delete("/notes/done.txt")
    assert kernel.listdir("/notes") == ["todo.txt"]
    with pytest.raises(minimal_os.NotAFile):
        kernel.read("/notes/done.txt")
    with pytest.raises(minimal_os.NotAFile):
        kernel.delete("/notes/done.txt")


# ---------------------------------------------------------------------------
# contracts — executable preconditions, postconditions, invariants
# ---------------------------------------------------------------------------


def test_contracts_requires_blocks_bad_entry():
    @contracts.requires(lambda n: n >= 0, "n must be non-negative")
    def root(n):
        return n**0.5

    assert root(9) == 3.0
    with pytest.raises(contracts.ContractViolation) as exc:
        root(-1)
    assert exc.value.kind == "precondition"
    assert "non-negative" in str(exc.value)


def test_contracts_ensures_checks_the_outcome():
    @contracts.ensures(
        lambda result, items: len(result) == len(items), "length preserved"
    )
    def doubled(items):
        return [x * 2 for x in items]

    assert doubled([1, 2]) == [2, 4]

    @contracts.ensures(lambda result: result > 0, "must stay positive")
    def broken():
        return -5

    with pytest.raises(contracts.ContractViolation) as exc:
        broken()
    assert exc.value.kind == "postcondition"


def test_contracts_invariant_holds_around_every_call():
    @contracts.invariant(lambda self: self.balance >= 0, "never overdrawn")
    class Purse:
        def __init__(self, balance):
            self.balance = balance

        @contracts.requires(lambda self, amount: amount > 0, "positive deposits")
        def deposit(self, amount):
            self.balance += amount

        def spend(self, amount):
            self.balance -= amount

    with pytest.raises(contracts.ContractViolation):
        Purse(-1)  # invariant checked right after construction
    purse = Purse(10)
    purse.deposit(5)
    assert purse.balance == 15
    with pytest.raises(contracts.ContractViolation):
        purse.deposit(-3)  # precondition fires first
    with pytest.raises(contracts.ContractViolation) as exc:
        purse.spend(99)  # invariant fires after the method
    assert exc.value.kind == "invariant"
    assert contracts.invariant_spec(Purse)[1] == "never overdrawn"


def test_contracts_stack_and_switch():
    @contracts.requires(lambda x: isinstance(x, int), "int only")
    @contracts.requires(lambda x: x % 2 == 0, "even only")
    @contracts.ensures(lambda r, x: r == x // 2, "halved")
    def halve(x):
        return x // 2

    assert halve(8) == 4
    with pytest.raises(contracts.ContractViolation):
        halve(7)
    with pytest.raises(contracts.ContractViolation):
        halve("8")
    specs = contracts.contract_specs(halve)
    assert {s[0] for s in specs} == {"precondition", "postcondition"}
    # The global switch silences everything for measured runs.
    assert contracts.contracts_enabled() is True
    contracts.contracts_enabled(False)
    try:
        assert halve(7) == 3  # no checks: 7 // 2
    finally:
        contracts.contracts_enabled(True)
    with pytest.raises(contracts.ContractViolation):
        halve(7)
