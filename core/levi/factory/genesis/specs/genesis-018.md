# Factory spec — dealspotter (provisional)

- **Spec ID:** `genesis-018`
- **Kind:** `agent`
- **Source:** Chauncey's order 2026-09-25 (more agents and skills)
- **Created:** 2026-09-25T05:25:00Z
- **Status:** queued
- **Builder glyph:** 🧵

## Intake
- **Working title:** dealspotter — provisional; final name is Chauncey's word (naming sovereignty).
- **Rationale:** Scans RSS/signal sources for demand signals; sensing only, never posts.

## Laws (declared before code)
1. Signals cited from actual sources, never invented.
2. Sensing only: never posts, publishes, replies, or writes.
3. Reports counts with sources attached.
4. Provisional name; final name is Chauncey's word.

## Guard
- registry_hooks.mint_agent(DealSpotter): agent_id/agent_id, generation == 2, commissioned_by == "factory-genesis", first_task() returns a non-empty dict.
- All first-task methods return data only (text/dicts); no mutations, no sends, no posts.

## Prove
- pytest from zero: tests/test_factory_genesis_agents.py::test_agent_dealspotter
- Registry proof: registry_hooks.mint_agent(DealSpotter) returns verified=True.

## Provenance (Section 0)
- core/levi/dynasty/wave/dealspotter.py carries the Section 0 IP block and Date of Invention 2026-09-25.
