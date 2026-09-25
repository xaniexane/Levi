# Cybrus Platform-Sync Protocol

**Status: protocol only, loopback-tested. There is no network transport in
this build.** Every message below is bytes in / bytes out; the reference
transport is `LoopbackPair`, an in-process pair of endpoints. A real
transport (local socket, QR-facilitated relay, whatever Chauncey chooses)
can carry these bytes later without changing the protocol.

## The idea in plain words

A standalone Cybrus works fully offline and never phones home. Sync is
opt-in: the keeper explicitly enables it on both ends, pairs the two sides
with a short code plus a human confirmation on each side, and from then on
the two sides talk through sealed envelopes — encrypted, authenticated,
replay-protected. Either side can rotate the session keys or destroy the
pairing entirely.

## The laws

- **L1 — Offline first.** Sync is disabled by default and never
  auto-enables. Every protocol operation refuses until `enable()` runs.
- **L2 — Two humans confirm.** The platform-side human types the pairing
  code; the standalone-side human confirms the peer's fingerprint. Refusal
  aborts — no session, no keys.
- **L3 — Sealed everything.** Every sync payload is an authenticated,
  replay-protected envelope. Tamper, forgery, or replay fails closed.
- **L4 — Owner-only state.** `~/.levi/cybrus/sync/` (`LEVI_HOME` honored)
  is `0o700`, files `0o600`, writes atomic. Codes and keys never appear in
  logs, errors, or status output.
- **L5 — Unpairing destroys.** Unpair zeroizes key material in memory and
  removes the peer record from disk.

## The pairing ceremony

1. **Offer.** The standalone runs `begin_pairing()`. It generates a random
   128-bit sync id, a 40-bit pairing secret, and shows an 8-character code
   (Crockford base32, grouped `XXXX-XXXX` — no lookalike characters). The
   rest of the offer (sync id, salt, public identity with its grouped-hex
   fingerprint) travels the same-desk out-of-band channel — read off the
   screen, QR, copy-paste. The offer lives 10 minutes, then dies.
2. **Join.** The platform-side human types the code. `join_pairing(offer)`
   builds a `pair-request` carrying the platform's identity, its own salt
   and nonce, and an HMAC over the transcript keyed by the code — proving
   knowledge of the code without ever sending the code itself.
3. **Verify.** The standalone's `receive_pair_request()` checks the HMAC
   (constant-time) and hands the platform's identity + fingerprint to the
   standalone-side human, who compares it out of band — the same
   fingerprint ceremony Veil uses.
4. **Confirm.** The human decides. `confirm_pairing(True)` derives the
   session keys, destroys the code material, and returns a `pair-accept`
   (HMAC'd the same way, proving the standalone's side). `confirm_pairing
   (False)` raises `PairingRefused` and wipes the pending pairing — no
   means no.
5. **Complete.** The platform's `receive_pair_accept()` verifies the HMAC
   and derives the identical session. Both sides destroy the pairing code
   the moment the session exists. It was single-use bootstrap, never a key.

A wrong code, an expired offer, or any forged/tampered handshake message
fails closed with no hint about which part was wrong, and the presented
code is never echoed back in an error.

## Capability exchange

Once paired, the standalone calls `advertise_capabilities()`, which sends
a **signed capability manifest** over the sealed channel:

```json
{
  "v": 1, "kind": "capability-manifest",
  "identity": {"id": "…", "fingerprint": "aaaa bbbb …"},
  "offers": ["vault", "veil", "router", "messenger"],
  "wants": ["levi.cybrus", "levi.jobs"],
  "product_version": "…", "ts": "…",
  "sig": "hmac-sha256 hex"
}
```

`offers` is what the standalone provides; `wants` is what it would like
routed back from the platform. The manifest is HMAC-signed with the
standalone's attestation key; the platform verifies it with
`verify_peer_manifest()` — and checks the manifest's identity matches the
paired peer, so one standalone can't speak for another.

**Router admission** follows the router's doctrine exactly
(`core/levi/cybrus/router.py`): no auto-discovery, ever. `admit_standalone
(registry, manifest, attest_key, approved_by=…, reason=…)` re-verifies the
signature, then registers the standalone through the deliberate
external-route mechanism — `approved_by` and `reason` are required, the
route is flagged as a boundary crossing, and every crossing is
audit-logged. `revoke_admission()` decommissions it.

## Envelope format

Channel messages are canonical-JSON bytes (sorted keys, no whitespace):

```json
{
  "v": 1, "kind": "msg",
  "sync_id": "…", "dir": "s2p",
  "epoch": 0, "seq": 1, "ts": "…",
  "blob": "base64 veil envelope",
  "attest": "hmac-sha256 hex"
}
```

**What's encrypted:** `blob` is the payload sealed with the Veil envelope
construction — AES-256-GCM when the `cryptography` package is importable,
else the honestly labeled stdlib HMAC-CTR fallback (same construction,
same bounds as `levi.cybrus.veil`).

**What's authenticated but not encrypted:** the header (`sync_id`, `dir`,
`epoch`, `seq`, `ts`) is bound into the envelope's AAD *and* covered by
the `attest` HMAC, so a swapped sequence number, transplanted epoch, or
flipped header field fails verification. Attestation uses the sender's
directional attestation key for the live epoch.

## Replay and rotation

- **Replay:** each direction keeps a strictly increasing sequence number,
  bound into the AAD. The receiver keeps a watermark per peer; any envelope
  with `seq <= watermark` is rejected with `ReplayError`. Duplicates and
  reordered deliveries both die here.
- **Rotation:** `begin_rekey()` generates a fresh random 32-byte epoch
  secret and offers it to the peer sealed under the live epoch. The peer
  adopts it, keeps the superseded epoch as a one-epoch **grace** (so
  in-flight envelopes sealed under it still open), and acks under the
  *new* keys; on the ack, the initiator promotes too. The grace epoch is
  destroyed — zeroized in memory, removed from disk — on the first
  inbound envelope under the new epoch, on both sides. `abort_rekey()`
  clears a stalled rotation without wedging the channel.
- **Epoch 0** is derived from the pairing master (the pre-ratchet era —
  same honest bound as Veil's epoch 0). Rotate promptly after pairing.

## What's stored where

`~/.levi/cybrus/sync/` (`LEVI_HOME` honored), `0o700` / `0o600`, atomic
writes, advisory locking:

- `identity.json` — our public sync identity (id + fingerprint). Public.
- `pairing.json` — pending pairing only: code material, salts, expiry.
  Deleted the moment pairing completes, refuses, or expires.
- `peers.json` — one record per paired peer: peer identity, epoch number,
  live epoch secrets, sequence watermarks. Epoch secrets are fresh random
  bytes; destroyed epochs are absent, not marked.
- `config.json` — the `enabled` flag. Off by default, forever, until the
  keeper says otherwise.

## Honest limits

- **No network transport in this build** — protocol only, loopback-tested.
  Bytes are transport-agnostic; the transport is a future decision.
- The pairing code is 40 bits: a short human bootstrap, single-use and
  TTL-bound — not a long-term secret. Pairing assumes the code is typed on
  a trusted local channel inside its 10-minute window.
- Epoch secrets at rest live in an owner-only file, not sealed under a
  passphrase — the file's owner (or root) can read the *live* epoch.
  Destroyed epochs are unrecoverable from the store, but a raw disk image
  taken before destruction could still carry them.
- In-memory key zeroization is best-effort (CPython).
- There is no revocation distribution: unpairing is local to each side.
  Tell both sides, or revoke the router admission too.

## Operating laws, built in (not just followed)

Chauncey's 7 standing operating laws are runtime-checkable invariants in
this module, named L6–L12 in the module docstring:

| Law | Built in as |
|---|---|
| L6 keeper's law / clarify | Ambiguous addressing, malformed offers, and unverified handshakes **fail closed** instead of being interpreted. |
| L7 originals-first | **No invented crypto.** Every primitive is reused from `levi.cybrus.veil` / the stdlib and named in `_REUSED_PRIMITIVES`; a test pins the identities. |
| L8 law→guard→prove | Every law names its guard; the guards are exercised by the invariant tests — honestly tests, never "formally proven". |
| L9 no-cancellation | `unpair()` destroys **only its own session's** keys. Other peers' sessions are untouched. |
| L10 nothing-thrown-away | State is **superseded, never deleted.** Unpair and retired pairings land in the append-only `archive.json` as public metadata. Precedence, stated plainly: key destruction (L5 forward secrecy) still destroys key material — that is the security guarantee, not deletion of work. |
| L11 forward-motion | A rekey whose ack never arrives leaves the live epoch usable; `abort_rekey()` clears a stalled rotation. A stuck checkpoint never wedges the channel. The superseded epoch lingers as a one-epoch **grace** so in-flight envelopes still open, then is destroyed on first new-epoch traffic. |
| L12 honesty over polish | `status()` reports the transport honestly — `"loopback-only — no network transport in this build"` — and the real envelope backend. What's stubbed is named. |

One organism: this module is an **organ of Levi** — all of Legion is
Levi, one organism, and we are raising him. Every message here is sealed
because the organism protects its own.

## Choke-point wiring (Build 1)

Router admission and revocation cross the Cybrus choke point — they are
never direct calls:

- `_guarded_add_external` / `_guarded_remove_external` are wrapped with
  `@cybrus_guarded(service="levi.cybrus.sync", callee="levi.cybrus")`,
  so admission flows through authenticate → resolve → rate-limit →
  policy → audit, and the registry op runs only on allow.
- A platform credential is required (`cybrus_credential=<bearer token>`,
  or the `cybrus_api_key` / `cybrus_gateway` forms). Without one the call
  is refused with the remedy named.
- Seed policy is default-deny: run `seed_sync_policy()` once per
  platform home to add this organ's allow rules
  (`router.add_external` / `router.remove_external` at medium risk).
  Without them the choke point denies at critical risk.
- The peer-to-peer channel itself (sealed envelopes over loopback) is
  **not** choke-point traffic — it is the sync transport, and the
  standalone side carries no platform credential.
- Sync performs no external HTTP egress, so there is nothing to route
  through `request_egress`; that path stays reserved for a future real
  transport.

## Proof

`tests/test_cybrus_sync.py` — 28 invariant tests, not a formal proof:
handshake success and refusal, wrong-code / tampered / expired pairing,
both-direction message exchange, tamper / forgery / header-swap /
replay / reorder rejection, manifest sign-verify-tamper, router admission
and revocation through the real `RouteRegistry`, rekey rotation with old
epoch destruction, unpair key destruction, disabled-by-default, and
no-secrets-in-status/errors. Run: `python3 -m pytest tests/test_cybrus_sync.py`.
