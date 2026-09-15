# LEVI Console & Simulation

Two interactive surfaces built on the `levi.ux` terminal effects kit
(`core/levi/ux/`). Both are stdlib-only, pipe-safe, and LEVI-branded.

## `levi console` — the interactive dashboard

Menu-driven text dashboard. Requires an interactive terminal; otherwise it
prints `levi console needs an interactive terminal.` and exits 1.

Screens (registry: `levi.console.app.SCREENS`):

| Key        | Screen                  | What it does                                         |
|------------|-------------------------|------------------------------------------------------|
| `security` | Security index browser  | Browse/search the 81-domain offline security index   |
| `bounty`   | Bounty recon            | Pick a scope, run recon with live finding feed       |
| `demand`   | Demand digest           | DemandPulse status + top five-factor score cards     |

Keyboard: number or letter to choose, `q` to quit/back. Inside the
security browser: `n`/`p` page, `s` search, `v` view entry.

**Design rule:** the console adds no new capabilities. Every screen calls
existing module functions (`levi.bounty.pipeline.run_recon`,
`DemandPulse`, the security catalog loader). Anything the console can do,
a plain CLI flag can do too.

**Extension point:** to add a screen (finance, agent, news…), write a
`screen_*() -> None` handler in `core/levi/console/screens.py` and add one
line to `SCREENS`. The menu loop picks it up with no other changes.

## `levi sim` — bounded text simulations

Clearly-labeled, deterministic, **zero real network** simulations.
Every scenario opens and closes with a `SIMULATION` banner and every line
of output is marked simulated. This is LEVI's bounded-simulation law:
sim output is never presented as real.

```
levi sim --list
levi sim bounty-hunt --seed 7
levi sim soc-shift --seed 42
```

| Scenario      | What it is                                                                    |
|---------------|-------------------------------------------------------------------------------|
| `bounty-hunt` | A fictional target org (`simtarget-<seed>.test` — RFC 2606, never real). The **real** `run_recon` orchestration runs unmodified against a shimmed network layer: scope gate, detectors, and pipeline logic are genuinely exercised; only the packets are fake. Ends with a debrief: coverage score + blind-spot list. |
| `soc-shift`   | Simulated SOC night shift: ~25 seeded events (attacks, false positives, noise). You triage each alert — investigate / escalate / dismiss — and get a graded shift report (S/A/B/C). |

Determinism: `--seed` drives all randomness. Same seed → identical world
and transcript (tested by transcript hash). Isolation: sim stores
(scope, findings) live in temp dirs; the real `~/.levi` is never touched.
The zero-network test turns `socket`/`urllib` into landmines — both
scenarios complete without tripping them.

**Honest limit:** the sim proves orchestration, scope gate, and detectors
work. It cannot prove the pipeline survives the real internet — timeouts,
rate limits, malformed responses, and DNS quirks are idealized away.

## The `levi.ux` effects kit

`color`, `banner`, `rule`, `Spinner`, `ProgressBar`, `Table`,
`typing_print`, `status_line`/`clear_status_line`, `sparkline`, `meter`,
`menu`, `confirm`, `pause_for_key`.

**Pipe-safety contract:** every effect consults `effects_enabled()`. When
stdout is not a TTY or `NO_COLOR` is set: zero ANSI codes, no cursor
movement, no animation — plain readable text. Progress bars degrade to
periodic one-line updates; spinners to a single static line; typing
effects print instantly. Safe in pipes, logs, and CI — always.
