---
skill_id: ml_dataloader_design
name: DataLoader Design: Shuffle, Batch, Prefetch
description: Building a training data pipeline that keeps the accelerator fed: shuffling, batching, workers, prefetch.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, data]
version: 1.0.0
---
# DataLoader Design: Shuffle, Batch, Prefetch

## Purpose

Explain the data-loading side of training throughput: the pipeline
must deliver shuffled batches faster than the GPU consumes them, or
the most expensive hardware in the building idles.

## When to use

- Training throughput is below expectations.
- Designing streaming ingestion (cf. data_pipe.py patterns).
- Debugging epoch-boundary stalls.

## Core ideas

The pipeline: read -> decode -> tokenize -> shuffle -> batch ->
pad/collate -> prefetch -> device. Each stage can starve the next:

- **Shuffle:** buffer-based shuffling (reservoir of N examples) for
  streams too big to shuffle globally; full permutation for
  epoch-based file datasets. Shuffle *before* batching.
- **Batch:** group by similar length (bucketing) to cut padding waste;
  or pack sequences (see packing playbook).
- **Workers + prefetch:** multiple loader workers prepare batches on
  CPU while the GPU trains; prefetch depth 2-4 hides latency spikes.
- **Tokenize once:** cache tokenized output (memmap, arrow) -
  re-tokenizing every epoch is pure waste.

Measure: GPU utilization and batch-wait time. If the GPU waits on
data, the fix is in the loader, never in the model.

## Gotchas

- Too many workers thrash disk/CPU; too few starve the GPU. Tune by
  measurement, typically 4-8.
- Shuffling with a tiny buffer on sorted data (all of class A, then
  all of class B) produces correlated batches - the buffer must span
  the sort order.
- Random seeds for worker shuffling must differ per worker and per
  epoch, or "shuffling" repeats patterns.

## Quick reference

- Tokenize once and cache. Shuffle before batch. Bucket by length.
  Workers + prefetch so the GPU never waits. Measure batch-wait.
