# Browser-layer build notes — for the layer architect

Date: 2026-09-29. Hunt wave: browser-hunt-20260929 (5 ArchiveRecords,
archive 565 -> 570; pending copy at
~/.levi/perpetual/pending/browser-hunt-20260929.jsonl).

Chauncey's scope ruling this run: the browser layer gets a dedicated
architect. These ideas are NOTES, not directives — adopt, reshape, or set
aside. Two were already implemented this run before the ruling (kept,
committed, adopt-or-set-aside); the rest are unbuilt.

## Already implemented (adopt or set aside)

### 1. Evidence exhibit — `core/levi/custody/exhibit.py` (committed 080350ea2)
- What: seals a claim + metadata + attachment bytes into one frozen object
  with a sha256 seal and an append-only, hash-chained handling log.
  `inspect_exhibit` returns INTACT/TAMPERED; `render_exhibit` prints an
  evidence card with a mandatory honesty footer.
- Why: X-Posed's forensic overlay proved the pattern — evidence capture is
  only trustworthy when custody is sealed and the verdict covers integrity,
  never truth. The footer ("INTEGRITY IS NOT TRUTH") is structural.
- Home: `levi.custody.exhibit`; wired into the custody SHELF
  (exhibit-seal/log/inspect/render). Tests: tests/test_custody_exhibit.py
  (11 tests, the law-guard-prove proof).

### 2. Claim grader — `core/levi/signals/claim_grade.py` (committed 080350ea2)
- What: grades one claim as OBSERVED (named direct observation, needs
  observed_via + method), INFERRED (named heuristic, mandatory structural
  "signal, not verdict" caveat), or UNVERIFIED (deny-closed default).
  Quotes the claim verbatim; names what evidence would change the grade;
  binds grade to a receipt digest.
- Why: X-Posed's standout honesty — probabilistic claims labeled as
  probabilistic, in the product itself. Grades never self-upgrade.
- Home: `levi.signals.claim_grade`; exported from `levi.signals`
  (`grade_claim`, `ClaimCard`, `render_card`, grade constants).
  Tests: tests/test_signals_claim_grade.py (9 tests).

## Unbuilt — for the architect's design

### 3. Who-pays card on every capability bundle
- What: every bundled capability ships a machine-readable card naming who
  pays for it (user, sponsor, data, funnel) plus an honesty footer stating
  what it does NOT do and cannot prove.
- Why: the Omni teardown — a "free" 18-tool browser never names its payer;
  unverifiable "100% on-device" claims are marketing until audited. LEVI
  bundles capability too; the card is the difference between generosity
  and theater.
- Home: likely `levi.custody` (rides with the artifact) or a new
  `levi.economics` shelf; enforced at bundle-registration time.

### 4. Manifest-diff guard against narrowing capability contracts
- What: a CI gate that fails when a capability's declared contract narrows
  (permissions, interception points, dynamic behavior) without a recorded
  ruling. The narrowing is an attributed event, never a silent deprecation.
- Why: the uBlock/Manifest-V3 lesson — the platform owner rewrote the API
  for its own competitor (blocking webRequest removed, observational kept).
  LEVI must not be re-platformed quietly, by vendors or by its own drift.
- Home: `levi.interop` (next to the manifest); runs in CI.

### 5. Hash-prefix private lookup for shared indexes
- What: queries against any future shared/community index carry only a
  short hash prefix (k-anonymous); the server returns candidates, the
  client filters locally. The server never learns the exact item.
- Why: SponsorBlock's lookup privacy — the crowd's index is useful without
  the querier confessing the query.
- Home: `levi.archive` (search path) or wherever a shared index lands.

### 6. No-remote-fetch lint
- What: a build gate that fails if committed code pulls a library, font, or
  asset from a remote host at runtime. Everything vendored or stdlib.
- Why: Decentraleyes' surviving rule — a dependency fetched from someone
  else's server is a phone call home. LEVI's stdlib-only law, made
  machine-checkable.
- Home: repo lint config / CI; trivial to implement, high leverage.

### 7. Consent ledger (Permission-Guard inversion)
- What: a deny-closed ledger for sensitive capabilities — every grant
  recorded with scope, expiry, and receipt; the user agent is permitted to
  deceive the surveillant (spoof/suppress permission prompts), and that
  deception is declared to the USER, never hidden from them.
- Why: Omni's Permission Guard — lying to the surveillant as a feature,
  with the honesty pointed inward at the user.
- Home: new module, possibly under `levi.custody` (it is a custody record)
  or the browser layer itself.

### 8. Sovereign-path-default sync rule
- What: where two sync paths exist (cloud vs no-cloud P2P), the sovereign
  no-cloud path is the default; the cloud path is the opt-in footnote —
  never the reverse.
- Why: Omni's Sync Mesh (honest, beta, footnoted) vs 1-click cloud sync
  (default headline). Defaults are policy.
- Home: the browser layer's sync design; possibly `levi.mesh` when it exists.

## Non-goals (explicitly not to be built)
- No browser clone, no X/Twitter clone, no account-tracking tool, no
  re-implementation of any extension. Clean-room patterns only.
- Nothing here authorizes network access, credential use, or reading
  anyone's private data. All eight ideas are local-first and stdlib-only.
