# Factory spec — specsmith (provisional)

- **Spec ID:** `genesis-015`
- **Kind:** `agent`
- **Source:** Chauncey's order 2026-09-25 (more agents and skills)
- **Created:** 2026-09-25T05:25:00Z
- **Status:** queued
- **Builder glyph:** 🧵

## Intake
- **Working title:** specsmith — provisional; final name is Chauncey's word (naming sovereignty).
- **Rationale:** Drafts factory specs from queued intake lines; never dispatches builders.

## Laws (declared before code)
1. Laws declared before code in every draft.
2. Drafts are text only; never dispatches builders.
3. Queue never mutated by the smith.
4. Provisional name; final name is Chauncey's word.

## Guard
- registry_hooks.mint_agent(SpecSmith): agent_id/agent_id, generation == 2, commissioned_by == "factory-genesis", first_task() returns a non-empty dict.
- All first-task methods return data only (text/dicts); no mutations, no sends, no posts.

## Prove
- pytest from zero: tests/test_factory_genesis_agents.py::test_agent_specsmith
- Registry proof: registry_hooks.mint_agent(SpecSmith) returns verified=True.

## Provenance (Section 0)
- core/levi/dynasty/wave/specsmith.py carries the Section 0 IP block and Date of Invention 2026-09-25.
