# LEVI Warehouses — not a tool belt

A tool belt is a small flat list you carry. A warehouse is a vast
categorized depot with inventory, indexing, and retrieval. LEVI's
capabilities are organized as distinct named warehouses, each with its
own inventory manifest — browsable, countable, pullable.

This is the **organization layer** over the capability atlas. For the
atlas contract itself (`export_atlas()` / `write_atlas()`), see
`docs/ATLAS.md`; this document is the warehouse framing and its API.

## The fourteen warehouses

| Warehouse | Shelves (modules) | What's stocked |
|---|---|---|
| `methods` — Methods | methods | 40 forgotten human techniques (loci, ACH, colon, …) |
| `revivals` — Revivals | revival, telegraph | 20 retired systems + the telegraph office (dead protocols: FidoNet store-and-forward, Telex answerback, AppleTalk chooser), all reborn as original LEVI works |
| `skills` — Skills & Playbooks | cyber-skills | 839 defensive blue-team + operator playbooks |
| `archive` — Archive Knowledge | archive, knowledge, academy, bounty, research | The Smithsonian records (perpetual-hunt finds) + public-source deep-web research |
| `services` — Services | galaxy, daemon, perpetual, bot-services | Live installs, automations, supervision |
| `games` — Games | games | Fair-play local games: every game passes the Fair Play Charter (no paid randomness, no streak punishment, no FOMO timers, free hints, offline-first, portable player-owned saves) |
| `memory` — Memory & Growth | memory-store, memory-retrieval, rag, agent-assistant, growth | The substrate + baby Levi's learning loop |
| `finance` — Finance | finance | Paper-trading intelligence (paper-only) |
| `factory` — Factory | factory | The production line: hunt → archive → manufacture → stocking → galaxy |
| `organism` — Organism Core | bloodstream, organs, lifepack, oath | The turn pipeline, event bus, organs, life packs |
| `forge` — Forge | forge | LEVI's own code home: local git hosting, issues, PRs, unmetered local CI, one-command full export |
| `operations` — Operations | signals, creed, promises, decisions, interruptions, snapshots, drift, teachback, energy, friction, sweeps, premortem | LEVI's operating layer: graded signal plane, frozen creed of laws, ledgers and rituals of a reliable operator |
| `commons` — Commons | communities, threads, bridging, classifieds, charters, commitments, recap, feedreader, feedlab | Portable social fabric: leave any platform, keep the community; consensus without a central moderator; a feed-ranking transparency lab |
| `craft` — Craft | ephemera, packs, shareware, dials, capproto, mailtriage, vaults, canvas, discover, presence, honestsearch, recommender | Sovereign instruments: true-delete channels, attention dials, local mail triage, LAN presence rooms, clean-room search, honest trial grants |

Inventory counts are **real** — counted from the actual modules,
playbooks, records, and live runtime state, never estimated.

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

browse_warehouse("skills")                       # 839 playbooks
warehouse_inventory("skills", limit=10)          # first 10, total=839
pull_from_shelf("methods", "methods.loci")       # full detail + invoke line
```

## The factory synthesis

Warehouses stock the inventory; the **factory** is the production line
that fills them: hunt (intake) → archive (processing) → manufacture
(the never-stops build engine) → warehouse stocking → galaxy
(distribution). The Megazord is the whole industrial complex:
warehouses of capability plus a factory that never stops — and the
**waymaker law** above all: where there isn't a way, LEVI creates one.
