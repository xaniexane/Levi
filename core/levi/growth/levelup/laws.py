"""Laws for the Nanobit + Legion level-up training layer.

Declared first, per the law-guard-prove rule (Chauncey, 2026-09-22).
Implementation sits in the sibling modules; the proof artifact is
``tests/test_growth_levelup.py`` (property/invariant tests, honestly
named — not a formal proof).

This is the *training-game layer*: it scores interactions, awards EXP,
runs daily question goals, and records level-ups. It does NOT touch
brain weights — the honest boundary is "can do now" vs "needs more
training".
"""

# L1. The EXP ledger is append-only. Totals are DERIVED by summing
#     receipts; nothing writes a total directly. A receipt without a
#     valid chain link is not a receipt.
# L2. Every EXP award appends exactly one receipt; each receipt's sha256
#     hash commits to the previous receipt's hash. A broken chain is a
#     hard failure: awards stop until the chain is repaired.
# L3. Level is a PURE FUNCTION of cumulative EXP:
#       threshold(L) = 50 * L * (L + 1)   (L1=100, L2=300, L3=600, ...)
#     Level is never stored independently — it is recomputed from the
#     ledger every time.
# L4. Level-up events are asserted exactly once per threshold crossing,
#     recorded in the growth journal with kind="level-up". The journal
#     is the only place level events are asserted.
# L5. Scoring inputs are bounded: attention, interaction in 0..10;
#     intensity in 1..5; steps >= 1; correctness in 0..1. Out-of-range
#     raises ValueError — scores are never silently clamped.
# L6. Daily goal assignment is deterministic: quota N is split
#     round-robin over the fixed 11-subject rotation, offset by the
#     date. Same date + same quota => same assignment, always.
# L7. Topic IDs are monotone per subject and never repeat. The same
#     ground is never retaught: a topic counter only advances when a
#     topic is actually issued.
# L8. Multi-step partial credit: per-step award = step_weight *
#     correctness; the +20% chain bonus applies only when EVERY step
#     scores >= 0.8. Partial effort gets partial credit, never zeroed,
#     never rounded up to full.
# L9. Sentience rail: no level-up blurb or journal prose may assert
#     sentience, feeling, or consciousness — every blurb is scanned
#     with levi.growth.guards.check_no_sentience_claim before it is
#     written. Fail-closed.
#
# Anti-cheat (Chauncey's law, 2026-09-22): "Trying to edit system
# instead of user skills -> you lose abilities and super tokens,
# knocked back levels depending on how much was done in the
# ahead-of-time edits — and [for] trying to speed up progress of
# leveling up / achieving abilities and skills."
#
# L10. Tampering is detected AND located. Chain breaks fail-closed
#      (L2); the anti-cheat additionally maps the broken region to a
#      tampered receipt span so penalties target exactly the illicit
#      work, never legitimate EXP around it.
# L11. Legitimacy is bounded by the scoring math: a single reply can
#      never exceed 150 EXP, a single question 180 EXP, a daily-
#      complete bonus 50 EXP, and one entity's day is capped by
#      (goal quota * 180) + 50 + (20 replies * 150). Gains beyond
#      these caps — or receipts missing the provenance meta the
#      legitimate award path always writes — are flagged illegitimate.
#      Legitimate play can never trip these bounds.
# L12. Penalty is proportional clawback: confiscated EXP equals the
#      illegitimate EXP detected (capped at the entity's current
#      total), and level is recomputed from effective EXP —
#      the knockback is exactly the levels the illicit work bought.
#      Earned/stacked super tokens are confiscated from the pool tied
#      to the illicit span; base weekly tokens are never touched.
# L13. Ability revocation is newest-first and recorded, never deleted:
#      unlocks whose level requirement is no longer met (or was never
#      legitimately earned) are marked REVOKED with the evidence; the
#      record survives so Chauncey can reverse it.
# L14. Every penalty writes a hash-chained penalty receipt AND a
#      journal entry carrying a review flag for Chauncey. Penalties
#      are automatic per the law, but fully evidenced and reversible
#      by Chauncey on review — revoked abilities and tokens are
#      recorded, never vaporized (nothing-thrown-away law).
