# MEGAZORD

> **Scope disclaimer:** this is persona scaffolding + flow stubs, **not a real
> engine.** Five persona presets, a think/decide/act flow loop, and thin
> adapters — single-process, in-memory, no persistence, no transport, no tests.
> Anything beyond that is planned work, not what is here.

Persona scaffolding + flow stubs that sit on top of the LEVI core. Today this
package is five persona presets (CYBRUS, ECHO, ALPHA, OMEGA, RUNTIME — there is no
LEVI persona), a think/decide/act flow loop, and thin persona adapters.

> **Status: alpha.** Single-process, in-memory, no persistence, no transport
> layer, no tests, no docs/ or scripts/ directories yet. Anything this README
> (or the root README) says about an L.W.P. protocol, gateways, or smoke tests
> describes planned work, not what is here.

## Layout

| Subsystem | Role |
|-----------|------|
| `megazord/personas/` | Persona presets: `cybrus_persona.py`, `echo_persona.py`, `alpha_persona.py`, `omega_persona.py`, `runtime_persona.py` + `persona_core.py` (`Persona`, `PersonaRegistry`, `DEFAULT_REGISTRY`) |
| `megazord/flows/` | Flow engine core + the think/decide/act steps: `flow_core.py`, `levi_think.py`, `levi_decide.py`, `levi_act.py` |
| `megazord/bridges/` | Adapters: `levi_bridge.py` plus `alpha/`, `cybrus/`, `echo/`, `runtime/` bridge modules |
| `megazord/megazord_core.py` | `MegaZord` — the unified think→decide→act loop over a chosen persona |

## Personas

The five voices of the megazord, as declared in `personas/__init__.py`:

| Persona | Role |
|---------|------|
| **CYBRUS** | Security, gatekeeping, threat assessment |
| **ECHO** | Blueprint designer, builder, creator |
| **ALPHA** | No-code AI compiler, executor, operator |
| **OMEGA** | OS brain, orchestrator, long-game strategist |
| **RUNTIME** | Logic runtime, memory, cross-orchestration brain |

## Use (dev)

```bash
cd delivery/megazord
PYTHONPATH=. python -c "
from megazord import MegaZord
z = MegaZord(persona='alpha')
print(z.think('Levi, run a diagnostic'))
"
```

## Quick API

```python
from megazord.bridges.levi_bridge import LeviBridge

bridge = LeviBridge(persona="alpha")
event = bridge.dispatch(raw_envelope_bytes)  # inbound
action = bridge.build_action(
    "system.diagnostic",
    "levi",
    {"scope": "full"},
    soul={"joy": 0.7, "trust": 0.9, "fear": 0.0, "surprise": 0.2, "sadness": 0.0},
)
```

## Spec & Status

- Personas: CYBRUS, ECHO, ALPHA, OMEGA, RUNTIME — see `megazord/personas/__init__.py`
- Levi runtime: v34 (hardened core) — see `core/levi`
- Status: **alpha** — persona scaffolding + flow stubs only; single-process,
  in-memory, no persistence, no transport, no tests yet
