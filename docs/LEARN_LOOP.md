# The Learning Loop — LEVI teaches itself

This is the self-sufficiency engine: the loop that turns "LEVI watched
other models work" into "LEVI's brain got better." It closes the biggest
structural weakness frontier AI has — frozen weights — by making LEVI's
weights a living thing that improves on a schedule, offline, on Chauncey's
own machines.

## The cycle

```
observe  ->  corpus  ->  estimate  ->  retrain  ->  eval  ->  gate  ->  receipt
   |            |           |             |            |          |
   v            v           v             v            v          v
~/.levi/    dedupe +    honest cost    candidate    held-out   promote ONLY
model-      quality      estimate       weights      loss +     on real
observations filters     (calibrated    (staged,     behavioral improvement;
.jsonl      teacher      when           never live)  checks +   else reject
            weights                     needs torch  regret     with reasons
            split                                    check
```

Every cycle writes a receipt, whatever happened — promoted, rejected,
blocked, or dry-run.

## Commands

All under `levi brain learn` (dry-run by default — nothing trains or
promotes until you say `--live` / `--learn-live`):

- `learn status` — observations, schedule, weights, last cycle, lineage
- `learn once` — one cycle now (dry-run unless `--learn-live`)
- `learn schedule --every 86400` — register the loop on an interval
  (add `--learn-live` to make the schedule train for real)
- `learn tick` — run the scheduled job if due (wire to cron/daemon)
- `learn unschedule` — remove the schedule
- `learn rollback [--to NAME]` — one-command restore of previous weights
- `learn history [N]` — recent cycle receipts

Flags: `--loop-dir`, `--weights-dir`, `--observations`, `--learn-steps`,
`--learn-margin`, `--learn-every`, `--learn-to`, `--learn-reason`.

## Where things live

- Observations: `~/.levi/model-observations.jsonl` (written by the
  torch-free runtime; the loop only reads)
- Loop state: `~/.levi/brain-loop/` — corpora, staging, schedules,
  receipts, calibration
- Live weights: `core/levi/brain/weights/tiny-gpt.pt` (originals never
  modified in place — promotion keeps `tiny-gpt.prev-<ts>.pt` + the old
  portable export as rollback)
- Lineage: `core/levi/brain/weights/lineage.jsonl` — every promotion and
  rollback, with content hashes from observations to weights

## The eval-gate (the part that guards the weights)

A candidate becomes the live brain only if ALL of these hold:

1. **Held-out loss** beats the incumbent by `--learn-margin` nats
   (default 0.02), measured on the same val text through the torch-free
   runtime. Characters the candidate never saw are *penalized*, never
   silently excluded — it can't win by forgetting.
2. **Behavioral checks** all pass: deterministic argmax, charset
   adherence, no collapse, corrupt input handled honestly.
3. **Regret check**: the candidate's loss on anchor texts (the
   incumbent's own good outputs, captured at the last promotion) stays
   within margin — no catastrophic forgetting.

Otherwise the candidate is rejected with explicit reasons, the live
weights are untouched, and the receipt says why.

## Strengthen moves (shipped)

- **Multi-teacher weighting** — per-teacher trust weights in config;
  deterministic oversampling at corpus build (capped).
- **Observation quality scoring** — garbage never reaches the corpus.
- **Curriculum ordering** — train split ordered easy→hard by a cheap
  difficulty heuristic; scores stored per line for future trainers.
- **Eval beyond loss** — behavioral suite + regret/anchor checks.
- **Lineage chain** — content hashes from observation log through
  corpus, candidate, eval scores, to the promoted weights.
- **One-command rollback** — `learn rollback` restores weights +
  portable export and logs it.

## Honest limits

- Retraining needs torch (the training environment); the loop degrades
  gracefully without it — observe, corpus, and estimate still run.
- Candidate quality is bounded by the tiny trainer (3.2M params,
  char-level). This is the *engine*, not the destination: the loop makes
  improvement compounding and safe, but the climb from proof-of-learning
  to genuinely capable is many cycles of better observations.
- The bundled trainer samples uniformly, so curriculum ordering is
  currently advisory (recorded in the corpus manifest for future
  curriculum-aware trainers).
- The loop never presents brain output as reasoning — the rules engine
  stays the decider, and brain output stays labeled everywhere.
