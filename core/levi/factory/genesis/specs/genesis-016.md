# Factory spec — proofclerk (provisional)

- **Spec ID:** `genesis-016`
- **Kind:** `agent`
- **Source:** Chauncey's order 2026-09-25 (more agents and skills)
- **Created:** 2026-09-25T05:25:00Z
- **Status:** queued
- **Builder glyph:** 🧵

## Intake
- **Working title:** proofclerk — provisional; final name is Chauncey's word (naming sovereignty).
- **Rationale:** Re-runs factory module tests and reports green/red; read-only, changes nothing.

## Laws (declared before code)
1. Reports only what test files declare; never claims a run happened.
2. Read-only; changes nothing.
3. Status reports carry the inventory method.
4. Provisional name; final name is Chauncey's word.

## Guard
- registry_hooks.mint_agent(ProofClerk): agent_id/agent_id, generation == 2, commissioned_by == "factory-genesis", first_task() returns a non-empty dict.
- All first-task methods return data only (text/dicts); no mutations, no sends, no posts.

## Prove
- pytest from zero: tests/test_factory_genesis_agents.py::test_agent_proofclerk
- Registry proof: registry_hooks.mint_agent(ProofClerk) returns verified=True.

## Provenance (Section 0)
- core/levi/dynasty/wave/proofclerk.py carries the Section 0 IP block and Date of Invention 2026-09-25.
