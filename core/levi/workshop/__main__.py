"""python -m levi.workshop — inventory summary from the package API."""

from __future__ import annotations

import json

from .inventory import inventory


def main() -> int:
    inv = inventory()
    print(json.dumps(inv["counts"], indent=2, sort_keys=True))
    print("agents:", ", ".join(a["agent_id"] for a in inv["agents"][:5]), "...")
    print("specialists:", ", ".join(s["specialist_id"] for s in inv["specialists"]))
    print("substrates:", ", ".join(s["substrate_id"] for s in inv["substrates"]))
    print("organs:", ", ".join(o["name"] for o in inv["organs"]))
    print("legion roles:", ", ".join(r["role"] for r in inv["legion_roles"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
