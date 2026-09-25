---
skill_id: ml_dataset_curation
name: Dataset Curation for Language Models
description: Selecting training data by quality: filters, classifiers, and why curation beats raw scale.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, data]
version: 1.0.0
---
# Dataset Curation for Language Models

## Purpose

Explain data curation as the highest-leverage step in LM training:
systematic quality filtering of web text, and why a smaller clean
corpus beats a larger dirty one.

## When to use

- Building any training corpus (cf. prepare_corpus.py patterns).
- Diagnosing a model that learned spam/boilerplate style.
- Allocating effort between data and architecture.

## Core ideas

Raw web text is mostly boilerplate, SEO spam, machine-generated
filler, and duplication. Curation pipeline stages:

1. **Language ID** - keep what your tokenizer/model targets.
2. **Heuristic filters** - length bounds, symbol/number ratios,
   repetition detectors ("buy now buy now"), line-length sanity.
3. **Quality classifiers** - train a small classifier on curated
   good vs raw web text; keep top-scoring documents. This single
   step historically gave some of the biggest quality jumps.
4. **Domain balancing** - cap overrepresented domains (forums,
   e-commerce) so they don't dominate; upsample books, reference,
   code deliberately.

Empirical rule: at fixed compute, better data beats bigger models.
A 1B model on clean data outperforms a 3B model on sludge on most
downstream measures.

## Gotchas

- Aggressive filtering can erase dialects and minority voices -
  "quality" classifiers encode the biases of their reference set.
  Audit what gets removed.
- Dedup *before* quality scoring (dupes skew classifier training).
- Keep the raw data and the filter decisions (provenance) - you'll
  re-tune filters and want to rebuild without re-crawling.

## Quick reference

- Pipeline: lang ID -> heuristics -> quality classifier -> domain
  balance. Clean beats big; audit removals; keep provenance.
