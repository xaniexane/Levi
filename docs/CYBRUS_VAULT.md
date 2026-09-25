# Cybrus Vault — the OAuth vault & platform API router

> "Like Bitwarden or Google Passwords — but better." Better means:
> **local-first, no cloud, no account, no sync server, no telemetry.**
> Your secrets never leave this machine. The vault is the platform's
> vault, not a consumer password-manager clone: no browser extension,
> no mobile autofill — those are out of scope by design.

## The vault (`core/levi/cybrus/vault.py`)

Two layers, one crypto backend:

- **Layer 1 — `CredentialVault`** (pre-existing): `(service, username) → secret`
  encrypted at rest.
- **Layer 2 (new)** — built additively on top, `CredentialVault` untouched:
  - `generate_password(length=24)` — CSPRNG passwords from an unambiguous
    alphabet (no `l`, `I`, `O`, `0`, `1`). Shown once, never logged.
  - `IdentityVault(passphrase, identity)` — per-identity namespaces:
    entries live under `cybrus.id.<identity>.<service>`, so identity A can
    never address identity B's entries. Scoping is by construction.
  - `OAuthVault(passphrase)` — OAuth token sets with provider, scopes,
    expiry, owning identity; `store_token` / `get_token` / `record_refresh`
    / `revoke` / `list_tokens`. Refresh metadata (`refresh_count`,
    `last_refreshed_at`) is tracked on every refresh.
  - `AutoLockVault(idle_seconds=900)` — drops the in-memory vault (and its
    derived key) after inactivity; raises `VaultLockedError` until unlocked
    again. The passphrase is never retained.

### Crypto posture

- Preferred: `cryptography`'s Fernet (AES-128-CBC + HMAC-SHA256, AEAD).
- Fallback (only when `cryptography` is absent): clearly-labeled stdlib
  construction — PBKDF2-HMAC-SHA256 (600k iterations), HMAC-SHA256
  counter-mode stream cipher, verify-then-decrypt. Documented in `vault.py`
  as fallback-grade, **not AES**. The instance reports its backend via
  `.backend` — check it, don't assume it.
- Wrong passphrase / tampered blob → `VaultError`, fail closed.
- Files: owner-only (`0o600`), vault dir `0o700`, atomic writes.

### Founder containment (binding law)

Founder-tier-owned entries are flagged `founder_owned` in vault metadata —
and the vault exposes **no share, copy, or export path for any entry**.
Founder-only powers never leave Cybrus because there is no API that could
move them.

### Audit

Every store / access / refresh / revoke writes an audit record with
**metadata only** — provider, identity, scopes, timestamps. Token and
secret values are never written to the audit log (tests assert this).

### Honest limits

- The OAuth vault records token metadata; it performs **no network calls**.
  The actual provider refresh HTTP exchange is the caller's job;
  `record_refresh` stores the fresh tokens the caller obtained elsewhere.
- Auto-lock drops *our* handle on the key; CPython may keep the bytes in
  freed memory until reused — best-effort hygiene, not a certified wipe.
- No browser extension, no mobile autofill, no cloud sync — this is the
  platform vault. Those would be separate products, not this module.

## The platform API router (`core/levi/cybrus/router.py`)

Doctrine (binding): **the platform should not need outside providers.**

- **Internal routes are first-class** — LEVI's own organs (`levi.cybrus`,
  `levi.strategy`, `levi.jobs`, `levi.monetize`, `levi.brain`, …) are always
  resolvable and always win.
- **External providers are special-request additions only** — never by
  default, never auto-discovered. `add_external(provider, scope,
  approved_by, reason)` records the approval provenance; every external
  resolution is flagged `crosses_boundary: True` and audit-logged.
- `resolve(target)` refuses unregistered external destinations with
  `RouteRefused` — including the exact command to register one deliberately.
- Relationship to `gateway.route_external`: the router is the route/address
  table (control plane); the gateway mints short-lived routing grants.
  Refusals happen in the router before any grant machinery is consulted.

## CLI

```bash
levi cybrus vault generate --length 24
levi cybrus vault oauth-store github --identity alice --scope repo --expires-in 3600
levi cybrus vault oauth-get github --identity alice
levi cybrus vault oauth-list [--identity alice]
levi cybrus vault oauth-refresh github --identity alice --expires-in 7200
levi cybrus vault oauth-revoke github --identity alice

levi cybrus route list
levi cybrus route add-external github --scope repo.read --reason "..." --actor alice
levi cybrus route remove-external github --actor alice
```

Secrets and tokens are **never** taken via argv — always `getpass` prompts.
`route add-external` / `remove-external` require an authenticated identity
(password prompted): adding an outside provider is a deliberate human act.
