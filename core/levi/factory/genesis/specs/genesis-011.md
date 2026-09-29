# Factory spec — watchtender (provisional)

- **Spec ID:** `genesis-011`
- **Kind:** `agent`
- **Source:** Chauncey's order 2026-09-25 (more agents and skills)
- **Created:** 2026-09-25T05:25:00Z
- **Status:** queued
- **Builder glyph:** 🧵

## Intake
- **Working title:** watchtender — provisional; final name is Chauncey's word (naming sovereignty).
- **Rationale:** Watches the DemandPulse watchlist and reports stalled or newly validated items; advisory-only.

## Laws (declared before code)
1. Watches the DemandPulse watchlist file; reports status counts honestly.
2. Never invents item states; absent file = zero items.
3. Advisory only: reports, never acts on watchlist items.
4. Provisional name; final name is Chauncey's word.

## Guard
- registry_hooks.mint_agent(WatchTender): agent_id/agent_id, generation == 2, commissioned_by == "factory-genesis", first_task() returns a non-empty dict.
- All first-task methods return data only (text/dicts); no mutations, no sends, no posts.

## Prove
- pytest from zero: tests/test_factory_genesis_agents.py::test_agent_watchtender
- Registry proof: registry_hooks.mint_agent(WatchTender) returns verified=True.

## Provenance (Section 0)
- core/levi/dynasty/wave/watchtender.py carries the Section 0 IP block and Date of Invention 2026-09-25.
