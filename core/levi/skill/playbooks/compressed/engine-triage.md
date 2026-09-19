---
skill_id: compressed.engine-triage
name: Triage Pattern
description: Pick a winner from competing options with weighted criteria, a visible margin, and an honest trace.
risk: info
permissions: []
requires_confirmation: false
tags: [engines, decision, ranking, determinism]
version: 1.0.0
---
# Triage Pattern

## Purpose

Decide between competing options without gut calls. Score every option
on the same criteria, weight the criteria, and let the ranking speak —
with the margin and the math on the table so the verdict can be audited.

## When to use

Choosing between vendors, designs, job offers, routes, tools — anywhere
three or more options compete and the criteria are knowable up front.
Run it through the `triage` engine (`levi engines run triage`).

## The pattern

1. **Name the options.** At least two. Each needs an id.
2. **Score every option on every criterion.** Missing scores default to 0.
3. **Weight the criteria.** Weights are declared before scoring, never
   tuned after the fact to rescue a favorite.
4. **Read the margin, not just the winner.** A 0.02 margin is a coin
   flip wearing a verdict's clothes — say so.

## Honest limits

- Criteria that don't vary across options contribute zero signal; the
  engine names them instead of hiding them.
- Exact ties break on option id — deterministic, disclosed, not fair.
  If fairness matters, add a distinguishing criterion.
- Triage weighs what you measured. It cannot tell you what you forgot
  to measure.
