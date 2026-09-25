"""Veil Messenger threat model — the honest version, shipped with the feature.

This is the anti-encryption-theater document. Read it before claiming
anything about what Veil Messenger protects.

WHAT THE SEALING IS
    VEIL1: Encrypt-then-MAC. Per-message keys derived from the keeper key
    via HMAC-SHA256 HKDF-style derivation; encryption is a SHA-256 CTR
    keystream XOR; authentication is HMAC-SHA256 over
    nonce + ciphertext + context. See levi.creator.seal (ALG =
    "VEIL1-HMAC-XOR"). It is NOT AES-GCM. Nothing in this codebase
    describes it as AES-GCM, "military-grade", "unbreakable", or markets
    it as "end-to-end". Those words are banned here.

WHAT IT PROTECTS AGAINST
    - Tampering with sealed records at rest on the owner's device. Flip
      a byte in a message envelope and the read fails loudly
      (SealError) instead of returning corrupted or forged content.
    - Casual reading of the SI store files. Payloads are not plaintext
      in the store; the keeper key lives in a 0600 file the owner holds.
    - Message transplant between chats. Each envelope's sealing context
      binds the chat id, so an envelope copied into another chat fails
      verification on read.
    - Out-of-band edits. si_update re-seals with the keeper key, so any
      edit made outside the code fails verification the next time the
      record is read.
    - Wrong-recipient delivery inside the app. Membership is enforced on
      every send AND every read; closed chats are readable but silent;
      attachment grants are checked per fetch, and listings are
      metadata-only so payloads never leak through a list view.

WHAT IT DOES NOT PROTECT AGAINST
    - An attacker who can read the keeper's memory or who already holds
      the keeper key file. Stated plainly in the base module and repeated
      here: the key file or the keeper's memory wins, full stop.
    - An unlocked or compromised device. Local-first means the owner IS
      the server; there is no remote party to appeal to.
    - Bundle confidentiality. Export bundles carry plaintext message
      bodies. Attestation proves the bundle came from the owner's
      machine (origin); it does not encrypt anything. Whoever holds the
      bundle file reads the messages — treat the export destination
      like the messages themselves.
    - Age. The adult gate (PIN + exact affirmation, default OFF,
      fail-closed, minors hard-locked) is an owner-authenticated opt-in
      on this machine. A PIN is never presented as proof of legal age,
      anywhere, ever.

WHAT THE AI TRACK SAYS OUT LOUD
    The AI (Echoverse) track stores plain local JSONL with no sealing
    and no adult gate. That is deliberate and documented here rather
    than dressed up: the reversal of the giants' encryption theater is
    to describe exactly what each track does, in code and in copy.

WHAT "NO SERVER" MEANS
    Delivery is local and instant; there is no server round-trip in the
    hot path. Sync is an explicit, owner-initiated bundle export/import
    — nothing ambient, nothing phoning home, no telemetry. The attested
    bundle is single-owner portability (backup, device move with the
    key file) in this build; cross-owner sync is not built and not
    claimed.

TRACK ISOLATION
    SI and AI stores, code paths, and keys never cross. The SI keeper
    key never touches the AI track; the AI attestation key never
    touches the SI track. Tests assert this on every run.
"""

THREAT_MODEL_VERSION = 1

__all__ = ["THREAT_MODEL_VERSION"]
