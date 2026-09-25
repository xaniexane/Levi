# INTEROP — the interpenetration doctrine

Interpenetration is a **binding law** of the LEVI organism: modules compose
through a shared substrate with **strictest-risk-ceiling inheritance** —
the organism wired together, not a bag of parts.

> **The law as an engine:** the machinery that computes and enforces this
> law — `composites.effective_ceiling`, `gate.run_composite_gated`, and the
> deny-closed defaults — is described in
> [INTERPENETRATION.md](INTERPENETRATION.md).

Two sub-laws, no exceptions:

1. **Shared substrate.** Every module that remembers, learns, or knows
   reads and writes through one substrate: the memory store
   (`levi.memory.store.MemoryStore`). Nothing keeps a private shadow copy
   of organism knowledge.
2. **Strictest-risk-ceiling inheritance.** When modules compose into one
   action, the composition is governed by the *highest* risk level among
   its participants (`levi.interop.risks.ceiling` /
   `levi.interop.risks.compose_risk`). A low-risk module composed with a
   high-risk module does not dilute the risk — it inherits it. The ceiling
   is deny-closed: unknown or unparseable risk levels raise `ValueError`
   rather than being silently dropped.

`levi.policy.gates.RiskLevel` (INFO=0 … CRITICAL=4) is the one and only
risk enum; the interop package reuses it and never redefines it.

## Connection map

```
                        ┌─────────────────┐
                        │   memory-store  │  ◄── the substrate
                        │  (write/read/   │
                        │   list)         │
                        └────────┬────────┘
            ┌───────────┬────────┼───────────┬────────────┐
            ▼           ▼        ▼           ▼            ▼
   memory-retrieval  agent-     rag         growth      organs
   (hybrid ranker)   assistant              (journal/   (echoverse/
   (BM25+vec+RRF)   (prompts,   (cited      cycle)      mandella/
                     user-ctx)  answers)                reim/riem)
            │           │        │              ▲
            │           │        │              │
            ▼           ▼        ▼              │
     ┌─────────────────────────────────┐       │
     │           bot-services          │───────┘
     │  (research-brief + others)      │  pending_learnings.jsonl
     └─────────────────────────────────┘       queue → journal
            │
   academy ─┴──► knowledge ◄── bounty
   (concepts)    (corpus)     (findings)
        │                         │
        └─ academy_memory ─┘      └─ bounty_knowledge ─┘
           (pure transform)            (pure transform)

   oath (identity/trust) — standalone substrate for now;
          wired in only where modules explicitly opt in.
```

What flows into what:

| from | into | via | flow |
|---|---|---|---|
| memory-retrieval | agent-assistant | `adapters.assistant_retrieval` | query-ranked user-context block (upgrade path for `load_user_context`) |
| rag | bot-services (`research-brief`) | `adapters.bot_rag` | cited, retrieval-backed brief dict (no agent runtime needed) |
| bot pending queue | growth journal | `adapters.growth_learnings` | validated candidate learnings → append-only journal |
| academy | memory-store | `adapters.academy_memory` | concepts → SEMANTIC memory entries (pure transform) |
| bounty | knowledge | `adapters.bounty_knowledge` | findings → dated corpus units (pure transform) |

The static capability declarations behind this map live in
`core/levi/interop/manifest.py` (11 modules: organs, memory-store,
memory-retrieval, rag, bot-services, growth, academy, bounty, knowledge,
oath, agent-assistant); `levi.interop.registry` validates the wiring
deny-closed and answers impact-analysis queries (`dependents_of`).

## Per-adapter contract

### `adapters.assistant_retrieval.load_user_context_retrieved(store, query, limit=8)`

Upgrade path for `levi.agent.assistant.load_user_context`. Runs
`levi.memory.retrieval.retrieve(query, store, limit, method="hybrid")` and
returns `{"block", "method": "hybrid"|"fallback", "entry_ids", "note"}`.
When retrieval is unavailable or returns no hits, falls back to the legacy
loader (method `"fallback"`); when both are unavailable the block is empty
and the note says so. Never raises.

### `adapters.bot_rag.research_brief_rag(topic, store)`

Runs `levi.rag.pipeline.ask(topic, store, generate=False)` and shapes the
result into the `research-brief` service dict:
`{"ok", "report", "citations", "notice", "method": "rag"}`. When RAG is
unavailable, `ok` is `False` with an explicit report — a failed research
step is reported, never papered over. See
`docs/INTEROP_FOLLOWUPS.md` for the one-line adoption patch in
`bot/services.py`.

### `adapters.growth_learnings.consume_pending_learnings(queue_path, journal)`

Consumes the bot's `~/.levi/bot/pending_learnings.jsonl` queue into the
growth journal via its public `append_entry`. Validates each line
deny-closed (dict with non-empty `text`/`learning`; malformed lines are
rejected and listed). Renames the queue to
`<name>.consumed-<UTC-ts>` **before** journaling, so consumed lines are
never reprocessed — idempotent by construction. Returns
`{"accepted", "rejected", "backup", "journaled_ids", "rejections"}`.
Only ever writes `kind: "learning"` journal entries; never touches memory,
tools, policy, or identity.

### `adapters.academy_memory.concepts_to_memory_entries(concepts)`

Pure transform (no store import): academy concept dicts → memory-store-ready
SEMANTIC entries `{"memory_type", "content", "tags", "importance",
"metadata": {"provenance": "academy", ...}}`. Deny-closed on malformed
concepts (`ValueError`).

### `adapters.bounty_knowledge.findings_to_corpus_units(findings)`

Pure transform (no knowledge import): bounty finding dicts →
knowledge-corpus-ready units `{"id": "bounty:<id>", "kind":
"security-finding", "text", "tags", "provenance", "metadata"}`.
Deny-closed on malformed findings. Evidence is carried verbatim as
detection data; the adapters add no attack guidance.

## Degradation policy

Every adapter follows the same ordered degradation:

1. **Full connection** — all modules present, real data flows.
2. **Honest fallback** — a documented weaker path (legacy loader,
   retrieval-only report) clearly labeled in the returned `method`/`note`.
3. **Explicit unavailability** — `ok: False` / empty block plus a note
   naming exactly what is missing.

What is never allowed: inventing data to fill a gap, silently dropping a
participant from a risk ceiling, or raising an unhandled exception out of
an adapter (adapters are composition infrastructure; they fail into
labeled states, not tracebacks).
