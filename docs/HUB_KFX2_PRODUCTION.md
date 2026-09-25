# HUB KFX² — Competitor Teardown, Synthesis & Production Plan

**Workstream:** KFX² 5/13 — Hub social platform
**Date:** 2026-09-21
**Status:** Planning document. No code. No commits. No release.
**Author:** Rex (subagent), for Chauncey

**What this document is:** a competitor teardown of the four platforms the Hub
absorbs (Facebook, X, Reddit, TikTok), the KFX² synthesis that turns their
strengths and compromises into Hub structure, and the sequenced production
plan with gates and hard prohibitions.

**Source-quality convention used throughout:**

- *Publicly described* = the platform itself says this (help centers, engineering blogs).
- *Secondary reporting* = press/analyst coverage; attributed, not independently audited.
- **Could not verify** = looked, could not confirm from a reliable current source.
  Facts are never invented to fill these gaps.

---

## Part A — Competitor teardown

### A1. Facebook

**Signature strengths**

- The durable real-world social graph: profiles, friends/family, Pages, Events.
- **Groups** are Facebook's living core. Secondary reporting widely cites
  ~1.8B monthly Groups users and ~70M admins/moderators; treat as secondary
  reporting, not an audited figure. Groups deliver the highest organic reach
  left on the platform — marketing sources claim group posts reach a large
  share of members versus ~1–2% Page reach. (Secondary reporting; exact reach
  multipliers vary by source — **could not verify** a single reliable number.)
- **Marketplace**: massive local classifieds surface; 2B monthly users cited in
  secondary marketing sources (**could not verify** precisely). Zero listing
  fees; monetization is via adjacent ads, not the transaction.
- Events, Messenger, and Reels round out a full-stack social OS for the 35+
  demographic with real purchasing power.

**Features & UX**

- Profile/timeline, friends, Pages, Groups (public/private/secret), Events,
  Marketplace, Watch/Reels, Stories, Messenger, dating, fundraisers.
- Feed is the default surface; Groups and Marketplace are parallel surfaces
  with their own discovery.

**Feed/ranking mechanics (publicly described)**

- Meta's public explanation of Feed ranking: **inventory → signals →
  predictions → ranking score**. Inventory is candidate posts from
  friends/followed Pages/Groups/joined content; signals include who posted,
  relationship history, content type, recency, and engagement patterns;
  predictions estimate likelihood of meaningful interaction; posts are scored
  and ordered.
- Since 2018 Meta has publicly weighted "meaningful social interactions"
  (comments, shares, back-and-forth conversation) above passive consumption.
  Exact current signal weights are **not published — could not verify**.

**Creator monetization**

- In-stream ads, Reels bonuses (historical programs), Stars (fan tipping),
  subscriptions, branded content. Eligibility thresholds and payout rates
  change frequently; current exact terms **could not verify reliably**.
- For Pages/creators the structural complaint is consistent across secondary
  sources: organic reach decayed as the feed became pay-to-play.

**Moderation model**

- Centralized: very large human review workforce plus automated systems,
  platform-wide Community Standards, plus the external Oversight Board for
  appeals on select cases.
- Secondary criticism is consistent: opacity of decisions, inconsistent
  enforcement at scale, and appeals that feel like shouting into a void.

**What users love / hate (secondary reporting)**

- Love: keeping up with real people, Groups that actually answer questions,
  Marketplace deals, Events, "everyone I know is here."
- Hate: the ad load and a Reuters-investigated deluge of fraudulent ads;
  algorithmic feed hiding friends' posts; privacy/surveillance unease;
  scams and spam in Groups and Marketplace; the sense that Pages must pay
  to be seen.

**Could not verify:** current exact MAU; current Groups reach multipliers;
current creator payout terms; whether any specific moderation headcount
figures from press are current.

---

### A2. X

**Signature strengths**

- Real-time public conversation: breaking news, live commentary, and the
  follow graph as an interest graph. Still the fastest surface on the
  internet for "what is happening right now."
- The **For You / Following** dual feed: algorithmic discovery plus a
  chronological escape hatch (a pattern worth stealing outright).
- Video, Spaces (live audio), long-form posts, and Community Notes.

**Features & UX**

- Posts, replies, reposts, quotes, likes, bookmarks, DMs, Lists, Spaces,
  Communities, Premium tiers, Grok AI tab in bottom navigation.
- **Custom Timelines (early access, April 2026, per secondary reporting):**
  75+ selectable topics, pin topic timelines to the home surface,
  personalization powered by Grok; initially reported as Premium/iOS-limited.
- The onboarding pattern Chauncey flagged: "Explore your interests" →
  topic tabs (Software, Crime, Digital Art, Biotech, Robotics…) → "See
  topics that interest you" → "Add Timelines." The user does manual setup
  labor against an empty state. This is the exact labor the Hub reverses.

**Feed/ranking mechanics (publicly described)**

- X publicly describes For You as drawing from followed **and** unfollowed
  accounts, ranked on predicted engagement: replies, reposts, likes, dwell
  time, and negative feedback signals.
- Historical open-source/commentary-era signal weights circulate online but
  are unstable and **not current constants — could not verify** present
  weights. Treat any "X weights replies 27×" style claim as stale.
- Secondary reporting (Nov 2025): even the Following feed became
  Grok-ranked rather than purely chronological — worth noting as the
  industry's direction of travel, and exactly what the Hub will not copy
  blindly.

**Creator monetization**

- Ad revenue sharing and subscriptions exist; Premium tiers reported at
  ~$8/$40 levels in secondary coverage (could not verify current pricing —
  it changes). Eligibility and payout terms vary across sources and change
  often; exact current requirements **could not verify reliably**.

**Moderation model**

- Community Notes: crowdsourced context appended to posts, with a
  bridging-based ranking (notes rated helpful across viewpoints surface).
  Genuinely novel; also genuinely slow on fast-moving harm.
- Central trust & safety staffing was deeply cut; secondary reporting
  describes inconsistent enforcement and advertiser-safety volatility.

**What users love / hate (secondary reporting)**

- Love: speed, direct access to notable people, real-time sports/news,
  Community Notes when they work, the For You discovery hit rate.
- Hate: bots and porn-bots in replies, ad load and mislabeled ads,
  algorithmic ragebait — a peer-reviewed study reported in secondary press
  found the algorithm systematically amplifies outrage content — verification
  confusion, the API paywall that killed third-party clients, and power-user
  drift to alternatives.

**Could not verify:** current ranking weights; current Premium pricing and
creator payout terms; Custom Timelines' current availability beyond the
April 2026 early-access reports.

---

### A3. Reddit

**Signature strengths**

- Topic-based communities with real self-governance: 100K+ active
  communities cited in Reddit's own public materials; ~108M daily actives
  reported early 2025 (secondary reporting of company statements).
- Nested threaded discussion + up/down voting + multiple sort modes
  (Hot/New/Top/Rising/Controversial). Still the best long-form Q&A and
  deep-dive discussion UX on the internet.
- Pseudonymous identity done right: reputation via karma and history,
  not real names.

**Features & UX**

- Subreddits with their own rules, flair, wikis, AMAs; multireddits;
  r/all and r/popular as cross-community discovery; chat, live threads.

**Feed/ranking mechanics (publicly described)**

- The classic "Hot" ranking combined vote score with time decay (the
  historically published formula family — Wilson-score lower bound for
  "Best" sorting). Reddit's current production ranking details are
  **not published — could not verify** the present formula.
- Known structural weakness from secondary commentary: early comments
  accumulate visibility before slower, higher-quality answers arrive —
  speed beats quality by construction.

**Creator monetization**

- Contributor Program: eligible users convert earned Gold into cash
  payouts. Announced 2023; exact current thresholds and payout rates
  **could not verify** (available reporting is older or inconsistent).
- Historically Reddit monetized almost entirely via ads; the IPO (2024)
  intensified monetization pressure, including data-licensing deals.

**Moderation model**

- Distributed: **volunteer moderators** enforce subreddit-specific rules;
  Reddit admins hold platform-wide policy. Secondary analysis credits
  millions of volunteers with keeping discussion human.
- The bargain's cost: quality depends on unpaid labor; mod teams can be
  inconsistent or insular; admin/mod relations are adversarial by
  tradition.

**What users love / hate (secondary reporting)**

- Love: finding *their* people, genuine expertise, the voting system
  surfacing real answers, old threads as evergreen knowledge.
- Hate: the 2023 API pricing protest — third-party apps (Apollo et al.)
  priced out of existence, thousands of subreddits going dark in protest,
  and lasting resentment among the most engaged users; mod power trips;
  repost farms; the official app's UX; data-licensing unease after the IPO.

**Could not verify:** current ranking formula; current Contributor Program
thresholds/payouts; current DAU.

---

### A4. TikTok

**Signature strengths**

- The content-first interest graph: discovery that does not require a
  follower relationship. A zero-follower video can reach millions on merit
  signals alone — the most imitated discovery engine in tech.
- Full-screen short video UX with near-zero friction; the fastest
  interest-learning loop ever shipped.

**Features & UX**

- For You feed, Following feed, search-as-discovery, Duet/Stitch,
  LIVE, Stories, TikTok Shop embedded in-feed.

**Feed/ranking mechanics (publicly described)**

- TikTok's public "how For You works" explanation names three factor
  families: **user interactions** (likes, shares, saves, comments,
  follows, hides, "not interested"), **video information** (captions,
  sounds, hashtags, effects), and **device/account settings** (language,
  country, device type — given less weight).
- Commonly described signals across secondary sources: watch completion,
  replays, shares, saves, comments, searches, skips/hides. TikTok has
  publicly stated follower count and prior viral performance are **not**
  direct recommendation factors — attribute cautiously; exact weighting
  is unpublished and **could not verify**.

**Creator monetization**

- Commonly reported: Creator Rewards, TikTok Shop/affiliate commissions,
  LIVE gifts, subscriptions, brand partnerships. Exact eligibility
  thresholds and payout figures **conflict across secondary sources —
  could not verify**; creator pay volatility is itself a widely reported
  complaint.
- Shop saturation of the For You feed is a widely reported user grievance.

**Moderation model**

- Increasingly automated-first with shrinking human review (secondary
  reporting on trust & safety layoffs); context errors and false
  positives are a consistent creator complaint; appeals are described
  as opaque.

**What users love / hate (secondary reporting)**

- Love: the algorithm "gets me" within an hour; discovering creators
  they'd never have found; low-follower virality; Shop convenience.
- Hate: addictiveness by design; moderation false positives and
  unexplained takedowns; Shop spam in the feed; creator earnings
  volatility; privacy and ownership-structure unease (US divestiture
  into a USDS joint venture was finalized January 2026 per legal
  reporting — noted for completeness, not load-bearing for this plan).

**Could not verify:** current ranking weights; current Creator Rewards
thresholds/payouts; current moderation staffing levels.

---

## Part B — KFX² synthesis: the Hub form

KFX²: **absorb** the outside pattern (strengths *and* weaknesses) →
**reverse** the compromises → **improve** → return a form only LEVI's
local-first, deterministic, gated architecture can support.

### The four absorptions

**From Facebook — absorb:** persistent identity, the real-world social
graph, profiles, Groups, Events, the feed as a social home.
**Reverse:** the graph becomes an advertising profile. In the Hub the
social graph is member-owned, local-first, and portable — it can never
become ad inventory because there is no ad system for it to feed.
**Amplify into:** the only social graph that gets *more* valuable the
less it is surveilled — portable identity and content the member carries,
not a profile the platform rents back to them.

**From X — absorb:** real-time public conversation, the follow graph,
topic timelines, the dual For You / Following structure, and the
bottom-nav AI tab pattern.
**Reverse two things:** (1) engagement farming — the Hub does not reward
outrage because replies are cheap; ranking optimizes for the member's
declared intent and satisfaction, never for time trapped. (2) The
setup-heavy empty state — X's "Add Timelines" makes the user build the
interest graph by hand; **the Hub earns the interest graph from the
member's own local activity** and offers visible correction and control
instead of demanding setup labor.
**Amplify into:** LEVI as a first-class bottom-nav tab — but X's Grok is
a chatbot behind a tab while **LEVI is the bloodstream**: working across
feed, communities, discovery, and creation under permission gates.
*The nav tab is the front door; the intelligence is the house.*

**From Reddit — absorb:** self-governing communities, threaded depth,
voting, local norms, pseudonymous reputation.
**Reverse:** moderation opacity and factional pile-ons. The Hub keeps
community self-governance but makes moderation **recorded-reason**:
every action carries a visible reason, every decision is appealable,
and voting is tuned to reward bridging quality, not mob velocity.
Volunteer stewards get real tooling instead of being the unpaid
absorption layer for platform decisions.
**Amplify into:** communities whose norms are legible, portable, and
member-ratified — governance you can read, not weather you endure.

**From TikTok — absorb:** immediate interest learning, short-form video,
discovery that doesn't require followers.
**Reverse:** watch-time maximalism. The Hub's discovery optimizes for
what the member said they wanted — satisfaction and intent completion —
not for the longest possible session. No infinite scroll tuned against
you; the loop serves the member, and the member can see and tune the
recipe.
**Amplify into:** discovery with the recipe card on the table —
disclosed, tunable ranking the member controls, running on a local
interest graph no advertiser will ever see.

### The structural moat (why they can't follow)

Ad platforms need centralized behavioral collection to target ads and
optimize inventory. A private, device-local interest and social graph
removes the raw material their economics depend on. Copying the Hub
faithfully would require them to undermine their own revenue engine —
that is the moat, and it is structural, not feature-based.

### The uproar doctrine — positioning law (Chauncey, 2026-09-21)

"We offer what they do, what they don't, and do it even better, and for
fraction of fractions." The product slate matches every competitor
feature-for-feature PLUS what they don't offer, better built, at
radically lower prices — fraction of their fractions. Dollar-scale
entry, volume over margin. This is the positioning law for the Hub:
the teardown above is the feature checklist we match; the reversals are
the "what they don't" we add; the 12% stated digital cut against
Etsy's 10–20%+ fee stack and Gumroad's 10%+$0.50/30% is the pricing
proof. Nothing in this plan prices at giant scale — entry stays at
dollar scale and margin comes from volume.

### Marketplace — KFX² section

**Chauncey's directive (2026-09-21):** the platform has a **digital AND
physical marketplace**. We take a cut on **digital products created and
monetized on our platform**. House rate: the standing **12% platform cut
(PL-05 doctrine)** unless Chauncey sets otherwise. **Physical goods: we
facilitate; the cut question stays OPEN — gated on Chauncey. No number
is assumed here.**

**Absorb — three patterns:**

1. **Facebook Marketplace (physical goods, social-graph distribution):**
   strength is zero-friction local exchange distributed through the
   social graph — mutual friends as implicit trust, local pickup, no
   listing fees, enormous reach. Weaknesses: scams and fraud with thin
   buyer protection, ghosting/no-shows, zero transaction structure, and
   the whole surface exists to keep users inside an ad inventory.
2. **Etsy (maker storefronts):** strength is the maker storefront with
   search/discovery tuned for handmade and a review system that builds
   buyer trust. Weaknesses are the fee stack: secondary sources
   consistently report **$0.20 listing + 6.5% transaction (incl. shipping)
   + ~3% + $0.25 US payment processing + 12–15% Offsite Ads when
   triggered** — a typical 10–20%+ effective take sellers experience as
   fee creep — plus reseller/dropshipper dilution of the handmade
   promise and ad-driven visibility sellers must pay to keep.
3. **Gumroad (digital products):** strength is dead-simple digital
   publishing — upload, price, get a link, sell in minutes — plus
   merchant-of-record tax handling. Weaknesses: majority secondary
   reporting says **10% + $0.50 per direct sale** (regressive on cheap
   items: ~20% effective on a $5 product) and **30% on Discover
   marketplace sales** — one outlier source reports different figures
   (8.5% + $0.30 / Pro 3.5% + $0.30), marked **could not verify
   reliably** — plus winner-take-most discovery where third-party
   analysis attributes a median lifetime of ~28 sales per product and
   44% earning $0, so small creators pay the fee without getting the
   marketplace.

**Reverse:** fee stacking with surprise layers, ad-bought visibility,
trust deficits papered over with centralized policing, and discovery
that taxes the smallest sellers hardest.

**The Hub marketplace form:**

- **Digital goods — stated-cut economics:** one number, stated up
  front, no stacked layers: **12% house cut per PL-05 doctrine** unless
  Chauncey sets otherwise. No listing fees, no payment-processing
  surprise, no offsite-ad ambush fee, no tier that punishes success.
  Creator-partner economics: the cut is a partnership term, published
  and stable, not a dial the platform turns against sellers.
- **Physical goods — facilitated, cut OPEN:** the Hub provides the
  trust surface (social-graph proximity, mutual connections visible,
  recorded-reason dispute handling through the moderation model) and
  **does not assume any cut**. The economics question is **gated on
  Chauncey** — options he can pick later include zero-cut facilitation
  or a stated cut, but nothing is decided in this document.
- **Local-first fulfillment for digital:** products live in the
  member's vault; delivery doesn't require uploading inventory to a
  platform cloud. Portable storefronts: identity and reputation travel
  with the creator, not locked to the marketplace.
- **LEVI-assisted commerce:** listing creation, pricing sense-checks,
  and buyer/seller matching assistance run through LEVI under the same
  permission gates as everything else — the front door, not a
  surveillance funnel.
- **Why it's unreplicable:** competitors' marketplaces monetize through
  fee stacking, promoted placement, and behavioral data. A marketplace
  with no ads, no surveillance analytics, a single stated cut, and
  trust rooted in the member's own social graph would require them to
  dismantle the revenue machinery the marketplace exists to serve.

---

## Part C — Sequenced production plan

**Standing constraints (not milestones — law):**

- Hub remains bound to **127.0.0.1**. Any broader network exposure is
  gated on Chauncey.
- The **8-tab vs 12-tab map is OPEN** — never resolved unilaterally.
  Phase 0 produces the options; Chauncey settles it.
- Any customer release is gated on Chauncey.
- Hard nos: **no advertising model, no surveillance analytics, no
  external exposure without approval, no training on member data.**

### Phase 0 — Contracts & reconciliation

- Reconcile `docs/SOCIAL_PLATFORM_DESIGN.md` (useful architecture:
  disclosed ranking recipes, recorded-reason moderation, portable
  identity/content, no training on platform data) with the Hub product
  definition (Facebook × X × Reddit × TikTok). Its older framing is
  reference, not canon — nothing unresolved is treated as settled.
- Freeze the constraint set: local-first, deterministic, gated;
  no-ads / no-surveillance / 127.0.0.1.
- Produce the 8-vs-12 tab map as **explicit options with trade-offs**,
  unresolved, for Chauncey's decision.
- **Gate:** Chauncey approves the contracts and the constraint freeze
  before any build phase starts.

### Phase 1 — Local identity & portable social graph

- Member-owned identity, profiles, friend/follow relationships stored
  local-first; export/portability from day one.
- **Gate:** identity round-trips (create → export → import) verified
  locally before any feed work.

### Phase 2 — Feed & disclosed ranking

- Friend/group feed with **published, tunable ranking recipes** —
  the member sees what the feed optimizes for and can change it.
- **Gate:** ranking recipe disclosure is user-visible and adjustable;
  no hidden weights ship.

### Phase 3 — Wire (real-time) + LEVI front door

- Real-time public conversation surface with follow graph; keep the
  For You / Following dual structure — chronological path always
  available.
- LEVI bottom-nav tab ships as the front door; bloodstream integration
  (feed, discovery, creation assistance) follows in Phase 7 under
  permission gates.
- **Gate:** interest graph is **earned from local activity**, never
  demanded via setup labor; the X-style empty state does not ship.

### Phase 4 — Communities (threaded, voted, self-governed)

- Reddit-absorbed: threaded discussion, voting, community rules,
  volunteer stewardship with real tooling.
- Recorded-reason moderation + appeals from day one of this phase.
- **Gate:** every moderation action carries a visible reason and an
  appeal path before communities open.

### Phase 5 — Short video & discovery

- TikTok-absorbed: short-form video, follower-independent discovery,
  satisfaction/intent-optimized ranking — never watch-time maximalism.
- **Gate:** discovery recipe is disclosed and member-tunable; no
  engagement-farming signals in the ranking.

### Phase 6 — Marketplace

- **6a. Digital goods:** storefronts, local-first delivery from the
  member's vault, LEVI-assisted listing creation. Economics: the
  stated **12% house cut (PL-05)** unless Chauncey sets otherwise —
  single number, published, no stacked fees.
- **6b. Physical goods:** facilitation surface with social-graph trust
  and recorded-reason dispute handling. **The cut stays OPEN and gated
  on Chauncey — no number assumed, none implemented.**
- **Gate:** no fee logic ships for physical goods without Chauncey's
  explicit economics decision.

### Phase 7 — LEVI bloodstream

- LEVI woven across feed, communities, discovery, creation, and
  marketplace under permission gates. Tab is the front door;
  intelligence is the house.
- **Gate:** every cross-surface LEVI action requires the member's
  permission grant; no ambient data use.

### Phase 8 — Local-only verification & hardening

- Full test pass with the machine offline: every Hub surface works
  with no network. Deterministic behavior verified; no telemetry
  leaves the device.
- **Gate:** Chauncey (or his designee) witnesses the offline run.

### Phase 9 — Networking & release (DOUBLE-GATED)

- **Gate 1:** broader network exposure beyond 127.0.0.1 — Chauncey's
  explicit order required.
- **Gate 2:** any customer release — Chauncey's explicit order
  required, separate from Gate 1.

### Hard prohibitions

1. No advertising model — in any surface, including the marketplace.
2. No surveillance analytics — no behavioral collection beyond what
   the member's local features require, nothing leaves the device.
3. No training on member data — platform models never train on
   member content or activity.
4. No external exposure beyond 127.0.0.1 without Chauncey's order.
5. No customer release without Chauncey's order.
6. The 8-vs-12 tab map is never resolved unilaterally.
7. No invented numbers — fees, thresholds, weights, and dates are
   either sourced or labeled **could not verify**.
8. No physical-goods marketplace cut without Chauncey's economics
   decision.
9. Documentation only in this workstream — no code, no commits.

### Open questions for Chauncey (checkpoints, not blockers)

1. 8-tab vs 12-tab map — options in Phase 0, his call.
2. Physical-goods marketplace economics — his call, whenever.
3. Digital 12% cut — stands per PL-05 unless he sets otherwise.
4. Gate 1 / Gate 2 timing — his call, in that order.

---

## Appendix — key sources

Secondary sources preferred throughout; primary platform pages used for
orientation only where noted.

- Meta Feed ranking overview (primary, orientation):
  https://transparency.meta.com/features/explaining-ranking/fb-feed/
- Reuters — Meta fraudulent-ads investigation:
  https://www.reuters.com/investigations/meta-is-earning-fortune-deluge-fraudulent-ads-documents-show-2025-11-06/
- Engadget — X custom timelines:
  https://WWW.ENGADGET.COM/social-media/x-finally-adds-custom-timelines-103130966.html
- MacRumors — X custom timelines for Premium:
  https://www.macrumors.com/2026/04/22/x-custom-timelines-for-premium-users/
- SocialMediaToday — X Grok in-stream integration:
  https://www.socialmediatoday.com/news/x-experiments-new-grok-ai-access-buttons-in-stream/700908/
- 404 Media — X ragebait algorithm study:
  https://www.404media.co/xs-algorithm-feeds-off-ragebait-and-impacts-democrats-more-study-finds/
- TechPolicy.Press — volunteer moderation:
  https://techpolicy.press/millions-of-volunteers-are-keeping-the-internet-human-for-now
- Android Authority — Reddit Contributor Program:
  https://www.androidauthority.com/reddit-contributor-program-announced-3368236/
- AdNews — TikTok recommendation explanation:
  https://www.adnews.com.au/news/tiktok-reveals-details-and-challenges-of-its-recommendation-algorithm
- WebTonic — TikTok algorithm overview:
  https://www.webtonic.io/blog/tiktok-algorithm
- Hootsuite — Facebook Groups for business (2026):
  http://blog.hootsuite.com/facebook-groups-business/?hootPostID=de42572e1578d3e50aab5a97123c9064
- BroadbandSearch — social media stats:
  https://www.broadbandsearch.net/blog/social-media-facts-statistics?msID=3b5cd099-c674-4024-b8c5-2f6711a41840
- Morning Brew — Reddit API revolt:
  https://www.morningbrew.com/stories/2023/06/11/the-revolt-of-the-redditors
- arXiv — Reddit client-shutdown user migration study:
  https://arxiv.org/pdf/2503.19513
- eDesk — Etsy seller fees 2026:
  https://www.edesk.com/blog/etsy-seller-fees/
- Sellbery — Etsy fees guide 2026:
  https://sellbery.com/blog/a-beginners-guide-to-etsy-seller-fees/
- Checkout Page — Gumroad fees 2026:
  https://checkoutpage.com/blog/gumroad-fees?srsltid=AfmBOornS1AA4wkY9Axu8s-RGUsdYOb_0DEzSk24QQUEHhXxIFHJg4mR
- NanoCart — Gumroad fees explained 2026:
  https://nanocart.app/posts/gumroad-fees-explained-2026/

*All research observed 2026-09-21. Figures cited as secondary reporting
are not independently audited. Anything marked "could not verify" was
checked and left blank on purpose.*
