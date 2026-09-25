---
skill_id: web_ops_health_checks
name: Health Checks and Readiness
description: Liveness vs readiness probes: what load balancers check, and how to report degraded but alive.
risk: info
permissions: []
requires_confirmation: false
tags: [ops, deployment]
version: 1.0.0
---
# Health Checks and Readiness
## Purpose
Let orchestrators route around trouble automatically by reporting honest health, not just 'process alive'.
## Key ideas
- Liveness asks 'is it running'; readiness asks 'can it serve traffic right now'.
- A service can be alive but not ready (warming caches, migrations running); only readiness should gate traffic.
- Health endpoints must be cheap and dependency-aware: check what serving actually needs.
- Failing readiness removes the instance from rotation; flapping readiness causes flapping traffic.
- Deep checks belong on a separate diagnostic endpoint, not on the hot path the balancer polls.

## In practice
Expose two endpoints: /healthz for liveness (cheap, always 200 if the process is sane) and /readyz for readiness (checks database connectivity, required caches, migration state). Make readiness checks fast with short timeouts; a probe that hangs is worse than one that fails, because it holds the balancer's attention. During startup, report not-ready until initialization truly completes, so no request meets a half-built service. Log every readiness transition with the reason; when traffic shifts mysteriously, the readiness history is usually the explanation.

```python
from flask import Flask, jsonify
app = Flask(__name__)

@app.get("/healthz")
def liveness():
    return jsonify(status="alive"), 200

@app.get("/readyz")
def readiness():
    checks = {
        "database": db.ping(timeout=2),
        "cache": cache.ping(timeout=2),
        "migrations": migrations_current(),
    }
    ok = all(checks.values())
    return jsonify(checks=checks), 200 if ok else 503
```

## Common mistakes
- Using one endpoint for both, so a warming instance gets traffic or a sick one never gets restarted.
- Making health checks expensive (full table scans), so the probe itself degrades the service.
- Reporting ready before initialization finishes, serving errors to the first requests.

## Checklist
- Are liveness and readiness separate endpoints with distinct semantics?
- Do readiness checks cover real dependencies with short timeouts?
- Is startup ordered so traffic arrives only when truly ready?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
