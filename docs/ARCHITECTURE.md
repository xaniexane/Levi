# Architecture

Honest description of what this repo *is* today (September 2026), not what the
marketing copy claims. It contains **separate products** that share a name and
a repository; they do not currently share a runtime.

## Map

```
levi/
├── core/levi/            Python core ("the kernel") — 32 subpackages
├── delivery/
│   ├── megazord/         persona scaffolding + flow stubs (separate import surface)
│   └── runtimes/
│       ├── apotheosis/   single-file monolith: levi.py (vApotheosis-Apex-1.2)
│       └── xenomax/      single-file monolith: levi.py (v32.0.0 Hyperdrive XenoMax)
├── web/                  TanStack Start app (TypeScript) — talks to xAI, NOT to the core
└── apps/vyve-messenger/  LEVI's messenger — Android app + FastAPI backend (OAuth + messaging), an organ of the organism
```

## The Python core (`core/levi/`)

Package version `0.9.5` (single-sourced from `core/levi/__init__.py::__version__`). The orchestration loop lives in
`levi/orchestration/loop.py` and runs a deterministic pipeline per turn:

```
UNDERSTAND → COMPANION/EI → PERSONA → SPECIALISTS → SKILLS/POLICY → SYNTHESIZE
```

"No unbound agent spawning" — the Phase 1 loop does not launch autonomous
agents. Key subpackages:

| Package | Role |
|---|---|
| `orchestration/` | turn loop, intent parsing |
| `persona/` | persona lattice, nervous system, wit, monotropism |
| `agent/` | specialist registry |
| `skill/` | skill registry |
| `policy/` | policy engine / risk gates |
| `memory/` | memory store |
| `model/` | model router (Ollama-first, local models) |
| `daemon/` | control daemon, automation registry |
| `vault/` | local secret sealing (`VaultSeal`) |
| `ei/` | companion/EI cores |
| `graph/`, `brain/`, `builder/`, `factory/`, `cloud/`, `lwp/`, `demand/`, `income/`, `media/`, `meta/`, `organs/`, `premium/`, `project/`, `pulse/`, `runtime/`, `integrations/`, `marketplace/`, `observability/`, `identity/` | domain subsystems |

Entry point: `python -m levi.cli.main` (see `docs/CLI.md`). Data stays local
(`~/.levi/`).

## The megazord (`delivery/megazord/`)

Separate package, separate import surface (`from megazord import MegaZord`).
Today it is **persona scaffolding + flow stubs**: five persona presets (CYBRUS,
ECHO, ALPHA, OMEGA, KAI — there is no LEVI persona), a think/decide/act flow
loop (`megazord_core.py`, `flows/`), and thin bridges (`bridges/`). Single
process, in-memory, no persistence, no transport, no tests. See its README for
the full honesty disclaimer. Per P3.6 it stays scoped as scaffolding.

## The runtimes (`delivery/runtimes/`)

Two single-file monoliths, each self-contained:

- **apotheosis** (`levi.py`, version Apotheosis-Apex-1.2): Soul, personalities,
  glyph UI, memory, music, Termux device automation, model auto-detect
  (Ollama/GGUF), Echoverse, Mandella, REIM, Pollinations image gen, HITL
  imagination training. HTTP server (`BaseHTTPRequestHandler`) + CLI flags.
- **xenomax** (`levi.py`, version 32.0.0): Web UI (:8000), CLI, TUI, one-shot
  query, tokens/tiers, Park commands.

They are legacy delivery artifacts, **not** built on the `core/levi/` package.

## The web UI (`web/`)

A TanStack Start (React 19) app: dev server `npm run dev` on `:8080`, deployed
to Vercel. Its AI calls go to **xAI's API** via `XAI_API_KEY`
(`src/lib/levi/ai.ts`) — it does **not** call the Python core. This is the
app that was built in the Grok sandbox (`web/AGENTS.md` is that scaffold's
house rules, not this repo's). Dead WebRTC `/api/rtc` signaling client code was
removed in Phase 3 — the endpoint never existed.

## VYVE (`apps/vyve-messenger/`) — LEVI's messenger

It's all LEVI: Vyve is not a separate product but LEVI's messaging organ —
an Android app plus a FastAPI **backend** with two services —
`backend/oauth/` (OAuth2 + PKCE server, RS256 JWTs) and
`backend/messaging/` (messaging + WebSocket). See `docs/RUNBOOK.md` and
`docs/SECURITY.md` for operations and the Phase 1 security hardening.

## Deferred decisions

These are deliberately **not built** yet; documenting them as products means
accepting this state.

- **Web↔core bridge (P3.5):** no bridge exists. Options are (a) document the
  separation as final, or (b) build a Python service API the web app can call.
  Deciding is owner work; this doc does not pre-decide.
- **Megazord's future (P3.6):** it is persona scaffolding today. Becoming a real
  engine would require L.W.P. cascade execution, persistence, and the claimed
  multi-persona composition — a scoped project, not incremental polish.
