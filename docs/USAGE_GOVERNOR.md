# LEVI Usage Governor

**The pain it fixes:** API/token usage spikes with no cool-down periods and no
way to see what caused them. The governor adds all three: metering with cause
attribution, spike detection, and automatic cool-downs — plus deny-closed
budgets and a plain-language "why did usage spike?" diagnosis.

Package: `core/levi/governor/` — additive, stdlib-only, local-first.
State lives under `~/.levi/governor/` (JSONL ledger, JSON circuit state,
JSON config; all owner-only files).

## Components

| Module | Job |
|---|---|
| `meter.py` | Per-call token ledger. Every record: timestamp, provider, model, task id, agent id, tool name, prompt fingerprint, tokens in/out. Attribution is the point — any token is traceable to its cause. |
| `spikes.py` | Two-window spike detector per attribution key (`global`, `provider:…`, `task:…`, `tool:…`, `agent:…`). Alerts when the current window exceeds N× (default 4×) the previous window, or blows an absolute cap (default 500k). No silent passes — every breach returns a `SpikeAlert` with the numbers. |
| `cooldown.py` | Circuit breaker per scope (default scope: one provider). closed → open → half-open. While open, calls are **refused with a clear reason** (`[governor] call refused: cool-down — …`), never silently dropped. Exponential backoff on repeated breaches (60s → 30min cap). State persisted, survives restarts. Deny-closed: an unreadable state file refuses everything until `reset`. |
| `budgets.py` | Per-session (default 200k) and per-day (default 2M) token budgets, deny-closed, configurable in `~/.levi/governor/config.json`. |
| `diagnose.py` | `top_contributors()` + `summarize()`: top token spenders over any window, correlated with cool-downs and budgets, rendered in plain language. This answers "not even have the cause behind them." |
| `priority.py` | Honest priority lane: `BurstPass` entitlements + `PassWallet`. Passes reserve the half-open probe slot during genuine contention only — they cannot manufacture it. See "Priority lane (honest)" below. |
| `governed.py` | The integration seam: `GovernedProvider` decorates any `ChatProvider` (same interface), and `governed_call()` is the one-shot version. |

## CLI

```bash
PYTHONPATH=core python -m levi.governor status      # totals, budgets, circuits
PYTHONPATH=core python -m levi.governor top --by tool --window 3600
PYTHONPATH=core python -m levi.governor why         # plain-language diagnosis
PYTHONPATH=core python -m levi.governor cooldowns
PYTHONPATH=core python -m levi.governor budgets
PYTHONPATH=core python -m levi.governor reset provider:openai
```

(The top-level `levi usage` name is already taken by the cloud surface's
`levi cloud usage`, so the governor ships as `python -m levi.governor`.)

## Priority lane (honest)

Burst passes are the monetization mechanism for contention — built on a
hard honesty rule: **passes can only ever act during genuine contention.
They cannot create it.**

- **What a pass buys:** during a genuine cool-down, the single half-open
  probe slot is the only scarce resource. Presenting a valid burst pass
  while a circuit is open redeems one use and *reserves that probe slot*.
  When the backoff elapses, the pass holder's call goes first; everyone
  else is told the slot is reserved by a priority pass holder.
- **What a pass cannot do:** against a closed circuit a pass changes
  nothing and consumes nothing — passes are worthless without real
  contention, by design. There is no code path by which issuing,
  holding, or redeeming a pass opens a circuit, alters metering, or
  manufactures load. (This is asserted by tests, including a source scan
  that bans overload-theater language like "servers are busy".)
- **Labeling:** every pass-influenced message says exactly what happened:
  "genuine contention on 'provider:x'", "priority pass 'bp_…' now holds
  the next probe slot (1 use consumed)". Metered records carry
  `priority_pass_id`, and `levi.governor why` reports pass usage
  separately. Nothing is ever framed as "servers overloaded."
- **Lifecycle:** `python -m levi.governor pass-issue --scope provider:openai
  --uses 10 --ttl 86400 --note "stripe:pi_123"` creates a pass (the
  `--note` is where the seller records the payment reference; selling is
  outside the governor). Passes expire, are scope-checked, and are
  refunded if a reservation is cancelled or the circuit is manually reset.
- **In code:** `GovernedProvider(..., pass_id="bp_…")` or
  `gov.chat_with_pass(messages, tools, pass_id)`.

## Integration seam (pending wiring)

The governor is built and tested but **not yet wired into the agent loop** —
deliberately, to avoid touching in-flight files. The patch is one line in
`core/levi/agent/loop.py`, inside `run_subtask()`, right after the provider
is resolved (~line 238):

```python
    if isinstance(provider, ChatProvider):
        prov = provider
    else:
        prov = select_provider(provider)

    # Usage governor (opt-in, one line): meter every model call, detect
    # spikes, enforce cool-downs. Removing it changes nothing else.
    from levi.governor import GovernedProvider
    prov = GovernedProvider(prov, task_id=task, agent_id="agent-loop")
```

This is safe because `provider_name` (computed just below) reads
`prov.name`, which `GovernedProvider` delegates to the inner provider, and
because refusals arrive as `ChatResponse(error=…)` — the exact shape the
loop already handles at the `if resp.error:` branch (it ends the run with
an honest message instead of crashing).

One patch covers the loop, the chat REPL (`agent/chat.py` calls
`run_subtask`), and the agent server (`agent/server.py`) — they all funnel
through `run_subtask`.

**Priority lane wiring (optional):** if the caller holds a burst pass,
attach it — it only matters during genuine contention:

```python
    prov = GovernedProvider(prov, task_id=task, agent_id="agent-loop",
                            pass_id=user_burst_pass_id)  # or None
```

or per call: `prov.chat_with_pass(messages, tools, pass_id)`.

**Attribution sharpening (follow-up):** a model call's `tool_name` currently
defaults to whatever the wrapper was constructed with. For per-tool
attribution inside the loop, after each tool-execution step set
`prov.tool_name = <name of the tool just executed>` before the next
`prov.chat(...)` (plain attribute on `GovernedProvider`). The next model
call is then attributed to the tool whose result it is reasoning about.

## Defaults (all configurable)

- Spike window: 600s, multiplier 4×, absolute cap 500k tokens, floor 2k.
- Cool-down: 60s base backoff, doubling per breach, 30min cap.
- Budgets: 200k tokens/session, 2M tokens/day.

## Honest gaps

- Budgets are token-count based, not cost based — no price table is baked
  in (providers change prices; a wrong table is worse than none).
- Cool-down scope is per provider, not per task: a runaway task on the
  local rules engine won't trip the cloud provider's breaker and vice
  versa. Per-task breakers are a natural next step.
- Refused calls end the agent run with an honest error; there is no
  automatic "queue and retry after cool-down" — queuing unbounded work is
  how you get a bigger spike later. (The priority lane's probe-slot
  reservation is the deliberate exception: exactly one slot, explicitly
  labeled, consumable.)
- The spike detector needs a baseline: on a cold start the first window
  has nothing to compare against, so only the absolute cap can fire.
- Session budget is per `BudgetEnforcer` instance lifetime (i.e. per
  process); a daemon that forks per request would need a shared session
  id — documented, not built.
- Simulated scarcity is off the table by user directive: there is no
  mechanism — and must never be one — that manufactures contention to
  sell passes. The deception-guard test (`test_no_fake_scarcity_language`)
  scans the governor's user-facing strings for overload theater.
