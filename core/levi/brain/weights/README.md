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
