# LEVI — Local-First Synthetic Intelligence

> **Proprietary** — Chauncey J. Logan / Cybrus AI Systems. See [LICENSE.txt](LICENSE.txt).

LEVI is a local-first AI agent: a conversational runtime that plans, uses
tools, and gets things done on your own machine. No account, no cloud
required — the default engine runs fully offline.

This repository is the public edition of LEVI: the agent runtime itself.
Twenty-five modules, stdlib only, zero dependencies.

## Quickstart

Requires Python 3.10+.

```bash
pip install .
levi ask "summarize this directory"
levi chat
```

Or without installing:

```bash
PYTHONPATH=core python -m levi ask "what can you do?"
PYTHONPATH=core python -m levi chat
```

`levi ask "..."` runs one task through the agent's tool loop and prints the
answer. `levi chat` opens an interactive session that remembers the
conversation (stored under `~/.levi/`).

## How it works

Three packages, one idea — every model sits behind the same contract, so
swapping the brain is a config change, never a code change:

- **`levi.agent`** — the runtime. `loop` runs the step-level tool loop
  (`run_subtask`); `chat` adds persistent sessions with context management
  (`ConversationManager`, `run_chat_repl`); `providers` selects the chat
  backend; `tools` is the tool registry (file operations, shell, notes,
  and more — every tool degrades gracefully when its optional backend is
  absent); `soul` lets the owner drop a `~/.levi/soul.md` file that becomes
  a persistent persona layer on every prompt.
- **`levi.operator`** — the universal operator contract. Providers,
  council minds, and nano-bit operators are all interchangeable seats
  behind one interface, with a registry, health reporting, and twin-turn
  judging (two operators, one verifier).
- **`levi.governor`** — budgets, cooldowns, and spike detection that keep
  the agent's resource use bounded.

## Providers

Out of the box LEVI runs on its built-in local engine — deterministic,
offline, private. Point it at a real model when you want full capability:

```bash
LEVI_PROVIDER=openai levi chat      # OpenAI-compatible endpoint
LEVI_PROVIDER=anthropic levi chat   # Anthropic endpoint
```

Provider choice is read from `--provider`, then the `LEVI_PROVIDER`
environment variable, then falls back to local. API keys follow each
provider's standard environment variables.

## Honest limits

- The built-in local engine is rules-based: fast, private, and offline,
  but not a large language model. For open-ended reasoning, connect a
  model provider (above).
- Tools that need subsystems outside this edition (skills, automation,
  growth) report that cleanly instead of failing silently.

## Layout

```
core/levi/agent/      chat, loop, providers, tools, soul, cli (+ model backends)
core/levi/operator/   contract, adapters, registry, twins
core/levi/governor/   budgets, meter, cooldown, priority, spikes, diagnose
tests/                suite for exactly what ships here
```

## License

Proprietary — all rights reserved. See [LICENSE.txt](LICENSE.txt).
