---
skill_id: cyber_b3_password_spraying_vpn_gateway_aws_cloud_foundational
name: Password Spraying Defense for VPN Gateways in AWS Cloud (Foundational Maturity)
description: "Password Spraying defense playbook for VPN Gateways in AWS Cloud at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, authentication, network, vpn, remote-access, cloud, aws, maturity-foundational]
version: 1.0.0
---
# Password Spraying Defense for VPN Gateways in AWS Cloud (Foundational Maturity)

## Purpose

Attackers try a small set of common passwords against many usernames, staying under per-account lockout thresholds. It is quieter than stuffing and specifically tuned to evade lockout policies, often running for days or weeks. Applies to VPN Gateways in AWS Cloud at Foundational maturity.

## When to use

- A handful of failed logons per account (1-3) spread across hundreds of accounts from one or a few IPs, repeating on a schedule — the classic low-and-slow pattern.
- The same few passwords attempted everywhere (SeasonYear!, Company123, Password1); check by aggregating failed-logon password hashes where your IdP logs them.
- Spray bursts correlated with newly published password lists or timed to holidays/weekends when response is slower.
- Lens: Best telemetry: authentication logs + session logs (user, IP, bytes, duration) + gateway patch state. Organization CloudTrail in all regions, GuardDuty, and VPC flow logs shipped to the security account.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CloudWatch and workload logs centralized; S3 access logging on sensitive buckets.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in VPN auth logs (success/failure per user with source IPs), session tables with data volumes and Gateway admin audit log and firmware/patch version; client version inventory; run `# conceptually (vendor CLIs differ):` then `show vpn-sessiondb detail anyconnect | grep -E 'Username|Assigned IP|Login Time'`.
3. **Analyze.** Reconstruct the spray window: first-seen to last-seen per source IP, and list every account with even one success inside the window — those are confirmed or suspected takeovers. Then: Check whether sprayed accounts share traits (same OU, same onboarding batch, service accounts) to find how the username list was built.
4. **Contain and harden.** Smart lockout (soft lockout with increasing delays) plus alerting on distributed low-volume failures, not just lockouts. Asset layer: MFA on every VPN profile, device posture checks before granting access, gateway firmware patched urgently. Environment layer: SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Per-account lockout thresholds alone will not catch spraying; you need cross-account velocity detection.
- Treating one success as an isolated incident misses the campaign — always scope the full spray window.

## References

- MITRE ATT&CK: T1110.003 (Credential Access: Brute Force: Password Spraying)
- Vendor logging and hardening baselines for VPN Gateways; SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
