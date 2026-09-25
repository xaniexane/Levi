---
skill_id: cyber_implementing_velociraptor_for_ir_collection
name: Implementing Velociraptor for IR Collection
description: Deploy Velociraptor for rapid, targeted forensic collection across the fleet during incidents.
risk: moderate
permissions: []
requires_confirmation: true
tags: [incident-response, forensics, velociraptor]
version: 1.0.0
---
## Purpose
This playbook covers deploying Velociraptor as an incident-response collection platform: server setup, client rollout, artifact design, and disciplined use during live incidents. Because collection touches live production endpoints, every collection run requires explicit confirmation and scoping.

## When to use
- Responding to an incident spanning many endpoints where manual collection is too slow.
- Building proactive hunting capability with scheduled artifact collection.
- You need a free, open-source alternative to commercial EDR forensic collection.

## Prerequisites
- Management approval for deploying an agent with remote collection capability to endpoints.
- Server infrastructure with TLS certificates and storage sized for collected artifacts.
- Defined collection policies: what may be collected routinely vs. only during declared incidents.

## Procedure
1. **Deploy the server securely.** Install Velociraptor with proper TLS, authentication (SSO or strong local accounts), and role-based access; restrict who can launch collections.
2. **Roll out clients in phases.** Pilot on IT-owned systems, validate performance impact, then expand; document the rollout for audit.
3. **Curate the artifact library.** Start with high-value artifacts: process listings, autoruns, browser history, event logs, recent file modifications, memory-adjacent artifacts.
4. **Scope every collection.** Before launching, record: incident ID, target hosts, artifact set, time bounds, and approver. Never run fleet-wide collection without incident-commander approval.
5. **Collect with care.** Prefer targeted artifacts over full disk images during triage; escalate to full acquisition only when analysis demands it, preserving chain of custody.
6. **Analyze centrally.** Use hunts and notebooks to correlate across hosts; export findings into the case record with hashes and timestamps.
7. **Review and purge.** After the incident, review what was collected, retain per policy, and purge data that exceeds retention or was out of scope.

8. **Pre-authorize incident scopes.** Maintain standing collection authorizations for declared incidents so responders do not wait on paperwork mid-breach.
9. **Exercise regularly.** Run quarterly hunts using the artifact library so operators are fluent before a real incident demands speed.

## Expected outputs
- Hardened Velociraptor deployment with RBAC and audit logging.
- Approved artifact catalog mapped to investigation scenarios.
- Per-incident collection records with scope, approval, and chain of custody.
- Example: during a suspected intrusion, an approved hunt collects autoruns, recent files, and event logs from 300 endpoints in under an hour, with every collection tied to the incident ID and approver.

## Pitfalls
- Over-collection: pulling everything from every host creates privacy, legal, and storage problems.
- Weak access control on the server turns the IR tool into an attacker-equivalent capability.
- Collecting without a declared incident or approval erodes trust with system owners.

- Client version drift across the fleet leaving blind spots; track client versions and remediate stragglers like any patch gap.
- Running hunts that return huge result sets with no analysis plan; define what "done" looks like for each hunt before launching it.

## References
- Velociraptor documentation (docs.velociraptor.app).
- NIST SP 800-61 Rev. 2, Computer Security Incident Handling Guide.
- SANS FOR508 (sans.org) — enterprise incident response and threat hunting concepts.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
