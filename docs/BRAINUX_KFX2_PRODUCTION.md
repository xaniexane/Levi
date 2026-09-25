# KFX² on the model-runners — Ollama, LM Studio, Jan (offline brain + void-theme UX)

Date: 2026-09-21. Workstream 6 of 13.
Frame: Chauncey's KFX² law — absorb their strengths as well as their weaknesses,
reverse them, improve them, return a version only we could build. Strengths
amplified, not just weaknesses reversed (per the giants-doc correction).

Standing context: LEVI's native brain is trained from scratch on its own corpus
(tiny-gpt weights, explicit-only, local). A 600-step continued-training campaign
with checkpointing is IN MOTION — this plan does not touch training. End goal,
his words: LEVI ships its own Ollama-style model-runner so LEVI itself becomes
a model — local-first, no mask, no persona. Web UX direction: dark-first 'void'
theme, streaming chat, register switcher; warmth/clarity blended with bold dark
playful energy and calm precision.

Sources below are public secondary sources (reviews, comparison guides, project
docs found via search). Anything not verifiable is marked [UNVERIFIED] — no
feature, price, or number in this doc is invented.

---

## (a) Competitor teardown

### Ollama — the one-command runner
- **What it is:** free, MIT-licensed open-source tool that downloads, manages,
  and runs open-weight LLMs locally with one command (`ollama run llama3.3`).
  De facto standard for local LLM inference; ~90,000+ GitHub stars cited in
  secondary guides. Wraps llama.cpp (and Apple's MLX on Mac since v0.19).
- **Features:** CLI-first; REST API on port 11434, OpenAI-compatible; model
  library with custom Modelfiles; handles quantization, GPU allocation, context
  sizing automatically. Fastest startup (pre-loaded daemon). Best ecosystem
  compatibility — most local-LLM tooling speaks Ollama. Excellent on macOS
  (Apple Silicon) and Linux; solid on Windows. Works fully offline once a model
  is downloaded.
- **Pricing:** free, open source. [SECONDARY SOURCE CLAIMS] a Cloud tier exists
  (fundesk table lists "Free (Cloud tier available)") — [UNVERIFIED] details,
  pricing, and whether it requires an account could not be confirmed.
- **Hardware:** 16 GB RAM minimum, 32 GB for anything past 13B parameters;
  5–20 GB disk per model; GPU helps (NVIDIA CUDA, AMD ROCm/Vulkan, Apple Metal/MLX)
  but CPU runs small models.
- **Users love:** zero marginal cost, complete privacy, no rate limits, drop-in
  API for scripting and agents, lowest-friction entry point ("lowest regret").
- **Users hate / weak spots:** terminal-first design is a learning curve for
  non-developers; **no built-in chat UI** (needs a separate frontend like Open
  WebUI); **no built-in visual model browser** — model discovery means
  memorizing names or browsing the registry site separately; a VRAM memory leak
  was widely reported in 2026 builds (per one Medium guide — [UNVERIFIED]
  whether fixed); not built for high-concurrency production serving (vLLM
  claimed 16–20× faster under load — [UNVERIFIED] benchmark).
- **Posture:** local-first by default, developer-oriented, infrastructure-not-app.

### LM Studio — the desktop playground
- **What it is:** polished desktop GUI (Electron) for discovering, downloading,
  and running local LLMs, aimed at daily desktop chat. Closed source;
  proprietary.
- **Features:** built-in Hugging Face model browser, described as hardware-aware;
  one-click model download with progress/queue tracking; clean ChatGPT-like
  chat UI with **streaming tokens and real-time metrics** (tok/s, VRAM/GPU
  usage); conversation branching from specific messages, chat cloning, notes;
  vision model support with image attachments; structured output (JSON schema);
  parameter sliders (temperature, GPU offload layers, context length, batch
  size); pre-load configuration; themes (Dark, Light, Sepia, System);
  automatic GPU detection and offload distribution; local OpenAI-compatible
  server (port 1234); CLI at `~/.lmstudio/bin/lms`. 2026 addition: **Bionic
  Agent** — a local agent that works on documents/research with review
  checkpoints and inline previews (per webpronews; early users report rough
  edges, slower model loading, manual working-directory setup).
- **Pricing:** free for personal use; **Enterprise plan available**
  ([UNVERIFIED] pricing/terms could not be confirmed). [SECONDARY SOURCE CLAIMS]
  "no telemetry — fully local-first operation" (research notes repo) —
  [UNVERIFIED] against their official privacy policy.
- **Hardware:** same envelope as Ollama territory — 16 GB RAM min realistic,
  32 GB for larger models; Electron app is heavier than CLI alternatives.
- **Users love:** lowest learning curve ("click Download, drag a temperature
  slider, start chatting"); persistent chat history; live performance metrics;
  the most complete day-30 daily-use experience among the three.
- **Users hate / weak spots:** feels heavy/sluggish (Electron overhead);
  higher resource consumption than Ollama; model discovery is "not intuitive"
  — the Discover tab wants a typed search, not real browsing; fresh installs
  reportedly ship outdated inference runtimes so new architectures won't load
  until updated; default GPU-offload settings can push users into slow shared
  memory (XDA 2026); loader crashes mid-offload when VRAM runs out ("Exit code:
  null"); closed source invites skepticism from the open-source community it
  serves. Desktop-only — no server-grade story, no mobile.
- **Posture:** local-first daily driver, non-developer friendly, but proprietary
  binary with a paid enterprise tier.

### Jan — the open-source all-rounder
- **What it is:** free, open-source (AGPL) desktop AI assistant for Windows,
  macOS, and Linux. ChatGPT-like UI that runs models 100% offline.
- **Features:** Hub tab (model library, download models), Chat tab
  (conversations stored locally); multi-engine inference (own Cortex engine +
  llama.cpp reported — [UNVERIFIED] current engine status); local
  OpenAI-compatible server (port 1337); built-in extensions; no account
  required; [SECONDARY SOURCE CLAIMS] no telemetry and no cloud dependency
  (makeuseof, Jan's own docs) — [UNVERIFIED] against current builds. Notably
  also supports remote APIs (OpenAI, Anthropic) if the user opts into cloud —
  local by default, cloud as an explicit choice.
- **Pricing:** free, open source (AGPL). [UNVERIFIED] whether any paid tier,
  hosted offering, or commercial licensing exists.
- **Hardware:** same class as the others; 8 GB machines can run 7B–8B
  quantized models at 15–25 tok/s per one guide ([SECONDARY SOURCE]);
  14B-class quality wants 16 GB+.
- **Users love:** true open-source + no-account + airgap-capable privacy;
  the local/remote toggle without giving up the local default; beginner FAQ
  and same-feature parity across OSes.
- **Users hate / weak spots:** hardware ceiling is the whole product story —
  you're limited to what your machine can run, and open models still trail
  cloud flagships on complex reasoning (10–15% gap cited for straightforward
  tasks, noticeably worse for multi-step logic — [SECONDARY SOURCE] estimate);
  inference can slow the machine during use; some reports of thinner
  documentation and feature rough edges vs LM Studio polish.
- **Posture:** the privacy-maximalist desktop client; local by default with a
  voluntary cloud escape hatch.

### Cross-cutting patterns (all three)
- Everyone converges on an OpenAI-compatible local server — that's the
  interop standard, not a differentiator.
- The real cost is always hardware: 16 GB RAM floor, 32 GB for the good
  stuff, 5–20 GB disk per model. Nobody escapes this.
- UX splits by audience: Ollama = developers/infrastructure, LM Studio =
  daily desktop chatters, Jan = privacy-first open-source users.
- Model discovery is universally weak: typing names, registry sites, or a
  search tab — nobody has made browsing models feel good.

---

## (b) KFX² — absorb, reverse, amplify, return unreplicable

### ABSORB — their patterns worth taking

1. **Ollama's one-command run.** `ollama run <model>` collapsed a weekend of
   CUDA errors into a single verb. We absorb the *ceremony of arrival*: one
   command, one daemon, tokens on screen, no setup theatre. Our form:
   `levi mind` — one command that starts the runner AND the organism's own
   brain, because for us the model and the machine are the same thing.
2. **LM Studio's hardware-aware browser.** They match models to the machine
   before download. We absorb it as the organism's honesty about its own body:
   LEVI already knows its host — it should say, before anything runs, what
   fits in this RAM, this disk, this CPU, in plain words, not a spec table.
3. **LM Studio's streaming surface.** Streaming tokens + live tok/s + VRAM
   readout is the difference between "tool" and "alive." We absorb streaming
   as baseline and pair it with our void theme and register switcher —
   their playground, our atmosphere.
4. **LM Studio's conversation instruments.** Branching, cloning, notes on a
   chat — small features that respect long work. We absorb them into the
   journal/depth layer, where they stop being chat tricks and start being
   the relationship ledger.
5. **Jan's no-account airgap posture.** No account, no telemetry, local by
   default — the posture Chauncey already chose for LEVI. We absorb their
   proof that it ships: a daily driver with zero sign-in can still be
   pleasant. Their cloud escape hatch is the one pattern we do NOT absorb
   (see hard nos).
6. **The OpenAI-compatible local server.** The interop standard. Absorb it as
   the runner's outer face so every existing local-LLM tool can talk to LEVI
   — while the inner face stays ours.

### REVERSE — their weaknesses, flipped into our strengths

| Their failure | Our reversal |
|---|---|
| RAM/VRAM hunger with opaque failure (mid-offload crash, "Exit code: null") | The runner reports the body's limits in plain speech BEFORE load; graceful refusal instead of a crash. Deterministic sizing, no roulette. |
| Model discovery = memorizing names / typing in a search box | The brain is not one of a thousand models to browse — it IS the mind. Discovery collapses to one question: which growth of LEVI do you want? No registry spelunking. |
| Cloud-account creep (Ollama's cloud tier, LM Studio Enterprise) | No cloud tier exists to creep toward. There is no account, no upsell tier, no server to phone home to — the architecture has no place for it. |
| Opaque model provenance (whose weights, trained on what, quantized by whom) | Our provenance is total: trained from scratch on our own corpus, on our own machines, intake-filtered by the nine-teacher data machine. Every weight traceable to our own records. |
| Heavy Electron shells, sluggish day-30 UX | The void-theme web surface is one light client against the daemon; the daemon is stdlib-only and always-on, not a browser in a trench coat. |
| Split brain: runner is infrastructure (Ollama) OR app is chat (LM Studio/Jan), never one thing | Ours is one organism. The runner and the mind share a bloodstream — growth loop, journal, memory, and inference are the same process, not three products duct-taped together. |
| Their cost structure = hardware lottery + metered cloud | Our cost structure = one honest machine + our own weights. No per-message meter exists; deterministic components have no marginal cost. |

### AMPLIFY — their strengths, made unreplicable

1. **Ollama's simplicity → LEVI-as-model.** They made running *someone else's*
   model one command. We amplify: the runner and the mind are one organism —
   `levi mind` doesn't download a brain, it *is* the brain waking up. They
   cannot build this without becoming what they sell; their whole value is
   being the neutral pipe for other people's weights. UNREPLICABLE because
   their neutrality is their business — a pipe can't be the mind inside it.
2. **LM Studio's playground → the void-theme streaming surface with the
   register switcher.** They made the playground pleasant for everyone. We
   amplify into a surface only we would build: dark-first void, streaming
   chat, and the register switcher — the warmth/clarity × bold-dark-playful ×
   calm-precision blend Chauncey specified — wired into the growth loop so
   the chat visibly matures with the organism (newborn → maturing as a
   function of learnings, shown honestly, not as a gimmick).
   UNREPLICABLE because their surface is a chat client; ours is the skin of
   a growing organism. A client can't grow.
3. **Jan's airgap purity → our already-declared physics.** They proved
   no-account, no-telemetry, local-by-default ships as a daily driver. We
   amplify: we go further — not just local by default but local as law (see
   hard nos), with the growth journal and teacher intake proving the mind
   improves *without ever leaving the machine*. They sell privacy as a
   feature; we sell a mind that only exists inside its own walls.
   UNREPLICABLE because every competitor keeps the cloud door as an escape
   hatch; we bricked the door and built the whole house behind it.
4. **The hardware-honesty gap → plain-speech body awareness.** None of the
   three tells a normal human what will actually run on their machine before
   it crashes. We amplify into a standing instrument: LEVI states its body's
   limits in plain speech and refuses gracefully. Their docs are spec tables
   for the already-converted; our surface is for the person who just wants
   to know "will it work on my phone." The phone story (Termux + Acode,
   $5-phone/Chromebook sync-storm world) is ours to own — none of the three
   ships a real mobile-local story.

### Return to sender
Everything they gate behind hardware lottery, cloud tiers, or registry
hunting, we ship as physics: the mind is one, the body is honest, the
surface is the skin, the growth is local. Their compromises exist to pay
for *their* architecture — neutral pipes, rented weights, metered clouds.
Ours doesn't have those costs, so it doesn't have those punishments.

---

### Positioning — the uproar doctrine (Chauncey, 2026-09-21)

Chauncey's positioning law: **we offer what they do, what they don't, and do
it even better, and for fraction of fractions.** The slate matches every
competitor feature-for-feature plus what they don't offer, better built, at
radically lower prices. Dollar-scale entry, volume over margin.

**Competitor features → our parity.** Everything the three do right is in
this plan: Ollama's one-command run becomes `levi mind`; the OpenAI-compatible
local server stays as the outer face so existing tooling talks to LEVI;
LM Studio's streaming chat with live tok/s and VRAM readout is absorbed as
baseline; hardware-aware fitting is kept and made plain-spoken instead of a
spec table; LM Studio's conversation instruments (branching, cloning, notes)
arrive wired to the journal/depth layer; Jan's no-account, no-telemetry,
airgap-capable posture is the standing default.

**Competitor gaps → our exclusives.** What none of them sells: the runner and
the mind as one organism — `levi mind` doesn't download a brain, it *is* the
brain waking up (a neutral pipe can't be the mind inside it); the growth
loop made visible in the chat surface, the mind visibly maturing with the
user; total provenance — trained from scratch on our own corpus, on our own
machines, intake-filtered by the nine-teacher data machine; deterministic
sizing with graceful refusal in plain speech instead of mid-offload crashes;
and local as law, not default — no cloud tier, no account, no upsell door at
all. None of the three ships a real mobile-local story; our phone story
(Termux, Acode, $5-phone/Chromebook floor) is ours to own.

**Our price as a fraction of theirs.** All three competitors are free at the
personal tier (Ollama MIT, LM Studio free for personal use, Jan AGPL free —
Enterprise/paid-tier details [UNVERIFIED] across the board), so this document
states no paid competitor price to undercut: **competitor price not verified
in this document.** Ours: this plan sets no price anchor and no meter — no
seats, no tiers, no per-message anything. There is no cloud bill, no metered
API, no rented weights to pass on, so the dollar-scale-entry law (volume over
margin) holds by architecture when Chauncey names the entry price.

---

## (c) PRODUCTION-PHASE PLAN

Sequenced build order. Docs only — no code, no commits in this plan.
Training pipeline is OUT OF SCOPE (600-step campaign in motion; the
nine-teacher data machine feeds it — this plan never touches either).

### Phase 1 — Runner interface (`levi mind`)
Goal: the one-command ceremony. A local daemon that loads the native
brain weights and serves them — OpenAI-compatible local server as the
outer face, organism plumbing as the inner face.
- Milestone 1.1: daemon skeleton — start/stop/status, stdlib-only,
  config at `~/.levi/mind/`, offline-mandatory (refuses to start with
  network inference paths enabled).
- Milestone 1.2: weights loading — load the tiny-gpt weights explicitly
  (explicit-only, as today); plain-speech body check before load
  (RAM/disk/CPU → "fits / doesn't fit, here's why").
- Milestone 1.3: local server — OpenAI-compatible `/v1/chat/completions`
  and `/v1/models` on localhost, so existing local-LLM tools can talk
  to LEVI; inner API stays organism-native.
- Milestone 1.4: graceful degradation — CPU fallback, smaller-context
  modes, honest refusal when the body can't hold the mind. No silent
  crashes, no "Exit code: null."
- Gate: none technical; Chauncey demo on his own machines before any
  wider claim of "LEVI is a model."

### Phase 2 — Brain packaging (LEVI-as-model)
Goal: the brain ships as a sealed, honest artifact — provenance you can
audit, not a black-box download.
- Milestone 2.1: packaging format — weights + training manifest
  (corpus snapshot hash, teacher-intake log, checkpoint lineage,
  eval scores) in one signed bundle. Every bundle says what it was
  trained on and what the evals measured.
- Milestone 2.2: one-command install — `levi mind pull` semantics
  against OUR bundles only; no third-party weight ingestion, ever.
- Milestone 2.3: update story — brain updates arrive as new sealed
  bundles with the manifest diff; rollback to the previous bundle is
  one command; the old brain is never deleted, it's composted
  (recycled-potential law — logs and manifests kept).
- Gate: **Chauncey.** Any distribution of brain bundles outside his
  machines — private link, public release, any channel — needs his
  five specifics per action (destination, scope, account, copy,
  media). Publication hold stands.

### Phase 3 — Void-theme web UX
Goal: the dark-first streaming surface — the skin of the organism.
- Milestone 3.1: void theme foundation — dark-first CSS system,
  streaming chat over the local daemon, register switcher
  (warmth/clarity × bold-dark-playful × calm-precision).
- Milestone 3.2: growth made visible — the chat surface reflects the
  developmental stage (newborn → maturing) honestly from the growth
  journal; conversation instruments absorbed (branching, cloning,
  notes) wired to the journal/depth layer, not a chat-client bolt-on.
- Milestone 3.3: body-awareness UI — plain-speech hardware readout in
  the surface ("your machine holds the mind at X tok/s"), streaming
  metrics (tok/s) like LM Studio's, minus the spec-table gatekeeping.
- Milestone 3.4: bottom-nav tab shape — per the Hub product definition,
  the pattern of a first-class LEVI tab; the web surface is the front
  door, the bloodstream is the house.
- Gate: any hosted/public deployment of the web surface is a release —
  **Chauncey's five specifics**, same as brain bundles.

### Sequencing notes
- Phase 1 and Phase 3 can overlap (runner ↔ surface are independent
  until integration); Phase 2 depends on Phase 1's loader.
- The 600-step training campaign and the nine-teacher data machine run
  on their own track — this plan consumes their outputs (weights,
  manifests) and never interrupts them.
- Forward-motion rule: while any milestone waits on Chauncey, work
  moves to the next unblocked milestone.

### GATED ON CHAUNCEY
- Any public release of the runner, the brain bundles, or the web UX.
- Any distribution of model weights to anyone, by any channel.
- Any hosted/cloud deployment of any component — even "just for testing."
- Naming and copy for the public surface (his law: he names, we draft).
- Any third-party model ingestion or external API integration, ever.

### HARD NOS
- **No cloud dependency.** No cloud tier, no hosted inference, no
  "supplement with secure cloud." Local is law, not default.
- **No telemetry.** No analytics, no usage pings, no crash reports
  leaving the machine. Jan proved the posture ships; we prove it's law.
- **No accounts.** No sign-in, no API keys, no seats. Nothing to log
  into, nothing to bill against.
- **No training-pipeline interference.** This plan does not touch the
  600-step campaign, the checkpoints, the teacher intake, or the data
  machine. Consumes outputs only.
- **No third-party weights.** Only our own brains load in our runner.
  "Only our stuff" is already the law (CrushOn doc) — it applies here
  with full force.
- **No consciousness/feeling claims.** The growth loop's binding rail
  extends to the surface: the organism reports its state honestly,
  never claims sentience or subjective experience.
- **No push.** Repo stays local-only until he orders it; the brain
  bundles are dynasty material — eyes-only until his word.

---

## Honest limits of this doc
- Competitor facts come from public secondary sources found 2026-09-21;
  items that couldn't be confirmed are marked [UNVERIFIED] or
  [SECONDARY SOURCE]. No feature, price, or number was invented.
- The VRAM-leak report on Ollama, Ollama's cloud tier details, LM Studio's
  Enterprise pricing, Jan's AGPL scope and any paid tier, and the "no
  telemetry" claims are all unverified against primary sources.
- Bionic Agent details come from one press article (webpronews); treat as
  early-impression reporting.
- This is a production plan, not a build — milestones are sequenced
  intentions with named gates, not commitments with dates. Dates land when
  Chauncey sequences the work.
