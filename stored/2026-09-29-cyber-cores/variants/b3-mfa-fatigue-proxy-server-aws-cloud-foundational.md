---
skill_id: cyber_b3_mfa_fatigue_proxy_server_aws_cloud_foundational
name: MFA Fatigue Attack Defense for Proxy Servers in AWS Cloud (Foundational Maturity)
description: "MFA Fatigue Attack defense playbook for Proxy Servers in AWS Cloud at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, authentication, network, proxy, web, cloud, aws, maturity-foundational]
version: 1.0.0
---
# MFA Fatigue Attack Defense for Proxy Servers in AWS Cloud (Foundational Maturity)

## Purpose

Attackers with a stolen password spam push notifications until the victim approves one out of annoyance or confusion. The defense is push hygiene: number matching, context display, and rate limits on prompts. Applies to Proxy Servers in AWS Cloud at Foundational maturity.

## When to use

- Dozens of MFA push prompts to one user in minutes, especially at odd hours, followed by a single approval.
- An approval immediately followed by session activity from an unusual IP or device enrollment changes.
- Helpdesk reports of users 'getting lots of MFA prompts' in the days before the incident.
- Lens: Best telemetry: full URL logs with user identity + TLS SNI logs + block/allow verdicts. Organization CloudTrail in all regions, GuardDuty, and VPC flow logs shipped to the security account.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CloudWatch and workload logs centralized; S3 access logging on sensitive buckets.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Access logs (user, URL, category, verdict, bytes) for the incident window and Blocked-request logs showing attempted C2/malware/phishing destinations; run `grep <username> /var/log/squid/access.log | awk '{print $7}' | sort | uniq -c | sort -rn | head -20` then `grep -E 'TCP_DENIED|BLOCK' /var/log/squid/access.log | tail -30`.
3. **Analyze.** Reconstruct the prompt storm: count, timing, and the approving event — then inventory the attacker's post-approval actions. Then: Check whether the attacker registered a new MFA method during the session (persistence via second factor).
4. **Contain and harden.** Number matching on all push MFA, show login context (app, location), and rate-limit prompts per user. Asset layer: Authenticated proxying (no anonymous egress), category blocking, TLS inspection where policy allows. Environment layer: SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Assuming an approved push means a legitimate user — approval is exactly what the attacker engineered.
- Not checking for newly registered MFA methods, which survive password resets.

## References

- MITRE ATT&CK: T1621 (Credential Access: MFA Request Generation)
- Vendor logging and hardening baselines for Proxy Servers; SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
