# SYNTHESIS — the organism's mind and vital signs

> **Proposed name — Chauncey renames.** `levi unified` was already taken
> (Daemon Core unified cycle). Module: `core/levi/synthesis/`.

One front door for the questions the organism must always answer
honestly: *what do you make of this?* (`synthesis ask`), *how are you?*
(`synthesis status`), and — new — *go do this* (`synthesis run`).
Everything else — the L.W.P. press console, King,
finance, growth, skills, daemon — stays where it is, reached through its
own clean API. Synthesis adds no duplicate organs.

## Agency is a pillar, not a bolt-on

The agentic loop runs every goal through five honest stages:

```
perceive → reason → act → verify → receipt
```

- **perceive** — memory recall, growth learnings, live subsystem status.
  Best-effort; perception never kills a run.
- **reason** — the synthesis mind deliberates first (native brain
  consulted, rules engine decides). The verdict frames the work.
- **act** — the canonical step-level tool loop
  (`levi.agent.loop.run_subtask`) with the deterministic offline planner
  and the real sandboxed `ToolRegistry` (31 tools: files, memory,
  skills, courses, news, shell, delegation…). The whole run executes
  inside `OfflineGuard`: zero network, enforced — network-shaped tools
  fail closed and the receipt says so.
- **verify** — the transcript is inspected: steps, tool calls, gates hit.
- **receipt** — append-only JSONL at `~/.levi/synthesis/receipts.jsonl`
  (`$LEVI_SYNTHESIS_DIR` when the operator redirects the front door's state).

**Permission discipline.** Gated tools (`file_write`, `file_edit`,
`shell_exec`, `http_request`, …) need the explicit `--consent` flag —
that flag IS the Permission step of
Plan → Preview → Permission → Execute → Verify → Receipt. Without it the
run stops at the gate: `ok=False`, the block recorded in the receipt,
nothing consequential executed. The loop never retries a denied gate.
Verified by `tests/test_synthesis_agent.py` (blocked-without-consent and
allowed-with-consent cases).

**Delegation.** `synthesis delegate "a" "b" …` fans out to bounded
sub-runs — one coordinator, N workers, one merged receipt (in-process,
sequential, deterministic).

**Scheduling.** `synthesis schedule "goal" --every 3600` registers a local
interval entry; `synthesis tick` runs whatever is due. Heavy-duty timed
choreography already lives in `levi.copper` and the daemon kernel; this
is the lightweight path.

## Commands

- `levi synthesis ask "task" [--brain-policy auto|rules-only]` — reason over
  a task. The answer ships with `substrate` (which mind reasoned) and
  `limits` (what each mind did and did not do).
- `levi synthesis status` — one dashboard: brain weights, skills, growth,
  L.W.P. press, finance mode, daemon kernel, config.
- `levi synthesis prove-offline [--task ...]` — run status + ask with sockets
  disabled. Prints `OFFLINE PROOF PASSED` or `OFFLINE PROOF FAILED`.
- `levi synthesis config [--show] [--brain-policy ...]` — show/change config
  (`~/.levi/synthesis/config.json`; env overrides `LEVI_SYNTHESIS_*`).
- `levi synthesis run "goal" [--max-steps N] [--consent]` — run one goal
  through the agentic loop; prints the receipt JSON (`ok` decides exit code).
- `levi synthesis delegate "goal1" "goal2" [...] [--max-steps N] [--consent]`
  — fan out to bounded sub-runs; prints the merged summary.
- `levi synthesis schedule "goal" --every SECONDS [--consent]` — register a
  local interval schedule (runs when `synthesis tick` executes).
- `levi synthesis tick [--max-steps N]` — run every due scheduled goal.
- `levi synthesis receipts [--limit N]` — show recent run receipts.
- `python -m levi.synthesis ...` works without the big CLI tree.

## What it does offline (verified)

- Loads the native-brain weights (`core/levi/brain/weights/tiny-gpt.pt`,
  3,271,168 params, 600 training steps) with sha256 verification, generates
  continuations on CPU — no network, no training, no weight changes.
- Deliberates on the rules engine (propose → critique → verdict) with the
  brain's raw continuation heard as one labeled, critiqued proposal.
- Reports 934 registered skills, the growth journal, L.W.P. press-console
  availability, paper-only finance mode, and daemon kernel state — all from
  local files and imports.
- `prove-offline` completes all of the above with socket creation disabled
  (`OfflineGuard`); any network touch would raise `OfflineViolation` and
  fail the proof. `tests/test_synthesis_offline.py` pins this.

## What it does NOT do (honest limits)

- The native brain **cannot reason, converse, or replace a language model**.
  Its samples are garbled proof-of-learning output (see
  `core/levi/brain/weights/eval.json` and `samples.md`). It is exercised as a
  labeled continuation voice, never as the decider.
- No sentience, subjective-experience, or consciousness claims — anywhere.
  The brain is a continuation engine; the rules engine is a deliberator;
  the report says exactly that.
- Not a chatbot and not a replacement for `levi ask` (the Orchestrator
  lattice: companion/intent/persona/specialists). Synthesis is the raw mind;
  `ask` is the product surface. Different layers, documented here so nobody
  confuses them.
- Finance stays paper/simulated-only — structurally, not by flag.
- No cloud, no accounts, no telemetry. Nothing leaves the machine.
- Dynasty/canon/IP materials are untouched by this build and stay eyes-only.

## The substrate honesty law

Every answer carries `substrate` and `limits`:

- `rules-engine` — deliberation ran on the rules engine only (torch missing,
  weights missing/unreadable, or `brain_policy=rules-only`).
- `rules-engine + native-brain` — the brain contributed one verbatim,
  labeled continuation as a critiqued proposal; the rules engine decided.

Brain failures degrade to an honest rules-only report — never an exception,
never a silent fallback.

## Open decision: who decides?

This build wires the brain **brain-first, rules-verdict**: the weights are
consulted first and heard, the rules engine decides. That is the repo's
binding honesty law, and the weights' garbled output earns no more. Making
the native brain the *decider* ("brain-primary") would need Chauncey's
explicit call — and better weights first. Surfaced, not taken.

## Middle-team interface contract (Phase 2 flagship)

The middle team (scan-mind + blackboard + rule-reflex + dictionary, in
`core/levi/gtpm/`) builds against this package by contract, never by
editing it. What this package honors, from their contract of 2026-09-20:

- **B1 — deliberative voice stable.** `mind.ask(task, brain_policy)` keeps
  its signature (positional-or-keyword) and its report key set
  (`answer, substrate, limits, proposals, critiques, verdict, brain`).
- **B2 — shared receipt log.** The substrate receipts log accepts entries
  of any `kind` (`write_receipt_entry`); flagship receipts
  (scan/board/firing/define/arbitration) append here with `kind` preserved.
- **B4-light — scan-per-tick.** `tick_schedules` runs one scan per tick:
  FREEZE (due set + consent snapshot) → EXECUTE (one `run_goal` per due
  schedule under the cycle budget) → FLUSH (schedule store written once) →
  HOUSEKEEPING (a `kind="tick"` cycle receipt). Budget exhaustion skips
  honestly, never silently. Full scan discipline is Phase 2's to build.
- **B5 — governance frame.** Each `run_goal` freezes
  (goal, consent, standing limits, safety signals) before perception; the
  reason step reads the snapshot and it ships in the receipt.
- **B6 — `delegate_goals(mind="scan")`.** The route exists and degrades
  honestly when the scan-mind is unavailable. **Conflict flagged:** the
  middle team's reference adapter (`levi.gtpm.adapters.delegate_scan`)
  currently re-enters `delegate_goals(mind="scan")` instead of executing
  scan-mind sub-runs — a circular route. This package guards the
  re-entrancy and raises it loudly rather than recursing; the middle team
  needs an executor, not a probe, before this route goes live.
- **B8 — permission-gate semantics confirmed.** The synthesis agent is
  fail-closed: gated tools require explicit `consent` (the Permission
  step); a denied gate is a recorded block, never a silent retry. This
  matches the standing approval law (risk levels 0–2 auto-approved,
  3–4 need Chauncey's word) as implemented in `levi.policy.gates`.
- **B9 — cycle budget knob.** `scan_budget_ms` (default 100) lives in
  `SynthesisConfig`; operator-tunable via
  `levi synthesis config --scan-budget-ms N` or
  `LEVI_SYNTHESIS_SCAN_BUDGET_MS`.

Decisions that need Chauncey's word (not the beginning team's): the final
names of the flagship modules (B3), whether `levi synthesis` gains
scan/board/reflex/words subcommands or the flagship keeps its own entry
point (B10), and the brain-as-decider question above.

## Offline proof

```
levi synthesis prove-offline
# OFFLINE PROOF PASSED: status + ask completed with the network disabled
```

The proof disables `socket.socket`, `socket.create_connection`, and
`socket.getaddrinfo` for the whole run. The static scan
(`assert_no_network_imports`, pinned by tests) keeps the synthesis
package's own sources free of network-library imports.

## What the Grok recovery corpus contributed

> **Status: under deep re-research.** Chauncey ordered that no element be
> marked not-possible on a shallow look. The verdicts below were the
> first-pass read; each is being re-earned file-by-file (originals never
> touched; inspection copies in `/tmp` only). The element catalog in
> `docs/SYNTHESIS_ARCHITECTURE.md` carries the final per-element verdicts.

Evaluated file-by-file against the local core (originals never touched;
inspection copies in `/tmp` only). First-pass verdict: **nothing earned a place as
code** — the local core supersedes this lineage:

- `automation-pack-v1` — safety lists duplicate `docs/AUTOMATION_SAFETY.md`
  and the automation module's HITL doctrine; its primitive registry is a
  stub ("see previous conversation").
- `knowledge-brain` packs (`free-minimal`, `pro-capable`,
  `private-omniscient`) — empty tier shells; local `core/levi/packs/`
  already covers scoped knowledge packs.
- `LWP_UNIFIED_COMPLETE` / `CASCADE_*` assemblies — earlier L.W.P.
  generation, superseded by the tested `core/levi/lwp/` press console.
- `lwp_sovereign_backend.py` — a FastAPI network service; contradicts
  offline-first on its face.
- `wyrd_*.zip` HTML consoles — the web UI already exists.
- `LEVI_Smithsonian_Kit` — two reference markdowns; not code.
- VYVE blueprint, pasted chat texts, prompt docs — different product or
  non-code.

The corpus remains preserved untouched at `~/workspace/grok-lwp-recovery/`
as evidence. If a future piece proves additive, it gets the same
inspect → diff → earn-its-place treatment.
