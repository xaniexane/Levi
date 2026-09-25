"""Tests for revival batch B01 — hypermedia systems.

cardstack, typedeck, augment, thingraph, pivotmesh, deepzoom, physpiles:
each an original, from-scratch LEVI mechanism. At least three meaningful
tests per module: construct, exercise the core mechanism, cover an edge.
"""

import pytest

from core.levi.revival import cardstack
from core.levi.revival import typedeck
from core.levi.revival import augment
from core.levi.revival import thingraph
from core.levi.revival import pivotmesh
from core.levi.revival import deepzoom
from core.levi.revival import physpiles


# ---------------------------------------------------------------------------
# cardstack — zero-mode-switch card programming
# ---------------------------------------------------------------------------


def _demo():
    return cardstack.demo_plant_stack()


def test_cardstack_builds_three_card_stack():
    stack, _, _ = _demo()
    assert stack.order == ["home", "fern", "cactus"]
    assert stack.card("fern").read_field("title") == "Boston fern"
    assert set(stack.card("home").buttons) == {"water fern", "tour"}


def test_cardstack_button_script_mutates_and_navigates():
    stack, engine, said = _demo()
    engine.run_button("water fern")
    assert stack.current.name == "fern"
    assert stack.card("fern").read_field("last watered") == "today"
    assert any("Fern watered" in line for line in said)


def test_cardstack_ask_into_variable_and_interpolation():
    stack, engine, said = _demo()
    stack.go("fern")
    engine.run_button("rename")
    assert stack.card("fern").read_field("title") == "Maidenhair"
    assert any("Renamed to Maidenhair" in line for line in said)


def test_cardstack_zero_mode_switch_reader_is_author():
    stack, _, _ = _demo()
    # The reader's API and the author's API are the same object.
    stack.go("cactus")
    stack.current.set_field("title", "Old faithful")
    assert "Old faithful" in stack.render()
    assert "Old faithful" in stack.card("cactus").render()


def test_cardstack_unknown_card_and_bad_verb():
    stack, engine, _ = _demo()
    with pytest.raises(cardstack.UnknownCard):
        stack.go("greenhouse")
    with pytest.raises(cardstack.KardSyntaxError):
        engine.run_script('frobnicated "nonsense"')
    with pytest.raises(cardstack.KardSyntaxError):
        engine.run_script('set field "x"')


# ---------------------------------------------------------------------------
# typedeck — typed links + structural browsers
# ---------------------------------------------------------------------------


def _deck():
    deck = typedeck.Deck()
    deck.add_card("c1", "Local-first wins", kind="claim")
    deck.add_card("e1", "Crash-safe demo", kind="evidence")
    deck.add_card("c2", "Cloud is simpler", kind="claim")
    deck.add_card("q1", "What about sync?", kind="question")
    deck.link("e1", "supports", "c1")
    deck.link("c2", "refutes", "c1")
    deck.link("q1", "elaborates", "c2")
    deck.link("e1", "defines", "q1")
    return deck


def test_typedeck_links_are_typed_and_directional():
    deck = _deck()
    assert [(e.source, e.rel, e.target) for e in deck.out_links("e1")] == [
        ("e1", "supports", "c1"),
        ("e1", "defines", "q1"),
    ]
    assert [e.source for e in deck.in_links("c1")] == ["e1", "c2"]


def test_typedeck_browser_draws_argument_structure():
    deck = _deck()
    text = typedeck.browse(deck, "e1")
    assert text.splitlines()[0] == "[evidence] Crash-safe demo"
    assert "supports → [claim] Local-first wins" in text
    assert "defines → [question] What about sync?" in text
    assert "elaborates → [claim] Cloud is simpler" in text


def test_typedeck_browser_is_cycle_safe():
    deck = _deck()
    deck.link("c1", "elaborates", "e1")  # close the loop
    text = typedeck.browse(deck, "e1", max_depth=10)
    assert "(seen)" in text  # the cycle is marked, not re-entered


def test_typedeck_rejects_unknown_link_type():
    deck = _deck()
    with pytest.raises(typedeck.UnknownLinkType):
        deck.link("e1", "vibes-with", "c1")
    assert typedeck.debate(deck, "e1")["supports"] == 1


# ---------------------------------------------------------------------------
# augment — outlines, view filters, append-only journal
# ---------------------------------------------------------------------------


def _outline():
    outline = augment.Outline("Build LEVI")
    outline.add("Design the kernel", node_id="design")
    outline.add("Write the tests", parent_id="design", node_id="tests")
    outline.add("Ship the docs", node_id="docs", tags=("writing",))
    outline.add("Draft KING.md", parent_id="docs", node_id="kingdoc", tags=("writing",))
    return outline


def test_augment_outline_numbering_is_machine_clerical():
    outline = _outline()
    numbered = outline.numbered()
    assert numbered[0] == "1. Design the kernel"
    assert numbered[1] == "1.1. Write the tests"
    assert numbered[2] == "2. Ship the docs"


def test_augment_level_view_collapses_depth():
    outline = _outline()
    shallow = outline.level_view(1)
    assert {n.node_id for _, n in shallow} == {"root", "design", "docs"}
    deep = outline.level_view(5)
    assert {n.node_id for _, n in deep} == {
        "root",
        "design",
        "tests",
        "docs",
        "kingdoc",
    }


def test_augment_predicate_view_surfaces_matches_with_context():
    outline = _outline()
    view = outline.predicate_view(lambda n: "writing" in n.tags)
    ids = [n.node_id for _, n in view]
    # matches plus their ancestor path for context — nothing deleted
    assert ids == ["docs", "kingdoc"]
    assert len(outline.numbered()) == 4  # the outline itself is untouched


def test_augment_move_and_journal_are_append_only():
    outline = _outline()
    journal = augment.Journal()
    journal.log("outline created", "Build LEVI")
    outline.move("kingdoc", "design")
    journal.log("move", "kingdoc under design")
    assert outline.node("kingdoc").parent.node_id == "design"
    assert "1.2. Draft KING.md" in outline.numbered()
    entries = list(journal)
    assert [e.seq for e in entries] == [1, 2]
    assert [e.seq for e in journal.since(1)] == [2]
    with pytest.raises(augment.AugmentError):
        outline.move("design", "kingdoc")  # cannot move a node inside itself


# ---------------------------------------------------------------------------
# thingraph — typed item graph with first-class edges
# ---------------------------------------------------------------------------


def _graph():
    graph = thingraph.Graph()
    graph.add_item("chauncey", "person", {"role": "builder"})
    graph.add_item("levi", "project", {"status": "active"})
    graph.add_item("hyper", "task", {"status": "open"})
    graph.add_item("docs", "task", {"status": "done"})
    graph.relate("chauncey", "owns", "levi")
    graph.relate("levi", "contains", "hyper")
    graph.relate("levi", "contains", "docs")
    graph.relate("hyper", "blocked-by", "docs", props={"reason": "needs the spec"})
    return graph


def test_thingraph_query_by_kind_and_props():
    graph = _graph()
    assert [t.item_id for t in graph.by_kind("task")] == ["hyper", "docs"]
    assert [t.item_id for t in graph.find(kind="task", status="open")] == ["hyper"]
    assert graph.kinds() == ["person", "project", "task"]


def test_thingraph_traversal_follows_relationships():
    graph = _graph()
    two_hops = graph.traverse("chauncey", depth=2)
    assert {i.item_id for i in two_hops} == {"levi", "hyper", "docs"}
    named = graph.traverse("levi", name="contains")
    assert {i.item_id for i in named} == {"hyper", "docs"}
    # reverse: who relates TO hyper?
    backers = graph.traverse("hyper", reverse=True)
    assert {i.item_id for i in backers} == {"levi"}


def test_thingraph_edges_are_first_class():
    graph = _graph()
    edge = graph.relate("chauncey", "reviews", "hyper", props={"when": "friday"})
    assert edge.edge_id in graph.edges
    assert graph.edges[edge.edge_id].props["when"] == "friday"
    graph.unrelate(edge.edge_id)
    assert edge.edge_id not in graph.edges
    assert "reviews" not in graph.relationship_names()


def test_thingraph_remove_item_cascades_edges():
    graph = _graph()
    graph.remove_item("docs")
    assert "docs" not in graph.items
    assert all(e.source != "docs" and e.target != "docs" for e in graph.edges.values())
    with pytest.raises(thingraph.UnknownItem):
        graph.relate("levi", "contains", "docs")


# ---------------------------------------------------------------------------
# pivotmesh — zzstructure pivoting
# ---------------------------------------------------------------------------


def test_pivotmesh_links_are_bidirectional():
    mesh, _ = pivotmesh.demo_mesh()
    assert mesh.cell("n1").neighbor("time", "+") == "n2"
    assert mesh.cell("n2").neighbor("time", "-") == "n1"
    assert mesh.cell("n2").neighbor("time", "+") == "n3"


def test_pivotmesh_pivot_rotates_hidden_dimension_into_view():
    mesh, view = pivotmesh.demo_mesh()
    assert view.h_dim == "time" and view.v_dim == "topic"
    pivoted = view.pivot("people", axis="h")
    assert pivoted.h_dim == "people" and pivoted.v_dim == "topic"
    # the mesh itself never moved
    assert mesh.cell("n2").neighbor("time", "+") == "n3"
    pivoted.move_cursor("n1")  # n1 sits on the people strip
    rendered = pivoted.render()
    assert "h [people]" in rendered
    assert "sam" in rendered


def test_pivotmesh_walk_travels_a_dimension():
    mesh, _ = pivotmesh.demo_mesh()
    forward = [c.cell_id for c in mesh.walk("n1", "time", "+")]
    assert forward == ["n2", "n3"]
    backward = [c.cell_id for c in mesh.walk("n3", "time", "-")]
    assert backward == ["n2", "n1"]
    people = [c.cell_id for c in mesh.walk("n1", "people", "+")]
    assert people == ["p-sam", "p-jo", "n3"]
    strip = [c.cell_id for c in mesh.row("n2", "time")]
    assert strip == ["n1", "n2", "n3"]


def test_pivotmesh_dimension_clash_and_unknown_cell():
    mesh, _ = pivotmesh.demo_mesh()
    with pytest.raises(pivotmesh.DimensionClash):
        mesh.connect("n1", "n3", "time")  # n1 already has a +time link
    with pytest.raises(pivotmesh.UnknownCell):
        mesh.cell("nowhere")
    mesh.disconnect("n1", "time", "+")
    assert mesh.cell("n1").neighbor("time", "+") is None
    assert mesh.cell("n2").neighbor("time", "-") is None  # mirror severed too


# ---------------------------------------------------------------------------
# deepzoom — semantic zoom scene graph
# ---------------------------------------------------------------------------


def test_deepzoom_detail_level_follows_zoom():
    scene = deepzoom.demo_scene()
    node = scene.node("y2026")
    assert node.detail_at(0.0) == "◈"
    assert node.detail_at(0.7) == "2026"
    assert node.detail_at(5.0) == "2026 — the year LEVI grew teeth"


def test_deepzoom_render_changes_what_is_shown():
    scene = deepzoom.demo_scene()
    far = scene.render(0.0)
    assert "◈" in far
    assert "hypermedia batch" not in far  # fine print not earned yet
    near = scene.render(5.0)
    assert "Sep 16 — hypermedia batch lands, 7 modules green" in near
    assert "◈" not in near  # the glyph gave way to meaning


def test_deepzoom_children_expand_past_threshold():
    scene = deepzoom.demo_scene()
    assert "inside" in scene.render(1.0)  # sep's children still hidden…
    assert "Sep 16" in scene.render(3.0)  # …until the zoom earns them
    assert scene.zoom_to_fit("sep") == 3.0


def test_deepzoom_rejects_bad_input():
    scene = deepzoom.demo_scene()
    with pytest.raises(deepzoom.DeepzoomError):
        scene.render(-1.0)
    with pytest.raises(deepzoom.UnknownNode):
        scene.node("nope")
    with pytest.raises(deepzoom.DeepzoomError):
        scene.add("y2026", [(0.0, "dup")])  # node id already taken


# ---------------------------------------------------------------------------
# physpiles — deterministic spatial piles
# ---------------------------------------------------------------------------


def test_physpiles_size_expresses_importance():
    pile = physpiles.demo_pile()
    assert pile.item("visa").size_class() == "large"
    assert pile.item("receipt").size_class() == "small"
    assert pile.peek().item_id == "visa"  # heaviest on top after sorting


def test_physpiles_layout_is_deterministic_not_physics():
    pile = physpiles.demo_pile()
    first = [(p.item.item_id, p.x, p.y, p.rotation) for p in pile.layout_items()]
    second = [(p.item.item_id, p.x, p.y, p.rotation) for p in pile.layout_items()]
    assert first == second  # same slots every time, openly choreographed
    pile.fan()
    fanned = [(p.x, p.y) for p in pile.layout_items()]
    pile.pile()
    stacked = [(p.x, p.y) for p in pile.layout_items()]
    assert fanned != stacked  # the modes genuinely differ


def test_physpiles_toss_pull_reweigh():
    pile = physpiles.Pile("triage")
    pile.toss("a", "alpha", importance=0.1)
    pile.toss("b", "beta", importance=0.9)
    pile.reweigh("a", 0.95)
    pile.sort_by_importance()
    assert [i.item_id for i in pile] == ["b", "a"]  # heaviest on top
    assert "alpha" in pile.render()
    pulled = pile.pull("a")
    assert pulled.label == "alpha" and len(pile) == 1
    with pytest.raises(physpiles.UnknownItem):
        pile.pull("a")


def test_physpiles_rejects_out_of_range_importance():
    pile = physpiles.Pile("triage")
    with pytest.raises(physpiles.PhyspilesError):
        pile.toss("x", "too much", importance=1.5)
    pile.toss("y", "fine", importance=0.5)
    with pytest.raises(physpiles.PhyspilesError):
        pile.reweigh("y", -0.1)
