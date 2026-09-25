# LAUNCH — native-brain v2 training run `tiny-gpt-v2`

Config: `core/levi/brain/train/v2/train.yaml` (reconstruction of the
2026-09-16 morning plan: 5,400 CPU steps, 13,767,552 params — every choice
documented in the yaml).

## Pre-flight (already done 2026-09-16)

- [x] `prepare_data.py` staged the frozen corpus snapshot:
  `corpora/{train,val,test}.{jsonl,manifest.json}`
  (739 raw docs → 379 unique after cross-file dedupe; 90/5/5 seeded split)
- [x] `--stage-only` built `curriculum.json` (4 difficulty stages)
- [x] Manifests pin sha256 — the run trains on exactly this data even if
  the live corpus files change afterwards

## Launch command

Run from the repo root (`~/workspace/levi`):

```bash
cd ~/workspace/levi && PYTHONPATH=core nohup \
  /home/hatch/workspace/.venv-vyve-post/bin/python \
  -m levi.brain.train.v2.trainer \
  --config core/levi/brain/train/v2/train.yaml \
  --run-dir runs/tiny-gpt-v2-20260916 \
  > runs/tiny-gpt-v2-20260916/train.log 2>&1 &
echo "PID=$!"
```

Notes:

- **Python**: torch lives only in `/home/hatch/workspace/.venv-vyve-post`
  (torch 2.14.0+cpu, py 3.12). The system python3 has no torch. A
  dedicated `~/workspace/.venv-levi-brain` would be cleaner long-term;
  the borrowed venv is what the morning run used.
- **Do NOT use `python3 -m` with the system python** — it will fail on
  `import torch`.
- **nohup + `&`**: the morning run died with its parent session. nohup
  detaches it; the log and checkpoints survive either way.
- **Resume**: if the run dies, re-issue the SAME command. The trainer
  auto-resumes from the latest checkpoint in `checkpoints/` and refuses
  to resume if the config hash changed (protects against mid-run edits).

## What lives where (all under `runs/tiny-gpt-v2-20260916/`)

| Path | Contents |
|---|---|
| `train.log` | stdout/stderr of the run |
| `corpora/` | frozen data snapshot + sha256 manifests |
| `curriculum.json` | staged simple→complex curriculum |
| `checkpoints/ckpt-SSSSSS.npz` | model checkpoints every 500 steps (+ final) |
| `reports/` | periodic eval reports |

## Monitoring

```bash
# progress (expect a line every 50 steps)
tail -f runs/tiny-gpt-v2-20260916/train.log
# trainer: step 50/5400 loss=5.7880 ema=6.1781 lr=3.00e-04 elapsed=1234s

# checkpoints landed
ls -la runs/tiny-gpt-v2-20260916/checkpoints/

# is it alive?
pgrep -af "levi.brain.train.v2.trainer" | grep -v grep
```

Expected cadence:

- `trainer: step N/5400 loss=… ema=… lr=… elapsed=…s` — every 50 steps
- `trainer: checkpoint -> runs/…/checkpoints/ckpt-NNNNNN.npz` — every 500 steps
- eval report in `reports/` — every 500 steps

## After it finishes

1. Check the final eval report in `reports/` (held-out loss, probes).
2. Promote the final checkpoint per `docs/BRAIN_TRAINING.md`
   (weights stay OUT of git; `core/levi/brain/weights/` has its own gitignore).
3. Record results in the run dir (`RESULTS.md`) before touching the config.
