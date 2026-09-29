# Factory spec — mystery-box-pricer (provisional; final name is Chauncey's word)

- **Spec ID:** `genesis-003`
- **Kind:** `skill`
- **Source:** Chauncey's order 2026-09-24 (mystery box business in the factory mix)
- **Status:** spec'd

## Purpose

Mystery-box business support: prices a box's contents from listing drafts
and suggests the profitable bundle split. Advisory only — it reads listing
drafts and emits pricing guidance; it never lists anything for sale, never
contacts buyers, spends nothing.

## Laws (invariants)

1. Data-driven playbook pack: `core/levi/skill/playbooks/factory/mystery-box-pricer.md`
   carries valid frontmatter; `skill_id == factory.mystery_box_pricer`;
   risk is `info`; category is always `factory`.
2. Read-only with respect to the world: computes prices and bundle splits
   from supplied inputs only; invents no sold comps, no buyers, no revenue.
   All money math is labeled projection.
3. Never touches marketplaces, accounts, listings, or spending.
4. Carries the mandatory frontmatter block (skill_id, name, description,
   risk, permissions, requires_confirmation, tags, version).

## Interface

- **Skill:** registry category `factory`; trigger — asked to price a mystery
  box or split a bundle; inputs — item list with est. values; outputs —
  per-box price guidance + bundle-split suggestion; risk tags: `info`.

## Registry target

- Playbook: `core/levi/skill/playbooks/factory/mystery-box-pricer.md`.
- Auto-registers via `levi.skill.factory_skills` scan into `SkillRegistry`
  (no hand edit to `registry.py`).

## Proof plan

- `tests/test_factory_genesis_drain.py::test_skill_mystery_box_pricer` —
  `mint_skill("factory.mystery_box_pricer")` verifies registration,
  category, and info risk.
- CLI smoke: `python3 -c` registry list contains the id.

## Out of scope

No marketplace posting, no buyer contact, no pricing enforcement, no
spending, no final name (provisional until his word).

## Builder

- Glyph: 🧵
- Notes: keep the playbook plain-speech; projection math only.

---
*Provisional working title. Final name awaits Chauncey's word (naming sovereignty).*
