# KFX² on the AI writing editors — Sudowrite, NovelAI: absorb, reverse, improve, return unreplicable

Date: 2026-09-21. Target workstream 9 of 13: L.W.P. WRITING ENGINE KFX² + production plan.
Order: "absorb the outside pattern — strengths as well as weaknesses — reverse it, improve it, return a version only we could build."

Our core is untouchable: local-first (runs persist in `~/.levi/lwp_machine/`,
never leave the device), the five-seat press line (ideation → drafting →
revision → polish → publish_ready) gated by the binding rail (Plan →
Preview → Permission → Execute → Verify → Receipt), stdlib-only kernel,
deterministic tooling, mythos-as-poetry (never smuggled into architecture
claims). What we take from them is the *craft surface* — rebuilt on our
physics.

Scope note: competitor facts below come from public review/directory
sources (Sept 2026). Everything is marked to the source's confidence.
Nothing here was verified against the vendors' live pricing pages; confirm
there before quoting to anyone.

## (a) COMPETITOR TEARDOWN

### Sudowrite — the fiction specialist

**What it is (well-attested):** AI writing assistant built specifically
for novelists and fiction writers. Its in-house **Muse** model (per
reviews, "Muse 1.5," trained for fiction rather than general use) is
consistently praised as producing some of the most natural fiction prose
of any hosted tool.

**Features (well-attested across reviews):**
- **Story Bible** — characters, worldbuilding, synopsis, outline,
  "braindump" of ideas; the AI references it for consistency across long
  projects. Story Engine guides premise → outline.
- Craft tools: **Write** (continue the scene in your voice), **Rewrite**,
  **Expand**, **Describe** (sensory detail), **Brainstorm**, **Feedback**,
  **Twist Generator**, First Draft.
- **Canvas** — visual corkboard for plotting/worldbuilding.
- **Visualize** — AI art from descriptions (unverified scope/quality).
- **Plugins** — user-made and community plugins (e.g. simulated readers,
  character conversations, genre advice); custom workflows.
- **Match My Style** (voice matching from your samples).
- Integrations: Google Docs, Chrome extension, Scrivener import for
  existing drafts, Zapier, Grammarly (per aggregators — could not verify
  first-hand).
- Mobile: iOS/Android companion app (per Kindlepreneur review, 2026) —
  Write and Rewrite, Smart Dictation, Chat; companion, not a replacement.
- Discord community, live classes; "built by writers" positioning.

**Pricing (from secondary sources, Sept 2026 — not verified on vendor page):**
- Free trial: 10,000 credits, no time limit, no card required (widely
  reported; no permanent free plan).
- Hobby & Student: $19/mo ($10/mo billed annually) — 225,000 credits/mo.
- Professional: $29/mo ($22/mo annual) — 1,000,000 credits/mo.
- Max: $59/mo ($44/mo annual) — 2,000,000 credits/mo, 12-month rollover
  on unused credits.
- Credits expire monthly on the two lower tiers. One review estimates
  225k credits ≈ 6k–15k words on premium models — could not verify the
  credit→word math first-hand.

**Content policy / privacy:** mainstream, filtered. Reviewers describe
corporate filters (the contrast with NovelAI's "natively uncensored"
posture is the constant frame). Details of the policy text: could not
verify.

**What writers love (consistent across sources):** fiction-native prose;
Story Bible and guided workflow; Describe tool; distraction-free UI and
themes; plugins; community; Scrivener import.

**What writers hate (consistent across sources):** the credit system is
the #1 complaint — "credit anxiety," caps hit before act two is done,
credits expire monthly. Story Bible has to be built by hand (manual data
entry from an existing manuscript is "irritating"). Continuity still
needs manual discipline (POV/tense, upkeep). Too many tools, scattered
non-linear workflow, learning curve. Exports are basic (.docx/.zip) and
— tellingly — the Story Bible is *not* in the project export: the
world's memory belongs to their cloud, not the writer. One Medium review
complains the Story Engine acts like an "equal partner," adding
characters and plot turns unprompted — the writer felt authorship slip
away with no way to rein it in.

### NovelAI — the unlimited marathon runner

**What it is (well-attested):** story + anime-image AI platform since
2021, running its own fine-tuned models. Positioning: permissive,
uncensored text ("natively uncensored"), unlimited drafting.

**Features (well-attested):**
- **Lorebook** — the always-open series bible: tagged entries (character
  secrets, world facts) that get injected into context automatically.
  Its memory is the celebrated feature.
- Text modes: **Storyteller** and **Text Adventure** (per reviews).
- Memory context tiers by plan (see pricing).
- **Modules** (worldbuilding/world styles; per a comparison piece).
- **Built-in image generation** (diffusion panel, anime style; Vibe
  Transfer style matching, Image2Image, prompt tags or natural
  language). Only tool in the roundups with words + art in one tab.
- Fine-grained controls: randomness sliders, repetition penalties,
  story bias, samplers/CFG/steps exposed — studio-gear learning curve.
- Text-to-speech playback on Scroll+ (per one source — could not verify
  first-hand).

**Pricing (from secondary sources, Sept 2026 — not verified on vendor page):**
- Free trial: 50 text generations; 30 free image generations
  (sources disagree on whether both apply — could not verify).
- **Unlimited text generation on every paid tier** (rare; widely
  reported). You pay for memory/features, not words.
- Tablet: $10/mo — 3,072-token context, 1,000 Anlas image credits/mo.
- Scroll: $15/mo — 6,144-token context, 10,000 Anlas/mo per one source
  (1,000 per another — could not verify), voice playback.
- Opus: $25/mo — 28,672 + 8,192 rollover tokens, biggest models (Erato
  70B and Xialong 355B MoE per one source — could not verify), 10,000
  Anlas/mo, effectively-unlimited standard 1024×1024 / 28-step images.
- Images metered by **Anlas** (internal credit); yearly billing trims
  roughly a third. Anlas top-ups purchasable outside the subscription.

**Content policy / privacy (could not verify the policy text first-hand,
but the posture is consistent):** marketed as "natively uncensored" text
and unfiltered art; writers praise the freedom to write dark/taboo
themes without toggles. Privacy: ToS;DR carries an APPROVED case quoting
their policy — "Content stored on our servers is encrypted and you bear
the decryption key in the form of your password and email address" —
i.e. encrypted-at-rest with the user's credentials as key, but generation
still runs on their servers. A third-party explainer blog (not the vendor)
claims browser encryption, could not verify.

**What writers love:** unlimited drafting (no word caps, no anxiety);
Lorebook continuity ("tag a protagonist's secret tattoo once and it
echoes through later chapters"); the permissive posture; anime art in
the same tab; price per scene for prolific authors.

**What writers hate:** dense interface (sliders, penalties, sampling —
"tedious on day one"); its own models are smaller than frontier LLMs and
it shows in complex plotting; anime-locked image style; web-only.

## (b) KFX² — ABSORB / REVERSE / AMPLIFY

### ABSORB — their best craft patterns, taken and rebuilt

1. **Sudowrite's Story Bible + NovelAI's Lorebook.** Two shapes of the
   same good idea: the world's memory, always referenceable. We absorb
   the *concept* into our existing `lwp/character_graph.py` as the
   **living bible** — but ours is built FROM the manuscript, not keyed
   in by hand: the press reads your draft and proposes characters,
   world-rules, timeline entries; you confirm them. Reversal of the
   drudgery: they make you re-enter what's already on the page; we read
   the page.
2. **Sudowrite's craft tools — Write, Rewrite, Expand, Describe,
   Brainstorm, Feedback, Twist.** Absorb the verb set, not the meter.
   These become deterministic seat tools in the press line (drafting /
   revision / polish seats), each gated by the binding rail. "Rewrite"
   is a press operation; "Feedback" is mandella's honest mirror, which
   we already built.
3. **Canvas corkboard.** Their visual plotting board becomes our
   story-fabric view — already in canon as a King control-plane
   concern; keep it local, keep it deterministic.
4. **Match My Style / voice training.** Absorb as *voice lock*: the
   press samples your prose into a style sheet that rides with the
   bible — versioned, inspectable, deletable. Stated plainly as
   pattern-matching, never "it knows your soul."
5. **NovelAI's Text Adventure / Storyteller modes.** Absorb as genre
   modes (we already carry 97): the press shifts seat behavior per
   mode — noir desk is not rom-com desk.
6. **Plugins.** Absorb the community-craft-shelf idea as deterministic,
   reviewable plugins — code the writer can read, not rented model
   prompts. Writers share tools, never manuscripts.
7. **Scrivener import / docx export.** Interchange is a craft
   requirement: we meet writers where their manuscripts live and let
   them leave with everything, bible included (the export Sudowrite
   refuses to give).
8. **NovelAI's image-in-the-same-tab loop.** Absorb as beat-triggered,
   honest-scope art: tarot/card/spread imagery and scene plates, stated
   as procedural art, never photorealism claims (same honest scope as
   the CrushOn KFX² beat-art).

### REVERSE — their weaknesses, flipped into our physics

| Their failure | Our reversal |
|---|---|
| Sudowrite's credit anxiety — caps before act two, credits expire monthly | No word-credit metering exists in our architecture. Local engine, no marginal generation cost — buy once, write forever |
| Cloud manuscript storage; NovelAI's "we can't read it" still runs generation on their servers | The manuscript never leaves the device. No server, no training harvest, no encryption promises needed — there is nothing to promise |
| Story Bible NOT in Sudowrite's export — the world's memory belongs to their cloud | The bible is a local file. Full export always, bible included, in open formats |
| Story Engine seizing authorship — characters/plots added unprompted, writer can't rein it in | The binding rail: every consequential act halts for the human. The press proposes; the writer disposes. Drafting always halts — that's the law, not a setting |
| Manual Story Bible entry drudgery | Living bible auto-built from the manuscript, writer-confirmed |
| Long-form continuity collapse (both of them, tier-gated context windows) | Character graph + timeline + genre state persist locally with no context-window ceiling to rent back from us |
| NovelAI's dense studio-gear UI | The void: one focused surface, dark-first, the seat tools as verbs — no sliders until you ask for them |
| Generic prose / model roulette / quiet policy changes | Deterministic tools + local models + the bounds law in code. The prose is yours; the policy is written down and does not move |

### AMPLIFY — their strengths, made unreplicable by our architecture

1. **Their AI co-writer → the engine where the world itself has
   memory.** Sudowrite's Story Bible is a reference file you key in;
   NovelAI's Lorebook is keyword injection into a rented context
   window. AMPLIFY: our living bible — characters, timelines, and
   **tarot/mythic structures** — persists locally across books, series,
   and years as first-class objects. Major-arcana arcs as plot frames,
   spreads as scene architecture, the world graph as a durable artifact
   no cloud editor can hold without harvesting the manuscript.
   UNREPLICABLE: their memory is a cloud feature metered by tier; ours
   is a file on the writer's machine. They cannot ship ours without
   deleting their revenue model; we cannot help but ship it.
2. **Their per-word meter → ownership economics.** Sudowrite sells
   words; NovelAI sells context. AMPLIFY: one honest price, stated
   plainly, no recurring word rent — the deterministic/local engine has
   no marginal cost, so the scarcity they monetize is *unnecessary
   physics* for us. Return to sender: everything they sell as scarcity
   (credits, context tiers, unlimited-as-a-plan) we ship as physics.
   UNREPLICABLE: their investors demand the meter; our architecture
   forbids it. (Pricing itself is Chauncey's call — gated.)
3. **Their guided workflow → the press line as ritual.** Their Story
   Engine walks you through structure; AMPLIFY into the five-seat line
   (alpha/levi/echo/mandella/omega) with the gates as the product: a
   publishing process with receipts, where "publish" requires a human
   seal, twice. UNREPLICABLE: cloud tools optimize for engagement;
   ours optimizes for the finished manuscript. Different gods.
4. **Their unfiltered posture → the writer's own bounds.** NovelAI's
   lane is "the models don't refuse." AMPLIFY: deterministic,
   writer-controlled bounds — the content decisions are the writer's,
   in code they can read, on a machine they own, never a stranger's
   model changing its mind mid-chapter. UNREPLICABLE: their posture
   depends on which model they route to today; ours is a switch in the
   writer's hand that never moves under them.
5. **Their community plugins → the craft shelf.** AMPLIFY: plugins as
   reviewable, deterministic, shareable code in the L.W.P. plugin
   contract (see `lwp/premium_craft.py`) — writers trade tools the way
   woodworkers trade jigs. UNREPLICABLE: their plugins are prompts
   rented on their cloud; ours run offline and are inspectable, so a
   writer can trust a tool with their manuscript without handing the
   manuscript to anyone.

### Positioning — the uproar doctrine (Chauncey, 2026-09-21)

Chauncey's positioning law: we offer what they do, what they don't, and
do it even better — at a fraction of their fraction. The slate matches
every competitor feature-for-feature PLUS what they never offered,
built better, at radically lower prices. Dollar-scale entry, volume
over margin.

**Competitor features → our parity (drawn from the teardown above):**
the world's memory (Sudowrite's Story Bible, NovelAI's Lorebook — our
living bible, auto-built from the manuscript you already wrote); the
full craft verb set (Write, Rewrite, Expand, Describe, Brainstorm,
Feedback, Twist — our press-seat tools, each gated, none metered); the
visual corkboard (their Canvas, our story-fabric view); voice matching
(their Match My Style, our versioned, inspectable voice lock);
exploratory modes (their Text Adventure / Storyteller, our 97 genre
modes and seat behaviors); plugins (their cloud-prompt plugins, our
deterministic reviewable craft shelf); docx / Scrivener interchange;
and the image-in-the-same-tab loop (their diffusion panel, our
beat-triggered honest-scope art, procedural, never photorealism
claims). Every tool they offer, rebuilt on local physics.

**Competitor gaps → our exclusives:** the bible is built FROM your
manuscript, not keyed in by hand — and it leaves with you in every
export (Sudowrite refuses to export its Story Bible); the binding rail —
the press proposes, the writer disposes, and no Story Engine ever adds
a character or plot turn unprompted; the manuscript never leaves the
device, so no credit system, no context-window tier to rent back, no
training harvest to disclaim; mythic structure (arcana arcs, spread
frames) as stated craft aids; no context ceiling on continuity — the
character graph persists across books and years as a file you own.

**Our price as a fraction of theirs:** ours — one honest price, stated
plainly, no recurring word rent; the number is Chauncey's call and
gated (not set in this doc). Theirs — Sudowrite Hobby & Student
$19/mo ($10/mo annual), Professional $29/mo ($22/mo annual), Max
$59/mo ($44/mo annual); NovelAI Tablet $10/mo, Scroll $15/mo, Opus
$25/mo — all from secondary sources, Sept 2026, none verified on the
vendors' live pricing pages. The doctrine framing: their floors start
where our one-time price is meant to end — and their meters keep
running every month after.

## (c) PRODUCTION-PHASE PLAN

Docs only. No code, no commits. Build phases below are sequenced for a
single builder; each phase ends with a milestone that can be demoed to
Chauncey.

**Phase 0 — Living bible core (foundation, no gates).**
- Extend `core/levi/lwp/character_graph.py`: characters, relationships,
  world-rules, timeline events as a durable local store beside the
  press ledger (`~/.levi/lwp_machine/`).
- Manuscript ingestion: read the writer's existing draft, propose bible
  entries, writer confirms each (reject-all is one key).
- Milestone: brief a test manuscript, watch the bible populate, export
  it and read it as plain data.

**Phase 1 — The verb set (craft tools).**
- Press-seat tools: Continue, Rewrite, Expand, Describe, Brainstorm,
  Feedback, Twist — each a discrete, inspectable operation on the
  draft, each gated by the binding rail where consequential.
- Voice lock: style-sheet sampling from the writer's prose,
  versioned and deletable.
- Milestone: a full revision pass (draft → revise → polish) with
  receipts on every tool invocation.

**Phase 2 — Mythic structure as craft (poetry, stated plainly).**
- Tarot/mythic plot frames: spreads as scene architecture, arcana as
  arc patterns — presented in the tool as *patterning aids the writer
  applies*, never as engineering claims. The honesty rule holds in the
  UI copy too.
- Genre modes (97) wired into seat behavior; Text-Adventure-equivalent
  exploratory mode.
- Milestone: one short story built end-to-end on a spread frame, bible
  and manuscript exported.

**Phase 3 — Interchange and the surface.**
- Import: docx, Scrivener-ish structure; Export: docx/epub,
  bible-included (the export Sudowrite won't give).
- Story-fabric/canvas view of the manuscript (local, deterministic).
- Beat-triggered honest-scope art for cards/spreads/scenes.
- Milestone: round-trip a manuscript in from another tool and back out
  with the bible intact.

**Phase 4 — Craft shelf (community without the cloud).**
- Deterministic plugin contract for writer-built tools; share the
  tool, never the manuscript.
- Milestone: two writer-built plugins running offline.

### GATED ON CHAUNCEY (nothing moves without his word)

- Any pricing (the ownership-model price is his number; house rate law
  from PL-05 applies to creator/marketplace cuts only if he sets it).
- Any customer release, beta, or waitlist — with the five specifics per
  action (destination, scope, account, copy, media).
- Any cloud touch whatsoever (sync, backup, collaboration) — default is
  never; if he ever asks, re-audit this whole doc first.
- Any fine-tuning on writer manuscripts, even local — default is no.
- Scope of the art backend (procedural vs any external synthesis).
- The mobile-companion question (Sudowrite has one; ours stays a
  decision, not an assumption).

### HARD NOS

- **No cloud training on manuscripts. Ever.** Not ours, not a
  partner's, not "anonymized." The writer's work stays the writer's.
- **No word-credit metering.** No credits, no tiers-by-words, no
  expiring allowances. Our cost structure makes the meter unnecessary,
  and unnecessary punishments don't ship.
- **Mythos is poetry, never engineering fact.** Tarot structures are
  craft tools with honest labels. No "the spread knows," no
  sentience-adjacent claims about the press, no poetry smuggled into
  architecture.
- **No authorship seizure.** The press never adds characters, kills
  darlings, or steers plot without the writer. Proposals are proposals;
  the gates are the law.
- **No model roulette.** No silent model swaps under the writer; the
  engine under a manuscript is named, versioned, and disclosed.
- **No training on user text without explicit, revocable, per-action
  consent** — and the default answer to the question is still no.

## Honest limits

- All competitor pricing and feature details are from public
  secondary sources, Sept 2026; nothing verified against live vendor
  pages. Treat numbers as directional until confirmed.
- NovelAI's encryption claim rests on a ToS;DR case quoting their
  policy; the actual implementation was not audited.
- Sudowrite's Visualize scope/quality and integration claims (Zapier,
  Grammarly, Scrivener depth) are aggregator-reported, could not
  verify first-hand.
- The local inference quality bar for fiction prose (the thing
  Sudowrite's Muse is genuinely good at) is the real technical risk
  of this plan — the bible and gates are structural wins regardless,
  but prose quality needs the native-brain campaign to keep turning.
- No external model routing, ever — "only our stuff" forbids renting
  their brains to power the press.
