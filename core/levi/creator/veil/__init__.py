"""Veil Messenger — KFX2 Milestone 1 (PL-05).

The hardened messaging layer over the creator platform's chat containers.

Two tracks, never merged:
- :mod:`levi.creator.veil.si` — SI track (Plaiground). Adult-gated,
  per-message sealed envelopes, keeper-held keys.
- :mod:`levi.creator.veil.ai` — AI track (Echoverse). SFW-checked,
  plain local records, no adult gate.

Shared across tracks (this module):
- The ternary delivery truth: every message is QUEUED, DELIVERED, or
  SYNCED. Giants do sent/failed (binary); the third state is the
  offline-sync truth — sealed on the owner's device, then attested
  into an owner-initiated bundle, never ambient.
- Per-tier attachment grants: open / entry / standard / flagship —
  beyond the binary locked/unlocked of the giants (tier names reuse
  the pricing advisor's entry|standard|flagship ladder).
- The honest threat model: :mod:`levi.creator.veil.threat_model`.

KFX2 notes baked in: no server in the hot path (delivery is local and
instant), no boosting or discovery surface here at all, no network
calls, nothing ambient — sync is an explicit owner act, opt-in always,
no dark patterns. The sealing construction is Encrypt-then-MAC
(VEIL1), described honestly — never AES-GCM, never "end-to-end"
marketing language.
"""

from __future__ import annotations

# -- Ternary delivery states ------------------------------------------------
# QUEUED: sealed (SI) / staged (AI) in the outbox, not yet in the chat store.
# DELIVERED: persisted in the owner's local chat store with a receipt.
# SYNCED: included in an owner-initiated attested bundle export.
# There is no fourth state: a flush that fails raises, and the entry
# stays QUEUED (fail-closed), never half-written.
QUEUED = "queued"
DELIVERED = "delivered"
SYNCED = "synced"

DELIVERY_STATES = (QUEUED, DELIVERED, SYNCED)

# -- Attachment grant tiers -------------------------------------------------
# Giants do locked/unlocked. We do the ladder: the pricing config's
# advisor tiers (entry|standard|flagship) plus "open".
ATTACH_TIERS = ("open", "entry", "standard", "flagship")
DEFAULT_ATTACH_TIER = "open"

# -- Attestation ------------------------------------------------------------
# Bundle attestation is HMAC-SHA256 keyed on the owner key — it proves
# the bundle came from the owner's machine. It does NOT encrypt the
# bundle: exported bundles carry plaintext message bodies. Named
# honestly; it is not a legal or cryptographic claim beyond that.
ATTEST_ALG = "VEIL1-ATTEST-HMAC"
ATTEST_V = 1

# -- Named limits -----------------------------------------------------------
MAX_ATTACHMENT_BYTES = 32 * 1024 * 1024  # 32 MiB, local-first cap


class MessengerError(ValueError):
    """A Veil Messenger operation was invalid."""


class DeliveryDeniedError(PermissionError):
    """Membership/grant/ownership check failed on a messenger operation."""


class AttestationError(MessengerError):
    """A bundle's attestation failed verification."""


__all__ = [
    "QUEUED",
    "DELIVERED",
    "SYNCED",
    "DELIVERY_STATES",
    "ATTACH_TIERS",
    "DEFAULT_ATTACH_TIER",
    "ATTEST_ALG",
    "ATTEST_V",
    "MAX_ATTACHMENT_BYTES",
    "MessengerError",
    "DeliveryDeniedError",
    "AttestationError",
]
