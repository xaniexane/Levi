# Factory spec — corpusminer (provisional)

- **Spec ID:** `genesis-014`
- **Kind:** `agent`
- **Source:** Chauncey's order 2026-09-25 (more agents and skills)
- **Created:** 2026-09-25T05:25:00Z
- **Status:** queued
- **Builder glyph:** 🧵

## Intake
- **Working title:** corpusminer — provisional; final name is Chauncey's word (naming sovereignty).
- **Rationale:** Cross-links corpus fragments (read-only); reports link candidates between unnamed fragments and named documents.

## Laws (declared before code)
1. Corpus is read-only; originals never modified.
2. Link candidates flagged as candidates, never asserted as fact.
3. Counts reported from the actual survey.
4. Provisional name; final name is Chauncey's word.

## Guard
- registry_hooks.mint_agent(CorpusMiner): agent_id/agent_id, generation == 2, commissioned_by == "factory-genesis", first_task() returns a non-empty dict.
- All first-task methods return data only (text/dicts); no mutations, no sends, no posts.

## Prove
- pytest from zero: tests/test_factory_genesis_agents.py::test_agent_corpusminer
- Registry proof: registry_hooks.mint_agent(CorpusMiner) returns verified=True.

## Provenance (Section 0)
- core/levi/dynasty/wave/corpusminer.py carries the Section 0 IP block and Date of Invention 2026-09-25.
