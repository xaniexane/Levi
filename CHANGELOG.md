# Changelog

History starts here. Earlier work was merged as a single squash commit
(dd591a9) and is not recoverable as a changelog — this file covers the
Phase 1–3 modernization and everything after.

## Unreleased

### Security (Phase 1)

- OAuth now signs tokens with **RS256** (`shared/jwt_keys.py`); `/oauth/jwks`
  publishes only the public key. The JWKS-symmetric-secret leak is closed.
- Server **fails closed** without `OAUTH_CLIENT_SECRET` or a JWT signing key.
- Demo accounts (`chauncey`/`cj`) gated behind `VYVE_DEMO_MODE` (default off).
- `redirect_uri` validated by **exact match** against registered URIs
  (`OAUTH_REDIRECT_URIS`); the old `startswith("http")` check is gone.
- CORS moved to explicit `CORS_ORIGINS` (localhost default) with credentials.
- Vault sealing is Fernet-only — the **XOR fallback was removed**; without the
  `cryptography` package `VaultSeal` raises `RuntimeError`. Vault files are
  `0o600`, vault dir `0o700`.
- WebSocket auth checks `exp`; `python-jose` → PyJWT 2.10.x; `passlib` →
  direct `bcrypt`.

### Deliberate breaks

- **Legacy XOR-sealed vault blobs are undecryptable.** Fail-closed was chosen
  over backwards compatibility; there is no migration path.
- **HS256 tokens are rejected.** All clients must re-authenticate under RS256.

### Modernization (Phase 2)

- VYVE backend dependencies upgraded: `fastapi` → 0.141.1, `uvicorn` →
  ~0.49.0, `pydantic` → 2.12.5, `cryptography` → 49.0.0, `bcrypt` → 5.0.0;
  unused pins (sqlalchemy, alembic, psycopg2, aiosqlite, httpx, itsdangerous,
  email-validator, python-dotenv) dropped or slated for P3.7 wiring.
- Android: Gradle wrapper added, `compileSdk`/`targetSdk` → 36, Kotlin →
  2.4.20, SQLCipher → 4.9.0, OkHttp → 5.4.0, Retrofit → 3.0.0, Flipper removed.

### Docs and hygiene (Phase 3)

- New `docs/ARCHITECTURE.md`: documents the Python core, megazord, runtimes,
  web UI, and VYVE as **separate products**; web↔core bridge and megazord's
  future are recorded as deferred decisions.
- New `docs/RUNBOOK.md`, `docs/SECURITY.md`; new `docs/CLI.md` generated from
  the actual CLI (81 subcommands); new root `CONTRIBUTING.md`.
- Megazord README rewritten honestly: persona scaffolding + flow stubs, alpha
  status, no fictional protocols. `DEFAULT_REGISTRY` added to the personas
  export surface; megazord imports and runs in-process.
- Web: removed dead WebRTC `/api/rtc` client code; `web/startup.sh` no longer
  `cd`s to a nonexistent `/workspace`.
