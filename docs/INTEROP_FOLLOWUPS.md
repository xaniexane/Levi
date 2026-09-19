# INTEROP follow-ups — patches that require editing existing files

Builder B (interpenetration glue) is additive-only: it may not modify any
existing file. The adapters are built and tested; the entries below are the
precise, minimal patches that *adopt* them inside the existing modules.
Each entry names the file, the exact location/function, a 3-line patch
sketch, and why it is deferred.

---

## F1. bot `research-brief` adopts `research_brief_rag` — LANDED 2026-09-18

- **File:** `core/levi/bot/services.py`
- **Location:** `_handle_research_brief`, after the `LEVI_BOT_OFFLINE`
  check, before the agent-runtime fallback import.
- The patch opens a default `MemoryStore` lazily and calls
  `research_brief_rag(topic, store)`; on `ok` it returns the cited
  report directly (citations as `notes`), otherwise falls through to
  the existing agent-runtime path. RAG failures never raise into the
  fallback; the `ServiceResult` contract is unchanged.
- Tests: `tests/test_interop_f1_research_brief.py` (4).

## F2. `agent/chat.py` adopts `load_user_context_retrieved` — LANDED 2026-09-18

- **File:** `core/levi/agent/chat.py` (`ConversationManager.turn()`).
- `chat.py` had no per-turn user-context loading path, so the landing
  created one: each turn now calls
  `load_user_context_retrieved(store=None, query=user_message, limit=8)`
  and injects a non-empty block into the turn's system prompt
  ("What LEVI remembers about the user…"). Kill switch:
  `LEVI_CHAT_USER_CONTEXT=0`. The adapter is lazy-imported and
  guarded — a retrieval failure can never break a turn.
- Tests: `tests/test_interop_f2_chat_context.py` (5).

## F3. growth `cycle.py` calls `consume_pending_learnings` — LANDED 2026-09-18

- **File:** `core/levi/growth/cycle.py` (`run_cycle()`, start of harvest).
- Calls `consume_pending_learnings(default_queue_path(), journal)` (the
  cycle's already-imported `journal` module exposes `append_entry`);
  the summary lands in `report["pending_learnings"]`. Skipped under
  `dry_run` (dry runs never write); the call can never break the cycle.
- Tests: `tests/test_interop_f3_growth_queue.py` (4).

## F4. academy session flow writes concepts to memory

- **File:** `core/levi/academy/run_session.py` (or `concepts.py`
  `register_session`, wherever a session's concepts are finalized)
- **Location:** after `extract_concepts(...)` returns the session's concept
  list.
- **Patch sketch:**
  ```python
  from levi.interop.adapters.academy_memory import concepts_to_memory_entries

  for entry in concepts_to_memory_entries(concepts):
      memory_store.new_entry(**entry)  # or the store's public write API
  ```
- **Why deferred:** requires editing the academy package, and the exact
  public write API (`new_entry` signature) should be confirmed against
  `levi/memory/store.py` at patch time. The transform itself is pure and
  fully tested.

## F5. knowledge ingestion consumes bounty corpus units

- **File:** `core/levi/knowledge/` ingest path (security catalog ingest;
  check `knowledge/security/__init__.py` for the public ingest entrypoint)
- **Location:** wherever dated corpus units are ingested.
- **Patch sketch:**
  ```python
  from levi.interop.adapters.bounty_knowledge import findings_to_corpus_units

  units = findings_to_corpus_units(FindingStore().list())  # dicts via .to_dict()
  ingest_units(units)  # the knowledge layer's existing ingest API
  ```
- **Why deferred:** requires editing the knowledge package, and the ingest
  entrypoint's exact name/signature must be confirmed at patch time. The
  transform is pure, tested, and carries full provenance per unit.

## F6. risk-ceiling enforcement at composition boundaries

- **Files:** `core/levi/bot/services.py` (service dispatch),
  `core/levi/agent/loop.py` (subtask composition), and Builder A's
  `core/levi/organs/**` (organ orchestration)
- **Location:** each place where two or more modules' outputs are combined
  into one action presented to the user.
- **Patch sketch:**
  ```python
  from levi.interop.risks import compose_risk
  ceiling = compose_risk({"name": "bot", "risk": bot_risk},
                         {"name": "rag", "risk": rag_risk})["ceiling"]
  proposal = ActionProposal(..., risk_level=ceiling, ...)  # gates enforce it
  ```
- **Why deferred:** requires editing multiple existing modules and a
  product decision about which compositions are risk-bearing. The ceiling
  machinery (`ceiling`, `compose_risk`) is built, tested, and ready.

## F7. registry `check_all()` in CI / boot self-check — LANDED 2026-09-18

- **CI:** `.github/workflows/ci.yml`, python job, new step after the root
  pytest suite: `python3 -c "from levi.interop.registry import
  check_all; check_all(); print('registry check_all OK')"`. Cheap
  (<1s), fail-fast.
- **Daemon boot self-check:** no sibling owned the daemon boot path, so
  it landed: `core/levi/daemon/supervisor.py` gained an
  `interop-registry` health-check entry running `check_all()`. Broken
  wiring reports the service DOWN in `python -m levi.daemon pulse`
  instead of failing silently at runtime; the check is guarded like
  every other health check, so it can never raise into the supervisor.
  (Deliberately a DOWN report rather than a boot aborter — a bricked
  daemon fails open worse.)
- Tests: `tests/test_interop_f7_registry_ci.py` (5).
