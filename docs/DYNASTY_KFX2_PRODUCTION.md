# KFX² — Dynasty wave orchestration (absorb, reverse, improve, return unreplicable)

Date: 2026-09-21. Program: **Dynasty** — LEVI's eleven-agent wave orchestration system: coordinated waves of agents doing build/research work inside the organism. This doc is the KFX² frame applied to multi-agent orchestration. It stays strictly CAPABILITY-LEVEL: what the orchestration does in functional terms (wave scheduling, agent roles, verification passes), with no IP detail, no internal codenames beyond "Dynasty", and no provenance content. Eyes-only (Chauncey + Rex); nothing here is a shared-surface artifact.

## 1. Competitor teardown — orchestration model, features, pricing, DX, sentiment

Everything below comes from public secondary sources (comparison writeups, research notes, dev blogs, March–Sept 2026). Marked where sources conflict or could not be verified. Nothing invented.

### 1.1 CrewAI — role-based crews

**Orchestration model.** Role-based: you define agents as roles with goal + backstory, tasks with expected outputs, and assemble a *Crew*. The framework infers coordination. Two architecture modes: **Crews** (autonomous role-playing agents with delegation) and **Flows** (event-driven production pipelines with structured state). Processes: `sequential` (task A → B → C), `hierarchical` (a manager LLM dynamically delegates subtasks — more flexible, adds cost and latency), plus consensus-based execution per one source. Agents pass outputs down the pipeline; each agent receives the previous agent's output as context. LLM-agnostic (OpenAI, Claude, Ollama/local models per secondary sources).

**Memory/state.** Unified memory system per one research source: short-term (ChromaDB/RAG), long-term (SQLite3), entity memory (tracks people/orgs/concepts), plus LLM-inferred importance/scope scoring. Other sources describe it more simply: "task outputs passed sequentially between agents."

**Tool use.** Agent tools ("hands"): web search, PDF reading, code execution, DB queries; LangChain tools work out of the box per one source; MCP support native/production since v1.0 GA (Oct 2025) per one source.

**Pricing/licensing.** License: MIT per most secondary sources — but one comparison table lists Apache 2.0. **Could not verify against the official repo; sources conflict.** CrewAI Cloud managed platform (reported, not re-verified against crewai.com): Free tier ~50 workflow executions/month; Professional ~$25/month (~100 executions); Enterprise custom (third-party reports cite ~$60,000/year with 10K executions/mo and an Ultra tier ~$120,000/year — **could not verify against the official pricing page**). Open-source self-hosted tier is free with no execution limits; cloud pricing applies only to the managed platform.

**DX & sentiment.** Loved: fastest ramp in the category (~2–3 days engineering ramp-up per comparisons); code "reads like English" — readable role/goal/backstory definitions non-technical stakeholders can read; strong docs and community (~47–58K GitHub stars cited). Hated: debugging opacity when a multi-agent pipeline fails at scale; ~18% token overhead vs LangGraph on equivalent tasks (self-reported 2026 benchmark cited by one source — treat as unverified claim); memory system JSON parsing bugs recurring; telemetry enabled by default; enterprise pricing opacity; well-known migration pattern — teams prototype in CrewAI then migrate to LangGraph when they need production-grade state management and conditional routing.

### 1.2 AutoGen (Microsoft) → Microsoft Agent Framework

**Orchestration model.** Conversation-driven: agents collaborate through structured conversation; the team pattern determines who speaks when. Two layers: **AgentChat** (high-level prebuilt agents: AssistantAgent, UserProxyAgent, CodeExecutorAgent; team patterns RoundRobin, Selector, Swarm, GraphFlow DAG) and **Core** (low-level event-driven actor model with typed messages, pub/sub topics, single-threaded or distributed gRPC runtime). Cross-language (Python + .NET). Responsible-AI features (task adherence, PII detection, prompt shields) reported on the Agent Framework line.

**Status — verified across multiple sources.** AutoGen merged with Semantic Kernel into the unified **Microsoft Agent Framework** (Oct 2025 announcement); AutoGen itself is in maintenance mode — its own README says no new features, new users directed to Agent Framework. GA timing for Agent Framework reported as Q1 2026 by one source and April 2026 by another — **could not verify the GA date**. AutoGen remains MIT-licensed, free; costs are the LLM APIs you pay directly plus whatever infra you bring (Azure deployment costs separate).

**Memory/state.** Thread-based state model for reproducible runs; multiple backends reported (in-memory, Redis, mem0); chat history buffers, summarization, vector-store RAG, sliding window. Built-in OpenTelemetry instrumentation.

**DX & sentiment.** Loved: actor-model cleanliness, group-chat patterns, strong observability. Hated: maintenance mode — starting new work on it is building on a framework Microsoft is moving away from; Azure lock-in may not justify benefits if you are not an Azure shop; conversational coordination has an LLM-conversation tax on every step.

### 1.3 LangGraph (LangChain) — graph-based state machines

**Orchestration model.** Workflows as state machines: typed state, nodes, edges, conditional routing. Supervisor, Swarm, and graph-of-graphs (subgraph composition) multi-agent patterns. LangGraph reached v1.0 in late 2025 per secondary sources (**could not verify release date**).

**Memory/state — the category benchmark.** Built-in persistence layer with checkpointers (SQLite, PostgreSQL, S3). State reducers define how concurrent updates merge. First-class human-in-the-loop via `interrupt()` — programmatic pausing mid-node. Time-travel debugging: replay any checkpoint, fork execution from any state, explore alternative branches. Durable execution survives failures and can span hours/days. Streams token output and intermediate state updates.

**Pricing/licensing.** LangGraph framework: MIT, free. LangSmith (closed source per Langfuse docs — **note**: LangSmith is NOT open source; the client SDKs are): Plus reported at ~$39/seat/month. LangGraph Platform (commercial hosted): per-node pricing reported in conflicting figures ($0.001/node executed + $0.005/deployment-run in one source; $0.005/run + $0.0036/min in another) — **could not verify against official pricing**.

**DX & sentiment.** Loved: most production-ready of the three — explicit control flow ("you drew the map yourself"), checkpointing, replay, HITL, observability via LangSmith, Python/JS/TS. Hated: steeper learning curve; opinionated state mental model; observability story "really wants LangSmith" (paid); ~6M monthly PyPI downloads cited by one source — adoption is real.

### Teardown summary

| | CrewAI | AutoGen / Agent Framework | LangGraph |
|---|---|---|---|
| Control flow | Declared roles; framework decides | Emerges from dialogue | You draw the map |
| Memory | 3-tier (bugs reported) | Thread-based, buffers | Checkpointers, time-travel |
| License | MIT (conflict: one source says Apache 2.0) | MIT | MIT |
| Platform cost | Metered executions ($25/mo→$60–120K/yr reported, unverified) | Your LLM + Azure bills | LangSmith $39/seat/mo (reported, unverified) |
| Core weakness | Opaque debugging, prompt-fragile roles, prototype→migrate pattern | Maintenance mode; conversation = token tax | Learning curve; observability paywalled |

---

## 2. KFX² — absorb, reverse, improve, return unreplicable

### 2.1 ABSORB — the patterns worth taking (strengths, not just gaps)

1. **CrewAI's readable roles.** Role/goal/specialist definitions that read like English are genuinely good DX — non-specialists can read and adjust agent definitions. Absorb the readability; keep agent definitions human-legible inside the Dynasty wave definitions.
2. **CrewAI's Flows (event-driven production pipelines).** Structured-state event flow on top of free-running agents — the two-layer instinct (autonomous workers + controlled production paths) is sound. Absorb the layering.
3. **LangGraph's checkpointed state.** Persistence that survives failures, resumable runs, human-in-the-loop interruption — this is the benchmark for stateful orchestration. Absorb the expectation that every wave state is durable and resumable.
4. **AutoGen's actor-model isolation.** Agents as independent actors communicating through messages; one agent's failure doesn't cascade. Absorb the failure-containment instinct.
5. **LangGraph's streaming intermediate state.** Observability into long-running workflows — builders need to watch a wave, not just see its final output. Absorb the observability shape.

### 2.2 REVERSE — their weaknesses, flipped

| Their failure | Our reversal |
|---|---|
| Every agent step is a cloud-LLM call; bills compound per wave (execution meters, per-node pricing, token overhead) | **Zero marginal cost per wave step.** Waves run on LEVI's own deterministic engine and native brain — local-first physics. No per-step API spend, no execution meter, no node pricing, because our architecture has none of those costs. |
| Prompt-fragility: roles are backstories interpreted by an LLM; drift, delegation loops, opaque failures at 5+ agents | **Deterministic wave scheduling with verifiable receipts.** Each wave step emits a machine-checkable receipt: what ran, what it consumed, what it produced. Failures are diagnosable from the record, not from re-reading a conversation transcript. |
| Stateless amnesia between runs; memory as an add-on (JSON parsing bugs, buffer loss, telemetry defaults) | **Persistent local wave state.** Wave state lives in local storage (SQLite family), checkpointed and resumable across runs — continuity is the architecture, not a plugin. Nothing leaves the device unless the owner sends it. |
| Migration pattern: prototype in CrewAI, rebuild in LangGraph for production | **One physics from prototype to production.** The same deterministic wave runner that does a first sketch runs production waves — no rebuild tax when a workflow graduates. |
| Telemetry on by default; observability paywalled (LangSmith seats, platform fees) | **Local-first observability.** Wave logs and receipts are plain local artifacts the owner already has. No seat license to watch your own system work. |
| Maintenance-mode framework (AutoGen); vendor lock-in (Azure) | **No vendor dependency.** Local-first, stdlib-only core — the orchestration survives any provider's roadmap. |

### 2.3 IMPROVE → UNREPLICABLE — strengths amplified until only we can sign them

1. **LangGraph's statefulness → verifiable deterministic wave state.** They made state durable; we make it *deterministic and receipted*. A Dynasty wave doesn't just resume — every step leaves a verifiable receipt, so a wave can be audited, replayed, and proven to have done what it did. Unreplicable because their state exists to serve their cloud LLM calls; ours exists because the organism keeps its own ledger. They cannot remove the per-step cloud cost without destroying how they eat; we never had it.
2. **CrewAI's roles → wave roles on local-first physics.** They made multi-agent work readable; we keep it readable at **zero per-step API cost**. A readable role definition that costs nothing to run per step is a capability their cost structure forbids: hierarchical crews and manager-LLM delegation are priced into their platform; our equivalent runs on local compute the owner already paid for. Unreplicable: their revenue is metered execution; our engine has no meter to attach to.
3. **AutoGen's group coordination → gated wave coordination.** They coordinate through LLM conversation (every turn billed, every handoff prompt-fragile). We coordinate through structured waves with **owner gates between waves** — the Plan→Preview→Permission→Execute→Verify→Receipt law. Their conversation tax makes gating expensive; our deterministic steps make it cheap and complete. Unreplicable: you can't bolt fail-closed gates onto a chat loop without wrecking its economics; our gates are the physics.
4. **LangSmith's observability → provenance-grade wave ledgers.** Their observability is a paid product layered on top. Ours is the exhaust of the deterministic engine — receipts, checkpoint records, and cross-wave memory are produced by the physics, auditable forever, local. Unreplicable: observability-as-product cannot compete with observability-as-physics.

**Return to sender:** everything they monetize through scarcity — executions, nodes, seats, observability tiers — we ship as physics, because our physics made scarcity unnecessary.

### Positioning — the uproar doctrine (Chauncey, 2026-09-21)

Chauncey's positioning law: we offer what they do, what they don't, and
do it even better, for a fraction of their fractions. Capability parity
with the category leaders, plus the capabilities their cost structures
forbid, at zero marginal cost per wave step — dollar-scale entry,
volume over margin. This section stays capability-level: what the
orchestration does, not how it's built. No IP detail, no codenames, no
provenance content.

**Competitor features → our parity.** We match the category's expected
capabilities: readable agent-role definitions (CrewAI's genuinely good
DX — roles you can read, not config to decode); layered orchestration
of autonomous workers under controlled production paths (CrewAI Flows);
durable checkpointed wave state that survives failures and resumes after
interruption (LangGraph's benchmark); actor-style failure containment
so one wave's failure never cascades (AutoGen's isolation); and live
observability of long-running waves (LangGraph's streaming state).

**Competitor gaps → our exclusives.** What they don't offer:
deterministic wave steps with verifiable receipts — every step
machine-checkable, auditable, replayable — against prompt-fragile role
backstories and conversation-tax coordination; owner gates between
waves — the Plan→Preview→Permission→Execute→Verify→Receipt law applied
to orchestration, where LangGraph has interruption and we have
fail-closed gates; one physics from prototype to production, no rebuild
tax when a workflow graduates (against the prototype-in-CrewAI,
migrate-to-LangGraph pattern); local-first observability as exhaust of
the engine, never a seat license; and zero vendor dependency — the
orchestration survives any provider's roadmap, including maintenance-
mode frameworks.

**Our price as a fraction of theirs.** This document sets no dollar
price; the standing plan is **zero marginal cost per wave step** —
waves run on local-first physics, no per-step cloud spend, no execution
meter, no node pricing, and any departure needs Chauncey's explicit
word. Against CrewAI Cloud's reported ~$25/month Professional tier
(reported, not re-verified; enterprise tiers cited at ~$60,000–
$120,000/year, could not verify), LangSmith's reported ~$39/seat/month
(reported, unverified), and LangGraph Platform's reported per-node
pricing (conflicting sources, could not verify) — plus the AutoGen
model of a free framework with the LLM API bill landing per step on
your cloud account — our fraction is zero over whatever they charge:
per-step API spend and execution metering are costs our architecture
never had, so there is nothing to price against.

---

## 3. PRODUCTION-PHASE PLAN (capability-level)

Build order for Dynasty wave orchestration inside LEVI. Sequenced so each phase is shippable on its own; later phases compose on earlier ones. No code or commits under this plan until Chauncey's standing rules allow (commits local-only; push on hold until he orders it).

**Phase 1 — Single-wave runner (MVP).** A deterministic scheduler that runs one wave of agents over a defined task list: sequential role execution, per-step receipts, local log. Milestone: a wave runs end-to-end offline with every step receipted and reproducible.

**Phase 2 — Wave state store.** Persistent local state between waves: checkpoint after every step, resume after interruption, replay of a wave from any checkpoint for review. Milestone: kill the process mid-wave; resume and the record is complete, byte-verifiable.

**Phase 3 — Wave roles.** Readable agent-role definitions (human-legible role + goal + scope), including dedicated verification-pass roles that check a wave's outputs against the receipt record. Milestone: role definitions a non-engineer can read; verification passes run as their own wave.

**Phase 4 — Owner gates.** Human-in-the-loop interruption between waves: a wave pauses, the owner reviews the receipts, and the next wave only starts on approval — the Plan→Preview→Permission→Execute→Verify→Receipt law applied to orchestration. Milestone: no wave crosses a gate without an explicit owner decision recorded in the ledger.

**Phase 5 — Concurrent waves.** Independent waves run in parallel with actor-style failure isolation: one wave's failure is contained and recorded, never cascades. Milestone: two independent waves complete with one deliberately failing; the survivor is unaffected and the failure's record is complete.

**Phase 6 — Cross-wave memory.** Waves learn from prior waves through the growth loop: harvested runs become learnings, stored with provenance, informing later wave definitions — capability, not errors, compounding. Milestone: a wave definition measurably improves from the record of a prior wave's failures.

**Phase 7 — Fleet dashboard (read-only).** A local read surface showing live wave state, receipts, and gates — observability as physics, no seat license. Milestone: watch a wave's receipts land in real time from a local page.

### Gated on Chauncey (his word required before these move)

- Any cloud spend on agent execution — currently **zero is the plan**; any departure needs his explicit word.
- Any Dynasty material leaving eyes-only: publication, sharing, demos to anyone outside Chauncey + Rex.
- Any push of Dynasty code beyond the local working copy (standing policy: local-only until he orders a push).
- Scaling beyond the local machine (new devices, new infrastructure) for wave execution.
- Changes to the owner-gate law itself (Plan→Preview→Permission→Execute→Verify→Receipt is binding; weakening it is his call, not mine).

### Hard nos — never, regardless of phase

- **No cloud-agent spend.** No metered LLM API calls per wave step, no execution-based pricing, no node/seat metering. Local-first compute only.
- **No IP detail in any shared surface.** This doc is the template: capability-level only. Phase plans, playbooks, codenames, provenance records stay eyes-only.
- **No prompt-only coordination.** Every cross-agent handoff is a structured, receipted step — never "ask the model what to do next" as the coordination mechanism.
- **No stateless waves.** A wave that cannot be resumed, replayed, or audited from its own record does not ship.
- **No gates weakened for speed.** The owner gate between waves is not optional at any phase; convenience never outranks the law.

### Honest limits (what this doc does not claim)

- Pricing and license details for competitors are third-party reports marked honestly above; several items explicitly could not be verified against official pages.
- "Eleven-agent" is the program's design envelope; the wave runner must prove itself at small wave counts (Phases 1–3) before any large-wave claim.
- Cross-wave memory (Phase 6) compounds learnings only through the existing honesty-checked intake — no consciousness/feeling claims, same guardrails as the dynasty trainer loop.
