---
skill_id: ml_levi_tinygpt_v2_architecture
name: LEVI tiny-gpt-v2: Verified Architecture
description: The v2 brain's exact config from train.yaml and RESULTS.md: 13.77M params, RoPE, RMSNorm, SwiGLU, tied embeddings.
risk: info
permissions: []
requires_confirmation: false
tags: [ml, levi]
version: 1.0.0
---
# LEVI tiny-gpt-v2: Verified Architecture

## Purpose

Record the verified architecture of LEVI's native brain v2
(tiny-gpt-v2) - every number below is from
`core/levi/brain/train/v2/train.yaml` and the verified RESULTS.md,
not from memory or assumption.

## When to use

- Working on the v2 brain (inference, continued training, analysis).
- Citing the model's specs accurately.
- Reproducing or extending the run.

## Core ideas

Model (builder `levi.brain.train.model_v2:build_model`):

- 6 layers, 6 heads, n_embd 384, head_dim 64 (even - RoPE requirement)
- Vocab 8192, block size 512, max train seq 128
- RoPE positional embeddings, RMSNorm (pre-norm), SwiGLU FFN with
  hidden = 8/3 * n_embd, plain MHA, **tied** token/output embeddings
- **13,767,552 parameters** exactly (default_param_count verified)

Training: 5,400 steps, batch 32, cosine LR 3.0e-4 -> 3.0e-5, 100
warmup steps, seed 1337. Checkpoints every 500 steps (keep last 5),
eval every 500. Run dir: `runs/tiny-gpt-v2-20260916/` (repo root,
git-ignored; checkpoints.json carries sha256 manifests).

Verified result: completed 5400/5400 steps 2026-09-17; held-out
nll/token 4.8284, **perplexity 125.01**. The run died silently twice
mid-run (steps 4500, 5000) and was resumed from checkpoints -
which is why checkpoint discipline matters.

## Gotchas

- Config hash is verified by the harness before training - a
  tokenizer/model vocab mismatch refuses loudly rather than
  training wrong.
- 5400 steps at batch 32 x seq 128 = ~22M tokens seen: far below the
  ~276M Chinchilla-optimal for 13.8M params. This brain is proof of
  learning, not a capability milestone - see the honest-limits
  playbook.
- Don't "improve" the config from memory; train.yaml is the source
  of truth and comments document *why* each choice was made.

## Quick reference

- 6L/6H/384d, 8192 vocab, RoPE+RMSNorm+SwiGLU+tied, 13,767,552
  params, cosine 3e-4->3e-5, 5400 steps, PPL 125.01 held-out.
