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
end on LEVI's own data, and serve as a smoke test for corpus quality
(if loss doesn't move, the corpus is broken).

What it **can't** do: answer questions, hold a conversation, or replace
any provider. It is not wired into the agent loop and should not be.

## 4. The path to a real brain

`finetune_lora.py` documents the real upgrade, never run here: LoRA
fine-tune the `levi-local` Qwen weights on `corpus.jsonl` (converted to
instruction pairs), merge, quantize to GGUF, drop into `~/.levi/models`.
That needs a GPU with 8GB+ VRAM. Until then, the agent's intelligence
comes from its providers + the curriculum knowledge base it can read —
which is already genuinely useful via `course_brief` / `course_search`.

## 5. News stays out of the weights (deliberate)

`core/levi/knowledge/news/` (see docs/NEWS.md) is **never** fed to
`prepare_corpus.py`. News goes stale; weights are for stable knowledge.
Dated recall lives in per-day JSONL and is read at runtime by
`news_latest` / `news_search`, always with dates attached. Baking
headlines into weights would produce a brain that confidently recalls
last month's news as current — exactly the failure this design avoids.
