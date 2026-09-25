---
skill_id: ml_model_checkpoints
name: Checkpoints: Saving and Resuming Training
description: What a checkpoint must contain for exact resumption, how often to save, and the keep-last discipline.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, training]
version: 1.0.0
---
# Checkpoints: Saving and Resuming Training

## Purpose

Define what belongs in a training checkpoint for *exact* resumption -
weights, optimizer state, scheduler position, RNG state - and the
operational discipline around saving.

## When to use

- Any training run longer than an hour.
- Preemptible/spot compute (checkpoints are survival).
- Debugging "resumed run behaves differently".

## Core ideas

A complete checkpoint:

- **Model weights** (the obvious part).
- **Optimizer state** (Adam m/v) - without it, resuming restarts
  adaptivity from zero and the run wobbles for hundreds of steps.
- **Scheduler position** - resume the LR at the right schedule step,
  not from the peak.
- **RNG states** (python, numpy, torch) - for exact data-order
  reproducibility.
- **Step/epoch counters, config hash** - so you know *what* you're
  resuming.

LEVI's v2 run saved every 500 steps keeping the last 5, each ~63MB -
cheap insurance that survived two silent mid-run deaths (steps 4500
and 5000) and allowed clean resumption to 5400.

## Gotchas

- Saving weights only is *not* resumption - it's fine-tuning from a
  warm start. Name it honestly.
- Keep-last-N bounds disk usage; keep-best (by val) separately - they
  serve different purposes (recovery vs selection).
- Verify a checkpoint loads *before* you need it: corrupt saves are
  discovered at the worst moment otherwise. A manifest with sha256
  (like LEVI's checkpoints.json) catches bit rot.

## Quick reference

- Save: weights + optimizer + scheduler + RNG + step + config hash.
  Cadence: every N steps, keep last K + best. Verify loads.
