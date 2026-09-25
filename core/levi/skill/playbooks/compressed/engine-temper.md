---
skill_id: compressed.engine-temper
name: Temper Pattern
description: Grade a claim as settled, leaning, provisional, or unfounded from its evidence — contradictions weigh double, old proof decays.
risk: info
permissions: []
requires_confirmation: false
tags: [engines, evidence, confidence, honesty]
version: 1.0.0
---
# Temper Pattern

## Purpose

The honesty discipline: never state a claim more strongly than its
evidence earns. Tempering takes a claim, counts what supports it and
what denies it, weighs how old the newest evidence is, and returns a
standing — *settled*, *leaning*, *provisional*, or *unfounded* — with
the arithmetic shown. It is the engine behind "raw truth, the whole
road": the verdict names exactly how much road is visible.

## When to use

- Any factual claim before it goes into a report, a reply, or canon.
- Retrospectives: was that call stated at the right strength?
- Claims built on old evidence — the 180-day half-life catches stale proof.
- Run it through the `temper` engine (`levi engines run temper`).

## The pattern

1. **State the claim in one sentence.** The engine refuses empty claims.
2. **Count independent corroborations.** A corroboration is one
   *independent* source saying it — two retellings of the same post are
   one source, not two.
3. **Count contradictions, honestly.** One contradiction costs two
   corroborations. An honest denial outweighs an echo.
4. **Age the evidence.** The newest evidence's age in days decays
   confidence on a 180-day half-life. Stale proof is not proof.
5. **Read the standing, then speak at that strength.** Settled claims
   can be stated plainly. Provisional ones must be flagged as
   provisional when you repeat them — the flag is part of the claim.

## Anti-patterns

- **Confidence laundering:** restating a provisional claim three times
  until it sounds settled. Tempering each repetition returns
  "provisional" every time.
- **Source inflation:** counting the same source twice under different
  names. The engine refuses when corroborations plus contradictions
  exceed sources consulted.
- **Fresh coat:** citing new work that merely cites the old proof. The
  age is the age of the *evidence*, not of the retelling.
