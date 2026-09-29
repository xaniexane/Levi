# Factory spec — stall-report (provisional)

- **Spec ID:** `genesis-030`
- **Kind:** `skill`
- **Source:** Chauncey's order 2026-09-25 (more agents and skills)
- **Created:** 2026-09-25T05:25:00Z
- **Status:** queued
- **Builder glyph:** 🧵

## Intake
- **Working title:** stall-report — provisional; final name is Chauncey's word (naming sovereignty).
- **Rationale:** Expanded factory line report with stall ages; read-only.

## Laws (declared before code)
1. Ages computed from the queue's own timestamps, never guessed.
2. Never reorders or reprioritizes the queue.
3. Never mutates the queue or marks items done.
4. Never invents reasons for a stall.

## Guard
- registry_hooks.mint_skill("factory.stall_report"): registered, category "factory", risk info, no permissions, requires_confirmation False.
- Playbook body carries `## Laws` and states its limits ("never").

## Prove
- pytest from zero: tests/test_factory_genesis_skills.py::test_skill_stall_report
- Registry proof: registry_hooks.mint_skill("factory.stall_report") returns verified=True.

## Provenance (Section 0)
- Playbook: core/levi/skill/playbooks/factory/stall-report.md (INFO risk, advisory/read-only).
