# Factory spec — receiptclerk (provisional)

- **Spec ID:** `genesis-019`
- **Kind:** `agent`
- **Source:** Chauncey's order 2026-09-25 (more agents and skills)
- **Created:** 2026-09-25T05:25:00Z
- **Status:** queued
- **Builder glyph:** 🧵

## Intake
- **Working title:** receiptclerk — provisional; final name is Chauncey's word (naming sovereignty).
- **Rationale:** Verifies receipt hash-chain integrity and reports breaks; read-only.

## Laws (declared before code)
1. One receipt per registered item is the target; missing named.
2. Read-only; fabricates nothing.
3. Reports carry the check method.
4. Provisional name; final name is Chauncey's word.

## Guard
- registry_hooks.mint_agent(ReceiptClerk): agent_id/agent_id, generation == 2, commissioned_by == "factory-genesis", first_task() returns a non-empty dict.
- All first-task methods return data only (text/dicts); no mutations, no sends, no posts.

## Prove
- pytest from zero: tests/test_factory_genesis_agents.py::test_agent_receiptclerk
- Registry proof: registry_hooks.mint_agent(ReceiptClerk) returns verified=True.

## Provenance (Section 0)
- core/levi/dynasty/wave/receiptclerk.py carries the Section 0 IP block and Date of Invention 2026-09-25.
