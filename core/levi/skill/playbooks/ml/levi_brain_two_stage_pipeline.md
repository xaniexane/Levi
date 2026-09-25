---
skill_id: ml_levi_brain_two_stage_pipeline
name: LEVI Brain: the Two-Stage Learning Pipeline
description: How LEVI learns: a runtime knowledge base plus a genuinely trained tiny neural network, per docs/BRAIN_TRAINING.md.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, levi]
version: 1.0.0
---
# LEVI Brain: the Two-Stage Learning Pipeline

## Purpose

Describe LEVI's actual learning architecture as documented in
docs/BRAIN_TRAINING.md: two stages - (1) a knowledge base the agent
reads at runtime with no training, and (2) a tiny neural network
really trained on the corpus as proof the brain learns.

## When to use

- Onboarding to the brain subsystem.
- Explaining what "LEVI's brain" concretely means today.
- Deciding where new knowledge should go (retrieval vs weights).

## Core ideas

Stage 1 - knowledge base (no training): the awesome-courses
curriculum is ingested by `ingest.py` into
`core/levi/knowledge/courses/` (catalog.json: 212 courses, 11
subjects; per-course coverage; raw page text; extractive field-guide
briefs via build_briefs.py). The agent reads this at runtime.

Stage 2 - tiny neural net (real training): `train/prepare_corpus.py`
(stdlib-only) chunks the corpus into ~512-token records in
`train/corpus.jsonl`; `train.py` trains a tiny char-level GPT
(~2-4M params, AdamW, CPU torch); `eval.py` reports held-out loss
plus sample generations. Weights land in `train/weights/tiny-gpt.pt`
with `train_log.json` (first/last loss, params, seconds).

The corpus also carries **identity records** - one per LEVI register
(14 registers, count asserted in tests, never hand-written) - so the
tiny brain meets LEVI's own voice before the course text.

## Gotchas

- The two stages answer different questions: retrieval answers "what
  does LEVI know", training answers "can LEVI learn". Don't conflate
  them.
- Stage-2 quality is bounded by corpus quality - garbage web text in,
  texture-only brain out. Curation is the lever.
- `finetune_lora.py` is a stub (needs GPU); the trained path is the
  tiny GPT, not LoRA.

## Quick reference

- Stage 1: ingest.py -> knowledge/courses (read at runtime). Stage
  2: prepare_corpus.py -> train.py -> tiny-gpt.pt (proof of
  learning). Identity records seed LEVI's voice.
