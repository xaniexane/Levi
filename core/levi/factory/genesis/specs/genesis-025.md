# Factory spec — audit-runner (provisional)

- **Spec ID:** `genesis-025`
- **Kind:** `skill`
- **Source:** Chauncey's order 2026-09-25 (more agents and skills)
- **Created:** 2026-09-25T05:25:00Z
- **Status:** queued
- **Builder glyph:** 🧵

## Intake
- **Working title:** audit-runner — provisional; final name is Chauncey's word (naming sovereignty).
- **Rationale:** Runs info-only site checks (speed/SEO/broken-link/mobile); no posting, polite reads.

## Laws (declared before code)
1. Read-only: never submits forms, posts, or writes.
2. Polite: one request per page, no hammering.
3. Findings are observations, never guarantees.
4. Never runs against a site Chauncey has not named.

## Guard
- registry_hooks.mint_skill("factory.audit_runner"): registered, category "factory", risk info, no permissions, requires_confirmation False.
- Playbook body carries `## Laws` and states its limits ("never").

## Prove
- pytest from zero: tests/test_factory_genesis_skills.py::test_skill_audit_runner
- Registry proof: registry_hooks.mint_skill("factory.audit_runner") returns verified=True.

## Provenance (Section 0)
- Playbook: core/levi/skill/playbooks/factory/audit-runner.md (INFO risk, advisory/read-only).
