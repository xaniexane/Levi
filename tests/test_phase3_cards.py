"""Acceptance tests for phase3/cards (A6 salvage formal spec, T1-T6).

Hermetic: no network, no daemons, no HOME writes. Sockets are blocked
in the T6 offline test by a local fixture (no import of the beginning
team's synthesis/offline.py).
"""

from __future__ import annotations

import random

import pytest

from levi.phase3.cards import (
    RELATIONS,
    CardIndex,
    CardStore,
    Decision,
    DictMemoryView,
    Fact,
    render,
)


@pytest.fixture
def no_sockets(monkeypatch):
    """Block all socket use: the offline test must not touch the network."""
    import socket

    def _blocked(*args, **kwargs):
        raise AssertionError("network access is disabled in this test")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
    return True


def _learning_view(n: int) -> DictMemoryView:
    """n learnings ingested as facts, one entity each."""
    view = DictMemoryView()
    for i in range(n):
        eid = f"topic_{i:03d}"
        view.set_entity(eid, kind="topic", title=f"Topic {i}")
        view.add_fact(
            Fact(
                id=f"f{i:03d}",
                entity_id=eid,
                text=f"Learning {i}: the predator keeps a card on every target.",
                witness=f"r-{i}",
            )
        )
    return view


# ---------------------------------------------------------------- T1
def test_t1_coverage_200_learnings_one_sync():
    view = _learning_view(200)
    store = CardStore()
    changed = store.sync_cycle(view)
    assert len(changed) >= 190, "only %d cards after one sync" % len(changed)
    assert len(store) >= 190
    # Every learning's card exists and cites its source fact.
    for i in range(200):
        card = store.get(f"card:topic_{i:03d}")
        assert card is not None, "missing card for topic_%03d" % i
        assert f"f{i:03d}" in card.sources


# ---------------------------------------------------------------- T2
def test_t2_determinism_20_syncs_byte_identical():
    view = _learning_view(40)
    store = CardStore()
    first = None
    for _ in range(20):
        store.sync_cycle(view)
        snapshot = store.to_json()
        if first is None:
            first = snapshot
        assert snapshot == first
    # A second sync on an unchanged corpus changes nothing.
    assert store.sync_cycle(view) == []


# ---------------------------------------------------------------- T3
def _linked_view() -> DictMemoryView:
    view = DictMemoryView()
    for i in range(30):
        eid = f"node_{i:02d}"
        view.set_entity(eid, kind="entity", title=f"Node {i}")
        view.add_fact(
            Fact(
                id=f"f{i:02d}",
                entity_id=eid,
                text=f"Node {i} links onward.",
                refers_to=(f"node_{(i + 1) % 30:02d}",),
                witness=f"r-{i}",
            )
        )
    return view


def test_t3_link_integrity_100_mutations_zero_dangling():
    rng = random.Random(20260920)
    view = _linked_view()
    store = CardStore()
    store.sync_cycle(view)
    fact_ids = [f"f{i:02d}" for i in range(30)]
    for m in range(100):
        op = rng.choice(["delete", "rename", "merge", "add", "remove_entity"])
        if op == "delete" and fact_ids:
            fid = rng.choice(fact_ids)
            view.remove_fact(fid)
            fact_ids.remove(fid)
        elif op == "rename":
            old = f"node_{rng.randrange(30):02d}"
            view.rename_entity(old, f"{old}_r{m}")
        elif op == "merge":
            a, b = rng.randrange(30), rng.randrange(30)
            if a != b:
                view.merge_entities(f"node_{a:02d}", f"node_{b:02d}")
        elif op == "add":
            i = 1000 + m
            view.add_fact(
                Fact(
                    id=f"fx{i}",
                    entity_id=f"node_{rng.randrange(30):02d}",
                    text="late arrival",
                    refers_to=(f"node_{rng.randrange(30):02d}",),
                    witness="r-x",
                )
            )
        elif op == "remove_entity":
            view.remove_entity(f"node_{rng.randrange(30):02d}")
    store.sync_cycle(view)
    ids = {c.id for c in store.all()}
    dangling = []
    for card in store.all():
        for link in card.links:
            assert link.relation in RELATIONS
            if link.to_id not in ids or link.from_id not in ids:
                dangling.append(link)
    assert not dangling, "dangling links: %r" % (dangling[:5],)


# ---------------------------------------------------------------- T4
def test_t4_contradiction_surfacing_30_conflicts():
    view = DictMemoryView()
    for i in range(60):
        eid = f"party_{i:02d}"
        view.set_entity(eid, kind="entity", title=f"Party {i}")
        view.add_fact(
            Fact(
                id=f"cf{i:02d}",
                entity_id=eid,
                text=f"Party {i} claims the field.",
                witness=f"r-{i}",
            )
        )
    for i in range(30):
        a, b = f"cf{i:02d}", f"cf{i + 30:02d}"
        fa = view.fact(a)
        view.remove_fact(a)
        view.add_fact(
            Fact(
                id=fa.id,
                entity_id=fa.entity_id,
                text=fa.text,
                conflicts_with=(b,),
                witness=fa.witness,
            )
        )
    store = CardStore()
    store.sync_cycle(view)
    contradicts = [
        link
        for card in store.all()
        for link in card.links
        if link.relation == "contradicts"
    ]
    assert len(contradicts) == 30, "got %d contradicts links" % len(contradicts)
    # Zero silent merges: both sides of every conflict still have cards
    # and both facts are still cited as sources.
    for i in range(60):
        card = store.get(f"card:party_{i:02d}")
        assert card is not None
        assert f"cf{i:02d}" in card.sources


# ---------------------------------------------------------------- T5
def test_t5_findability_100_lookups_within_2_hops():
    view = DictMemoryView()
    for i in range(100):
        eid = f"harbor_{i:03d}"
        view.set_entity(eid, kind="entity", title=f"Harbor Ledger {i}")
        view.add_fact(
            Fact(
                id=f"h{i:03d}",
                entity_id=eid,
                text=f"Ledger entry {i} balanced at dusk.",
                witness=f"r-{i}",
            )
        )
        view.add_decision(
            Decision(
                id=f"hd{i:03d}",
                entity_id=eid,
                summary="Ratified the quarterly plan.",
                receipt_id=f"r-d{i}",
            )
        )
    store = CardStore()
    store.sync_cycle(view)
    index = CardIndex.build(store.all())
    hits = 0
    for i in range(100):
        # Query names the entity; the target is its decision card.
        found = index.find(store, f"harbor ledger {i}", max_hops=2)
        if f"card:decision:hd{i:03d}" in found:
            hits += 1
    assert hits >= 95, "only %d/100 targets reachable" % hits


# ---------------------------------------------------------------- T6
def test_t6_offline_full_sync_cycle(no_sockets):
    assert no_sockets
    view = _learning_view(25)
    view.add_decision(
        Decision(
            id="d0",
            entity_id="topic_000",
            summary="File under topics.",
            receipt_id="r-d0",
            proof_handle="prf-9",
        )
    )
    store = CardStore()
    changed = store.sync_cycle(view)
    assert len(changed) == 26  # 25 topics + 1 decision card
    index = CardIndex.build(store.all())
    assert index.lookup("predator")
    text = render(store.get("card:decision:d0"))
    assert "r-d0" in text and "prf-9" in text
