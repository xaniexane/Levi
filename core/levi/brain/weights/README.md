# LEVI native brain weights — provenance

`tiny-gpt.pt` (13.4 MB) is the proof-of-learning model, trained 2026-09-15
on the LEVI course corpus. It is **gitignored** — this README records
provenance so the binary can be verified or reproduced.

- **Run**: `core/levi/brain/train/train.py --steps 600 --seed 1337`
- **Corpus**: `core/levi/brain/train/corpus.jsonl` — 353 chunks
  (14 LEVI identity records + 339 course chunks), 847,990 chars.
  News is deliberately excluded (see docs/BRAIN_TRAINING.md §5).
- **Model**: char-level causal GPT — 4 layers, 256 dim, 4 heads,
  block size 128, vocab 162 chars → **3,271,168 params**.
- **Training**: 600 steps, AdamW, CPU, 1252.7s.
- **Loss**: 5.2830 → 2.1067 (min 2.0692); held-out 1.8570.
- **sha256**: `7474e24f97c8df50904a26367a27e2e57dbaa050b0238cba1b1e79a46997e3b2`

Eval artifacts (committed): `train_log.json`, `eval.json`, `samples.md`.

Honest verdict: the loss curve proves the architecture learns, but the
samples are garbled — a 3.3M-param char model cannot reason, converse, or
replace `levi-local`. It is a training-pipeline proof, not a brain.
Reproduce with the venv at `~/workspace/.venv-vyve-post`
(`train/requirements.txt`, torch CPU).

---

# Torch-free model runner (`core/levi/brain/runtime.py`)

LEVI's own Ollama-style local model runner. Stdlib-only at import;
NumPy is used lazily and only if already installed. **Zero runtime
network calls.** The old torch path (`inference.py`) is untouched and
still available via `load_brain_auto()` when torch is importable.

- **Portable weights**: `tiny-gpt-portable/` — `manifest.json` plus 49
  raw little-endian float32 blobs, format `levi-brain-portable/1`.
  Exported from `tiny-gpt.pt` (never modified) with a one-off torch
  script; every blob round-trips byte-identically against the torch
  tensors. Manifest sha256:
  `0f72759b56b41b0a05c209e58a261ee8452d6e5a128119b81601e93c054202bb`
  (49 tensors incl. 4 derived causal masks; the runtime loads the 45
  parameter tensors and rebuilds the masks itself).
- **Backends**: `numpy` (vectorized, preferred) and `stdlib`
  (pure-Python KV-cache, fallback). Both cross-checked against the
  torch reference: max logit abs diff < 4e-6, argmax continuations
  byte-identical.
- **Registries**: `register_architecture` / `get_architecture` /
  `list_architectures`; `register_model` / `get_model` /
  `list_models` / `unregister_model`. Unknown model or architecture
  raises an honest `BrainError` — never a silent substitution.
- **Built-ins**: arch `char-gpt`, model `levi-native` (LEVI's own).
  `qwen-class` is a reserved arch id and is NOT implemented.
- **Identity law**: `origin="levi"` models are labeled "LEVI native
  model"; `origin="reference"` models must name a
  `plugins/references.py` entry and are labeled
  "reference model (not LEVI)" on every display path. Model output is
  always labeled **raw brain continuation — not reasoning**; the rules
  engine stays the decider.
- **CLI**: `levi brain run levi-native "the prompt"`
  (`--temperature`, `--seed`, `--max-chars`, `--backend`,
  `--no-record`); `levi brain models` lists the registry.
- **Loopback server** (optional, off by default):
  `runtime.serve_loopback()` returns an unserved HTTP server bound to
  127.0.0.1 only — non-loopback hosts raise `BrainError`. Endpoints:
  `GET /models`, `POST /run`.

## Observation store — the training substrate

Every run through the runner appends one observation record to the
append-only local log `~/.levi/model-observations.jsonl` (owner-only:
file `0o600`, dir `0o700` — same pattern as `~/.levi/references.json`).
Recording is **on by default** for local runs (your machine, your
models); pass `record=False` / `--no-record` to disable per run.
Never networked. This log is what the future training track will train
LEVI's brain off (distillation) — the loop itself is not built here,
only this clean record format. Prompts are stored in plaintext locally
so the trainer can consume them; disable recording for anything you
would not want on disk.

Schema `levi-observation/1` fields: `schema`, `ts`, `model_id`,
`arch`, `origin`, `model_label`, `prompt`, `prompt_truncated`,
`prompt_sha256`, `output`, `output_chars`, `sampling`
(`temperature`, `seed`, `max_new_chars`), `timing` (`started_at`,
`finished_at`, `seconds`, `backend`), `receipt`
(`ok` + `unmapped_chars`/`params`, or `ok: false` + honest `error`),
`label` ("recorded model output — not LEVI reasoning"). Corrupt lines
are skipped and counted on read — one bad line never poisons the log.
Example record:

```json
{"model_id": "levi-native", "arch": "char-gpt", "origin": "levi",
 "model_label": "LEVI native model", "prompt": "the river runs",
 "prompt_truncated": false,
 "prompt_sha256": "5ff2fbe950bc88ac7c1ab8bd66983ddb0214e58c08ea30e37ab8d1a9432c4a2d",
 "output": "tront th", "output_chars": 8,
 "sampling": {"max_new_chars": 8, "temperature": 0, "seed": 7},
 "timing": {"started_at": "2026-09-21T02:16:01.380020+00:00",
            "finished_at": "2026-09-21T02:16:01.912916+00:00",
            "seconds": 0.533, "backend": "numpy"},
 "receipt": {"ok": true, "unmapped_chars": 0, "params": 3271168},
 "label": "recorded model output — not LEVI reasoning",
 "schema": "levi-observation/1", "ts": "2026-09-21T02:16:01.913552+00:00"}
```

## Adding a new architecture

1. **Validated weight format** — extend `load_portable_tensors()` (or
   add a sibling loader): a `manifest.json` declaring format version,
   per-tensor names/shapes/dtype/sha256, plus raw blobs. Every blob
   is length-checked and sha256-checked before a single float is used.
2. **Tokenizer implementation** — the `Architecture.tokenizer` field
   documents it; the handle implements `encode()`/`decode`. For
   char-gpt: the ordered vocab comes from the manifest; out-of-vocab
   input maps to a space and is counted honestly.
3. **Forward pass / model-handle implementation** — subclass
   `ModelHandle` and implement `describe()`, `encode()`, `generate()`
   (plus `logits_for()` for cross-checking). Register with
   `register_architecture(Architecture(arch_id=...,
   description=..., load=..., weights_format=..., tokenizer=...))`,
   then `register_model(ModelSpec(model_id=..., arch=...))`. Reference
   (non-LEVI) models must set `origin="reference"` and name their
   `plugins/references.py` entry — they can never be labeled as LEVI.
