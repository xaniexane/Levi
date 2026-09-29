---
skill_id: compressed.engine-braid
name: Braid Pattern
description: Arbitrate verdicts from multiple engines into one ruling — consensus when all agree, named-dissent majority otherwise, deadlock held for the keeper.
risk: info
permissions: []
requires_confirmation: false
tags: [engines, arbitration, verdicts, consensus, nothing-thrown-away]
version: 1.0.0
---
# Braid Pattern

## Purpose

Turn "three engines, three answers" into one honest ruling. Braid does
not re-run the engines — it arbitrates their verdicts. When every engine
lands the same verdict, the braid says consensus. When a strict majority
agrees, the braid says majority and names every dissenter. When nothing
commands a majority, the braid refuses to compromise: it holds the
question for the keeper with verdict None.

The engine form of the two-sided coin: both faces show, or the coin is
held. Never flipped, never silently averaged.

## When to use

Whenever a decision was run through more than one engine — triage plus
weigh plus gavel on the same question, a muster roll alongside a season
read — and you need one ruling out of the pile. Also whenever the
dissent itself is the deliverable: braid's trace and `dissenting` list
are the disagreement, on the record.

## The pattern

1. **Collect the verdicts.** Each is `{"engine": str, "verdict": <json-able>,
   "confidence": 0.0–1.0}`. One verdict per engine — duplicates are
   refused, never double-counted. Verdicts must be JSON-serializable;
   anything JSON can't hold is refused outright.
2. **Run the engine.** `registry.run("braid", {"verdicts": verdicts,
   "question": "..."})` — or the `compressed.run-braid` skill. Keep the
   verdict list under `max_verdicts` (default 64).
3. **Read the outcome.** `"consensus"` → act. `"majority"` → act on the
   agreed verdict, but carry the dissent: the `dissenting` engines and
   their reasons go into the record. `"deadlocked"` → stop. The question
   is held for the keeper; braid will not invent a compromise.
4. **Carry the dissent.** A majority verdict is a verdict with a
   minority report attached. The minority report is not a footnote — it
   names the dissenting engines so the keeper knows exactly who saw it
   differently and can ask them directly.

## The laws

- **Unanimity:** identical verdicts always yield consensus, never
  "majority".
- **Conflict-honesty:** every disagreement is named in the trace; no
  merge happens off the books.
- **Dissent-surfaces:** a non-unanimous outcome lists every dissenting
  engine in the verdict itself.
- **Determinism:** same inputs → byte-identical verdict.
- **Hold-on-deadlock:** no strict majority → outcome deadlocked, verdict
  None, confidence 0.0. The engine never invents a compromise.

## Honest limits

- Braid arbitrates *verdicts*, not reasoning. A consensus of three
  engines that all misread the same bad input is a confident mistake —
  garbage in, consensus out. The pattern guards the arithmetic, not the
  inputs.
- Verdict equality is canonical JSON equality: `{"a": 1}` and
  `{"a": 1.0}` are the same verdict to braid. Engine scores that differ
  in the third decimal still agree if the verdict matches.
- Confidence of a majority verdict is the mean of the *agreeing* side's
  confidences — the dissenters' numbers never touch it. That asymmetry
  is disclosed on purpose: the confidence says how sure the winners
  were, not how contested the question was. The `distinct_verdicts`
  count tells the other half.
