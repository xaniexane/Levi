# Factory spec — launch-gatekeeper (provisional)

- **Spec ID:** `genesis-029`
- **Kind:** `skill`
- **Source:** Chauncey's order 2026-09-25 (more agents and skills)
- **Created:** 2026-09-25T05:25:00Z
- **Status:** queued
- **Builder glyph:** 🧵

## Intake
- **Working title:** launch-gatekeeper — provisional; final name is Chauncey's word (naming sovereignty).
- **Rationale:** Checks DDD launch-kit gates: PENDING vs APPROVED; reports what still needs Chauncey.

## Laws (declared before code)
1. Reports gates; never opens one.
2. PENDING means pending — never implies approval.
3. Approval is Chauncey's word alone.
4. Never launches anything or moves kit items.

## Guard
- registry_hooks.mint_skill("factory.launch_gatekeeper"): registered, category "factory", risk info, no permissions, requires_confirmation False.
- Playbook body carries `## Laws` and states its limits ("never").

## Prove
- pytest from zero: tests/test_factory_genesis_skills.py::test_skill_launch_gatekeeper
- Registry proof: registry_hooks.mint_skill("factory.launch_gatekeeper") returns verified=True.

## Provenance (Section 0)
- Playbook: core/levi/skill/playbooks/factory/launch-gatekeeper.md (INFO risk, advisory/read-only).
