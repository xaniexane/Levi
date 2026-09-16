# INTERPENETRATION — the law as an engine

Interpenetration is a binding law of the LEVI organism (see
[INTEROP.md](INTEROP.md) for the doctrine): when modules compose into one
action, the composition inherits the **strictest (highest) risk level**
among its participants. This document describes the law *as an engine* —
the code that computes and enforces it, with a worked example.

## The machinery

```
                        ┌─────────────────────────────┐
                        │  levi.interop.risks           │  single source of the
                        │  RiskLevel ordering           │  ceiling ordering —
                        │  parse_level / ceiling /      │  never redefined,
                        │  compose_risk /               │  never duplicated
                        │  highest_caution              │
                        └──────────────┬────────────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        ▼                              ▼                              ▼
┌───────────────────┐        ┌───────────────────┐        ┌───────────────────┐
│ composites        │        │ gate              │        │ receipts          │
│ .effective_ceiling│        │ .run_composite_   │        │ carry the ceiling │
│ (pure function)   │        │  gated            │        │ + contributions   │
│                   │        │                   │        │ (why it was risky)│
│ bare level /      │        │ deny when auth <  │        │                   │
│ mapping / object  │        │ inherited ceiling │        │                   │
│ → {ceiling,       │        │ allow when auth   │        │                   │
│    contributions} │        │ meets it          │        │                   │
└───────────────────┘        └───────────────────┘        └───────────────────┘
```

Three layers, one law:

1. **Compute — `levi.bloodstream.composites.effective_ceiling(components)`.**
   A pure function: each component is a bare level (`RiskLevel` / int /
   name string), a mapping like `{"name": "rag", "risk": ...}`, or an
   object exposing `risk_level` / `risk_ceiling` (skills, specialists,
   automations). Returns `{"ceiling", "contributions"}` — the ceiling plus
   per-component evidence, so callers can audit *why* a composition is
   risky. **Deny-closed:** an unknown or unrated component does not dilute
   the ceiling — it raises it to the highest caution (`CRITICAL`). An
   empty component list has ceiling `INFO` (no parts, no risk).

2. **Enforce — `levi.bloodstream.gate.run_composite_gated(...)`.** The
   execution path. Computes the inherited ceiling, then:
   - If `authorization_level` is presented and is *below* the inherited
     ceiling → **denied outright**. The outcome carries an explicit reason
     naming the ceiling and the component(s) that raised it; nothing
     executes. The denial still walks Plan → Preview so it is auditable.
   - Otherwise the act runs the full six-step gate
     (Plan → Preview → Permission → Execute → Verify → Receipt) at the
     inherited ceiling's risk level. Without an explicit authorization,
     the standing ceiling (or the human `confirm` channel) decides — and
     the human sees the inherited ceiling in the proposal reason.

3. **Order — `levi.interop.risks`.** The one and only place the ceiling
   ordering lives (`RiskLevel`: INFO=0 … CRITICAL=4). `parse_level()` and
   `highest_caution()` are its public face; composites and the gate call
   them, never a private copy.

## Worked example

A turn composes three parts into one action:

| component | risk |
|---|---|
| `skill:file_read` (a LOW skill) | LOW (1) |
| `skill:shell_exec` (a HIGH skill) | HIGH (3) |
| `specialist:researcher` (a MODERATE specialist) | MODERATE (2) |

```python
from levi.bloodstream.composites import effective_ceiling
from levi.bloodstream.gate import run_composite_gated
from levi.policy.gates import PolicyEngine, RiskLevel

evidence = effective_ceiling([
    {"name": "skill:file_read", "risk": RiskLevel.LOW},
    {"name": "skill:shell_exec", "risk": RiskLevel.HIGH},
    {"name": "specialist:researcher", "risk": RiskLevel.MODERATE},
])
evidence["ceiling"]          # → RiskLevel.HIGH  (max wins; LOW does not dilute)
evidence["contributions"]    # → {"skill:file_read": LOW,
                             #    "skill:shell_exec": HIGH,
                             #    "specialist:researcher": MODERATE}
```

A LOW authorization for this act is **denied** — the ceiling is HIGH:

```python
out = run_composite_gated(
    engine=PolicyEngine(),
    name="ops",
    components=[...],          # as above
    description="ops composite",
    reason="nightly maintenance",
    execute=lambda: "done",
    authorization_level=RiskLevel.LOW,
)
out.approved      # → False
out.executed      # → False — nothing ever ran
out.error         # → "denied: composite 'ops' inherits risk ceiling HIGH
                  #    (raised by skill:shell_exec); presented authorization
                  #    LOW is below the ceiling — explicit approval at HIGH
                  #    or above is required"
```

The same act with HIGH authorization **proceeds** through all six gate
steps at HIGH risk:

```python
out = run_composite_gated(
    engine=PolicyEngine(),
    name="ops",
    components=[...],
    description="ops composite",
    reason="nightly maintenance",
    execute=lambda: "done",
    authorization_level=RiskLevel.HIGH,
)
out.approved      # → True
out.executed      # → True
out.ceiling       # → RiskLevel.HIGH
```

And the deny-closed default: add a component nobody can rate, and the
ceiling jumps to the highest caution — a HIGH authorization is no longer
enough:

```python
evidence = effective_ceiling([
    {"name": "skill:file_read", "risk": RiskLevel.LOW},
    {"name": "mystery_plugin"},          # unrated
])
evidence["ceiling"]   # → RiskLevel.CRITICAL
```

## Invariants (what tests prove)

- Low + high ⇒ HIGH. The strictest always wins, regardless of order.
- The ceiling ordering used by composites equals `risks.ceiling` for every
  level pair — there is exactly one copy of the rules.
- `authorization_level` below the inherited ceiling ⇒ denied, with the
  ceiling and its raisers named; nothing executes.
- `authorization_level` meeting or exceeding the ceiling ⇒ the full
  six-step gate runs at the ceiling's risk level.
- Unknown/unrated components ⇒ ceiling `CRITICAL` (deny-closed).

See `core/levi/bloodstream/tests/test_risk_ceiling_enforcement.py`.
