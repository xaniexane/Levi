# LEVI RAG & Memory Retrieval

Local-first, stdlib-only, offline. No embeddings service, no vector DB, no
network — the whole pipeline runs on LEVI's own hardware.

## Architecture (in prose)

```
  .md / .txt files
        │ ingest (chunking.py + ingest.py)
        ▼
  ┌─────────────┐   sliding windows (~500 chars, 100 overlap),
  │   CHUNKS    │   markdown headers tracked → section context,
  │  +provenance│   each chunk = {source_doc, chunk_index, char_span, section}
  └──────┬──────┘
         ▼ stored as SEMANTIC memory entries, tagged "rag"
  ┌─────────────┐
  │ MEMORY STORE│  (levi.memory.store — unchanged, read via list())
  └──────┬──────┘
         │ retrieve()  (levi.memory.retrieval)
         ▼
  ┌─────────────┐
  │   RANKER    │  BM25 (tags 3×) + hashed char-n-gram vectors,
  │  hybrid RRF │  fused by reciprocal rank fusion (k=60),
  │             │  modulated by recency × importance × corroboration
  └──────┬──────┘
         │ rerank (coverage + provenance trust)
         ▼
  ┌─────────────┐   context block with [memory:<id>] citations
  │    ASK      │──▶ generator (agent runtime, lazy)
  │  pipeline   │   or honest "no generator available" notice
  └─────────────┘   or "nothing relevant — treat as unsupported"
```

## The retrieval ladder

`core/levi/memory/retrieval.py` ranks over the existing store without
modifying it:

1. **BM25** — k1=1.5, b=0.75; tokenize → lowercase, stopwords, light
   stemming; tags weighted 3× content.
2. **Recency + importance** — exponential half-life decay (default 7 days,
   configurable) × importance (0..1, never zeroes a hit) × corroboration
   boost (`metadata["corroboration"]`, +10% each up to 5).
3. **Sparse semantic vectors** — character 4-gram hashing trick
   (hashlib.md5 → 512 dims, L2-normalized) + cosine similarity. Catches
   paraphrase with no model.
4. **Hybrid fusion** — reciprocal rank fusion over BM25 + vector rankings.
5. **Query expansion** — small synonym map; multi-queries split on
   " or " / commas / semicolons and fused.

`retrieve(query, store, limit=10, method="hybrid")` returns
`(entry, score, explanation)` triples; the explanation names the
contributing signals. It is fail-closed: blank queries → `[]`, and it
never raises — failures return `[]` with the reason in `LAST_ERROR`.

## Chunking choices

- Sliding character windows with sentence-boundary preference (never
  mid-word); overlap carries trailing context into the next chunk.
- Markdown headers are tracked: the active section is prepended as
  `[Section]` context and stored in provenance, so chunks stay
  self-describing out of order.
- Defaults: 500 chars / 100 overlap — small enough for precise citation,
  large enough for a claim plus its evidence.

## Citation / provenance contract

- Every chunk carries `{source_doc, chunk_index, char_span, section}` in
  `metadata["provenance"]`.
- The ask pipeline cites as `[memory:<entry_id>]`; the generator prompt
  instructs: use ONLY the context, cite sources, and say plainly when the
  context lacks the answer.
- `hierarchy.py`'s why-belief discipline is honored: conclusions link back
  toward evidence; unsupported claims are labeled, never invented.

## Usage

```bash
python -m levi.rag ingest notes.md            # chunk + store
python -m levi.rag ingest docs/ --pattern "*.md"
python -m levi.rag ask "what does the doc say about backups?"
python -m levi.rag ask "q" --no-generate      # retrieval + citations only
python -m levi.rag eval --k 5                 # retrieval quality as a number
```

Hermetic use: set `LEVI_RAG_HOME` (or `--data-dir`) to an isolated dir.

## Eval harness

`eval.py` builds templated questions from ingested chunks
("What does the document say about \<keyword\>?") and measures
**hit-rate@k / recall@k** plus mean rank of hits. Run it before and after
tuning chunk size, k, or the ranker — "good memory" becomes a number.
Typical failure modes it exposes: chunks too large (diluted terms),
headers missing (no section keywords), or over-aggressive stopwords.

## Honest limits

- **Sparse vectors ≠ true embeddings.** The hashing trick catches surface
  paraphrase ("laptop" vs "laptpo", "quick" vs "quikc") and some synonymy
  via expansion, but it has no real semantic understanding — "bank" (river)
  vs "bank" (money) look identical. It is a big step up from substring
  search, not a replacement for embeddings.
- **Dense embeddings are future work**, deliberately: they need a model
  (breaks the pure-stdlib constraint) or a download (breaks offline-first
  install). LEVI's native brain (`core/levi/brain/`) is the natural home
  for a tiny embedder later; the `embedding_ref` field on `MemoryEntry`
  already reserves the slot.
- The eval's templated questions measure *retrieval of the source chunk*,
  not answer correctness — generation quality is a separate harness.
- Rerank coverage is lexical; adversarial paraphrase can still slip past
  it. The citation contract is the backstop: every claim is traceable.
