# LEVI Fleet — Digital Workforce Foundation

Enterprise Phase 1 (charter §2–4): the modular agent fleet with dynamic,
budgeted swarming. This is the workforce layer — LEVI stops being one
assistant and becomes a coordinator of specialized agents.

## Concepts

**Categories** (`core/levi/fleet/categories.py`) — 30 agent types
(executive, supervisor, project_manager, planning, research, coding,
architect, uiux, database, devops, qa, security, automation, browser,
computer, device, communication, finance, payment, support, sales,
marketing, data, document, memory, learning, verification, fraud_risk,
compliance). Data-driven: each declares a role, a tool subset drawn from
the existing 24-tool registry, a cost class (light/standard/heavy), and a
role-prompt fragment. No category forks the tool organ — subsets are
filters.

**Supervisor** (`supervisor.py`) — decomposes a user objective into a
subtask DAG: nodes with category, task, acceptance criteria, and
dependencies. Two paths: model-assisted (drives the existing agentic
loop, parses strict `NODE` lines, falls back honestly on parse failure)
and deterministic heuristic (keyword routing — a first draft, not
genius). Plans are inspectable: `levi fleet plan "<objective>"`.

**Swarm runner** (`swarm.py`) — executes the DAG with ephemeral workers.
Workers are spawned per node, run the existing `run_subtask` loop with
their category's tool subset, then terminate. They share a thread-safe
**blackboard** (structured state + artifact exchange). The run verifies
each node, retries once on verification failure, escalates to the user
after that, and replans the remaining DAG at most once.

**Verification agent** (`verify.py`) — independent pass per node:
structural checks always (worker success, non-empty summary, claimed
artifacts present on the blackboard), plus an optional model-assisted
semantic judgment against the acceptance criteria.

## Budgets (charter §4, hard enforcement)

| Budget | Default | Meaning |
|---|---|---|
| `max_depth` | 3 | Recursion ceiling for explicit sub-swarms |
| `max_agents` | 12 | Total workers spawned per run |
| `max_time_seconds` | 600 | Wall-clock deadline |
| `max_tool_calls` | 200 | Total tool calls across all workers |
| `max_cost_units` | 400 | Σ tool calls × cost-class weight |

Cost classes: light = 1, standard = 3, heavy = 8 units per tool call.
**Cost units are relative budget tokens, not dollars.** They exist to
bound runaway swarms, not to bill anyone.

Enforcement: budgets are checked before every worker spawn and before
every tool call. Exceeded → the swarm halts immediately with a structured
report (`status: "halted"`, `halt_reason` naming the budget, limits, and
spend). Never silently.

## Safety

- **No uncontrolled recursive spawning.** Worker registries never contain
  the `delegate` tool; recursion happens only through the explicit
  `spawn_subswarm()` API with a depth counter. Beyond `max_depth` →
  `MaxDepthExceeded`, never silent.
- **Payment/finance are stubs.** `finance` and `payment` categories refuse
  to execute without explicit human approval wiring. Real money movement
  stays HITL-gated per the control plane (enterprise phase 2). The
  refusal is a structured escalation, not a crash.
- **Verification before trust.** Every node result is checked against its
  own acceptance criteria: one retry, then escalation to the user.
- **Decision journal.** Every swarm run persists a full report to
  `~/.levi/fleet/runs/<run_id>.json` — objective, node outcomes, budgets
  spent vs. limits, escalations. `levi fleet status <run_id>` reads it back.

## CLI

- `levi fleet categories` — list all 34 categories with cost class, tool
  count, and stub flags
- `levi fleet plan "<objective>" [--model]` — print the subtask DAG
- `levi fleet run "<objective>" [--max-agents N] [--max-minutes M]
  [--max-tool-calls N] [--max-cost N]` — execute as a budgeted swarm
- `levi fleet status <run_id>` — show a past run's report

## Product lines: NeighborOS (PL-01)

`docs/PRODUCT_LINES.md` defines NeighborOS as the fleet's first enterprise
workload. Its agent catalog is expressible 1:1 as fleet categories:

| NeighborOS agent | Fleet category | Cost | Notes |
|---|---|---|---|
| dispatch matcher | `dispatch` | standard | proposes matches; assignment needs approval |
| bid engine | `bidding` | standard | estimates are analysis, never price commitments |
| fraud detector | `fraud_risk` | standard | read-only |
| compliance gate | `compliance` | standard | read-only |
| business coach | `coach` | light | advice only; no cross-worker private data |
| property guardian | `guardian` | standard | record writes + reminders; outreach needs approval |

## Design input: enterprise blueprint §6–9

`docs/ENTERPRISE_BLUEPRINT.md` §§6–9 shaped this build, adapted to
stdlib (no pydantic/fastapi) and to Phase 1 scope:

- **§6 Agent runtime** → `WorkerContext` carries the blueprint's
  `AgentContext` fields (task/run id, user/tenant, permissions, budget,
  max_steps). Workers are ephemeral: spawn, run the existing
  `run_subtask` loop, report, terminate. `delegate` is stripped from
  worker registries; recursion goes only through the depth-counted
  `spawn_subswarm()` API. Every tool call is audit-logged.
- **§7 Model routing** → `select_worker_provider()`: light (read-only)
  work stays on the local provider — cheapest and most private;
  heavier work uses the run's provider (LEVI's shared chain). Full
  cost-aware routing with token estimates is phase 2.
- **§8 Tool registry** → category subsets are permission grants; every
  tool carries a risk classification (info/low/moderate) and an
  estimated relative cost via its cost class. The per-call audit log
  (`tool_audit` in every run report) is the phase-1 audit trail.
- **§9 Permission engine** → the category subset *is* the grant:
  `WorkerContext.check_permission()` refuses out-of-grant tools with a
  structured `FleetRefusal`. MODERATE+ tools without consent escalate
  through the tool organ's own confirmation gate. The universal L0–L4
  approval engine with real-time UI is enterprise phase 2.

## Honest limits

- **Stub workers vs. real workers.** The default worker drives the real
  `run_subtask` loop, but with the local rule-based provider it produces
  deterministic, limited output — real intelligence arrives when a model
  provider is configured. The swarm machinery (budgets, verification,
  retries) is fully real either way.
- **Heuristic plans are first drafts.** Keyword routing gets the shape
  right for common objectives; novel objectives deserve `--model` or a
  human-reviewed plan.
- **Cost units are not money.** They bound computation; the economic
  engine (phase 5) will price real runs.
- **Verification is only as good as its judge.** Structural checks catch
  empty/broken results; semantic judgment needs a capable model. The
  default is structural-only unless `--model` verification is wired.
- **Single-machine.** The worker pool is threads on one box — true
  distributed swarming is later-phase infrastructure work.
