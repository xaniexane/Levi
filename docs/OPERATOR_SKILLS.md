# Operator Skills

Sixteen productivity playbooks for LEVI, registered in the `SkillRegistry`
under `category="operator"`. They are advisory-only: no system actions, no
surveillance, no coercion. Every skill is INFO risk.

Registration is data-driven — `core/levi/skill/operator_skills.py` scans
`core/levi/skill/playbooks/operator/*.md` at import, so new playbooks
register automatically with zero merge conflicts. Skill IDs are namespaced
`operator.<slug>`.

| Skill ID | Name | Purpose | When to use |
|---|---|---|---|
| `operator.stress` | Stress-Test the Plan | Red-team a plan before reality does: attack it, find every way it dies, harden what survives. | Before committing to a vague or high-stakes plan; when everyone agrees too fast. |
| `operator.eighty` | The Vital Few | Find the ~20% of work carrying ~80% of results, and produce an explicit stop-doing list. | Full plate; weekly planning; before adding anything new. |
| `operator.mvd` | Minimum Viable Day | Exactly three must-happen items for the day; everything else is bonus. | Morning planning; days at risk of dissolving into reactive work. |
| `operator.ship` | Define Done, Freeze Scope | Turn "almost done" into shipped: write the definition of done, freeze scope, execute. | "90% done" for too long; scope creep mid-flight. |
| `operator.lock` | Commitment + Watch | Convert an intention into a commitment with a deadline and a check-in. | Decisions that must survive your future self; after defining done. |
| `operator.triage` | NOW / NEXT / PARK / KILL | Sort a pile fast; every item gets exactly one bucket, and something must die. | Inbox or brain-dump overflow; "I'll get to it" as a storage strategy. |
| `operator.review` | Shipped / Slipped / Pattern / Tomorrow | Close the day honestly: what moved, what didn't, what it means, what's next. | End of day; end of week; after a streak breaks. |
| `operator.deep` | Sprint Design | Design one deep-work block that stays deep: one objective, a start ritual, a distraction contract. | Before focus-heavy work; when "I'll focus today" keeps dissolving. |
| `operator.blocker` | Hard / Unclear / Avoided | Name what's actually stuck: classify the blocker honestly, then apply its class fix. | "I'm stuck" with no analysis; a task that keeps getting rescheduled. |
| `operator.actions` | Owners + Deadlines | Turn notes and meetings into commitments: every action gets one owner and one deadline. | After meetings/calls/threads; pasted notes with implied actions. |
| `operator.no` | One Clean Decline | Say no well — cleanly, briefly, finally. | Requests you won't take on; protecting the vital few; resentful yeses. |
| `operator.streak` | Ship / Deep-Work Days | Track consecutive days of shipping or deep work — a mirror for consistency. | Building a daily practice; restarting after a break. |
| `operator.spark` | Creative Ignition | Generate raw creative material fast — quantity first, judgment later. | Starting anything creative; empty-page paralysis; before cutting. |
| `operator.cut` | Cut Ruthlessly | Improve by removing: whatever survives was load-bearing. | Bloated drafts/plans/lists; refining raw material. |
| `operator.voice` | Voice Calibration | Match the writing voice to the job the words must do. | Drafts in the wrong register; new audiences; pre-publish. |
| `operator.title` | Name the Thing | Give the thing a name worth remembering — a promise the work must keep. | Naming anything; embarrassing working titles; pre-publish. |

## How they compose

The skills are designed to chain: `operator.triage` sorts the pile,
`operator.eighty` finds the vital few, `operator.mvd` picks today's three,
`operator.deep` protects the hardest one, `operator.ship` gets it out the
door, `operator.review` closes the day, and `operator.streak` keeps the
practice alive. `operator.stress` guards the plan, `operator.blocker`
unblocks it, `operator.lock` commits it, `operator.actions` extracts
commitments from meetings, and `operator.no` defends the whole system.

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
