# VEIL_COMPANIONS — Plaiground AI Companions Inside Veil

**Status:** implemented — `core/levi/cybrus/veil_companions.py`
(`VeilCompanions`), smoke-tested end to end 2026-09-27.

## The idea in one line

Open Veil, see your AI companions next to your human contacts, and chat
with them through the same sealed interface. The companion's messages go
through Veil's envelope/ratchet crypto like any other conversation.

## Design decisions

### 1. How companions appear in the contact list

A companion is a **virtual peer**: `peer_id = "companion-<slug>"`,
registered through the normal `VeilChat.add_peer()` path with a
deterministic virtual X25519 identity (HKDF from the keeper's master
key — stable per keeper+companion, never leaves the device, never a real
remote identity). The peer record carries:

- `"kind": "companion"` (humans keep `"kind": "human"`, back-compatible)
- `"companion_name"`, `"verified": true`, `"verified_by": "local-companion"`

No remote fingerprint ceremony applies — the keeper *is* both sides — so
the record is marked verified-by-local at registration instead.

`VeilCompanions.list_chats()` joins conversations with peer records and
returns every chat with its `kind`, so the UI badges companions (🤖-style)
while the crypto underneath stays identical.

### 2. How Veil routes a message to a companion (vs a human)

`send_to_companion(conv_id, text)` performs one full turn:

1. **Gate first** — `require_adult()`; fails closed when the Plaiground
   gate is off (VC1). The companion can't even be *listed* with the gate
   locked.
2. **Bounds** — `check_bounds(text)` (VC2).
3. **Outgoing** — sealed via `VeilChat.send_message()` (send chain
   advances, ratchet destroys the old key).
4. **Brain** — `ChatSession(companion_name, tone).say(text)` runs
   **in-process** (VC4): deterministic traits + tone + one Echoverse beat
   per turn. No network, no external model.
5. **Incoming** — the reply is sealed as an *incoming* envelope by
   advancing the **recv** chain (`_companion_incoming`), with
   `sender_fp` set to the companion's virtual fingerprint so the
   transcript distinguishes sides exactly like a human conversation.
6. **Continuity** — the exchange is journaled via `plaiground.depth`
   (rapport/recall); the Cybrus audit log records conv id + sequence
   numbers only (VC7).

Both envelopes are stored in the conversation's sealed journal —
ciphertext at rest, re-openable while the epoch lives.

### 3. Where the companion's "brain" runs

Locally, in-process: `levi.plaiground.chat.ChatSession`. The reply engine
is the shipped deterministic one (traits, whitelisted non-explicit tones,
Echoverse branching). Session objects are cached per conversation so
turns accumulate; `depth` journaling gives cross-session continuity.

### 4. QR distribution still works

`companion_invite_qr()` issues a signed ticket
(`cybrus://companion/<body>.<sig>`, HMAC-SHA256 under a keeper-derived
key) carrying the persona definition (name, traits, boundaries) plus a
definition hash — no secrets, single-use default, 72h TTL, broker_qr
pattern (VC6/VS7).

`redeem_companion_qr()` verifies the ticket, then provisions the persona
**through plaiground's own gate-checked `create_companion()`** — the
ticket is data, plaiground is the law (VC5). Redemption fails closed when
the receiving device's Plaiground gate is locked: a companion can never
be defined with the gate off.

## Laws

| Law | Statement |
|-----|-----------|
| VC1 GATE-FIRST | Every public entry calls `require_adult()` first. |
| VC2 BOUNDS | User text passes `check_bounds()` before the brain. |
| VC3 SEALED-TRANSCRIPT | Same envelope/ratchet machinery as human messages. |
| VC4 LOCAL-BRAIN | Brain runs in-process; no network imports. |
| VC5 NO-BYPASS | Definitions only via plaiground's gate-checked functions. |
| VC6 QR-SIGNED | Invites HMAC-signed, single-use, expiring. |
| VC7 AUDIT-METADATA-ONLY | Audit carries ids/counts, never plaintext. |
| VC8 NO-CANCELLATION | Companion peers/chats follow VeilChat's no-drop rules. |

`verify_laws()` statically checks VC1 (every public method calls
`require_adult`) and VC4 (no network imports).

## Honest bounds

- The local self-handshake uses **fresh random chain roots** (like a
  human handshake's derived roots), sealed under a fresh epoch key. The
  epoch key is sealed under the master-derived wrap key, so a master-key
  compromise exposes live epochs — the same documented bound as Veil's
  single-party envelopes and human conversations. Forward secrecy holds
  against chain-key seizure: old chain keys are destroyed on advance.
- The companion brain is the shipped deterministic engine, not a large
  model. Replies reflect/reframe/branch; they don't generate novel
  content. Upgrading the brain later doesn't change the transport.
- Companion invites share a persona *definition*; each device's
  conversation history stays local (no sync — by design).
