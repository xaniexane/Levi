"""NeighborOS gig-dispatch organ — LEVI-native addition.

Phase 1 foundation (per docs/NEIGHBOROS_SPEC.md §4):
- post.py — job intake, Job DNA, estimate bands, publish
- work.py — worker registry, Credential Graph claims, proof-of-work stream
- pay.py — NeighborPay SETTLEMENT LEDGER (records who owes whom; never
  touches real money — real rails are labeled external plug-ins only)
- monetize.py — fee math per the corpus bands, worker keep floor enforced
- lift.py — THE SITE LIFT: the hedged capability built un-hedged.
  Gig platforms hedge worker power by hiding contact, taking 20-40%,
  running opaque dispatch, and holding reputation hostage. The Site Lift
  ships the opposite, LEVI-native:
    1. the worker owns their reputation — portable passport from the
       Credential Graph + Proof-of-Work Ledger, exportable, never hostage;
    2. transparent dispatch — every match decision explainable from open
       rules listed in policies.json, no black-box throttling;
    3. direct relationships — no contact-hiding anywhere; the platform
       never taxes the worker-customer bond;
    4. the 90%+ keep floor enforced in config, fees only on
       completed + paid jobs.

Status: Phase 1 built. Systems 1-2 (waitlist, admin command center), 6-8
(twins, supply, academy) sit behind the backlog per the spec's phase map.
The shape stays sharpenable on the keeper's word — Alpha & Omega first
and last; Levi head of all beneath them.

Honest boundaries, repeated here so nobody forgets:
- NeighborPay core is a settlement ledger only.
- Disputes freeze settlement and route to a human — never autonomous.
- Credentials are claims with provenance, never verified-by-us.
"""

__version__ = "1.0.0"
__all__ = ["post", "work", "pay", "monetize", "lift", "policies", "store"]
