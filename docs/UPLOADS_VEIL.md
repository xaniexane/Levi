# Upload Study: Veil lineage (`lock-and-key-vault-genesis.zip`)

**Track:** Veil — the keeper's sealed, tamper-evident, keeper-held-keys
secure messenger. (Per docs/LEXICON.md: "Veil (2026-09-17). The vault, a
secure messenger. The keeper's lock-and-key lineage: sealed, tamper-evident,
keeper-held keys. Not the social platform's name — the messenger's.")
**Worker:** uploads worker (vault track). **Date:** 2026-09-17.
**Original (untouched):** `~/workspace/user/files/lock-and-key-vault-genesis.zip`
**Improved working copy:** `~/workspace/uploads-work/vault-genesis/`

## 1. What the upload was

"Lock & Key Vault" — a security-first concept for a private Android
(Kotlin/Jetpack Compose) platform combining: cryptographic device identity,
end-to-end encrypted 1:1 messaging, an encrypted local vault
(Bitwarden-style), private profiles/contacts, a lawful digital-goods
marketplace, and a self-hostable Kotlin/Ktor relay server. The standout
quality is its *honesty*: phased plan, explicit non-claims ("no production
cryptographic claims until verified"), a real threat model, and
cryptography-decision docs. No invented algorithms anywhere.

## 2. State assessment (working / stub / dead)

**Working (real, platform-backed):** CSPRNG (`PlatformSecureRandom`),
AES-256-GCM AEAD (`AesGcmAead`), SHA-256 fingerprints, HKDF-SHA-256,
Android Keystore EC P-256 device identity (`KeystoreDeviceIdentityManager`,
private key never leaves the Keystore), `EncryptedKeyValueStore`
(AndroidX Security Crypto), unit tests (AEAD round-trip/tamper/wrong-key/
wrong-AAD, in-memory store, Result type), CI workflow with secret-scan and
docs-presence jobs, full doc suite (ARCHITECTURE, SECURITY, SECURITY_
ARCHITECTURE, THREAT_MODEL, CRYPTO_DECISIONS, identity/messaging protocol
skeletons).

**Stub (interfaces/skeletons):** `BiometricUnlock` (interfaces only),
`Transport`/`TransportManager` (interfaces only), `VaultStore` /
`MessageEnvelopeStore` (interfaces only), server routes (only `/` and
`/health`; device registration, envelope relay, marketplace all "future"),
`features/` (8 empty module dirs), `scripts/` (empty), root `tests/`
(empty), `security/incident-response/` (referenced by docs, missing).

**Dead:** nothing dead — except one *live bug* (see §3).

## 3. What was improved in the working copy

1. **Fixed a real, security-critical bug: `AesGcmAead` double-nonce.**
   `seal()` prepended the nonce to its output while `sealWithRandomNonce()`
   prepended it a *second* time, so `openWithPrefixedNonce()` always fed 12
   stray bytes into GCM as ciphertext and authentication failed — the
   round-trip, wrong-key, and wrong-AAD unit tests could never pass (the
   tamper test passed only by accident). `seal()` now returns
   ciphertext+tag only, per its interface contract; `sealWithRandomNonce()`
   prepends exactly one nonce. Byte-layout verified by simulation (no Kotlin
   toolchain in this sandbox).
2. **Branding → Veil** (keeper's name): README title, app display name
   (`strings.xml`). Internal `com.lockandkeyvault` package identifiers are
   deliberately unchanged — renaming them is a mechanical Android-layer
   follow-up that needs a compile check.
3. **Completed the missing `security/incident-response/` playbook**
   (contain → assess → rotate → notify → root-cause), which
   SECURITY_ARCHITECTURE.md §8 referenced but didn't exist.
4. **De-staled docs:** SECURITY_ARCHITECTURE.md implementation-status table
   ("Concrete crypto: Not yet" → landed + fix note), docs/DEVELOPMENT.md
   current phase, README phase map (Phase 2 → done), GENESIS_BUILD_STATUS.md
   study-pass entry, CHANGELOG Unreleased (Added/Fixed/Changed).

## 4. What was applied LEVI-native (revival laws: recreate, never copy)

**New module: `core/levi/cybrus/veil.py`** — Veil recreated as a
LEVI-original, stdlib-only, defensive, local-only secure-messenger core.
Ideas studied from the upload; no code copied, nothing masked:

- **Keeper-held keys** — everything (device tokens, conversation keys,
  ledger key) derives via PBKDF2-HMAC-SHA256 (600k iters) + HKDF-SHA256 from
  the keeper's passphrase. Master key lives in memory only while unlocked;
  `lock()` best-effort zeroizes it. No key material ever touches disk.
- **Sealed tamper-evident envelopes** — encrypt-then-MAC construction
  (HMAC-SHA256 counter-mode stream + HMAC tag, domain-separated,
  verify-then-decrypt, `VB1` magic), header fields (sender, recipient, seq,
  versions, timestamp) bound into the AAD, device HMAC attestation over
  header+blob. Tampered blob/header, wrong key, wrong AAD → fail closed.
- **Device identity** — stable device IDs, key versions, grouped-hex
  fingerprints + `verify_fingerprint()` ceremony helper, rotation with a
  one-version grace window (in-flight envelopes still open), and an
  HMAC-chained revocation ledger (`verify_ledger()` detects tampering).
  Documented honestly: local HMAC attestation, **not** cross-device PKI.
- **Replay protection** — per-(conversation, sender) strictly increasing
  sequence numbers; replays and reorders rejected. (Found and fixed in
  testing: the send counter and receive watermark initially shared one
  registry and tripped the replay defense on self-talk — now split into
  `sent`/`seen` namespaces.)
- **Ciphertext-only envelope store** — per-conversation append-only JSONL;
  tests assert plaintext never appears in the store files.
- **Threat register + explicit non-claims** — 8 data-driven threats
  (asset/attack/mitigation/residual/status) and 6 non-claims (no forward
  secrecy, no post-quantum, not AES, attestation≠PKI, local-only, no
  unlocked-device protection), with `check_invariants()` the keeper can
  audit. All owner-only file permissions (0o700/0o600), atomic writes,
  `store_lock` for read-modify-write paths (reuses `levi.cybrus._paths` —
  the existing gateway was not rewritten).

**Tests: `tests/test_veil.py` — 32 tests, all green**, hermetic
(tmp_path roots, no HOME writes, no network): AEAD round-trip/tamper/
wrong-key/wrong-AAD/bad-magic/nonce-uniqueness, passphrase verifier +
lock/unlock, device lifecycle, fingerprint ceremony, rotation grace,
revocation + ledger-chain tamper detection, envelope round-trip, header
tampering, replay rejection, revoked-sender rejection, rotation survival,
ciphertext-only store, threat-register completeness, invariants.

## 5. Honest gaps

- The upload's Android app and Ktor server were **study-only** (no Android
  builds in repo scope); the AEAD fix is verified by byte-layout simulation,
  not by running the Kotlin test suite.
- The revocation ledger is local — no network distribution in this module.
- Internal `com.lockandkeyvault` package IDs in the working copy still await
  the mechanical rename (needs an Android compile check).
- Ready-for-review: keeper (Chauncey) has **not** reviewed this. Marking
  ready-for-review only — never claiming his review.

## 6. Hardening pass (2026-09-18) — "make it stronger"

The keeper ordered Veil strengthened; the three known gaps above (fallback-
grade symmetric construction, no forward secrecy, no memory-hard KDF) are
now closed LEVI-native in `core/levi/cybrus/veil.py`:

- **Real AEAD when available.** AES-256-GCM via the `cryptography` package
  is preferred when importable (`Veil.backend == "aes-256-gcm"`); otherwise
  the stdlib HMAC-CTR construction remains as a honestly-labeled fallback
  (`"stdlib-fallback"`). Envelopes are versioned by magic (`VB2` vs `VB1`);
  the opener dispatches on the magic and fails closed — a `VB2` blob on a
  machine without `cryptography` errors with an install hint, never opens
  silently.
- **Memory-hard KDF.** `hashlib.scrypt` (n=2^15, r=8, p=1, 32 MiB,
  workstation-grade) where available; PBKDF2-HMAC-SHA256 600k fallback.
  The choice is pinned in `config.json` (pre-hardening vaults default to
  PBKDF2, which sealed them) and reported via `Veil.kdf` /
  `Veil.crypto_report()`.
- **Forward secrecy.** Per-conversation epoch ratchet
  (`Veil.rotate_conversation`): epoch 0 is the legacy master-derived key
  (pre-ratchet era, kept so old envelopes still open); every epoch ≥ 1 is
  a fresh random key, sealed owner-only under a master-derived wrap key,
  with only the live epoch plus one grace epoch retained — older epochs
  are destroyed (removed, local copies zeroized). A destroyed epoch
  cannot be re-derived, not even with the master key.
- **Post-quantum remains open** — explicitly not claimed; separate future
  track.

**Tests: `tests/test_veil.py` — 46 tests, all green** (32 original + 14
new): backend reporting, KDF selection/pinning/legacy-default,
scrypt-vs-PBKDF2 divergence, fallback `VB1` sealing, `VB2`-without-
`cryptography` fail-closed, versioned dispatch, epoch isolation (old keys
can't read new traffic, new keys can't read old), epoch AAD binding,
legacy pre-ratchet envelope compatibility, ratchet-store owner-only +
sealed-only, locked-rotation rejection, bad-name rejection.
