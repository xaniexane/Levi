# Factory spec — inboxtender (provisional)

- **Spec ID:** `genesis-020`
- **Kind:** `agent`
- **Source:** Chauncey's order 2026-09-25 (more agents and skills)
- **Created:** 2026-09-25T05:25:00Z
- **Status:** queued
- **Builder glyph:** 🧵

## Intake
- **Working title:** inboxtender — provisional; final name is Chauncey's word (naming sovereignty).
- **Rationale:** Watches operator inbox/outbox files for need hypotheses; drafts only, never sends.

## Laws (declared before code)
1. Reports new inbox/outbox items by name from the paths themselves.
2. Hypotheses drafted as text; never sent or acted on.
3. Nothing mutated in the inbox.
4. Provisional name; final name is Chauncey's word.

## Guard
- registry_hooks.mint_agent(InboxTender): agent_id/agent_id, generation == 2, commissioned_by == "factory-genesis", first_task() returns a non-empty dict.
- All first-task methods return data only (text/dicts); no mutations, no sends, no posts.

## Prove
- pytest from zero: tests/test_factory_genesis_agents.py::test_agent_inboxtender
- Registry proof: registry_hooks.mint_agent(InboxTender) returns verified=True.

## Provenance (Section 0)
- core/levi/dynasty/wave/inboxtender.py carries the Section 0 IP block and Date of Invention 2026-09-25.
