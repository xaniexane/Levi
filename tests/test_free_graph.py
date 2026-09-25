"""Tests for levi.integrations.free_graph — hand-computed fixture assertions."""

from __future__ import annotations

import json

import pytest

from levi.graph.symbiosis import SymbiosisPair
from levi.integrations.free_graph import (
    JSON_SCHEMA,
    W_COMBINES_WITH,
    W_SYMBIOSIS,
    FreeGraph,
    build_free_graph,
)
from levi.integrations.free_lattice import (
    CATALOG,
    FreeIntegration,
    interpenetration_matrix,
)


def _fixture() -> FreeGraph:
    """Triangle a-b-c (weight 1.0 each), leaf d on a, isolated e.

    Hand-computed expectations:
      degree:            a=3 b=2 c=2 d=1 e=0
      degree centrality: a=3/4 b=c=1/2 d=1/4 e=0   (N=5)
      closeness:         a=3/3=1.0  b=3/4=0.75  e=0.0
      clustering:        a=2*1/(3*2)=1/3  b=1.0  d=0.0 (k<2)  e=0.0
      paths:             d->c = [d,a,c]; d->e = None; a->a = [a]
      neighborhood(a,1)  = {1: [b,c,d]}
      neighborhood(d,2)  = {1: [a], 2: [b,c]}
    """
    g = FreeGraph()
    for x, y in (("a", "b"), ("b", "c"), ("c", "a"), ("a", "d")):
        g.add_edge(x, y, 1.0, "combines_with")
    g.add_node("e")  # planted orphan
    return g


def test_degree_and_weighted_degree():
    g = _fixture()
    assert {n: g.degree(n) for n in "abcde"} == {"a": 3, "b": 2, "c": 2, "d": 1, "e": 0}
    assert {n: g.weighted_degree(n) for n in "abcde"} == {
        "a": 3.0,
        "b": 2.0,
        "c": 2.0,
        "d": 1.0,
        "e": 0.0,
    }


def test_degree_centrality():
    g = _fixture()
    dc = g.degree_centrality()
    assert dc["a"] == pytest.approx(0.75)
    assert dc["b"] == pytest.approx(0.5)
    assert dc["c"] == pytest.approx(0.5)
    assert dc["d"] == pytest.approx(0.25)
    assert dc["e"] == pytest.approx(0.0)


def test_closeness_centrality():
    g = _fixture()
    cc = g.closeness_centrality()
    assert cc["a"] == pytest.approx(1.0)  # dists 1,1,1 -> 3/3
    assert cc["b"] == pytest.approx(0.75)  # dists 1,1,2 -> 3/4
    assert cc["c"] == pytest.approx(0.75)
    assert cc["e"] == pytest.approx(0.0)  # isolated


def test_clustering_coefficient():
    g = _fixture()
    assert g.clustering_coefficient("a") == pytest.approx(1.0 / 3.0)
    assert g.clustering_coefficient("b") == pytest.approx(1.0)
    assert g.clustering_coefficient("c") == pytest.approx(1.0)
    assert g.clustering_coefficient("d") == pytest.approx(0.0)  # k<2
    assert g.clustering_coefficient("e") == pytest.approx(0.0)


def test_orphan_lint_finds_planted_orphan():
    g = _fixture()
    assert g.orphans() == ["e"]
    lint = g.lint()
    assert lint["orphans"] == ["e"]
    assert lint["ok"] is False


def test_shortest_path():
    g = _fixture()
    assert g.shortest_path("d", "c") == ["d", "a", "c"]
    assert g.shortest_path("a", "a") == ["a"]
    assert g.shortest_path("d", "e") is None  # disconnected
    assert g.shortest_path("d", "zzz") is None  # unknown id
    assert g.shortest_path("zzz", "a") is None  # unknown id


def test_neighborhood():
    g = _fixture()
    assert g.neighborhood("a", 1) == {1: ["b", "c", "d"]}
    assert g.neighborhood("d", 2) == {1: ["a"], 2: ["b", "c"]}
    assert g.neighborhood("zzz", 1) == {}  # unknown id


def test_weight_adds_when_both_registries_declare_pair():
    g = FreeGraph()
    g.add_edge("x", "y", W_COMBINES_WITH, "combines_with")
    g.add_edge("x", "y", W_SYMBIOSIS, "symbiosis")
    assert g.edge_weight("x", "y") == pytest.approx(3.0)
    assert g.weighted_degree("x") == pytest.approx(3.0)
    top = g.strongest_bonds(1)
    assert top[0][:3] == ("x", "y", 3.0)
    assert top[0][3] == ["combines_with", "symbiosis"]


def test_strongest_bonds_ranking():
    g = FreeGraph()
    g.add_edge("p", "q", 1.0, "combines_with")
    g.add_edge("r", "s", 2.0, "symbiosis")
    ranked = g.strongest_bonds(2)
    assert ranked[0][:3] == ("r", "s", 2.0)
    assert ranked[1][:3] == ("p", "q", 1.0)


def _cat(entries):
    return build_free_graph(catalog=entries, pairs=[])


def test_build_dangling_ref_becomes_external_node_and_lint_finding():
    cat = [
        FreeIntegration("solo", "modern", "Solo", "stdlib", ("ghost",), "$", "u"),
    ]
    g = _cat(cat)
    assert g.dangling_refs() == ["ghost"]
    assert g.nodes["ghost"].external is True
    assert g.degree("ghost") == 1  # still wired into the topology
    assert g.shortest_path("solo", "ghost") == ["solo", "ghost"]
    assert g.lint()["dangling_refs"] == ["ghost"]


def test_build_empty_combines_with_is_orphan_defect():
    cat = [
        FreeIntegration("lonely", "modern", "Lonely", "stdlib", (), "$", "u"),
        FreeIntegration("solo", "modern", "Solo", "stdlib", ("lonely",), "$", "u"),
    ]
    g = _cat(cat)
    # lonely IS connected (solo -> lonely edge), so no orphan here...
    assert g.orphans() == []
    # ...but a truly undeclared asset is a defect
    cat2 = [FreeIntegration("lonely", "modern", "Lonely", "stdlib", (), "$", "u")]
    assert _cat(cat2).orphans() == ["lonely"]
    assert _cat(cat2).lint()["ok"] is False


def test_build_symbiosis_pairs_get_weight_2():
    cat = [FreeIntegration("x1", "modern", "X1", "stdlib", (), "$", "u")]
    pairs = [SymbiosisPair("x1", "y1", "bond", "a1", "b1", "v", "f")]
    g = build_free_graph(catalog=cat, pairs=pairs)
    assert g.edge_weight("x1", "y1") == pytest.approx(W_SYMBIOSIS)
    assert g.nodes["y1"].external is True  # symbiosis-only asset kept as node
    assert g.dangling_refs() == []  # ...but not a dangling combines_with ref


def test_real_catalog_graph_has_no_orphans():
    g = build_free_graph()
    counts = g.counts()
    assert counts["nodes"] >= len(CATALOG)
    assert counts["edges"] > 0
    assert counts["total_weight"] > 0
    for c in CATALOG:
        assert g.degree(c.id) >= 1, c.id
    assert g.orphans() == []


def test_json_export_schema():
    g = _fixture()
    payload = json.loads(g.to_json_str())
    assert payload["schema"] == JSON_SCHEMA
    assert set(payload) == {
        "schema",
        "nodes",
        "edges",
        "counts",
        "orphans",
        "dangling_refs",
        "top_bonds",
    }
    by_id = {n["id"]: n for n in payload["nodes"]}
    assert set(by_id) == {"a", "b", "c", "d", "e"}
    a = by_id["a"]
    assert a["degree"] == 3 and a["weighted_degree"] == 3.0
    assert a["degree_centrality"] == pytest.approx(0.75)
    assert a["closeness"] == pytest.approx(1.0)
    assert a["clustering"] == pytest.approx(1.0 / 3.0)
    assert a["external"] is False and a["era"] is None
    for e in payload["edges"]:
        assert set(e) == {"a", "b", "weight", "kinds"}
        assert isinstance(e["kinds"], list) and e["kinds"]
    assert payload["orphans"] == ["e"]
    assert payload["dangling_refs"] == []
    weights = [b["weight"] for b in payload["top_bonds"]]
    assert weights == sorted(weights, reverse=True)


def test_json_export_real_graph_schema():
    payload = json.loads(build_free_graph().to_json_str())
    assert payload["schema"] == JSON_SCHEMA
    assert payload["orphans"] == []
    assert isinstance(payload["dangling_refs"], list)
    assert payload["counts"]["nodes"] == len(payload["nodes"])


def test_human_matrix_view_enriched_but_backward_compatible():
    text = interpenetration_matrix()
    assert "=== Max Interpenetration Matrix ===" in text
    assert "json_state <-> corpus" in text  # flat edge list kept
    assert "Symbiosis formal pairs: 30" in text
    assert "Graph model (weighted undirected)" in text
    assert (
        "weighting: declared combines_with = 1.0; symbiosis formal pair = 2.0;" in text
    )
    assert "orphans are defects" in text
    assert "orphans: none - every asset has an other half" in text
