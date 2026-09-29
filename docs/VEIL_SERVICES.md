# VEIL_SERVICES — Escort Directory & Creator Platform Inside Veil

**Status:** implemented — `core/levi/cybrus/veil_services.py`
(`VeilEscorts`, `VeilCreators`), smoke-tested end to end 2026-09-27.

## The idea in one line

Two adult services that live **inside Veil as chat-native experiences** —
no website. Discovery, negotiation, booking, subscribing, and delivery all
happen as Veil conversations under Cybrus law.

## 1. VeilEscorts — directory + booking

**Directory.** Providers publish profiles: display name, services,
rates (integer minor units — no float money), availability, boundaries,
area. Stored owner-only (0600), gate-checked, bounds-checked. The
directory is local-first: providers the keeper knows, each one a Veil
contact.

**Booking flow (all inside a Veil conversation):**

```
request_booking → requested → respond_booking → approved/denied
     → confirm_booking → confirmed → complete_booking → completed
                                    ↘ cancel → cancelled (audited)
```

- `request_booking()` sends the request as a **sealed envelope** inside
  the provider conversation (VS4) and checks the provider's stated
  boundaries (VS6).
- `respond_booking()` is the provider's approve/deny. Deny is terminal.
- `confirm_booking()` raises the Cybrus **approval-ledger entry** and
  builds the `MoneyPlan` intent (VS3). Money executes only through
  `MoneyGateway` with the keeper's authorization — with no rail
  registered the gateway fails closed and the booking waits in
  `approved` with the intent recorded. Money never moves on a promise.
- Every transition is an audited state change; bookings are never
  silently dropped (VS8). Audit carries ids/amounts only (VS5).

**QR discovery.** `provider_qr()` issues `cybrus://provider/<ticket>`
(HMAC-signed, single-use, expiring) so a provider's profile can be
shared client-to-client.

## 2. VeilCreators — OnlyFans-shaped, chat-first

**Creators** publish profiles with content tiers (`free`, `bronze`,
`silver`, `gold` — prices in minor units/month). **Subscribers** discover
via the directory or QR (`cybrus://creator/<ticket>`), then
`subscribe()` through Veil:

- `free` tier activates immediately.
- Paid tiers build a Cybrus `MoneyPlan` + approval-ledger entry (VS3);
  status `pending_payment` until the keeper authorizes and the gateway
  executes — failing closed with no rail.

**Content drops — per-post paywall** (`publish_drop` → `view_drop` /
`deliver_drop` → `unlock_drop` → `confirm_unlock`):

Every drop carries **per-post visibility**, independent of tier:

- `"free"` — teaser / free post. Anyone can view; delivered whole.
- `"locked"` — paywalled. Unlocks after payment through Cybrus money
  handlers: `unlock_drop()` builds a Cybrus `MoneyPlan` + approval-ledger
  entry (VS3); `confirm_unlock()` flips it to `unlocked` only when the
  backing approval is keeper-approved (fails closed otherwise).

A creator runs **free teasers alongside paid content on the same tier**:
free photo/video drops (`visibility="free"`, price forced to 0) sit next
to locked drops (`visibility="locked"`, price defaults to the tier price,
overridable per post).

**Media**: drops carry `media_type` (`text` | `photo` | `video`) and raw
media bytes stored owner-only (0600). `view_drop()` returns the full
content — body + media bytes — only when the drop is free, the viewer
unlocked this post, or the viewer holds an active paid subscription
covering the tier. Locked-and-unpaid views return the **teaser + price +
unlock hint only** — media and body never leak (VS5). `deliver_drop()`
sends full content or teaser accordingly, as a sealed Veil envelope
(VS4); media embeds directly up to 5MB, larger media ships as a sealed
manifest with hash (transfer is a next step).

**Unsubscribe** is an explicit audited transition (VS8).

## Laws

| Law | Statement |
|-----|-----------|
| VS1 GATE-FIRST | Every public entry calls `require_adult()` first. |
| VS2 BOUNDS | All user text passes `check_bounds()`. |
| VS3 MONEY-THROUGH-CYBRUS | Every payment is a Cybrus MoneyPlan: approval → authorize → execute. |
| VS4 SEALED-DELIVERY | Bookings, drops, negotiation travel as sealed Veil envelopes. |
| VS5 AUDIT-METADATA-ONLY | Audit carries ids/tiers/amounts/counts, never plaintext. |
| VS6 PROVIDER-BOUNDARIES | Boundaries checked on every request; violations fail closed. |
| VS7 QR-SIGNED | Discovery tickets HMAC-signed, single-use, expiring. |
| VS8 NO-CANCELLATION | End states only via explicit audited transitions. |

## Money: the honest state

Cybrus is the sole money handler (platform plan §3). Both services
*describe* payment intents as `MoneyPlan`s and raise approval-ledger
entries; `MoneyGateway.execute()` performs the movement **only** when a
rail is registered and the keeper's authorization (backed by an approved,
unconsumed approval receipt) is presented. Today no rails are registered,
so paid flows correctly park in `pending_payment` / `approved` with the
intent recorded and audited. This is the designed behavior, not a bug —
rails are a Chauncey-gated step (platform plan §5).

## What's local-first vs what's next

- **v1 (this):** local directory, local booking state machine, sealed
  chat transport, QR-shared profiles, money intents through Cybrus.
- **Next (needs Chauncey's word):** money rails registration, relay-based
  cross-device directory sync, provider-side companion app surface.

## 3. Creator NFTs — drops minted as tokens

Creators mint photo/video drops as NFTs; buyers purchase through Cybrus
money handlers; discovery rides the QR ticket flow.

- **Mint:** `VeilCreators.mint_drop_as_nft(drop_id)` certifies the drop's
  exact media bytes. Token id = `sha256("creator-nft:v1":creator:content)`
  as uint256 — one content hash mints exactly once per creator
  (counterfeits impossible by construction), domain-separated from every
  genesis id. Text-only drops can't mint. Approval-gated: `pending_mint`
  until the keeper approves, then `confirm_nft_mint`.
- **Economics (genesis law, reused not rebuilt):** deterministic ids,
  50/30/20 primary split with the creator in the keeper's seat
  (50% creator / 30% pool / 20% buyback treasury), 7.5% (750 bps)
  EIP-2981 royalties to the creator on secondary sales. Token standard
  ERC-721, chain Base. The split is Chauncey's to reset.
- **Buy:** `buy_nft` → MoneyPlan + approval → `confirm_nft_purchase`
  transfers ownership on the hash-chained creator NFT ledger and records
  the revenue split + royalty basis. Fails closed without approval.
- **QR:** `nft_qr(token_id)` issues a signed single-use expiring
  `cybrus://creator-nft/` ticket carrying token + price; the buyer scans,
  `verify_nft_qr` checks signature/expiry/availability, then buys through
  the normal flow.
- **Ledger:** `core/levi/cybrus/veil_nft.py` (`CreatorNftLedger`) —
  hash-chained mint/transfer receipts, separate track from the genesis
  annual series (the 1,000/year keeper's-N law governs genesis packs,
  not creator drops).
- **Legal:** the lawyer-before-first-mint gate (2026-09-18) was CLEARED
  per Chauncey 2026-09-27. Mint intents proceed through approval gates.
  Actual Base deployment remains an explicit order (gas is spend).
