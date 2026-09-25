# The 48 — Forward/Reverse Strategy Engine

`core/levi/strategy/` — 48 original LEVI-native strategic laws, each one object
carrying its **forward** application and its **reverse** (when the law
inverts), compressed into a single engine with one interface.

## The one method

```python
from levi.strategy import consult, project, apply, return_to_sender

for reading in consult("Should I quit my failing side project and focus?"):
    print(reading.law.name, "—", reading.stance)
    print(reading.guidance())
```

`consult(situation, top=5)` returns ranked `Reading`s: the law, a score, the
matched signals, and a stance (`forward` / `reverse` / `both`) — forward and
reverse guidance delivered together, never as two lists.

## THE LIFE FORMULA

Deterministic and repeatable — situation in, projection out:

```
Projection = 5-3-5( consult( Situation ) )
```

- **The 48 laws are the constants.**
- **Return-to-sender is the operator** — applied automatically when the
  situation is an attack, or directly via `return_to_sender(attack)` /
  `levi strategy reflect "..."`.
- **5-3-5 is the computation** — `project(situation, depth=5)`: think 5 steps
  ahead, lock the first 3, map the next 5 from there. Inside-out: every angle
  (ranked laws), every outcome (forward+reverse), optimized for the best
  EFFICIENT outcome — the best result at the lowest cost. Each step carries
  its price (the law's constraints) and a cost tier; the efficient pick is
  the locked move with the best score-per-cost.
- `apply(situation)` runs the whole formula at once and returns a
  `FormulaResult`: readings + optional reflection + projection.

## Return-to-sender (signature defensive move)

When attacked, undermined, or provoked: reflect it back to the sender
cleanly. Name the behavior once, plainly, without heat — then let the
consequences belong to the one who sent it. Stay on your aim.

- No escalation — you don't raise the stakes.
- No manipulation — you don't play their game back at them.
- No absorption — you don't carry what isn't yours.

## Domain-universal

The engine takes any life area — health, relationships, money, work, family,
goals, daily decisions, learning, conflict, community, self, anything. Every
law carries example `domains`; pass `domain=` (or `--domain`) to weight laws
proven in that arena. Laws are framed generally, never locked to one arena.

## CLI

```
levi strategy consult "I need to decide whether to launch now or wait" --top 3
levi strategy project "Should I confront my coworker or let it go" --domain work
levi strategy reflect "Someone is spreading rumors about me"
levi strategy laws
levi strategy law 28
```

## Doctrine (binding)

- **Defense never manipulates; attack = going and getting the goal.** This is
  the attack/goal-pursuit side of the life-chess doctrine. Strategic
  projection, not exploitation. Law 28 (Allies, Not Pawns) and Law 48 (The
  Living Law) hard-bound this: no law may be used to manipulate people, and
  Law 48 never excuses Law 28.
- **One object, two faces.** Every law ships forward + reverse + constraints
  + signals in a single `Law`. The reverse is not an "opposite law" — it is
  the same law inverted by circumstance.
- **Constraints are load-bearing.** Each law names its guardrails; the engine
  surfaces them with every reading.

## The 48 (names)

01 The Open Hand · 02 First Light · 03 The Long Ledger · 04 High Ground ·
05 The Clean Cut · 06 Borrowed Fire · 07 The Quiet Build · 08 One True North ·
09 The Patient Stone · 10 Visible Work · 11 The Fair Trade · 12 Deep Roots ·
13 The Second Door · 14 Small Wins, Stacked · 15 The Honest Mirror · 16 Tempo ·
17 The Wide Net · 18 Named Things · 19 The Steady Signal · 20 Own the Frame ·
21 The Spare Key · 22 Strike the Iron · 23 The Empty Chair ·
24 Compound Interest · 25 The Clean Name · 26 Terrain Reading ·
27 The Decisive No · 28 Allies, Not Pawns · 29 The Rehearsed Mind ·
30 Visible Scars · 31 The Long Game Face · 32 Build the Table ·
33 The Sharp Edge · 34 Fog and Lantern · 35 Hunter and Farmer · 36 Stone Soup ·
37 The Unplayed Card · 38 Measure Twice · 39 The Common Ground ·
40 Winter Stores · 41 The Clean Break · 42 Many Small Bets · 43 The Storyteller ·
44 The Anvil · 45 Gatekeeping Inverted · 46 The Oath · 47 The Last Mile ·
48 The Living Law

## Honest limits

- Ranking is keyword/signal-weighted, not a model of your life — it surfaces
  candidate laws, it does not decide for you.
- The engine is only as wise as the situation you describe; vague input,
  vague readings.
- Law 48 lets you break any law for a rightly-held goal — which means the
  judgment stays yours. The engine advises; you project.
