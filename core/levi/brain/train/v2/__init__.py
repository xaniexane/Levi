"""LEVI brain v2 train/teach harness.

Config-driven training infrastructure. The v1 scripts (train.py / eval.py)
are left untouched; v2 composes the same pipeline from replaceable parts:

- config          — ONE YAML file: model size, data mix, schedule, eval cadence
- corpus_manager  — dedupe, versioned manifests, seeded train/val/test splits,
                    hard policy: news-tagged corpora are REJECTED from training
- curriculum      — simple->complex ordering of approved teaching material
- trainer         — the training loop itself: reads a Config, stages the
                    curriculum, trains with checkpointing, calls the eval
                    harness on cadence (needs torch; everything else is
                    torch-free)
- checkpoint      — atomic saves, manifest, resume-from-latest, pruning
- eval_harness    — honest held-out perplexity + probe evals, baseline
                    comparison, JSON reports that say "not capable" plainly

The model and tokenizer are PLUGGABLE via config: give dotted import-path
strings for a builder callable and a tokenizer, e.g.::

    model:
      builder: "levi.brain.train.model_v2:build_model"   # (cfg) -> model object
      ...

The model object only needs ``logits_for_batch(prefixes) -> np.ndarray``
of shape (B, V); the tokenizer needs ``encode`` / ``decode`` / ``vocab_size``.
The IMPROVE worker's model_v2/tokenizer plug in here without changes.

Nothing here claims capability LEVI does not have. Numbers are reported
as measured; low scores are reported as low scores.
"""

from levi.brain.train.v2 import (
    checkpoint,
    config,
    corpus_manager,
    curriculum,
    eval_harness,
    trainer,
)

__all__ = [
    "checkpoint",
    "config",
    "corpus_manager",
    "curriculum",
    "eval_harness",
    "trainer",
]
