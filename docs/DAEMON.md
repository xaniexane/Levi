# LEVI Daemon — unified supervisor

LEVI's long-running services are supervised, not installed. One foreground
supervisor (`core/levi/daemon/supervisor.py`) knows every service as data and
can check all of them with a single command. Nothing runs unless the user
starts it, and nothing survives the user closing it.

## The service catalog

`Supervisor.SERVICE_CATALOG` is static data — every LEVI service as one dict
with `name`, `module`, `summary`, `start_hint`, and a zero-arg `health`
callable returning `(ok: bool, detail: str)`:

| name | module | what it is |
|---|---|---|
| `control-daemon` | `levi.daemon.control` | Personas, wit styles, alchemy stances; no-pure-negative control plane |
| `automation-engine` | `levi.daemon.automation` | Scheduled automations registry (triggers, actions, due runs) |
| `daemon-kernel` | `levi.daemon.kernel` | Event bus, tool registry, audit trail, safety-level enforcement |
| `heartbeat` | `levi.daemon.heartbeat` | Periodic self-check; silent when nothing needs attention (see `docs/HEARTBEAT.md`) |
| `perpetual` | `levi.perpetual.supervise` | Supervision loops (heartbeat/growth/automation children), crash reports, hunt waves |
| `galaxy-services` | `levi.galaxy.service` | Third-party service packages: ports, verbs, install registry |
| `oath-trust` | `levi.oath` | Cryptographic trust: contacts, commands, audit ledger, inbox |
| `agent-server` | `levi.agent.server` | Agentic loop HTTP server (`POST /v1/agent/chat`, bearer auth) |

Health checks never raise (an exception becomes `(False, "<error>")`), never
bind a port, never spawn a thread, and never start a background process —
they only instantiate each service's core object against the LEVI home and
ask whether it is coherent.

## Foreground-only operation — why no OS daemons

LEVI never installs itself behind the user's back: no systemd units, no
launchd plists, no cron jobs, no OS daemons. The user owns their machine,
and anything LEVI runs must be something the user started and can see. A
"pulse" is one foreground pass of every health check, run by the user (or by
a foreground process the user started) and then exiting.

This is deliberate, not a missing feature: background installation is the
one privilege LEVI will not grant itself. If the user wants periodic pulses,
they schedule them themselves with their own tools — LEVI provides the
command, never the installation.

## Running the pulse

```bash
# one foreground pass over all eight services
python -m levi.daemon pulse

# the catalog
python -m levi.daemon list

# health of one service, or all
python -m levi.daemon status heartbeat
python -m levi.daemon status --json
```

`--home <dir>` (or `$LEVI_HOME`) points the supervisor at a different LEVI
home; the default is `~/.levi`.

## Stable API (for the CLI and other workers)

```python
from levi.daemon.supervisor import (
    list_services,    # -> list[dict]: the catalog
    service_status,   # (name) -> dict: one service's health; "unknown" if not found
    all_status,       # -> dict[str, dict]: every service's health
    supervise_once,   # -> dict: the foreground pulse (ran_at, up, down, services)
)
```

`service_status()` never raises on unknown names — it returns
`{"status": "unknown", "ok": False, ...}` listing the known services. Every
health callable is guarded so a broken service reports `down` with the error
in `detail` instead of crashing the pulse.
