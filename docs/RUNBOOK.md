# Runbook

Operator instructions for running each piece. The products are independent —
run only what you need.

## Python core (CLI)

```bash
cd levi/core
python3 -m levi.cli.main init        # first-run onboarding (~/.levi/)
python3 -m levi.cli.main ask "..."  # one-shot
python3 -m levi.cli.main --help     # ~80 subcommands, see docs/CLI.md
```

No env vars required. Local-first: state in `~/.levi/`, models via Ollama if
present. The ControlDaemon is in-process (`levi daemon status`).

## VYVE backend (FastAPI)

Two services, run each with uvicorn from its own directory:

```bash
cd apps/vyve-messenger/backend/oauth && uvicorn server:app --port 8080
cd apps/vyve-messenger/backend/messaging && uvicorn server:app --port 8081
# (both also accept `python server.py [port]`; do NOT use reload=True in prod)
```

Dependencies: `pip install -r apps/vyve-messenger/backend/requirements.txt`.

### Required env vars

| Var | Where | Meaning |
|---|---|---|
| `OAUTH_CLIENT_SECRET` | OAuth | Client secret; server **fails closed at startup** if unset (non-demo) |
| `VYVE_DEMO_MODE` | both | `true` enables the `chauncey`/`cj` demo accounts. Default off. Demo only. |
| `VYVE_JWT_PRIVATE_KEY_PEM` | both | RSA private key PEM for RS256 token signing. Preferred over files. |
| `VYVE_KEY_DIR` | both | Key directory; default `~/.vyve/keys`. Generated keys live at `vyve-rs256.pem`. |
| `CORS_ORIGINS` | both | Comma-separated allowed origins; default `http://localhost:8080,http://localhost:8081` |
| `OAUTH_REDIRECT_URIS` | OAuth | Comma-separated registered redirect URIs; **exact-match** enforced on authorize |
| `DATABASE_URL` | planned | Not yet consumed by code (P3.3: wire SQLAlchemy→PostgreSQL via `infrastructure/database/schema.sql`) |

`VYVE_JWT_PRIVATE_KEY_PEM` takes precedence; without either var or key files
the server raises `RuntimeError` at startup (fail closed, no generated-at-boot
production keys).

### Supervision notes

- State is **in-memory dicts** — everything is lost on restart, and tables grow
  unbounded (P3.3). Do not treat this as a production store.
- No systemd units are shipped. Until then, run under a supervisor (systemd
  `Restart=always`, docker `restart: unless-stopped`, or tmux for dev).
- Health: neither server exposes a `/health` endpoint yet — probe the JWKS
  endpoint (`/oauth/jwks` on the OAuth service) from your supervisor.
- Keep the OAuth and messaging services on separate ports/processes; they share
  only the key material.

## Megazord

Dev-only; no supervision needed:

```bash
cd delivery/megazord
PYTHONPATH=. python -c "
from megazord import MegaZord
z = MegaZord(persona='alpha')
print(z.think('Levi, run a diagnostic'))
"
```

Single-process, in-memory, no persistence. Do not run it as a service.

## Web app

```bash
cd web
npm install
npm run dev        # :8080 (uses scripts/with-app-env.mjs)
```

Requires `XAI_API_KEY` (server-only) for AI features. `web/startup.sh` restarts
the dev server in sandbox environments — it must run from its own directory.

## Runtimes (apotheosis / xenomax)

Legacy monoliths; each is a single `levi.py` with CLI flags
(`--cli`, `--tui`, `--query`, ports). Run directly with `python3`; data in
`~/levi/` (apotheosis) via `LEVI_HOME`.
