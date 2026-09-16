# LEVI Signal Plane

Every daemon, heartbeat, and instinct speaks through one plane:
**grades → instincts → focus mute → active-hours gate → delivery**.
Package: `core/levi/signals/`. stdlib-only, local-first, no network.

## Signal grades

| Grade | User sees | Example |
|-------|-----------|---------|
| `SILENT` | **nothing** — no line, no log whisper, no output at all | `HEARTBEAT_OK`-style quiet pulse |
| `NUDGE` | one line in chrome (status bar / CLI), never chat | `[sentinel] focus block ends in 8m` |
| `CARD` | a tagged daemon card with actions | `[warden] DUE: ship landing page` |
| `ESCALATE` | a card that **requires acknowledgment** | `[warden] 2x missed lock` |

`route(signal)` returns a delivery descriptor. `SILENT` always routes to
*suppressed entirely* — the plane enforces this, so a silent result can
never leak into user-visible output by accident. `ESCALATE` always forces
`requires_ack=True`; callers cannot downgrade it.

Daemon voice is always a bracketed tag: `[warden]`, `[sentinel]`,
`[heartbeat]`, `[supervisor]` — daemon lines never look like chat.
Cards carry taps: **done / snooze 1h / drop** (per-card actions vary).

## Instinct spec format

An instinct is a tiny spec, not a vibe meter:

```yaml
id: instinct.two_miss
fires_on: commitments.missed>=2   # evidence key, optional >=, <=, ==, !=, >, <
cooldown: 86400                    # seconds
max_grade: ESCALATE
does: quote the original lock; demand a new time or an explicit drop
```

- **Evidence or it doesn't fire.** `fires_on` names a key in the evidence
  dict; a bare key fires when truthy, a suffixed comparison fires when
  the comparison holds. Missing keys never fire.
- **Cooldowns** persist at `<levi-home>/signals/cooldowns.json`. A second
  evaluation inside the window produces nothing (and does not refresh
  the cooldown). The LEVI home resolves at call time from `$LEVI_HOME`
  (else `~/.levi`) — never hardcoded, never read at import time.
- **Grade caps** are enforced by clamping: a handler may build any
  signal, but the plane downgrades anything above `max_grade` before
  returning it. An instinct NEVER emits above its max grade.

## The three wired instincts

Evaluated on every supervisor pulse via `wiring.signals_for_supervisor()`
and `wiring.default_registry()`:

| ID | Fires on | Grade | Cooldown | Does |
|----|----------|-------|----------|------|
| `instinct.two_miss` | `commitments.missed>=2` (real store, neutral copy) | ESCALATE | 24h | quotes the original lock; demands a new time or an explicit drop |
| `instinct.empty_block` | `focus.empty_block` (scheduled block ≥25m in, no session activity since it started) | CARD (due-now: pierces focus) | 50m | asks: done \| stuck \| switch |
| `instinct.error_spike` | `logs.error_spike` (≥5 errors in 1h or ≥10 in 24h across agent sessions) | CARD | 1h | surfaces the spike count; suggests a log review |

Focus blocks are declared in `<levi-home>/focus/blocks.json`:
`[{"name": "deep work", "start": "<ISO>", "end": "<ISO>"}]` (naive = local).
No blocks file → no focus evidence → the instinct stays silent.

## Focus contract

Modes: `focus` | `plan` | `review` | `play` (persisted at
`<levi-home>/signals/mode.json`, default `plan`).

- **focus**: only `due_now` signals and ESCALATE pass. Everything else is
  held — not downgraded, not queued loudly, just not delivered.
- **plan / review / play**: everything passes.
- **quiet mode** is equivalent to focus filtering.

`should_deliver(signal, mode)` is the predicate; `deliver()` runs it.

## Active hours

Default window **08:00–22:00 local**; configurable via
`ActiveHours(start=(h, m), end=(h, m))`, including overnight windows
(e.g. 22:00–06:00). Outside the window **only ESCALATE speaks**.
`should_deliver(signal, now)` takes an injectable clock (naive = local).

## Wiring (adapters — never rewrites)

- **Supervisor**: `signals_for_supervisor(report)` maps each down service
  to a `[supervisor]` CARD and layers the wired instincts on top,
  highest grade first. `pulse_with_signals(supervisor)` runs the whole
  foreground pulse: supervise → grade → focus → hours → render.
- **Heartbeat**: `heartbeat_to_signals(result)` maps a silent result to
  one SILENT signal; attention items become `[heartbeat]` CARDs (bullets
  fold into their parent card's body). `graded_digest(result, …)` runs
  the full pipeline and returns `None` when nothing survives — a SILENT
  heartbeat therefore produces genuinely no user-visible output.

## CLI

```bash
python -m levi.signals status
python -m levi.signals test-fire [--mode focus|plan|review|play] [--json]
```

`test-fire` evaluates the wired instincts against live evidence and shows
what the delivery pipeline would let through. `status` shows instincts,
cooldowns, mode, and the active-hours window.
