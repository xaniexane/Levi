# Factory spec — watch-summary (provisional)

- **Spec ID:** `genesis-021`
- **Kind:** `skill`
- **Source:** Chauncey's order 2026-09-25 (more agents and skills)
- **Created:** 2026-09-25T05:25:00Z
- **Status:** queued
- **Builder glyph:** 🧵

## Intake
- **Working title:** watch-summary — provisional; final name is Chauncey's word (naming sovereignty).
- **Rationale:** Summarizes the DemandPulse watchlist in plain speech; statuses only, no invented traction.

## Laws (declared before code)
1. Never invents an item's status — reports what the watchlist file says.
2. Absent watchlist file means zero items, said plainly.
3. No traction, revenue, or completion claims.
4. Never posts, publishes, replies, or writes anywhere.

## Guard
- registry_hooks.mint_skill("factory.watch_summary"): registered, category "factory", risk info, no permissions, requires_confirmation False.
- Playbook body carries `## Laws` and states its limits ("never").

## Prove
- pytest from zero: tests/test_factory_genesis_skills.py::test_skill_watch_summary
- Registry proof: registry_hooks.mint_skill("factory.watch_summary") returns verified=True.

## Provenance (Section 0)
- Playbook: core/levi/skill/playbooks/factory/watch-summary.md (INFO risk, advisory/read-only).
