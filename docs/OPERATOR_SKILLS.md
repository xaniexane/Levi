# Operator Skills

Seven productivity playbooks for LEVI, registered in the `SkillRegistry`
under `category="operator"`. They are advisory-only: no system actions, no
surveillance, no coercion. Every skill is INFO risk.

Since the 2026-09-29 signature-recipe run, the pack is five **composite**
playbooks (each chaining absorbed originals into one higher-order skill)
plus two standalone originals. The 16 absorbed 2026-09-18 originals are
preserved byte-identical under `stored/2026-09-29-operator-playbooks/`
with a provenance note — stored, never deleted, regenerable on demand.

Registration is data-driven — `core/levi/skill/operator_skills.py` scans
`core/levi/skill/playbooks/operator/*.md` at import, so new playbooks
register automatically with zero merge conflicts. Skill IDs are namespaced
`operator.<slug>`.

| Skill ID | Name | Purpose | When to use |
|---|---|---|---|
| `operator.day` | Run the Day | The daily operating stack: vital few → triage → the three → deep block. | Morning planning; full plate; before the hardest work. |
| `operator.loop` | The Shipping Loop | Ship the work, close the day honestly, keep the streak alive. | "Almost done" drag; end of day; building a daily practice. |
| `operator.create` | Make the Thing | Generate fast, cut ruthlessly, calibrate the voice, name it. | Starting anything creative; bloated drafts; pre-publish. |
| `operator.decide` | Unstick and Rule | Classify the blocker, stress-test the plan, rule like a judge. | Stuck with no analysis; vague plans; colliding claims. |
| `operator.commit` | Commitments That Hold | Owned, dated commitments with a check-in that keeps them alive. | After meetings; intentions that must survive your future self. |
| `operator.no` | One Clean Decline | Say no well — cleanly, briefly, finally. | Requests you won't take on; protecting the vital few. |
| `operator.xyz` | X + Y = Z | Solve for the how from the endpoints: x inventory, z destination, y derived. | Any new directive; unknown how; stalled plans. |

## How they compose

The composites are the chains, formalized: `operator.day` runs
eighty→triage→mvd→deep; `operator.loop` runs ship→review→streak;
`operator.create` runs spark→cut→voice→title; `operator.decide` runs
blocker→stress→gavel; `operator.commit` merges actions×lock.
`operator.no` defends the whole system; `operator.xyz` derives the how for
any of them.

Symbolic notation used in the pack (DaVinci glyph compression, 2026-09-29):
`→` = phase chain, `×` = merge/interpenetration, `⇐` = source echo
(composite → absorbed originals), ①②③④ = phase order.

## Frontmatter contract

Each playbook carries a mandatory frontmatter block (stdlib-parsed):

```yaml
skill_id: operator.<slug>   # must match the filename
name: Human Readable Title
description: Single-sentence description.
risk: info
permissions: []
requires_confirmation: false
tags: [tag1, tag2]
version: 1.0.0
```

Every body has four sections: Purpose, When to use, Steps, Honesty notes.
