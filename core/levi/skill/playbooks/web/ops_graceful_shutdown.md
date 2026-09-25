---
skill_id: web_ops_graceful_shutdown
name: Graceful Shutdown
description: Shut down without dropping work: signal handling, draining connections, and deploy sequencing.
risk: info
permissions: []
requires_confirmation: false
tags: [ops, deployment]
version: 1.0.0
---
# Graceful Shutdown
## Purpose
Make restarts and deploys invisible to users by finishing in-flight work before exiting.
## Key ideas
- SIGTERM means 'please stop soon'; SIGKILL means 'stop now' with no cleanup.
- On SIGTERM: stop accepting new work, finish in-flight requests, close connections, then exit.
- Load balancers need a drain window: deregister first, wait, then signal the process.
- Shutdown needs a timeout; work that cannot finish in time must be requeueable, not losable.
- Rolling deploys replace instances one at a time so capacity never drops to zero.

## In practice
Handle SIGTERM explicitly in every service: set a flag that stops the accept loop, wait for active requests with a deadline (30 seconds is typical), then close database pools and exit. Coordinate with the load balancer: mark the instance draining, wait for existing connections to migrate, and only then terminate. Design background jobs to be interruptible and requeueable, because a deploy will eventually interrupt one mid-run. Test shutdown in staging by deploying under load and counting failed requests; zero failures is the bar, and anything above it is a bug in the drain sequence.

```python
import signal, sys

shutting_down = False

def on_term(signum, frame):
    global shutting_down
    shutting_down = True          # stop accepting new work
    # finish in-flight requests (with deadline), close pools, then exit

signal.signal(signal.SIGTERM, on_term)

while not shutting_down:
    serve_one_request(deadline=30)

close_pools()
sys.exit(0)
```

## Common mistakes
- Ignoring SIGTERM so the orchestrator SIGKILLs mid-request, dropping user work.
- Deregistering and killing simultaneously, stranding in-flight requests.
- Writing background jobs that cannot be safely interrupted and re-run.

## Checklist
- Does SIGTERM trigger drain-then-exit with a bounded timeout?
- Is load-balancer deregistration sequenced before process termination?
- Are background jobs interruptible and requeueable?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
