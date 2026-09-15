# LEVI Lab — on-device agentic AI, hands on

LEVI Lab is an interactive lab for **on-device agentic AI**: small models
running locally, driving LEVI's real tool-using agentic loop. It is an
original, clean-room implementation — the *idea* of a hands-on lab is
inspired by public lab repos, but every scenario, line of code, and
captured transcript here was written from scratch against LEVI's own
runtime.

## What "on-device agentic AI" means for LEVI

Most assistants are a chat box in front of a giant cloud model. LEVI's
design inverts that: the **agentic loop is the product**, and the model is
a wing, never a dependency. The loop (`levi.agent.loop.run_subtask`) is
plain stdlib Python:

1. take a task,
2. ask the provider what to do next (a tool call or a final answer),
3. execute the tool, feed the result back,
4. repeat until done — or until a confirmation gate stops it.

Providers plug into that loop. `local` (always available, deterministic,
rule-based) makes the loop useful with no network and no weights at all.
`levi-local` swaps in a real GGUF model (Qwen3) via llama-server when you
want actual language understanding on-device. `levi-brain` is LEVI's own
trained-from-scratch proof-of-learning model. The lab lets you *see* the
loop work, measure what models cost to run, and try a live endpoint.

## The four scenarios

Run `levi lab scenarios` to list them. Each ships with a **captured
fixture** — the real transcript of a real loop execution (provider
`local`, clean HOME), with provenance (date, provider, LEVI version).
`levi lab run <id>` plays the fixture back; `levi lab run <id> --live`
executes the loop for real and re-captures it.

| id | what it shows | captured transcript |
|---|---|---|
| `resilient-file` | multi-step file task: first tool call **fails** (missing file) → diagnose → recover | fail: 1 step, 1 failed `file_read`; recover: 2 steps, `file_write` + `file_read`, 0 failed |
| `red-green` | coding fix loop: run buggy script (**red**, real traceback) → patch → re-run (**green**) | red: 1 step, 1 failed `shell_exec`; green: 1 step, `shell_exec` ok, output `answer: 42` |
| `research-brief` | research with web tools: fetch a page over HTTP, save findings to memory | fetch: 1 step `shell_exec` ok (real page text); note: 1 step `memory_write` ok |
| `effort-ab` | reasoning-effort A/B: same question, plain vs. elaborated system prompt | both runs: 2 steps, `file_write` + `file_read`, **identical** |

The effort A/B's negative result is the point: with the deterministic
local provider, prompt effort changes nothing. Re-run it against a real
model backend (`--live` with `levi-local`) and the comparison becomes
interesting.

## CLI

```
levi lab scenarios                        # list scenarios + fixture status
levi lab run resilient-file              # play back the captured transcript
levi lab run red-green --live            # execute the loop live, re-capture
levi lab footprint --params 30B --quant int4 --ctx 32k
levi lab card                             # models LEVI actually supports
levi lab card qwen3-4b
levi lab chat --endpoint http://localhost:8080 --model qwen3-0.6b
```

## Footprint math

`levi lab footprint` estimates the RAM envelope for running a model:

```
weights  = params × bytes-per-param(quant)      fp32=4  fp16/bf16=2  int8=1  int4=0.5
kv_cache = 2 × layers × hidden_dim × ctx × bytes/elem
total    = (weights + kv_cache + headroom) × overhead
```

Sizes are decimal GB (as publishers quote them); context "k" means 1024.
When you don't pass `--layers`/`--hidden`, a *typical* architecture is
used and flagged as estimated. It is an estimate for capacity planning,
not a measurement — real runners add allocator and backend overhead.

## Wiring a real local endpoint

The lab's `chat` command talks to **any OpenAI-compatible endpoint** —
the URL comes from `--endpoint` or `LEVI_LAB_ENDPOINT`, never hardcoded.
To serve LEVI's own local model:

```
levi agent model pull              # downloads the pinned Qwen3 GGUF weights
# start llama-server against ~/.levi/models (see `levi agent model status`)
levi lab chat --endpoint http://localhost:8080 --model qwen3-0.6b
```

`levi lab chat` probes `GET /v1/models` first and tells you plainly when
the endpoint is unreachable.

## Honest limits

- **Fixtures are illustrative of real runs, not live intelligence.**
  They record what the loop did on the capture date with the `local`
  provider. They don't update, learn, or generalize.
- **The `local` provider is a deterministic planner**, not a model. It
  follows fixed intent rules (file tasks, shell commands, memory notes).
  It cannot diagnose tracebacks (the red-green patch is applied by the
  lab harness and labeled as such), and its command parser stops at the
  first `.` (the scenarios use dot-free helper names for this reason —
  documented in the code, not hidden).
- **The footprint math is an estimate.** KV-cache uses the dense upper
  bound (real GQA checkpoints use less); allocator behavior varies.
- **`tiny-gpt` is a training-pipeline proof**, not a brain: 3.3M params,
  garbled samples. Its card says so.
- **`levi lab chat` sends your text to whatever endpoint you point it
  at.** Point it at loopback for private use; a remote URL is *your*
  choice and your data leaving the machine.

## For agents

Two read-only tools are registered in the default tool registry:

- `lab_scenario` — list scenarios or play back a captured transcript.
  Playback only; it never executes the loop.
- `lab_footprint` — estimate a model's RAM envelope. Pure math.

## Files

- `core/levi/lab/scenarios.py` — registry, live runners, capture/playback
- `core/levi/lab/footprint.py` — memory-envelope math
- `core/levi/lab/models.py` — model cards for supported models
- `core/levi/lab/live.py` — endpoint probe + chat passthrough (stdlib)
- `core/levi/lab/fixtures/*.json` — captured real transcripts
- `tests/test_lab.py` — hermetic tests
