# Memory — `core/levi/memory/`

LEVI's durable, local-first memory: a JSON-backed store of typed
entries plus hybrid retrieval (BM25 + vector + recency + corroboration).
The agent's `memory_write` / `memory_search` tools and the growth loop
both write here. Also backs `python -m levi.rag`.

## Purpose

Give LEVI long-term memory that survives sessions: facts, preferences,
procedures, relationships, device state — retrievable by meaning, not
just by keyword.

## Key APIs

- `MemoryStore(data_dir=None)` — defaults to `~/.levi/memory`.
  - `add(memory_type, content, importance=0.5, source="user", tags=None, ...)` → `MemoryEntry` (raises `ValueError` on invalid input; importance clamped 0..1)
  - `get(entry_id)`, `list(memory_type=None, limit=50)`, `search(query, limit=20)`, `delete(entry_id) -> bool`, `stats()`
- `MemoryType`: `working`, `episodic`, `semantic`, `preference`, `project`, `procedural`, `relationship`, `device`
- `levi.memory.retrieval.retrieve(query, store, limit=10, method="hybrid")` → list of `(entry, score, explanation)`; methods `bm25 | vector | hybrid | recency`
- `levi.memory.hierarchy`: `hierarchy_status()`, `explain_belief(claim)` — provenance narrative for a claim
- RAG layer (`core/levi/rag/`): `ingest_file/ingest_directory`, `ask`, `evaluate`

## CLI usage

```bash
python -m levi.memory add "Chauncey likes oolong tea" --type preference --tags drink
python -m levi.memory search "tea preferences"
python -m levi.memory list --type preference --limit 20
python -m levi.memory stats
python -m levi.memory explain "Chauncey likes tea"
python -m levi.memory delete <id>
```

## Honest limits

- Local JSON file, no vector DB — retrieval is honest but small-scale;
  `vector` here means sparse hash vectors, not embeddings.
- No encryption at rest: the vault (`docs/VAULT.md`) exists for
  secrets; memory is for ordinary recall.
- Growth-loop writes are tagged and deduped; memory never rewrites
  policy/identity (see `docs/GROWTH.md` binding rails).
- The `forget` flow is the supported removal path; there is no
  automatic expiry — `recency_factor` only down-ranks, never deletes.
