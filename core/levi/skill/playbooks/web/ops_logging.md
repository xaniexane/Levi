---
skill_id: web_ops_logging
name: Logging for Web Services
description: Log what matters: structured events, request tracing, levels, retention, and keeping secrets out.
risk: info
permissions: []
requires_confirmation: false
tags: [ops, deployment]
version: 1.0.0
---
# Logging for Web Services
## Purpose
Build logs that answer 'what happened' in minutes during an incident, not archaeology expeditions.
## Key ideas
- Structured logs (JSON with named fields) are queryable; free-text logs are archaeology.
- Every request gets a trace id propagated through services so one user's journey is one query.
- Levels (debug, info, warn, error) are a contract: error means needs attention, not merely interesting.
- Log the decision inputs (ids, codes, durations), never credentials, tokens, or full PII.
- Retention and rotation are part of the design; unbounded logs are a disk-full outage on a schedule.

## In practice
Standardize a small set of fields on every log line: timestamp in UTC, service, level, trace id, message, and key ids; everything else is optional context. Log at the boundaries: request in/out with duration and status, external calls with latency, and state changes with before/after ids. Keep debug logging behind a flag that can be enabled per-request via the trace id, so production stays quiet but diagnosable. Ship logs to a central store with retention matched to compliance needs, and test the pipeline by actually querying it during game days; the log system you cannot query under pressure is decoration.

```json
{"ts":"2026-09-22T06:10:00Z","svc":"orders-api","lvl":"info",
 "trace":"req_9f2c7a1e","msg":"order created",
 "order_id":987,"user_id":42,"duration_ms":84}
{"ts":"2026-09-22T06:10:01Z","svc":"orders-api","lvl":"error",
 "trace":"req_9f2c7a1e","msg":"payment charge failed",
 "order_id":987,"code":"CARD_DECLINED"}
```

## Common mistakes
- Logging passwords, tokens, or full card numbers, turning the log store into a breach waiting to happen.
- Free-text logs with no trace ids, making multi-service debugging a manual correlation nightmare.
- Letting logs grow unbounded until the disk fills and takes the service with it.

## Checklist
- Are logs structured with trace ids propagated across services?
- Are secrets and sensitive PII excluded by design, not by hope?
- Are retention, rotation, and central querying all working and tested?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
