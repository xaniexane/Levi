---
skill_id: operator.stress
name: Stress-Test the Plan
description: Red-team a plan before reality does: attack it, find every way it dies, harden what survives.
risk: info
permissions: []
requires_confirmation: false
tags: [planning, red-team, focus]
version: 1.0.0
---
# Stress-Test the Plan

## Purpose

A plan you have not tried to kill is a plan you have not tested. This
playbook red-teams the plan in conversation so reality does not have to do
it in production. What survives is worth committing to; what does not was
never real.

## When to use

- Before committing to a plan that feels vague, ambitious, or suspiciously easy.
- Before shipping anything with real stakes.
- When everyone agrees too fast — agreement is not validation.

## Steps

1. State the plan's core claim in one sentence: "This works because ___."
2. List every way it could fail. Aim for at least five. Include the
   embarrassing ones — the obvious failures are the ones that actually happen.
3. For each failure mode, score likelihood x damage. High/low is fine; false
   precision is worse than none.
4. Sort by score. For the top three, decide: mitigate (change the plan),
   accept (name the risk and carry it openly), or kill (the plan dies here).
5. Rewrite the plan with the mitigations baked in — or bury it and say what
   replaces it.

## Honesty notes

- Attack the plan, not the planner. The goal is a survivor, not a scapegoat.
- Never stress-test a decision that is already made in order to justify it.
  That is theater, not testing.
- A plan that survives this earns commitment. A plan that cannot survive
  questions cannot survive contact with the world.
