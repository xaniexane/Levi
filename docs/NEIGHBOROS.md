# NeighborOS — LEVI Product Line 01

**Decision:** 2026-09-15 — Chauncey. NeighborOS is reframed as a LEVI
product line, not a separate brand. "It's all LEVI": it presents as
LEVI, answers to LEVI's mission, and runs on LEVI's organism.

**What it is:** a dispatch-first operating system for local services —
customers post jobs, LEVI estimates and dispatches trusted local
workers. Free to start, earn-first, compliance-gated, founder-bootstrapped.
Recreated LEVI-native from Chauncey's own NeighborOS blueprint IP
(master blueprints, 20-star establishment plan, action plan). No
Taskade, no Base44, no external service is wrapped or required.

## What this module covers (v1)

`core/levi/neighboros/` — stdlib only, local-first:

- **The live Jobs project** (`tracker.py`): service jobs move
  `requested → dispatched → in_progress → completed` (or `cancelled`),
  plus a worker roster with per-category coverage. State under
  `~/.levi/neighboros/` with owner-only permissions.
- **The founder's daily operations brief** (`brief.py`): reads the
  queue and produces dispatch bottlenecks, urgent work, supply gaps,
  and the single highest-leverage action — the same brief the old
  Taskade automation sent, now generated locally with documented,
  deterministic selection rules.

## CLI

```bash
levi neighboros jobs add --title "Fix leaky faucet" --category plumbing \
    --priority high --customer "R. Diaz" --due 2026-09-20
levi neighboros jobs list --status requested
levi neighboros jobs assign 1 --worker "Sam K"
levi neighboros jobs move 1 in_progress
levi neighboros jobs note 1 "customer prefers mornings"
levi neighboros workers add --name "Sam K" --categories "plumbing,handyman"
levi neighboros workers list
levi neighboros brief            # prints + writes dated brief file
levi neighboros stats
```

## The daily brief, cron-friendly

One command produces the dated brief file
(`~/.levi/neighboros/briefs/brief-YYYY-MM-DD.md`) and prints it:

```bash
levi neighboros brief
```

Schedule it (replaces the Taskade automation; no limits, no cost):

```cron
0 7 * * * /usr/bin/env levi neighboros brief >/dev/null 2>&1
```

### How the brief decides (auditable rules)

1. **Bottlenecks** — requested jobs with no worker; requested jobs older
   than 24h; dispatched/in-progress jobs with no update in 48h.
2. **Urgent** — emergency priority, or due past / within 24h.
3. **Supply gaps** — categories with open jobs and zero active workers.
4. **Highest-leverage action** — oldest emergency/overdue → oldest
   unassigned → largest supply gap (recruit) → oldest stalled (follow
   up) → empty queue means a founder recruiting day → otherwise the
   oldest open job.

The tracker never invents jobs, workers, estimates, or payouts. An
empty queue briefs honestly: "Queue is empty — run a founder
recruiting day."

## Explicitly deferred (founder decisions required)

- **NeighborPay / live money** — wallets, payouts, commissions on real
  jobs. Collides with the paper-only finance rule; no live-money code
  until Chauncey makes the business/legal call.
- **Worker Twin / Property Twin** — living reputation and maintenance
  records; the data model here (job history per worker/category) is
  the foundation they build on.
- **Compliance-gated market launch & launch modes** — admin concepts
  from the blueprints; the queue is mode-agnostic for now.
- **The launch itself** — action plans and marketing kits are his to
  execute; LEVI's job is to be ready underneath.
