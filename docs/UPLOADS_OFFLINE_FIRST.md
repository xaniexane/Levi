# Upload study: offline-first assistant MVP

**Source:** `~/workspace/user/files/offline_first_assistant_mvp.zip` (18.5 KB, keeper's own material — analyze/study only, original untouched).
**Working copy (improved):** `~/workspace/uploads-work/offline-first/offline_first_assistant_mvp/`
**Applied LEVI-native:** `core/levi/offline/` (chain, gates, journal) + `tests/test_offline_chain.py`
**Status:** ready-for-review by the keeper. Never claims his review.

## What the upload was

A "hybrid offline-first assistant MVP" scaffold: docker-compose wiring four
services (FastAPI backend, React/Vite frontend, Ollama local model, Qdrant
vector store) plus SQLite interaction logging, a scheduled batch fine-tune
loop (export redacted JSONL → optional LoRA), and per-request cloud/sync
opt-in checkboxes in the UI.

The core idea — the keeper's own — is the **offline-first answer chain**:
answer locally first; escalate to cloud only when local confidence is low
AND both a global flag and a per-request opt-in agree; scrub secrets before
anything is stored or sent; keep a local interaction log with retention and
a redacted export for fine-tuning.

## State assessment (as received)

- **Working pattern:** `router.py` — confidence-threshold escalation with
  the dual gate (`cloud_allowed(global, request)`), redaction before
  logging, interaction log schema. Sound doctrine, thin implementation.
- **Stubbed by design:** `openai_stub.py`, `azure_openai_stub.py` return
  canned "not configured" text. Correct to keep as stubs.
- **Broken/incomplete (fixed in the working copy):**
  - `LOG_RETENTION_DAYS` was configured but **never enforced** — the log
    grew forever. Now enforced at startup (`purge_old_logs`) and via
    `POST /purge`.
  - `rag.py` let a Qdrant outage **crash the chat path** — the opposite of
    offline-first. `retrieve()`/`ingest_file()` now degrade to empty
    context / skip with a warning, never raise.
  - `ingest.py` restarted point IDs at 1 on every run (silent overwrite);
    now uses deterministic uuid5 ids — re-ingest is idempotent.
  - `main.py` used deprecated `@app.on_event` and CORS `allow_origins=["*"]`
    **with credentials** (browsers reject this; insecure). Now lifespan +
    localhost-only origins.
  - `scheduler.py` crashed on malformed cron, used hardcoded `/app/data`
    paths, swallowed no errors. Now validates, logs, paths from settings.
  - `privacy.py` redaction covered only 3 patterns (missed email, phone,
    IPv4, tokens). Now v2 with broader patterns; date-safe phone regexes
    (does not eat `2026-09-17`).
  - `/feedback` existed in the API but **nothing returned the interaction
    id**, so the UI couldn't use it. Router now returns `interaction_id`;
    the frontend has error handling + 👍/👎 feedback buttons wired to it.
  - `config.py` class-based `Config` (pydantic deprecation) → `model_config`.
  - Chunking moved to stdlib-only `app/text.py` so it is testable without
    the vector stack.
  - `backend/tests/` added: **32 tests green** (privacy gates, chunking,
    router escalation matrix with fake adapters, RAG degradation,
    retention purge). Run: `python -m pytest tests/` (venv with
    fastapi/sqlalchemy/pydantic at `~/workspace/.venv-offline`).

## What was applied LEVI-native (recreation, not copy)

Per the revival laws, docker/ollama/qdrant pieces are **study-only** — none
of that stack enters the repo. What enters is the pattern, rebuilt
LEVI-native under `core/levi/offline/` (stdlib-only):

- `chain.py` — `Offliner`: local-first answer chain. Any `Backend` goes in
  (LEVIs own `levi.rag` pipeline can be wrapped as one); `RuleBackend` is
  the honest local stub — it says when it has no context and reports low
  confidence instead of guessing. No sentience claims anywhere.
- `gates.py` — `GatePolicy`: the dual gate as standing keeper policy
  (`keeper_allows_cloud`, threshold, retention). One gate alone never
  opens the wire.
- `journal.py` — `Journal`: sqlite3 interaction log (stdlib), retention
  purge that is actually enforced, redacted JSONL export.
- Reuse, not duplication: scrubbing goes through LEVI's own
  `levi.growth.redact.redact_text`; local recall stays in
  `levi.memory.retrieval` / `levi.rag`. This package holds **no** second
  redactor and **no** vector store of its own.
- `__main__.py` — `python -m levi.offline status|demo|journal-demo`.
- Tests: `tests/test_offline_chain.py`, **11 tests green** (gate matrix,
  escalation receipts, scrubbing before backend/disk, journal purge/export).

## Doctrine notes for the keeper

- The dual gate is the whole doctrine: keeper policy × per-call consent.
  This package defaults to local-only; cloud requires his word *and* the
  call's yes.
- Receipts, not vibes: every chain run returns a `ChainReceipt` naming
  which backend answered, why escalation was granted/denied, and whether
  redaction changed the prompt.

## Honest gaps

- The docker stack was **never run here** (no docker/ollama in scope);
  the Ollama adapter, live Qdrant ingest, and the React build are
  untested against real services. Backend logic is tested with fakes.
- `lora_finetune.py` is syntax-checked only (needs torch/peft + a base
  model); the scheduler path is export-only without one.
- Cloud adapters remain stubs by design — escalation currently lands on
  an honest "not configured" message.
- Redaction is heuristic regex (shared LEVI gate); unusual phrasings can
  slip through. Double-scrubbed (log time + export time) as practice.
- `docs/` report is this file only; no other docs touched.
