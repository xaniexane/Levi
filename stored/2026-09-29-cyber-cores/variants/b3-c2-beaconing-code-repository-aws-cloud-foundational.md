---
skill_id: cyber_b3_c2_beaconing_code_repository_aws_cloud_foundational
name: C2 Beaconing Defense for Code Repositories in AWS Cloud (Foundational Maturity)
description: "C2 Beaconing defense playbook for Code Repositories in AWS Cloud at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [network, c2, devops, supply-chain, secrets, cloud, aws, maturity-foundational]
version: 1.0.0
---
# C2 Beaconing Defense for Code Repositories in AWS Cloud (Foundational Maturity)

## Purpose

Compromised hosts check in with attacker infrastructure on a schedule — the heartbeat of an intrusion. Beaconing detection is statistical: regularity, jitter analysis, and connection uniformity reveal what signatures miss. Applies to Code Repositories in AWS Cloud at Foundational maturity.

## When to use

- Outbound connections at fixed intervals (e.g., every 60s) with consistent byte counts to an external host — visible in NetFlow or proxy logs as metronomic traffic.
- Long-lived sessions to IPs with no domain, newly registered domains, or domains with no legitimate business purpose.
- Jittered but statistically regular timing: inter-arrival times clustering around a mean with small variance.
- Lens: Best telemetry: push/audit logs + secret-scanning alerts + branch-protection change history. Organization CloudTrail in all regions, GuardDuty, and VPC flow logs shipped to the security account.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CloudWatch and workload logs centralized; S3 access logging on sensitive buckets.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Push logs (who pushed what to which branch), force-push and history-rewrite records and Secret-scanning and code-scanning alerts with their resolution state; run `git log --since='7 days ago' --format='%h %an %ad %s' --date=short | head -30` then `git log --all --diff-filter=A -- '*secret*' '*credential*' '*key*' --format='%h %an %s' | head -20`.
3. **Analyze.** Compute inter-arrival statistics on the suspect flows; true beacons show low variance even with jitter, unlike human browsing. Then: Capture the beacon payload in a sandbox detonation to identify the implant family and its tasking protocol.
4. **Contain and harden.** Egress filtering: default-deny outbound with allowlisted destinations for servers; alert on direct-to-IP connections. Asset layer: Branch protection with required reviews, signed commits, push protection for secrets. Environment layer: SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Chasing the C2 IP instead of the implant — infrastructure is disposable, the foothold is what matters.
- Assuming encrypted traffic cannot be analyzed: timing, size, and destination metadata still betray beacons.

## References

- MITRE ATT&CK: T1071.001 (Command and Control: Web Protocols)
- Vendor logging and hardening baselines for Code Repositories; SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
