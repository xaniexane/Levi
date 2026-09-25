---
skill_id: ml_deduplication
name: Deduplication of Training Data
description: Why duplicates harm training, exact vs near-dup detection, and MinHash/LSH at web scale.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, data]
version: 1.0.0
---
# Deduplication of Training Data

## Purpose

Explain why training corpora must be deduplicated - memorization,
wasted compute, inflated eval - and the two-level approach: exact
hashes plus near-duplicate detection.

## When to use

- Building any corpus from web crawls.
- A model that recites boilerplate verbatim.
- Eval scores that look too good.

## Core ideas

Duplicates hurt three ways: (1) the model wastes capacity memorizing
repeated text instead of generalizing; (2) repeated sequences get
effectively upweighted, distorting the learned distribution; (3) dupes
spanning train/eval inflate scores and hide overfitting.

Two levels:

- **Exact dedup:** hash normalized documents (sha256 of stripped
  text), keep first occurrence. Cheap, catches mirrors and copies.
- **Near-dup:** MinHash signatures + LSH banding find documents that
  are 80%+ similar (templates with different dates, SEO variants).
  More expensive, catches what hashing misses.

Also dedup *within* documents: repeated paragraphs/headers inside one
page (nav bars, disclaimers) are the most common dupe of all.

## Gotchas

- Dedup across train/val/test boundaries, not just within train -
  cross-split dupes are the silent eval killers.
- Over-dedup can remove legitimately repeated content (licenses,
  standard disclaimers) - usually fine, occasionally load-bearing.
- Order matters: dedup before tokenization stats and before quality
  scoring.

## Quick reference

- Exact: sha256 of normalized text. Near: MinHash + LSH. Dedup
  within docs, across docs, and across splits.
