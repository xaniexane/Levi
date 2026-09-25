# Native brain v2 (`tiny-gpt-v2`) — verified RESULTS

Record kept honest: every claim below is backed by a file the author
personally inspected. Where a claim cannot be verified it says so.

## Verdict (as of 2026-09-17 ~23:35 CDT / 2026-09-18 04:35 UTC, verified by brain-resume worker)

**COMPLETE — 5,400 / 5,400 steps.** Verified on disk:

- Final line of `train.log`:
  `trainer: done. {'name': 'tiny-gpt-v2', 'steps': 5400,
  'final_ema_loss': 3.6466548409635013, 'config_hash': 'c6e8fa46…', ...}`
- Final training line: `trainer: step 5400/5400 loss=4.0380 ema=3.6467
  lr=3.00e-05 elapsed=141s` (this segment: 5000→5400, resumed 2026-09-17
  ~23:03 CDT per Chauncey's authorization; ~2.4 min of training, then a
  ~26-min final eval — the eval harness runs ~18+ min per report).
- `checkpoints/ckpt-005400.npz`: 62,886,664 bytes, saved
  2026-09-18T04:05:49Z (= Sep 17 23:05:49 CDT); `__step__`=5400 verified
  by loading the file (52 arrays); sha256 prefix `5fe41a96…`.
- `reports/eval-step-005400.json` (step 5400): held-out nll/token 4.8284,
  **perplexity 125.01** (n_tokens 17877).
- Training process exited cleanly (no longer in `ps`).
- Path note (corrected 2026-09-17): the run dir is at repo root
  `~/workspace/levi/runs/tiny-gpt-v2-20260916/`, not under
  `core/levi/brain/`.

History (superseded by completion above):

- The run first reached **step 4,500 / 5,400** on 2026-09-16 and died
  silently mid-run (no error, no traceback). The stale "step 3,000"
  note was corrected.
- Resumed ~20:35 CDT 2026-09-17 from `ckpt-004500.npz`; reached
  **step 5,000 / 5,400 (92.6%)** at 20:42 CDT and died silently AGAIN
  (ckpt-005000.npz, 62,884,639 bytes, ema 3.9327).
- Resumed ~23:03 CDT 2026-09-17 from `ckpt-005000.npz` on Chauncey's
  authorization — completed to 5,400 with no incident.

## Model config (from `core/levi/brain/train/v2/train.yaml`)

- 6 layers / 6 heads / 384 embd, vocab 8192, block 512, RoPE, RMSNorm,
  SwiGLU FFN, tied embeddings — **13,767,552 params**
- 5,400 steps, batch 32, seq 128, cosine LR 3.0e-4 → 3.0e-5, warmup 100
- Checkpoint every 500 steps (keep_last 5), eval every 500 steps

## Verified checkpoints — `runs/tiny-gpt-v2-20260916/checkpoints/`

(Git-ignored; local only. Manifest `checkpoints.json` carries sha256.)

| step | file | bytes | loss | saved (UTC) |
|------|------|-------|------|-------------|
| 4500 | ckpt-004500.npz | 62,885,622 | 4.1584 | 2026-09-16 22:40:02 |
| 4000 | ckpt-004000.npz | 62,882,654 | 4.1460 | 2026-09-16 22:19:21 |
| 3500 | ckpt-003500.npz | 62,883,320 | 4.2174 | 2026-09-16 21:23:11 |
| 3000 | ckpt-003000.npz | 62,885,982 | 4.2232 | 2026-09-16 19:06:12 |
| 2500 | ckpt-002500.npz | 62,881,141 | (see train.log) | 2026-09-16 18:45 |

ckpts 500–2000 were pruned by keep_last=5. **ckpt-005400 is the final.**

Newest verified checkpoint (2026-09-18T04:05:49Z = Sep 17 23:05:49 CDT):

| step | file | bytes | ema loss | sha256 (prefix) |
|------|------|-------|----------|-----------------|
| 5000 | ckpt-005000.npz | 62,884,639 | 3.9327 | b81adb4a… |
| **5400** | **ckpt-005400.npz** | **62,886,664** | **3.6467** | **5fe41a96…** |

Final EMA loss 3.6467 (`trainer: done.` summary). Prior silent-death
incidents at steps 4,500 and 5,000 are recorded in the verdict history
above; the final resume completed cleanly.

## Verified eval reports — `runs/tiny-gpt-v2-20260916/reports/`

| step | nll/token | perplexity | recorded (UTC) |
|------|-----------|------------|----------------|
| 1000 | 4.9476 | 140.84 | 2026-09-16 17:40:33 |
| 2000 | 4.8678 | 130.03 | 2026-09-16 18:22:17 |
| 2500 | 4.7364 | 114.02 | 2026-09-16 18:45:27 |
| 4000 | 4.7791 | 118.99 | 2026-09-16 22:19:21 |
| **5400** | **4.8284** | **125.01** | **2026-09-18 04:31** |

Perplexity improved 140.8 → 114.0 through step 2500, then drifted
119.0 (step 4000) → 125.0 (step 5400). Trend is recorded as-is; no
conclusion drawn. Final-step train loss 4.0380 vs EMA 3.6467 — the
loss trace is noisy; the EMA is the smoother signal.

## v1 (superseded — not the current target)

`core/levi/brain/weights/tiny-gpt.pt` — 13,365,895 bytes, 2026-09-15 18:07.
`train_log.json`: 600 steps, loss 5.283 → 2.107 (min 2.069), held-out 1.857.
Git-ignored via `core/levi/brain/weights/.gitignore` (also ignores
`train_log.json`, `eval.json`, `samples.md`).

## Conventions worth keeping

- Runtime artifacts (checkpoints, corpus snapshots, logs, reports) stay
  local under `runs/` (`runs/.gitignore`: ignore `*`, except `LAUNCH.md`
  and `.gitignore`). This RESULTS.md is the committed record; the run dir
  is not.
- Resume path: re-run the exact LAUNCH.md command
  (`runs/tiny-gpt-v2-20260916/LAUNCH.md`); the trainer auto-resumes from
  the latest checkpoint and refuses config-hash mismatches.
- Torch lives ONLY in `/home/hatch/workspace/.venv-vyve-post`
  (py 3.12, torch 2.14.0+cpu). System `python3` has no torch — do not use it.

## What this file does NOT claim

- The run finished all 5,400 steps (verified). "Trained" means
  training ran to the planned step count with a final checkpoint —
  no quality/benchmark claim beyond the eval perplexity table above.
- No accuracy/benchmark claims beyond the eval perplexity table above.
