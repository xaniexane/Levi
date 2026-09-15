---
skill_id: cyber_conducting_pass_the_ticket_attack
name: Detecting Pass-the-Ticket Attacks
description: Defensive playbook for detecting Kerberos ticket reuse and forgery, and hardening Active Directory against ticket-based lateral movement.
risk: low
permissions: []
requires_confirmation: false
tags: [active-directory, detection, hardening]
version: 1.0.0
---
## Purpose
Pass-the-ticket reuses stolen Kerberos tickets to impersonate users without knowing their passwords, enabling stealthy lateral movement. This playbook is defensive: recognizing ticket-reuse anomalies in authentication logs, detecting forged tickets, and applying the hardening measures that limit ticket abuse. No offensive technique instruction is included.

## When to use
- Hunting for Kerberos-based lateral movement in an AD environment.
- Investigating alerts about anomalous ticket usage or impossible logons.
- Hardening Kerberos after a credential-theft incident or assessment finding.
- Validating that ticket-lifetime and auditing policies are effective.

## Prerequisites
- Kerberos operational and security event logging on domain controllers and key servers.
- Baseline of normal ticket lifetimes, renewal patterns, and service-ticket usage.
- SIEM correlation across authentication events and host logons.
- Authority to adjust Kerberos policy and investigate privileged accounts.

## Procedure
1. Enable comprehensive Kerberos logging. Ensure ticket-granting and service-ticket events are collected centrally with sufficient detail.
2. Baseline normal ticket behavior. Document typical ticket lifetimes, renewal rates, and which accounts request tickets for which services.
3. Hunt for reuse anomalies. Look for tickets used from unexpected hosts, concurrent use of the same ticket from multiple systems, and logons inconsistent with the ticket's user context.
4. Detect forgery indicators. Watch for tickets with anomalous lifetimes, encryption types inconsistent with policy, or privileged tickets issued to unusual accounts.
5. Correlate with host telemetry. Match suspicious ticket usage to process and logon events on the source hosts to confirm compromise.
6. Harden Kerberos policy. Reduce maximum ticket lifetimes, enforce AES encryption, and restrict delegation (prefer constrained or resource-based constrained delegation).
7. Protect ticket-granting material. Ensure KRBTGT and privileged account credentials are rotated after incidents; consider tiered administration to limit exposure.
8. Maintain detections. Keep ticket-anomaly rules tuned; re-baseline after infrastructure changes.

## Expected outputs
- Detections for ticket reuse and forgery anomalies.
- Hardened Kerberos policy with documented settings.
- Investigation findings if abuse is confirmed.

## Pitfalls
- Without detailed Kerberos logging, ticket attacks are nearly invisible; enable it first.
- Overly aggressive lifetime reductions break long-running legitimate processes; tune carefully.
- Alerting on every ticket anomaly without baselines floods analysts.
- Focusing on tickets while ignoring the credential theft that enabled them.

## References
- MITRE ATT&CK: T1558 (Steal or Forge Kerberos Tickets)
- Microsoft Learn: Kerberos policy and auditing guidance
- CISA guidance on Active Directory hardening
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
