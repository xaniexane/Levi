# Factory spec — competitor-brief (provisional; final name is Chauncey's word)

- **Spec ID:** `genesis-005`
- **Kind:** `skill`
- **Source:** DemandPulse signals (📡 scan upgrade 2026-09-24)
- **Status:** spec'd

## Purpose

Reads DemandPulse competitor state and writes a plain-speech competitor
brief (prices, tactics, user-base signals) for the morning brief. Pairs with
the hyper-aggressive scan upgrade. Advisory only: reads and reports; never
posts, never scrapes aggressively, invents nothing.

## Laws (invariants)

1. Data-driven playbook pack: `core/levi/skill/playbooks/factory/competitor-brief.md`
   carries valid frontmatter; `skill_id == factory.competitor_brief`;
   risk is `info`; category is always `factory`.
2. Polite reads stay polite: reads only keyless/public sources; never
   hammers; numbers are cited or labeled projection — never invented.
3. Never posts, publishes, replies, or writes anywhere (DemandPulse sensing
   discipline).
4. Carries the mandatory frontmatter block (all eight keys).

## Interface

- **Skill:** registry category `factory`; trigger — morning brief needs a
  competitor section; inputs — competitor state dict; outputs —
  plain-speech brief (prices, tactics, user-base signals); risk tags: `info`.

## Registry target

- Playbook: `core/levi/skill/playbooks/factory/competitor-brief.md`.
- Auto-registers via `levi.skill.factory_skills` scan.

## Proof plan

- `tests/test_factory_genesis_drain.py::test_skill_competitor_brief` —
  `mint_skill("factory.competitor_brief")` verifies registration, category,
  info risk.

## Out of scope

No aggressive scraping, no posting, no invented competitor numbers, no
spending, no final name.

## Builder

- Glyph: 🧵

---
*Provisional working title. Final name awaits Chauncey's word (naming sovereignty).*
