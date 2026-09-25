# Prompt Chips

One-tap prompt injects: short, fixed prompts the user can fire with a single
tap instead of typing. They live as data in `core/levi/skill/chips.json`
(seven entries, each with `id`, `label`, `inject`), loaded at import by
`levi.skill.operator_skills.load_chips()`.

A chip is a shortcut into an operator skill's mechanism — the inject is the
prompt text sent as the user's message.

| Chip ID | Label | Inject | Invokes |
|---|---|---|---|
| `chip.cut-the-list` | Cut the list | "Triage the list I just gave you — half of it dies." | `operator.triage` |
| `chip.name-the-fear` | Name the fear | "In one sentence: what am I avoiding?" | `operator.blocker` (avoided class) |
| `chip.ship-minimum` | Ship minimum | "Define the smallest version worth shipping, then freeze it there." | `operator.ship` |
| `chip.hold-me-to-it` | Hold me to it | "Lock this in as a commitment and check in on me." | `operator.lock` |
| `chip.no-comfort` | No comfort | "No softening. Hold the standard." | Tone override for any skill |
| `chip.mirror` | Mirror | "Reflect my own stated priority back to me, word for word." | `operator.review` / `operator.mvd` |
| `chip.next-90` | Next 90 | "Show me only what matters in the next 90 minutes." | `operator.mvd` (compressed) |

## Contract

- Exactly 7 entries. Each has non-empty `id`, `label`, and `inject`.
- Chip IDs are namespaced `chip.<slug>`.
- Injects are written in LEVI's voice: direct, warm, no fluff.
- Chips are data, not skills — they are not registered in the
  `SkillRegistry`. UI surfaces consume them via `load_chips()`.

## Adding a chip

Append an object to `chips.json`, document it in the table above, and the
loader plus `tests/test_operator_skills.py` (which asserts the count is
exactly 7 — update the assertion when the set intentionally grows) pick it
up with no code changes.
