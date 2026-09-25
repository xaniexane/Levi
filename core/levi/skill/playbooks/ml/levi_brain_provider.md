---
skill_id: ml_levi_brain_provider
name: LEVI Brain as Runtime Provider (levi-brain)
description: How the trained brain plugs into the agent as an explicit provider, and the Echoverse training-data doctrine.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, levi]
version: 1.0.0
---
# LEVI Brain as Runtime Provider (levi-brain)

## Purpose

Explain how LEVI's own trained brain serves inside the agent runtime
as the `levi-brain` provider - explicit-only, prose answers, honest
boundary - plus the canon training-data doctrine (Echoverse engine
simulations) that feeds future brains.

## When to use

- Selecting the brain in the agent loop.
- Understanding what "LEVI is the provider, not the renter" means
  operationally.
- Planning training-data strategy under the current canon.

## Core ideas

**Provider wiring:** `--provider levi-brain` (or
`LEVI_PROVIDER=levi-brain`) selects LEVI's own weights inside the
agent runtime. It is explicit-only - never the default; the
deterministic rule-based `local` planner stays default until the
brain earns more. In the loop the brain answers in prose; it does not
emit tool calls.

**Honest boundary:** the standing framing is "can do now" versus
"needs more training" - capability claims track verified artifacts
(loss curves, eval gates, samples), never aspiration. This is the
operational form of the honest-limits doctrine.

**Training-data doctrine (Chauncey, 2026-09-22):** the brains train
on **Echoverse-engine-generated simulation corpora** - the Echoverse
engine forms a hypothesis/theory, simulates it, and the simulation
becomes training data (hypothesize -> simulate -> train).
External software knowledge feeds the *corpus/memory retrieval* side
(playbooks, seeds, knowledge base); the *weight-training* source is
Echoverse-generated. Correction noted in canon: the engine, not Echo
the entity.

## Gotchas

- Explicit-only is load-bearing: silent default routing to an
  unready brain would corrupt the agent loop. Keep the gate.
- The doctrine splits the world cleanly - retrieval knowledge (this
  playbook library, seeds) vs weight training (Echoverse sims). Don't
  mix the two provenances in manifests.
- Provider selection is per-invocation; nothing persists the choice
  implicitly.

## Quick reference

- Select: --provider levi-brain / LEVI_PROVIDER=levi-brain.
  Default: local planner. Boundary: can-do-now vs needs-training.
  Weight-training data: Echoverse simulations; retrieval: external
  knowledge.
