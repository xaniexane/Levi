# Factory spec — receipt-audit (provisional)

- **Spec ID:** `genesis-023`
- **Kind:** `skill`
- **Source:** Chauncey's order 2026-09-25 (more agents and skills)
- **Created:** 2026-09-25T05:25:00Z
- **Status:** queued
- **Builder glyph:** 🧵

## Intake
- **Working title:** receipt-audit — provisional; final name is Chauncey's word (naming sovereignty).
- **Rationale:** Audits a factory receipt for completeness against the receipt format.

## Laws (declared before code)
1. Never marks a receipt complete with a required section missing.
2. Never invents test counts — read them from the run.
3. Never fabricates a commit hash — checks git log.
4. Never edits a receipt to pass the audit.

## Guard
- registry_hooks.mint_skill("factory.receipt_audit"): registered, category "factory", risk info, no permissions, requires_confirmation False.
- Playbook body carries `## Laws` and states its limits ("never").

## Prove
- pytest from zero: tests/test_factory_genesis_skills.py::test_skill_receipt_audit
- Registry proof: registry_hooks.mint_skill("factory.receipt_audit") returns verified=True.

## Provenance (Section 0)
- Playbook: core/levi/skill/playbooks/factory/receipt-audit.md (INFO risk, advisory/read-only).
