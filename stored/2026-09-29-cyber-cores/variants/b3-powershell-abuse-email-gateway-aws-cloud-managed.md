---
skill_id: cyber_b3_powershell_abuse_email_gateway_aws_cloud_managed
name: Malicious PowerShell Abuse Defense for Email Gateways in AWS Cloud (Managed Maturity)
description: "Malicious PowerShell Abuse defense playbook for Email Gateways in AWS Cloud at Managed maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, execution, email, phishing, cloud, aws, maturity-managed]
version: 1.0.0
---
# Malicious PowerShell Abuse Defense for Email Gateways in AWS Cloud (Managed Maturity)

## Purpose

PowerShell is the attacker's Swiss-army knife: encoded commands, in-memory execution, credential theft, lateral movement. Deep script-block and module logging turns it from a blind spot into one of your richest telemetry sources. Applies to Email Gateways in AWS Cloud at Managed maturity.

## When to use

- Event 4104 (script block logging) with encoded commands (-enc/-e), Invoke-Mimikatz/Invoke-Shellcode patterns, or obfuscation (heavy string concatenation, char codes).
- PowerShell spawned by Office, browsers, or WMI with hidden window styles, or AMSI bypass patterns in the script text.
- Module logging showing credential-access or AD-enumeration cmdlets from non-admin workstations.
- Lens: Best telemetry: message-tracking logs + sandbox verdicts + URL-rewrite click logs. Organization CloudTrail in all regions, GuardDuty, and VPC flow logs shipped to the security account.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CloudWatch and workload logs centralized; S3 access logging on sensitive buckets.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Message tracking (sender, recipients, subject hash, attachments, verdicts) for the campaign window and Sandbox detonation reports for attachments/URLs; quarantined message copies; run `# conceptually (gateway CLIs differ):` then `message-tracking --sender <suspect-domain> --last 7d`.
3. **Analyze.** Decode every obfuscated layer — the final script reveals the true objective (many 'downloaders' are actually ransomware staging). Then: Correlate the PowerShell session with its parent to find the delivery vector (macro, scheduled task, remote session).
4. **Contain and harden.** Enable script-block logging, module logging, and transcription fleet-wide; forward to the SIEM with alerting. Asset layer: Sandbox detonation for all attachments/links, DMARC p=reject on owned domains, banner external mail. Environment layer: SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).
5. **Document and improve.** Pre-authorize low-risk containment (host isolation, session revoke, password reset) in the SOAR playbook with full audit logging. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Logging PowerShell without a SIEM pipeline to analyze it — 4104 events are high-volume and useless unsearched.
- Assuming -noprofile -w hidden is always malicious; admins use it too — baseline first.

## References

- MITRE ATT&CK: T1059.001 (Execution: PowerShell)
- Vendor logging and hardening baselines for Email Gateways; SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
