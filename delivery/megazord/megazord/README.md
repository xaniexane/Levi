# LEVI × L.W.P. MEGAZORD

The combined organism of **LEVI** (Soul/Genome + 5D Emotional Intelligence) and
**L.W.P.** (Lightweight Workspace Protocol). A single, deployable package that
plugs Levi into any external surface — Omega OS, third-party tools, automations,
browsers, devices, terminals — through a tiny, soul-aware protocol.

## Why "megazord"?
Each subsystem is a small, focused robot. Together they form one organism:

| Subsystem | Role |
|-----------|------|
| `personas/` | Cybrus, Echo, Alpha, Omega, Kai — Levi's voices |
| `flows/`    | How Levi thinks, decides, and acts over time |
| `bridges/`  | Adapters into Omega OS, Kai runtime, Echo compiler, Cybrus security |
| `lwp/`      | The transport that ties it all together (mirrored from `omega_os/lwp/`) |
| `tests/`    | Roundtrip validation for envelopes, souls, and personas |
| `docs/`     | Architecture, threat model, persona reference |
| `scripts/`  | Run, build, deploy, and test helpers |

## Install (dev)
```bash
cd megazord
pip install -r ../core/requirements.txt
python -m tests.smoke
```

## Run
```bash
# Start the Levi gateway (HTTP + WebSocket)
python -m bridges.omega.gateway --port 7860

# In another shell, send a soul-aware prompt
python -m examples.send_prompt "Levi, run a diagnostic"
```

## Quick API
```python
from bridges.levi_bridge import LeviBridge

bridge = LeviBridge(persona="alpha")
event  = bridge.dispatch(raw_envelope_bytes)              # inbound
action = bridge.build_action("system.diagnostic", "levi",
                             {"scope": "full"},
                             soul={"joy": 0.7, "trust": 0.9, "fear": 0.0, "surprise": 0.2, "sadness": 0.0})
```

## Spec & Status
- L.W.P. version: **0.1.0** — see `lwp/protocol/SPEC.md`
- Levi runtime:   **v34 (hardened core)** — see `../core/README.md`
- Status:         **alpha** — single-process, in-memory, no persistence yet
