---
skill_id: cyber_coercing_authentication_with_coercer_petitpotam
name: Detecting Coerced Authentication and NTLM Relay Abuse
description: Defensive playbook for detecting authentication-coercion techniques (PetitPotam, Coercer-style) and hardening Active Directory against NTLM relay.
risk: low
permissions: []
requires_confirmation: false
tags: [active-directory, detection, hardening]
version: 1.0.0
---
## Purpose
Authentication-coercion techniques trick Windows servers into authenticating to an attacker-controlled host, enabling NTLM relay attacks that can lead to domain compromise. This playbook is purely defensive: recognizing coercion attempts in logs, detecting relay activity, and applying the hardening measures (SMB signing, EPA, patching) that neutralize the attack class. No offensive tooling guidance is included.

## When to use
- Hunting for NTLM relay or authentication-coercion activity in an AD environment.
- Responding to alerts about unusual EFSRPC, Print Spooler, or MS-RPRN traffic.
- Hardening Active Directory after a coercion-related pentest finding.
- Validating that relay mitigations are actually effective.

## Prerequisites
- Windows Security event logs (especially logon and NTLM auditing) centralized in the SIEM.
- Network visibility into SMB, RPC, and LDAP traffic between servers.
- Patch and configuration baseline for domain controllers and servers.
- Change window for enabling signing and protection settings.

## Procedure
1. Enable the right logging. Ensure NTLM auditing (operational logs), logon events (4624/4625 with logon types), and relevant RPC activity are collected.
2. Hunt for coercion indicators. Look for servers initiating outbound authentication to unexpected hosts, especially via EFSRPC or spooler-related RPC calls from non-admin contexts.
3. Detect relay patterns. Correlate rapid authentication sequences where a server's credentials appear used against a second target shortly after an inbound coercion attempt.
4. Inventory relay exposure. Identify where SMB signing is not required, where LDAP signing is off, and which web or AD CS endpoints lack Extended Protection for Authentication.
5. Patch coercion vectors. Apply Microsoft updates addressing PetitPotam-class issues; disable unnecessary services (Print Spooler on servers that do not need it).
6. Enforce signing and EPA. Require SMB signing, enforce LDAP signing and channel binding, and enable EPA on AD CS and other relay targets.
7. Reduce NTLM usage. Move applications to Kerberos where possible; audit and restrict NTLM authentication to lower relay opportunity.
8. Monitor continuously. Build detections for coercion RPC patterns and relay signatures; re-audit signing posture quarterly.

## Expected outputs
- Detections for authentication-coercion and relay activity.
- Hardening checklist with signing, EPA, and patch status per system.
- Reduced NTLM relay attack surface with verification evidence.

## Pitfalls
- Enabling signing without verifying clients support it breaks legacy applications; test first.
- Patching alone does not stop relay; signing and EPA are the durable fixes.
- NTLM auditing generates heavy volume; scope collection to key servers initially.
- Disabling the Print Spooler on systems that need it causes operational issues.

## References
- Microsoft security guidance on PetitPotam mitigations (ADV210003 and related)
- Microsoft Learn: NTLM auditing and SMB signing configuration
- MITRE ATT&CK: T1557 (Adversary-in-the-Middle), T1187 (Forced Authentication)
- CISA guidance on Active Directory hardening
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
