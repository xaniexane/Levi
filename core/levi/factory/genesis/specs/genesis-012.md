# Factory spec — ledgerwarden (provisional)

- **Spec ID:** `genesis-012`
- **Kind:** `agent`
- **Source:** Chauncey's order 2026-09-25 (more agents and skills)
- **Created:** 2026-09-25T05:25:00Z
- **Status:** queued
- **Builder glyph:** 🧵

## Intake
- **Working title:** ledgerwarden — provisional; final name is Chauncey's word (naming sovereignty).
- **Rationale:** Watches the DDD deposits ledger for expected-vs-received gaps; advisory-only, never claims revenue.

## Laws (declared before code)
1. Reads ledger JSONL read-only; reports expected vs received side by side.
2. Never confirms a deposit or claims revenue.
3. Expected and received are never summed or conflated.
4. Provisional name; final name is Chauncey's word.

## Guard
- registry_hooks.mint_agent(LedgerWarden): agent_id/agent_id, generation == 2, commissioned_by == "factory-genesis", first_task() returns a non-empty dict.
- All first-task methods return data only (text/dicts); no mutations, no sends, no posts.

## Prove
- pytest from zero: tests/test_factory_genesis_agents.py::test_agent_ledgerwarden
- Registry proof: registry_hooks.mint_agent(LedgerWarden) returns verified=True.

## Provenance (Section 0)
- core/levi/dynasty/wave/ledgerwarden.py carries the Section 0 IP block and Date of Invention 2026-09-25.
