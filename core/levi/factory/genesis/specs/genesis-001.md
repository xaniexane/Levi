# Factory spec — intake-triage (provisional; final name is Chauncey's word)

- **Spec ID:** `genesis-001`
- **Kind:** `skill`
- **Source:** factory bootstrap (coordinator 🌊)
- **Status:** spec'd

## Purpose

The factory's first minted skill. Reads `core/levi/factory/genesis/intake/queue.jsonl`
and reports the line's status — counts per status, oldest unbuilt spec, what's
in proving — so the coordinator sees the line at a glance. Read-only:
it never mutates the queue and never dispatches builders.

## Laws (invariants)

1. The playbook carries valid frontmatter; `skill_id` is `factory.intake_triage`
   and matches the filename `intake-triage.md`.
2. The pack registers in `SkillRegistry` with `category == "factory"`,
   INFO risk, and a unique id.
3. Advisory only: the skill reads and reports. It dispatches nothing, mutates
   nothing, spends nothing.

## Interface

- **Skill:** registry category `factory`; trigger — coordinator asks "how's the
  line"; inputs — none (reads the queue path); outputs — status counts +
  oldest-waiting spec; risk tags: INFO.

## Registry target

- New data-driven pack: `core/levi/skill/playbooks/factory/*.md` +
  `core/levi/skill/factory_skills.py` exposing `FACTORY_SKILLS`,
  wired into `SkillRegistry.__init__` in `core/levi/skill/registry.py`.

## Proof plan

- `tests/test_factory_skills.py`: frontmatter valid, id scheme, registry
  contains `factory.intake_triage` with category `factory`, unique ids.
- Registry verification:
  `python3 -c "from levi.skill.registry import SkillRegistry;
  print('factory.intake_triage' in [s.id for s in SkillRegistry().list()])"`
  → `True`.

## Out of scope

No queue mutation, no builder dispatch, no external action, no money.

## Builder

- Glyph: 🌊 (coordinator-built proof-of-run)

---
*Provisional working title. Final name awaits Chauncey's word (naming sovereignty).*
