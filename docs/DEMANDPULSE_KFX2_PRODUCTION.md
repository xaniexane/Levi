# DemandPulse KFX² + Production Plan — absorb, reverse, improve, return unreplicable

Date: 2026-09-21. Product: **DemandPulse** — trend/demand sensing engine
(ingestion + processing + heatmap + workflows, stdlib-only, local), with a
competition module (competitor tracking + upgrade recommender).
Price anchor: **$6/month** standalone customer product (Chauncey's word,
2026-09-21; the anchor lives in `core/levi/demand/competition.py` as
`CURRENT_PRICE_MONTHLY`).

KFX² frame (Chauncey's law): absorb the outside pattern — STRENGTHS as
well as weaknesses — → reverse it → improve it → return a version only we
could build. Unreplicable means: our architecture (local-first,
deterministic, gated) makes their cost structures and compromises
unnecessary. See `PLAIGROUND_CRUSHON_KFX2.md` and the corrected
`PLAIGROUND_GIANTS_KFX2.md` (strengths amplified, not only weaknesses
reversed).

This is a DOCS-ONLY artifact. No code ships from it, nothing commits from
it, and the plan ends at the release gate — never past it (see §HARD NOS).

---

## 1. Competitor teardown — features, pricing, UX, sentiment

Researched 2026-09-21 via public secondary sources (comparison roundups,
reputation-management guides, vendor blog pages). Pricing and feature
details are NOT verified against the vendors' own pricing pages — mark
accordingly. Nothing below is invented; where the sources disagreed or
went stale, it says so.

### 1a. Google Alerts — the free incumbent

**What it is.** Free saved-search monitor launched 2003. Enter keywords →
Google reruns the query against its web index → delivers matches by email
or RSS. Cadence: "as it happens", daily, weekly. Source filter: Everything,
News, Blogs, Video, Discussions, Books. Volume knob: "Only the best
results" vs "Everything".

**Pricing.** Free. No paid tier exists. No official API (Google has never
shipped one; third parties note the backend likely runs on spare/lower-tier
capacity with no monetization to justify it).

**Data sources.** Google's own web index only. Reports: picks up Reddit but
NOT Twitter/X, Facebook, Instagram, or other social networks. Misses
mentions from smaller sites frequently.

**Strengths (what users love).** Simplicity — a saved search in seconds.
Free forever. Directly from Google's index. RSS option (no account lock-in
for delivery). Useful for tracking your own published quotes/content and
competitor news headlines.

**Weaknesses (what users hate).** Reliability: users on Google's own help
forums and press (Computerworld, 2013; reputation-management guides,
2024–2025) report it silently MISSING mentions that a manual search finds —
one publisher's open letter documented alert volume down ~80% with worse
results. No social coverage. No analytics (no volume/sentiment/demographic
trend). One search per alert — can't combine terms; many competitors means
an inbox full of alert emails. Single email recipient only; no team sharing.
No archive — delete the email and the record is gone. "As it happens" mode
floods the inbox; "best results" mode hides things.

**Verdict.** Beloved surface, decaying engine. Free is the moat; noise and
silence are the tax. Could not verify: current 2026 alert reliability (no
recent primary measurement found); whether Google plans to deprecate it.

### 1b. Mention / Brand24 — the social-listening tier

**What they are.** Keyword-based brand/social monitoring: track terms across
social, news, blogs, forums, reviews; dashboards, sentiment, reports,
competitor tracking, alert notifications. The SMB/brand tier of social
listening (below Brandwatch/Meltwater/Talkwalker enterprise).

**Mention — pricing (per secondary sources, not vendor-verified).**
Mention discontinued its Solo ($49/mo), Pro ($99/mo), and Pro Plus
($179/mo) tiers in **July 2025** after its acquisition by Agorapulse; the
only plan for new customers is the **Company plan at $599/month,
annual-only**. In **January 2026** Mention retired its Publish and Respond
features — it is now monitoring + analytics only; publishing/engagement
requires a separate subscription.

**Mention — features.** Complex Boolean query control (power users love
this). Near-instant alert speed. Unlimited users on Company. Scheduled
reporting. Covers all major platforms + web. NO AI synthesis layer (you
read and interpret everything manually). No historical data before account
creation. Caps: 50,000 mentions/month, 5 alerts on Company; collection
STOPS at the cap (no overage — you go blind). Misses Medium, Quora, Twitch,
podcasts, newsletters (per comparison tests). No audio transcription or
on-screen text detection for TikTok/Reels — caption-and-hashtag monitoring
only.

**Brand24 — pricing (per secondary sources, not vendor-verified; sources
disagree).** Public ladder reported as: Individual ~$199–$249/mo (monthly)
or $149–$199/mo (annual), Team ~$299–$349, Pro ~$399–$499, Business
~$599–$699, Enterprise from ~$999–$1,499. **Mark as volatile — not verified
against brand24.com.** 14-day free trial reported.

**Brand24 — features.** 3–25 keywords, 2,000–100,000 mentions/month by
tier. Update cadence 12h (Individual) → hourly (Team) → realtime (Pro+).
AI layer: AI Sentiment Analysis (all tiers), AI Event Detection, AI Brand
Assistant, AI Insights, AI Topics (Pro/Business only — the AI layer is
tier-gated). 25+ sources including podcasts, newsletters, Twitch, Medium,
Quora, reviews. 30-day historical margin from project creation. Daily/weekly
automated email reports; customizable reports on higher tiers. Lightning
Search (Pro+). Influencer analysis. iOS/Android app, Slack/Teams
integrations.

**Sentiment.** Brand24: the SMB favorite — praised for AI-assisted
interpretation, broader source coverage, self-serve pricing; hated for
cost-vs-volume thinness and ~5-minute alert lag. Mention: respected for
Boolean power and speed; the 2025 price jump ($49 entry → $599-only) reads
as a forced upsell in review discourse. Both: "expensive for small
businesses" is the universal complaint; neither hears video content
(TikTok/Reels audio is invisible to both).

**Verdict.** Real listening costs $200–$600/mo and the AI interpretation
layer sits behind the Pro paywall. Their metering (mentions/month caps,
keyword caps) is their cost structure talking — cloud collection, cloud ML,
cloud margins. Could not verify: exact 2026 Brand24 tier prices and
inclusion lists; Mention's current cap policy beyond the comparisons.

### 1c. Exploding Topics — the trend-discovery reference

**What it is.** Trend intelligence: ML over billions of searches,
conversations, and web mentions (Google, social, forums) + human-expert
refinement, surfacing trends claimed 6–12+ months before mainstream
adoption. Database reported at 1.1M+ trends. Growth classifications
(regular, peaked, exploding, consistent). Meta trends. "My Projects"
folders for tracked topics. Weekly expert-curated reports. Trending
Products tab with Amazon Marketplace data layered in (best-seller rank,
revenue, sales, price, reviews). Trend Search (search any term, region,
"people also search for"). Channel breakdown (which social networks a topic
explodes on). CSV export (Investor+). API access (Business).

**Pricing (per vendor's own blog + secondary sources; "billed annually"
noted by the vendor).** Freemium — free tier with limited historical data.
Pro: **Entrepreneur $39/mo**, **Investor $99/mo**, **Business $249/mo**.
7-day all-Pro trial; some sources cite a $1 14-day trial. Export and API
are paywalled to the upper tiers.

**Data sources.** Online forums, blogs, news outlets, social platforms
(YouTube, Spotify, Reddit, TikTok cited), Google search signals, Amazon
Marketplace data.

**Strengths (what users love).** The early-spotting mechanic is genuinely
differentiated — trend-before-mainstream is the whole pitch, and the
weekly expert reports + product-marketplace data layer make it actionable
for e-commerce/startup users. Clean visualizations of growth trajectory.

**Weaknesses (what users hate).** Restrictive free tier (teaser database).
Data updates WEEKLY, not realtime. Basic search vs dedicated SEO
platforms. Exports locked to upper tiers. Annual-billing pressure. No
customization for specific industries on lower tiers. Discovery-only: it
finds trends, it doesn't tell you what to DO about them (no gap analysis,
no competitive move, no action loop).

**Verdict.** Best-in-class at seeing what's rising; stops at seeing. The
trend is the product — the response is your problem. Could not verify:
the "12+ months early" claim (marketing, no independent evaluation found);
current free-tier exact limits.

### Honest-limit ledger (whole teardown)

- All pricing marked above comes from secondary comparison pages crawled
  between 2 hours and ~7 months ago — not from live vendor pricing pages.
  Treat every dollar figure as approximate and re-verify before any
  competitive claim in customer-facing copy.
- No primary user-review dataset (G2/Capterra/Trustpilot) was pulled;
  sentiment is synthesized from comparison/review-guide prose.
- Google Alerts' current reliability: no 2026 primary measurement found.
- Exploding Topics' lead-time claims: vendor marketing only.

---

## 2. KFX² — what we take, reverse, amplify

### 2a. ABSORB — their patterns worth taking

1. **Exploding Topics' growth classification.** Regular / peaked /
   exploding / consistent — a trend's SHAPE matters more than its size.
   DemandPulse already clusters signals and scores cards; the absorbed
   pattern is a shape classifier over cluster velocity (breakout velocity
   across scans), stored as INFERENCE on the cluster, feeding the feed's
   tiering and the breakout watch alert (workflow 9).
2. **Exploding Topics' Meta trends.** Roll clusters up one level: named
   meta-trends that own N clusters. DemandPulse's INFERENCE clustering is
   the substrate; the absorbed pattern is the two-level digest view
   (meta-trend → clusters → OBSERVED signals).
3. **Brand24's automated digests.** Daily/weekly briefing of mentions, top
   movers, sentiment shifts. DemandPulse already has briefing alerts
   (workflows 1, 3) and the SI-native feed digests — the absorbed pattern
   is the RENDER: a formatted briefing document in the file outbox with
   tiered sections (exploding / rising / watch / quiet), ready to be
   emailed later but never sent without config.
4. **Brand24's influencer/source breadth.** 25+ sources incl. podcasts and
   newsletters. DemandPulse's ingestion layer already carries HN, Reddit,
   GitHub, arXiv, job feeds, Census economics. The absorbed pattern is
   the coverage checklist: keep expanding polite keyless public sources
   (podcast RSS, newsletter archives) with the same failure contract
   (dead source → empty list, never an exception).
5. **Mention's Boolean-ish precision.** Complex query control is what
   power users actually love. DemandPulse's honest version: explicit
   keyword sets with exclusion terms per watch alert, logged in the alert
   definition so the filter is auditable — precision without a query
   language nobody can read back.
6. **Google Alerts' simplicity.** Saved search in seconds. The absorbed
   pattern is the zero-config path: one command, a keyword set, watch
   alerts installed, digest lands in the file outbox. No account, no
   dashboard onboarding, no funnel.

### 2b. REVERSE — their weaknesses, flipped into our strengths

| Their failure | Our reversal |
|---|---|
| Google Alerts' silent misses — mentions it never reported, no archive | Every scan is FILED: `~/.levi/demand/` scans + JSONL digests. The archive is the product; silence is auditable, never assumed |
| Google Alerts' spam mode — "as it happens" inbox flooding | Dedup by law (same item never fires twice), quiet hours hold-and-flush, briefing cadences — volume is engineered down, not up |
| Keyword-only matching (all of them at base tier) | Signal Correlation Engine (workflow 8): clusters are INFERENCE over multi-source signals; a breakout is a multi-source cluster, not a keyword hit |
| Opaque sentiment/ML grading (Brand24's black box) | The label law: OBSERVED (fetched text) / INFERENCE (clustering) / HYPOTHESIS (scored opportunities). Nothing is graded without its basis note; items that can't prove a basis are QUARANTINED, never published |
| Enterprise pricing ($199–$599/mo listening; $39–$249/mo trends) with mentions/month metering | $6/mo works because our physics has no marginal message cost: stdlib-only, local, polite public reads. Their metering exists to pay for THEIR cloud; we don't have that cloud, so we don't have that meter |
| Mention's cap-blindness (collection STOPS at 50k, no overage) | No mention metering exists in the architecture — scans degrade gracefully to empty lists on failure, never to a paywall on volume |
| Exploding Topics' discovery-only dead end (finds trends, no response) | The loop closes: trend → competitive gap map → upgrade proposal, all inside one module, all labeled, all gated on the founder's word |

### 2c. AMPLIFY — their strengths, made unreplicable

The giants-doc correction applies here too: the signature runs on their
strengths, amplified, not only on their weaknesses reversed.

1. **Exploding Topics' trend-spotting → local-first demand sensing with
   the competition module's upgrade recommender.** They spot the trend;
   we spot the trend, map the competitive gap against it from what our
   code ACTUALLY does (competition.py's honest feature column — never
   invented), and emit a labeled upgrade proposal. Their stack is
   monitoring-only; it cannot cross from sensing to recommending without
   rebuilding its architecture. UNREPLICABLE because the
   sense→gap→propose chain is one deterministic local module with the
   founder's-word gate in the middle — they would have to become an
   advisory engine, not a dashboard.
2. **Google Alerts' simplicity → zero-config local alerts with no
   account.** Their simplicity still costs an email address handed to a
   cloud and alerts that die if you delete the email. Ours: one command,
   keyword set, watches installed, digests in the file outbox — nothing
   leaves the machine, nothing to leak, nothing to deprecate. Their
   backend runs on spare capacity and could vanish; ours is files.
   UNREPLICABLE because their business model forbids the no-account,
   no-cloud posture — simplicity that isn't a funnel.
3. **Brand24's AI event detection → deterministic event detection with
   receipts.** Their AI layer is tier-gated (Pro/Business) because ML
   inference costs them money per run. Ours is the breakout detector
   (workflow 9) + correlation engine (workflow 8): deterministic,
   label-carrying, free to run every tick for every user. No tier wall
   because no marginal cost. UNREPLICABLE because any cloud competitor
   that drops the tier wall eats its own margin — our physics made the
   wall unnecessary.
4. **The label law itself.** Google Alerts drowns you in ungraded noise;
   Brand24 grades with opaque ML. Nobody labels every item
   OBSERVED/INFERENCE/HYPOTHESIS and refuses to publish what can't prove
   a basis. The quarantine list is the honesty feature. UNREPLICABLE
   because admitting uncertainty costs a dashboard its "insight" theater
   — their UX is built on certainty theater; ours is built on the label.
5. **Advisory-only as architecture.** All three competitors stop at the
   screen; none touches action. We stop EARLIER than the screen for
   anything consequential: the authority engine classifies actions and
   refuses what it can't do, proposals are HYPOTHESIS, applying anything
   needs the founder's explicit word, and the module says so on every
   proposal. Plan→Preview→Permission→Execute→Verify→Receipt is the
   bloodstream. They can't replicate the gate without becoming a
   different product.

**Return to sender:** everything they monetize through scarcity — AI
interpretation, export, API access, mention volume, realtime updates —
we ship as physics. Our physics has no marginal cost, so it has no
scarcity, so it has no tiers. The $6 price is a product decision, not a
cost recovery — and that is the part none of them can follow us into.

### Positioning — the uproar doctrine (Chauncey, 2026-09-21)

Chauncey's positioning law: we offer what they do, what they don't, and
do it even better, for a fraction of their fractions. The slate matches
every competitor feature-for-feature, adds what they lack, better built,
at radically lower prices — dollar-scale entry, volume over margin.

**Competitor features → our parity.** We match the category's table
stakes one-for-one: Exploding Topics' growth-shape classification
(regular / peaked / exploding / consistent) computed over cluster
velocity; their meta-trend roll-ups; Brand24's automated daily/weekly
briefings and broad source coverage; Mention's Boolean-grade precision
via auditable include/exclude keyword sets per watch alert; and Google
Alerts' zero-config saved-search simplicity — one command in, watch
alerts installed, digest in the file outbox. Nothing the competitor
dashboards do that a demand-sensing buyer needs is missing.

**Competitor gaps → our exclusives.** What they don't offer: the label
law — every item graded OBSERVED / INFERENCE / HYPOTHESIS with a basis
note, and whatever can't prove a basis is QUARANTINED, never published;
the closed loop — trend → competitive gap map → labeled upgrade proposal
in one module, where Exploding Topics stops at discovery and charges
extra for the response; the archive — every scan filed and auditable,
against Google Alerts' silent misses; advisory-only architecture with
the founder's-word gate in the middle; and zero metering — no
mention/month caps, no tier-gated AI layer, no "collection STOPS at
50k" cliff.

**Our price as a fraction of theirs.** Our anchor is **$6/month**
(Chauncey's word, 2026-09-21). Against Mention's $599/month Company plan
(per secondary sources, not vendor-verified) that's roughly one
hundredth; against Brand24's reported $199–$699/month ladder (marked
volatile, not verified) it's a fraction of even the entry tier; against
Exploding Topics' $39/$99/$249/month tiers (per vendor's own blog +
secondary sources) it's roughly one-sixth to one-fortieth. Google
Alerts is free — we don't undercut it on price; we beat it on
reliability, analytics, and an archive that exists. Every competitor
dollar figure here carries §1's honest-limit ledger: re-verify against
vendor pages before any customer-facing competitive claim.

---

## 3. PRODUCTION-PHASE PLAN — sequenced, milestone-gated, ending at the gate

**Standing state (already built, tested, committed local):**
ingestion (keyless public sources, failure contract), processing
(cluster/label/score), scoring (five-factor ScoreCards with basis notes),
alerts (threshold/briefing/watch/reminder, dedup, quiet hours,
console+file outbox; push/email declared-but-not-configured), the 10
workflows, the SI-native feed (rank/tier/dedupe/quarantine), the
competition module (competitor tracking + upgrade recommender), the
authority engine (action classification + refusal). CLI: `levi demand`.

The production phase is HARDEN → ABSORB → PACKAGE → GATE. Docs only —
this section authorizes no code, no commits, no release.

### Phase P1 — Harden the sensing skin (reversible, internal)

- **P1.1 Ingestion health ledger.** Every fetcher already fails to an
  empty list; production adds a per-source health record (last ok,
  last fail, fail streak) in the scan file so a dead source is VISIBLE,
  not silent. Milestone: a scan file whose health section names every
  source and its last-seen-ok timestamp.
- **P1.2 Polite-reads audit.** One request per page per run, proper
  User-Agent, no retries — re-verify per source against the actual
  current robots/TOS posture of the public endpoints (Reddit search.json,
  Remotive, Arbeitnow, Census ACS, HN/ArXiv/GitHub). Drop or replace any
  source that no longer permits polite reads. Milestone: signed-off source
  list with per-source permit note, dated.
- **P1.3 Alert precision pass.** Tune the breakout threshold (workflow 9)
  and high-score bar (workflow 4, composite ≥ 75) against real scan
  history: count false-positive firings per week, adjust, re-measure.
  Milestone: a precision note — firings/week before and after, method
  recorded.

### Phase P2 — Absorb the KFX² pattern (reversible, internal)

- **P2.1 Growth-shape classification.** Classify clusters regular /
  peaked / exploding / consistent from velocity across scans (their
  pattern #1, our INFERENCE label). Milestone: cluster records carry a
  shape field with basis (which scans, which counts).
- **P2.2 Meta-trend roll-up.** Two-level digest: meta-trend → clusters →
  OBSERVED signals (their pattern #2). Milestone: digest file contains a
  meta-trend section naming its member clusters.
- **P2.3 Briefing renderer.** Formatted briefing document in the file
  outbox — tiered sections (exploding / rising / watch / quiet),
  quarantine appendix, label legend (their pattern #3). Email-TEMPLATE
  shaped but file-only: the renderer produces the body that email WOULD
  send, and stops there. Milestone: one rendered briefing from a real
  scan, reviewed for invented claims (zero allowed).
- **P2.4 Zero-config quickstart.** One command: keyword set in, watch
  alerts installed, first digest out (their pattern #6). Milestone: a
  cold-start run documented step by step, timed.
- **P2.5 Auditable keyword filters.** Per-watch keyword sets with
  exclusion terms, logged in the alert definition (their pattern #5).
  Milestone: an alert definition file showing include/exclude sets and
  firing history.
- **P2.6 Coverage checklist pass.** Evaluate polite keyless additions
  (podcast RSS, newsletter archives) against the P1.2 audit rules
  (their pattern #4). Milestone: checklist with add/skip decisions and
  reasons.

### Phase P3 — Competition module as the closer

- **P3.1 Honest competitor seeds.** Seed Google Alerts, Mention/Brand24,
  Exploding Topics into the competition module with ONLY the facts in
  this teardown — each marked OBSERVED + source + date + confidence,
  anything uncertain `verified: false`. (The module already requires
  this; this doc is the seed source.)
- **P3.2 Gap-map refresh.** Re-run the feature-gap map with the absorbed
  P2 features in DemandPulse's honest column (derived from code only).
  Milestone: gap table where every DemandPulse cell cites the module
  that implements it.
- **P3.3 Reprice reasoning.** The module already reasons from the $6/mo
  anchor — record the reasoning: which competitor tiers we undercut, why
  the physics allows it, what we deliberately don't match (e.g. realtime
  social firehose — honest scope boundary). Milestone: one-page pricing
  rationale, no invented competitor prices (cite this doc's ranges with
  the verification caveat).

### Phase P4 — Package (stops at the gate)

- **P4.1 Release bundle.** A tarball + setup script shaped like the
  existing Termux toolchain pattern: stdlib-only, no dependencies, data
  under `~/.levi/demandpulse/`. Milestone: clean-HOME install test,
  status/scan/digest all OK.
- **P4.2 Customer copy.** One-page product sheet: what it senses, what
  the labels mean, the $6/mo anchor, honest limits (no social firehose,
  weekly-vs-realtime cadences per source, push/email "not configured"
  until the owner sets them up). No invented claims; every capability
  sentence must cite a module.
- **P4.3 GATE REVIEW.** Chauncey reviews P1–P4 artifacts. Nothing below
  this line moves without his explicit per-action word.

### What is GATED on Chauncey (nothing moves without him)

- **Payments:** the $6/mo price needs a destination — Stripe/payment
  link, account, terms. (Standing boundary from the 2026-09-21 blanket
  approval: publication hold stands; per-action specifics required:
  destination, scope, account, copy, media.)
- **Entitlements:** how a paying customer is recognized (key, account,
  license file) — design exists nowhere yet; needs his word.
- **Customer delivery/release:** any listing, installer, or handoff of
  the bundle to a real customer. The plan ENDS at the gate review.
- **Push/email channels:** alerts.py declares them "not configured" by
  design — a device target / mail provider needs his setup word.
- **Any push of the repo:** standing local-only law; a push needs his
  explicit order + fresh transient token.

### HARD NOS (law, not caution)

- NO payment, entitlement, listing, release, installation, or customer
  delivery is authorized by this plan — console/file outbox only.
- NO push and NO email until configured — the engine must never pretend
  a notification reached a device it didn't.
- NO code and NO commits from this doc — docs only; implementation is a
  separate workstream with its own authorization.
- NO invented competitor facts in customer copy — every price and feature
  claim carries the verification caveat from §1 until re-verified
  against vendor pages.
- NO offensive use of the sensing skin — reads are polite public feeds
  only; the module changes nothing and touches no money.
- The publication hold stands: a blanket approval does not satisfy the
  five specifics per irreversible external action.

---

*End of doc. Next action belongs to the parent orchestrator: dispatch P1
work or hold for Chauncey's gate decisions.*
