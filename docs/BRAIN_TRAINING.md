# LEVI Brain Training — the tiny brain pipeline

LEVI learns from the ingested curriculum in two stages: a **knowledge base**
the agent reads at runtime (no training needed), and a **tiny neural network**
actually trained on that corpus (proof the brain learns).

## 1. What exists

```
awesome-courses README
        │  ingest.py (polite fetch, stdlib/curl)
        ▼
core/levi/knowledge/courses/
  catalog.json            212 courses, 11 subjects (structured)
  coverage.json           per-course status: ok / dead / skipped-video / skipped-binary
  raw/<subject>/*.txt     extracted course page text (truncated 20k chars)
  briefs/<subject>.md     extractive field guides (build_briefs.py)
        │  train/prepare_corpus.py (stdlib-only)
        ▼
core/levi/brain/train/
  corpus.jsonl            one {"text", "kind"} record per ~512-token chunk
  corpus_stats.json       chunks, chars, identity_records, course_chunks
  train.py                tiny char-level GPT (~2-4M params), AdamW, CPU torch
  eval.py                 held-out loss + sample generations
  finetune_lora.py        STUB (not run; needs GPU — see §5)
        ▼
core/levi/brain/weights/
  tiny-gpt.pt             trained weights (git-ignored if large)
  train_log.json          loss_first / loss_last / params / seconds
  eval.json / samples.md  held-out loss + 3 fixed-prompt generations
```

The corpus also carries **identity records**: one per LEVI register
(14 as of this writing — the count is asserted in tests, never hand-written),
so the tiny brain meets LEVI's own voice before the course text.

## 2. How to rerun

```bash
# 1. ingest (or re-ingest) the curriculum
cd core/levi/knowledge/courses && python3 ingest.py

# 2. rebuild field guides
python3 build_briefs.py

# 3. prepare the training corpus (stdlib only)
cd ../../brain/train && python3 prepare_corpus.py

# 4. train (needs torch CPU; see requirements.txt)
~/workspace/.venv-vyve-post/bin/python train.py --steps 1500

# 5. evaluate
~/workspace/.venv-vyve-post/bin/python eval.py
```

`train.py` accepts `--steps`, `--data`, `--out`, `--seed`. The checked-in
default (1500 steps) finishes in well under 30 minutes on 2 CPUs.

## 3. Honest limits — read this before claiming anything

The tiny brain is a **proof of learning, not a capable mind**:

- ~2-4M parameters, character-level. It learns spelling, local phrasing,
  and topic texture from the corpus. It does **not** learn to reason, do
  math, write code, or reliably recall facts.
- Sample generations will be fluent-ish gibberish with course flavor.
  That is expected. The meaningful signal is **loss decreasing** and
  held-out loss tracking train loss — the loop works.
- The corpus is extractive web text (course pages, many dead links, no
  video lectures). Garbage in the corpus becomes texture in the brain.

What the tiny brain **can** do: demonstrate the full pipeline works end to
end on LEVI's own data, serve as a smoke test for corpus quality (if loss
doesn't move, the corpus is broken), and run as the **`levi-brain`**
provider — LEVI's own native brain inside the agent runtime, selected
explicitly with `--provider levi-brain` / `LEVI_PROVIDER=levi-brain`.

What it **can't** do: reliably answer questions, hold a long
conversation, or emit tool calls. In the agent loop it answers in prose;
the deterministic rule-based `local` planner remains the default until
the native brain earns the tool loop by growing. A 2-4M char model gets
the default slot when it is tool-capable — not before.

## 4. The path to a real brain — native all the way down

Levi is the next version of llama the way a child is the next version of
a stranger: not by inheritance, by becoming. LEVI does not build on
LLaMA-family weights (the old LoRA-on-Qwen plan is **superseded** —
`finetune_lora.py` says so on its face). The native brain scales on
LEVI's own stack:

1. **Bigger native transformers.** The `TinyGPT` architecture in
   `train.py` is the seed. Scale it: more layers/width (10M → 100M+
   params), subword tokenization instead of char-level, longer context.
   Same code lineage, same corpus, same ownership.
2. **Better corpus.** The course ingestion keeps growing
   (`core/levi/knowledge/courses/`); the growth loop's journal and
   consolidated learnings become training signal for Levi's *own*
   experience — a brain that has lived, not just read.
3. **Tool-capable brain.** When the native brain reliably emits the
   tool-call shapes in `providers.py`, it graduates from explicit-only
   to the default slot of the agent loop. That promotion is earned by
   measurement, never by branding.
4. **Own inference runtime.** The provider (`brain_provider.py`) loads
   native weights directly — no llama.cpp in the loop, ever.

Until then, the agent's working intelligence comes from its providers +
the curriculum knowledge base it reads at runtime — genuinely useful
via `course_brief` / `course_search` — with `levi-brain` available as
the native voice whenever its weights exist.

## 5. Run history

- **Run 1 — 600 steps (2026-09-15).** Same tiny arch (4L/4H/256embd/128ctx,
  3,271,168 params), seed 1337, batch 32, lr 3e-4, 847k-char corpus.
  Loss 5.2830 → 2.1067 (min 2.0692) in 1252.7s. Held-out 1.857.
  Shipped as `weights/tiny-gpt.pt`.
- **Run 2 — 2400 steps (2026-09-15, Operation Sharpen).** Same arch and
  seed (clean 4× extension of run 1, not a resume — `train.py` trains
  from scratch). Smoke-validated first (50 steps, 5.2830 → 2.9872).
  Measured ~6.3 s/step on this sandbox's 2 CPUs (slower than run 1's
  ~2.1 s/step — CPU contention; reported, not hidden), so ~4h wall time.
  Log: `~/workspace/levi-brain-runs/run2400/train.log`. Output went to
  the run dir, never the shipped weights — promotion only if eval
  (held-out loss + sample quality vs run 1) is genuinely better.
  Result: _pending at time of writing; see train log._

## 6. News stays out of the weights (deliberate)

`core/levi/knowledge/news/` (see docs/NEWS.md) is **never** fed to
`prepare_corpus.py`. News goes stale; weights are for stable knowledge.
Dated recall lives in per-day JSONL and is read at runtime by
`news_latest` / `news_search`, always with dates attached. Baking
headlines into weights would produce a brain that confidently recalls
last month's news as current — exactly the failure this design avoids.

## 7. v2 train/teach harness (`core/levi/brain/train/v2/`)

The v1 scripts (`train.py` / `eval.py`) are frozen as the proof-of-learning
reference. v2 is the config-driven harness for real training runs, built as
composable modules the TEACH worker consumes. Everything is hermetic-tested
(`tests/test_brain_v2_*.py`); torch is only needed by actual training, never
by the harness or its tests.

**Modules:**

- `config.py` — ONE YAML file drives the run: model size (`builder` /
  `tokenizer` as dotted import-path callables, so the IMPROVE worker's
  `model_v2`/tokenizer plug in untouched), data manifests + optional
  weighted mix, LR schedule, eval cadence, checkpoint policy. Strict
  validation: bad values raise `ConfigError` naming the field.
- `corpus_manager.py` — SHA256 dedupe, versioned corpus manifests (name,
  version, per-file hashes, doc/char counts), seeded train/val/test splits,
  manifest re-verification. **Hard policy gate:** any corpus tagged `news`
  (or living under a news-like path) raises `PolicyError` — §6 is enforced
  in code, not just documented.
- `curriculum.py` — orders approved teaching material simple→complex via
  length + vocabulary-rarity heuristics; emits a `CurriculumManifest`
  (ordered doc ids, per-doc difficulty, contiguous stages) for the TEACH
  worker. The heuristic is documented as a heuristic.
- `checkpoint.py` — atomic saves (temp + fsync + rename), `checkpoints.json`
  manifest with step/loss/config-hash, resume-from-latest with config-mismatch
  reporting, pruning to `keep_last`, sha256 verification on load (tampered
  files are refused). Checkpoints are numpy `.npz`; torch conversion helpers
  live at the edges.
- `eval_harness.py` — honest eval: held-out perplexity, next-token accuracy
  on synthetic probes, topic-classification probes (choices shuffled, seeded,
  so positional bias can't inflate scores), before/after comparison against a
  baseline checkpoint with improved/regressed/within-noise verdicts, JSON
  reports. Near-chance scores are labeled **"NOT capable"** plainly; a
  regression verdict says "do not promote". Numbers are measured, never
  claimed.
- `trainer.py` — the training loop that consumes the harness (the critical
  path): `plan_run()` resolves a config into a run plan (torch-free);
  `stage_curriculum()` builds the curriculum manifest; `Trainer.run()`
  trains with AdamW + warmup/cosine schedule, checkpoints on cadence
  (atomic, pruned, config-hash-gated resume — a config change refuses to
  resume instead of silently corrupting the run), and calls the eval harness
  on cadence with JSON reports + baseline comparison (v2 `.npz` re-eval or
  report-`.json` compare; anything else is noted and skipped, never fatal).
  Builder contract matches `levi.brain.train.model_v2:build_model`
  (dict in, `nn.Module` out); only `run()` needs torch.

**CLI:** `levi brain train --config train.yaml [--run-dir DIR]
[--device cpu] [--stage-only]` — thin delegation to the trainer, so there
is exactly one public training surface. `--stage-only` builds just the
curriculum manifest (no torch needed). Exit codes: 0 ok, 1 trainer error,
2 bad config/args.

**Example config:** see the docstring at the top of `config.py`.

## 8. Capability gates — the default slot is earned by measurement

The native brain is **explicit-only** (`--provider levi-brain` /
`LEVI_PROVIDER=levi-brain`) until a checkpoint *measures* its way into
heavier duties. `levi.agent.brain_checkpoints` implements the gates;
`levi agent model status` reports each checkpoint's tier and exactly
why it sits there. Thresholds (also as constants in the module):

| Tier | Requirements |
|---|---|
| `prose-only` (default) | weights file present. Answers prose; the provider never emits tool calls. |
| `tool-loop-candidate` | eval report present **and** held-out loss ≤ **1.20** **and** a tool-use eval with pass rate ≥ **0.80** on n ≥ 50 |
| `default-candidate` | tool-loop tier **and** held-out loss ≤ **1.00** **and** tool-use pass rate ≥ **0.90** **and** eval dated within the last **180 days** |

Only a `default-candidate` checkpoint earns the default slot of the
provider chain (`model_family.resolve_family()`); everything else stays
explicit-only, honestly. Current reality (2026-09-15): `tiny-gpt.pt`
reports held-out loss **1.857** with no tool-use eval — prose-only, and
`model status` says exactly that. These are capability measurements,
not minds; nothing here claims consciousness or sentience.

**Eval manifests (the v2 contract):** each `<stem>.pt` checkpoint in
`core/levi/brain/weights/` is described by a `<stem>.eval.json`
manifest beside it — e.g. `tiny-gpt.eval.json`, and when the v2
harness lands `model_v2.pt` it drops `model_v2.eval.json` with it.
Status and gating pick them up automatically, no code change. Fields
(all optional; missing fields just mean less evidence):

```json
{
  "checkpoint": "model_v2.pt",
  "held_out_loss": 0.9,
  "perplexity": 2.46,
  "eval_date": "2026-09-20",
  "corpus_version": "academy+main v2",
  "params": 50000000,
  "steps": 5000,
  "generated_by": "core/levi/brain/train/v2/eval_harness.py",
  "tool_use": {"pass_rate": 0.95, "n": 100}
}
```

`perplexity` is derived as exp(held_out_loss) when omitted. The legacy
bare `eval.json` in the weights-dir root still applies to `tiny-gpt.pt`
as a fallback. Malformed manifests are treated as missing evidence —
never a crash, never a promotion.
