# Factory spec — briefscribe (provisional)

- **Spec ID:** `genesis-013`
- **Kind:** `agent`
- **Source:** Chauncey's order 2026-09-25 (more agents and skills)
- **Created:** 2026-09-25T05:25:00Z
- **Status:** queued
- **Builder glyph:** 🧵

## Intake
- **Working title:** briefscribe — provisional; final name is Chauncey's word (naming sovereignty).
- **Rationale:** Drafts plain-speech morning-brief summaries from the alert outbox; never sends anything.

## Laws (declared before code)
1. Drafts plain-speech briefs from what is actually in the outbox.
2. Nothing invented: counts and highlights only.
3. Never sends, posts, or publishes.
4. Provisional name; final name is Chauncey's word.

## Guard
- registry_hooks.mint_agent(BriefScribe): agent_id/agent_id, generation == 2, commissioned_by == "factory-genesis", first_task() returns a non-empty dict.
- All first-task methods return data only (text/dicts); no mutations, no sends, no posts.

## Prove
- pytest from zero: tests/test_factory_genesis_agents.py::test_agent_briefscribe
- Registry proof: registry_hooks.mint_agent(BriefScribe) returns verified=True.

## Provenance (Section 0)
- core/levi/dynasty/wave/briefscribe.py carries the Section 0 IP block and Date of Invention 2026-09-25.
