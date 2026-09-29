# Factory spec — namecheck (provisional)

- **Spec ID:** `genesis-028`
- **Kind:** `skill`
- **Source:** Chauncey's order 2026-09-25 (more agents and skills)
- **Created:** 2026-09-25T05:25:00Z
- **Status:** queued
- **Builder glyph:** 🧵

## Intake
- **Working title:** namecheck — provisional; final name is Chauncey's word (naming sovereignty).
- **Rationale:** Checks a provisional name against canon and the factory for collisions.

## Laws (declared before code)
1. Naming is Chauncey's word alone — advises, never names.
2. Never renames anything, even on a clear collision.
3. Near matches flagged, not judged.
4. Never invents canon entries to compare against.

## Guard
- registry_hooks.mint_skill("factory.namecheck"): registered, category "factory", risk info, no permissions, requires_confirmation False.
- Playbook body carries `## Laws` and states its limits ("never").

## Prove
- pytest from zero: tests/test_factory_genesis_skills.py::test_skill_namecheck
- Registry proof: registry_hooks.mint_skill("factory.namecheck") returns verified=True.

## Provenance (Section 0)
- Playbook: core/levi/skill/playbooks/factory/namecheck.md (INFO risk, advisory/read-only).
