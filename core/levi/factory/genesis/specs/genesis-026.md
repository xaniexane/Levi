# Factory spec — signal-triage (provisional)

- **Spec ID:** `genesis-026`
- **Kind:** `skill`
- **Source:** Chauncey's order 2026-09-25 (more agents and skills)
- **Created:** 2026-09-25T05:25:00Z
- **Status:** queued
- **Builder glyph:** 🧵

## Intake
- **Working title:** signal-triage — provisional; final name is Chauncey's word (naming sovereignty).
- **Rationale:** Deterministic 1-10 triage of demand signals; no invented scores.

## Laws (declared before code)
1. Never invents a signal — every triaged signal is cited.
2. Never inflates a score — the number follows the rules.
3. Triage advises; it never decides.
4. Never acts on a signal; never posts or publishes.

## Guard
- registry_hooks.mint_skill("factory.signal_triage"): registered, category "factory", risk info, no permissions, requires_confirmation False.
- Playbook body carries `## Laws` and states its limits ("never").

## Prove
- pytest from zero: tests/test_factory_genesis_skills.py::test_skill_signal_triage
- Registry proof: registry_hooks.mint_skill("factory.signal_triage") returns verified=True.

## Provenance (Section 0)
- Playbook: core/levi/skill/playbooks/factory/signal-triage.md (INFO risk, advisory/read-only).
