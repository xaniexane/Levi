---
skill_id: ml_backpropagation
name: Backpropagation
description: The chain rule applied at scale: how gradients flow backward through a network in one efficient pass.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, training]
version: 1.0.0
---
# Backpropagation

## Purpose

Explain backpropagation without mystique: it is the chain rule,
evaluated once per parameter via dynamic programming on the
computation graph - one forward pass to record, one backward pass to
differentiate everything.

## When to use

- Understanding what autograd frameworks actually do.
- Debugging vanishing/exploding gradients conceptually.
- Explaining training to someone who knows calculus.

## Core ideas

Forward pass: compute activations layer by layer, keeping the
intermediates. Backward pass: start from dL/d(output) = 1-ish seed,
apply the chain rule layer by layer in reverse. Each layer needs only
its local Jacobian times the incoming gradient - so all parameter
gradients cost about one forward pass, not one pass per parameter
(which is what finite differences would cost: impossibly slow).

Two structural facts fall out:

- **Vanishing:** gradients multiply through Jacobians; if each layer
  shrinks them (sigmoid derivatives <= 0.25), deep nets get nothing
  at the bottom. Residuals + careful activations exist to fight this.
- **Exploding:** if each layer amplifies, gradients blow up -
  gradient clipping exists to fight this.

Memory cost: intermediates must be stored for the backward pass
(activation checkpointing trades recompute for memory when needed).

## Gotchas

- `loss.backward()` accumulates into .grad - forget `zero_grad()` and
  gradients sum across batches silently.
- In-place ops on tensors needed for backward corrupt the graph;
  autograd will error - believe it.
- Second derivatives (Hessian) need create_graph=True; almost never
  needed for standard training.

## Quick reference

- Forward records, backward applies chain rule in reverse. Cost ~1
  forward pass for all grads. Vanishing: shrink-through-depth;
  exploding: clip.
