---
skill_id: ml_teacher_forcing
name: Teacher Forcing
description: Training sequence models on ground-truth prefixes: why it's fast, and the exposure-bias gap it creates.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, training]
version: 1.0.0
---
# Teacher Forcing

## Purpose

Explain teacher forcing - feeding true previous tokens during
training instead of the model's own predictions - why training would
be impractical without it, and the train/inference mismatch
(exposure bias) it introduces.

## When to use

- Understanding any autoregressive training loop.
- Debugging generation quality that lags training loss.
- Reading scheduled-sampling literature.

## Core ideas

At training step for position t, the model conditions on the *true*
tokens 1..t-1 (the data), not on its own earlier predictions. This
makes training fully parallel across positions (one forward pass
scores every position) - without it, training would be sequential
like generation, and impossibly slow.

The price is **exposure bias**: at inference the model conditions on
its *own* outputs, including its mistakes. Training never showed it
a prefix containing an error, so one wrong token can derail the rest
- the model hasn't learned to recover. Mitigations: large-scale
training (errors stay rare), sampling-based fine-tuning (RLHF/DPO
trains on the model's own outputs), and scheduled sampling
(gradually mix in own predictions - fiddly, rarely used now).

## Gotchas

- Teacher forcing is why train loss and generation quality can
  diverge: the loss measures one-step prediction given perfect
  history, generation measures the model's ability to steer itself.
- Always evaluate with real generation (samples), not just loss.
- The causal mask is the mechanism that makes teacher forcing valid
  - position t physically cannot see the future.

## Quick reference

- Train on true prefixes (parallel, fast). Inference on own outputs
  (sequential, error-prone). Gap = exposure bias; close it with
  generation-time eval and output-based fine-tuning.
