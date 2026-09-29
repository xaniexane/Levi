---
skill_id: cyber_b3_mfa_fatigue_email_gateway_on_prem_datacenter_developing
name: MFA Fatigue Attack Defense for Email Gateways in On-Premises Datacenter (Developing Maturity)
description: "MFA Fatigue Attack defense playbook for Email Gateways in On-Premises Datacenter at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, authentication, email, phishing, on-prem, datacenter, maturity-developing]
version: 1.0.0
---
# MFA Fatigue Attack Defense for Email Gateways in On-Premises Datacenter (Developing Maturity)

## Purpose

Attackers with a stolen password spam push notifications until the victim approves one out of annoyance or confusion. The defense is push hygiene: number matching, context display, and rate limits on prompts. Applies to Email Gateways in On-Premises Datacenter at Developing maturity.

## When to use

- Dozens of MFA push prompts to one user in minutes, especially at odd hours, followed by a single approval.
- An approval immediately followed by session activity from an unusual IP or device enrollment changes.
- Helpdesk reports of users 'getting lots of MFA prompts' in the days before the incident.
- Lens: Best telemetry: message-tracking logs + sandbox verdicts + URL-rewrite click logs. Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Centralized syslog from all infrastructure with NTP-synced timestamps for cross-device correlation.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Message tracking (sender, recipients, subject hash, attachments, verdicts) for the campaign window and Sandbox detonation reports for attachments/URLs; quarantined message copies; run `# conceptually (gateway CLIs differ):` then `message-tracking --sender <suspect-domain> --last 7d`.
3. **Analyze.** Reconstruct the prompt storm: count, timing, and the approving event — then inventory the attacker's post-approval actions. Then: Check whether the attacker registered a new MFA method during the session (persistence via second factor).
4. **Contain and harden.** Number matching on all push MFA, show login context (app, location), and rate-limit prompts per user. Asset layer: Sandbox detonation for all attachments/links, DMARC p=reject on owned domains, banner external mail. Environment layer: Physical access controls with badge logs correlatable to logical access during investigations.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Assuming an approved push means a legitimate user — approval is exactly what the attacker engineered.
- Not checking for newly registered MFA methods, which survive password resets.

## References

- MITRE ATT&CK: T1621 (Credential Access: MFA Request Generation)
- Vendor logging and hardening baselines for Email Gateways; Physical access controls with badge logs correlatable to logical access during investigations.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
