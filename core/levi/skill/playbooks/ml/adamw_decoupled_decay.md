---
skill_id: ml_adamw_decoupled_decay
name: AdamW: Decoupled Weight Decay
description: Why AdamW replaced Adam+L2, what 'decoupled' means, and how to set weight decay without wrecking training.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, training]
version: 1.0.0
---
# AdamW: Decoupled Weight Decay

## Purpose

Explain the AdamW fix: classic L2 regularization interacts badly with
Adam's adaptivity, so AdamW applies weight decay as a separate step -
and give practical decay values.

## When to use

- Any Adam-based training (use AdamW, not Adam, by default).
- Tuning weight decay for transformers vs CNNs.
- Understanding why some parameters should be excluded from decay.

## Core ideas

With Adam + L2, the L2 gradient (lambda*theta) gets divided by
sqrt(v_hat) like everything else - parameters with large gradients
get *less* regularization, exactly backwards. AdamW decouples it:

    theta = theta - lr * (m_hat/(sqrt(v_hat)+eps) + wd*theta)

Weight decay now shrinks every parameter by a steady factor per step,
independent of gradient history. This is proper regularization again,
and it consistently beats L2-with-Adam on transformers.

Practice: wd ~0.01-0.1 for transformers (0.1 common at large scale,
0.01 safer small). Exclude from decay: biases, normalization gains,
and the embedding table (sometimes) - decaying biases/gains just adds
noise, and embedding decay can hurt rare tokens. Most frameworks'
AdamW implementations take a param-group list for exactly this.

## Gotchas

- wd interacts with lr: decay's effective strength scales with the
  learning rate schedule. Retune together, not separately.
- Too much decay on a small model underfits visibly - the model
  "forgets" faster than it learns.
- Some implementations still call it "Adam with weight_decay arg"
  while doing the coupled thing - check whether decay is inside or
  outside the adaptive denominator.

## Quick reference

- AdamW: decay applied outside adaptivity: theta -= lr*(update +
  wd*theta). wd ~0.01-0.1; skip biases and norms.
