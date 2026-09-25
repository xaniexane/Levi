# Cybrus — standalone customer product

Cybrus is the Security & Identity layer of the LEVI dynasty — a standalone,
customer-facing product like DemandPulse, not an internal-only module. It
seals credentials, mints passwords, and brokers third-party access:
account creation, external API keys, and OAuth tokens through platform
OAuth layers — an automated vault that never forgets a secret and never
tells one.

**Status:** local-only build. Not published. No release authorization has
been given. Pricing is UNDECIDED — provisional tier labels below are
Chauncey's to set.

## What it does

- **Vault** — encrypted local store for passwords, tokens, and keys.
  Master password from explicit input, `CYBRUS_MASTER_PASSWORD`, or
  `getpass`; never from argv, never logged.
- **Password generation** — cryptographically strong passwords, on demand.
- **Broker** — third-party account provisioning (approval-gated), external
  API-key storage/retrieval, and an OAuth2 authorization-code + PKCE state
  machine: start, callback, token storage, refresh, abandonment, status.
- **Rate limits (anti-spam)** — tier-based quotas on every automated
  broker action, burst cooldowns, one in-flight OAuth flow per user, and
  audit logging of every allow and deny.

## Quickstart

```bash
cd ~/workspace/levi/core
python -m cybrus quickstart        # CYBRUS_MASTER_PASSWORD optional
python -m cybrus status            # vault health
python -m cybrus limits            # rate-limit policy + your tier usage
python -m cybrus broker --help     # broker commands
```

The quickstart initializes and unlocks the vault, generates a first
password, stores a credential, verifies the round-trip, and hands back a
receipt. `CYBRUS_HOME` points it at a custom data home.

Or as a Python API:

```python
from levi.cybrus import product, quickstart
sheet = product.customer_sheet()        # what it is, features, honest limits
receipt = quickstart.run(master_password="...")  # full lifecycle, returns receipt
```

## Security model

- **Local-only.** All state lives on the machine, under `~/.levi/cybrus/`
  (or `CYBRUS_HOME`). Nothing phones home.
- **Fernet seal.** AES-128-CBC with HMAC via the `cryptography` package.
  Where `cryptography` cannot be installed, a labeled `stdlib-fallback`
  backend keeps the vault usable and is *honest about being weaker* —
  check `python -m cybrus status` to see which backend sealed your vault.
- **Approvals before automation.** Account creation stays individually
  human-approved even when quota allows it. Quota-exempt admins still face
  approval gates.
- **No live web driving.** The broker prepares, stores, and brokers —
  the browser/operator layer performs the actual clicks on external sites.
  The broker never impersonates a human.

## Rate limits and anti-spam policy

Every automated retrieval passes through the tier ladder:

| Tier | Price (PROVISIONAL) | Automated retrievals/day | Account creations/day |
|------|--------------------|-------------------------|----------------------|
| FREE | $0 | 0 — vault + generation only | 0 |
| STARTER | $6/mo provisional | 20 | 5 |
| PRO | $18/mo provisional | 200 | 50 |
| PLATFORM | custom | uncapped | uncapped |

Plus per-hour ceilings (OAuth initiation is tighter than OAuth refresh),
a burst rule (>10 retrievals in 5 minutes → 15-minute cooldown), and one
in-flight OAuth flow per user at a time. Every allow and deny is audit
logged. Chauncey (founder) is exempt from quotas but every attempt is
still logged. See `python -m cybrus limits` for the live table.

## Honest limits

- The OAuth layer runs the protocol state machine — it does not complete
  external logins by itself; the operator does.
- The vault is as strong as its master password. Forget it and the data
  stays sealed; there is no backdoor.
- `stdlib-fallback` backends are labeled as such — do not treat them as
  Fernet-grade.
- Tier assignment is currently a local stub with a documented billing
  entitlement seam (`rate_limits.set_tier`) — real billing decides the
  real source of truth.
- Nothing leaves the machine. That is the whole point.
