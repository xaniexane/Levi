---
skill_id: cyber_detecting_broken_object_property_level_authorization
name: Detecting Broken Object Property Level Authorization
description: Detect BOPLA/API3 mass-assignment and property-tampering attacks with schema-aware API monitoring.
risk: info
permissions: []
requires_confirmation: false
tags: [api, detection, web]
version: 1.0.0
---
## Purpose

Detect Broken Object Property Level Authorization (OWASP API3:2023) — attackers writing to properties they shouldn't touch (mass assignment, `is_admin: true`, read-only field tampering) — by monitoring API requests against the authorized property schema. This is the vulnerability class behind "the user made themselves admin via a PUT request."

## When to use

- Protecting APIs with role-dependent object properties (user roles, prices, account status, approval flags).
- Testing and monitoring after implementing property-level authorization.
- Investigating suspected privilege tampering via API (a user whose role changed unexpectedly).
- Auditing API request logs for mass-assignment attempts.

## Prerequisites

- API request/response logging with full bodies (or at least field names) at the gateway or application layer.
- A property-authorization matrix: which roles may write which fields on which objects.
- Baseline of normal write patterns per role (which fields each role legitimately updates).
- Alerting path with the API owner and a process to revoke tampered privileges.

## Procedure

1. **Build the property-authorization matrix.** For each API object, document every writable property and which roles may write it. Mark explicitly: immutable properties (IDs, creation timestamps), role-restricted properties (`role`, `is_admin`, `account_status`, `price`, `approved`), and read-only-by-design fields. This matrix is the detection reference — without it, you can't distinguish attack from feature.
2. **Detect writes to restricted properties.** Alert when a request body contains properties the caller's role may not write: a standard user sending `role`, `is_admin`, or `account_balance`; any role sending immutable fields like `id` or `created_at`. Log the full request for forensics — the attempt itself is the evidence.
3. **Detect mass-assignment probing.** Alert on requests containing unusually many properties, properties not in the API schema at all (framework mass-assignment binds whatever you send), or rapid iterations of the same endpoint with varying property sets. Attackers fuzz property names; the fuzzing pattern is detectable.
4. **Monitor read-path property exposure.** BOPLA has a read side too: APIs returning properties the caller shouldn't see (password hashes, internal flags, other users' PII). Alert on response schemas deviating from the documented contract, and audit logs for clients systematically harvesting sensitive fields across many objects.
5. **Correlate with privilege changes.** Join property-write alerts with identity outcomes: did the user's role actually change? Did an order's price change? Did an approval flag flip? An attempt that succeeded is an active compromise requiring immediate privilege revocation and impact scoping — which records were tampered with, and what downstream actions resulted?
6. **Test your own APIs for BOPLA.** Periodically replay the detection logic as authorized tests: submit role-restricted properties as a low-privilege test user and verify they're rejected (not just ignored — silently ignoring is better than accepting, but explicit rejection with logging is best). Feed failures to the development team as vulnerabilities, not just monitoring gaps.
7. **Fix at the framework level.** The durable fix is allowlist-based binding (explicit `@JsonIgnore` / strong parameters / DTOs that only include writable fields), not blocklisting "bad" properties. Work with engineering to ensure every endpoint binds only its documented writable set, and re-run the BOPLA tests after each API change.

## Expected outputs

- A property-authorization matrix per API object with role-based write permissions.
- Detections for restricted-property writes, mass-assignment probing, and sensitive-field exposure.
- Correlation with actual privilege/data changes; framework-level allowlist binding as the remediation standard.

## Pitfalls

- No property matrix — you can't detect unauthorized writes without defining authorized ones.
- Blocklist-based filtering — attackers find the property you forgot; allowlists are the fix.
- Logging request bodies without a PII-handling policy — the detection logs become a sensitive-data store.
- Treating "silently ignored" as safe — it's better than accepted, but log and alert on the attempt anyway.
- Testing once — every new endpoint and every schema change re-opens the class.

## References

- OWASP API Security Top 10 (2023) — API3: Broken Object Property Level Authorization
- OWASP Testing Guide — API authorization testing methodology
- MITRE ATT&CK T1548 (Abuse Elevation Control Mechanism) in API context
- Framework documentation for mass-assignment protection (strong parameters, DTOs)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
