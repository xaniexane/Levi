"""Trust, earned — never rented.

The giants turned trust signals into tolls: X and Meta rent the blue check,
Meta throttles your followers' reach and sells it back, Amazon rents the
shelf and costumes it as endorsement. The honest inversion is LEVI's own
trust layer:

- ``attest.py`` — badges earned by PROOF, never by payment. An attestation
  binds three things: the claim (who/what), the evidence (how it was proven),
  and the issuer (who checked). Payment-as-proof is refused by construction.
  Receipts hash-chain, so a badge can be carried and verified anywhere.
- ``reach.py`` — the no-auction feed. The only ranking inputs are the user's
  explicit subscriptions. Every item carries a ``why_shown`` provenance
  strip; ``audit_insertions()`` flags anything from a non-subscribed
  publisher. There is no code path anywhere that accepts bid money as a
  ranking input.

stdlib-only, local-first, no network, no telemetry.

LAWS (declared before implementation; the test suite is the proof gate):

1. Payment is never valid proof of identity. ``issue()`` refuses any
   attestation whose evidence is a payment/subscription receipt.
2. ``verify()`` succeeds only for badges present in the ledger, unrevoked,
   with an intact receipt chain.
3. The receipt chain is tamper-evident: altering any stored receipt breaks
   ``verify_chain()``.
4. Revocation is a public ledger entry, never a quiet delete — a revoked
   badge fails ``verify()`` with reason "revoked".
5. A feed contains only publishers the user explicitly subscribed to.
   Items from anywhere else are rejected at build time, not filtered later.
6. Unsubscribing removes reach immediately — no grace-period ghost delivery.
7. No ranking input accepts money. ``audit_insertions()`` reports any item
   whose provenance strip claims a sponsored or boosted source.
"""
