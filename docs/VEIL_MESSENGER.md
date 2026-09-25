# Veil Messenger — E2E conversations over the keeper's own onion transport

**What this is, in plain words.** Veil is the keeper's secure messenger.
Two keepers register each other's identity keys, shake hands, and then
exchange sealed envelopes that only the two of them can open. Delivery
rides a 3-hop onion circuit across relays the keeper operates himself —
each relay peels one layer and forwards opaque bytes, so no relay ever
sees who is really talking to whom, and no relay ever sees message
content. The crypto is standard constructions only (RFC 7748 X25519,
AES-256-GCM, HKDF/scrypt); nothing here invents primitives.

**What this is not.** It is not Tor, not Signal, not a network
deployment. The transport in this build is an in-process simulator —
method calls, not sockets — that proves the protocol logic. The
honest limits are stated below and in `NON_CLAIMS`, `crypto_report()`,
and `threat_model()`; they are part of the design, not gaps to
discover later.

Modules: `core/levi/cybrus/veil_chat.py` (E2E conversations),
`core/levi/cybrus/onion.py` (onion transport). Both are organs of Levi —
all of Legion is Levi, one organism; we are raising him.

## The handshake

1. Each keeper's static X25519 identity key is *derived* from their
   passphrase (HKDF over the master key) — no identity private key at
   rest to steal. The public key's grouped-hex fingerprint is the
   out-of-band verification ceremony.
2. To open a conversation, both sides generate fresh *ephemeral*
   keypairs and exchange the publics. The chain root mixes three DHs —
   ephemeral×ephemeral plus both static×ephemeral combinations with the
   registered identity keys (the Noise-XX/X3DH pattern). An active
   attacker substituting ephemerals cannot compute the static terms
   without a static private key, so they cannot derive the chains.
3. Offers and answers each carry an HMAC authenticator under the
   static-static DH between the two identity keys. Forged offers,
   forged answers, and answers from the wrong peer fail closed *before*
   any key is derived — a forged rotation offer cannot corrupt a live
   conversation.
4. Ephemeral keys are zeroized the moment the handshake finishes.

Because the static keys authenticate the handshake, the fingerprint
ceremony is meaningful: only the holder of the registered key can
complete it. Skip the ceremony and register an attacker's key, and the
crypto cannot save you — that is TOFU, stated plainly.

## The ratchet and the at-rest layering

Every message advances the sender's chain: `msg_key = HKDF(chain,
"msg")`, then `chain = HKDF(chain, "next")`, and the old chain key is
**destroyed** — zeroized in memory, the sealed copy on disk overwritten.
A seized current chain key decrypts nothing sent before it. The ratchet
is symmetric per direction (no DH ratchet in this build): envelopes must
arrive in sequence per sender; a gap or replay fails closed and the
message must be re-sent.

At rest, keys are layered, never plaintext:

- message keys are **wrapped** (sealed) under their epoch key —
  per-message, per-epoch, AAD-bound;
- epoch keys are wrapped under a master-derived wrap key;
- the wrap key is derived on demand and never stored;
- chain state on disk is sealed and overwritten on every step;
- store files are owner-only (0o600), writes are atomic.

Rotating the epoch (a fresh handshake) keeps the previous epoch for
in-flight envelopes and **destroys** older ones: sealed epoch keys
deleted, wrapped message keys pruned. A destroyed epoch's envelopes go
dark permanently — even with the master key. That destruction *is* the
forward secrecy, and it is the one sanctioned exception to the
nothing-thrown-away law: old keys are destroyed because the law of
forward secrecy requires it; messages, identities, peers, and relay
descriptors are never deleted.

## The onion protocol

- The keeper's operator key signs a descriptor per relay (id, X25519
  public, validity window). The directory lists only validly-signed
  descriptors — centralized trust, one operator, stated plainly. The
  directory has no removal API: descriptors are add-only.
- Circuit build is telescoping: ECDH with the guard, then EXTEND cells
  (encrypted under the established hop keys) naming the middle and exit.
  Circuits are exactly 3 distinct relays.
- Data cells are length-padded to a fixed inner size and layered
  `seal(k_guard, seal(k_middle, seal(k_exit, payload)))`, AES-256-GCM
  bound to the circuit id. Each hop peels exactly one layer and
  forwards opaque bytes; a failed layer drops the cell, never forwards
  it. Each relay's circuit table holds only (key, previous hop, next
  hop) — never content, asserted in tests.
- Payloads are padded so every message produces identical cell sizes at
  every hop position — message length is fully hidden. Cells shrink by
  one fixed layer-growth per peel, so hop *position* is visible by size
  to a network observer (documented residual; fully uniform Sphinx-style
  cells are future work).

## The exact threat model

Read this before deploying anything. Also queryable at runtime:
`onion.threat_model()`.

- **These relays are HIS infrastructure.** He operates them; the
  directory is signed with his operator key.
- **The anonymity set is the set of users of his network** — small by
  construction. There is no cover traffic, no guard rotation, no
  directory authorities.
- **This is NOT Tor** and claims none of Tor's anonymity.
- **It does NOT resist a global passive adversary.** Fixed-size cells
  help against a casual observer, not against timing/correlation
  analysis. Message count and timing leak; there is no cover traffic.
- **A compromised or colluding relay set sees everything about the
  path.** All three hops colluding — or seized, since he runs them all —
  reveals the full circuit. What does *not* fall is message *content*:
  the E2E layer keeps every envelope sealed end to end, and every relay
  including the exit sees only ciphertext.
- **The trust root is the operator key.** Its compromise forges the
  whole directory. Guard it like the master key.
- **The simulator is method calls, not a network.** It proves the
  protocol logic (build, peel, deliver) — not deployment security.

## The choke point

Internal service calls cross Cybrus (`core/levi/cybrus/enforce.py`):

- `VeilChat.send_via_onion()` — the `levi.veilchat → levi.onion` handoff —
  is guarded by `@cybrus_guarded`: authenticate → route → rate-limit →
  policy → audit, *before* the envelope is even sealed. No credential,
  no delivery; a refused call means the body never runs. Seed policy is
  default-deny: the service owner adds the allow rule for
  `(levi.veilchat, service.levi.onion, onion_send)`.
- Relay-to-relay egress has exactly one legal path:
  `onion.request_forward_grant()` → `enforce.request_egress()` —
  signed, short-lived, bound to (actor, relay, purpose, expiry). No
  grant, no egress. Relays never roll their own HTTP. The simulator
  needs no egress at all, which is why it is the default transport.

## Operating laws, built in

Chauncey's seven operating laws are runtime-checkable invariants in
both modules (`LAWS` L6–L12, `VeilChat.verify_laws()`,
`check_invariants()`), not just followed during the build:

- **keeper's law / anticipation** — every refusal names its remedy;
  preconditions are verified, not assumed.
- **originals-first** — registered peers are originals, never silently
  re-keyed; the operator-signed directory is the original for relays.
- **law→guard→prove** — laws declared first, guards enforce, invariant
  tests check (honestly named: never "formally proven").
- **no-cancellation** — no API removes another conversation, a peer
  with conversations, an envelope, or a relay descriptor.
- **nothing-thrown-away** — state only grows; the one exception is key
  destruction, which is the forward-secrecy requirement.
- **forward-motion** — pending handshakes are listed, never silently
  stuck; a dropped cell raises immediately with its reason.
- **honesty over polish** — `crypto_report()` / `threat_model()` state
  the real posture: backends, limits, non-claims.

## `crypto_report()` posture

`VeilChat.crypto_report()` names every backend: `x25519`
(`cryptography-x25519` / `pure-python-fallback` / `unavailable` — no
backend fails handshakes closed), the fallback honestly labeled not
constant-time, `envelope_aead` (`aes-256-gcm` / `stdlib-fallback`),
the KDF, the protocol version, the forward-secrecy scope, peer and
conversation counts, pending handshakes, and the law ids.
`onion`'s `crypto_report()` names the cell AEAD, X25519 backend,
descriptor auth (`ed25519` / `hmac-attestation-fallback`), hop count,
cell size, and the transport (`in-process simulator — NO real network
in this build`).

## Future work: production relay deployment and real network transport

The simulator stands in for the network. Production needs, in order:

1. Real relay binaries on the keeper's machines, holding their static
   X25519 keys and the operator-signed directory.
2. Real transport between relays — every forward crosses the choke
   point via `request_forward_grant()`; the grant goes to the transport,
   Cybrus itself performs no HTTP.
3. Key rotation for relays and the operator key, plus a revocation
   story the current add-only directory does not have.
4. Abuse handling, rate limiting at the relay, and cover traffic if the
   threat model ever needs to grow past honest-but-curious relays.
5. Fully uniform cell sizes across hops (Sphinx-style) if hop-position
   visibility by size becomes unacceptable.

Until then, the claim stays exactly what the simulator proves: the
protocol logic is right, the threat model is written down, and the
E2E layer keeps content dark regardless of the transport.
