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

The corpus also carries **identity records**: one per KAI-9000 register
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
