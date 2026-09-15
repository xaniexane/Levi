# LEVI Monetization Plan — DRAFT v0.1

> Status: planning draft, 2026-09-15. Prices are targets anchored to verified
> competitor pricing (June–Sept 2026). Validate against real unit costs
> (hosted inference, fleet compute) before launch. Nothing here overrides
> **free core forever** — that is binding (see `docs/ENTERPRISE.md`).

## The boundary (non-negotiable)

**Free forever, no account, no ads:** the local LEVI core — agent runtime,
fleet (local), PWA, growth loop, model family, all skills, courses corpus,
MCP, learning-pack *receiving*. This is the mission and the moat.

**Paid only for things that cost us money or serve businesses:** hosted
inference, cloud sync/API, fleet compute at scale, team features, product-line
SaaS, marketplace rails. If it can run on the user's own hardware, it is free.

## Pricing philosophy: more bang for the $1

The market anchor is $20/mo for a chatbot (ChatGPT Plus $20, Claude Pro $20,
Gemini Advanced $19.99 — verified June 2026; source: theeditorial.news
comparison). LEVI undercuts the anchor **while selling work, not chat**:
agent-hours and completed tasks, not messages. Every paid tier is framed as
"for less than a chatbot, you get a workforce."

- Annual billing = 2 months free (standard).
- No ads in any tier, ever — including free (unlike ChatGPT Free/Go, which
  carry ads as of 2026).
- Early adopters lock their price for life (grandfathering).
- Publish a public "bang-per-dollar" page: agent-hours per dollar vs.
  competitors' rate limits (e.g. Plus ≈ 50 messages/3h).

## Pack 1 — LEVI Cloud (the $20-killer)

| Tier | Price | What you get |
|---|---|---|
| **Cloud Free** | $0 | Device sync, learning-pack receiving, 25 cloud agent-tasks/mo (taste of hosted) |
| **Cloud Solo** | **$12/mo** | Hosted API + PWA sync everywhere, learning packs, **500 agent-task credits/mo**, LEVI-native models hosted, bring-your-own-key for external providers |
| **Cloud Pro** | $24/mo | 2,500 agent-task credits/mo, priority routing, long memory, 3-seat team workspace, API access |

Pitch: *For 40% less than ChatGPT Plus, LEVI doesn't chat at you — it does
the work.* Solo at $12 is the wedge; Pro at $24 matches the anchor dollar
while offering ~5x the productive output.

## Pack 2 — Fleet Packs (the workforce — the real differentiator)

Sold as **agent-hours**, because that's what businesses buy: outcomes.

| Tier | Price | What you get |
|---|---|---|
| **Fleet Starter** | $29/mo | 100 fleet agent-hours/mo, 1 operator seat, approval workflows, decision-ledger audit |
| **Fleet Team** | $99/mo | 5 seats, 1,000 pooled agent-hours/mo, shared blackboard, role-based approvals, audit export |
| **Fleet Enterprise** | Custom | SSO/SAML, SLA, dedicated capacity, data residency (+10% like OpenAI's regional uplift), private learning packs, white-glove onboarding |

Overage: agent-hours at a published per-hour rate (target: undercut
equivalent human VA cost by 10x — the story writes itself).

## Pack 3 — PL-01 NeighborOS SaaS (per home-services business)

Competitor anchors (verified 2026): Housecall Pro $59–$299/mo annual
($79–$329 monthly); Jobber $19–$49 solo → $344–$699 team tiers. Both charge
extra for AI add-ons (HCP: proposal tool $40, GPS $20/vehicle, price book
$149; Jobber: AI receptionist separate).

| Tier | Price | What you get |
|---|---|---|
| **Solo** | **$39/mo** | Scheduling, dispatch, photo-to-estimate, invoicing, customer hub, AI receptionist *included* — undercuts Jobber Core ($49) and HCP Basic ($59/$79) |
| **Crew** | $99/mo | Up to 5 users, GPS + route optimization, marketing + review engine, QuickBooks sync — vs HCP Essentials $149 / Jobber Connect $139 |
| **Scale** | $229/mo | Up to 10 users, advanced reporting, API, dedicated onboarding — vs HCP MAX $299 |

The differentiator at every tier: the agentic workforce (dispatch, bidding,
coach, guardian) is **included, not an add-on**. Competitors sell software;
NeighborOS sells outcomes with a crew that never sleeps.

**NeighborPay** (deferred): card processing at a published rate only after
the money-transmitter / contractor-classification legal decision. Not priced
here on purpose.

## Pack 4 — Marketplace (10% take)

Agents, workflows, skills, model remixes sold between users: **10% platform
take** — undercuts app-store 30%, matches the indie-friendly bar (Gumroad
10%). Covers escrow, verification, and review. Free to list; LEVI takes its
cut only when creators get paid.

## Pack 5 — Enterprise & white-label (custom)

For companies that want LEVI inside their walls: private cloud, custom model
remixes, compliance packs (SOC 2 roadmap), training. Priced per deal, floor
set by dedicated-capacity cost.

## What we deliberately do NOT sell

- **The core.** Never. Not a "pro local" tier, not feature-gated intelligence.
- **Weights.** LEVI-native weights are free to download; we monetize *hosting*
  them, not the files.
- **User data.** Learning packs are aggregated technique-only; selling data
  would torch the trust the whole organism runs on.
- **Ads.** No ad tier, no sponsored answers. Ever.

## Launch order

1. Cloud Solo ($12) — smallest infra lift, biggest wedge vs. $20 chatbots.
2. NeighborOS Solo ($39) — PL-01 is the most specified product line; home
   services is a proven SaaS market with clear anchors to undercut.
3. Fleet Starter ($29) — once Phase 2 control plane proves trustworthy.
4. Marketplace 10% — once creators exist to sell.
5. Enterprise — inbound-driven.

## Open questions (need answers before launch)

- Real unit costs: hosted inference $/1M tokens for LEVI-native models,
  fleet compute per agent-hour. Prices above assume healthy margin — verify.
- Payment rails: Stripe (standard); merchant-of-record for global tax?
- Refund/chargeback policy for agent-hours (failed tasks = automatic credit?).
- Grandfathering mechanics in billing system.
