---
skill_id: ml_momentum_optimizer
name: SGD with Momentum
description: How a running average of past gradients damps oscillation and accelerates through consistent directions.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, training]
version: 1.0.0
---
# SGD with Momentum

## Purpose

Explain classical momentum: keep a velocity vector - an exponential
moving average of gradients - and step with the velocity instead of
the raw gradient.

## When to use

- Training CNNs or small models where SGD+momentum is still standard.
- Understanding what Adam's first moment is doing.
- Diagnosing oscillation across ravines in the loss landscape.

## Core ideas

    v = mu * v + grad        # mu ~ 0.9
    theta = theta - lr * v

The velocity accumulates consistent directions and cancels
oscillating ones. Picture a ravine: raw SGD bounces wall to wall;
momentum averages the bounces away and accelerates along the valley
floor. Effective step size grows to lr/(1-mu) in persistent
directions - mu=0.9 gives 10x amplification, which is why momentum
runs use smaller nominal learning rates than plain SGD.

Nesterov momentum looks ahead: compute the gradient at
theta - mu*v (where velocity is taking you) instead of at theta -
a correction that anticipates overshoot. Marginally better, slightly
fussier.

## Gotchas

- Momentum + tiny batches = velocity dominated by noise; the
  averaging helps, but very noisy gradients still need lower lr.
- mu too close to 1 (0.999) with high lr diverges spectacularly -
  the classic "loss NaN at step 200" config.
- Adam won for transformers largely because per-parameter adaptivity
  matters more than a single global velocity.

## Quick reference

- v = 0.9*v + g; theta -= lr*v. Damps oscillation, amplifies steady
  directions ~10x. Nesterov: gradient at the lookahead point.
