# Factory spec — budget-ledger-post (provisional)

- **Spec ID:** `genesis-027`
- **Kind:** `skill`
- **Source:** Chauncey's order 2026-09-25 (more agents and skills)
- **Created:** 2026-09-25T05:25:00Z
- **Status:** queued
- **Builder glyph:** 🧵

## Intake
- **Working title:** budget-ledger-post — provisional; final name is Chauncey's word (naming sovereignty).
- **Rationale:** Posts income records to the budget ledger with the required 'source' field.

## Laws (declared before code)
1. The 'source' field is required — a record without one is rejected.
2. Expected vs received never conflated or summed.
3. Never claims a projection as income.
4. Append-only: corrections are new records, never edits.

## Guard
- registry_hooks.mint_skill("factory.budget_ledger_post"): registered, category "factory", risk info, no permissions, requires_confirmation False.
- Playbook body carries `## Laws` and states its limits ("never").

## Prove
- pytest from zero: tests/test_factory_genesis_skills.py::test_skill_budget_ledger_post
- Registry proof: registry_hooks.mint_skill("factory.budget_ledger_post") returns verified=True.

## Provenance (Section 0)
- Playbook: core/levi/skill/playbooks/factory/budget-ledger-post.md (INFO risk, advisory/read-only).
