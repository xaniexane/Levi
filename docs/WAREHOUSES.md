# LEVI Warehouses — not a tool belt

A tool belt is a small flat list you carry. A warehouse is a vast
categorized depot with inventory, indexing, and retrieval. LEVI's
capabilities are organized as distinct named warehouses, each with its
own inventory manifest — browsable, countable, pullable.

This is the **organization layer** over the capability atlas. For the
atlas contract itself (`export_atlas()` / `write_atlas()`), see
`docs/ATLAS.md`; this document is the warehouse framing and its API.

## The ten warehouses

| Warehouse | Shelves (modules) | What's stocked |
|---|---|---|
| `methods` — Methods | methods | 40 forgotten human techniques (loci, ACH, colon, …) |
| `revivals` — Revivals | revival | 20 retired systems reborn as original LEVI works |
| `skills` — Skills & Playbooks | cyber-skills | 823 defensive blue-team playbooks |
| `archive` — Archive Knowledge | archive, knowledge, academy, bounty | The Smithsonian records (perpetual-hunt finds) |
| `services` — Services | galaxy, daemon, perpetual, bot-services | Live installs, automations, supervision |
| `games` — Games | — | Fair-play additions (standing theme, no stock yet) |
| `memory` — Memory & Growth | memory-store, memory-retrieval, rag, agent-assistant, growth | The substrate + baby Levi's learning loop |
| `finance` — Finance | finance | Paper-trading intelligence (paper-only) |
| `factory` — Factory | factory | The production line: hunt → archive → manufacture → stocking → galaxy |
| `organism` — Organism Core | bloodstream, organs, lifepack, oath | The turn pipeline, event bus, organs, life packs |

Inventory counts are **real** — counted from the actual modules,
playbooks, records, and live runtime state, never estimated. `games`
honestly reports 0: the stock arrives via the perpetual hunt.

## API (stable — the CLI wires to exactly this)

From `levi.interop.warehouses`:

- `list_warehouses()` → `[{name, title, summary, inventory_count}]`
- `browse_warehouse(name)` → `{name, title, summary, shelves, inventory_count, pull_hint}` —
  each shelf carries its module's provides/requires and CLI reachability
- `warehouse_inventory(name, limit=50, offset=0)` →
  `{warehouse, total, offset, limit, truncated, items}` — `total` is always
  the true count; `limit=None` returns everything; no silent truncation
- `pull_from_shelf(warehouse, item_id)` → one item's full detail plus
  `invoke` (how to use it) — **read-only**, never executes

Unknown warehouse/item names raise `ValueError` naming what *is*
available. Example:

```python
from levi.interop.warehouses import browse_warehouse, warehouse_inventory, pull_from_shelf

browse_warehouse("skills")                       # 823 playbooks
warehouse_inventory("skills", limit=10)          # first 10, total=823
pull_from_shelf("methods", "methods.loci")       # full detail + invoke line
```

## The factory synthesis

Warehouses stock the inventory; the **factory** is the production line
that fills them: hunt (intake) → archive (processing) → manufacture
(the never-stops build engine) → warehouse stocking → galaxy
(distribution). The Megazord is the whole industrial complex:
warehouses of capability plus a factory that never stops — and the
**waymaker law** above all: where there isn't a way, LEVI creates one.
