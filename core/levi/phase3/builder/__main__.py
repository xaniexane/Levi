"""Demo: earn rank, build a region, sync the delta (working title: builder)."""

from __future__ import annotations

from .ranks import Builder, advance, demote
from .regions import RungStub, attempt_build, new_region
from .sync import Spool


def main() -> None:
    rung = RungStub()
    region = new_region("grove", "clearing")
    region.builders.append("demo-builder")

    mason = Builder(agent_id="demo-builder")
    advance(mason, 5, lambda work: True)
    advance(mason, 15, lambda work: True)
    print("rank:", mason.rank.name)

    op = {
        "kind": "add",
        "entity_type": "room",
        "entity_id": "r1",
        "props": {"name": "clearing"},
        "rung": 0,
        "asset_refs": {"moss": "sha256:abc"},
    }
    print("build:", attempt_build(mason, region, [op], rung))

    spool = Spool(link_up=False)
    from .regions import make_delta

    spool.enqueue(make_delta(region, [op | {"entity_id": "r2"}], mason.agent_id, rung))
    spool.link_up = True
    print("spool flushed:", spool.flush(region), "versions:", spool.applied)
    demote(mason, "validated harmful addition")
    print("after demotion:", mason.rank.name)


if __name__ == "__main__":
    main()
