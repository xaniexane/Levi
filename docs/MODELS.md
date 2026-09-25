# LEVI Models — LEVI is the model; everything else is a selectable source

The agent runtime's default slot belongs to the **LEVI model family**.
Cloud providers and the rule-based planner are selectable sources you
can switch to per run — they are not the default, and they are not
LEVI.

## The family

| LEVI name | Kind | Base | What it is |
|---|---|---|---|
| `levi-tiny` | **native** | — | LEVI's own brain: a transformer trained from scratch on LEVI's own corpus. Weights: `core/levi/brain/weights/tiny-gpt.pt`. Genuinely LEVI's — LEVI architecture, LEVI data, no LLaMA weights, no llama.cpp. |
| `levi-0.6b` | **remix** | `qwen3-0.6b` | Levi remix of Qwen3-0.6B (Q8_0, ~640MB, Apache-2.0). LEVI-packaged: downloaded with `levi agent model pull`, served by LEVI's own local runner. |
| `levi-4b` | **remix** | `qwen3-4b` | Levi remix of Qwen3-4B (Q4_K_M, ~2.5GB, Apache-2.0). LEVI-packaged, same runner. Needs ~4–6 GB free RAM. |

**Native vs remix, stated plainly:** `levi-tiny` is LEVI-trained.
The `levi-*` remixes are third-party bases (Qwen3) that LEVI downloads,
verifies (SHA-256), and serves itself. A remix is LEVI-packaged, not
LEVI-trained — the registry records `base:` on every remix so the
distinction is never blurred.

## Default resolution

With no `--provider` flag and no `LEVI_PROVIDER` env var, the agent
uses the best available LEVI weight, in this order:

1. Your persisted choice (`levi agent model use <name>`) — when it is
   actually downloaded and runnable.
2. `levi-tiny` — when the native brain weights are present and torch
   is importable.
3. The largest downloaded `levi-*` remix whose runner is present.
4. The deterministic rules planner (`local`) — the honest fallback.

`levi agent model status` shows exactly which weight is active and why.
The loop always reports the provider it actually used, so a fallback
is never silent.

## CLI

```
levi agent model list             # LEVI family first, then other sources
levi agent model status           # active weight, readiness, honest limits
levi agent model pull levi-0.6b   # download a remix (~640MB) + runner
levi agent model pull levi-4b     # the larger remix (~2.5GB)
levi agent model use levi-4b      # persist the default LEVI weight
levi agent run "task" --provider levi-4b   # per-run override
```

`model use` writes `~/.levi/agent/model_choice.json`. Delete the file
(or pick another weight) to go back to automatic best-available
resolution. `LEVI_PROVIDER=levi-4b` overrides everything except an
explicit `--provider` flag.

## Honest capability notes

- **`levi-tiny`**: prose continuations only — it does **not** emit tool
  calls, so inside the tool loop its answer is taken as final. At tiny
  scale the output is fluent-ish gibberish with corpus flavor
  (documented in `docs/BRAIN_TRAINING.md`). It holds the default slot
  because it is LEVI's, and it earns real loop capability by growing —
  by measurement, never by branding.
- **`levi-0.6b`**: runs the agent loop's tools offline via native
  tool-call support. A 0.6B model — good for simple plans and chat,
  shaky on long multi-step reasoning. Not a reasoning giant.
- **`levi-4b`**: noticeably better at multi-step tool plans than the
  0.6B; slower per token on CPU; needs ~4–6 GB free RAM.
- **Rules planner (`local`)**: deterministic, offline, no model at all.
  The fallback is a feature: the agent stays useful with zero weights.

## Other selectable sources

| Source | Select with | Needs |
|---|---|---|
| OpenAI-compatible (cloud OpenAI, Ollama, vLLM) | `--provider openai` | `LEVI_OPENAI_API_KEY`, or `LEVI_OPENAI_BASE_URL=http://localhost:11434/v1` for keyless local servers |
| Anthropic | `--provider anthropic` | `LEVI_ANTHROPIC_API_KEY` |
| Rules planner | `--provider local` | nothing — always available |

These are wings, not the bird. They never become the default on their
own.

## Adding a remix

A remix is a third-party base that LEVI packages and serves. To add
one permanently:

1. Add its download spec to `MODELS` in `core/levi/agent/local_model.py`
   (URL pinned to an exact commit, authoritative SHA-256, honest
   `ram_note` and `blurb`).
2. Add a `levi-*` entry to `_FAMILY` in
   `core/levi/agent/model_family.py` with `kind: "remix"`,
   `base:` naming the upstream model honestly, and `local_key:`
   pointing at the new `MODELS` entry.
3. Document it in the family table above.

`model_family.register_remix(name, base=..., version=...,
local_key=...)` exposes the same structure at runtime for experiments.
Never register weights that do not exist — the registry seeds only
what is real.
