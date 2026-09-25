# The trust toll — hunt report 2026-09-22

Theme: **tech-giant patterns (c)** — the sly-generosity vein. Four finds, one
pattern.

## The pattern

The giants build a *commons trust signal*, wait for everyone to depend on it,
then convert the signal into a toll:

| signal | who built it | the toll |
|---|---|---|
| blue check = verified identity | X/Twitter | $8–16/month rent for the same pixels |
| blue badge = authentic presence | Meta | $11.99–14.99/month, + rent for support |
| your follower graph = your audience | Meta, everyone | ~1–2% organic delivery; pay to reach them |
| "Choice" badge / search rank = endorsement | Amazon | sellers pay the auction; badge gamed |

What they REFUSE to add, in all four cases: **earned, portable, owner-held
proof** — verification bound to claim+evidence+issuer with no rent; delivery
bound to explicit subscription with no auction. They refuse it because a
one-time proof can't be re-billed and a subscription-only feed can't carry
promoted slots.

## Honest inversion (built)

`core/levi/trust/`:

- **attest.py** — the attestation ledger. Badges are issued only against a
  named proof (document check, demonstrated history, community vouch).
  Payment-as-proof is refused *by construction*. Receipts hash-chain;
  revocation is a ledger entry, not a quiet delete. `audit()` flags any
  badge whose only "proof" is a payment receipt.
- **reach.py** — the no-auction feed. Ranking inputs are the user's explicit
  subscriptions only. Every item carries a `why_shown` provenance strip;
  `audit_insertions()` flags anything from a non-subscribed publisher.
  Unsubscribing cuts reach immediately. There is no code path that accepts
  bid money as a ranking input.

Proof gate: 16 tests, all green. Laws declared up front in the module docstrings.

## Skepticism

Percentages vary across trackers; the FTC-Amazon suit is contested and
ongoing. Per-finding flags are in the records' `skepticism` fields.
