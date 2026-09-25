---
skill_id: ml_levi_corpus_construction
name: LEVI Corpus Construction
description: How brain training records get built: chunking, record shape, identity records, and deterministic held-out carving.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, levi]
version: 1.0.0
---
# LEVI Corpus Construction

## Purpose

Explain how LEVI's brain corpora are actually built - the record
shape, the chunking, the identity records, and the held-out carving -
so new corpus work follows the same contracts.

## When to use

- Adding a new corpus domain (the ml_* pattern here is the template).
- Debugging corpus quality via loss behavior.
- Reading corpus_stats.json / manifest files.

## Core ideas

Record shape: `{"text", "kind", "register"}` (plus optional sidecars
like source/topic in curriculum corpora). `prepare_corpus.py`
chunks source text into ~512-token records - chunking keeps records
uniform for batching and lets the corpus mix sources by *record*,
not by file.

**Identity records:** one per LEVI register, written into the corpus
so the brain meets LEVI's voice during training. The register count
(14) is asserted in tests, never hand-written - the corpus can't
silently drift out of sync with the persona lattice.

**Held-out carving:** `carve_heldout.py` removes ~20 records from the
training pool into a held-out file, stratified by kind, with a fixed
seed (20260921) - deterministic, so the eval gate measures genuinely
unseen material and reruns agree.

**Manifests:** corpus builds write manifests (generator name/version,
seed, timestamp, record counts, char counts, record shape, sources)
- e.g. corpus_curriculum_manifest.json. A corpus without a manifest
is an anecdote; with one, it's reproducible.

## Gotchas

- Chunk size interacts with the model's block size: chunks much
  longer than block get truncated silently - keep chunking <= block.
- Identity records are tiny vs the corpus; they flavor the voice,
  they don't teach it. Don't expect persona from 14 records.
- Any corpus edit (dedup, re-chunk) changes the seed story - rebuild
  manifests and re-carve held-out afterward.

## Quick reference

- Records: {text, kind, register}, ~512-token chunks. Identity: one
  per register (test-asserted count). Held-out: seeded stratified
  carve. Manifest every build.
