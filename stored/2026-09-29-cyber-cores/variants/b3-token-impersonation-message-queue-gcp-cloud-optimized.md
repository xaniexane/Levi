---
skill_id: cyber_b3_token_impersonation_message_queue_gcp_cloud_optimized
name: Token Impersonation Defense for Message Queues in GCP Cloud (Optimized Maturity)
description: "Token Impersonation defense playbook for Message Queues in GCP Cloud at Optimized maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, privilege-escalation, messaging, application, cloud, gcp, maturity-optimized]
version: 1.0.0
---
# Token Impersonation Defense for Message Queues in GCP Cloud (Optimized Maturity)

## Purpose

Attackers steal or duplicate Windows access tokens to act as another user — often SYSTEM — without knowing any password. EDR sees odd parent/child relationships and token-privilege enabling that legitimate software rarely performs. Applies to Message Queues in GCP Cloud at Optimized maturity.

## When to use

- Processes enabling SeDebugPrivilege or SeImpersonatePrivilege outside of known admin tooling, or unexpected token duplication API sequences in EDR telemetry.
- A low-privilege process spawning children as SYSTEM or as another logged-on user without a legitimate service path.
- Named-pipe impersonation patterns (PrintSpooler-style) from non-printer processes.
- Lens: Best telemetry: queue depth/lag metrics + producer/consumer auth logs + dead-letter queues. Cloud Audit Logs (admin + data access) exported to a locked-down logging project.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Security Command Center findings and VPC flow logs centralized.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Queue metrics: depth spikes, consumer lag, and poison-message dead-letter queues and Authentication logs for producers/consumers; new queue/topic creation events; run `rabbitmqctl list_queues name messages consumers 2>/dev/null | head -20` then `kafka-consumer-groups --bootstrap-server <broker> --describe --all-groups 2>/dev/null | head -20`.
3. **Analyze.** Trace the token source: which process's token was stolen, and did that source process itself get compromised first? Then: Check what the impersonated context accessed — file, registry, and network actions taken as the victim identity.
4. **Contain and harden.** Remove SeImpersonatePrivilege from service accounts that do not need it; patch print-spooler-class vulnerabilities promptly. Asset layer: Authentication on all clients, TLS in transit, authorization per queue/topic, quotas on producers. Environment layer: Organization policies constraining public exposure, API enablement, and service-account key creation.
5. **Document and improve.** Feed incident lessons back into detection-as-code within one sprint — the playbook is a living document, not a PDF. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Assuming token theft requires admin — some impersonation primitives work from lower privilege.
- Missing that a stolen token can be replayed on OTHER hosts via remote authentication.

## References

- MITRE ATT&CK: T1134 (Privilege Escalation: Access Token Manipulation)
- Vendor logging and hardening baselines for Message Queues; Organization policies constraining public exposure, API enablement, and service-account key creation.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
