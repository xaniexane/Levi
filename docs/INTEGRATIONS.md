# Integrations — `core/levi/integrations/`

LEVI's "plug in universal" layer: free, local-first integrations with
outside systems, plus the interpenetration map that says which
integrations may compose with which capabilities.

## Purpose

Wire LEVI to the world without paid APIs or cloud lock-in — and make
the *composition* of integrations explicit, so a risky combination
inherits the strictest risk ceiling of its parts (organism DNA law).

## Key APIs

- `free_lattice.py`
  - `FreeIntegration` — one integration record (name, kind, risk, cost)
  - `free_catalog() -> List[FreeIntegration]` — all free integrations
  - `format_catalog() -> str` — human-readable listing
  - `interpenetration_matrix() -> str` — which integrations may compose
- `free_graph.py`
  - `FreeGraph` / `build_free_graph(...)` — graph of integrations and
    their symbiosis pairs (`_symbiosis_pairs()`)
- References registry (`core/levi/plugins/references.py`,
  `docs/REFERENCES.md`): external providers are **references, never
  sources** — LEVI's identity is LEVI-only. `levi reference add/list/remove`,
  `levi mcp add --reference`.

## CLI usage

```bash
levi symbiosis        # asset other-half map + value check
levi plugins          # capability/plugin catalog
levi reference list   # registered external references
```

## Honest limits

- "Free" means zero marginal cost and no paid API — not zero setup:
  some integrations still need accounts, OAuth, or keys from the
  provider (stored in the vault, never in code).
- The interpenetration matrix is advisory policy, not a sandbox —
  enforcement lives in the calling code's risk checks.
- References are pointers for comparison/attribution; nothing in this
  layer lets an external provider speak as LEVI.
