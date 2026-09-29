---
skill_id: operator.decide
name: Unstick and Rule
description: Diagnose what is stuck, red-team the plan, adjudicate the collision — decide like it is real.
risk: info
permissions: []
requires_confirmation: false
tags: [decisions, planning, unblocking, red-team]
version: 1.0.0
---
# Unstick and Rule

Composite: blocker × stress × gavel (absorbed 2026-09-29).

## Purpose

Three moves, escalating: ① name what is actually stuck, ② try to kill the
plan before reality does, ③ rule on the collision like a judge. Most
blockers are misdiagnosed, most plans untested, most rulings vibes — this
chain fixes all three in order.

## When to use

- "I'm stuck" is the whole analysis, or a task keeps getting rescheduled.
- Before committing to a plan that feels vague, ambitious, or suspiciously easy.
- Two claims collide and both sound right.

## Steps

1. ① Classify the blocker in one sentence — "I can't ___ because ___" —
   HARD (break it into the smallest next step), UNCLEAR (go get the missing
   piece today: one question, one decision), AVOIDED (name the fear out
   loud, shrink the first step until it is laughable). Take that step
   within 24 hours or reclassify.
2. ② Stress-test: state the plan's core claim ("this works because ___"),
   list every way it dies (at least five, embarrassments included), score
   likelihood × damage, and for the top three decide: mitigate, accept
   openly, or kill. Rewrite with mitigations baked in — or bury it.
3. ③ Gavel: write each competing claim as one sentence; score its evidence
   0–1 (harsh — inflated evidence is how bad rulings happen); contradicted
   claims score half, no exceptions. Pick the burden of proof BEFORE
   scoring — moving the bar after is cheating.
4. Run the gavel engine (`levi.engines` id `gavel`) with the claims and the
   chosen standard. Accept all four outcomes: upheld, overturned, split
   (name the evidence that would settle it), remanded (send it back — a
   ruling on this little evidence would be fiction).
5. Write the ruling into the verdict ledger. A ruling nobody wrote down
   didn't happen.

## Honesty notes

- Most "hard" blockers are avoided. Classify with a witness if you can.
- Never stress-test a decided plan to justify it. That is theater, not testing.
- Split and remanded are rulings, not failures. Forcing a winner from thin
  evidence is how you get confident mistakes.
- If you chose the standard after seeing the scores, throw the ruling out.

Source echo ⇐ operator.blocker × operator.stress × operator.gavel —
originals stored at stored/2026-09-29-operator-playbooks/, regenerable on demand.
