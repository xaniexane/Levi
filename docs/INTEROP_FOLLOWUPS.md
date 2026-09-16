# INTEROP follow-ups — patches that require editing existing files

Builder B (interpenetration glue) is additive-only: it may not modify any
existing file. The adapters are built and tested; the entries below are the
precise, minimal patches that *adopt* them inside the existing modules.
Each entry names the file, the exact location/function, a 3-line patch
sketch, and why it is deferred.

---

## F1. bot `research-brief` adopts `research_brief_rag`

- **File:** `core/levi/bot/services.py`
- **Location:** `_handle_research_brief` (around line 596), after the
  `LEVI_BOT_OFFLINE` check and before the `from levi.agent.loop import
  run_subtask` fallback.
- **Patch sketch:**
  ```python
  from levi.interop.adapters.bot_rag import research_brief_rag
  rag_brief = research_brief_rag(topic, store=None)  # store opened lazily inside
  if rag_brief["ok"]:
      return ServiceResult(ok=True, report=rag_brief["report"], notes=rag_brief["citations"])
  # else: fall through to the existing agent-runtime path
  ```
- **Why deferred:** requires editing `bot/services.py` (additive-only
  rule). Note: the current adapter takes an explicit `store`; the patch
  should open the default `MemoryStore` lazily (or thread the bot's
  existing store through) before this lands.

## F2. `agent/chat.py` adopts `load_user_context_retrieved`

- **File:** `core/levi/agent/chat.py` (the REPL / session-context builder;
  check where it calls `assistant.load_user_context`)
- **Location:** wherever the per-turn user-context block is assembled.
- **Patch sketch:**
  ```python
  from levi.interop.adapters.assistant_retrieval import load_user_context_retrieved
  ctx = load_user_context_retrieved(store, user_message, limit=8)
  block = ctx["block"]  # method is "hybrid" or "fallback"; both are honest
  ```
- **Why deferred:** requires editing `agent/chat.py`. Semantics are safe:
  the adapter never raises and degrades to today's exact behavior
  (`method="fallback"`) when retrieval is unavailable.

## F3. growth `cycle.py` calls `consume_pending_learnings`

- **File:** `core/levi/growth/cycle.py` (the harvest → reflect → consolidate
  → journal loop)
- **Location:** at the start of the harvest phase.
- **Patch sketch:**
  ```python
  from levi.interop.adapters.growth_learnings import consume_pending_learnings, default_queue_path
  from levi.growth import journal
  consumed = consume_pending_learnings(default_queue_path(), journal)
  # consumed["accepted"] learnings are now journaled; harvest continues as before
  ```
- **Why deferred:** requires editing `growth/cycle.py`. The adapter is
  idempotent (queue renamed to `.consumed-<ts>` before journaling), so
  double-harvests are safe even if the patch is applied twice.

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

## F7. registry `check_all()` in CI / boot self-check

- **File:** the CI workflow (`.github/workflows/ci.yml`) and/or the daemon
  boot sequence (`core/levi/daemon/...`)
- **Location:** test stage of CI; early boot of the daemon.
- **Patch sketch:**
  ```python
  from levi.interop.registry import check_all
  check_all()  # raises RegistryError on any broken provides/requires wiring
  ```
- **Why deferred:** requires editing CI config / daemon boot code. This
  turns the manifest into a living contract: any module that drops a
  capability its dependents require fails fast instead of failing
  silently at runtime.
