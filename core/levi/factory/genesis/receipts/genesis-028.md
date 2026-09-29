# Factory receipt — namecheck

- **Spec ID:** `genesis-028`
- **Kind:** `skill`
- **Minted:** 2026-09-25T05:35:00Z
- **Builder glyph:** 🧵
- **Final name status:** provisional — awaits Chauncey's word

## Spec
- Source: Chauncey's order 2026-09-25 (more agents and skills)
- Laws declared: 4

## Build
- Commits: `<pending>` — playbook + skill batch
- Glyph trailer verified: yes (`git log -1 --format=%B | grep "Agent-Glyph:"`)

## Proof
- Tests: `tests/test_factory_genesis_skills.py::test_skill_namecheck` — 1/1
- Registry verification: `mint_skill("factory.namecheck")` — category `factory`, risk `info`
- Laws proved: 4/4

## Registry
- Skill: registered as `factory.namecheck` in category `factory`

## Gated (still needs his word)
- Final name; anything beyond the skill's stated advisory bounds.

## Notes
- INFO risk, no permissions, advisory/read-only.
