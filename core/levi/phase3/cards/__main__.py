"""Demo: derive cards over a stub memory, sync, link, and look them up.

Run: ``python -m levi.phase3.cards`` (from the repo root with ``core/``
on ``sys.path``).
"""

from __future__ import annotations

from . import CardIndex, CardStore, Decision, DictMemoryView, Fact, render


def _demo_memory() -> DictMemoryView:
    view = DictMemoryView()
    view.set_entity("ada_lovelace", kind="entity", title="Ada Lovelace")
    view.set_entity("analytical_engine", kind="topic", title="Analytical Engine")
    view.add_fact(
        Fact(
            id="f1",
            entity_id="ada_lovelace",
            text="Wrote the first published algorithm for the Engine.",
            refers_to=("analytical_engine",),
            witness="r-101",
        )
    )
    view.add_fact(
        Fact(
            id="f2",
            entity_id="analytical_engine",
            text="Babbage's proposed mechanical computer.",
            witness="r-102",
        )
    )
    view.add_fact(
        Fact(
            id="f3",
            entity_id="analytical_engine",
            text="It was fully built in 1843.",
            conflicts_with=("f4",),
            witness="r-103",
        )
    )
    view.add_fact(
        Fact(
            id="f4",
            entity_id="ada_lovelace",
            text="The Engine was never completed in her lifetime.",
            conflicts_with=("f3",),
            witness="r-104",
        )
    )
    view.add_decision(
        Decision(
            id="d1",
            entity_id="ada_lovelace",
            summary="Publish the notes on the Engine.",
            receipt_id="r-200",
            proof_handle="prf-1",
            decider_entity_id="ada_lovelace",
        )
    )
    return view


def main() -> None:
    view = _demo_memory()
    store = CardStore()
    changed = store.sync_cycle(view)
    print("synced %d cards (%d changed)" % (len(store), len(changed)))
    print()
    for card in store.all():
        print(render(card))
        print()
    index = CardIndex.build(store.all())
    print("lookup 'lovelace':", index.lookup("lovelace"))
    print("find 'engine' (<=2 hops):", index.find(store, "engine"))


if __name__ == "__main__":
    main()
