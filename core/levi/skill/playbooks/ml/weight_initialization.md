---
skill_id: ml_weight_initialization
name: Weight Initialization: Xavier and He
description: Why initial weight scale matters, what Xavier/He init do, and the failure modes of bad init.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, training]
version: 1.0.0
---
# Weight Initialization: Xavier and He

## Purpose

Explain why weights can't start at zero or at arbitrary scale, what
Xavier (Glorot) and He initialization compute, and how init interacts
with activations and residuals.

## When to use

- Implementing layers by hand.
- Debugging a network that doesn't learn from step 0.
- Understanding "scaled init" in transformer configs.

## Core ideas

Zero init: all neurons symmetric, gradients identical, nothing
differentiates - the network never learns. Too-large init:
activations explode through depth. Too-small: signals vanish.
The goal: keep activation variance ~constant across layers at init.

- **Xavier/Glorot:** Var(W) = 2/(fan_in + fan_out) (uniform variant:
  limit = sqrt(6/(fan_in+fan_out))). Designed for symmetric
  activations (tanh, sigmoid) - preserves variance forward and
  backward.
- **He:** Var(W) = 2/fan_in. Designed for ReLU, which kills half the
  activations - the factor of 2 compensates.

Transformers typically use small normal init (std 0.02) on most
matrices with *scaled* init on residual-branch outputs (divide by
sqrt(2 * n_layers)): residual additions accumulate variance with
depth, so the layers feeding the skip path start smaller.

## Gotchas

- Init must match the activation: He for ReLU-family, Xavier-ish for
  tanh/sigmoid. Mismatched init silently slows or stalls training.
- Embedding tables and output heads often use plain small-normal init
  regardless - they're single layers, no depth accumulation.
- Reproducibility: init RNG is part of the seed story. Same seed +
  same code = same start.

## Quick reference

- Never zero. Xavier: 2/(in+out) for symmetric acts. He: 2/in for
  ReLU. Residual outputs: scale down by depth.
