---
skill_id: cyber_b3_asreproasting_message_queue_aws_cloud_foundational
name: ASREPRoasting Defense for Message Queues in AWS Cloud (Foundational Maturity)
description: "ASREPRoasting defense playbook for Message Queues in AWS Cloud at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, active-directory, messaging, application, cloud, aws, maturity-foundational]
version: 1.0.0
---
# ASREPRoasting Defense for Message Queues in AWS Cloud (Foundational Maturity)

## Purpose

Accounts with Kerberos pre-authentication disabled can have their AS-REP responses requested by anyone and cracked offline — no authentication needed at all. One misconfigured user account is enough. Applies to Message Queues in AWS Cloud at Foundational maturity.

## When to use

- 4768 (TGT request) events where pre-authentication was not used, from external or unexpected hosts, for accounts flagged DONT_REQ_PREAUTH.
- Enumeration of such accounts (LDAP queries for userAccountControl flags) preceding the roast requests.
- Later logons with the cracked credentials from attacker hosts.
- Lens: Best telemetry: queue depth/lag metrics + producer/consumer auth logs + dead-letter queues. Organization CloudTrail in all regions, GuardDuty, and VPC flow logs shipped to the security account.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CloudWatch and workload logs centralized; S3 access logging on sensitive buckets.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Queue metrics: depth spikes, consumer lag, and poison-message dead-letter queues and Authentication logs for producers/consumers; new queue/topic creation events; run `rabbitmqctl list_queues name messages consumers 2>/dev/null | head -20` then `kafka-consumer-groups --bootstrap-server <broker> --describe --all-groups 2>/dev/null | head -20`.
3. **Analyze.** Enumerate all accounts with pre-auth disabled (the full roast-able population) — the fix is one checkbox per account, so find them all. Then: Check whether any of those accounts are privileged or service accounts; prioritize accordingly.
4. **Contain and harden.** Enable Kerberos pre-authentication on every account; audit for the flag regularly — it gets re-disabled by legacy app troubleshooting. Asset layer: Authentication on all clients, TLS in transit, authorization per queue/topic, quotas on producers. Environment layer: SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Fixing the roasted account but not scanning for the other 40 accounts with the same misconfiguration.
- Assuming pre-auth-disabled accounts are always legacy — verify before re-enabling to avoid breaking production auth.

## References

- MITRE ATT&CK: T1558.004 (Credential Access: AS-REP Roasting)
- Vendor logging and hardening baselines for Message Queues; SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
