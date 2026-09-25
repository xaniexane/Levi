# LEVI Product Lines

**Decision:** 2026-09-15 — Chauncey. NeighborOS is reframed as a LEVI product line, not a separate brand. "It's all LEVI" holds: product lines present as LEVI, answer to LEVI's mission, and run on LEVI's organism.

Source material (reference only, not merged): 8 archived NeighborOS source documents (keeper's files).

---

## Product Line 01 — NeighborOS: LEVI's local-services workforce

**What it is:** A dispatch-first operating system for local services — customers post jobs by photo, LEVI estimates the work, and dispatches trusted local workers. Workers build a living business record; properties build a living maintenance record.

**LEVI-native mapping** (how the organism powers it):

| NeighborOS concept | LEVI organ |
|---|---|
| Dispatch agent, compliance agent, fraud detector, business coach, property guardian | Fleet agent categories (Enterprise Phase 1) |
| Worker Twin / Property Twin (living records) | Memory + growth structures (twin = long-lived memory entity with history, reputation, credentials) |
| Job DNA, Proof-of-Work Ledger | Decision ledger (Enterprise Phase 2) |
| Marketplace of workers/services | Automation/agent marketplace (Enterprise Phase 4) |
| Commissions, subscriptions, payouts | Economic engine (Enterprise Phase 5) |
| Recruiting-first launch, waitlists, manual dispatch fallback | Founder bootstrap doctrine — LEVI runs the ops before automation matures |

**Build route (binding):** Not Base44/Lovable, not an external no-code stack. NeighborOS is built by LEVI's own software factory and operated by LEVI's fleet. The cloud product tier hosts it; the local-first core is never its dependency.

**Explicitly deferred — founder decisions required:**

1. **NeighborPay / live money.** Wallets, payouts, and commissions on real jobs collide with the paper-only finance rule and bring money-transmitter and contractor-classification regulation. No live-money code until Chauncey makes the business/legal call.
2. **Launch itself.** The action plans and marketing kits are his to execute; LEVI's job is to be ready underneath.

**SupraFabric:** reference only. Its durable-audit-fabric concept informs the Phase 2 decision ledger; its code targets a different stack and is not integrated.

---

## Product Line 02 — Hunts: the weakness hunt, productized

**Decision:** 2026-09-21 — Chauncey. "Hunts" joins the product line.

**What it is:** The weakness hunt as a service — find where AI fails and SI succeeds. A hunt dissects a target (a model, a system, a giant's pattern), delivers detailed, accurate, verifiable findings, and the deliverable is always an *addition*: a new LEVI-native capability the target refuses or can't build. Public track record of completed hunts; admission only on verified delivery.

**LEVI-native mapping** (how the organism powers it):

| Hunts concept | LEVI organ |
|---|---|
| Daily perpetual hunt (twice daily), giant-patterns research | Hunt jobs + research crews |
| Weakness-hunt outputs, resurrected rigor candidates | Rigor pipeline, scan-mind, GTPM |
| "SI succeeds where AI doesn't" | Mission banner — the hunt's thesis |

**Build route (binding):** Hunts run on the organism's own research crews and research the patterns; the deliverable is never a rebuild of a giant's feature — analysis only, additions only. If a find can't become an addition, archive it and move on.

**Explicitly deferred — founder decisions required:**

1. **Live-money hunts.** Bounty hunting with real payouts is real money movement: money flows through Cybrus only (binding), and no bounty/payment code until Chauncey makes the business/legal call.
2. **Public track record launch.** The hunt showcase goes live on his word, not before.

---

## Product Line 03 — Creation: the Alpha creation lab

**Decision:** 2026-09-21 — Chauncey. "Creation" joins the product line.

**What it is:** Alpha as a product — the AI no-code compiler. A prompt goes in, Echo architects the blueprint, Alpha compiles it through its generators into a real build directory plus manifest. Creation, not configuration.

**LEVI-native mapping** (how the organism powers it):

| Creation concept | LEVI organ |
|---|---|
| Echo blueprint architect | `revival/omega` Echo organ |
| 47 template generators | `revival/omega` Alpha organ |
| Blueprint → build pipeline with human gates | Forge pipeline (echo → alpha → preview → permission → materialize → nexus → receipt) |
| Creation console | Hub shell (`core/levi/hub/`) |

**Build route (binding):** Only our stuff — stdlib plus our own code, no borrowed frameworks. Honest labeling: generators emit genuine working scaffolds, not production apps; never claim production-readiness for a fresh build.

**Explicitly deferred — founder decisions required:**

1. **Multi-user / hosted creation.** The lab is single-user local-first today; any hosted or multi-user offering is a separate decision.
2. **Generator depth.** Deeper, production-grade generation is future work, not a launch claim.

---

## Product Line 04 — Training academy of operators

**Decision:** 2026-09-21 — Chauncey. "Training academy of operators" joins the product line.

**What it is:** An academy that trains operators — people who run LEVI's systems: the hub, DemandPulse, hunts, creation. Real learning science (spaced repetition, interleaving, Feynman drills, shadow mode, pressure drills, Socratic interrogation), real subjects (threat intel, OSINT, forensics, secure code review, LEVI canon operator training), honest about what a course can and can't build.

**LEVI-native mapping** (how the organism powers it):

| Academy concept | LEVI organ |
|---|---|
| Sessions, budgets, curricula | `core/levi/academy/` (Boot Camp sessions) |
| Learning-science wiring | Retrieval practice, elaboration, dual coding, desirable difficulty, metacognition scoring |
| Operator certification path | LEVI canon operator training (2026-09-17 curriculum expansion) |

**Build route (binding):** The academy's sessions run on the organism; operators train against live organs. Defensive-only curriculum (blue-team) — never offensive.

**Explicitly deferred — founder decisions required:**

1. **Credentialing authority.** No claiming accredited or certified status the academy doesn't hold.
2. **Tuition / paid seats.** Any money around the academy is a business decision, not a launch assumption.

---

## Product Line 05 — Veil Messenger + Creator Services

**Decision:** 2026-09-21 — Chauncey. "The secure messaging app and digital creation services layer — like skip the games and OnlyFans and Telegram together, but even more secure and encrypted."

**What it is:** Three things the incumbents keep separate, fused into one airtight platform: a skip-the-games-style discovery/classifieds layer, an OnlyFans-style digital creator services layer (profiles, subscriptions, gated content drops, private 1:1 + owner-moderated group chats), and a Telegram-style messenger — with real end-to-end sealing by default, stronger than any of them. The non-conforming bet: the adult creator space runs on weak security; we run it airtight.

**LEVI-native mapping** (how the organism powers it):

| Product concept | LEVI organ |
|---|---|
| Sealed messenger (E2E, tamper-evident envelopes, device rotation/revocation) | Veil (`core/levi/cybrus/veil.py`) — the Void Box lineage, renamed on his word 2026-09-17 |
| Creator services: profiles, subscriptions, content drops, 1:1 + group chats | `core/levi/creator/si/` (SI side) / `core/levi/creator/ai/` (AI side, reformed SFW) |
| Skip-the-games-style dating/classifieds: post a price, sealed messaging, nothing leaks beyond user authorization | Creator extension (2026-09-17 spec) |
| Pricing that undercuts | Dating $1 day / $5 week / $12–15 month; creator $1 taste / $4 monthly / $20 patron; 12% platform cut vs 20% standard — two schedules, kept separate |
| Money movement | Cybrus only, fail-closed, paper-only until the business call |

**Two tracks, never merged:** the SI side (adult, sealed behind the Plaiground gate) and the AI side (same shape reformed for society and ethics — SFW dating, general-audience creator platform). The gate proves opt-in, not age.

**Build route (binding):** Security is the product, not a feature — sealing by default, keeper-held key hierarchy, Encrypt-then-MAC with HKDF-derived keys. Chauncey's law (2026-09-21): every adult-themed service is age-gated with a PIN and an on/off switch — the SI side adopts the same PIN+switch pattern as the Plaiground gate (PIN required to enable, disable always allowed, PIN stored hashed never plaintext). No explicit content ships in the repo, ever.

**Explicitly deferred — founder decisions required:**

1. **Launch of the SI side.** Sealed design exists (commit `c0b3b5d`, 38/38 tests); going live with adult services needs his word plus legal review — same bar as the LEGION first-mint lawyer gate.
2. **Live money.** Creator payouts and subscriptions are real money movement: Cybrus-only, and no live-money code until the business/legal call.
3. **Sealing strength claims.** Current sealing is Encrypt-then-MAC, not AES-GCM — never claim stronger crypto than what's actually built.

---

## Product Line 06 — Plaiground (NSFW companion chat + image generation)

**Decision:** 2026-09-21 — Chauncey. "Plaiground — the NSFW companion chat and image generation service," seated in Echoverse. His spelling, preserved.

**What it is:** The NSFW companion experience as a product: companion creator + simulator, tailored companion chat, and image/photo generation — backed by Echoverse. The engine already survives in the repo (`core/levi/plaiground/`: gate, companions, chat, photos, simulator, stories, afterdark, depth, wellness, bounds, CLI — commit `10b07b7`, 50/50 tests green including bypass attempts).

**LEVI-native mapping** (how the organism powers it):

| Product concept | LEVI organ |
|---|---|
| Companion creator + simulator | `core/levi/plaiground/companions.py`, `simulator.py` |
| Tailored companion chat | `core/levi/plaiground/chat.py`, `stories.py`, `depth.py`, `afterdark.py` |
| Image/photo generation | `core/levi/plaiground/photos.py` hooks → media/creator image pipeline |
| The gate everything sits behind | `core/levi/plaiground/gate.py` — adult mode defaults OFF, every public function rechecks the age gate, minor indicators force re-lock |

**The split, his word (2026-09-21):** Plaiground IS the NSFW side. Echoverse is the SFW side. Two products, two tracks, never merged — Plaiground never leaks into Echoverse, Echoverse never gates Plaiground's content. The Vibe Chat rename (his 2026-09-19 pick for the erotic companion chat) was never applied to the code; still awaiting his word whether it stands or Plaiground carries the whole NSFW name.

**Build route (binding):** No explicit content ships in code or tests, ever. Chauncey's law (2026-09-21): every adult-themed service is age-gated with a PIN and an on/off switch — implemented in `core/levi/plaiground/gate.py` (PIN required to enable, disable always allowed fail-closed, PIN stored as PBKDF2 hash never plaintext, 101/101 tests green). The age gate is honest about its limits: local-only gates cannot cryptographically prove age, and no ID-verification layer exists — never claim otherwise.

**Explicitly deferred — founder decisions required:**

1. **Launch.** The engine is built and tested; going live needs his word plus legal review — same bar as the PL-05 SI-side launch.
2. **Image generation depth.** The photo hooks exist; the generation backend behind them is still spec/building — no fluency or quality claims until it's real.
3. **Vibe Chat rename.** Code still says Plaiground; his 2026-09-19 rename to Vibe Chat is unapplied. His call whether it stands.

---

## How new product lines get added

A product line is a named workload the organism serves — never a separate identity. Each entry records: what it is, which LEVI organs power it, what build route it takes, and what is explicitly deferred. No product line may override the mission, the unity principle, or the safety floors.
