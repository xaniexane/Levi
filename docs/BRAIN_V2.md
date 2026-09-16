# LEVI Native Brain v2 — architecture, measurements, recipes

The v2 brain stack lives in `core/levi/brain/train/` and plugs into the
v2 training harness in `core/levi/brain/train/v2/` (SCAFFOLD worker).
The v1 lineage (`train.py`, `eval.py`, `weights/tiny-gpt.pt`) is untouched.

**Honest scope, read first:** an 8–15M parameter CPU model learns local
statistics and short-range structure. It will NOT reason, plan, or reliably
recall facts. Nothing here claims otherwise; numbers below are measured,
not projected. LEVI is never described as conscious or sentient.

## 1. Model (`model_v2.py`)

`LeviBrainV2`: decoder-only transformer with RMSNorm, RoPE rotary
positions, SwiGLU gated MLP, optional grouped-query attention
(`n_kv_head < n_head`), optional embedding/output weight tying, and an
optional per-block gradient-checkpointing flag. Context up to `block_size`
(512 default, tested to 1024 — see §5).

Harness entry point: `build_model(cfg)` takes a plain dict (the YAML
`model:` section minus `builder`/`tokenizer` keys); unset keys fall back
to `DEFAULT_CFG`. Also `build_tokenizer()` (no-arg; resolves
`$LEVI_TOKENIZER_PATH` or `train/tokenizer.json` — the shipped artifact
below, so the harness works out of the box).

Default config ≈ **13.8M parameters** (vocab 8192, 6 layers, 6 heads,
384 wide, SwiGLU 1024, tied embeddings) — inside the 8–15M target band.

Checkpoints: two formats, one bridge.
- Torch-native `.pt` (`save_checkpoint`/`load_checkpoint`, format
  `levi-brain-v2` v1): config + weights + optimizer + step. For ad-hoc
  experiments. Refuses to load anything that isn't `levi-brain-v2`.
- Harness format (`save_v2_checkpoint`/`load_v2_checkpoint`): the
  canonical numpy `.npz` + `checkpoints.json` manifest from
  `v2/checkpoint.py`, with the model config embedded as
  `__levi_config__`. Loading into a mismatched architecture raises
  instead of silently corrupting. **This is the format the TRAIN
  worker's background run uses.**

## 2. Tokenizer (`tok.py`) — measured on the real corpus

Byte-level BPE, pure-Python stdlib. Vocab layout: ids 0–255 raw bytes,
256–259 `<pad>/<doc>/<eod>/<unk>` (never emitted by `encode`; the data
pipeline inserts `<doc>`/`<eod>`), 260+ merges. Lossless round-trip on
any UTF-8 text, verified byte-exact.

**Trained artifact:** `core/levi/brain/train/tokenizer.json`
(vocab 8192 = 7932 merges, trained on `train/corpus.jsonl` — the
existing course corpus). Regenerate with:
`python3 tok.py --corpus corpus.jsonl --vocab 8192 --out tokenizer.json`.

Measured on this machine (2-CPU sandbox):

| metric | value |
|---|---|
| Corpus | 353 docs, 847,130 chars (`corpus.jsonl`) |
| BPE training (7932 merges) | ~131 CPU-s |
| Round-trip exactness | **353/353 docs byte-exact** |
| Compression | **2.743 chars/token** |
| vs char-level baseline (1.00) | **2.74× fewer tokens** |
| Full-corpus encode + decode | 6.5 s |

Interpretation: at ~2.7 chars/token, the same 512-token context window
covers ~2.7× more text than the v1 char-level model, and a training step
processes ~2.7× more text per token budget. (Shorter than the ~4× typical
of web-scale BPE because the corpus is dense instructional prose with
code fragments; still a clear win over char-level.)

**Round-2 fix (measured, then fixed):** `encode()` used to apply the
byte→unicode map *before* splitting words. The map turns whitespace
bytes into non-whitespace chars, so the pretokenizer saw each document
as one giant "word" and BPE ran quadratic — 106 s for a single 10KB
doc, and full-corpus encoding projected to tens of minutes. Words are
now split on the raw text first (exactly mirroring training):
10 KB doc encodes in **0.010 s**, token-for-token identical output,
full corpus in 6.5 s. Covered by
`test_encode_splits_words_before_byte_mapping`.

## 3. Data pipeline (`data_pipe.py`)

Streaming JSONL → tokenized batches: document-boundary-aware packing
(every doc ends with `<eod>`; each batch carries `segment_ids`), and
with `isolate_docs=True` (default) an additive attention mask that is
causal *and* block-diagonal over documents — no cross-document attention
unless explicitly disabled. Curriculum manifests order documents by
stage (unlisted docs stream first — documented, not hidden). The
train/val split is a deterministic hash of the doc id, so it needs no
second pass and is stable across runs.

Batch dict: `input_ids` (B,T), `labels` (B,T, shifted by one),
`segment_ids` (B,T), `attn_mask` (B,1,T,T) or None.

## 4. Ablations — do the modern pieces matter at small scale?

v2 (RMSNorm + RoPE + SwiGLU) vs v1-style (LayerNorm + learned absolute
positions + GELU), matched ~1.3M-param budgets, identical synthetic
data, identical batch order, identical seeds, 200 steps, batch 8,
block 128. (`/tmp/ablate.py`; synthetic word salad — speed of learning
local statistics, nothing more.)

| step | v2 loss | v1-classic loss |
|---|---|---|
| 1 | TBD | TBD |
| 50 | TBD | TBD |
| 100 | TBD | TBD |
| 150 | TBD | TBD |
| 200 | TBD | TBD |

TBD — honest reading goes here when the run finishes. Expectation set
up front: at 1.3M params on synthetic data, any gap is about
optimization dynamics, not capability.

## 5. Longer context (1024) — memory and throughput

TBD — smoke run at block_size 1024, batch 4, measuring peak RSS and
steps/sec, with and without gradient checkpointing.

## 6. Measured CPU throughput (this machine)

Default config (13.8M params), random-token micro-benchmark
(`/tmp/microbench.py`), contention-independent CPU seconds:

| block | batch | tokens/step | CPU-s/step | tokens/CPU-s | peak RSS |
|---|---|---|---|---|---|
| 512 | 4 | 2048 | TBD | TBD | TBD |
| 512 | 8 | 4096 | TBD | TBD | TBD |
| 1024 | 4 | 4096 | TBD | TBD | TBD |
| 1024 | 4 + grad-ckpt | 4096 | TBD | TBD | TBD |

Early smoke (10.9M-param config, batch 4, block 512, 30 steps):
loss 6.44 → 3.74, 55 tokens/s wall under heavy multi-worker load —
wall numbers are contention-inflated; budget from the CPU-s column
above, not from guesses.

Machine: 2-CPU Linux sandbox, torch 2.14.0+cpu, 2 threads.

## 7. Training recipe (v2)

1. `python3 tok.py --corpus corpus.jsonl --vocab 8192 --out tokenizer.json`
   (or reuse the shipped `train/tokenizer.json`)
2. Write `train.yaml` (see `v2/config.py` docstring); point
   `model.builder` at `levi.brain.train.model_v2:build_model` and
   `model.tokenizer` at `levi.brain.train.model_v2:build_tokenizer`.
3. Harness run stages the curriculum, trains with the v2 checkpoint
   format, and evaluates on cadence via `v2/eval_harness.py`.
4. Budget from §6: at X steps/sec, 2000 steps ≈ Y hours on this box.
   Prefer gradient accumulation over large batches on 2 CPUs.

## 8. What this is NOT

- Not a reasoning engine. Not a knowledge store. Not conscious.
- The growth loop's journal/learnings are training signal for the
  future (roadmap §4 item 2); they are not in these weights.
- News stays out of the weights (BRAIN_TRAINING.md §6).
