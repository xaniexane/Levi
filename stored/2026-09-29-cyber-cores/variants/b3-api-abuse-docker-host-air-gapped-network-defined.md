---
skill_id: cyber_b3_api_abuse_docker_host_air_gapped_network_defined
name: Public API Abuse Defense for Docker Hosts in Air-Gapped Networks (Defined Maturity)
description: "Public API Abuse defense playbook for Docker Hosts in Air-Gapped Networks at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [web, api, containers, docker, air-gap, ot, high-security, maturity-defined]
version: 1.0.0
---
# Public API Abuse Defense for Docker Hosts in Air-Gapped Networks (Defined Maturity)

## Purpose

Exposed APIs are probed for injection, broken auth, and excessive data exposure. API abuse looks like legitimate traffic at volume — detection needs API-aware logging (endpoint, parameters, auth context), not just web logs. Applies to Docker Hosts in Air-Gapped Networks at Defined maturity.

## When to use

- High-rate 4xx/5xx sequences against API endpoints indicating fuzzing, or single clients enumerating object IDs sequentially.
- Authenticated API calls accessing other users' objects (BOLA/IDOR patterns) or returning bulk data far beyond normal use.
- Known attack strings (SQLi, SSTI payloads) in API parameters.
- Lens: Best telemetry: Docker daemon logs + host auditd + container stdout/stderr shipped centrally. Local SIEM/log collector inside the enclave (no cloud shipping); removable-media transfer logs.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Strict allowlisting logs: every binary execution recorded, since the set is small and known.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Docker daemon log (container create/start with full flags), docker events history and Container image digests and layer histories (docker history) versus expected digests; run `docker ps --format '{{.Names}} {{.Image}}' ; echo ---; docker events --since 24h --until 0s 2>/dev/null | tail -20` then `docker inspect $(docker ps -q) --format '{{.Name}} privileged={{.HostConfig.Privileged}} mounts={{.Mounts}}' 2>/dev/null`.
3. **Analyze.** Replay the suspect API sessions to determine exactly which records were accessed — the breach scope is the data returned, not the requests made. Then: Check whether the abused endpoint lacks authorization checks versus a credentialed attacker using stolen tokens.
4. **Contain and harden.** Positive-security API gateway policies: schema validation, rate limits per client, and authorization checks on every object reference. Asset layer: No --privileged, no host socket mounts except for explicit agents, user namespaces enabled, read-only root filesystems. Environment layer: Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- WAF-only defense: most API abuse is semantically valid HTTP that no signature catches.
- Logging without the auth context — you cannot distinguish attack from customer without knowing WHO called.

## References

- MITRE ATT&CK: T1190 (Initial Access: Exploit Public-Facing Application)
- Vendor logging and hardening baselines for Docker Hosts; Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
