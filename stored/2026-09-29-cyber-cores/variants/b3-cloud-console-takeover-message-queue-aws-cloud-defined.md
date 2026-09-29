---
skill_id: cyber_b3_cloud_console_takeover_message_queue_aws_cloud_defined
name: Cloud Console Takeover Defense for Message Queues in AWS Cloud (Defined Maturity)
description: "Cloud Console Takeover defense playbook for Message Queues in AWS Cloud at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [cloud, identity, messaging, application, aws, maturity-defined]
version: 1.0.0
---
# Cloud Console Takeover Defense for Message Queues in AWS Cloud (Defined Maturity)

## Purpose

Stolen cloud credentials used in the web console give attackers point-and-click infrastructure control. Console logons from unusual locations followed by IAM changes are the classic takeover sequence. Applies to Message Queues in AWS Cloud at Defined maturity.

## When to use

- CloudTrail/Entra sign-in logs showing console logons from new countries or anonymizing services for privileged users.
- IAM policy changes, new access keys, or new users created within minutes of the anomalous logon.
- Disabling of CloudTrail/logging or deletion of log data — the attacker covering tracks.
- Lens: Best telemetry: queue depth/lag metrics + producer/consumer auth logs + dead-letter queues. Organization CloudTrail in all regions, GuardDuty, and VPC flow logs shipped to the security account.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CloudWatch and workload logs centralized; S3 access logging on sensitive buckets.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Queue metrics: depth spikes, consumer lag, and poison-message dead-letter queues and Authentication logs for producers/consumers; new queue/topic creation events; run `rabbitmqctl list_queues name messages consumers 2>/dev/null | head -20` then `kafka-consumer-groups --bootstrap-server <broker> --describe --all-groups 2>/dev/null | head -20`.
3. **Analyze.** Reconstruct the full API call sequence after takeover: what was created, modified, exfiltrated, or destroyed. Then: Check for persistence: new IAM users, roles with trust policies pointing outward, or modified instance user-data.
4. **Contain and harden.** Phishing-resistant MFA on all console users, especially root/ break-glass; SCPs preventing logging disablement. Asset layer: Authentication on all clients, TLS in transit, authorization per queue/topic, quotas on producers. Environment layer: SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Rotating the compromised user's keys but missing the backdoor IAM role the attacker created.
- Trusting the account's own logs after the attacker had admin — verify against the immutable archive.

## References

- MITRE ATT&CK: T1078 (Persistence: Valid Accounts) — cloud console
- Vendor logging and hardening baselines for Message Queues; SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
