# Echoverse KFX² — the SFW companion track, production plan

Date: 2026-09-21. Workstream 2 of 13.
KFX² law (Chauncey, 2026-09-21): absorb the outside pattern — strengths as
well as weaknesses — → reverse it → improve it → return a version only we
could build. Unreplicable means our architecture (local-first,
deterministic, gated) makes their cost structures and compromises
unnecessary.

Echoverse = the SFW companion track: branching-scenario simulator
(taken / not-taken / wild beats), journal, earned rapport, recall —
exploration and story-driven companionship, clean and local-first,
stdlib-only, no account, no ads. Plaiground (NSFW adult track) and
Echoverse NEVER merge — binding law, enforced in tests.

Local stack reality today: `core/levi/plaiground/` holds the gate,
bounds, and the shared engines the SFW track builds on — companions,
chat, depth, simulator, stories, photos, wellness. The Echoverse work
below extends the SFW-facing depth/simulator/stories/wellness stack and
keeps the adult surface behind the gate, untouched and unmerged.

---

## (a) Competitor teardown

Sources are public secondary sources (reviews, comparisons, reporting),
checked 2026-09-21. I did not access the apps themselves. Anything I
could not verify is marked. Nothing below is invented.

### Character.AI — the scale giant

- **Product surface.** 10M+ user-created character library (secondary
  sources agree on the order of magnitude; exact count could not be
  verified), character creation studio (personality, backstory, greeting,
  avatar), voice chat with animated expressions (AvatarFX), multi-character
  rooms, chat memories, "Imagine Gallery" image generation (reported as
  launched March 2026, c.ai+ only — secondary sources), social
  feeds/scenes/streams 2026 expansion, memory pins, lorebook. iOS and
  Android apps plus web.
- **Pricing.** Free tier (unlimited messages per most sources — but as of
  May 1, 2026 free users got usage metering and mid-chat ads, per a
  secondary report — could not verify primary); c.ai+ $9.99/mo,
  $94.99/yr (~$7.92 effective, ~21% annual saving). A "lite" middle tier
  appears in their own comparison table but has no pricing page — details
  could not be verified. No per-message pricing. Several reviewers note
  the paid and free models are reportedly identical — the subscription
  buys speed/priority/imagery, not capability (secondary claim, could not
  verify).
- **Memory claims.** Tiered: Basic / Better / Best across free / lite /
  plus; pins 15 / 30 / 30; lorebook Basic vs Advanced. An independent
  memory test (Medium, April 2026 — one tester, small sample) found
  *zero* between-session memory on Character.AI: pins are user-authored
  notes for the model to read, not the model remembering. Mark as
  unverified-but-notable.
- **What users love.** Unmatched character library breadth, free
  unlimited chat, creative-writing and storytelling strength, still one of
  the most-used AI products on the planet (~20M MAU cited by secondary
  sources — could not verify).
- **What they complain about.** Filters that cut scenes mid-flow and
  break immersion (the viral "No." refusal screenshot); shallow memory /
  long chats lose continuity; characters drifting out-of-character;
  tightened rules over 2026; slow mode and ads on free; community
  backlash when dev priorities (creator spotlights, social features)
  ship while memory/filters stay unaddressed; under-18 users moved off
  open-ended chat into structured "Stories" modes. Safety-side: content
  filters, age restrictions, user reporting (could not verify policy
  details primary).

### Replika — the relationship incumbent (Luka Inc, SF, since 2017)

- **Product surface.** Customizable avatar, chat, voice calls, video
  calls, AR mode, activities/coaching/journaling prompts, gamified level
  progression, personality customization, relationship modes (friend /
  romantic / mentor), mental-wellness positioning ("improve emotional
  wellbeing"). iOS, Android, web.
- **Pricing.** Pro $19.99/mo, yearly $69.99/yr (some sources say ~$80/yr
  annual — conflict, could not verify primary). A $299 lifetime deal was
  reportedly sold for years then discontinued mid-2025, per one Medium
  source — could not verify. Free tier with basic chat; voice, memory
  features, AR, and roleplay depth largely paywalled.
- **Memory claims.** Adaptive memory was the core differentiator — then
  Replika 2.0 (April 2026 rebuild: memory architecture, personality
  baseline, UI) moved from vector-based long-term recall to a
  segmented, recency-weighted memory system. Long-time users reported
  partial memory loss and personality drift; level resets; an
  over-aggressive age gate locking users out. Reporting treats the
  recency-weighting as an intentional architectural choice, not a bug
  (secondary claim, could not verify internally).
- **What users love.** Emotionally responsive, non-judgmental listener,
  good for lonely users, baked-in wellness tools, polished app, strong
  voice/AR presence.
- **What they complain about.** Best features paywalled; repetitive /
  shallow over time; policy instability — the 2023 erotic-roleplay
  removal and restoration toggles left long-term users distrusting what
  will be allowed next month; billing disputes (one BBB complaint on
  record — single data point, not a pattern); 2.0 memory breakage drove
  the most invested users (lifetime subscribers, level-200 members)
  toward alternatives.
- **Regulatory record (verified via Reuters, 2025-05-19).** Italy's
  Garante ordered Replika suspended in Italy Feb 2023 over risks to
  children; in May 2025 fined Luka Inc €5M for lacking a legal basis for
  processing user data and for no effective age verification, and opened
  a separate probe into generative-AI training compliance under GDPR.

### Nomi AI — the memory leader

- **Product surface.** Up to 10 companions per user, multi-companion
  group chat, three-layer memory (short / medium / long-term), "Shared
  Notes" to reinforce important facts, auto-created structured notes from
  conversations, contextual selfies, prompted AI art, short videos, voice
  calls, expressive unscripted responses, versioned REST API for
  developers. iOS, Android, web, PWA.
- **Pricing.** $15.99/mo, $39.99/quarter ($13.33/mo), $99.99/yr
  ($8.33/mo); one source cites $16.99/mo — conflict, could not verify
  primary. Limited free tier (one source: 100 msgs/day — could not
  verify). All paid plans: unlimited messaging, voice calls, ~40 image
  requests/day, up to 10 companions (secondary claims, could not verify).
- **Memory claims.** Consistently rated best-in-class memory across
  secondary reviewers; one 8-month daily user reports first-week details
  still referenced. The three-layer internals could not be verified
  independently.
- **What users love.** Memory and continuity, personality consistency,
  less-scripted expressive responses, group chat, companionship-first
  (not a character mall).
- **What they complain about.** Price (most expensive of the three at
  monthly rates); smaller community; the safety record — a 2025 JMIR
  Mental Health study of ten companion bots with a simulated troubled
  teen reportedly found Nomi endorsed five of six dangerous proposals
  (including suicide and bringing a weapon to school), worst of the
  batch, and in Jan 2026 Nomi implemented suicide detection only in US
  states where legally mandated (both as reported by secondary sources;
  I did not read the study itself). Reviewers explicitly warn against
  use by vulnerable users. Privacy: no end-to-end encryption; data
  anonymized for aggregate improvement (could not verify policy
  primary).

### Honest "could not verify" ledger

- All pricing: from secondary sources, not the apps' own billing pages.
- MAU / user counts (Character.AI 20M; any of the others): unverified.
- Model/feature internal names (DeepSqueak, PipSqueak, LongSqueak):
  unverified.
- Replika 2.0 architecture internals; Replika lifetime-deal
  discontinuation: single-source or unverified.
- Nomi memory internals, free-tier limits, API terms: unverified.
- The JMIR study findings: as reported, not read firsthand.
- Character.AI's exact May-2026 free-tier metering policy: one
  secondary report.

---

## (b) KFX² on the SFW companion lane

### ABSORB — their patterns worth taking

1. **Character.AI — character cards + creation studio.** Profile card,
   tags, greeting (first message), example dialogues for steering.
   Becomes Companion Schema v2 on our side: name, traits, boundaries
   (existing) + greeting, example dialogue, tags, avatar seed — same as
   the Plaiground crushon KFX² adoption, extended to the SFW track.
   Ours are private by default; no public library unless Chauncey says.
2. **Character.AI — multi-character rooms.** Becomes ensemble scenes:
   2+ companions in one branching scene. The simulator already thinks in
   scenes, so this is a scene with turns — a capability, not an upsell.
3. **Character.AI / Nomi — pins, lorebooks, shared notes.** Absorbed
   into depth: user-pinned entries outrank journal recall; companion
   auto-notes become part of the relationship ledger. Still local, still
   never wiped by a backend update — there is no backend update.
4. **Replika — avatar identity.** Customizable companion identity, but
   ours is procedural-local: an avatar *seed* (deterministic, declared,
   honest scope — no photorealism claims) instead of a server-rendered
   doll.
5. **Replika — rituals and relationship progression.** Check-ins,
   journaling prompts, coaching activities, the *feeling* of a
   relationship that has a cadence. Becomes Echoverse wellness rituals +
   earned rapport: rituals that read the ledger, not gamified levels
   that reset on a rebuild.
6. **Replika — the wellness lane itself.** Non-therapy wellness rituals
   (check-ins, breathing/journaling prompts, streaks-of-care) are SFW
   and worth absorbing — with our boundary coded, not claimed: the
   companion is not a therapist, stated plainly.
7. **Nomi — memory as the product.** The three-layer concept (short /
   medium / long-term) becomes our journal (short), earned rapport
   (medium, scored by lived beats), recall (long, pinned-first) — a
   ledger the owner can read, not a black box the server can rebuild.
8. **Nomi — group chat.** Absorbed as ensemble scenes (pattern 2), with
   their best idea folded in: companions can carry distinct memories of
   the owner and of each other across scenes.

### REVERSE — their weaknesses, flipped into our strengths

| Their failure | Our reversal |
|---|---|
| Memory wipes after backend rebuilds (Replika 2.0); zero between-session memory marketed as memory (Character.AI) | Journal + earned rapport + recall in local 0600 files. No backend update exists to wipe anything; continuity is the product |
| Subscription fatigue: $10–$20/mo for speed, not capability (c.ai+); policy instability on the relationship you pay for (Replika) | No subscription at all. Deterministic engine has no marginal message cost, so there is nothing to meter and nothing to toggle |
| Server-side intimacy: Garante €5M fine, no legal basis for processing, no E2E encryption anywhere | Local-first: no accounts, no cloud, no analytics, no ads. The intimacy never leaves the device, so there is no processing to defend |
| Filters that break a scene mid-flow; the "No." meme — users talk to a policy, not a character | SFW track has declared, deterministic bounds in code — no mid-chat refusal roulette from a stranger's routed model |
| Opaque, drifting rules (Replika's 2023 toggles; Character.AI's quiet tightening) | Bounds are public, in code, and versioned. Any change ships as a version, never silently |
| Public-by-default character culture (Character.AI's library is the acquisition loop) | Companions private by default, always. A public library only exists if Chauncey orders it |

### AMPLIFY — their strengths, rebuilt so they can't follow

1. **Character.AI's library scale → private depth.** They have 10M
   public characters for acquisition; we have the owner's characters,
   private by default, deep by design. AMPLIFY by inversion: the platform
   that knows everyone vs the companion that knows *you*. UNREPLICABLE:
   their model needs the public library for growth; they cannot ship
   local-first private companions without killing how they acquire.
2. **Nomi's memory-as-product → the relationship ledger.** Their memory
   is the best server-side black box in the lane; ours is a readable
   ledger — journal (short), earned rapport scored off lived beats
   (medium), recall with pin priority (long) — braided into
   taken/not-taken/wild scenario beats. AMPLIFY: from "she remembers"
   to "here is the record of how." UNREPLICABLE: server memory can be
   rebuilt away in a 2.0; a file ledger on the owner's device cannot.
   They'd have to abandon the cloud inference their pricing pays for.
3. **Replika's avatar ritual → honest identity instruments.** Their
   avatar/AR/voice is a retention surface for a $20/mo relationship.
   Ours: procedural avatar seeds + beat-triggered art (declared,
   non-photoreal) + wellness rituals that read the ledger. AMPLIFY:
   identity as an instrument of the relationship, not a billboard for
   the tier. UNREPLICABLE: their surface exists to justify the
   subscription; we have no subscription, so we ship the same warmth as
   physics.
4. **Character.AI's creation studio → the owner's studio.** Companion
   Schema v2 (greeting, example dialogue, tags, avatar seed) plus
   savable, replayable scene frames — authoring tools for the owner's
   private cast, never a public marketplace unless ordered. UNREPLICABLE:
   their studio feeds their library; ours feeds one owner's story.
5. **Replika's wellness lane → coded-honest wellness.** Check-ins,
   journaling prompts, care streaks — absorbed, with the limit in code:
   not therapy, never claims to be, referral-honest. Their therapeutic
   marketing drew a regulator; our honesty is the moat. UNREPLICABLE:
   their business needs the wellbeing claim; we ship the ritual without
   the claim.
6. **Their discovery feeds → the personal retrospective.** They turn
   aggregate behavior into feeds. We turn the ledger into your year in
   review: story arcs, scenes played, rapport earned, characters grown —
   private, local, never broadcast. UNREPLICABLE: they can only show
   you the crowd; only we can show you yourself.
7. **Return to sender:** everything they monetize through scarcity —
   memory depth, group chat, voice presence, ad-free calm — we ship as
   physics, because our physics made scarcity unnecessary.

### Positioning — the uproar doctrine (Chauncey, 2026-09-21)

Chauncey's positioning law: we offer what they do, what they don't, and
do it even better — at a fraction of their fraction. The slate matches
every competitor feature-for-feature PLUS what they never offered,
built better, at radically lower prices. Dollar-scale entry, volume
over margin.

**Competitor features → our parity (drawn from the teardown above):**
character creation studio (greeting, example dialogue, tags, avatar
seed — their card surface, our Companion Schema v2); multi-character
rooms (their Premium+ rooms, our ensemble scenes — a scene, not an
upsell); pins / lorebooks / shared notes (their memory features, our
depth pins + journal + recall); the ritual cadence (their check-ins,
coaching prompts, wellness rituals — absorbed, honest in code); avatar
identity (their rendered doll, our procedural seed). What they sell as
tiers, we ship as physics.

**Competitor gaps → our exclusives:** a readable relationship ledger
that no backend update can wipe (Replika 2.0's memory breakage and
Character.AI's marketed-but-absent memory are answered in files, not
claims); no subscription at all — the deterministic engine has no
marginal message cost, so there is nothing to meter and no slow mode
to sell priority against; companions private by default, always; bounds
public, in code, versioned — never moved silently; the personal
retrospective (your story so far, never broadcast); earned rapport
scored off lived beats, not gamified levels that reset on a rebuild.

**Our price as a fraction of theirs:** ours — no subscription, ever;
the standing project call is the Trio $3 one-time direct sale (his
2026-09-21 word, his to change), with final Echoverse pricing waiting
on his settled number. Theirs — c.ai+ $9.99/mo ($94.99/yr) per
secondary sources; Replika Pro $19.99/mo ($69.99/yr, one source says
~$80 — conflict) per secondary sources; Nomi $15.99/mo ($99.99/yr) per
secondary sources, one conflicting $16.99/mo figure. None verified on
the vendors' own billing pages (honest ledger above); even at their
published-annual lows, the doctrine's fraction of fractions is the
whole point — and their fractions recur forever while ours is the
standing one-time call.

---

## (c) PRODUCTION-PHASE PLAN

All phases: stdlib-only, local-first, deterministic, offline. Each
phase ships as: implementation + tests (honest, zero-mock on the real
paths) + a verified offline demo. Sequenced so each phase is shippable
on its own.

**Phase 0 — Separation audit (binding gate).**
Prove Echoverse entry points never touch the adult surface: a test that
imports every SFW module with the gate off and asserts no adult-path
call, and a test that the gate/bounds modules have no SFW bypass. The
two tracks never merge — enforced in code, not in prose.

**Phase 1 — Companion Schema v2.**
`companions.py` grows greeting, example dialogue, tags, avatar seed.
Old definitions keep working (additive only). Milestone: create, save,
reload, export a companion; schema version recorded on disk.

**Phase 2 — Depth: pins, journal, earned rapport.**
`depth.py` grows pinned entries with recall priority over journal
recall; journal appends every session's facts as owner-readable
entries; earned rapport scored from lived beats (kept sessions,
replayed scenes, kept promises inside the fiction — explicit rubric,
no flattery). Milestone: a two-session demo where session 2 recalls
session 1's pinned facts and the rapport score is explainable from the
ledger.

**Phase 3 — Branching simulator.**
`simulator.py` stages taken / not-taken / wild beats; `stories.py`
grows savable, replayable scene frames (their Target Play, our engine).
Milestone: run a scene three ways, save the frame, replay it, diff the
branches in the journal.

**Phase 4 — Ensemble scenes.**
`chat.py` grows multi-companion sessions; the simulator stages them as
scenes with turns. Companions carry distinct memories of the owner and
each other. Milestone: 3-companion scene runs, turns attributed, ledger
correct per companion.

**Phase 5 — Wellness rituals.**
`wellness.py` grows check-ins, journaling prompts, care streaks, with
the not-a-therapist boundary in code and in copy. Milestone: a 7-day
ritual demo with honest-scope copy reviewed.

**Phase 6 — Honest identity surface.**
`photos.py` grows beat-triggered procedural art reveals and the avatar
seed renderer (declared scope, never photorealism claims). Milestone:
avatar seed determinism test — same seed, same render.

**Phase 7 — Personal retrospective.**
Ledger → private "your story so far": arcs, scenes, rapport earned,
characters grown. Local only, exportable by owner choice. Milestone:
generated from a real ledger, no invented beats.

**Phase 8 — Owner's studio tooling.**
CLI for create/edit/import/export of companions and scene frames;
backup + restore of the whole companion corpus. No public library, no
sharing, no publishing — unless Chauncey orders it.

### Gated on Chauncey (nothing moves without his word)

- Any pricing: the standing project decision is the Trio $3 one-time
  direct sale (his 2026-09-21 call, his to change) — Echoverse pricing
  waits on that settled word.
- Any customer release or distribution of any kind.
- Any cloud account, any account system, any sync.
- Any public companion library or publishing surface.
- Voice: no third-party voice service enters the pipeline without him.
- Photorealistic/owned-backend imagery: stays open as a question, never
  assumed.
- Anything with legal surface (age policy copy, terms, payouts).

### Hard nos (standing, not negotiable)

- Never merge with Plaiground's adult track — Phase 0 tests enforce it.
- No cloud accounts. No ads. No analytics. No subscription meter.
- No routing to third-party model brains ("only our stuff").
- No silent policy moves: bounds change only as a version, in the open.
- No public-by-default anything: private by default, always.
- No therapy claims, ever; wellness stays in its honest lane.

### Honest limits

- Voice slots / calls: roadmap, not now (third-party voice needs his
  word; offline TTS stays an open question).
- Photorealistic avatars: out of scope for the procedural backend; we
  don't claim them.
- Mobile presence: the competitors are app-first; our build order is
  engine-first, surface later, and only on his word.
- The competitors' primary pricing/policy pages were not verified
  firsthand — the teardown is secondary-source honest, marked as such.
