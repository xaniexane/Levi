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

**Harness factory:** `tok.build_tokenizer(spec)` — load, or train + save,
from a JSON spec. The v2 harness calls the tokenizer builder with no
arguments; the spec is then read from `$LEVI_TOKENIZER_SPEC` or
`train/tokenizer_spec.json` (shipped; documents the canonical recipe:
vocab 8192 on `corpus.jsonl`). Spec keys: `path`, `vocab_size`,
`corpus`, `text_field`, `max_train_chars`, `force_retrain` (unknown keys
rejected). Resolution: existing `path` → load; missing `path` + `corpus`
→ train, save, return; missing `path` and no `corpus` → loud
`FileNotFoundError` with the training command (never a silently wrong
vocabulary). `model_v2.build_tokenizer` (the name the harness docstring
references) delegates to the same spec resolution, so both entry points
behave identically.

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

**Round-5 hardening:**
- Malformed JSONL lines fail fast with `path:line N` in the message —
  a corrupt corpus can never train quietly on a subset of itself. Both
  the public `iter_jsonl_docs` and the pipeline's internal plan builder
  share one strict parser (`_parse_record`); previously the plan
  builder silently skipped bad lines while the public iterator raised.
- Non-object JSON records (e.g. a bare array) raise a clear error
  instead of dying on a bare `AttributeError`.
- Duplicate doc ids are deduped (first occurrence wins) and hash to
  one split, so a duplicated doc can never leak from train into val.
- Manifest robustness: unknown doc ids in a manifest are ignored
  without crashing; a stage missing `doc_ids` is an empty stage.
- New introspection API for split debugging:
  `iter_train_docs()` / `iter_val_docs()` yield `(doc_id, text)` in
  stream order — the TRAIN worker can verify split assignment and
  curriculum order without decoding batches.
- `build_model` rejects unknown config keys loudly (a typo'd YAML key
  no longer silently falls back to the default).

## 4. Ablations — do the modern pieces matter at small scale?

v2 (RMSNorm + RoPE + SwiGLU) vs v1-style (LayerNorm + learned absolute
positions + GELU), matched ~1.3M-param budgets, identical synthetic
data, identical batch order, identical seeds, 200 steps, batch 8,
block 128. (`/tmp/ablate.py`; synthetic word salad — speed of learning
local statistics, nothing more.)

| step | v2 loss | v1-classic loss |
|---|---|---|
| 1 | 7.0408 | 7.0065 |
| 50 | 3.1694 | 2.8955 |
| 100 | 2.0406 | 1.8673 |
| 150 | 1.7023 | 1.6372 |
| 200 | 1.6298 | 1.5998 |

Honest reading: the classic baseline is slightly ahead at every
checkpoint, and v2 cost ~25% more CPU (215 vs 172 CPU-s for 200 steps).
At ~1M params on 200 steps of synthetic data, the modern components
show **no advantage** — the gap is optimization dynamics at small
scale, not capability. v2 stays the documented architecture (roadmap
target; the gap is small), but no superiority is claimed on this
evidence. (`~/workspace/brain_bench/ablate.py`, result JSON alongside.)

## 5. Longer context (1024) — memory and throughput

Measured on the default 13,767,552-param config
(`~/workspace/brain_bench/microbench.py`, contention-independent
CPU seconds, peak RSS via `resource`):

| block | batch | tokens/step | CPU-s/step | tokens/CPU-s | peak RSS |
|---|---|---|---|---|---|
| 512 | 4 | 2048 | 8.048 | 254.5 | 1678 MB |
| 512 | 8 | 4096 | 13.748 | 297.9 | 2616 MB |
| 1024 | 4 | 4096 | 16.659 | 245.9 | 2836 MB |
| 1024 | 4 + grad-ckpt | 4096 | 16.485 | 248.5 | 2836 MB |

Readings: block 1024 runs fine and fits comfortably (2.8 GB peak on a
7.9 GB box), but costs ~21% more CPU per token than block 512 at the
same tokens/step (attention is quadratic in block size). Batch 8 is the
most token-efficient (297.9 tok/CPU-s — better amortization of fixed
per-step overhead). Gradient checkpointing is ~neutral at these sizes
here; its memory win matters at larger batches than fit this box
anyway. Prefer wider batches over longer contexts on 2 CPUs.

## 6. Measured CPU throughput (this machine)

Use the §5 table (CPU-s/step is contention-independent). Rule of thumb
for the default config at block 512: **~250–300 tokens per CPU-second**,
i.e. ~8 CPU-s per 2048-token step. A 5400-step run at 2048 tok/step ≈
12 CPU-hours on this box; the live TRAIN run (§9) uses block 256 and
measures ~4.6 s/step wall including trainer overhead.

Machine: 2-CPU Linux sandbox, torch 2.14.0+cpu, 2 threads.

## 7. Training recipe (v2)

1. `python3 tok.py --corpus corpus.jsonl --vocab 8192 --out tokenizer.json`
   (or reuse the shipped `train/tokenizer.json`)
2. Write `train.yaml` (see `v2/config.py` docstring); point
   `model.builder` at `levi.brain.train.model_v2:build_model` and
   `model.tokenizer` at `levi.brain.train.model_v2:build_tokenizer`.
3. Harness run stages the curriculum, trains with the v2 checkpoint
   format, and evaluates on cadence via `v2/eval_harness.py`.
4. Budget from §6: at ~8 CPU-s per 2048-token step (block 512,
   batch 4), 2000 steps ≈ 4.4 CPU-hours on this box. Prefer gradient
   accumulation over large batches on 2 CPUs.

## 9. Live training run (TRAIN worker, in flight)

Reference numbers from the TRAIN worker's background run, which uses
this stack (default config, v2 harness, `model_v2:build_tokenizer`):

- Params: **13,767,552** (matches the §5 micro-benchmark config exactly)
- Tokenizer: vocab 8192 BPE, 388 s to train on the train split
- Smoke: 60 steps, loss 6.09 → 4.94
- Full run: 5400 steps ≈ **6.9 CPU-hours** (~4.6 s/step wall including
  trainer overhead), ~690k tokens ≈ 2.8 epochs

Known harness limits found during launch (noted for future harness
rounds; SCAFFOLD's rounds are complete — not edited here): `batch_size`
is config-validated but `_train_step` trains one B=1 sequence per step;
eval `sequence_nll` scores every prefix independently (~63 min per 20k
val tokens — TRAIN caps via `max_val_tokens`); pass `python -u` so
trainer prints aren't buffered to files.

## 8. What this is NOT

- Not a reasoning engine. Not a knowledge store. Not conscious.
- The growth loop's journal/learnings are training signal for the
  future (roadmap §4 item 2); they are not in these weights.
- News stays out of the weights (BRAIN_TRAINING.md §6).
