# LEVI void-mind web UI

The real void UI — no sidebar, no dashboard; the void IS the interface.

- **`index.html`** — the whole app in one file (inline CSS + JS). Zero build
  step, zero external requests. Opens from disk; talks to the local daemon
  at the same origin.
- **`mockups/`** — phase-1 design proof: the approved mockup
  (`void-mind-v1.html`) and its proof gate, plus the v2 proof gate for the
  real build.

## Run it

From the repo root:

```sh
python3 -m levi serve --dir web --port 8742
# or: levi serve --dir web --port 8742
```

Then open http://127.0.0.1:8742/ — the void UI loads; chat turns run
through the local LEVI orchestrator via `/api/chat`. If the daemon is
down the UI says so honestly and refuses to fake chat.

## Backend

`core/levi/serve/void_api.py` — stdlib-only API mounted by
`core/levi/serve/server.py` under `/api/*`:

| route | what it really does |
|---|---|
| `GET /api/health` | daemon heartbeat (offline detection) |
| `GET /api/registers` | 14 registers, live from `levi.persona.levi.all_variants()` |
| `GET /api/growth` | growth stage, live from `levi.growth.cycle.status()` |
| `GET /api/journal` | recent growth-journal entries |
| `GET /api/model` | honest model status |
| `POST /api/chat` | one real orchestrator turn + measured tok/s + hash-chain tick |
| `POST /api/note` | pin a note to the session log |
| `POST /api/fork` | fork the session hash chain (branch) |
| `GET /api/session/<id>` | session records + chain head |

The previous React app was relocated (not deleted) to
`stored/2026-09-24-react-app/` with a provenance note, per Chauncey's
"Replace with real" ruling.
