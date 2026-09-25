---
skill_id: ml_warmup_phase
name: The Warmup Phase: Why First Steps Are Fragile
description: A closer look at warmup mechanics: what goes wrong at initialization and how ramping the LR prevents it.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, training, optimization]
version: 1.0.0
---
# The Warmup Phase: Why First Steps Are Fragile

## Purpose

Zoom in on warmup specifically: the initialization-time dynamics that
make the first few percent of training uniquely dangerous, and how to
size warmup for your run.

## When to use

- A run diverges in the first few hundred steps.
- Porting a recipe to a larger model or batch size.
- Understanding Adam's early-step behavior.

## Core ideas

At initialization: weights are random, activations have uncontrolled
scale, Adam's v (second moment) is warming up from zero, and the data
order is arbitrary. A full-size gradient step in this regime can push
activations into saturated regions (softmax one-hot, dead ReLUs)
from which gradients cannot recover the model - the damage is
structural, not just a bad step.

Warmup ramps lr from 0 linearly over W steps so that: (1) Adam's
moment estimates stabilize before big steps, (2) activations settle
into sane ranges gradually, (3) early batches cannot individually
wreck the weights. W ~ 1-5% of total steps; tiny-gpt-v2 used 100 of
5400 (~2%).

Longer warmup is cheap insurance when scaling up (bigger model, bigger
batch, higher peak lr all increase early fragility).

## Gotchas

- Warmup does not fix a fundamentally too-high peak lr - it only
  delays the explosion. If loss diverges right after warmup ends,
  lower the peak.
- With gradient clipping, warmup and clipping compose fine - use both.
- Resuming from a checkpoint mid-schedule: resume the *schedule
  position* too, not just the weights.

## Quick reference

- Warmup: linear 0 -> max lr over ~2% of steps. Protects init
  fragility; does not excuse an absurd peak lr.
