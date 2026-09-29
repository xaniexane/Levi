# Factory spec — listing-drafter (provisional)

- **Spec ID:** `genesis-024`
- **Kind:** `skill`
- **Source:** Chauncey's order 2026-09-25 (more agents and skills)
- **Created:** 2026-09-25T05:25:00Z
- **Status:** queued
- **Builder glyph:** 🧵

## Intake
- **Working title:** listing-drafter — provisional; final name is Chauncey's word (naming sovereignty).
- **Rationale:** Drafts marketplace listing copy from photo + keywords; drafts only, never posts.

## Laws (declared before code)
1. Condition described from what is visible/said — never assumed.
2. Prices are projections labeled as projections.
3. Every draft ends with the approval gate.
4. Never posts a listing or contacts a buyer.

## Guard
- registry_hooks.mint_skill("factory.listing_drafter"): registered, category "factory", risk info, no permissions, requires_confirmation False.
- Playbook body carries `## Laws` and states its limits ("never").

## Prove
- pytest from zero: tests/test_factory_genesis_skills.py::test_skill_listing_drafter
- Registry proof: registry_hooks.mint_skill("factory.listing_drafter") returns verified=True.

## Provenance (Section 0)
- Playbook: core/levi/skill/playbooks/factory/listing-drafter.md (INFO risk, advisory/read-only).
