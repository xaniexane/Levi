# PL-05 KFX² — Veil Messenger + Creator Services + Production Plan

Date: 2026-09-21. Workstream 3 of 13.
Frame: KFX² (Chauncey's law) — absorb the outside pattern (strengths as well
as weaknesses) → reverse it → improve it → return a version only we could
build. Unreplicable means: our architecture (local-first, deterministic,
gated) makes their cost structures and compromises unnecessary.

## Binding constraints (standing law, non-negotiable)

1. **Adult/SI and SFW/AI tracks NEVER merge.** Separate stores, separate code
   paths, no cross-track queries. Tests must keep asserting this.
2. **All adult surfaces PIN-gated with the on/off switch**, minors
   hard-locked, default OFF. The gate is the product architecture, not a
   popup.
3. **Money flows ONLY via Cybrus.** No other rail, no side channel.
4. **LIVE PAYMENTS, LEGAL REVIEW, ADULT LAUNCH, and CUSTOMER RELEASE stay
   GATED on Chauncey.** This plan ends AT the gates and never crosses them.
   Publication hold stands: push/publish/ship still require his five
   specifics per action (destination, scope, account, copy, media).
5. **Veil sealing is Encrypt-then-MAC / HKDF.** Do NOT describe it as
   AES-GCM. No legal-sounding claims about encryption: no "military-grade,"
   no "unbreakable," no "end-to-end" marketing language. The honest threat
   model ships with the feature.
6. **Pricing anchors** (Chauncey, standing): dating $1/day pass, $5/week,
   $12–15/month; creator $1 taste, $4/month, $20 patron; **platform cut
   12%** on digital products created and monetized on our platform.
7. **Physical-goods cut stays OPEN** — no number assumed, no number invented.
   Gated on Chauncey. We facilitate; the cut question waits on his word.
8. No free core: every tier priced above $0 (standing doctrine).
9. No per-sale fee surprises beyond the stated digital cut. No
   discovery-tax penalty for being found on our own marketplace.

Existing base this plan builds on: `core/levi/creator/` (si/ + ai/ tracks,
PIN gate, bounds/SFW rules, pricing config with advisor receipts),
`core/levi/creator/money.py` (Cybrus MoneyGateway, fail-closed, paper
only), private media + private chats + dating privacy + meetup safety, and
the Veil sealing lineage (Encrypt-then-MAC, SHA-256 CTR keystream +
HMAC-SHA256, HKDF keys, keeper-held 0600 key file). See
`docs/CREATOR_PLATFORM.md`. Nothing below re-litigates that base; it grows
it.

---

## (a) Competitor teardown

Everything below is from public secondary sources found 2026-09-21, marked
as reported. Where sources conflict, the conflict is stated. Nothing is
invented; every "could not verify" is labeled.

### Telegram — messaging + channels + Stars monetization

**Features.** One-to-one chats, group chats, public/private channels,
"secret chats" (opt-in per-device), bots, Mini Apps, file sharing up to
4GB (Premium tier). Creator monetization stack: Telegram Stars (in-app
currency launched mid-2024; users buy Stars via App Store/Google
Play/Fragment; channels charge Stars for paid media posts, paid messages,
gifts); ad revenue share 50/50 on channels over 1,000 subscribers, paid in
Toncoin via Fragment; Premium subscription at $4.99/mo (US). Paid media
posts allow paywalling individual channel posts.

**Pricing/fees (reported, sources disagree on the cut — both stated).**
Source A claims Telegram takes NO commission on Stars from paid media or
gifts (creator keeps 100%, withdraws to TON). Source B reports effective
creator take ~65% after platform + app-store fees, with a $0.013/Star
withdrawal rate vs ~$0.02/Star purchase rate, a 21-day hold, and a 1,000-Star
(~$13) minimum cashout. **Could not verify the exact take; the sources
contradict each other.** Premium: $4.99/mo US (multiple sources, consistent).

**Trust & safety.** The sharp edge: only secret chats are end-to-end
encrypted. All default chats (private, group, channel) are client-to-server
encrypted via the proprietary MTProto protocol and stored on Telegram's
servers — ESET's published study concluded Telegram holds the decryption
keys and servers can access cloud-chat contents. Deletion is a request, not
verifiable erasure. Support is thin (volunteer-run). The platform is a single
point of policy risk: Apple briefly delisted Telegram in August 2026 over
content violations (restored after removals); Telegram claims 337,000+
groups/channels shut down in 2026 for illegal material. NCMEC has logged
570,000+ reports relating to Telegram since 2013 (reported by NCMEC-linked
coverage). **Could not independently verify these enforcement numbers.**

**What users love:** raw speed, near-total reach (one source reports ~18%
average channel post reach, claimed higher than Instagram — unverified),
4GB file sharing, frictionless Stars monetization with no minimum subscriber
count, channel-as-storefront flexibility.

**What users/creators hate:** the encryption story is widely described as
misleading (E2EE marketing vs non-E2EE defaults); moderation that is
simultaneously too lax (CSAM criticism) and arbitrary (channel bans with no
appeal path); no real customer support; platform dependence — a national
block or App Store action can erase a creator's distribution overnight.

### OnlyFans / Fansly — creator monetization

**Features.** Creator profiles, subscription tiers, pay-per-view (PPV)
posts, tips, direct messages with paid content (DMs are a major revenue
surface), live streams. OnlyFans has no native internal discovery — creators
drive 100% of their traffic externally (reported). Strict identity
verification (government ID + selfie + biometric matching, tightened 2026).
Immediate permanent bans for deepfake/AI-face content (reported). 35,865
accounts removed in February 2026 for policy violations (single-source
report, could not verify).

**Pricing/fees (well-sourced).** OnlyFans: flat 20% platform fee on
subscriptions, tips, and PPV, confirmed by quoted Terms of Service and
checked against an archived ToS copy dated July 2026. Fansly: creators earn
80% (20% fee), confirmed via quoted ToS checked July 2026. Fanvue: 15% for
the first 12 months, then 20% (reported; terms quoted by a fee-comparison
source). Passes: flat 10%, fee includes processing, instant payouts
(reported by multiple secondary sources — not independently verified).

Typical subscription pricing reported: $4.99–$9.99 entry, $9.99–$19.99
sweet spot, $24.99–$49.99 premium. DMs + PPV + tips reported at 60–70% of
creator revenue (single secondary source — mark as unverified industry
estimate).

**Payouts.** OnlyFans: 7-day clearance on new earnings, then bank transfer
3–5 business days, $20 minimum; PayPal does not allow payouts for adult
content; withdrawals must go to the name matching the verified ID. Payout
complaints center on holds, bank blocks, and verification stalls. In August
2026 Fenix International (OnlyFans' owner) was hit with a proposed class
action over withdrawn 5% lifetime referral commissions (reported by legal
press — the case is a filing, not a finding).

**What creators love:** the largest paying audience in the lane (377M users
reported by one secondary source — could not verify), DM/PPV surfaces that
actually monetize fan relationships, a proven payout pipeline.

**What creators hate:** the 20% cut (compounds to tens of thousands of
dollars over a career — $12,000/year difference vs a 10% fee at
$10,000/month revenue, per fee-comparison math); slow support (responses
reported at 3 days to weeks); opaque, unilateral policy changes; account
bans with appeals that often fail; no discovery — every fan must be imported
from elsewhere; the platform's terms can be rewritten under them.

### Adult classifieds (SkipTheGames-style discovery)

**Features.** Free-to-post listings by city, keyword search, free unlimited
messaging between posters and responders (per a review site — could not
independently verify the current site), saved searches. Minimal to no
identity verification. No matchmaking algorithm.

**What users like:** free, simple, no account friction, broad category
coverage, fast manual search.

**What users hate (and the pattern is the point):** scam density —
deposit/gift-card demands before meeting, fake profiles and recycled ads
across cities, ransom-style extortion after contact begins; reviews are
unreliable (competitor sabotage, fake self-boosts); no dedicated customer
support; legal exposure (law-enforcement reverse stings documented across
multiple states; enforcement is patchy but real); meetings linked to
robberies in police warnings. The site's own safety guidance puts personal
security entirely on the user. Multiple civil actions have alleged
inadequate prevention of harmful postings (reported — cases, not findings).

**Could not verify:** exact current fee structure for promoted/boosted ads
(the baseline is free); current moderation practices; user counts.

### Dating pricing anchor (for context on our $1/$5/$12–15 ladder)

Tinder's 2026 pricing is dynamic by age, market, and platform — multiple
sources report different numbers, which is itself the finding: **could not
verify a single current US price.** Reported ranges: Plus ~$9.99–$24.99/mo,
Gold ~$19.99–$39.99/mo, Platinum ~$29.99–$49.99/mo, Select $499/mo
invite-only; age-based pricing (over-29 pays more) reported across sources.
The standing PL-05 dating ladder ($1 day / $5 week / $12–15 month) sits
under every reported tier of the giant's ladder — consistent with the
existing CREATOR_PLATFORM.md schedule and the no-free-core doctrine. Not
re-litigated here.

---

## (b) KFX² — absorb, reverse, amplify, unreplicable

### Telegram

**Absorb — strengths worth taking:**
1. **Speed as a design value.** Their clients feel instant because the
   product is engineered for it. We adopt the bar: Veil Messenger targets
   sub-interaction latency on-device; no server round-trip in the hot path,
   ever.
2. **Channel-as-storefront.** One publisher, many subscribers, paywalled
   posts — the exact shape of our creator drops (tiers + grants already
   built). We adopt the surface; we rebuild the plumbing.
3. **Frictionless in-platform monetization.** Stars prove that when paying
   is one tap, fans pay. We adopt the one-tap shape through Cybrus
   settlement — planned, paper-only until Chauncey registers a rail.
4. **Reach without the algorithm tax.** Their channel posts land in feeds
   without a pay-to-boost layer. We adopt that as doctrine: our discovery
   is chronological / subscription-graph ordered, and boosting does not
   exist on our marketplace.

**Reverse — their weaknesses, flipped:**
1. **Default chats are server-readable.** ESET's finding is our opening:
   there is no server. Veil Messenger messages are sealed on the owner's
   device (Encrypt-then-MAC, keeper-held keys); a court order to "the
   platform" finds nothing because there is no platform holding plaintext.
   There is no server to subpoena, no server to breach, no server to
   sell.
2. **Encryption theater.** They market privacy while defaults stay
   readable. Our reversal is the honest threat model shipped next to the
   feature: what is sealed, against whom, and exactly where the boundary
   stops (attacker holding the key file or the keeper's memory wins —
   stated plainly).
3. **Opaque moderation + thin support.** Their bans land without appeal.
   Our reversal: the SI bounds law is public and in code; it does not move
   under users. The gate is a physical-feeling switch in the owner's hand,
   fail-closed.
4. **Single-point platform risk.** Their creators' distribution can vanish
   in a delisting or a national block. Our reversal: local-first stores,
   portable exports (attestation-signed bundles), the owner holds the
   data — a takedown of "us" is meaningless because there is no "us" to
   take down.

**Amplify — their strengths, past what their structure allows:**
Telegram's speed came from client engineering funded by an ad-and-currency
machine that requires their servers. Our version — sealed, serverless
messaging with instant local delivery and optional offline sync — is faster
where it matters (no round trip) and needs no ad model to pay for. Their
Stars monetization is a closed currency that can be held, taxed, and
reversed by the platform; our version is Cybrus settlement with a stated
12% digital cut computed in the open, per sale, in the ledger the creator
can read. They cannot copy this without deleting their servers — which is
how they eat.

### OnlyFans / Fansly

**Absorb — strengths worth taking:**
1. **The creator economy shape itself.** Profiles → tiers → content drops →
   DMs → PPV → tips → payouts. It works because it matches how fans
   actually pay for relationships. We adopt the whole shape.
2. **DM/PPV as the revenue core.** If ~60–70% of creator revenue is DM/PPV
   (industry estimate, unverified), then sealed private chats and gated
   private media are the product, not accessories. We adopt that priority:
   our private chats and media modules ARE the monetization surface.
3. **Strict verification for the adult lane.** We adopt the principle —
   age gating with teeth — while keeping it owner-local: PIN + affirmation
   + minor hard-lock, never a selfie sent to a vendor's server.

**Reverse — their weaknesses, flipped:**
1. **Opaque 20% cut.** Their cut is a line item you can't negotiate and
   barely see. Our reversal: **contract-grade economics** — 12% stated in
   the pricing config, computed per sale, every receipt shows the split.
   The creator is a partner with a ledger, not a supplier with a dashboard.
2. **Payout fog and holds.** 7-day clearance, bank blocks, name-match
   rejections. Our reversal: every paid flow records honestly as
   `pending_payment` with the plan id until a rail exists; once a rail is
   registered, settlement records carry the full trail (amount, cut, rail
   reference) — no lump-sum fog deposits, no mystery deductions.
3. **No discovery + policy roulette.** They give creators no audience and
   rewrite the terms underneath them. Our reversal: discovery with no
   boosting (subscription graph + chronological), and terms that live in
   code and config the owner can read — nothing moves under users.
4. **Unilateral commission changes** (the referral class action is the
   pattern). Our reversal: the cut is versioned in the pricing config;
   changing it changes the config, visibly, with receipts — never a quiet
   terms edit.

**Amplify — their strengths, past what their fee structure allows:**
They pay creators for uploads; **we pay creators for relationships.**
Fan-interaction automation, companion characters, scene commissions — the
layer the giants never built. Our amplification: the creator keeps 88% on
every flow (subscription, PPV, tip — all of it, no flow carved out), the
cut never rises on "discovery" sales (see Gumroad's 30% below), and the
ledger is the creator's own file, portable, readable, theirs. OnlyFans'
business model forbids this margin of generosity; our local-first
architecture has no 1,000-person trust-and-safety payroll to feed, so it
doesn't need the 20%.

### SkipTheGames-style classifieds

**Absorb — strengths worth taking:**
1. **Frictionless posting and search.** Their speed comes from zero-friction
   publishing. We adopt the UX: post in seconds, search instantly —
   while adding what they refuse to.
2. **Local discovery granularity.** City-scoped, category-scoped boards map
   directly onto our classifieds trust graph.

**Reverse — their weaknesses, flipped (this is the whole lane):**
1. **Scam density → auditable trust.** Redacted listings (no poster
   identity in public search — already built in `si/privacy.py`) plus the
   published trust formula from `docs/CLASSIFIEDS.md` (score ships with its
   explanation; unknown listers score 0.0 and say so). Fake profiles meet
   a graph, not a feed.
2. **Unreliable reviews → ledger over ratings.** No five-star theater;
   trust comes from vouches the owner curates, recomputed per importer.
3. **Safety-is-your-problem → meetup safety as a feature.** Opt-in
   check-in plans with pre-authorized escalation records (already built in
   `safety.py`) — the platform does the work they tell users to do alone.
4. **Sting exposure → explicit disclosure gates.** The responder chooses
   identity revelation per response; nothing leaks beyond the choice.

**Amplify:** they sell "skip the games" as speed. Our version is speed WITH
safety physics: redacted discovery, gated disclosure, trust you can audit,
a safety plan that fires exactly once on a missed check-in. They can't
copy it — trust-graph auditing and sealed redaction destroy the
volume-driven, verification-free model that is their entire supply.

### The marketplace layer — digital AND physical (Chauncey's directive)

**The directive:** the platform has a digital AND physical marketplace. We
take a cut on digital products created and monetized on our platform —
**house rate 12%** (the standing PL-05 cut, unchanged), unless Chauncey
sets otherwise. Physical goods: we facilitate; **the cut stays OPEN and
gated on Chauncey** — no number is assumed here.

**Absorb — three patterns:**

*Facebook Marketplace (physical goods, social-graph distribution):*
1. **Social-graph distribution as trust.** Profile ratings, friends in
   common, seller history — the trust signal rides the graph, not a star
   rating. We adopt the shape; we replace their opaque graph with our
   auditable one (published formula, per-owner contacts, recomputed trust).
2. **Zero-friction local listings.** Post a photo, set a price, done. We
   adopt the UX for physical listings.
3. **Distribution without an ad layer for local sales.** We adopt the
   doctrine: no boosting, no paid placement on our boards.

*Etsy (maker storefronts):*
1. **Storefronts as identity.** Shops with a face, a catalog, a story.
   We adopt creator storefronts on both tracks (SFW storefronts open; SI
   storefronts behind the gate).
2. **Maker economics done right.** We absorb the storefront pattern and
   reverse the fee fog below.

*Gumroad (digital products):*
1. **Dead-simple digital checkout.** Product page, pay, download. We adopt
   the shape through Cybrus (paper until a rail is registered).
2. **Merchant-of-record honesty.** Gumroad handling sales tax since 2025
   proves buyers and sellers both prefer the platform to own the messy
   part. We adopt the principle: when rails go live, the settlement record
   owns the full trail (tax, cut, rail ref) — never the creator's
   spreadsheet problem.

**Reverse — their fee and trust deficits:**
1. **Etsy's fee fog → one stated number.** Listing fee + 6.5% transaction
   + ~3% processing + 12–15% mandatory offsite ads = an effective 10–25%+
   that forces sellers to "act as diligent accountants" (seller quote,
   reported). Our reversal: **12% flat on digital, stated in the contract,
   computed per sale, receipted.** No listing fee, no per-transaction
   nickel ($0.20s, $0.25s), no mandatory ad tax, no "payout fog" lump-sum
   deposits.
2. **Gumroad's Discover tax → no discovery penalty.** Gumroad charges 30%
   flat on sales through its own Discover marketplace — even on the
   seller's own traffic — triple the direct rate, no volume discounts
   ever. Our reversal: discovery costs the creator nothing extra. The 12%
   is the 12% whether the buyer came from a link or from our own
   discovery. Punishing a creator for being found is the exact
   unreplicable inversion.
3. **Gumroad's scale penalty → partner economics at scale.** Their 10%
   flat forever means a $10K/month seller pays $1,000+ every month with no
   ceiling and no volume break. Our reversal: 12% flat, no per-sale fixed
   fees ($0.50s), and the ledger is the creator's — plus local-first
   delivery has no marginal cost for us, so the cut funds the ledger, not
   a server farm.
4. **Facebook Marketplace's scam economy → the trust layer above.** Their
   model is "trust our graph" — a graph you can't inspect — plus Purchase
   Protection that only covers shipped onsite-checkout items, leaving local
   cash sales (the majority) unprotected. Our reversal: the auditable
   trust graph + redacted listings + meetup-safety plans, on physical
   listings too.

**Amplify — past what their fee structures and trust deficits allow:**
Their marketplaces are ad-and-fee machines: Etsy's mandatory offsite ads,
Gumroad's Discover tax, Facebook's shipped-checkout 10%. Every one of them
charges the seller for the platform's own distribution. Our version —
**the distribution IS the physics**: the trust graph, the sealed chat, the
redacted search, the ledger. The creator keeps 88% of digital revenue at
any scale, pays nothing extra to be discovered, and owns a portable,
receipted record of every sale. Their cost structures (ad teams, moderation
armies, server fleets) make this generosity impossible for them; our
local-first architecture makes the 12% cut *plenty*, which is exactly why
they can't follow us here.

**Physical goods — the open question:** we facilitate (listings, trust
graph, sealed chat, meetup safety); **the physical-goods cut is OPEN and
gated on Chauncey.** This doc assumes no number and invents none. The build
ships the facilitation layer with the cut as a config placeholder that
refuses to compute until he sets it — fail-closed, like the money gateway.

### UNREPLICABLE — the signature only we can sign (PL-05)

1. **No server to subpoena.** Sealed on-device messaging + keeper-held
   keys. Telegram's entire business is the server; ours doesn't have one.
2. **Contract-grade 12%.** Stated, versioned, receipted, computed per sale
   — against OnlyFans' opaque 20%, Etsy's fee fog, Gumroad's 30% Discover
   tax. Their margins need their cuts; our physics doesn't.
3. **The gate as architecture.** PIN + on/off + minor hard-lock on every
   adult surface. No competitor ships adult mode as a physical-feeling
   switch with a fail-closed off position.
4. **Tracks that cannot merge.** The isolation is structural (separate
   stores, no cross-track queries), not policy. A policy can be
   reinterpreted; a code path that doesn't exist can't be.
5. **Discovery with no tax and no boost.** Chronological /
   subscription-graph ordering, auditable trust scores, zero paid
   placement. Their discovery is their revenue; ours is our physics.
6. **The ledger is the product.** Every sale, every sub, every tip —
   receipted, portable, creator-readable. Their dashboards are retention
   tools; our ledger is the creator's property.
7. **Physical + digital under one trust roof.** Facilitated physical
   exchange (trust graph + meetup safety) and digital commerce (12% cut,
   Cybrus settlement) sharing the same sealed chat and the same honest
   pricing — with the physical cut still open and waiting on his word.

**Return to sender:** everything they monetize through scarcity and fog —
per-message metering (n/a, but their caps), blurred tiers, opaque cuts,
paid discovery, server-side lock-in — we ship as physics, because our
physics made the scarcity unnecessary. Standing positioning law (Chauncey,
2026-09-21, the uproar doctrine): we offer what they do, what they don't,
and do it even better, at fraction-of-fractions prices — feature-for-feature
parity PLUS what they lack, better built, dollar-scale entry, volume over
margin.

---

### Positioning — the uproar doctrine (Chauncey, 2026-09-21)

Chauncey's positioning law: we offer what they do, what they don't, and
do it even better, and for fraction of fractions — feature-for-feature
parity PLUS their gaps, better built, at radically lower prices.
Dollar-scale entry, volume over margin. For PL-05 the law is concrete:
the teardown above is the feature checklist matched; the reversals are
the "what they don't" added; the 12% stated digital cut and the
dollar-scale ladders are the pricing proof.

**Parity — what we match feature-for-feature.** Telegram's shape (fast
messaging, groups, channels, in-platform one-tap monetization); the
full OnlyFans creator-economy shape (profiles → tiers → drops → DMs →
PPV → tips → payouts); SkipTheGames' frictionless posting and local
search; Etsy's maker storefronts; Gumroad's dead-simple digital
checkout; Facebook Marketplace's zero-friction local listings. The
slate matches the lane feature-for-feature — rebuilt on our physics,
not borrowed from theirs.

**Exclusives — what they don't offer.** Sealed, serverless messaging —
there is no server to subpoena, breach, or sell — with the honest
threat model shipped next to the feature instead of encryption
theater; contract-grade economics (12% stated in config, computed per
sale, receipted, versioned); the adult gate as architecture (the PIN
age-gate doctrine already in this doc — unchanged, not restated);
SI and AI tracks that structurally cannot merge; discovery with no
boosting, no paid placement, no Discover-style tax; a portable
creator ledger the owner keeps; an auditable trust graph, redacted
listings, and meetup-safety plans where the classifieds giants ship
scam density.

**Price as a fraction of theirs.** Our digital cut is **12%**, stated
and receipted — against OnlyFans/Fansly's **20%** (well-sourced in this
doc: quoted Terms of Service, checked against archived ToS copies,
July 2026), Gumroad's **30% Discover tax** (majority secondary
reporting), and Etsy's reported **10–25%+** effective take (secondary
sources: listing + transaction + processing + offsite-ad layers).
Physical-goods cut is **OPEN — gated on Chauncey; no number assumed,
none invented.** Dating entry ($1/day, $5/week, $12–15/month) and
creator entry ($1 taste, $4/month, $20 patron) sit at dollar scale under
the giants' ladders — Tinder's reported $19.99–$49.99+/mo tiers
(dynamic pricing; this doc could not verify a single current number).
All money flows route through Cybrus, per the binding constraint above.

## (c) PRODUCTION-PHASE PLAN

Sequenced build order. Ends AT the Chauncey gates; never crosses them.
Docs only here — milestones are build contracts for the implementation
crew, not code.

### Milestone 0 — Law and canon audit (read-only)
- Re-verify track isolation (si/ sealed vs ai/ plain, no cross-track
  queries), gate enforcement on every SI entry, Veil sealing described
  honestly (Encrypt-then-MAC/HKDF, never AES-GCM), money gateway still
  fail-closed with `NoRailConfigured`.
- Output: a short audit note + any violations repaired before M1. No new
  features.

### Milestone 1 — Veil Messenger hardening
- Sealed 1:1 and owner-moderated group chats (extends existing
  `si/chats.py`, `ai/chats.py`): per-message sealed envelopes at rest,
  membership enforced on every send and read, closed chats readable but
  silent.
- Offline-first delivery: outbox queue with local delivery receipts; sync
  is explicit and owner-initiated, never ambient.
- Portability: export/import of chat history as attestation-signed bundles
  (same pattern as classifieds export); trust recomputed against the
  importer's own contacts.
- Attachment sealing: media payloads sealed at rest with per-tier grants
  (extends existing media modules); metadata-only listings keep payloads
  out of list views.
- Threat-model doc shipped next to the feature: what is sealed, against
  whom, where the boundary stops. **No encryption claims beyond
  Encrypt-then-MAC with keeper-held keys.**
- Tests: membership enforcement, tamper-evidence (flip a byte, read
  fails), gate-locked SI entries, export/import round-trip.

### Milestone 2 — Creator services KFX² surface
- Creator profiles + subscription tiers + content drops wired to the
  existing pricing config (dating $1/day, $5/week, $12–15/month; creator
  $1 taste, $4/month, $20 patron).
- **Creator ledger:** every sale/sub/tip appends a receipted entry —
  amount, stated 12% cut computed in the open, creator share, timestamp,
  `pending_payment` state. The ledger is a readable, portable file the
  creator owns. This is the OnlyFans-reversal made concrete.
- DM/PPV primitives: private media grants + sealed chats as the paid
  interaction surface; tips as ledgered micro-flows (paper until rail).
- Discovery: chronological / subscription-graph ordering; **no boosting,
  no paid placement, no Discover-style discovery tax** — the cut is 12%
  whether the buyer arrived by link or by search.
- SI creator surfaces behind the gate; AI creator surfaces open and SFW.
  Tracks never merge — tests assert it on every milestone.
- Tests: ledger math (12% on subs, PPV, tips), tier gating, gate-locked
  SI, track isolation, no-boost invariant.

### Milestone 3 — Dating/classifieds trust layer
- Redacted public search (headline/seeking/terms, no poster identity) —
  extends existing `si/privacy.py`; AI-track SFW equivalent.
- Auditable trust scores ported from the classifieds trust graph:
  published formula, per-owner contacts, unknown listers score 0.0 and say
  so; every score ships with its explanation.
- Disclosure gates on every response: responder chooses identity
  revelation per message; nothing leaks beyond the choice.
- Meetup safety wired to dating/classifieds flows (opt-in check-in plans,
  exactly-once escalation with pre-authorized disclosure only).
- Tests: redaction in search results, disclosure-gate choices honored,
  trust scores explain themselves, escalation fires exactly once.

### Milestone 4 — Physical marketplace facilitation (cut OPEN/gated)
- Physical listing schema: item, condition, price, pickup/shipping,
  location granularity the seller chooses.
- Sealed negotiation chats (Veil Messenger, M1) between buyer and seller;
  no poster identity in public search.
- Trust graph + meetup-safety plans attached to physical exchange.
- **Money handling:** physical payments route through Cybrus like
  everything else; the platform cut for physical goods is a config
  placeholder that **refuses to compute until Chauncey sets it** —
  fail-closed, documented, tested (unset cut = no settlement math, sale
  recorded as pending).
- Tests: placeholder refusal, no assumed number anywhere in code or docs,
  facilitation flows green without a cut.

### Milestone 5 — Digital marketplace (12% stated cut, paper settlement)
- Digital product listings: scene commissions, companion characters,
  digital goods (the marketplace KFX² surface).
- Checkout shape: product page → Cybrus settlement intent → recorded as
  `pending_payment` with plan id; 12% cut computed and receipted in the
  creator ledger. **No live rail** — the gateway still fails closed.
- Provenance honesty: procedural/AI-generated content labeled as exactly
  what it is; no photorealism claims; the honesty gap the tube giants left
  open stays filled by us.
- No per-sale fixed fees, no listing fees, no discovery surcharge — the
  stated 12% is the whole story, and the receipt proves it.
- Tests: 12% math across product types, paper-settlement states, no
  hidden deductions, provenance labels present.

### Milestone 6 — Hardening, test green, doc review
- Full test suite green across creator, messenger, marketplace modules;
  track-isolation and gate-lock tests re-run from zero.
- Privacy review: redaction, disclosure gates, sealing boundaries,
  physical-facilitation records.
- Copy review: **no legal claims about encryption anywhere** (grep for
  AES-GCM / "military-grade" / "end-to-end" marketing language and kill
  it); pricing copy matches the standing anchors exactly.
- Output: a readiness memo listing every gate still closed and what each
  gate needs from Chauncey.

### The gates (where this plan STOPS)

| Gate | Held by | What unlocks it |
|---|---|---|
| LIVE PAYMENTS | Chauncey | His five specifics per action (destination, scope, account, copy, media) + a registered rail |
| LEGAL REVIEW | Chauncey | Counsel review of ToS, pricing copy, adult-lane terms before any customer release |
| ADULT LAUNCH | Chauncey | Publication hold release, per-action approval, five specifics |
| CUSTOMER RELEASE | Chauncey | Same five specifics per shipping action; no blanket "ship it" crosses this |
| PHYSICAL-GOODS CUT | Chauncey | He sets the number (or confirms zero); placeholder stays fail-closed until then |

### Hard nos (the crew does not do these, ever)

- No live payments without the five specifics. Paper stays paper.
- No legal claims about encryption. Veil = Encrypt-then-MAC/HKDF; the
  threat model ships with the feature; "AES-GCM" never appears.
- Adult/SI and SFW/AI tracks never merge — in code, in stores, in UI, in
  docs. Any proposal that merges them is rejected, not debated.
- No per-sale fee surprises: digital is 12%, stated, receipted. No
  Discover-style discovery tax. No listing fees on digital.
- No physical-goods cut assumed. The placeholder refuses until he sets it.
- No free core. Every tier above $0.
- No boosting, no paid placement, no ad layer on discovery or the
  marketplace. Their revenue model is not ours.
- No external model routing or third-party service enters the pipeline
  without his word.
- No customer release, no adult launch, no push/publish/mint/ship without
  the per-action five specifics.

---

## Honest limits (what this doc does not claim)

- Competitor figures are secondary-source reports from 2026-09-21 web
  research; every conflict and unverified number is marked above. Pricing
  and policies move; nothing here substitutes for re-verification at build
  time.
- OnlyFans/Fansly fee figures (20%) are the best-sourced numbers in the
  doc (quoted ToS, archived copies). Telegram's Stars take is genuinely
  disputed between sources. Tinder's pricing is dynamic and was not
  reducible to a single number.
- The creator ledger, paper settlement, and marketplace modules described
  in (c) are build contracts, not shipped code. No code was written for
  this doc.
- Physical-goods facilitation assumes buyers and sellers arrange their own
  handoff; we provide the trust layer and the safety plan, not escrow,
  not dispute resolution, not shipping — unless Chauncey orders otherwise.
- Adult launch legality (2257-style record-keeping, state AV laws, payment
  processor adult-content rules) is exactly why LEGAL REVIEW is a gate.
  This doc does not pre-judge it.

## Sources (research conducted 2026-09-21, secondary sources)

- Telegram Stars/monetization: autogram.ninja (2026 toolkit), Medium
  creator guides, GitHub research notes (pmoves.ai, doradura), membertel.com
- Telegram encryption criticism: ESET study via inview.org.uk; loginsoft.com;
  socialagechecker.net; thehackernews.com; businesscloud.co.uk
- Telegram moderation: iphoneincanada.ca (Aug 2026 App Store delisting);
  walaw.press (CSAM coverage)
- Telegram scale: telegra.ph growth guide; grabon.in stats (sourced to
  Financial Times/Telegram/Tgstat — could not verify primary)
- OnlyFans/Fansly/Fanvue/Passes fees: techbullion.com, mexc.com,
  creatorverdict.com (ToS quotes checked July 2026), onlytraffic.com,
  supercreator.app, vocal.media, whisper.fans
- OnlyFans referral class action (Aug 2026): ppc.land
- SkipTheGames pattern: tplearn/quantumcourse mirrors, medium.com
  (Aug 2026 pieces), bahaynakpil.org review
- Tinder pricing: lustfind.com, subger.com, vidaselect.com, swipestats.io,
  wppluginsify.com, thedatingring.ca
- Facebook Marketplace: supdropshipping.com, shafaataliedu.blog,
  inspiretothrive.com, underpriced.app, infoxlog.com, WashU infosec guide
- Etsy fees: craftybase.com, ecommerceceo.com, crosslist.com, sellermind
  (GitHub), Medium seller pieces (Sep 2026)
- Gumroad fees: checkoutpage.com, insightraider.com, aifind.info,
  medium.com seller guides

---

*Workstream 3 of 13. Doc only — no code, no commits. Companion docs:
`docs/CREATOR_PLATFORM.md` (base), `docs/PLAIGROUND_CRUSHON_KFX2.md`,
`docs/PLAIGROUND_GIANTS_KFX2.md`.*
