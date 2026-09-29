# Factory spec — nametender (provisional)

- **Spec ID:** `genesis-017`
- **Kind:** `agent`
- **Source:** Chauncey's order 2026-09-25 (more agents and skills)
- **Created:** 2026-09-25T05:25:00Z
- **Status:** queued
- **Builder glyph:** 🧵

## Intake
- **Working title:** nametender — provisional; final name is Chauncey's word (naming sovereignty).
- **Rationale:** Tracks provisional vs final names across canon and the factory; flags collisions for Chauncey's ruling.

## Laws (declared before code)
1. Lists every provisional working title on the line.
2. Flags duplicate titles for Chauncey's ruling.
3. Renames nothing, ever — naming is his word alone.
4. Provisional name; final name is Chauncey's word.

## Guard
- registry_hooks.mint_agent(NameTender): agent_id/agent_id, generation == 2, commissioned_by == "factory-genesis", first_task() returns a non-empty dict.
- All first-task methods return data only (text/dicts); no mutations, no sends, no posts.

## Prove
- pytest from zero: tests/test_factory_genesis_agents.py::test_agent_nametender
- Registry proof: registry_hooks.mint_agent(NameTender) returns verified=True.

## Provenance (Section 0)
- core/levi/dynasty/wave/nametender.py carries the Section 0 IP block and Date of Invention 2026-09-25.
