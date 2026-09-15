# LEVI PWA — the chat organ

The Xeno rebirth, done right. The old "LEVI Ultimate Xeno" single-file
lineage is composted; its good ideas — an installable chat PWA, a tone
picker, media commands — are reincarnated here as a proper LEVI organ.

## Architecture

```
phone / browser (PWA shell: index.html + app.js + sw.js)
        │  HTTPS in production, plain HTTP on localhost/LAN
        ▼
core/levi/pwa/server.py   (stdlib ThreadingHTTPServer — no fastapi)
   ├─ static/             (PWA: dark void theme, chat UI, register picker)
   ├─ POST /api/chat     ──▶ levi.agent.chat.ConversationManager
   │                          (the EXISTING agentic loop — reused, not forked)
   ├─ POST /api/chat/stream (SSE liveness + final payload)
   ├─ GET  /api/registers (14 real KAI-9000 registers)
   ├─ GET  /api/models    (LEVI-first model family, live status)
   └─ POST /api/image     ──▶ levi.media.pollinations (existing pipeline)
```

Chat turns run the full agentic loop with tools on every turn. Sessions
persist as JSONL in `~/.levi/agent/sessions/` — **the PWA and
`levi agent chat` share sessions**: start on the CLI, continue on the
phone.

## Endpoints

| Method | Path | Body → Response |
|---|---|---|
| GET | `/`, `/app.js`, `/styles.css`, `/manifest.json`, `/sw.js`, `/icon.svg` | PWA shell (correct content types; `sw.js` is `no-cache`) |
| GET | `/api/health` | `{"status":"ok","service":"levi-pwa","version"}` |
| GET | `/api/registers` | 14 real registers: `id`, `name`, `tagline`, `voice` |
| GET | `/api/models` | LEVI family (`levi-tiny`, `levi-0.6b`, `levi-4b`) with live download status + resolved default |
| POST | `/api/chat` | `{session, message, register?, provider?, max_steps?, consent?}` → `{reply, provider, ok, steps, context_pct, compressed, session}` |
| POST | `/api/chat/stream` | Same body, `text/event-stream`: `status` liveness events, then `done` (or `error`) |
| POST | `/api/image` | `{prompt, width?, height?}` → `{url, path, seed, model}` |

In-chat slash commands: `/help`, `/image <prompt>`, `/register <id>`,
`/clear` (view only — server history is untouched).

## Offline behavior (honest)

The service worker caches the app shell, so the UI loads with no
server. API calls are network-only and never cached: if the LEVI server
is unreachable, the UI shows an offline banner instead of faking chat.
"Offline" for the PWA means the *client* is offline from its server;
on-device inference without the server is Android-native work
(`apps/levi-android`), not this organ's job.

## Security

Single-user local server. Default bind `127.0.0.1`. Set
`LEVI_PWA_TOKEN` to require `Authorization: Bearer` on `/api/*`
(static files stay open — they carry no data). Binding a LAN address
without the token prints a loud warning. Public exposure belongs
behind a TLS reverse proxy, never this server directly.

`consent` defaults to `false`: a gated tool is honestly denied and the
turn says the gate tripped. The PWA does not bypass HITL — a real
approval UI is enterprise Phase 2.

## Usage

```bash
levi pwa serve                      # http://127.0.0.1:8000/
levi pwa serve --host 0.0.0.0       # LAN — set LEVI_PWA_TOKEN first
levi pwa serve --register kai_9000_void --provider levi-local
```

The CLI prints the LAN URL for phone access; "Add to Home screen"
installs the PWA.

## Honest limits

- **Single-user, single-machine.** No multi-tenancy, no billing, no
  production hardening. TLS/reverse proxy still required for public
  exposure.
- **Streaming is liveness, not tokens.** The agentic loop doesn't
  stream tokens; `/api/chat/stream` emits progress heartbeats then the
  full reply.
- **Media is cloud-backed.** `/image` uses Pollinations over the
  network; it fails honestly (502) when unreachable. Local generation
  is future native work.
- **No NSFW mode, no joke personalities.** The register picker serves
  LEVI's real registers only — that was a binding constraint from the
  start.
- **Model quality = provider quality.** With no LEVI weights
  downloaded, the loop runs the deterministic rules planner; pull
  weights (`levi agent model pull`) for real inference.
