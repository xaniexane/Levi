# Security (operator note)

What Phase 1 fixed, what the posture is now, and what is still out of scope.
Covers the VYVE backend (`apps/vyve-messenger/backend/`) and the Python core
vault.

## Phase 1 fixes (shipped)

1. **JWKS no longer leaks the signing secret.** Tokens are signed with **RS256**
   (`shared/jwt_keys.py`); `/oauth/jwks` publishes only the public key. The old
   HS256 design published the symmetric secret in JWKS — **any previously
   issued HS256 token is now rejected** and clients must re-authenticate.
2. **Fail-closed secrets.** `OAUTH_CLIENT_SECRET` must be set (server refuses to
   start without it); JWT signing raises `RuntimeError` without a key. No
   silent fallbacks.
3. **Demo gating.** The `chauncey`/`cj` demo accounts exist only when
   `VYVE_DEMO_MODE=true`. Never enable in production.
4. **`redirect_uri` exact-match.** Authorization validates the URI against the
   per-client registered list (`OAUTH_REDIRECT_URIS`); the old `startswith("http")`
   check is gone.
5. **CORS is explicit.** `allow_origins` comes from `CORS_ORIGINS` (default
   localhost only) instead of `"*"` with credentials.
6. **Vault fail-closed.** `core/levi/vault/seal.py` uses Fernet (AES-128-CBC +
   HMAC) from the `cryptography` package only — the old XOR fallback was
   deleted, and instantiating without `cryptography` raises `RuntimeError`.
   Vault files are `0o600`, vault dir is `0o700` (re-enforced on open). Legacy
   XOR-sealed blobs are **undecryptable by design** — a deliberate break.

## Current posture (verified in code)

- PKCE S256 enforced; 10-minute single-use auth codes with reuse-revocation;
  refresh-token rotation; `require_exp`/`require_sub`/audience claims checked;
  access/refresh/id tokens separated by `typ`-style claims.
- WebSocket auth checks `exp` on connect.
- `python-jose` replaced with PyJWT 2.10.x (CVE-2024-23342 in jose);
  `passlib` dropped in favor of direct `bcrypt`.

## Explicitly out of scope / known gaps

- **Rate limiting** is in-memory only — add a shared limiter (Redis/token bucket)
  before any public exposure.
- **No WAF**, no request-size anomaly alerting, no centralized logging of auth
  events.
- **In-memory backend storage** — restart wipes users, codes, tokens
  (planned DB work in P3.3). An attacker-caused restart is also a data-wipe.
- WebSocket sessions have no message-rate cap beyond the global poll cadence.
- The web app (`web/`) keeps secrets server-side (`XAI_API_KEY` never in
  client bundles), but has not had a security review; treat it as untrusted
  input surface toward any future core bridge.
- Megazord has no auth story at all — it is dev scaffolding.
