# LEVI Bloodstream

The **bloodstream** is the one-turn pipeline of the LEVI organism. It is not a
new psychology and not new physics — it is the wiring that carries one user
text through every strand in DNA order:

```
USER TEXT
  │
  ▼
┌─────────────────┐
│ 1. companion_ei │  Companion + 5D EI (levi.affect)
│                 │  Observe the turn's affect. UX/state shaping only —
│                 │  never sentience, never overrides safety/facts/permission.
└────────┬────────┘
         ▼
┌─────────────────┐
│ 2. persona      │  Persona lens (levi.persona)
│                 │  Special behaviors: interrogation ⊥ no_hero.
│                 │  At most ONE fires per turn — enforced here, never mixed.
│                 │  If one fires, the turn short-circuits (reply + memory + trace).
└────────┬────────┘
         ▼
┌─────────────────┐
│ 3. governor     │  L.W.P. graph + governor (levi.graph.lwp_primitives)
│                 │  Governor authorizes budget; CircuitBreaker refuses on overload.
│                 │  Effective risk = max(intent risk, composite ceiling).
└────────┬────────┘
         ▼
┌─────────────────┐
│ 4. route        │  Intent classification (deterministic, offline)
│                 │  constructive → FACTORY   (Software Factory cascade)
│                 │  what-ifs      → ORGAN     (Echoverse)
│                 │  decisions    → ORGAN     (Mandella)
│                 │  otherwise    → MODEL      (provider chain + specialists)
└────────┬────────┘
         ▼
┌─────────────────┐
│ 5. policy       │  Plan → Preview → Permission → Execute → Verify → Receipt
│                 │  (levi.bloodstream.gate — no bypass paths)
│                 │  Risk 0–1: auto-approved. Risk ≥ 2: HITL confirm required.
│                 │  No confirm channel → awaiting_permission, NEVER executed.
└────────┬────────┘
         ▼
┌─────────────────┐
│ 6. memory       │  One episodic entry per turn (levi.memory)
└────────┬────────┘
         ▼
┌─────────────────┐
│ 7. trace        │  One JSONL record per turn → ~/.levi/traces/YYYY-MM-DD.jsonl
└────────┬────────┘
         ▼
  promotion? — verified receipts only (graph/story promotion is eligible
  exactly when a verified policy receipt exists for the turn)
```

Run it: `levi turn "your text"`. It prints the reply plus a one-line
receipt summary: `[route] receipt <id>… · risk N · route <route> · provider <provider>`.

## Stage contracts

All stages speak the dataclasses in `levi.bloodstream.stages`:

- **`TurnContext`** — per-turn inputs (session, persona, provider, HITL
  `confirm` callback, `data_dir` override for hermetic tests, composite name,
  dry-run). Pure data; the pipeline never mutates it.
- **`StageRecord`** — `{stage, decision, detail}`; the pipeline appends one per
  stage in DNA order. Exact ordering is asserted in
  `core/levi/bloodstream/tests/test_stages.py`.
- **`TurnResult`** — the complete honest outcome: reply, route, behavior,
  persona, risk, receipt summary, trace id, policy receipt id,
  `awaiting_permission`, `promotion_eligible`, `ok`/`error`, and the stage list.

Exact stage order:

- normal turn: `companion_ei → persona → governor → route → policy → memory → trace`
- special-behavior turn: `companion_ei → persona → memory → trace`
- governor-refused turn: `companion_ei → persona → governor → route → memory → trace`
- failed turn: `... → failure → memory → trace` (failure composted via REIM)

### 1. companion_ei

`SessionEI.observe_user(text)` + `modulate()` + `evaluate()`. Records the
affect read (dominant, valence, arousal), policy decision (deescalate/crisis),
and suggested register. The 5D EI is UX/state: it modulates tone and
registers, never policy, facts, permission, or the route decision.

### 2. persona

`PersonaLattice` + `apply_special_behavior`. Guards:

- `interrogation` (persona flag `requires_explicit_answer_request`) and
  `no_hero` (flag `no_hero_mode`) are structurally distinct. At most one fires
  per turn. On a misconfigured both-flags persona, interrogation takes
  precedence and the conflict is recorded in the trace (`behavior_conflict`).
- A firing special behavior short-circuits: no governor, no model call, no
  policy receipt — the turn still writes memory + trace.

### 3. governor

`Governor` (budget) + `CircuitBreaker` (overload refusal) from
`levi.graph.lwp_primitives` — note: the L.W.P. primitives canonically live in
`levi.graph.lwp_primitives`, not under `core/levi/lwp/` (which holds the
Mirror Cascade / Opportunity Rail helpers).

Composite risk ceiling: if the context names a composite,
`CompositeRegistry.risk_ceiling()` computes the strictest (maximum) ceiling
across its persona (0 — lenses aren't authority), skills, specialists, and
automations. Effective turn risk = max(intent risk, composite ceiling).

### 4. route

Deterministic keyword classification (offline). Intent risk heuristics:

- external-send / financial language → HIGH (3)
- constructive (factory) → MODERATE (2)
- everything else → LOW (1)

### 5. policy

`levi.bloodstream.gate.run_gated` walks all six steps for every consequential
act. Permission: at/below the auto-approve ceiling → automatic; above it →
the context's `confirm` callback decides; no callback → the act is NOT
executed and the turn returns `awaiting_permission`. `dry_run` walks the gate
without executing and still issues a receipt for the preview. The executor
and verifier are route-specific:

- factory: `SoftwareFactory.create` / `factory.get(id) is not None`
- organ: `run_echo`/`format_echo` or `run_mandella`/`format_mandella`
- model: `run_subtask` with the provider chain (deterministic
  `LocalProvider` default; `levi-brain`/`levi-local` are explicit-only)

### 6. memory

One `EPISODIC` memory entry per turn (`source="bloodstream"`), tagged with
the route and persona. Failed turns additionally tag `compost-pending`.

### 7. trace

`TraceWriter` appends one JSONL record per turn. Every record carries all
`TRACE_FIELDS`: trace id, timestamp, session, text excerpt, stage decision
path, provider actually used (or `deterministic-local` / `special-behavior`),
skills invoked, policy receipt id, risk level, route, outcome, error, and the
compost record (failures only). The writer never raises into the turn.

## Composites (interpenetration)

A **composite** is a named, testable, reversible bundle:

```python
from levi.bloodstream.composites import Composite, CompositeRegistry

registry = CompositeRegistry()  # ~/.levi/bloodstream/composites.json
registry.register(
    Composite(
        name="ops",
        description="ops persona + tools",
        persona_id="mentor",
        skill_ids=["file_read", "shell_exec"],
        specialist_ids=["researcher"],
        automation_ids=["nightly_digest"],
    ),
    skills=...,
    specialists=...,
    automations=...,
)
```

- `register()` validates every part exists — fail fast, no dangling refs.
- `unregister(name)` removes it completely (reversible).
- `risk_ceiling(composite, ...)` = max risk across all parts (persona = 0).
- Use it in a turn: `levi turn --composite ops "..."`.

## Failure composting

If any stage raises, the turn never crashes the caller: the failure is
recorded, tagged `compost-pending` in memory, and its residue is routed to
the existing `LWPModelEngine.reim_forks()` (the REIM literary-fork facility
in `levi/lwp/model_engine.py` — routed to, not expanded; REIM/RIEM organs
are a later package). The compost record lands in the trace.

## Adding a stage

1. Add the stage name to the DNA order in `run_turn` (`core/levi/bloodstream/turn.py`).
2. Write a `_stage_*` function returning a `StageRecord` (and any artifacts).
3. Append the record in order; update `FULL_ORDER`/`SPECIAL_ORDER` in
   `core/levi/bloodstream/tests/test_stages.py`.
4. The trace picks it up automatically from `result.stages`.

Rules: stages are pure-ish functions of `(text, ctx, prior artifacts)`; they
must not execute consequential acts (those live inside the policy gate); they
must not raise into the turn (catch and record, or let the failure path
compost).

## Adding an organ

1. Implement `run_<organ>(...)` / `format_<organ>(...)` under `core/levi/organs/`
   (see `echo.py`, `mandella.py` — deterministic, bounded simulation only).
2. Add keyword hints to `_ORGAN` hint tuples and a branch in `_execute_organ`
   in `turn.py`.
3. Add a route test in `test_stages.py` asserting the organ's output marker in
   the reply.

## Interface notes (honest gaps)

- The L.W.P. primitives (`Governor`, `CircuitBreaker`, `CascadeChain`, …)
  live in `levi.graph.lwp_primitives`, not `core/levi/lwp/`. The bloodstream
  reuses the canonical location; don't duplicate them.
- `levi.orchestration.loop.Orchestrator` (used by `levi ask`) is an older,
  parallel pipeline. `levi turn` is the new bloodstream; `ask` is untouched.
  A future package may retire one.
- `PolicyEngine` has no `mark_executing` — the bloodstream preserves the
  six-step sequence through typed `StageRecord`s and only calls
  `mark_completed` after verification.
- Promotion currently means eligibility (`promotion_eligible` on verified
  receipt); the graph/story-fabric promotion writer is a later package.

## The event bus — one organism, one event stream (axis 2)

The turn pipeline is the bloodstream's *circulation*; the event bus
(`core/levi/bloodstream/bus.py`) is its *nervous system*. Subsystems hear
each other without coupling: growth publishes learnings, the archive
publishes ingestions, the hunt publishes findings, and every completed
turn publishes `levi.turn.completed` with its trace summary.

- **API** (stdlib-only, in-process pub/sub):
  `publish(topic, payload)`, `subscribe(topic, handler) -> token`,
  `unsubscribe(token)`, `topics()`.
- **Topic convention** (enforced): `levi.<subsystem>.<event>` —
  e.g. `levi.growth.learning`, `levi.archive.ingested`,
  `levi.hunt.finding`, `levi.turn.completed`. Bad names raise
  `ValueError`.
- **Payloads must be JSON-serializable** — validated, rejected otherwise
  (`TypeError`), because every publish appends to the trace.
- **Trace binding**: `publish()` writes an event record via `TraceWriter`
  only while a trace is active (`trace_scope(trace_id, base_dir)`). The
  turn pipeline opens the scope in `_finish()`, so each turn's trace file
  carries its `levi.turn.completed` event alongside the turn trace.
- **Handler isolation**: one failing subscriber never breaks the bus or
  the turn — failures are recorded in the trace event's
  `handler_errors`.

## Warehouses, not a tool belt

The organism's capabilities are organized as **warehouses**, not a flat
tool belt (`core/levi/interop/warehouses.py` — presentation over the
existing modules, no rewrites): Methods (40 forgotten techniques),
Revivals (20 reborn systems), Skills & Playbooks (823 defensive
blue-team playbooks), Archive Knowledge (the Smithsonian records),
Services (galaxy + daemon + perpetual), Games (standing theme, no stock
yet), Memory & Growth, Finance, Factory (the production line), and
Organism Core.

Each warehouse has a real, counted inventory manifest — `list_warehouses()`,
`browse_warehouse(name)`, `warehouse_inventory(name, limit, offset)`
(honest pagination: `total` is always the true count), and
`pull_from_shelf(warehouse, item_id)` (read-only lookup of one item's
full detail + how to invoke it; never executes). The capability atlas
(`levi.interop.atlas.export_atlas()`) groups modules under their
warehouses while keeping the flat module list for existing consumers.
See `docs/WAREHOUSES.md`.
