# LEVI Control Plane — Enterprise Phase 2

**Status:** Phase 2 complete (2026-09-15). Blueprint §§7, 9, 15, 34.

The control plane is LEVI's **human control + institutional memory + economic
brain**. Three organs, all local-first, all stdlib-only:

| Organ | Module | What it does |
|---|---|---|
| Universal approval engine | `core/levi/control/approvals.py` | L0–L4 human gating for every consequential action |
| Decision ledger | `core/levi/control/ledger.py` | SQLite record of every task, step, verification, outcome, cost |
| Cost-aware routing + AI router | `core/levi/control/routing.py`, `router.py` | Cheapest viable model per task; learns from ledger history |

CLI: `levi approve …`, `levi ledger …`, `levi route plan "…"`.

---

## 1. Universal approval engine (L0–L4)

Formalizes the control plane on top of the existing
`levi.policy.gates.PolicyEngine` — it drives it, not forks it.

**Risk vocabulary (shared with policy gates):**

- **L0 INFO** — pure information; auto-resolves, logged
- **L1 LOW** — low-risk local actions; auto-resolves, logged
- **L2 MODERATE** — moderate impact; waits for human approval
- **L3 HIGH** — high impact; waits for human approval
- **L4 CRITICAL** — financial / security / irreversible; waits for human approval

**Decisions:**

- `approve-once` — releases **exactly one** action. The next request for the
  same action+workflow *claims* the decision (marked consumed); every later
  request asks again. A worker that was blocked, then retried after the human
  decided in the CLI, proceeds once — never twice, never zero times.
- `approve-for-workflow` — grants the same `action_key` for the rest of a
  workflow/run id (e.g. one fleet run).
- `deny` — denies that request; a later re-request asks again (deny is a
  decision, not a permanent ban).

**Queue semantics:**

- The pending queue persists at `~/.levi/control/approvals.json`
  (owner-only `0o600`, atomic writes), so a CLI decision in one process
  unblocks a worker waiting in another.
- Retrying a request for the same action+workflow **reuses** the existing
  pending record — the queue never fills with duplicates.
- `guard(…, timeout=None)` returns the pending record at once (the caller
  escalates). `timeout>0` polls the persisted queue until decided or the
  timeout elapses — cross-process human decisions work mid-run.
- `require(…)` raises `ApprovalBlocked` unless the action came back
  approved. The record travels on the exception, so callers can report the
  pending approval id instead of executing.

**Fleet wiring:** every fleet worker's tool registry routes MODERATE+
tools (`shell_exec`, `file_write`, `file_edit`, `http_request`, `web_fetch`,
`schedule_add` — see `tool_risk_level`) through `require()` *before*
execution. L0/L1 tools never touch the queue. A blocked tool call raises
`ApprovalBlocked` out of the agentic loop; the node is marked
`awaiting_approval` (dependents skip), and the escalation tells the human
exactly what to run: `levi approve approve <id>`. Category permission
checks and the tool-level confirmation gates are preserved — the control
plane is an outer gate, not a replacement.

---

## 2. Decision ledger (blueprint §15)

SQLite at `~/.levi/ledger/ledger.db` (stdlib `sqlite3`). Three tables:

- **tasks** — task/user/tenant scope, objective, plan version, status,
  accumulated relative cost and latency.
- **steps** — every decision step: agent, category, task *class*
  (simple/medium/hard), model/version, tools used, concise decision
  summary, action, expected vs actual result, verification notes,
  error/recovery, outcome, relative cost, latency.
- **feedback** — human ratings/comments per task.

**Explicitly not stored:** hidden chain-of-thought. `decision_summary` is a
concise rationale — what a reviewer needs to understand *why*, never the
model's internal monologue.

**Writers:** every fleet run (task + per-node steps + final status),
every `levi agent run` (one task + one step), and router actuals
(`routing.record_actual`) write here. Writes are telemetry — a ledger
failure never breaks a run.

**Reads:** `stats()` (counts, cost, outcomes), `recent_tasks()`,
`get_task(id)` (full task with steps + feedback), and
`model_category_stats()` — per-(model, category, task-class) runs,
success rate, and average cost. That last query is what the AI router
learns from.

---

## 3. Cost-aware routing (blueprint §7)

Every task gets a cost budget:

```
TASK → classify complexity → estimate tokens → estimate relative cost
     → cheapest model meeting the quality bar → execute
     → track actuals back into the ledger
```

- **Complexity** is a crude keyword/shape heuristic
  (`simple` / `medium` / `hard`) with stated reasons — honest about being
  a heuristic, not understanding.
- **Cost units are RELATIVE, not dollars** (`levi-tiny` = 1). They rank
  models against each other for routing decisions and must never be
  presented as money. Cloud sources are ranked, unpriced placeholders.
- **Quality bar:** `levi-tiny` never wins a tool task (it cannot emit tool
  calls) or anything compositional; `hard` tasks prefer `levi-4b`.
- **Family first:** the LEVI family (`levi-tiny`, `levi-0.6b`, `levi-4b`)
  is preferred; other providers are selectable sources, never the
  default. When weights aren't downloaded, the router falls back to the
  full family rather than refusing.
- **Budget:** if the cheapest viable model exceeds the task budget, the
  router keeps the quality bar and *flags* the overrun — it never silently
  downgrades to a worse model.

---

## 4. AI router (blueprint §§7, 34 — first version)

`router.plan(task)` maps a task to
**(model, agent category, tools, execution strategy)** plus a plain-language
explanation of *why* — a route is never a bare decision.

- **Heuristic first:** complexity → model (via cost-aware routing);
  keyword scoring → fleet category (validated against the real registry);
  strategy by complexity (`direct` / `single_worker` / `swarm`).
- **Learning:** the router consults `model_category_stats()` for the
  task's complexity class. A (model, category) combo with **≥3 recorded
  runs and ≥60% success** that is cheaper than the heuristic pick wins,
  and the explanation says so. Thin history is not evidence — with no
  qualifying history the router says it's running on heuristics.
- `privacy="local-only"` excludes cloud sources from candidacy.

---

## 5. CLI reference

```bash
levi approve                  # list pending approvals
levi approve approve <id>     # approve once (releases exactly one action)
levi approve deny <id>        # deny
levi approve for-workflow <id> --workflow <run-id>
                              # grant action for the rest of a workflow

levi ledger                   # aggregate stats
levi ledger recent            # latest tasks
levi ledger query --task <id> # full task: steps, verification, feedback

levi route plan "<task>"            # show the planned route + why
levi route plan "<task>" --budget 5 # flag overruns, keep the quality bar
levi route plan "<task>" --local-only
```

---

## 6. Honest limits (first version)

- Complexity classification is keyword/shape matching, not understanding.
- Relative costs are ranked estimates, not measured prices and not dollars.
- The router learns only from recorded outcomes; provider-dependent output
  quality is not modeled.
- Approval polling is second-granularity file polling — fine for human
  timescales, not for millisecond loops.
- The ledger is local SQLite: one machine, one operator. Multi-tenant
  fields exist in the schema for the road ahead, not for a fleet of
  servers today.
