# Creator Content Service

Plain words: how creators, subscribers, and payouts work in the
Phase-1 Cybrus Build 4 creator content service (OnlyFans-style
subscription content).

## What it is

A creator makes a profile, sets subscription tiers, and publishes content
items gated by tier (or by per-subscriber grant, pay-per-view style).
Subscribers subscribe to a tier, get a short-lived access token, and can
view the content their tier unlocks. Creators earn the subscriber
revenue minus the platform cut, recorded as payouts.

Two modules:

- `core/levi/creator/subscriptions.py` — creator profiles, tiers,
  subscribe/unsubscribe, access tokens, payouts.
- `core/levi/creator/content.py` — publishing, gating (tier / grant /
  public), listing, revoking.

Both are track-aware (`si` / `ai`): storage goes through the existing
per-track creator stores (`~/.levi/creator/si/` sealed, `~/.levi/creator/ai/`
plain local). The tracks never merge — separate directories, separate
code paths, no cross-track queries. The SI track is locked behind the
Plaiground adult gate and fails closed when the gate is off; the AI
track enforces the SFW rules instead.

## How money flows — Cybrus only

**All money movement goes through the Cybrus MoneyGateway
(`core/levi/cybrus/money.py`). No side ledgers, no parallel money path.
That is the binding law, and this service has no money code of its own.**

1. **Subscribe.** The subscriber's charge is planned, previewed, and
   authorized through the gateway (the keeper's authorization is bound to
   the exact plan id; non-keeper authorization is refused). With no
   registered money rail — the standing state — execution refuses with
   `NoRailConfigured` and the subscription is recorded as
   `pending_payment` with `paper=True`. The receipt says plainly that no
   money moved.
2. **Payouts.** A creator's payout plans a gateway `payout` operation for
   their unsettled balance (subscriber revenue minus the 12% platform
   cut, computed per pricing.py in the open), binds the keeper's
   authorization, and executes. With no rail, it refuses and the payout
   is recorded as `pending_payout` with the plan id, the gateway's full
   six-gate audit trail, and the receipt. Each subscription settles
   exactly once — settled subscription ids ride on the payout record.
3. **The ledger is the creator's.** Payout records live in the creator's
   own track store (`creator_payouts`), portable and readable: amount,
   platform fee, plan id, status, receipt. Audit is metadata-only —
   operation, amount, identity, decision, plan id. No secrets, no
   credentials, ever.

**Paper-only status (stated plainly):** there are no live money rails.
Every charge records as `pending_payment`, every payout as
`pending_payout`, every access token as paper. Nothing here represents
real payment. When Chauncey deliberately registers a rail, the same
code path starts moving real money through the same gates — no rewrite
needed.

## How access works — verified server-side, never trusted from the client

1. A subscriber with a valid subscription (inside its paid period, not
   lapsed) asks for an access token. The module issues a short-lived
   (15-minute) bearer token through the **Cybrus token engine**
   (`levi.cybrus.tokens.TokenEngine`) — scoped to creator + tier — and
   keeps a server-side binding (token id → subscriber) in the creator
   store. The plaintext token is returned exactly once.
2. **Every access** runs `verify_access`, which does four things in
   order: (a) validates the token *through Cybrus* — unknown, revoked,
   or expired tokens fail; (b) checks the server-side binding; (c)
   re-checks the subscription's current validity — a live token on a
   lapsed subscription grants nothing; (d) evaluates the content's gate.
   Tampered tokens fail at step (a). A revoked content item denies
   everyone, tokens included.
3. Tier gating: tiers have ranks; a subscription at rank N unlocks all
   content gated at rank ≤ N. Per-item grants (PPV) unlock one item for
   named subscribers. Public items unlock for everyone. Creators always
   see their own content. List views are metadata-only for viewers who
   are not entitled — payload references never leak into listings.

## Safety gates

The `safety.py` track rules apply to this service and cannot be
bypassed:

- **SI track:** the Plaiground adult gate must be open (`require_adult`)
  and all text is bounds-checked — on publishing, subscribing, token
  issuance, and payouts. Gate off = everything refuses.
- **AI track:** the SFW rules (`check_sfw`) gate all published text —
  violating content fails the publish, it does not get stored.
- **Payout references are opaque labels** (e.g. `bank-ref-8472`), never
  credentials. Secret-looking values are rejected at write time, and the
  reference never enters audit logs.

Content payloads given at publish time are stored through the creator
store patterns — sealed with the Veil-lineage envelope on the SI track,
plain local JSONL on the AI track. The store is not a secret store;
never publish secrets as content.

## Choke-point wiring (Cybrus router)

The creator service is the first live consumer of the Cybrus router
choke point (Build 1, `core/levi/cybrus/enforce.py`): every
subscription-token verification and every payout recording crosses the
choke point — authenticated, rate-limited, policy-checked, audited
(metadata only).

- `verify_access` carries `@cybrus_guarded(service="creator",
  callee="levi.cybrus")`: pass `cybrus_credential=` (a Cybrus `api` token
  with the `service.call` scope, or a vault API key). A refused call
  means the token-verification body never runs — fail closed at the
  choke point, then fail closed again inside.
- `record_payout` routes explicitly through `levi.creator.router.route`
  and attaches the returned routing ticket (`cybrus_ticket`) to the
  payout record. The money still moves only through the MoneyGateway —
  the choke point adds the routing/audit envelope around it.
- The call crosses INTO the Cybrus security core, so policy evaluates as
  `("creator", "service.levi.cybrus", <action>)`. The needed allow rules
  live as a clearly-marked seed-policy addition in
  `core/levi/creator/router.py` and are installed (additively,
  idempotently — never edited or removed) by
  `levi.creator.router.ensure_creator_routing()`.
- Deployment needs two deliberate operator steps: run
  `ensure_creator_routing()`, and give the `creator` caller a
  rate-limit tier of at least `starter` (free-tier callers cannot cross
  the choke point at all).
- The conjunction of the creator laws (L1–L5) and the choke-point laws
  (L1–L12) is asserted in
  `tests/test_creator_router_integration.py` — invariant tests, honestly
  named (nothing here is formally proven, only machine-checked).

## Honest limits

- No rail, no money movement: subscriptions and payouts are paper
  records until a rail is registered by Chauncey, deliberately.
- Access tokens are bearer credentials for this local service only —
  15-minute TTL, SHA-256 hashes stored, plaintext never recoverable.
- Unsubscribing stops renewal but keeps access until the paid period
  ends; after the period, access stops even for live tokens.
- This build does not include games or dating — those surfaces were not
  touched.
