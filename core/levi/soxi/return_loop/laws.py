"""Laws for the SOXI teaching return loop.

Declared first, per the law-guard-prove rule (Chauncey, 2026-09-22).
Implementation sits in the sibling modules; the proof artifact is
``tests/test_soxi_return.py`` (property/invariant tests, honestly
named — not a formal proof).

Chauncey's law (2026-09-22): "Then the answers come back here and are
verified and refined and put in cloud — and anyone that connects to
cloud updates the collective intelligence. Update is say every day but
maybe 2-3 days is good."

The return loop is the LOCAL half of that order: inbox -> verify ->
refine -> promote -> sync-package. The cloud backend itself is NOT
built here — the sync package (manifest + deltas + receipts + version
vector) is the interface the cloud side will consume. Cloud endpoint:
the named next build.

Honest limits:
- The verifier can mechanically check schema, ASCII, hype words,
  persona frames, duplicates, and simple arithmetic answers. It CANNOT
  fact-check history/government/grammar/civics lessons — those ride on
  the teacher's correctness duty ("Lessons must be correct") plus
  Chauncey's spot-check queue. The verdict records exactly what was
  checked, so nothing passes silently unverified.
"""

# R1. Verified-only promotion. A lesson enters the local knowledge
#     store ONLY on a PASS or PASS_WITH_CORRECTIONS verdict from the
#     verification gate. Quarantined batches never promote. There is no
#     back door: promote() refuses any lesson without a matching
#     verdict receipt.
# R2. Raw originals are immutable. Returned batch files land under
#     raw/ and are NEVER modified, renamed, or deleted. Refinement
#     produces NEW correction-kind lessons that reference the
#     originals; the originals stand as the record of what the
#     teacher actually said (nothing-thrown-away law).
# R3. Every verdict is receipted. PASS, PASS_WITH_CORRECTIONS, and
#     QUARANTINE all write one hash-chained verdict receipt carrying
#     the full reason set. A promotion without a chained verdict
#     receipt is not a promotion.
# R4. No duplicate topics. The same ground is never retaught: a
#     lesson whose content hash or teacher-supplied topic_id is
#     already in the store is caught as a re-teach, routed to
#     corrections (as a duplicate-flag correction), and NOT
#     promoted again.
# R5. Malformed batches quarantine, never drop. JSONL that cannot be
#     parsed is moved to quarantine/ byte-for-byte with its arrival
#     receipt, and the batch is quarantined with reasons. Quarantine
#     is a waiting room, not a bin.
# R6. Everything is reversible. Every promotion writes a
#     promotion_id; revert_promotion(promotion_id) marks the rows
#     reverted and writes a chained receipt. Chauncey can roll any
#     promotion back from the evidence.
# R7. Sync cadence is Chauncey's dial. Default: collective-intelligence
#     sync package every 3 days ("maybe 2-3 days is good" — his
#     words, reversible). Daily is a one-line config flip. The
#     scheduler never invents cadence; it reads config.json.
