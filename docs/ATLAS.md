# LEVI Docs Atlas — the one map of everything

> ## Prime directive — the Waymaker law
>
> **"Where there isn't a way, Levi creates one."** This sits above all other
> laws. When LEVI hits no-API / no-tool / no-path, it does not stop — it
> creates the way: clean-room, stdlib-only, local-first, per the hard-route
> law. "No existing way" is the trigger to manufacture one, never a dead end.

> The Megazord is the whole industrial complex: warehouses of capability + a factory that never stops.

This file indexes every document in `docs/`. Each entry gets one honest line
written from the doc's own opening, not from memory. Docs that describe
intended or future work — not shipped code — are marked **(planned)**.

Related: `docs/LIFEPACK.md` (how the whole organism duplicates itself),
`docs/ARCHITECTURE.md` (honest description of the repo as it stands today).

---

## The factory floor — the production line

LEVI doesn't have a tool belt; it has **warehouses** of capability, and a
**factory** that never stops filling them. Raw material in, LEVI-native
additions out, stocked on shelves, distributed to the galaxy:

1. **Intake** — the hunt pipeline (`levi.perpetual.hunt` and the scheduled
   hunt jobs): raw-material intake — forgotten software, forgotten methods,
   tech-giant patterns, fallen platforms, games. → [PERPETUAL.md](PERPETUAL.md)
2. **Materials processing** — the Archive (`levi.archive`): finds validated,
   indexed, and stored with provenance; the growing "everything" half of the
   capstone identity. → [ARCHIVE.md](ARCHIVE.md)
3. **Manufacture** — the never-stops build engine (`levi.perpetual`
   supervision + build queues): findings are analyzed and recreated from
   scratch as LEVI-native **additions** (never rebuilds of a giant's feature,
   never paid tolls — the hard-route law). → [PERPETUAL.md](PERPETUAL.md)
4. **Warehouse stocking** — new capabilities land on warehouse shelves: the
   methods warehouse, the revivals warehouse, the skills/playbooks warehouse
   (incl. the defensive cyber playbooks), the archive-knowledge warehouse,
   services, games. → [METHODS.md](METHODS.md), [REVIVAL.md](REVIVAL.md),
   [SECURITY_INDEX.md](SECURITY_INDEX.md), [WAREHOUSES.md](WAREHOUSES.md) *(planned)*
5. **Distribution** — Galaxy (`levi.galaxy`): capabilities packaged,
   installed, and served — third parties build on LEVI; LEVI is the platform.
   → [GALAXY.md](GALAXY.md)

And the whole organism can duplicate itself: a life pack (v2) carries
identity, settings, durable memory, the skill manifest, the capability
snapshot, the growth snapshot, and the workflow registry to a new machine.
→ [LIFEPACK.md](LIFEPACK.md)

---

## Organism DNA & law

The identity, the binding laws, and the architecture the organism runs on.

- [ARCHITECTURE.md](ARCHITECTURE.md) — honest description of what this repo actually is today: separate products sharing a name, not marketing copy.
- [ATLAS.md](ATLAS.md) — this file: the one map of every doc.
- [BLOODSTREAM.md](BLOODSTREAM.md) — the one-turn pipeline: how one user text flows through every DNA strand in order.
- [BLUEPRINT_GROUNDED.md](BLUEPRINT_GROUNDED.md) — **(planned)** the clean-slate build spec for LEVI × L.W.P., grounded in the full prior build history (a spec, not shipped code).
- [GALAXY.md](GALAXY.md) — the ecosystem substrate: third parties publish skills, tools, and services on LEVI; LEVI is the platform, not just the product.
- [INTEROP.md](INTEROP.md) — the interpenetration doctrine, a binding law: modules compose through a shared substrate with strictest-risk-ceiling inheritance.
- [INTERPENETRATION.md](INTERPENETRATION.md) — the law as an engine: `composites.effective_ceiling` computes the strictest ceiling, `gate.run_composite_gated` enforces it on the execution path, deny-closed.
- [INTEROP_FOLLOWUPS.md](INTEROP_FOLLOWUPS.md) — **(planned)** deferred minimal patches that adopt the additive interop adapters inside existing modules.
- [MISSION.md](MISSION.md) — the prime directive: LEVI is next-generation offline-first, privacy-oriented synthetic intelligence.
- [OATH.md](OATH.md) — the trust-bound mission plane: a clean-room LEVI-native recreation of Beadle's trust model (inspiration reference only — no code read or copied).
- [ORGANS.md](ORGANS.md) — the four branching organs — echoverse, mandella, reim, riem — that explore possibility space, choose under fog, compost failure, and grow a genome.
- [PERPETUAL.md](PERPETUAL.md) — the engine that never stops: always-on, self-supervising hunt/grow/build mechanisms; all stdlib, all local-first.
- [REFERENCES.md](REFERENCES.md) — binding rule: provider names (KAI-9000, Qwen, LLaMA, …) are *references* for attribution, never sources; LEVI is sourced from itself.
- [SOUL.md](SOUL.md) — the owner-editable prompt override: `~/.levi/soul.md` is prepended to every agent system prompt on this machine.

## Subsystems

The working organs and modules of the organism.

- [ACADEMY.md](ACADEMY.md) — LEVI Boot Camp: a 30-day 24/7 training program for the user, driven by `levi academy`.
- [AFFECT.md](AFFECT.md) — the 5D emotional-intelligence engine: pattern-based affect modeling for conduct shaping; claims no sentience or felt emotion.
- [AGENT.md](AGENT.md) — the agent runtime: offline-first, stdlib-only, tool-using agentic loop with persistent sessions and context compaction.
- [ARCHIVE.md](ARCHIVE.md) — the Smithsonian module: the growing, provenance-tracked collection of everything the hunts bring back; never closes, never stops growing.
- [ASSISTANT_CORE.md](ASSISTANT_CORE.md) — the Muse-like behavioral core, promoted out of the spark-bot prototype for the whole agent runtime.
- [BACKUP.md](BACKUP.md) — encrypted off-machine snapshots: timestamped, hash-manifested tarballs shipped via rclone to Google Drive (crypt overlay).
- [BOUNTY.md](BOUNTY.md) — the bug-bounty recon pipeline: automates the *machine* half of bounty hunting (attack-surface inventory).
- [BRAIN_TRAINING.md](BRAIN_TRAINING.md) — the tiny-brain pipeline: a curriculum knowledge base the agent reads at runtime, plus a small neural net actually trained on the corpus (CPU-feasible; proof the brain learns).
- [CAPABILITIES.md](CAPABILITIES.md) — the capability-atlas honesty file: the structured answer to "what can you do?" across fourteen domains.
- [CONVO.md](CONVO.md) — thread-sense: conversational proprioception — LEVI feels the *shape* of a dialogue, not just the last N turns.
- [COURSES.md](COURSES.md) — the awesome-courses curriculum: 212 real university courses ingested as a queryable knowledge base; nothing fabricated.
- [CURRICULUM.md](CURRICULUM.md) — the growth curriculum: structured seed learnings from Chauncey and Rex, ingested with high initial corroboration.
- [GROWTH.md](GROWTH.md) — raising baby Levi: harvest → reflect → consolidate → journal, the developmental learning loop with honest stage labels.
- [HEARTBEAT.md](HEARTBEAT.md) — the autonomous self-check: a periodic, offline, read-only sweep of local state; stays quiet when everything is fine.
- [INTEGRATIONS.md](INTEGRATIONS.md) — "plug in universal": free, local-first integrations with outside systems, plus the interpenetration map of what may compose with what.
- [KING.md](KING.md) — King: the single control plane for narrative operations — an orchestration layer over the story-fabric and model engines, not a third engine.
- [KNOWLEDGE.md](KNOWLEDGE.md) — the local queryable knowledge base: capability atlas, defensive security catalog, course corpus, and a dated daily news corpus.
- [LAB.md](LAB.md) — the on-device agentic-SI lab: clean-room hands-on scenarios driving LEVI's real tool-using loop (idea inspired by public labs; all content original).
- [LEARNING_SYNC.md](LEARNING_SYNC.md) — collective learning, the distribution half: what one LEVI learns reaches every LEVI — batched, versioned, privacy-gated updates.
- [LIFEPACK.md](LIFEPACK.md) — life-pack export/import: versioned JSON bundles carrying portable state between homes and machines (v2 duplicates the whole organism).
- [MCP.md](MCP.md) — LEVI speaks MCP in both directions: client to external tool servers, server for external clients.
- [MEMORY.md](MEMORY.md) — durable, local-first memory: a JSON-backed store of typed entries with hybrid retrieval; also backs `python -m levi.rag`.
- [METHODS.md](METHODS.md) — 40 forgotten human techniques, each reimplemented from scratch as LEVI's own stdlib-only, local-first code (the methods warehouse).
- [MODELS.md](MODELS.md) — LEVI is the model: the default slot belongs to the LEVI family; cloud providers and the rules planner are selectable sources, never the default.
- [NEWS.md](NEWS.md) — dated current-events recall: a daily news snapshot corpus; every output carries dates so staleness is visible, never implied fresh.
- [PERSONA.md](PERSONA.md) — the persona nervous system: a local-first neuro-symbolic control surface steering which persona lens is active (lenses, not identities).
- [RAG.md](RAG.md) — local-first, stdlib-only, offline retrieval: no embeddings service, no vector DB, no network.
- [REVIVAL.md](REVIVAL.md) — ten retired-software ideas rebuilt as real working LEVI modules: ahead-of-their-time mechanisms in modern bodies (the revivals warehouse).
- [SECURITY.md](SECURITY.md) — operator security note: what Phase 1 fixed, the current posture, and what is still out of scope.
- [SECURITY_INDEX.md](SECURITY_INDEX.md) — the offline security knowledge index: 81 domains from category names only; defensive blue-team posture throughout.
- [SIM.md](SIM.md) — bounded text-based simulations: deterministic, clearly labeled, zero real network I/O; safe rehearsal of dangerous pipelines.
- [TORCH.md](TORCH.md) — pass the torch: packages what this instance has learned into a mentor bundle a fresh LEVI can ingest as seed.
- [USAGE_GOVERNOR.md](USAGE_GOVERNOR.md) — usage metering with cause attribution, spike detection, automatic cool-downs, deny-closed budgets, and a plain-language spike diagnosis.
- [VAULT.md](VAULT.md) — LEVI's secrets store: passphrase-derived encryption for the small secrets LEVI must hold; nothing secret lives in plaintext.

## Operations

How to run, operate, and plan the organism.

- [ANDROID_APP.md](ANDROID_APP.md) — installing LEVI on Android: a thin native shell around the web client, plus the Termux toolchain notes.
- [CLI.md](CLI.md) — the CLI reference, generated from `levi --help`; regenerate, don't hand-edit.
- [CLOUD_API.md](CLOUD_API.md) — `levi agent serve` as a multi-user API: LEVI as its own cloud provider.
- [CONSOLE.md](CONSOLE.md) — the interactive terminal surfaces (dashboard console + simulation) built on the `levi.ux` effects kit.
- [ENTERPRISE.md](ENTERPRISE.md) — **(planned)** the Global Agentic SI Enterprise program: what LEVI becomes at global scale.
- [ENTERPRISE_BLUEPRINT.md](ENTERPRISE_BLUEPRINT.md) — **(planned)** the detailed implementation design reference for the enterprise program, adapted to the organism rather than adopted literally.
- [MONETIZATION.md](MONETIZATION.md) — **(planned)** draft monetization plan (2026-09-15 draft; its "free core forever" binding constraint was superseded 2026-09-17 — live law is no-free-core, dollar-scale entry, volume over margin).
- [RUNBOOK.md](RUNBOOK.md) — operator instructions for running each piece; the products are independent — run only what you need.

## Product lines

The user-facing surfaces, each answering to LEVI's mission.

- [BOT.md](BOT.md) — the spark voice card: Grok-inspired energy on a LEVI core; Grok is a *reference*, never a source.
- [CONTROL_PLANE.md](CONTROL_PLANE.md) — the enterprise control plane: human control + institutional memory + economic brain; local-first, stdlib-only (Phase 2 complete).
- [DEMAND.md](DEMAND.md) — DemandPulse: advisory, hypothesis-labeled product-opportunity scoring; never claims real market demand, never invents data.
- [FINANCE.md](FINANCE.md) — the paper-only finance simulator with advisory signals; live trading is structurally impossible. (Doc header's sign-off note is stale: both sign-offs were granted in writing 2026-09-15 and the build shipped.)
- [FLEET.md](FLEET.md) — the agent fleet: modular agents with dynamic, budgeted swarming — the digital-workforce layer.
- [PRODUCT_LINES.md](PRODUCT_LINES.md) — the framing decision: everything (including NeighborOS) is a LEVI product line, not a separate brand; "it's all LEVI."
- [PWA.md](PWA.md) — the chat organ: an installable chat PWA reincarnating the good ideas of the old Xeno lineage.

---

## Honest status key

- No marker — the doc describes shipped, tested code in this repo.
- **(planned)** — the doc describes intended, deferred, or design-stage work; the code is not (fully) there yet. Read it as direction, not as fact.
- Counts: 61 docs mapped above + this atlas = 62 entries. Generated 2026-09-15 from the docs' own openings.
