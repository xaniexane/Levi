---
skill_id: ml_residual_connections
name: Residual Connections
description: Why adding the input back around every sublayer is what makes deep networks trainable at all.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, transformers]
version: 1.0.0
---
# Residual Connections

## Purpose

Explain the residual (skip) connection - output = x + Sublayer(x) -
and why this one addition is the structural reason networks deeper
than ~20 layers can be trained.

## When to use

- Designing any deep architecture.
- Diagnosing vanishing gradients in a deep stack.
- Understanding ResNets, transformers, and modern CNNs uniformly.

## Core ideas

A plain stack of layers must learn full transformations, and gradients
multiply through every layer's Jacobian - shrinking or exploding with
depth. A residual block only has to learn the *change* F(x), with the
identity path carrying x through untouched:

    y = x + F(x)

The gradient of the loss w.r.t. x gets a direct +1 term from the skip,
so signal reaches early layers no matter how deep the stack. If a
layer has nothing useful to add, it can push F(x) toward 0 and the
network degrades gracefully to a shallower one - deep residual
networks cannot easily be *worse* than their shallow counterparts.

Initialization interacts: F(x) should start small (near-zero) so early
training behaves like a shallow net and depth is "grown into".

## Gotchas

- The +1 gradient path is why you can train 100+ layers; remove the
  skip and the same architecture dies past a handful of layers.
- Pre-norm vs post-norm is really a debate about *where* the norm sits
  relative to this addition.
- Stochastic depth (randomly dropping whole residual branches during
  training) regularizes very deep nets by training an ensemble of
  depths.

## Quick reference

- y = x + F(x); gradient carries a clean identity term through depth.
