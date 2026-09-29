---
skill_id: operator.gavel
name: Gavel Rulings
description: Adjudicate competing claims like a judge: score the evidence, penalize contradictions, and rule only when the burden of proof is met.
risk: info
permissions: []
requires_confirmation: false
tags: [decisions, adjudication, evidence, rulings]
version: 1.0.0
---
# Gavel Rulings

## Purpose

Two claims collide and both sound right. Gavel Rulings is the procedure
for settling it: turn each claim into scored evidence, apply the
contradiction penalty honestly, pick the burden of proof up front, and
let the ruling fall where the evidence lands — including the honest
outcomes most people skip: split, and remanded.

## When to use

- Two plans, vendors, hires, or directions both claim to be the answer.
- A standing decision is being challenged and you need a clean
  upheld-or-overturned ruling, not a vibe.
- The evidence is thin on every side and someone has to say so out loud.
- After a disagreement, to write down WHY the ruling went the way it did.

## Steps

1. Write down every competing claim as one sentence each. No claim, no
   score — vibes don't get weighed.
2. For each claim, name its evidence as a number from 0 to 1. 0.9 means
   "I could defend this in front of a skeptic"; 0.3 means "a hunch with
   a nice chart." Be harsh. Inflated evidence is how bad rulings happen.
3. Mark every claim that contradicts known facts. A contradicted claim
   scores half — no exceptions, no matter how much you like it.
4. Weight the sources if some evidence is worth more (a measured result
   outweighs an anecdote), then pick the burden of proof BEFORE scoring:
   preponderance (more likely than not), clear (strongly convincing), or
   beyond doubt (near-certain). Moving the bar after seeing the scores
   is cheating.
5. Run the gavel engine (`levi.engines` id `gavel`) with the claims, the
   optional incumbent (the current ruling under challenge), and the
   chosen standard.
6. Read the ruling and accept all four outcomes:
   - **upheld** — the leader (or incumbent) met the burden. Act on it.
   - **overturned** — a challenger met the burden and beat the
     incumbent. The old ruling is dead; say so plainly.
   - **split** — nobody met the burden. Do NOT pick a winner anyway.
     Name what evidence would settle it and go get it.
   - **remanded** — every claim is below the evidence floor. Send it
     back. A ruling on this little evidence would be fiction.
7. Write the ruling into the verdict ledger (`levi automation
   verdict-record`): ruling, prevailing claim, scores, and the reason.
   A ruling nobody wrote down didn't happen.

## Honesty notes

- Split and remanded are rulings, not failures. Forcing a winner from
  thin evidence is how you get confident mistakes.
- The contradiction penalty is not negotiable. If the evidence changed,
  update the evidence — don't waive the penalty.
- Never name a prevailing claim on a split or remanded ruling. The
  engine refuses to; so do you.
- If you chose the standard after seeing the scores, throw the ruling
  out and start over. The bar is set before the weigh-in, always.
