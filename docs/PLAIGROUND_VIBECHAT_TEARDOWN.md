# Plaiground vs "VibeChat AI – Vibe Your Chat" — competitive teardown

Date: 2026-09-21. Research: public web (AppBrain, APKPure, review corpus).
Their app: `com.appmixer.vibechatai`, developer "Appmixer", on Play since Jan 2026.
**Verdict up front:** different category, different architecture, different
audience, different brand. The only thing they share with us is the job
"talk to a synthetic companion" — and even that job is done opposite.

## 1. Their product, as it actually is

- **Scale/reputation:** 120K downloads, **3.0/5 from 120 ratings**, histogram
  polarized 42×5★ vs 42×1★ — trust is broken on sight.
- **Positioning:** cozy, pastel-adjacent, SFW safe-space. Rated **Everyone**,
  Entertainment category. "Come vibe, imagine, and create."
- **Features (their own listing):** chat with AI personalities; create custom
  AI models from preset vibes (calm, creative, playful, thoughtful; 6 humanoid
  species); casual conversation; AI image generation; privacy claims.
- **Explicitly disclaimed:** not for therapy, dating, or professional advice —
  three of the highest-demand companion use cases, refused on purpose.
- **Business model:** free download, ad-supported chat allowance, "watch ads
  for more chats" loop that **users report is broken** (no ads served, infinite
  "check back later"), plus paid "packs". Metadata claims no ads; users report
  "so many ADS". The listing and the lived product disagree.
- **Technical footprint:** 33.9 MB APK, **17 permissions** — advertising,
  analytics, network, **audio recording**, billing. Their privacy page says
  "chats stay private" while the manifest asks for ad/analytics/audio access.
- **Review themes:** ads everywhere; broken reward loop; "fake app… no work";
  text-only shallow interaction ("no other input to narrate the story");
  amateur feel ("backbencher students AI project"); one satisfied reviewer
  still uneasy — "it feels less like role play and more like trying to talk
  to a human… I never want to be confused about what's on the other end."

## 2. Their gaps — every one is our open field

1. **No memory or continuity.** Nothing about journals, evolving companions,
   or relationship depth. A vibes dispenser, not a companion that grows.
2. **SFW-only by design.** The Everyone rating leaves the entire adult lane —
   plus dating-adjacent and creator lanes — unserved.
3. **Shallow interaction.** Text-only character output; no scenarios, no
   narrative input modes, no voice (despite the audio permission).
4. **Privacy theater.** "Private chats" vs. ad/analytics/audio permissions.
5. **Broken monetization.** The ad-for-chats loop strands free users; the
   packs funnel reads as a trap. Ads are their #1 complaint.
6. **No transparency.** Users unsure what's human vs. AI on the other end.
7. **Thin moat.** One small dev, 2 apps, commodity feature set, no ecosystem,
   no creator economy, no community.
8. **Disclaimed the demand.** Therapy, dating, advice — refused outright.

## 3. Our product — what Plaiground actually is

- **Gate-first:** PIN + on/off switch, default OFF, minor hard-lock,
  fail-closed disable. No competitor does local PIN-gated adult mode.
- **Companions:** user-authored personas with explicit boundaries, stored
  owner-local as 0600 JSON. Neutral defaults; no shipped persona content.
- **Depth:** per-companion journal, rapport meter *earned from actual
  history*, recall summaries. Continuity is the product.
- **Simulator:** scenario runner over Echoverse branching (taken / not-taken /
  wild) — a different interaction paradigm than chat, not a chat skin.
- **Stories:** adult-fiction writing engine — craft tools for grown writers
  (openers, character builders, arc weavers, tension dial).
- **Wellness:** adult relationship & intimacy wellness — check-ins,
  communication decks, date-night planner. The lane they disclaim, owned
  responsibly with non-medical disclaimers.
- **Afterdark:** grown-folks entertainment, unfiltered stance, never preachy.
- **Photos:** capability contract + in-repo procedural backend (deterministic
  generative art — honest scope, not photorealistic, not likenesses).
  **No third-party image service anywhere in the pipeline** (Perchance
  re-routed out 2026-09-21 — see §6).
- **Bounds:** hard content law in code — minors, non-consensual, violent,
  manipulative content refused at every entry point.
- **Architecture:** local-first, stdlib-only, no account, no ads, no
  analytics, no audio recording, deterministic engine, no per-message costs.

## 4. Head-to-head — where we share nothing

| Axis | VibeChat | Plaiground |
|---|---|---|
| Audience | Everyone, SFW cozy | Adults only, grown and direct |
| Access control | None | PIN + on/off switch, minor hard-lock |
| Memory | None | Journal + earned rapport + recall |
| Interaction | Text-only chat | Chat + scenario simulator + fiction engine |
| Image gen | Cloud, unknown quality | Procedural local art, honest scope |
| Privacy | Claims vs. 17 permissions | Local-first, no ads/analytics/audio |
| Monetization | Ads + packs, broken loop | No ads ever; clean pricing when priced |
| Transparency | Users unsure what's AI | Deterministic engine, SI stance stated |
| Disclaimed lanes | Therapy, dating, advice | Wellness lane owned |
| Creator economy | None | PL-05 adjacency, creator services |

## 5. The differentiation law — no distinct similarities

These are binding, not aspirational:

1. **Different category, different rating.** They are Everyone/SFW; we are
   adult-only. No store shelf, no audience, no confusion.
2. **Different name.** Plaiground vs VibeChat — visually and phonetically
   distinct. (Their app's existence in our exact category is itself the
   reason the Vibe Chat rename is dead.)
3. **Different visual brand.** Dark-first void aesthetic. Never pastel, never
   cozy, never soft-gradients-and-smiles.
4. **Different voice.** Direct, grown, unfiltered-in-stance. Never "come
   vibe", never "wholesome", never euphemism-first.
5. **Different architecture.** Local-first, no permissions theater, no ad
   SDKs — the technical opposite of their manifest.
6. **Different business model.** No ads ever. No broken reward loops. No
   packs funnel. If it costs money, the price is stated plainly.
7. **Different moat.** Depth/continuity + simulator + creator adjacency +
   the gate itself. Their moat is a vibes dispenser; ours is a system.
8. **Documented independence.** This file exists so the lineage is on
   record: independent design, independent code, no shared DNA.

## 6. Perchance re-route (2026-09-21)

Chauncey's order: the image design work that ran through Perchance stops
there. **No reliance on Perchance anywhere in the pipeline.** The photos
module was already contract + procedural-local; the re-route makes it law:

- No Perchance API calls, keys, embeds, or endpoints in code, docs, or
  design references.
- The image story is: procedural offline generation now (honest scope),
  a declared `PhotoBackend` contract for a future owned backend later.
- Any design artifacts that assumed Perchance get re-pointed at the
  procedural backend's actual output (gradients, glow, geometry, grain)
  or parked until the owned backend exists.

## 7. What we build next to widen the gap

1. **Depth first** — memory is their biggest hole and our biggest weapon.
2. **Simulator scenarios** — the interaction paradigm they can't copy
   without rebuilding.
3. **Wellness lane** — the demand they disclaimed, served responsibly.
4. **Owned image backend** — when it's real, it ships inside our house,
   never rented from a third party again.
5. **Creator adjacency** — the economy layer that turns a toy into a
   platform.
