---
skill_id: ml_mixture_of_experts
name: Mixture of Experts (MoE)
description: How sparse expert layers scale parameters without scaling compute, via per-token routing.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, transformers]
version: 1.0.0
---
# Mixture of Experts (MoE)

## Purpose

Explain MoE transformer layers: replace the FFN with many "expert"
FFNs plus a router that sends each token to only 1-2 experts -
multiplying parameters while keeping FLOPs per token roughly flat.

## When to use

- Understanding large sparse models (Mixtral-style and successors).
- Deciding whether MoE fits your compute budget (memory vs FLOPs).
- Debugging expert collapse and load imbalance.

## Core ideas

Each token is scored by a small gating network over E experts; the
top-k (usually 1 or 2) experts process it, and their outputs are mixed
by the gate weights. An 8-expert layer with top-2 routing has ~8x the
FFN parameters but only ~2x the FFN compute per token. Experts tend to
specialize (some fire on code, some on morphology) without any explicit
supervision to do so.

The hard part is balance: without a load-balancing loss, the router
collapses - a few experts get all tokens, the rest atrophy. Standard
fix: an auxiliary loss penalizing uneven assignment, plus capacity
limits that drop overflow tokens.

## Gotchas

- MoE saves FLOPs, not memory: all experts must live in VRAM.
- Fine-tuning MoE is fussier; router behavior shifts under new data.
- Inference batching is less efficient - different tokens in a batch
  take different expert paths.

## Quick reference

- y = sum over top-k experts of gate_i(x) * Expert_i(x); add a load-
  balancing auxiliary loss or the router collapses.
