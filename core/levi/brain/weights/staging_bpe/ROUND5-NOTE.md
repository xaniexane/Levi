# Round 5 transition note (written 2026-09-26 ~21:35 CDT)

Round 4 is training on the OLD corpus (595 dialogue records, loaded at
round start). It is healthy — do NOT kill it (destroy-only-on-harm law).

When round 4 completes (step 6480), launch round 5 with:

    python3 continue_bpe.py --resume --steps 2000 --n-embd 96 --block-size 48

Round 5 will load the ENLARGED corpus automatically:
- corpus_dialogue_train.jsonl: 102,546 records (was 595)
  - 515 original + 80 Grok-session lessons (batches 1-4) + 101,951
    verified zip lessons (4 hand batches + 2000-file + 99,859 from 100k-file)
  - 141 duplicate rows quarantined, never ingested
- Same tokenizer (levi-bpe-v1), same arch — resume is bit-continuous.

Expect round-5 startup to take a few minutes (corpus re-encode of the
102k records). First loss readings after the corpus switch may jump;
that is the distribution widening, not a bug — watch the trend.

## Round 5 launcher + head-to-head (added 2026-09-27, glyph 📊)

Launch round 5 with the wired launcher (it runs the head-to-head
automatically at completion):

    cd core/levi/brain/train && bash run_round5.sh

What it does:
- continue_bpe.py --resume --steps 2000 --n-embd 96 --block-size 48
- then eval_headtohead.py: perplexity of the final checkpoint on 40 pinned
  LEVI-voice bench texts vs gpt2 + TinyStories-33M (own tokenizer each;
  cross-tokenizer ppl is directional only), plus a deterministic LEVI-voice
  coherence check (fixed prompts, fixed seeds).
- writes headtohead-<step>.json and EVAL_HEADTOHEAD.md into this dir.

The head-to-head venv lives at ~/workspace/.headtohead-venv (transformers).
If it is missing, the LEVI leg still runs; baselines are skipped honestly.
