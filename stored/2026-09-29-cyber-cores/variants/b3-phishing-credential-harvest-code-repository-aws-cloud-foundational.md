---
skill_id: cyber_b3_phishing_credential_harvest_code_repository_aws_cloud_foundational
name: Phishing Credential Harvest Defense for Code Repositories in AWS Cloud (Foundational Maturity)
description: "Phishing Credential Harvest defense playbook for Code Repositories in AWS Cloud at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [email, phishing, devops, supply-chain, secrets, cloud, aws, maturity-foundational]
version: 1.0.0
---
# Phishing Credential Harvest Defense for Code Repositories in AWS Cloud (Foundational Maturity)

## Purpose

Users are lured to lookalike login pages (often via adversary-in-the-middle kits that relay MFA) and submit credentials. The defender's job: find who clicked, who submitted, and whether sessions were hijacked even where MFA appeared to hold. Applies to Code Repositories in AWS Cloud at Foundational maturity.

## When to use

- Email gateway logs show a burst of messages with lookalike domains, newly registered domains, or QR-code lures pointing at a credential-harvest kit URL.
- Proxy/DNS logs show visits to the kit domain followed within minutes by logons from unusual IPs or impossible-travel pairs for the same user.
- AiTM kits leave telltales: logon session created without a matching MFA challenge event, or token replay from datacenter IP ranges.
- Lens: Best telemetry: push/audit logs + secret-scanning alerts + branch-protection change history. Organization CloudTrail in all regions, GuardDuty, and VPC flow logs shipped to the security account.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CloudWatch and workload logs centralized; S3 access logging on sensitive buckets.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Push logs (who pushed what to which branch), force-push and history-rewrite records and Secret-scanning and code-scanning alerts with their resolution state; run `git log --since='7 days ago' --format='%h %an %ad %s' --date=short | head -30` then `git log --all --diff-filter=A -- '*secret*' '*credential*' '*key*' --format='%h %an %s' | head -20`.
3. **Analyze.** Pull the kit URL from the email, fetch it in a sandbox, and extract the credential-post endpoint and any session-cookie exfiltration to scope which submissions completed. Then: For each submitter, check for concurrent sessions: revoke all refresh tokens and list OAuth app consents granted in the phish window.
4. **Contain and harden.** Move to phishing-resistant MFA (FIDO2/WebAuthn); TOTP and push MFA fall to AiTM relay. Asset layer: Branch protection with required reviews, signed commits, push protection for secrets. Environment layer: SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Resetting the password without revoking sessions leaves the attacker logged in via stolen tokens.
- Blaming the clicker instead of fixing the control gap guarantees a repeat with a better lure.

## References

- MITRE ATT&CK: T1566.002 (Initial Access: Phishing: Spearphishing Link)
- Vendor logging and hardening baselines for Code Repositories; SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
