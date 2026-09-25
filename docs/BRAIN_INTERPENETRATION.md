# Brain interpenetration — one phone-sized train-it-yourself brain

Date: 2026-09-22. Directive (Chauncey): *"Put them together with what we
already got. Interpenetrate them."*

Three things become one design — not three side-by-side modules:

1. **The ternary direction** — weights as +1/0/-1 (the Bonsai-2 pattern).
2. **The growing-expert direction** — mixture-of-experts that adds and
   prunes experts mid-training, only a subset active (the mini-AGI pattern).
3. **LEVI's existing native brain** — tiny-gpt (3.3M params, char-level,
   trained 600 steps on the LEVI corpus), the torch-free runtime, the
   BPE-round-three tokenizer, the v2 training harness.

## What interpenetrates with what

```
existing trained linears ──ternarize──> phone stores codes+scales
        │                                        │
        v                                        v
  MLP blocks ──grow──> expert sets ──ternarize──> tiny experts
        │                    │ (top-k active: phone pays for k)
        v                    v
  stream loop ──utilization──> add/prune mid-run ──> stays phone-sized
```

- **Ternary × the real weights** (`core/levi/brain/ternary.py`):
  post-training ternarization of the trained 2-D linears (attention
  qkv/proj, MLP, output head). Embeddings, biases, norms stay fp32.
  The phone stores int8 codes + per-tensor scales; 2-bit packing is
  the projected format (4 weights/byte).
- **Growable experts × the real MLP blocks**
  (`core/levi/brain/growable.py`): each block's MLP becomes a
  `GrowableMLP`. Starts at one expert — gating bypassed, forward is
  bit-identical to today, so the existing forward pass cannot break.
  `add_expert` clones expert 0 + seeded noise; `prune_expert` sheds
  the lowest-utilization expert (never the last). Only top-k experts
  run per token.
- **Streaming batch-1 × the real data path**
  (`core/levi/brain/stream1.py`): the loop as structure — stream a
  batch, forward, cross-entropy, log. No weight updates here (needs
  autograd); the production streamer stays `train/data_pipe.py`
  under torch. The handoff is named in code, not hidden.
- **The three × each other**: experts are stored ternary (growable
  AND tiny); the stream loop drives add/prune from utilization
  (growth mid-run, the mini-AGI direction); ternarization keeps the
  grown model inside the phone's memory band.

## Measured here (this repo, 2026-09-22)

On tiny-gpt's actual trained weights (13.08 MB fp32 params,
`core/levi/brain/weights/tiny-gpt-portable/`), deterministic probe:

| | measured |
|---|---|
| fp32 params | 13.08 MB |
| ternary, int8 codes + scales (measured) | 3.52 MB — **3.71x** |
| ternary, 2-bit packed (projection, labeled) | 1.13 MB — **11.55x** |
| mean \|Δlogit\| vs fp32 (8-char probe) | 0.82 |
| max \|Δlogit\| | 2.47 |
| top-1 agreement (all 8 positions) | 37.5% |

Reading: the size cut is real and lands in the same band as the
vendor direction (~10x at 2-bit). The fidelity cost of *naive*
post-training ternarization on a 3.3M char model is significant —
this is not a free lunch. Recovery path (not built): quantization-aware
fine-tuning on the existing training loop, then re-measure. That
experiment is what this prototype exists to motivate.

Growable mechanics verified: 1-expert forward is bit-identical to the
plain MLP; add/prune keeps shapes and the forward working;
deterministic given seeds (`tests/test_brain_interpenetration.py`).

## Vendor-claimed (UNVERIFIED — treat as directions, not facts)

- Bonsai 2 (PrismML): ternary-compressed 27B at 5.9 GB with "98% of
  benchmark scores intact" — **the company's claim**, for a 27B model
  with quantization-aware training. Not comparable to the naive-PTQ
  measurement above; not reproduced here.
- mini-AGI (r/LocalLLaMA builder): 530M-param MoE that "grows itself
  on an 8GB laptop", batch-1 streaming — **weights unreleased**,
  independent verification impossible as of this writing.

## Untested / explicitly not done

- Quantization-aware retraining (the recovery experiment).
- Expert specialization or load-balancing loss (growth skeleton only).
- A real 2-bit packed matmul kernel (projection only).
- Any full training run — **hard limit stands**: Brain V2 stays
  stopped at ckpt-005400.npz. Prototype + measurement only.
- Phone deployment: the design target is single-digit-GB total
  footprint, inside a modern phone's usable memory band; on-device
  runs on the Moto G are untested.

## Files

- `core/levi/brain/ternary.py` — quantize/dequantize, policy, size +
  divergence measurement. Never touches original weights (copies only).
- `core/levi/brain/growable.py` — `GrowableMLP`, add/prune/top-k,
  built from real block tensors.
- `core/levi/brain/stream1.py` — batch-1 streaming loop skeleton
  (forward + loss + log; optimizer step marked as future torch work).
- `tests/test_brain_interpenetration.py` — the proofs.
