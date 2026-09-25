# POWER.md — LEVI signal layer (`levi.power`)

Organism-wide power primitives, generalized from L.W.P.'s power concepts.
Generic and non-narrative: any organ imports these and moves signal
lawfully. Nothing in this layer knows what a story is.

## Primitives

| Primitive | Module | Job |
|---|---|---|
| `Signal` | `signal.py` | Dumb energy packet: value, strength (0–1), noise (0–1), opaque payload, tags. Decays per hop via `attenuate()`. |
| `Transformer` / `TransformChain` | `transformer.py` | Convert energy (value mapping) **and** isolate noise — anything below the noise floor is quarantined, never passed downstream. |
| `Booster` | `amplifier.py` | Short intensity amp. Multiplies while charges last, then passes through untouched. Sprints, not baselines. |
| `GainStage` | `amplifier.py` | Step-up toward a target band. Adds `step` per round until the value sits in the band, then holds. Climbing, not spiking. |
| `StepAmplifier` | `amplifier.py` | Named fixed steps applied by kind (`apply(value, kind)`); unknown kinds pass through. |
| `Repeater` | `repeater.py` | Decay resistance. Re-injects a kept essence every `interval` hops so length cannot rot the signal. `Repeater.multi` cycles several essences (rare multi-sequence). |
| `CircuitBreaker` | `breaker.py` | Fault isolation. Opens after N consecutive failures (calls refused fast with `BreakerOpen`); one probe after cooldown — success closes, failure re-opens. Manual `isolate()`/`reset()` for operators. |
| `PowerRail` | `rail.py` | Load balancing. Shares a per-round budget across consumers by weight, capped by need, with leftover redistribution. Each consumer has its own breaker — a faulted consumer is isolated while the rail keeps serving the healthy ones. |
| `Direction` | `rail.py` | Signal routing: `FORWARD` (consumer order), `REVERSE` (back toward source), `INVERSE` (same door, opposite cost — value negated), `FREE` (first healthy consumer). |
| `PowerRail.surge` | `rail.py` | Endgame gear: multiply the budget for N rounds. Breakers stay armed — a surge never excuses a fault. |

## Quick use

```python
from levi.power import PowerRail, Signal, Direction, Booster, Repeater

rail = PowerRail("drive")
rail.consumer("indexer", lambda d: index(d.signal), weight=2.0)
rail.consumer("notifier", lambda d: notify(d.signal), weight=1.0, need=10.0)

report = rail.distribute(budget=100.0, signal=Signal(value=1.0))
print(report.allocations, report.isolated)  # faults isolate, the rail flows on

rail.surge(factor=2.0, rounds=1)  # finale: surge under breakers
rail.route(Signal(value=5.0), Direction.REVERSE)

boosted = Booster(factor=1.5, charges=3).apply(Signal(value=10.0))
kept, log = Repeater(essence="checkpoint", interval=5).propagate(
    Signal(value=1.0), hops=20
)
```

## L.W.P. mapping

L.W.P.'s powers are bound to these primitives in `levi.power.lwp`
(`PowerProfile` per power name); `model_engine` delegates its word-target
steps and repeater engagement to that binding instead of hard-coding them.
Behavior is unchanged — the numbers and rules now live in one place.

| L.W.P. power | Primitive composition |
|---|---|
| `repeater` | `Repeater` — re-injects the kept scar so length does not rot |
| `booster` | short step amp (+30 word-target step) |
| `transformer` | `Transformer` — convert energy, isolate noise |
| `gain` | step-up toward the band (+70 word-target step) |
| `immortal` | rare multi-sequence: `Repeater.multi` cycling essences (+120 step) |
| `finale` phase | `PowerRail.surge` — endgame surge under breakers |

Directions (`forward`/`reverse`/`inverse`/`free`) map to `Direction` routing
when an organ needs them as signal routing rather than story direction.

## Laws

- This layer never interprets payloads. Meaning belongs to organs.
- Conversion never passes rot downstream: quarantine is part of the transform.
- A faulted consumer is isolated; the rail is never killed by one consumer.
- Surges amplify budgets, never excuse faults.
