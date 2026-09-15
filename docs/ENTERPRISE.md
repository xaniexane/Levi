# LEVI Enterprise — Global Agentic AI Program

**Charter source:** Chauncey's master build prompt, 2026-09-15.
**Relationship to mission:** `docs/MISSION.md` is the product prime directive (what LEVI *is*). This document is the enterprise program (what LEVI *becomes* at global scale). Neither overrides the other.

## The thesis

LEVI grows from a personal synthetic intelligence into a global AI enterprise whose core product is an **intelligent digital workforce**: a fleet of cooperating agents that complete digital work — research, software, automation, operations — rather than merely advising. The enterprise pursues market leadership through superior execution, automation, reliability, and economics. **Never** through illegal exclusion, collusion, price fixing, sabotage, or deception. The goal is the most capable *legitimate* AI-powered digital workforce possible.

## Reconciliation with the mission (binding)

- **Free core forever.** The local-first LEVI core is never monetized. Revenue lives in the cloud, marketplace, and enterprise layers — never in the core, never as a toll on the organism itself.
- **Privacy-preserving learning.** Global learning uses consent, anonymization, aggregation, and opt-out — the rails already built for cross-user learning (`docs/CLOUD_API.md`). No private conversation is ever dumped into a shared corpus.
- **Fearless and unblocked** apply to the enterprise too: no corporate refusal theater in the workforce product.
- **Human control is architectural.** The HITL control plane is not a feature; it's a load-bearing wall (see phase 2).

## 35-section gap map (honest, 2026-09-15)

Status: **HAVE** = built · **PARTIAL** = real pieces exist · **GAP** = not built · **INFRA** = needs real-world infrastructure beyond this repo.

| # | Section | Status | Notes |
|---|---------|--------|-------|
| 1 | Core vision (assistant+fleet+factory+...) | PARTIAL | Many organs exist; not yet unified as one enterprise |
| 2 | AI fleet (modular, ephemeral) | PARTIAL | Delegation + subagents exist; no fleet registry |
| 3 | Agent categories (~30 types) | GAP | No category registry |
| 4 | Agent swarming (dynamic, budgeted) | GAP | No swarm lifecycle or budget enforcement |
| 5 | Cross-orchestration engine | PARTIAL | Bloodstream + tool registry; no universal workflow engine |
| 6 | Cross-device automation | GAP | Device graph not built |
| 7 | Digital workforce workflows | PARTIAL | Agent loop does these ad hoc |
| 8 | HITL control plane | PARTIAL | PolicyEngine + risk levels + purchase approvals exist; needs formal universal approval engine |
| 9 | Secure payment engine | PARTIAL | Wallet/Stripe Link/purchasing flow; no orchestration architecture |
| 10 | Economic engine | GAP | Metering exists; no billing, pricing, or margin monitoring |
| 11 | Cost-aware AI routing | GAP | — |
| 12 | Local+cloud model hybrid | PARTIAL | Provider chain exists; no intelligent routing |
| 13 | Provider routing / free-tier economics | PARTIAL | Chain exists; no quota/budget-aware routing |
| 14 | Global learning engine | PARTIAL | Cross-user learning built with privacy rails |
| 15 | Decision & execution ledger | PARTIAL | Journal + metering; not structured telemetry |
| 16 | Data intelligence layer | GAP | — |
| 17 | Agent performance database | GAP | — |
| 18 | Continuous learning loop | PARTIAL | Growth loop; no offline-eval-to-deploy pipeline |
| 19 | Global knowledge network | PARTIAL | Memory store; no global layer or graph |
| 20 | Automation marketplace | GAP | — |
| 21 | Agent marketplace | GAP | — |
| 22 | AI software factory | PARTIAL | Builder organ + artifacts |
| 23 | Autonomous software engineering | PARTIAL | Coordinators do this today; needs sandboxing |
| 24 | Self-debugging factory | PARTIAL | Ad hoc iteration; no formal loop with limits |
| 25 | Visual application testing | GAP | — |
| 26 | Cross-device software development | GAP | — |
| 27 | Autonomous business operations | GAP | — |
| 28 | Customer acquisition engine | GAP | Ethical only: no spam, fake reviews, impersonation, deception |
| 29 | Global scaling engine | INFRA | Regional infra, data residency — real-world deployment work |
| 30 | Self-sustaining operations | GAP | Heartbeat monitors; no infra control |
| 31 | Economic flywheels | PARTIAL | Learning flywheel exists in growth loop |
| 32 | Freemium economics | GAP | Design decision required; reconciled with free core above |
| 33 | Model economics engine | GAP | — |
| 34 | AI router | GAP | — |
| 35 | Global evaluation system | GAP | Tests exist; not a production eval platform |

## Phase plan

- **Phase 1 — The Fleet** (§2–4): agent category registry, supervisor decomposition, budgeted swarm lifecycle, verification agent. **NOW BUILDING.**
- **Phase 2 — Control & Telemetry** (§8, 15, 11, 33, 34): universal approval engine, decision ledger, cost-aware routing, model economics, AI router.
- **Phase 3 — Software Factory** (§22–26): sandboxed autonomous engineering, self-debug loop, visual testing.
- **Phase 4 — Marketplaces** (§20–21): automation + agent marketplaces with permission/risk declarations and verification.
- **Phase 5 — Economic Engine** (§9, 10, 32): payment orchestration, billing, freemium design, margin monitoring.
- **Phase 6 — Global Systems** (§14 full, 16, 17, 19, 29, 30): needs real infrastructure; designed in-repo, deployed in the world.

Rule for every phase: reuse LEVI's existing organs — don't fork them. Commit locally; never push without a fresh transient credential.
