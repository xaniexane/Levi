# Factory receipt — intake-triage

- **Spec ID:** `genesis-001`
- **Kind:** `skill`
- **Minted:** 2026-09-24T16:20:00Z
- **Builder glyph:** 🌊 (coordinator-built proof-of-run)
- **Final name status:** provisional — awaits Chauncey's word

## Spec
- Source: factory bootstrap (coordinator 🌊)
- Laws declared: 3 (valid frontmatter + id scheme; registry category/risk; advisory-only)

## Build
- `core/levi/skill/playbooks/factory/intake-triage.md` — playbook, INFO risk
- `core/levi/skill/factory_skills.py` — data-driven loader, `FACTORY_SKILLS`
- `core/levi/skill/registry.py` — wired into `SkillRegistry.__init__`
- `tests/test_factory_skills.py` — 4 tests
- Commits: (see commit below)
- Glyph trailer verified: yes

## Proof
- Tests: `tests/test_factory_skills.py` — 4/4 passed
- Neighbor suite: `tests/test_operator_skills.py` — 8/8 passed (registry edit is safe)
- Registry verification: `mint_skill('factory.intake_triage')` → verified True,
  category `factory`, risk 0; registry total 1220 → 1221 skills
- Laws proved: 3/3

## Registry
- Skill: registered as `factory.intake_triage` in category `factory`
- Note: category `factory` is shared with the WriteBuild fusion pipeline's
  10 skills (no id collision; distinct `factory.*` ids)

## Gated (still needs his word)
- Final skill name (naming sovereignty)

## Notes
- Read-only advisory skill: reads the intake queue, reports status; dispatches
  nothing, mutates nothing.
