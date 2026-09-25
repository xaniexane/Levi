---
skill_id: web_ops_processes_supervision
name: Process Supervision
description: Keep services running with supervisors: restarts, backoff, and what a process manager guarantees.
risk: info
permissions: []
requires_confirmation: false
tags: [ops, deployment]
version: 1.0.0
---
# Process Supervision
## Purpose
Make 'the service died at 3am' a non-event: supervised processes restart themselves with sane limits.
## Key ideas
- A supervisor (systemd, runit, a container runtime) starts your process, watches it, and restarts it on failure.
- Restart policies need backoff: immediate tight-loop restarts on a persistent crash burn CPU and fill logs.
- The supervisor should own logging capture, so crashes leave their last words somewhere findable.
- Health and readiness are separate concerns from 'process is alive'; a running process can still be broken.
- One service per supervised unit keeps restarts, logs, and resource limits cleanly separated.

## In practice
Define the unit file or container spec as code, checked into the repo beside the service, so the production process matches what developers run. Set restart with a backoff ceiling and a start limit; a service that crashes ten times in a minute is telling you something, and the supervisor should eventually stop and page rather than spin forever. Capture stdout/stderr into the central log pipeline from day one, because the crash you cannot read is the crash you cannot fix. Test the supervision itself: kill the process in staging and watch the supervisor bring it back, measuring how long the gap lasts.

```ini
[Unit]
Description=orders-api
After=network.target postgresql.service

[Service]
ExecStart=/opt/orders/bin/api --config /etc/orders/api.env
Restart=on-failure
RestartSec=5
StartLimitIntervalSec=300
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

## Common mistakes
- Running production services from a terminal session with no supervisor, so a hang or reboot ends them silently.
- Restarting instantly with no backoff, turning a config error into a CPU-burning crash loop.
- Losing crash logs because stdout went nowhere the team can read.

## Checklist
- Is every production process supervised with restart and backoff?
- Are unit specs versioned alongside the service code?
- Do crash logs land in a searchable, retained store?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
