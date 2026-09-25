---
skill_id: ml_gradient_accumulation
name: Gradient Accumulation
description: Simulating big batches on small memory: N micro-steps, one update, and the numerics that differ.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, training]
version: 1.0.0
---
# Gradient Accumulation

## Purpose

Explain gradient accumulation: run several small forward/backward
passes, sum the gradients, update once - reaching effective batch
sizes that don't fit in memory.

## When to use

- GPU memory too small for your target batch size.
- Reproducing a large-batch recipe on fewer/smaller GPUs.
- Understanding "batch size 512 (accum 8x64)" in configs.

## Core ideas

    for micro in range(accum_steps):
        loss = forward(micro_batch) / accum_steps
        loss.backward()          # grads accumulate in .grad
    optimizer.step(); zero_grad()

Effective batch = micro_batch * accum_steps. The division by
accum_steps keeps the gradient magnitude equal to a true large batch
(mean, not sum). Throughput is slightly worse than a native large
batch (no cross-micro parallelization), but it runs at all, which is
the point.

Differences from a true large batch: BatchNorm statistics would
differ (irrelevant for norm-free transformers), dropout masks differ
per micro-step (negligible), and gradient all-reduce happens once per
update instead of per micro-step in distributed setups (a real
communication saving).

## Gotchas

- Divide the loss by accum_steps (or scale lr equivalently) -
  forgetting this multiplies your effective lr by accum_steps.
- zero_grad() placement: after step, not inside the micro loop.
- Learning-rate schedules count *optimizer steps*, not micro-steps -
  schedule accordingly.

## Quick reference

- Effective batch = micro * accum. Scale loss by 1/accum. Schedule
  on optimizer steps. Slight throughput cost, big memory win.
