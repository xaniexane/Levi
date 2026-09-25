# Cybrus as platform Security & Identity — plan

**Standing law:** Cybrus is the Security & Identity layer, and the ONLY
component allowed to handle money. Every other agent and platform
service goes through Cybrus for payments, credentials, permissions,
external routing, and execution authorization. "I'm Cybrus." — Chauncey.

This document is a PLAN, not an implementation. The standalone customer
product (`README_CYBRUS_STANDALONE.md`,
`docs/CYBRUS_STANDALONE_PRODUCTION.md`) is the same Cybrus wearing a
different hat: what customers run on their own machines, the platform
runs as shared infrastructure.

## 1. The shape of it

Three services, one sealed box:

- **Vault service** — the encrypted credential store for the whole
  platform. Agent seats never hold raw third-party secrets; they hold
  references, and Cybrus releases the secret only into an authorized
  execution context.
- **Broker service** — third-party account provisioning, API-key
  storage/retrieval, OAuth token lifecycle — the automated credential
  creation and fetching any agent needs, always approval-gated and
  quota-checked.
- **OAuth service** — the authorization-code + PKCE state machine:
  initiation, callback, token storage, refresh, abandonment, status —
  with the one-in-flight-flow-per-user rule so flows can never collide.

## 2. How the eleven consume it

No agent touches a secret, a payment rail, or an external site directly.
The pattern:

1. Agent requests an action through Cybrus with its identity and the
   target scope.
2. Cybrus checks tier quota (`rate_limits.check`), approval gates, and
   permission policy — every check audit-logged.
3. Cybrus either performs the brokered action itself (provision, fetch,
   token refresh) or issues a bounded, single-purpose authorization the
   agent spends immediately.
4. Money flows only through Cybrus's money handlers; agents describe
   intent, Cybrus executes.

Agent identities get tiers like customers do — platform-internal seats
run at PLATFORM tier (uncapped, fully audited); Chauncey's own identity
is quota-exempt but fully logged. Approval gates apply to everyone,
including admins: quota exemption never skips human approval.

## 3. Money law

Cybrus remains the only money-handler. Platform services that need to
charge, pay, refund, or hold funds describe the intent; Cybrus executes
and receipts. This keeps every dollar in one auditable place and keeps
the anti-spam ladder (rate limits) between automation and the outside
world at all times.

## 4. What exists today (building blocks)

- Vault engine: `core/levi/cybrus/vault.py` (Fernet seal, labeled fallback).
- Broker engine: `core/levi/cybrus/broker.py` (provision, keys, OAuth
  state machine, approvals, audit log).
- Rate limits: `core/levi/cybrus/rate_limits.py` (tier ladder, hour/day
  windows, burst cooldown, in-flight OAuth reservation, audit logging,
  founder exemption).
- Product definition + quickstart: `core/levi/cybrus/product.py`,
  `core/levi/cybrus/quickstart.py`.
- The broker already enforces quotas internally, so platform consumers
  inherit the ladder without extra wiring.

## 5. What is NOT this plan

- No service extraction yet: no HTTP/gRPC boundary, no multi-tenant
  isolation design, no billing system. The tier seam
  (`rate_limits.set_tier`) is documented and stubbed; real billing owns
  it when it exists.
- No change to the standalone product's local-only nature: the customer
  edition stays on the customer's machine. The platform edition is a
  separate deployment of the same engines.
- No release, no publishing, no pricing — all gated on Chauncey.
