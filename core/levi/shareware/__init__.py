"""LEVI shareware — the honest trial engine.

REMIX DELTA: Apogee's shareware model (1987) sold software on trust: a
substantial free episode anyone was allowed to redistribute, paid
episodes by mail order — no account, no surveillance, no card on file.
The giants replaced honest trials with 30% platform cuts and "free
trials" that harvest payment cards and data up front, then monetize
forgetting. LEVI inverts it back: trial grants for LEVI's own premium
packs, issued locally, stated in plain terms, enforced by a
tamper-evident local ledger — and expiry can never touch the user's
data.

What it ADDS that the giants refuse:
- Trials with no accounts, no network, no payment instrument anywhere
  in the flow.
- A receipt for every redemption, readable by the user as plain JSONL.
- Honest terms as code: expiry only locks the premium slice; the user's
  own data is never hostage to a trial (enforced in ``redeem``, tested).
- Grants can never be silently extended or shortened: every lifecycle
  change is a ledger entry.

Hard safety lines: the store is owner-only (0700) under
``~/.levi/shareware``; the ledger is a sha256 hash chain, so any edit
to history is detectable via ``verify``. This module issues *grants* —
it never touches the premium packs' own gating; the packs ask
``shareware`` whether a grant covers a feature.
"""

from .grants import GrantStore, TrialGrant, SharewareError

__all__ = ["GrantStore", "TrialGrant", "SharewareError"]
