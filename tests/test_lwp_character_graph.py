"""Tests for levi.lwp.character_graph — unbounded character generation (hermetic)."""

import json
import random

import pytest

from levi.lwp.character_graph import (
    BONDS,
    DRIVES,
    CharacterGraph,
    _name_from_axes,
)


@pytest.fixture()
def graph(tmp_path):
    return CharacterGraph(path=tmp_path / "graph.json")


def test_mint_deterministic_for_same_seed(graph):
    a = graph.mint(seed="fixed-seed")
    b = graph.mint(seed="fixed-seed")
    assert a.id == b.id
    assert a.name == b.name
    assert (a.drive, a.wound, a.method, a.voice, a.domain, a.era) == (
        b.drive,
        b.wound,
        b.method,
        b.voice,
        b.domain,
        b.era,
    )


def test_mint_different_seeds_differ(graph):
    a = graph.mint(seed="one")
    b = graph.mint(seed="two")
    assert a.id != b.id


def test_mint_rejects_unknown_axis_value(graph):
    with pytest.raises(ValueError):
        graph.mint(drive="world domination")
    with pytest.raises(ValueError):
        graph.mint(era="tuesday")


def test_mint_rejects_non_str_seed(graph):
    with pytest.raises(ValueError):
        graph.mint(seed=123)


def test_mint_persists_and_reloads(tmp_path):
    g1 = CharacterGraph(path=tmp_path / "graph.json")
    node = g1.mint(seed="keep-me", drive="justice")
    g2 = CharacterGraph(path=tmp_path / "graph.json")
    assert g2.nodes[node.id].drive == "justice"
    assert g2.nodes[node.id].name == node.name


def test_load_missing_or_corrupt_file_never_raises(tmp_path):
    g = CharacterGraph(path=tmp_path / "nope" / "missing.json")
    assert g.nodes == {} and g.edges == []
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    g2 = CharacterGraph(path=bad)
    assert g2.nodes == {} and g2.edges == []


def test_load_skips_malformed_nodes_but_keeps_good_ones(tmp_path):
    p = tmp_path / "graph.json"
    good = {
        "id": "char.abc123",
        "name": "Ashx-Jus",
        "drive": "justice",
        "wound": "betrayal",
        "method": "strategy",
        "voice": "spare",
        "domain": "city_under",
        "era": "mythic",
        "want": "w",
        "need": "n",
    }
    p.write_text(
        json.dumps({"nodes": [good, {"nope": 1}, "junk"], "edges": []}),
        encoding="utf-8",
    )
    g = CharacterGraph(path=p)
    assert list(g.nodes) == ["char.abc123"]


def test_mint_batch_bounds(graph):
    assert len(graph.mint_batch(0)) == 1  # documented floor: at least one
    assert len(graph.mint_batch(60)) == 50  # documented ceiling
    with pytest.raises(ValueError):
        graph.mint_batch("five")
    with pytest.raises(ValueError):
        graph.mint_batch(True)


def test_link_validates_nodes_and_relation(graph):
    a = graph.mint(seed="link-a")
    b = graph.mint(seed="link-b")
    e1 = graph.link(a.id, b.id)
    e2 = graph.link(a.id, b.id)
    assert e1.relation != e2.relation  # default relation rotates through BONDS
    assert e1.relation in BONDS
    with pytest.raises(ValueError):
        graph.link(a.id, "char.unknown")
    with pytest.raises(ValueError):
        graph.link(a.id, b.id, relation="nemesis")
    with pytest.raises(ValueError):
        graph.link(a.id, "")


def test_weave_structure(graph):
    text = graph.weave(3)
    assert "L.W.P. Character Graph Weave" in text
    assert text.count("Edge:") == 2
    assert "Graph size: 3 nodes" in text


def test_weave_rejects_bad_n(graph):
    with pytest.raises(ValueError):
        graph.weave("three")
    with pytest.raises(ValueError):
        graph.weave(True)


def test_theoretical_types_matches_axes(tmp_path):
    from levi.lwp.character_graph import DOMAINS, ERAS, METHODS, VOICES, WOUNDS

    g = CharacterGraph(path=tmp_path / "g.json")
    assert g.theoretical_types() == (
        len(DRIVES)
        * len(WOUNDS)
        * len(METHODS)
        * len(VOICES)
        * len(DOMAINS)
        * len(ERAS)
    )


def test_mint_does_not_touch_global_random_state(graph):
    before = random.getstate()
    graph.mint(seed="global-state-check")
    graph.weave(2)
    assert random.getstate() == before


def test_name_from_axes_stable_and_local():
    n1 = _name_from_axes("justice", "betrayal", "strategy", 12345)
    before = random.getstate()
    n2 = _name_from_axes("justice", "betrayal", "strategy", 12345)
    assert n1 == n2
    assert n1.endswith("-Jus")
    assert random.getstate() == before


def test_format_status_lists_commands(graph):
    status = graph.format_status()
    assert "levi characters --mint" in status
    assert "Theoretical distinct axis combos" in status
