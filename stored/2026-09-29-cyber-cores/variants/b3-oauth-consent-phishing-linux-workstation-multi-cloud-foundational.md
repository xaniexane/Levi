---
skill_id: cyber_b3_oauth_consent_phishing_linux_workstation_multi_cloud_foundational
name: OAuth Consent Phishing Defense for Linux Workstations in Multi-Cloud (Foundational Maturity)
description: "OAuth Consent Phishing defense playbook for Linux Workstations in Multi-Cloud at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, cloud, oauth, linux, endpoint, multi-cloud, maturity-foundational]
version: 1.0.0
---
# OAuth Consent Phishing Defense for Linux Workstations in Multi-Cloud (Foundational Maturity)

## Purpose

Users grant a malicious app OAuth permissions, giving the attacker persistent API access to mailbox, files, or directory — no password needed, survives password resets, invisible in logon logs. Applies to Linux Workstations in Multi-Cloud at Foundational maturity.

## When to use

- New enterprise app registrations or OAuth consent grants for apps with vague names, especially requesting Mail.Read or Files.ReadWrite.All.
- Consent grants by users outside any change process, or apps verified by unknown publishers.
- API-driven mailbox/file access patterns (Graph API) with no corresponding interactive logon.
- Lens: Best telemetry: auditd user-session logging + EDR agent + desktop shell histories (with user notice). Cloud-agnostic SIEM normalizing AWS CloudTrail, Azure Activity Log, and GCP Audit Logs into one schema.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CSPM coverage across all clouds with consistent misconfiguration alerting.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in User shell histories (~/.bash_history), desktop autostart entries (~/.config/autostart/) and auditd execve logs and USB device logs; browser profiles for web-vector cases; run `ls -la ~/.config/autostart/ 2>/dev/null; grep -r 'Exec=' ~/.config/autostart/ 2>/dev/null` then `sudo ausearch --start recent -m EXECVE -i | tail -30`.
3. **Analyze.** Inventory every permission the malicious app holds and every API call it made — the data accessed defines the breach. Then: Check for admin-consent abuse: was the app granted tenant-wide access by a compromised admin?
4. **Contain and harden.** Require admin consent for third-party apps; maintain an allowlist of approved publishers. Asset layer: Standard user accounts for daily work, full-disk encryption, and screen-lock enforcement. Environment layer: Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Resetting the user's password and declaring victory while the OAuth grant keeps working.
- Overlooking that the app may have been granted access by an ADMIN — scope tenant-wide, not per-user.

## References

- MITRE ATT&CK: T1528 (Credential Access: Steal Application Access Token)
- Vendor logging and hardening baselines for Linux Workstations; Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
