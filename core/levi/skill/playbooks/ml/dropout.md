---
skill_id: ml_dropout
name: Dropout
description: Randomly zeroing activations during training: rates, inverted dropout, and why it is off at inference.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, training]
version: 1.0.0
---
# Dropout

## Purpose

Explain dropout precisely - what gets zeroed, the inverted scaling
that keeps expectations matched, and where it helps vs hurts.

## When to use

- Small-model training that overfits.
- Understanding transformer configs (dropout 0.1 everywhere).
- Debugging train/eval behavior gaps.

## Core ideas

During training, each activation is zeroed with probability p, and
survivors are scaled by 1/(1-p) (**inverted dropout**) so the expected
sum stays constant - no rescaling needed at inference, where dropout
is simply disabled. The network learns redundant pathways because no
single neuron can be trusted, which is the regularization.

Standard placement in transformers: after attention output, after FFN
output, sometimes on embeddings. p=0.1 is the historical default.
Large-scale LM training often drops dropout entirely - with billions
of tokens seen once, the model never memorizes, so the regularization
is pure cost.

## Gotchas

- Forgetting eval mode is the #1 dropout bug: nondeterministic,
  degraded inference that "works but worse".
- Dropout + BatchNorm interact badly (variance shift); with
  LayerNorm/RMSNorm transformers this is a non-issue.
- Very small models + high dropout = underfitting. p=0.1 on a 2-layer
  toy can erase real signal.

## Quick reference

- Train: zero with prob p, scale survivors by 1/(1-p). Eval: off,
  no scaling. p ~ 0.1; large-scale single-epoch training often skips
  it.
