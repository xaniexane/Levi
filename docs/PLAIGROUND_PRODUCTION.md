# Plaiground Production Plan — KFX² synthesis

Date: 2026-09-21. Synthesizes three prior docs without re-research:
`PLAIGROUND_VIBECHAT_TEARDOWN.md` (VibeChat AI teardown),
`PLAIGROUND_CRUSHON_KFX2.md` (CrushOn KFX² — absorb/reverse/improve),
`PLAIGROUND_GIANTS_KFX2.md` (tube giants KFX² — strengths-amplified lens).

KFX² = Chauncey's law (2026-09-21): absorb the outside pattern —
STRENGTHS as well as weaknesses → reverse it → improve it → return a
version only we could build. Unreplicable means: our architecture
(local-first, deterministic, gated) makes their cost structures and
compromises unnecessary.

Standing facts (not up for debate here): Plaiground is the NSFW adult
companion track. PIN-gated (PBKDF2, on/off switch, minor hard-lock,
fail-closed, default OFF). Local-first, stdlib-only. Companions are
user-authored personas with boundaries, stored 0600 JSON; no shipped
persona content, neutral defaults. Bounds law lives in code. Echoverse
(SFW) is a SEPARATE track — never merge. The "Vibe Chat" rename question
is open and NOT resolved by this doc — nothing renamed here.

No explicit content in this document.

## (a) Synthesis teardown — condensed from the three docs

**VibeChat AI** (120K downloads, 3.0/5, polarized ratings): SFW cozy chat
toy, Everyone rating, no memory, no continuity, text-only, ad/analytics/
audio permissions behind privacy claims, broken "watch ads for chats"
reward loop, and three of the highest-demand companion use cases
(therapy, dating, advice) explicitly disclaimed. Eight binding
differentiation laws already recorded: different category, name, visual
brand (dark-first void, never pastel), voice, architecture, business
model, moat, and documented independence.

**CrushOn.AI** (~700K+ off-Play downloads, $0–$199.99/mo in 6 tiers):
web-first NSFW character chat. Strengths: character cards (greeting,
example dialogue, tags, discovery), multi-character/group chat, memory
pins, scene cards / target play, inspiration replies, keyword-triggered
image unlocks, creator economy (publish → followers → tips). Weaknesses:
memory wipes after backend updates, credit/coin/diamond/pack currency
confusion, server-side chats with ad-data sharing, "unfiltered" that
breaks when a routed model refuses mid-chat, bot replies eating message
caps, NSFW images blurred below premium tiers, quiet re-filtering of
once-explicit characters, no verifiable age gate. The "a lot like that"
directive stands: absorb the surface richness, keep our core.

**The tube giants** (Pornhub, XNXX, XVideos): none has an AI companion
product. Pornhub's only live AI is reThink (2022), a CSAM-deterrence
chatbot with independent evaluation showing real-world harm reduction
(Univ. of Tasmania via WIRED). XNXX/XVides show zero public AI surface;
no creator-side AI tools at any of the three; age "verification" is
geoblocking, not access control. OpenAI shelved its erotic chatbot in
March 2026 — the top of the industry walked away from adult AI
companions. The companion lane at the top is EMPTY. Their strengths are
raw material: scale, protective AI with receipts, creator money movement,
recommendation engines, data culture (Year in Review), trust & safety at
scale.

Condensed verdict: VibeChat defines what we refuse to be (ad toy, no
memory, privacy theater). CrushOn defines the surface richness to absorb
(character depth, discovery, creator economy) with its failure modes
reversed. The giants define the strategic lane — empty at the top — and
the strengths to amplify into things only our physics can ship.

## (b) KFX² — absorb, reverse, amplify into the unreplicable

### Absorbed patterns (the outside pattern, kept)

- **Character richness → Companion Schema v2.** Greeting (first message),
  example dialogue for steering, tags, avatar seed — layered onto the
  existing boundaries/traits schema. Private by default; publication is
  always an explicit owner act.
- **Multi-character chat → ensemble scenes.** Their Premium+ group chat
  becomes scenes with 2+ companions and turns — no tier wall, it's a
  scene, not an upsell, and our simulator already thinks in scenes.
- **Memory pins → depth pins.** User-pinned memories with priority recall,
  local only, never wiped by a backend update (there is no backend).
- **Scene cards / target play → scene frames.** User-authored savable,
  replayable narrative frames, mapped onto our stories engine +
  simulator.
- **Inspiration replies → deterministic suggestion lines.** Derived from
  companion traits and scene state — no model call, no cost, no refusal
  risk.
- **Hidden images / unlocks → beat-triggered art.** Keyword/beat-triggered
  procedural reveals, honest scope (gradients, glow, geometry, grain) —
  no photorealism claims, no blurred-tier teasing.
- **Creator economy → PL-05 creator services.** Publish → followers →
  tips shape, routed through Cybrus money flows with the stated 12% cut —
  contract-grade economics, not opaque diamonds.

### Reversed weaknesses (their failure → our law)

| Their failure | Our reversal |
|---|---|
| Memory wipes after backend updates; context collapse | Journal + earned rapport + recall, local files, nothing to wipe — continuity is the product |
| Credits vs coins vs diamonds vs packs confusion | One honest price, stated plainly; deterministic engine has no marginal message cost |
| Server-side chats, ad-data sharing, no encryption | Local-first 0600 storage, no ads, no analytics; Veil sealing for anything that leaves the device |
| "Unfiltered" breaks when a routed model refuses | Deterministic engine + bounds law in code — consistent, no mid-chat refusals from a stranger's model |
| Bot replies count against message caps | No per-message metering exists in our architecture |
| NSFW images blurred below ~$50/mo | Procedural art has no tiers — same honest scope for everyone |
| Quiet re-filtering of once-explicit characters | Bounds law is public, in code, and does not move under users |
| No verifiable age gate | PIN + affirmation + minor hard-lock, documented and tested |

### Amplified strengths (made unreplicable) — giants lens applied, and extended to CrushOn's own strengths

The strengths-amplified lens from the giants doc applies to CrushOn
too, per the coordinator: CrushOn's strengths deserve amplify-treatment,
not just its weakness list.

1. **Scale (giants).** They serve billions of anonymous sessions; their
   business is impressions on strangers. Amplified by inversion: we
   serve one owner with total memory. The platform that knows no one vs
   the companion that knows you. Unreplicable because their ad model
   forbids the local-first relationship ledger.
2. **reThink protective AI (giants).** The only adult-platform AI with an
   independent harm-reduction evaluation. Amplified: protection as
   foundation, not pop-up — our gate (PIN + affirmation + minor
   hard-lock + fail-closed off-switch) and bounds law ARE the product
   architecture. Their compliance is geofencing; ours is a
   physical-feeling switch in the owner's hand.
3. **Creator money movement (giants + CrushOn).** ModelHub pays at scale
   on uploads; CrushOn pays via tips. Amplified: PL-05 creator services
   with Cybrus money flows, stated 12% cut — we pay for relationships
   (fan-interaction automation, companion characters, scene
   commissions), contract-grade, creators as partners with a ledger.
4. **Recommendation engines (giants).** Their personalization is a video
   queue that keeps sessions watching. Amplified: from
   content-you-might-click to a companion that remembers — journal +
   earned rapport + recall turns personalization from a feed into a
   relationship. A queue optimizes watch time; a ledger optimizes depth.
5. **Data culture (giants).** Their Year in Review turns aggregate
   behavior into cultural events. Amplified: the personal Year in
   Review — story arcs, scenes played, rapport earned, characters grown.
   Private, local, yours, never broadcast. They can only show you the
   crowd; only we can show you yourself.
6. **Character richness (CrushOn).** Their card surface is their best
   asset — greeting, example dialogue, tags, discovery. Amplified: the
   card becomes a full instrument — greeting + examples + tags + avatar
   seed wired into earned rapport and scene frames, so a card doesn't
   just start a chat, it seeds a growing relationship. They rent
   discovery on a web page; we grow it in the ledger.
7. **Creator economy (CrushOn).** Their publish → followers → tips loop.
   Amplified: published companions carry provenance — author, bounds
   declaration, generation lineage — and the ledger of their growth
   stays auditable. Their economy is opaque diamonds; ours is stated
   terms on real money.
8. **Discovery (CrushOn).** Their library is a catalog of strangers'
   characters. Amplified: discovery routed through the gate and the
   ledger — any adopted companion starts its own local journal from the
   moment of adoption, so "found" characters become "yours" instantly.
9. **Trust & safety at scale (giants) → honesty as offense.** AI content
   floods tube sites with no visible labeling stance from any of them.
   Amplified: we label our procedural art for exactly what it is, never
   claim photorealism. They can't label honestly without indicting
   their own catalog; we have nothing to hide.
10. **The Echoverse simulator (ours alone, still unmatched).** Taken /
    not-taken / wild branching scenarios — they have chat; we have
    scenes that branch. Nothing in any competitor's stack does this.

Return-to-sender summary: everything they monetize through scarcity
(memory, group chat, images, unfiltered consistency, creator tips) we
ship as physics — because our physics made scarcity unnecessary.

### Positioning — the uproar doctrine (Chauncey, 2026-09-21)

Chauncey's positioning law: we offer what they do, what they don't, and
do it even better — at a fraction of their fraction. The slate matches
every competitor feature-for-feature PLUS what they never offered,
built better, at radically lower prices. Dollar-scale entry, volume
over margin. This is the adult track's own positioning — it stands on
its physics, and it never borrows from or merges with Echoverse's SFW
track. The binding split holds: separate tracks, shared engines only.

**Competitor features → our parity (drawn from the teardown above):**
character cards (greeting, example dialogue, tags, discovery — their
best surface, our Companion Schema v2, private by default); multi-
character group chat (their Premium+ tier wall, our ensemble scenes —
a scene, not an upsell); memory pins (their context-collapse patch,
our depth pins with local priority recall); scene cards / target play
(their frames, our savable replayable scene frames with provenance);
inspiration replies (their prompt-nudge, our deterministic suggestion
lines — no model call, no cost, no refusal risk); keyword-triggered
image unlocks (their blurred tiers, our beat-triggered procedural
reveals, same honest scope for everyone); the creator economy (their
publish → followers → opaque-diamond tips, our PL-05 publish →
followers → tips on real money with contract-grade terms).

**Competitor gaps → our exclusives:** the Echoverse simulator —
taken / not-taken / wild branching scenes, unmatched in any
competitor's stack (chat is not a scene); continuity as a readable
local ledger — journal + earned rapport + recall — that no backend
update can wipe and no memory wipe resets; no per-message metering
exists in our architecture (their bot replies eat your caps); no
blurred premium tiers on art; the bounds law public, in code, never
moved under users (their quiet re-filtering answered in writing);
protection as architecture — PIN + affirmation + minor hard-lock +
fail-closed off-switch, and Veil sealing for anything that leaves the
device (their "verification" is geoblocking); provenance labeling on
every artifact, honest about what it is; the personal retrospective —
private, local, never broadcast; creator relationships paid on a stated
12% platform cut through Cybrus money flows, partners with a ledger,
not diamond theater.

**Our price as a fraction of theirs:** ours — one honest price, stated
plainly; the number is Chauncey's call and gated (not set in this
doc). Creator-side economics are stated: 12% platform cut per PL-05
(contract-grade, in this document). Theirs — CrushOn $0–$199.99/mo
across 6 tiers (per the synthesized CrushOn teardown, secondary-source
based); the tube giants have no AI companion product at all — the top
of the lane is empty, which the doctrine reads as price-setting space,
not a ceiling. Their heaviest tier is ~$200/month of recurring rent
for memory, images, and unfiltered consistency we ship as physics —
the fraction of fractions works because their fractions recur forever
and ours is a single honest number.

## (c) Production-phase plan — sequenced build order

All builds sit behind the existing gate, local-first, stdlib-only.
Dependencies first; creator publishing and anything money- or
customer-facing gated on Chauncey.

### Phase 1 — Companion Schema v2 (foundation)
Scope: extend the companions module with greeting (first message),
example dialogue, tags, avatar seed. Old definitions keep working
(backward-compatible schema migration). Bounds fields unchanged.
Milestones:
- M1.1 Schema v2 spec ratified in-repo (fields, defaults, migration path).
- M1.2 Loader migration: v1 JSON loads unchanged; writer emits v2.
- M1.3 Greeting + example dialogue wired into chat openers and steering.
- M1.4 Avatar seed feeding the procedural backend (deterministic seed →
  reproducible art).
- Gate note: no Chauncey gate to build; schema ships private-by-default.

### Phase 2 — Depth: memory pins + earned rapport instrument
Scope: depth module grows pinned entries with recall priority over
journal recall. Rapport meter reads the record (earned from actual
history, not flattery). Pins are local, never synced, never wiped.
Milestones:
- M2.1 Pin/unpin/list commands with priority recall weighting.
- M2.2 Rapport ledger: reads journal + pins + scene history into a
  readable score with an audit trail.
- M2.3 Personal retrospective generator (the "Year in Review" amplify):
  story arcs, scenes played, rapport earned — private, local, never
  broadcast.

### Phase 3 — Ensemble scenes
Scope: multi-companion sessions as simulator scenes with turns.
Independent of any paywall: it's a scene, not an upsell.
Milestones:
- M3.1 Scene session model: 2+ companions, turn order, shared scene state.
- M3.2 Deterministic suggestion lines (the "inspiration replies" absorb):
  from companion traits + scene state, no model call.
- M3.3 Scene history feeding depth (journal + rapport per participant).

### Phase 4 — Scene frames
Scope: savable, replayable narrative frames (their Target Play, our
engine), authored by the owner, stored with provenance.
Milestones:
- M4.1 Frame schema: beats, roles, memory logic hooks, replay entry points.
- M4.2 Frames wired into simulator (Echoverse branching: taken /
  not-taken / wild) and stories engine.
- M4.3 Frame library: local-only browsing, explicit publish to creator
  layer only when PL-05 lands (gated).

### Phase 5 — Beat-triggered art
Scope: keyword/beat-triggered procedural reveals from the in-repo
procedural backend. Honest scope: deterministic generative art —
gradients, glow, geometry, grain. No photorealism claims, no likenesses,
no blurred tiers.
Milestones:
- M5.1 Beat registry: keyword/beat → art event mapping per scene frame.
- M5.2 Reveal mechanic wired to photos module via avatar/frame seeds.
- M5.3 Provenance labeling on every artifact (what it is, how made).

### Phase 6 — Creator publishing (GATED)
Scope: companions publishable to the PL-05 creator layer by explicit
owner choice only. Economics: stated 12% platform cut, Cybrus money
flows, contract-grade terms.
GATED ON CHAUNCEY: creator publishing → PL-05 readiness, payment
destination, production keys, terms details (his five specifics per
action). Also gated: any payouts, any live payments, any customer
release (legal review before first mint/release-style action applies).
Milestones:
- M6.1 Publish contract: package format, bounds declaration, provenance
  manifest (author, bounds, generation lineage).
- M6.2 Private-by-default verified end to end; publish is a deliberate
  two-step owner action.
- M6.3 PL-05 integration on his word; payouts only after his five
  specifics per action.

### What is gated on Chauncey (explicit)
- Creator publishing → PL-05 readiness (Phase 6 entirely).
- Payments: payment destination, production keys, terms details —
  his five specifics per action, no blanket.
- Any customer release of Plaiground — legal review gate stands.
- Owned image backend beyond procedural scope (future, his word).
- Any third-party service entering any pipeline (voice, anything) —
  his word, default is no.

### Hard nos (law, not preference)
1. No external model routing, ever. "Only our stuff" — no renting
   their brains to power our product.
2. No third-party image services. Perchance re-routed out 2026-09-21 —
   never again; pipeline is procedural-local now, owned backend later
   only on his word.
3. No ads. Ever. No ad SDKs, no reward loops, no packs funnel.
4. No Echoverse merge. Echoverse (SFW) is a separate track — the
   simulator engine is shared physics, the tracks never merge.
5. No shipped persona content. Neutral defaults; companions are
   user-authored. Bounds law in code, public, does not move under users.
6. No privacy theater. No analytics, no audio recording, no ad
   permissions. Local-first 0600 storage; Veil sealing for anything
   that leaves the device.
7. No per-message metering. Deterministic engine has no marginal
   message cost — scarcity pricing is their physics, not ours.

### Honest limits (carried from the three docs)
- Voice slots / voice messages: roadmap, not now. No third-party voice
  service without his word.
- Photorealistic image synthesis: outside procedural scope; not claimed.
- Pornhub AI-labeling policy / XVideos-XNXX internal AI use: unknown,
  no public document found.
- Aylo state-by-state geoblock list not re-verified for 2026.
- No unannounced competitor AI betas surfaced in press, patents, or
  job postings.
