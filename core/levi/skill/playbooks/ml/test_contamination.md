---
skill_id: ml_test_contamination
name: Test Contamination and Leakage
description: How eval text sneaks into training data, why it invalidates benchmarks, and how to check for it.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, data, evaluation]
version: 1.0.0
---
# Test Contamination and Leakage

## Purpose

Explain test contamination - benchmark text present in training data
- as the integrity issue behind inflated scores, and give detection
and prevention practices.

## When to use

- Reporting benchmark numbers honestly.
- Building eval sets that survive web-scale training.
- Reading benchmark claims skeptically.

## Core ideas

If the model trained on the test questions, the score measures
retrieval, not capability. Contamination routes: benchmark text in
Common Crawl, GitHub solutions to benchmark tasks, paraphrased copies
that near-dup misses, and (increasingly) *model-generated* benchmark
solutions polluting the web for the next generation.

Detection: n-gram overlap between train corpus and eval items
(13-gram match rates are the standard screen), canary strings
(benchmarks embed GUID-like markers; grep your corpus for them),
and behavioral tells (suspiciously perfect formatting on odd tasks).

Prevention: keep eval items out of crawlable public text, use canary
strings, dedup eval from train at high n-gram sensitivity, and prefer
fresh/private evals for high-stakes claims.

## Gotchas

- Paraphrase contamination evades n-gram screens - no screen is
  complete; defense in depth.
- Contamination inflates *some* tasks hugely (memorized QA) and
  others barely (reasoning) - uneven, which makes it hard to spot
  by aggregate score.
- Your own earlier experiments' outputs can contaminate later
  training runs if outputs get re-ingested. Track provenance.

## Quick reference

- Screen: 13-gram overlap + canary grep. Prevent: private evals,
  cross-split dedup, provenance tracking.
