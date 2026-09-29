# Factory spec — deposit-tracker (provisional)

- **Spec ID:** `genesis-022`
- **Kind:** `skill`
- **Source:** Chauncey's order 2026-09-25 (more agents and skills)
- **Created:** 2026-09-25T05:25:00Z
- **Status:** queued
- **Builder glyph:** 🧵

## Intake
- **Working title:** deposit-tracker — provisional; final name is Chauncey's word (naming sovereignty).
- **Rationale:** Records/tracks expected deposits; projection vs confirmed never conflated.

## Laws (declared before code)
1. Never confirms a deposit — only ledger 'received' entries count.
2. Expected and received never summed or conflated.
3. No revenue claims: projections are projections.
4. Never writes or edits ledger entries.

## Guard
- registry_hooks.mint_skill("factory.deposit_tracker"): registered, category "factory", risk info, no permissions, requires_confirmation False.
- Playbook body carries `## Laws` and states its limits ("never").

## Prove
- pytest from zero: tests/test_factory_genesis_skills.py::test_skill_deposit_tracker
- Registry proof: registry_hooks.mint_skill("factory.deposit_tracker") returns verified=True.

## Provenance (Section 0)
- Playbook: core/levi/skill/playbooks/factory/deposit-tracker.md (INFO risk, advisory/read-only).
