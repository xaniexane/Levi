---
skill_id: ml_feedforward_networks
name: Position-wise Feedforward Networks (and SwiGLU)
description: The MLP in every transformer block: expand, activate, contract - and the gated SwiGLU upgrade.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, transformers]
version: 1.0.0
---
# Position-wise Feedforward Networks (and SwiGLU)

## Purpose

Describe the feedforward sublayer of a transformer block - applied
independently at each position - and the SwiGLU gated variant that
replaced plain ReLU MLPs in modern models.

## When to use

- Sizing the FFN hidden dimension (the 4x rule and its variants).
- Reading LLaMA-style or LEVI-v2 model code with three projections.
- Understanding where most of a transformer's parameters live.

## Core ideas

Classic FFN: expand d_model -> 4*d_model, apply ReLU/GELU, contract
back. It holds roughly two-thirds of the block's parameters and does
the position-local "thinking": attention moves information *between*
positions, the FFN transforms it *within* each position.

SwiGLU replaces the single expansion with a gated pair:

    FFN(x) = (Swish(x @ W1) * (x @ W3)) @ W2

Two parallel projections, one passed through Swish (x * sigmoid(x)),
multiplied elementwise, then contracted. The gate lets the network
modulate features multiplicatively - consistently better than ReLU
MLPs in ablations. Standard sizing: hidden = (8/3)*d_model rounded to
a multiple that keeps parameter count near the 4x equivalent (LEVI's
tiny-gpt-v2 uses exactly hidden = 8/3 * n_embd per its config).

## Gotchas

- The FFN dominates parameter count; shrinking it is the cheapest way
  to cut model size, but it costs capability per parameter.
- Activation choice matters less than the gating; Swish/GELU beat ReLU
  modestly and consistently.
- Dead neurons accumulate in ReLU FFNs; gated variants suffer less.

## Quick reference

- Classic: d -> 4d -> d with GELU. SwiGLU: gate(xW1) * (xW3), then xW2;
  hidden ~= 8/3 * d.
